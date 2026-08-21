from __future__ import annotations

import json
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from dataops_agent.app import AppDependencies, create_app
from dataops_agent.data import DuckDBRepository
from dataops_agent.knowledge import ElasticsearchHybridRetriever
from dataops_agent.router import Route, route_request
from dataops_agent.settings import Settings
from dataops_agent.runtime import JsonlTracer
from dataops_agent.tasks import (
    AuditTask,
    AuditWorker,
    DuckDBTaskStore,
    InMemoryTaskQueue,
    InMemoryTaskStore,
    RedisStreamsTaskQueue,
    TaskStatus,
)


class FakeRepository:
    pass


class FakeRetriever:
    def search(self, query: str, *, filters: dict[str, object] | None, limit: int):
        return [
            type(
                "Chunk",
                (),
                {"id": "guide-1", "content": f"Guide for {query}", "metadata": {"kind": "guide"}},
            )()
        ][:limit]


def test_route_request_selects_deterministic_routes() -> None:
    assert route_request("find record invoice-1") is Route.LOOKUP
    assert route_request("select * from records") is Route.SQL
    assert route_request("search the runbook for ingestion") is Route.KNOWLEDGE
    assert route_request("run a data quality audit") is Route.AUDIT
    assert route_request("make a plan for the migration") is Route.PLAN


def test_route_request_matches_keywords_at_word_boundaries() -> None:
    assert route_request("research the invoice record") is Route.LOOKUP


def test_route_request_classifies_dataops_intents_beyond_explicit_tool_names() -> None:
    assert route_request("count orders grouped by customer state") is Route.SQL
    assert route_request("show records for customer state SP") is Route.SQL
    assert route_request("what is the definition of a late order") is Route.KNOWLEDGE
    assert route_request("inspect batch batch-42 for anomalies") is Route.AUDIT
    assert route_request("run a batch inspection for batch-43") is Route.AUDIT
    assert route_request("first ingest the file, then audit it and summarize the result") is Route.PLAN
    assert route_request("ingest the file and then summarize quality") is Route.PLAN


def test_fastapi_endpoints_use_injected_fakes(monkeypatch) -> None:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=queue,
        load_records=lambda records, *, batch_id, repository: {
            "batch_id": batch_id,
            "received": len(records),
            "loaded": len(records),
            "duplicates": 0,
            "quarantined": 0,
            "skipped": False,
        },
        execute_sql=lambda repository, sql: [{"record_id": "record-1"}],
    )
    client = TestClient(create_app(dependencies))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.post(
        "/ingest",
        headers={"Idempotency-Key": "ingest-b-1"},
        json={"batch_id": "b-1", "records": [{"record_id": "r-1"}]},
    ).json()["loaded"] == 1
    assert client.post("/sql", json={"sql": "SELECT * FROM records"}).json() == {"rows": [{"record_id": "record-1"}]}
    assert client.get("/knowledge", params={"query": "ingestion"}).json()["chunks"][0]["id"] == "guide-1"

    created = client.post("/audit", headers={"Idempotency-Key": "audit-b-1"}, json={"batch_id": "b-1"})
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    progress = client.get(f"/tasks/{task_id}").json()
    assert progress["status"] == TaskStatus.QUEUED.value


