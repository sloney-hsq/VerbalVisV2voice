"""FastAPI composition root for the standalone DataOps Agent."""

from __future__ import annotations

import csv
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import field
from hashlib import sha256
import io
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from threading import Condition, Event, RLock, Thread
from time import perf_counter, sleep
from typing import Any, Callable, Mapping
from uuid import uuid4

import duckdb
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .data import DuckDBRepository, execute_readonly_sql, load_records
from .knowledge import ElasticsearchHybridRetriever, HybridRetriever, KnowledgeChunk
from .router import route_request
from .runtime import JsonlTracer
from .settings import Settings
from .tasks import (
    AuditTask,
    AuditWorker,
    DuckDBTaskStore,
    InMemoryTaskQueue,
    RedisStreamsTaskQueue,
    TaskQueue,
    TaskStatus,
    TaskStore,
)


class IngestionRequest(BaseModel):
    batch_id: str
    records: list[dict[str, object]] = Field(default_factory=list)


class SqlRequest(BaseModel):
    sql: str


class AuditRequest(BaseModel):
    batch_id: str
    metadata: dict[str, object] = Field(default_factory=dict)


class RoutedRequest(BaseModel):
    text: str = Field(min_length=1)


class IdempotencyConflictError(ValueError):
    """A caller reused a key for a semantically different mutation."""


class RequestIdempotencyStore:
    """Thread-safe replay protection for HTTP mutations within one app process.

    The ETL batch identifier remains the durable ingestion key. This request
    layer prevents a transport retry from entering the handler twice before
    callers observe that durable batch result.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], tuple[str, dict[str, object] | None]] = {}
        self._changed = Condition(RLock())

    def execute(
        self,
        *,
        scope: str,
        key: str,
        payload: Mapping[str, object],
        operation: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        record_key = (scope, key)
        fingerprint = _request_fingerprint(payload)
        with self._changed:
            while True:
                existing = self._records.get(record_key)
                if existing is None:
                    self._records[record_key] = (fingerprint, None)
                    break
                stored_fingerprint, cached_response = existing
                if stored_fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used for a different request"
                    )
                if cached_response is not None:
                    return deepcopy(cached_response)
                self._changed.wait()

        try:
            response = operation()
        except Exception:
            # Failures remain safely retryable under the same request key.
            with self._changed:
                self._records.pop(record_key, None)
                self._changed.notify_all()
            raise

        with self._changed:
            self._records[record_key] = (fingerprint, deepcopy(response))
            self._changed.notify_all()
        return response


class DurableRequestIdempotencyStore:
    """Replay protection persisted beside a file-backed DataOps database.

    It records the request fingerprint and the first JSON result.  That keeps
    HTTP retries correct after a new FastAPI dependency graph is constructed,
    while the in-memory implementation remains convenient for injected fakes.
    """

    _POLL_SECONDS = 0.01
    _WAIT_SECONDS = 30.0

    def __init__(self, database_path: str | Path) -> None:
        self._connection = duckdb.connect(str(database_path))
        self._lock = RLock()
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS request_idempotency (
                scope VARCHAR NOT NULL,
                idempotency_key VARCHAR NOT NULL,
                fingerprint VARCHAR NOT NULL,
                response JSON,
                PRIMARY KEY (scope, idempotency_key)
            )
            """
        )

    def execute(
        self,
        *,
        scope: str,
        key: str,
        payload: Mapping[str, object],
        operation: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        fingerprint = _request_fingerprint(payload)
        owner = self._claim_or_replay(scope=scope, key=key, fingerprint=fingerprint)
        if not owner[0]:
            return owner[1]

        try:
            response = operation()
        except Exception:
            with self._lock:
                self._connection.execute(
                    """
                    DELETE FROM request_idempotency
                    WHERE scope = ? AND idempotency_key = ? AND fingerprint = ? AND response IS NULL
                    """,
                    [scope, key, fingerprint],
                )
            raise

        encoded = json.dumps(response, sort_keys=True, default=str)
        with self._lock:
            self._connection.execute(
                """
                UPDATE request_idempotency
                SET response = ?
                WHERE scope = ? AND idempotency_key = ? AND fingerprint = ?
                """,
                [encoded, scope, key, fingerprint],
            )
        return deepcopy(response)

    def _claim_or_replay(
        self, *, scope: str, key: str, fingerprint: str
    ) -> tuple[bool, dict[str, object]]:
        deadline = perf_counter() + self._WAIT_SECONDS
        while True:
            with self._lock:
                row = self._connection.execute(
                    """
                    SELECT fingerprint, response
                    FROM request_idempotency
                    WHERE scope = ? AND idempotency_key = ?
                    """,
                    [scope, key],
                ).fetchone()
                if row is None:
                    try:
                        self._connection.execute(
                            """
                            INSERT INTO request_idempotency (scope, idempotency_key, fingerprint, response)
                            VALUES (?, ?, ?, NULL)
                            """,
                            [scope, key, fingerprint],
                        )
                    except duckdb.ConstraintException:
                        # Another app instance won the durable claim. Re-read
                        # rather than executing the mutation a second time.
                        continue
                    return True, {}
                if row[0] != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used for a different request"
                    )
                if row[1] is not None:
                    return False, json.loads(row[1])
            if perf_counter() >= deadline:
                raise RuntimeError("Timed out waiting for the original idempotent request")
            sleep(self._POLL_SECONDS)


