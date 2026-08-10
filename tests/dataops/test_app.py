from __future__ import annotations

from fastapi.testclient import TestClient

from dataops_agent.app import AppDependencies, create_app
from dataops_agent.data import DuckDBRepository
from dataops_agent.knowledge import ElasticsearchHybridRetriever
from dataops_agent.router import Route, route_request
from dataops_agent.settings import Settings
from dataops_agent.tasks import InMemoryTaskQueue, InMemoryTaskStore, TaskStatus


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
    assert client.post("/ingest", json={"batch_id": "b-1", "records": [{"record_id": "r-1"}]}).json()["loaded"] == 1
    assert client.post("/sql", json={"sql": "SELECT * FROM records"}).json() == {"rows": [{"record_id": "record-1"}]}
    assert client.get("/knowledge", params={"query": "ingestion"}).json()["chunks"][0]["id"] == "guide-1"

    created = client.post("/audit", json={"batch_id": "b-1"})
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    progress = client.get(f"/tasks/{task_id}").json()
    assert progress["status"] == TaskStatus.QUEUED.value


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

    created = client.post("/audit", json={"batch_id": "b-1"})
    progress = client.get(f"/tasks/{created.json()['task_id']}")

    assert created.status_code == 202
    assert progress.json()["status"] == TaskStatus.COMPLETED.value
    assert progress.json()["percent"] == 100


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