def test_csv_ingestion_parses_raw_text_body_and_uses_existing_etl_tool() -> None:
    received: dict[str, object] = {}
    store = InMemoryTaskStore()

    def capture_load(records, *, batch_id, repository):
        received.update(batch_id=batch_id, records=list(records), repository=repository)
        return {
            "batch_id": batch_id,
            "received": 2,
            "loaded": 2,
            "duplicates": 0,
            "quarantined": 0,
            "skipped": False,
        }

    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
        load_records=capture_load,
    )
    client = TestClient(create_app(dependencies))

    response = client.post(
        "/ingest/csv",
        params={"batch_id": "csv-demo"},
        content='record_id,source,note\r\nr-1,demo,"has, comma"\r\nr-2,demo,plain\r\n',
        headers={"Content-Type": "text/csv", "Idempotency-Key": "csv-demo-ingest"},
    )

    assert response.status_code == 200
    assert response.json()["loaded"] == 2
    assert received == {
        "batch_id": "csv-demo",
        "records": [
            {"record_id": "r-1", "source": "demo", "note": "has, comma"},
            {"record_id": "r-2", "source": "demo", "note": "plain"},
        ],
        "repository": dependencies.repository,
    }


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ("", "CSV body is empty"),
        ("record_id,source\r\n", "CSV must contain at least one data row"),
        ('record_id,source\r\n"r-1,demo\r\n', "CSV is malformed"),
    ],
    ids=["empty", "header-only", "malformed-quote"],
)
def test_csv_ingestion_rejects_empty_or_malformed_csv(body: str, detail: str) -> None:
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
        load_records=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("invalid CSV must not reach ETL")
        ),
    )
    client = TestClient(create_app(dependencies), raise_server_exceptions=False)

    response = client.post(
        "/ingest/csv",
        params={"batch_id": "csv-demo"},
        content=body,
        headers={"Content-Type": "text/csv", "Idempotency-Key": "invalid-csv"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": detail}


def test_csv_ingestion_rejects_a_blank_batch_id_before_etl() -> None:
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
        load_records=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("blank batch id must not reach ETL")
        ),
    )
    client = TestClient(create_app(dependencies), raise_server_exceptions=False)

    response = client.post(
        "/ingest/csv",
        params={"batch_id": "   "},
        content="record_id,source\r\nr-1,demo\r\n",
        headers={"Content-Type": "text/csv", "Idempotency-Key": "blank-csv"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "batch_id must not be blank"}


def test_app_uses_lazy_elasticsearch_retriever_only_when_configured() -> None:
    app = create_app(settings=Settings(elasticsearch_url="http://search.example:9200"))

    assert isinstance(app.state.dataops.retriever, ElasticsearchHybridRetriever)


def test_default_app_creates_database_parent_and_uses_durable_task_store(tmp_path) -> None:
    database_path = tmp_path / "nested" / "dataops.duckdb"

    app = create_app(settings=Settings(database_path=str(database_path)))

    assert database_path.exists()
    assert type(app.state.dataops.task_store).__name__ == "DuckDBTaskStore"


def test_audit_request_reaches_a_terminal_progress_state(tmp_path) -> None:
    client = TestClient(create_app(settings=Settings(database_path=str(tmp_path / "agent.duckdb"))))

    created = client.post("/audit", headers={"Idempotency-Key": "audit-b-1"}, json={"batch_id": "b-1"})
    progress = client.get(f"/tasks/{created.json()['task_id']}")

    assert created.status_code == 202
    assert progress.json()["status"] == TaskStatus.COMPLETED.value
    assert progress.json()["percent"] == 100


def test_file_backed_api_ingest_then_audit_reaches_terminal_progress(tmp_path) -> None:
    client = TestClient(
        create_app(settings=Settings(database_path=str(tmp_path / "ingest-audit.duckdb"))),
        raise_server_exceptions=False,
    )

    ingested = client.post(
        "/ingest",
        headers={"Idempotency-Key": "ingest-b-1"},
        json={"batch_id": "b-1", "records": [{"record_id": "r-1", "source": "test"}]},
    )
    created = client.post("/audit", headers={"Idempotency-Key": "audit-b-1"}, json={"batch_id": "b-1"})

    assert ingested.status_code == 200
    assert created.status_code == 202
    progress = client.get(f"/tasks/{created.json()['task_id']}")
    assert progress.json()["status"] == TaskStatus.COMPLETED.value


def test_file_backed_request_idempotency_survives_a_second_app_dependencies_instance(tmp_path) -> None:
    """A transport retry after an API restart must reuse the first durable result.

    The second app deliberately has fresh Python objects.  It therefore catches
    regressions where replay protection only lives in a process-local dict.
    """
    database_path = tmp_path / "restart-idempotency.duckdb"

    def file_backed_dependencies() -> AppDependencies:
        repository = DuckDBRepository(str(database_path))
        store = DuckDBTaskStore(repository)
        queue = InMemoryTaskQueue(store)
        return AppDependencies(
            repository=repository,
            retriever=FakeRetriever(),
            task_store=store,
            task_queue=queue,
            audit_worker=AuditWorker(queue=queue, store=store, repository=repository),
        )

    first_client = TestClient(create_app(file_backed_dependencies()))
    ingest_headers = {"Idempotency-Key": "ingest-after-restart"}
    ingest_body = {"batch_id": "first-batch", "records": [{"record_id": "r-1", "source": "demo"}]}

    first_ingest = first_client.post("/ingest", headers=ingest_headers, json=ingest_body)
    first_audit = first_client.post(
        "/audit",
        headers={"Idempotency-Key": "audit-after-restart"},
        json={"batch_id": "first-batch", "metadata": {"source": "demo"}},
    )
    assert first_ingest.status_code == 200
    assert first_audit.status_code == 202

    second_client = TestClient(create_app(file_backed_dependencies()))
    replayed_ingest = second_client.post("/ingest", headers=ingest_headers, json=ingest_body)
    conflicting_ingest = second_client.post(
        "/ingest",
        headers=ingest_headers,
        json={"batch_id": "second-batch", "records": [{"record_id": "r-2", "source": "other"}]},
    )
    replayed_audit = second_client.post(
        "/audit",
        headers={"Idempotency-Key": "audit-after-restart"},
        json={"batch_id": "first-batch", "metadata": {"source": "demo"}},
    )
    conflicting_audit = second_client.post(
        "/audit",
        headers={"Idempotency-Key": "audit-after-restart"},
        json={"batch_id": "second-batch", "metadata": {"source": "other"}},
    )

    assert replayed_ingest.status_code == 200
    assert replayed_ingest.json() == first_ingest.json()
    assert conflicting_ingest.status_code == 409
    assert replayed_audit.status_code == 202
    assert replayed_audit.json() == first_audit.json()
    assert conflicting_audit.status_code == 409
    assert second_client.post(
        "/sql", json={"sql": "SELECT COUNT(*) AS total FROM records"}
    ).json() == {"rows": [{"total": 1}]}


def test_default_local_knowledge_contains_a_deterministic_audit_rule(tmp_path) -> None:
    """The no-Elasticsearch quick start must still return useful audit guidance."""
    client = TestClient(create_app(settings=Settings(database_path=str(tmp_path / "local-knowledge.duckdb"))))

    response = client.get(
        "/knowledge",
        params={
            "query": "schema validation quality audit rule",
            "filters": '{"kind":"audit-rule"}',
        },
    )

    assert response.status_code == 200
    assert response.json()["chunks"][0]["id"] == "local-audit-schema-validation"
    assert response.json()["chunks"][0]["metadata"] == {
        "kind": "audit-rule",
        "retrieval_mode": "local_deterministic",
        "source": "built_in",
    }


def test_audit_idempotency_key_returns_original_task_id() -> None:
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
    )
    client = TestClient(create_app(dependencies))
    headers = {"Idempotency-Key": "audit-batch-1"}

    first = client.post("/audit", headers=headers, json={"batch_id": "b-1"})
    repeated = client.post("/audit", headers=headers, json={"batch_id": "b-1"})

    assert repeated.json()["task_id"] == first.json()["task_id"]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/ingest", {"batch_id": "b-1", "records": [{"record_id": "r-1"}]}),
        ("/audit", {"batch_id": "b-1"}),
    ],
    ids=["ingest", "audit"],
)
def test_mutating_endpoints_require_a_nonblank_idempotency_key(path: str, payload: dict[str, object]) -> None:
    """Removing the request guard would let a transport retry create duplicate mutations."""
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
        load_records=lambda records, *, batch_id, repository: {"loaded": len(records)},
    )
    client = TestClient(create_app(dependencies))

    missing = client.post(path, json=payload)
    blank = client.post(path, headers={"Idempotency-Key": "   "}, json=payload)

    assert missing.status_code == 400
    assert blank.status_code == 400
    assert missing.json() == {"detail": "Idempotency-Key header is required"}
    assert blank.json() == {"detail": "Idempotency-Key header is required"}