class _InProcessWorkerLifecycle:
    """Own the Redis delivery worker inside the only DuckDB-writing API process."""

    def __init__(self, worker: AuditWorker) -> None:
        self._worker = worker
        self._stop_requested = Event()
        self._thread = Thread(target=self._run, name="dataops-audit-recovery", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        self._worker.run_forever(
            poll_interval_seconds=0.05,
            should_continue=lambda: not self._stop_requested.is_set(),
            sleep=lambda seconds: self._stop_requested.wait(seconds),
        )


@dataclass(slots=True)
class AppDependencies:
    repository: Any
    retriever: Any
    task_store: TaskStore
    task_queue: TaskQueue
    load_records: Callable[..., object] = load_records
    execute_sql: Callable[[Any, str], list[dict[str, object]]] = execute_readonly_sql
    audit_worker: AuditWorker | None = None
    tracer: JsonlTracer | None = None
    idempotency_store: RequestIdempotencyStore = field(default_factory=RequestIdempotencyStore)


def create_app(dependencies: AppDependencies | None = None, *, settings: Settings | None = None) -> FastAPI:
    """Create an app with explicit adapters, defaulting to local in-memory ones."""
    dependencies = dependencies or _default_dependencies(settings or Settings.from_env())
    _promote_file_backed_idempotency_store(dependencies)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        lifecycle = (
            _InProcessWorkerLifecycle(dependencies.audit_worker)
            if dependencies.audit_worker is not None
            and isinstance(dependencies.task_queue, RedisStreamsTaskQueue)
            else None
        )
        if lifecycle is not None:
            lifecycle.start()
        try:
            yield
        finally:
            if lifecycle is not None:
                lifecycle.stop()

    app = FastAPI(title="DataOps Agent", version="0.1.0", lifespan=lifespan)
    app.state.dataops = dependencies

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest")
    @app.post("/ingestion")
    def ingest(
        request: IngestionRequest,
        http_request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        key = _require_idempotency_key(idempotency_key)
        payload = {"batch_id": request.batch_id, "records": request.records}
        return _trace_tool(
            dependencies,
            "ingest",
            payload,
            lambda: _run_idempotent_mutation(
                dependencies,
                scope="ingest",
                key=key,
                payload=payload,
                operation=lambda: _json_object(
                    dependencies.load_records(
                        request.records,
                        batch_id=request.batch_id,
                        repository=dependencies.repository,
                    )
                )
            ),
            trace_context=_trace_context(http_request),
        )

    @app.post("/ingest/csv")
    async def ingest_csv(
        request: Request,
        batch_id: str = Query(...),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        try:
            validated_batch_id = _validate_batch_id(batch_id)
            records = _parse_csv_records(await request.body())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _trace_tool(
            dependencies,
            "ingest",
            {"batch_id": validated_batch_id, "format": "csv", "records": records},
            lambda: _run_idempotent_mutation(
                dependencies,
                scope="ingest",
                key=_require_idempotency_key(idempotency_key),
                payload={"batch_id": validated_batch_id, "format": "csv", "records": records},
                operation=lambda: _json_object(
                    dependencies.load_records(
                        records,
                        batch_id=validated_batch_id,
                        repository=dependencies.repository,
                    )
                )
            ),
            trace_context=_trace_context(request),
        )

    @app.post("/audit", status_code=202)
    def audit(
        request: AuditRequest,
        background_tasks: BackgroundTasks,
        http_request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        key = _require_idempotency_key(idempotency_key)
        payload = {"batch_id": request.batch_id, "metadata": request.metadata}

        def submit() -> dict[str, object]:
            task = AuditTask(
                batch_id=request.batch_id,
                metadata=request.metadata,
                idempotency_key=key,
            )
            task_id = dependencies.task_queue.enqueue(task)
            progress = dependencies.task_store.progress(task_id)
            if (
                dependencies.audit_worker is not None
                and progress.status is not TaskStatus.PENDING_PUBLISH
            ):
                # DuckDB remains a single-process writer topology. Redis is an
                # inter-thread delivery queue here, not a separately runnable
                # worker service sharing this database file.
                background_tasks.add_task(dependencies.audit_worker.run_until_empty)
            return {
                "task_id": task_id,
                "status": progress.status.value,
            }

        return _trace_tool(
            dependencies,
            "audit",
            {
                "batch_id": request.batch_id,
                "metadata": request.metadata,
                "idempotency_key": key,
            },
            lambda: _run_idempotent_mutation(
                dependencies,
                scope="audit",
                key=key,
                payload=payload,
                operation=submit,
            ),
            trace_context=_trace_context(http_request),
        )

    @app.get("/tasks/{task_id}")
    @app.get("/tasks/{task_id}/progress")
    def task_progress(task_id: str) -> dict[str, object]:
        try:
            return _json_object(dependencies.task_store.progress(task_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Task not found") from error

    @app.post("/sql")
    def sql(request: SqlRequest, http_request: Request) -> dict[str, object]:
        try:
            return _trace_tool(
                dependencies,
                "sql",
                {"sql": request.sql},
                lambda: {"rows": dependencies.execute_sql(dependencies.repository, request.sql)},
                trace_context=_trace_context(http_request),
            )
        except (ValueError, duckdb.Error) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/knowledge")
    def knowledge(
        http_request: Request,
        query: str,
        limit: int = Query(default=10, ge=1, le=100),
        filters: str | None = None,
    ) -> dict[str, object]:
        parsed_filters = _parse_filters(filters)
        return _trace_tool(
            dependencies,
            "knowledge",
            {"query": query, "filters": parsed_filters, "limit": limit},
            lambda: {
                "chunks": [
                    _json_object(chunk)
                    for chunk in dependencies.retriever.search(
                        query, filters=parsed_filters, limit=limit
                    )
                ]
            },
            trace_context=_trace_context(http_request),
        )

    @app.post("/route")
    def route(request: RoutedRequest, http_request: Request) -> dict[str, str]:
        return _trace_tool(
            dependencies,
            "route",
            {"text": request.text},
            lambda: {"route": route_request(request.text).value},
            trace_context=_trace_context(http_request),
        )

    return app


def _promote_file_backed_idempotency_store(dependencies: AppDependencies) -> None:
    """Make explicitly injected file-backed dependencies restart-safe as well.

    Tests and production composition sometimes inject their own repository and
    task adapters.  A process-local default is correct for fake/in-memory
    adapters but would silently weaken idempotency for that file-backed path.
    """
    database_path = getattr(dependencies.repository, "_database_path", None)
    if database_path is not None and isinstance(dependencies.idempotency_store, RequestIdempotencyStore):
        dependencies.idempotency_store = DurableRequestIdempotencyStore(database_path)


def _default_dependencies(settings: Settings) -> AppDependencies:
    _ensure_database_parent(settings.database_path)
    repository = DuckDBRepository(settings.database_path)
    store = DuckDBTaskStore(repository)
    queue: TaskQueue
    if settings.redis_url:
        queue = RedisStreamsTaskQueue(
            store,
            url=settings.redis_url,
            stream=settings.redis_stream,
            group=settings.redis_group,
        )
    else:
        queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=repository)
    retriever: Any = HybridRetriever(_local_audit_rule_chunks())
    if settings.elasticsearch_url:
        retriever = ElasticsearchHybridRetriever(
            index=settings.elasticsearch_index,
            url=settings.elasticsearch_url,
        )
    trace_path = os.getenv("DATAOPS_TRACE_PATH")
    return AppDependencies(
        repository=repository,
        retriever=retriever,
        task_store=store,
        task_queue=queue,
        audit_worker=worker,
        tracer=JsonlTracer(trace_path) if trace_path else None,
        idempotency_store=DurableRequestIdempotencyStore(settings.database_path)
    )


def _local_audit_rule_chunks() -> list[KnowledgeChunk]:
    """Provide a deterministic, dependency-free quick-start knowledge result.

    This is lexical local retrieval only.  It intentionally makes no vector or
    semantic-search claim when Elasticsearch is not configured.
    """
    return [
        KnowledgeChunk(
            id="local-audit-schema-validation",
            content=(
                "Audit rule: validate every ingested record against the expected schema before "
                "calculating data quality metrics. Quarantine malformed records, report the "
                "schema_valid_rate, and keep the batch identifier in the audit result."
            ),
            metadata={
                "kind": "audit-rule",
                "retrieval_mode": "local_deterministic",
                "source": "built_in",
            },
        )
    ]


def _ensure_database_parent(database_path: str) -> None:
    if database_path == ":memory:":
        return
    Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _parse_filters(filters: str | None) -> dict[str, object] | None:
    if filters is None:
        return None
    try:
        parsed = json.loads(filters)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="filters must be a JSON object") from error
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="filters must be a JSON object")
    return parsed


def _json_object(value: object) -> dict[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        raw = asdict(value)
    elif isinstance(value, Mapping):
        raw = dict(value)
    else:
        raw = dict(vars(value))
        for name in ("id", "content", "metadata"):
            if name not in raw and hasattr(value, name):
                raw[name] = getattr(value, name)
    if hasattr(value, "percent"):
        raw["percent"] = getattr(value, "percent")
    return {key: item.value if hasattr(item, "value") else item for key, item in raw.items()}


def _validate_batch_id(batch_id: str) -> str:
    normalized = batch_id.strip()
    if not normalized:
        raise ValueError("batch_id must not be blank")
    return normalized


def _parse_csv_records(body: bytes) -> list[dict[str, str]]:
    if not body:
        raise ValueError("CSV body is empty")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must be UTF-8 encoded") from error
    if not text.strip():
        raise ValueError("CSV body is empty")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise ValueError("CSV is malformed") from error
    if not rows:
        raise ValueError("CSV body is empty")
    headers = [header.strip() for header in rows[0]]
    if not headers or any(not header for header in headers) or len(set(headers)) != len(headers):
        raise ValueError("CSV header is malformed")
    data_rows = rows[1:]
    if not data_rows:
        raise ValueError("CSV must contain at least one data row")
    if any(len(row) != len(headers) for row in data_rows):
        raise ValueError("CSV is malformed")
    return [dict(zip(headers, row)) for row in data_rows]


def _require_idempotency_key(value: str | None) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    return value.strip()


def _request_fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _run_idempotent_mutation(
    dependencies: AppDependencies,
    *,
    scope: str,
    key: str,
    payload: Mapping[str, object],
    operation: Callable[[], dict[str, object]],
) -> dict[str, object]:
    try:
        return dependencies.idempotency_store.execute(
            scope=scope,
            key=key,
            payload=payload,
            operation=operation,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _trace_context(request: Request) -> dict[str, object]:
    trace_id = request.headers.get("X-Trace-ID", "").strip() or str(uuid4())
    session_id = request.headers.get("X-Session-ID", "").strip() or "anonymous"
    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "call_id": str(uuid4()),
        "retry_count": 0,
    }


def _trace_tool(
    dependencies: AppDependencies,
    tool_name: str,
    payload: Mapping[str, object],
    operation: Callable[[], dict[str, object]],
    *,
    trace_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    started_at = perf_counter()
    event_context = dict(trace_context or _default_trace_context())
    try:
        result = operation()
    except Exception as error:
        _emit_trace(
            dependencies,
            {
                **event_context,
                "event": "tool.failed",
                "tool_name": tool_name,
                "status": "failed",
                "elapsed_ms": _elapsed_ms(started_at),
                "input": payload,
                "error": str(error),
            },
        )
        raise
    _emit_trace(
        dependencies,
        {
            **event_context,
            "event": "tool.completed",
            "tool_name": tool_name,
            "status": "completed",
            "elapsed_ms": _elapsed_ms(started_at),
            "input": payload,
            "result": result,
        },
    )
    return result


def _default_trace_context() -> dict[str, object]:
    return {
        "trace_id": str(uuid4()),
        "session_id": "anonymous",
        "call_id": str(uuid4()),
        "retry_count": 0,
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _emit_trace(dependencies: AppDependencies, event: Mapping[str, object]) -> None:
    if dependencies.tracer is None:
        return
    try:
        dependencies.tracer.emit(event)
    except Exception:
        # Observability cannot turn an otherwise valid request into a 500.
        return


app = create_app()
