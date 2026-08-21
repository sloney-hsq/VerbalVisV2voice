"""Queue and state adapters for audit work."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, runtime_checkable

import duckdb

from .models import AuditTask, TaskProgress, TaskStatus


@runtime_checkable
class TaskStore(Protocol):
    def create(
        self, task: AuditTask, *, initial_status: TaskStatus = TaskStatus.QUEUED
    ) -> TaskProgress: ...
    def task(self, task_id: str) -> AuditTask: ...
    def queued(self, task_id: str) -> TaskProgress: ...
    def start(self, task_id: str) -> TaskProgress: ...
    def complete(self, task_id: str, *, result: Mapping[str, object]) -> TaskProgress: ...
    def fail(self, task_id: str, *, error: str) -> TaskProgress: ...
    def progress(self, task_id: str) -> TaskProgress: ...
    def pending_publish_tasks(self) -> list[AuditTask]: ...


@runtime_checkable
class TaskQueue(Protocol):
    def enqueue(self, task: AuditTask) -> str: ...
    def dequeue(self) -> AuditTask | None: ...
    def acknowledge(self, task: AuditTask) -> None: ...


class InMemoryTaskStore:
    """A deterministic task store intended for local development and tests."""

    def __init__(self) -> None:
        self._progress: dict[str, TaskProgress] = {}
        self._tasks: dict[str, AuditTask] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = RLock()

    def create(
        self, task: AuditTask, *, initial_status: TaskStatus = TaskStatus.QUEUED
    ) -> TaskProgress:
        with self._lock:
            if task.idempotency_key is not None:
                existing_id = self._idempotency.get(task.idempotency_key)
                if existing_id is not None:
                    return self._progress[existing_id]
            if task.task_id in self._progress:
                raise ValueError(f"Task already exists: {task.task_id}")
            progress = TaskProgress(task_id=task.task_id, status=initial_status)
            self._progress[task.task_id] = progress
            self._tasks[task.task_id] = task
            if task.idempotency_key is not None:
                self._idempotency[task.idempotency_key] = task.task_id
            return progress

    def task(self, task_id: str) -> AuditTask:
        with self._lock:
            try:
                return self._tasks[task_id]
            except KeyError as error:
                raise KeyError(f"Unknown task: {task_id}") from error

    def queued(self, task_id: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.PENDING_PUBLISH},
            status=TaskStatus.QUEUED,
        )

    def start(self, task_id: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.PENDING_PUBLISH, TaskStatus.QUEUED},
            status=TaskStatus.RUNNING,
        )

    def complete(self, task_id: str, *, result: Mapping[str, object]) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.RUNNING},
            status=TaskStatus.COMPLETED,
            completed=1,
            result=dict(result),
        )

    def fail(self, task_id: str, *, error: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.RUNNING},
            status=TaskStatus.FAILED,
            error=error,
        )

    def progress(self, task_id: str) -> TaskProgress:
        with self._lock:
            try:
                return self._progress[task_id]
            except KeyError as error:
                raise KeyError(f"Unknown task: {task_id}") from error

    def pending_publish_tasks(self) -> list[AuditTask]:
        with self._lock:
            return [
                task
                for task_id, task in self._tasks.items()
                if self._progress[task_id].status is TaskStatus.PENDING_PUBLISH
            ]

    def _transition(
        self,
        task_id: str,
        *,
        allowed: set[TaskStatus],
        status: TaskStatus,
        completed: int = 0,
        result: Mapping[str, object] | None = None,
        error: str | None = None,
    ) -> TaskProgress:
        with self._lock:
            current = self.progress(task_id)
            if current.status not in allowed:
                raise ValueError(f"Cannot transition task {task_id} from {current.status}")
            updated = TaskProgress(
                task_id=task_id,
                status=status,
                completed=completed,
                total=current.total,
                result=result,
                error=error,
            )
            self._progress[task_id] = updated
            return updated


class DuckDBTaskStore:
    """Durable audit progress stored alongside the agent's DuckDB data."""

    def __init__(self, repository: Any) -> None:
        self._lock = RLock()
        database_path = getattr(repository, "_database_path", None)
        if database_path is not None:
            self._connection = duckdb.connect(str(Path(database_path)))
            self._owns_connection = True
        elif isinstance(repository, (str, Path)) and str(repository) != ":memory:":
            self._connection = duckdb.connect(str(repository))
            self._owns_connection = True
        else:
            self._connection = repository.connection
            self._owns_connection = False
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_tasks (
                task_id VARCHAR PRIMARY KEY,
                batch_id VARCHAR NOT NULL,
                requested_at TIMESTAMP WITH TIME ZONE NOT NULL,
                metadata JSON NOT NULL,
                status VARCHAR NOT NULL,
                completed INTEGER NOT NULL,
                total INTEGER NOT NULL,
                result JSON,
                error VARCHAR,
                idempotency_key VARCHAR
            )
            """
        )
        columns = {
            row[1] for row in self._connection.execute("PRAGMA table_info('audit_tasks')").fetchall()
        }
        if "idempotency_key" not in columns:
            self._connection.execute("ALTER TABLE audit_tasks ADD COLUMN idempotency_key VARCHAR")
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS audit_tasks_idempotency_key "
            "ON audit_tasks(idempotency_key)"
        )

    def create(
        self, task: AuditTask, *, initial_status: TaskStatus = TaskStatus.QUEUED
    ) -> TaskProgress:
        with self._lock:
            if task.idempotency_key is not None:
                existing = self._connection.execute(
                    "SELECT task_id FROM audit_tasks WHERE idempotency_key = ?",
                    [task.idempotency_key],
                ).fetchone()
                if existing is not None:
                    return self.progress(existing[0])
            try:
                self.progress(task.task_id)
            except KeyError:
                try:
                    self._connection.execute(
                        """
                        INSERT INTO audit_tasks
                        (task_id, batch_id, requested_at, metadata, status, completed, total,
                         result, error, idempotency_key)
                        VALUES (?, ?, ?, ?, ?, 0, 1, NULL, NULL, ?)
                        """,
                        [
                            task.task_id,
                            task.batch_id,
                            task.requested_at,
                            json.dumps(dict(task.metadata), sort_keys=True, default=str),
                            initial_status.value,
                            task.idempotency_key,
                        ],
                    )
                except duckdb.ConstraintException:
                    if task.idempotency_key is None:
                        raise
                    existing = self._connection.execute(
                        "SELECT task_id FROM audit_tasks WHERE idempotency_key = ?",
                        [task.idempotency_key],
                    ).fetchone()
                    if existing is None:
                        raise
                    return self.progress(existing[0])
                return self.progress(task.task_id)
            raise ValueError(f"Task already exists: {task.task_id}")

    def task(self, task_id: str) -> AuditTask:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT task_id, batch_id, CAST(requested_at AS VARCHAR), metadata, idempotency_key
                FROM audit_tasks WHERE task_id = ?
                """,
                [task_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown task: {task_id}")
            return AuditTask(
                task_id=row[0],
                batch_id=row[1],
                requested_at=datetime.fromisoformat(row[2]),
                metadata=json.loads(row[3]),
                idempotency_key=row[4],
            )

    def queued(self, task_id: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.PENDING_PUBLISH},
            status=TaskStatus.QUEUED,
        )

    def start(self, task_id: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.PENDING_PUBLISH, TaskStatus.QUEUED},
            status=TaskStatus.RUNNING,
        )

    def complete(self, task_id: str, *, result: Mapping[str, object]) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.RUNNING},
            status=TaskStatus.COMPLETED,
            completed=1,
            result=result,
        )

    def fail(self, task_id: str, *, error: str) -> TaskProgress:
        return self._transition(
            task_id,
            allowed={TaskStatus.RUNNING},
            status=TaskStatus.FAILED,
            error=error,
        )

    def progress(self, task_id: str) -> TaskProgress:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT task_id, status, completed, total, result, error
                FROM audit_tasks WHERE task_id = ?
                """,
                [task_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown task: {task_id}")
            result = json.loads(row[4]) if row[4] is not None else None
            return TaskProgress(
                task_id=row[0],
                status=TaskStatus(row[1]),
                completed=row[2],
                total=row[3],
                result=result,
                error=row[5],
            )

    def pending_publish_tasks(self) -> list[AuditTask]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT task_id, batch_id, CAST(requested_at AS VARCHAR), metadata, idempotency_key
                FROM audit_tasks
                WHERE status = ?
                ORDER BY requested_at, task_id
                """,
                [TaskStatus.PENDING_PUBLISH.value],
            ).fetchall()
            return [
                AuditTask(
                    task_id=row[0],
                    batch_id=row[1],
                    requested_at=datetime.fromisoformat(row[2]),
                    metadata=json.loads(row[3]),
                    idempotency_key=row[4],
                )
                for row in rows
            ]

    def _transition(
        self,
        task_id: str,
        *,
        allowed: set[TaskStatus],
        status: TaskStatus,
        completed: int = 0,
        result: Mapping[str, object] | None = None,
        error: str | None = None,
    ) -> TaskProgress:
        with self._lock:
            current = self.progress(task_id)
            if current.status not in allowed:
                raise ValueError(f"Cannot transition task {task_id} from {current.status}")
            self._connection.execute(
                """
                UPDATE audit_tasks
                SET status = ?, completed = ?, result = ?, error = ?
                WHERE task_id = ?
                """,
                [
                    status.value,
                    completed,
                    json.dumps(dict(result), sort_keys=True, default=str) if result is not None else None,
                    error,
                    task_id,
                ],
            )
            return self.progress(task_id)