def test_ingest_replay_returns_original_result_without_a_second_etl_call() -> None:
    """A replay must be served from the idempotency record, not rely only on batch-level ETL skips."""
    calls = 0
    store = InMemoryTaskStore()

    def load_once(records, *, batch_id, repository):
        nonlocal calls
        calls += 1
        return {"batch_id": batch_id, "loaded": len(records), "attempt": calls}

    client = TestClient(
        create_app(
            AppDependencies(
                repository=FakeRepository(),
                retriever=FakeRetriever(),
                task_store=store,
                task_queue=InMemoryTaskQueue(store),
                load_records=load_once,
            )
        )
    )
    headers = {"Idempotency-Key": "ingest-one"}
    body = {"batch_id": "b-1", "records": [{"record_id": "r-1"}]}

    first = client.post("/ingest", headers=headers, json=body)
    replay = client.post("/ingest", headers=headers, json=body)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == {"batch_id": "b-1", "loaded": 1, "attempt": 1}
    assert calls == 1


def test_mutation_rejects_reusing_an_idempotency_key_for_a_different_payload() -> None:
    """A key collision must not silently run a different mutation or return the wrong response."""
    store = InMemoryTaskStore()
    client = TestClient(
        create_app(
            AppDependencies(
                repository=FakeRepository(),
                retriever=FakeRetriever(),
                task_store=store,
                task_queue=InMemoryTaskQueue(store),
                load_records=lambda records, *, batch_id, repository: {"batch_id": batch_id, "loaded": len(records)},
            )
        )
    )
    headers = {"Idempotency-Key": "collision-key"}

    assert client.post("/ingest", headers=headers, json={"batch_id": "b-1", "records": []}).status_code == 200
    collision = client.post("/ingest", headers=headers, json={"batch_id": "b-2", "records": []})

    assert collision.status_code == 409
    assert collision.json() == {"detail": "Idempotency-Key was already used for a different request"}


