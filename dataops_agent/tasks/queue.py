"""Queue and state adapters for audit work."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from .models import AuditTask, TaskProgress, TaskStatus


@runtime_checkable
class TaskStore(Protocol):
    def create(self, task: AuditTask) -> TaskProgress: ...
    def start(self, task_id: str) -> TaskProgress: ...
    def complete(self, task_id: str, *, result: Mapping[str, object]) -> TaskProgress: ...
    def fail(self, task_id: str, *, error: str) -> TaskProgress: ...
    def progress(self, task_id: str) -> TaskProgress: ...


@runtime_checkable
class TaskQueue(Protocol):
    def enqueue(self, task: AuditTask) -> str: ...
    def dequeue(self) -> AuditTask | None: ...
    def acknowledge(self, task: AuditTask) -> None: ...


class InMemoryTaskStore:
    """A deterministic task store intended for local development and tests."""

    def __init__(self) -> None:
        self._progress: dict[str, TaskProgress] = {}
        self._lock = RLock()

    def create(self, task: AuditTask) -> TaskProgress:
        with self._lock:
            if task.task_id in self._progress:
                raise ValueError(f"Task already exists: {task.task_id}")
            progress = TaskProgress(task_id=task.task_id, status=TaskStatus.QUEUED)
            self._progress[task.task_id] = progress
            return progress

    def start(self, task_id: str) -> TaskProgress:
        return self._transition(task_id, allowed={TaskStatus.QUEUED}, status=TaskStatus.RUNNING)

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
        self._connection = repository.connection
        self._lock = RLock()
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
                error VARCHAR
            )
            """
        )

    def create(self, task: AuditTask) -> TaskProgress:
        with self._lock:
            try:
                self.progress(task.task_id)
            except KeyError:
                self._connection.execute(
                    """
                    INSERT INTO audit_tasks
                    (task_id, batch_id, requested_at, metadata, status, completed, total, result, error)
                    VALUES (?, ?, ?, ?, ?, 0, 1, NULL, NULL)
                    """,
                    [
                        task.task_id,
                        task.batch_id,
                        task.requested_at,
                        json.dumps(dict(task.metadata), sort_keys=True, default=str),
                        TaskStatus.QUEUED.value,
                    ],
                )
                return self.progress(task.task_id)
            raise ValueError(f"Task already exists: {task.task_id}")

    def start(self, task_id: str) -> TaskProgress:
        return self._transition(task_id, allowed={TaskStatus.QUEUED}, status=TaskStatus.RUNNING)

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
        self._store.create(task)
        self._tasks.append(task)
        return task.task_id

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
        self._store.create(task)
        self.client.xadd(
            self.stream,
            {
                "task_id": task.task_id,
                "batch_id": task.batch_id,
                "metadata": json.dumps(dict(task.metadata), sort_keys=True),
            },
        )
        return task.task_id

    def dequeue(self) -> AuditTask | None:
        self._ensure_group()
        message = self.reclaim_stale()
        if message is None:
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

    def _to_task(self, message: tuple[Any, Mapping[Any, Any]]) -> AuditTask:
        entry_id, fields = message
        decoded = {_decode(key): _decode(value) for key, value in fields.items()}
        task = AuditTask(
            task_id=str(decoded["task_id"]),
            batch_id=str(decoded["batch_id"]),
            metadata=json.loads(str(decoded.get("metadata", "{}"))),
        )
        self._inflight[task.task_id] = _decode(entry_id)
        return task


def _decode(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