class InMemoryTaskQueue:
    """FIFO queue which creates progress records at enqueue time."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store
        self._tasks: deque[AuditTask] = deque()

    def enqueue(self, task: AuditTask) -> str:
        progress = self._store.create(task)
        if progress.task_id == task.task_id:
            self._tasks.append(task)
        return progress.task_id

    def dequeue(self) -> AuditTask | None:
        return self._tasks.popleft() if self._tasks else None

    def acknowledge(self, task: AuditTask) -> None:
        return None


class RedisStreamsTaskQueue:
    """Optional Redis Streams queue with consumer-group ACK and stale reclaim."""

    def __init__(
        self,
        store: TaskStore,
        *,
        client: Any | None = None,
        url: str | None = None,
        stream: str = "dataops:audit",
        group: str = "dataops-workers",
        consumer: str = "worker-1",
        reclaim_idle_ms: int = 60_000,
    ) -> None:
        self._store = store
        self._client = client
        self._url = url
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self.reclaim_idle_ms = reclaim_idle_ms
        self._groups_ready = False
        self._inflight: dict[str, str] = {}

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self._url:
                raise RuntimeError("Redis Streams requires a URL or injected client")
            try:
                import redis
            except ImportError as error:  # pragma: no cover - depends on optional install
                raise RuntimeError("Install redis to use RedisStreamsTaskQueue") from error
            self._client = redis.Redis.from_url(self._url, decode_responses=False)
        return self._client

    def enqueue(self, task: AuditTask) -> str:
        progress = self._store.create(task, initial_status=TaskStatus.PENDING_PUBLISH)
        if progress.status is TaskStatus.PENDING_PUBLISH:
            try:
                self._publish_pending_task(self._store.task(progress.task_id))
            except Exception:
                # The caller can truthfully report accepted/pending work while
                # the worker lifecycle retries the durable outbox entry.
                pass
        return progress.task_id

    def recover_pending(self) -> int:
        """Republish durable outbox records without requiring an HTTP retry.

        Redis publication and DuckDB persistence cannot be made atomic.  The
        durable ``pending_publish`` state is therefore a small transactional
        outbox: after a transient XADD failure, the owning API process retries
        it from its in-process worker loop.  A duplicated XADD is safe because
        the worker checks the durable task status before executing an audit.
        """
        recovered = 0
        for task in self._store.pending_publish_tasks():
            try:
                self._publish_pending_task(task)
            except Exception:
                continue
            recovered += 1
        return recovered

    def _publish_pending_task(self, task: AuditTask) -> None:
        try:
            self.client.xadd(
                self.stream,
                {
                    "task_id": task.task_id,
                    "batch_id": task.batch_id,
                    "metadata": json.dumps(dict(task.metadata), sort_keys=True),
                },
            )
            self._store.queued(task.task_id)
        except Exception:
            # Keep the durable outbox row untouched.  The in-process worker
            # recovers it later and the caller receives pending_publish.
            raise

    def dequeue(self) -> AuditTask | None:
        self._ensure_group()
        reclaimed = self.reclaim_stale()
        if reclaimed is not None:
            return self._to_task(reclaimed, reclaimed=True)
        messages = self.client.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream: ">"},
            count=1,
            block=1,
        )
        message = self._first_message(messages)
        return self._to_task(message) if message is not None else None

    def reclaim_stale(self) -> tuple[Any, Mapping[Any, Any]] | None:
        self._ensure_group()
        response = self.client.xautoclaim(
            name=self.stream,
            groupname=self.group,
            consumername=self.consumer,
            min_idle_time=self.reclaim_idle_ms,
            start_id="0-0",
            count=1,
        )
        entries = response[1] if isinstance(response, (tuple, list)) and len(response) > 1 else []
        return entries[0] if entries else None

    def acknowledge(self, task: AuditTask) -> None:
        entry_id = self._inflight.pop(task.task_id, None)
        if entry_id is not None:
            self.client.xack(self.stream, self.group, entry_id)

    def _ensure_group(self) -> None:
        if self._groups_ready:
            return
        try:
            self.client.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise
        self._groups_ready = True

    @staticmethod
    def _first_message(messages: Any) -> tuple[Any, Mapping[Any, Any]] | None:
        if not messages:
            return None
        entries = messages[0][1]
        return entries[0] if entries else None

    def _to_task(
        self, message: tuple[Any, Mapping[Any, Any]], *, reclaimed: bool = False
    ) -> AuditTask:
        entry_id, fields = message
        decoded = {_decode(key): _decode(value) for key, value in fields.items()}
        task = AuditTask(
            task_id=str(decoded["task_id"]),
            batch_id=str(decoded["batch_id"]),
            metadata=json.loads(str(decoded.get("metadata", "{}"))),
            reclaimed=reclaimed,
        )
        self._inflight[task.task_id] = _decode(entry_id)
        return task


def _decode(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