def test_local_audit_background_task_drains_all_fresh_work(monkeypatch) -> None:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: {"schema_valid_rate": 1.0},
    )
    existing_id = queue.enqueue(AuditTask(batch_id="existing"))
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=queue,
        audit_worker=worker,
    )
    client = TestClient(create_app(dependencies))

    created = client.post("/audit", headers={"Idempotency-Key": "audit-fresh"}, json={"batch_id": "fresh"})

    assert store.progress(existing_id).status is TaskStatus.COMPLETED
    assert store.progress(created.json()["task_id"]).status is TaskStatus.COMPLETED


def test_redis_stream_audit_is_drained_by_the_owning_api_process(monkeypatch) -> None:
    """A second process must not consume a DuckDB-backed task stream; the API drains it in-process."""
    class FreshOnlyRedis:
        def __init__(self) -> None:
            self.entries: list[tuple[str, dict[str, object]]] = []
            self.acknowledged: list[tuple[object, ...]] = []

        def xgroup_create(self, *args, **kwargs) -> None:
            return None

        def xadd(self, stream, fields) -> str:
            self.entries.append(("1-0", fields))
            return "1-0"

        def xautoclaim(self, **kwargs):
            return ["0-0", [], []]

        def xreadgroup(self, **kwargs):
            if not self.entries:
                return []
            entry_id, fields = self.entries.pop(0)
            return [("dataops:audit", [(entry_id, fields)])]

        def xack(self, *args) -> int:
            self.acknowledged.append(args)
            return 1

    store = InMemoryTaskStore()
    redis = FreshOnlyRedis()
    queue = RedisStreamsTaskQueue(store, client=redis)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: {"schema_valid_rate": 1.0},
    )
    client = TestClient(
        create_app(
            AppDependencies(
                repository=FakeRepository(),
                retriever=FakeRetriever(),
                task_store=store,
                task_queue=queue,
                audit_worker=worker,
            )
        )
    )

    response = client.post(
        "/audit",
        headers={"Idempotency-Key": "redis-same-process"},
        json={"batch_id": "b-1"},
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert store.progress(task_id).status is TaskStatus.COMPLETED
    assert redis.acknowledged == [("dataops:audit", "dataops-workers", "1-0")]


def test_redis_publish_failure_returns_pending_then_is_recovered_by_the_api_lifecycle(tmp_path) -> None:
    """The API owns recovery: no second client request is needed after a transient XADD failure."""

    class GatedFailOnceRedis:
        def __init__(self) -> None:
            self.publish_attempts = 0
            self.entries: list[tuple[str, dict[str, object]]] = []
            self.allow_recovery = Event()
            self.acknowledged: list[tuple[object, ...]] = []

        def xgroup_create(self, *args, **kwargs) -> None:
            return None

        def xadd(self, stream, fields) -> str:
            self.publish_attempts += 1
            if self.publish_attempts == 1:
                raise ConnectionError("redis unavailable")
            assert self.allow_recovery.wait(timeout=1), "test must observe pending state before recovery"
            entry_id = f"{self.publish_attempts}-0"
            self.entries.append((entry_id, fields))
            return entry_id

        def xautoclaim(self, **kwargs):
            return ["0-0", [], []]

        def xreadgroup(self, **kwargs):
            if not self.entries:
                return []
            entry_id, fields = self.entries.pop(0)
            return [("dataops:audit", [(entry_id, fields)])]

        def xack(self, *args) -> int:
            self.acknowledged.append(args)
            return 1

    database_path = tmp_path / "pending-publish.duckdb"
    repository = DuckDBRepository(str(database_path))
    store = DuckDBTaskStore(repository)
    redis = GatedFailOnceRedis()
    queue = RedisStreamsTaskQueue(store, client=redis)
    worker = AuditWorker(queue=queue, store=store, repository=repository)
    dependencies = AppDependencies(
        repository=repository,
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=queue,
        audit_worker=worker,
    )

    with TestClient(create_app(dependencies)) as client:
        accepted = client.post(
            "/audit",
            headers={"Idempotency-Key": "recover-without-retry"},
            json={"batch_id": "batch-1"},
        )

        assert accepted.status_code == 202
        assert accepted.json()["status"] == TaskStatus.PENDING_PUBLISH.value
        task_id = accepted.json()["task_id"]
        assert store.progress(task_id).status is TaskStatus.PENDING_PUBLISH

        redis.allow_recovery.set()
        deadline = monotonic() + 2
        while monotonic() < deadline and store.progress(task_id).status is not TaskStatus.COMPLETED:
            sleep(0.01)

        assert store.progress(task_id).status is TaskStatus.COMPLETED
        assert redis.publish_attempts >= 2
        assert redis.acknowledged


def test_route_endpoint_and_tool_endpoints_emit_redacted_traces(tmp_path) -> None:
    trace_path = tmp_path / "api.jsonl"
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=FakeRepository(),
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
        tracer=JsonlTracer(trace_path),
        load_records=lambda records, *, batch_id, repository: {
            "batch_id": batch_id,
            "loaded": len(records),
        },
        execute_sql=lambda repository, sql: [{"authorization": "Bearer result-secret"}],
    )
    client = TestClient(create_app(dependencies))
    trace_headers = {"X-Trace-ID": "trace-123", "X-Session-ID": "session-123"}

    routed = client.post("/route", headers=trace_headers, json={"text": "count records by source"})
    client.post(
        "/ingest",
        headers={**trace_headers, "Idempotency-Key": "ingest-trace"},
        json={
            "batch_id": "trace-batch",
            "records": [{"record_id": "r-1", "nested": {"x-api-key": "secret-key"}}],
        },
    )
    client.post("/audit", headers={**trace_headers, "Idempotency-Key": "audit-trace"}, json={"batch_id": "trace-batch"})
    client.post("/sql", headers=trace_headers, json={"sql": "SELECT 'Basic c2VjcmV0' AS authorization"})
    client.get("/knowledge", headers=trace_headers, params={"query": "Bearer query-secret"})

    assert routed.json() == {"route": "sql"}
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert {event["tool_name"] for event in events} == {"route", "ingest", "audit", "sql", "knowledge"}
    for event in events:
        assert event["trace_id"] == "trace-123"
        assert event["session_id"] == "session-123"
        assert isinstance(event["call_id"], str) and event["call_id"]
        assert event["status"] == "completed"
        assert isinstance(event["elapsed_ms"], int) and event["elapsed_ms"] >= 0
        assert event["retry_count"] == 0
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "secret-key" not in trace_text
    assert "result-secret" not in trace_text
    assert "query-secret" not in trace_text


