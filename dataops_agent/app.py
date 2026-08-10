"""FastAPI composition root for the standalone DataOps Agent."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import duckdb
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .data import DuckDBRepository, execute_readonly_sql, load_records
from .knowledge import ElasticsearchHybridRetriever, HybridRetriever
from .settings import Settings
from .tasks import AuditTask, AuditWorker, DuckDBTaskStore, InMemoryTaskQueue, RedisStreamsTaskQueue, TaskQueue, TaskStore


class IngestionRequest(BaseModel):
    batch_id: str
    records: list[dict[str, object]] = Field(default_factory=list)


class SqlRequest(BaseModel):
    sql: str


class AuditRequest(BaseModel):
    batch_id: str
    metadata: dict[str, object] = Field(default_factory=dict)


@dataclass(slots=True)
class AppDependencies:
    repository: Any
    retriever: Any
    task_store: TaskStore
    task_queue: TaskQueue
    load_records: Callable[..., object] = load_records
    execute_sql: Callable[[Any, str], list[dict[str, object]]] = execute_readonly_sql
    audit_worker: AuditWorker | None = None


def create_app(dependencies: AppDependencies | None = None, *, settings: Settings | None = None) -> FastAPI:
    """Create an app with explicit adapters, defaulting to local in-memory ones."""
    dependencies = dependencies or _default_dependencies(settings or Settings.from_env())
    app = FastAPI(title="DataOps Agent", version="0.1.0")
    app.state.dataops = dependencies

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest")
    @app.post("/ingestion")
    def ingest(request: IngestionRequest) -> dict[str, object]:
        summary = dependencies.load_records(
            request.records, batch_id=request.batch_id, repository=dependencies.repository
        )
        return _json_object(summary)

    @app.post("/audit", status_code=202)
    def audit(request: AuditRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
        task = AuditTask(batch_id=request.batch_id, metadata=request.metadata)
        task_id = dependencies.task_queue.enqueue(task)
        if dependencies.audit_worker is not None:
            background_tasks.add_task(dependencies.audit_worker.run_once)
        return {"task_id": task_id, "status": "queued"}

    @app.get("/tasks/{task_id}")
    @app.get("/tasks/{task_id}/progress")
    def task_progress(task_id: str) -> dict[str, object]:
        try:
            return _json_object(dependencies.task_store.progress(task_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Task not found") from error

    @app.post("/sql")
    def sql(request: SqlRequest) -> dict[str, object]:
        try:
            return {"rows": dependencies.execute_sql(dependencies.repository, request.sql)}
        except (ValueError, duckdb.Error) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/knowledge")
    def knowledge(
        query: str,
        limit: int = Query(default=10, ge=1, le=100),
        filters: str | None = None,
    ) -> dict[str, object]:
        parsed_filters = _parse_filters(filters)
        chunks = dependencies.retriever.search(query, filters=parsed_filters, limit=limit)
        return {"chunks": [_json_object(chunk) for chunk in chunks]}

    return app


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
    retriever: Any = HybridRetriever([])
    if settings.elasticsearch_url:
        retriever = ElasticsearchHybridRetriever(
            index=settings.elasticsearch_index,
            url=settings.elasticsearch_url,
        )
    return AppDependencies(
        repository=repository,
        retriever=retriever,
        task_store=store,
        task_queue=queue,
        audit_worker=worker,
    )


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


app = create_app()