def test_a_successful_mutation_is_fail_open_when_the_trace_sink_is_unavailable() -> None:
    """An observability outage must not turn a durable user mutation into a 500 response."""
    class BrokenTracer:
        def emit(self, event):
            raise OSError("trace disk unavailable")

    store = InMemoryTaskStore()
    client = TestClient(
        create_app(
            AppDependencies(
                repository=FakeRepository(),
                retriever=FakeRetriever(),
                task_store=store,
                task_queue=InMemoryTaskQueue(store),
                tracer=BrokenTracer(),
                load_records=lambda records, *, batch_id, repository: {"loaded": len(records)},
            )
        ),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/ingest",
        headers={"Idempotency-Key": "trace-failure"},
        json={"batch_id": "b-1", "records": [{"record_id": "r-1"}]},
    )

    assert response.status_code == 200
    assert response.json() == {"loaded": 1}


def test_sql_endpoint_returns_bad_request_for_duckdb_syntax_errors() -> None:
    repository = DuckDBRepository()
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=repository,
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
    )
    client = TestClient(create_app(dependencies), raise_server_exceptions=False)

    response = client.post("/sql", json={"sql": "SELECT FROM"})

    assert response.status_code == 400


def test_sql_endpoint_rejects_table_statement_for_unlisted_table() -> None:
    repository = DuckDBRepository()
    repository.connection.execute("CREATE TABLE secret(value VARCHAR)")
    repository.connection.execute("INSERT INTO secret VALUES ('leak')")
    store = InMemoryTaskStore()
    dependencies = AppDependencies(
        repository=repository,
        retriever=FakeRetriever(),
        task_store=store,
        task_queue=InMemoryTaskQueue(store),
    )
    client = TestClient(create_app(dependencies))

    response = client.post("/sql", json={"sql": "WITH x AS (TABLE secret) SELECT * FROM x"})

    assert response.status_code == 400
