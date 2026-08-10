from __future__ import annotations

import pytest

from dataops_agent.data import DuckDBRepository
from dataops_agent import tasks
from dataops_agent.tasks import (
    AuditTask,
    InMemoryTaskQueue,
    InMemoryTaskStore,
    RedisStreamsTaskQueue,
    TaskStatus,
)
from dataops_agent.tasks.worker import AuditWorker


class FakeRepository:
    pass


def test_queue_assigns_an_audit_task_id_and_records_queued_progress() -> None:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)

    task_id = queue.enqueue(AuditTask(batch_id="batch-1"))

    progress = store.progress(task_id)
    assert progress.task_id == task_id
    assert progress.status is TaskStatus.QUEUED
    assert progress.completed == 0
    assert progress.total == 1


def test_worker_transitions_an_audit_task_to_completed(monkeypatch) -> None:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: {"schema_valid_rate": 1.0, "duplicate_rate": 0.0},
    )
    task_id = queue.enqueue(AuditTask(batch_id="batch-1"))

    assert worker.run_once() is True

    progress = store.progress(task_id)
    assert progress.status is TaskStatus.COMPLETED
    assert progress.completed == 1
    assert progress.result == {"schema_valid_rate": 1.0, "duplicate_rate": 0.0}


def test_worker_marks_task_failed_when_audit_raises(monkeypatch) -> None:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    task_id = queue.enqueue(AuditTask(batch_id="batch-1"))

    worker.run_once()

    progress = store.progress(task_id)
    assert progress.status is TaskStatus.FAILED
    assert progress.error == "audit unavailable"


def test_store_rejects_completion_before_a_task_is_running() -> None:
    store = InMemoryTaskStore()
    task = AuditTask(batch_id="batch-1")
    store.create(task)

    with pytest.raises(ValueError, match="queued"):
        store.complete(task.task_id, result={})


def test_duckdb_task_store_persists_terminal_progress_across_reopen(tmp_path) -> None:
    database_path = tmp_path / "task-state.duckdb"
    task = AuditTask(batch_id="batch-1", task_id="task-1")
    first_repository = DuckDBRepository(str(database_path))
    store_type = getattr(tasks, "DuckDBTaskStore", None)
    assert store_type is not None
    first_store = store_type(first_repository)
    first_store.create(task)
    first_store.start(task.task_id)
    first_store.complete(task.task_id, result={"schema_valid_rate": 1.0})
    first_repository.connection.close()

    reopened_store = store_type(DuckDBRepository(str(database_path)))

    progress = reopened_store.progress(task.task_id)
    assert progress.status is TaskStatus.COMPLETED
    assert progress.result == {"schema_valid_rate": 1.0}


class FakeRedisStreams:
    def __init__(self) -> None:
        self.created_groups: list[tuple[object, ...]] = []
        self.acked: list[tuple[object, ...]] = []
        self.reclaimed = False

    def xgroup_create(self, *args, **kwargs) -> None:
        self.created_groups.append(args)

    def xadd(self, stream, fields) -> str:
        self.fields = fields
        return "1-0"

    def xreadgroup(self, **kwargs):
        return []

    def xautoclaim(self, **kwargs):
        self.reclaimed = True
        return ["0-0", [("2-0", {b"task_id": b"task-1", b"batch_id": b"batch-1"})], []]

    def xack(self, *args) -> int:
        self.acked.append(args)
        return 1


class ReclaimFirstRedisStreams(FakeRedisStreams):
    def __init__(self, *, reclaimed_task_id: str = "stale-task") -> None:
        super().__init__()
        self.calls: list[str] = []
        self.reclaimed_task_id = reclaimed_task_id

    def xreadgroup(self, **kwargs):
        self.calls.append("read")
        return [("audits", [("fresh-1", {b"task_id": b"fresh-task", b"batch_id": b"fresh-batch"})])]

    def xautoclaim(self, **kwargs):
        self.calls.append("claim")
        return [
            "0-0",
            [("stale-1", {b"task_id": self.reclaimed_task_id.encode(), b"batch_id": b"stale-batch"})],
            [],
        ]


def test_redis_stream_queue_reclaims_stale_messages_and_acknowledges_them() -> None:
    store = InMemoryTaskStore()
    store.create(AuditTask(batch_id="batch-1", task_id="task-1"))
    redis = FakeRedisStreams()
    queue = RedisStreamsTaskQueue(store, client=redis, stream="audits", group="workers", consumer="worker-1")

    task = queue.dequeue()
    assert task is not None
    queue.acknowledge(task)

    assert redis.reclaimed is True
    assert redis.acked == [("audits", "workers", "2-0")]


def test_redis_queue_reclaims_pending_work_before_reading_fresh_work() -> None:
    store = InMemoryTaskStore()
    store.create(AuditTask(batch_id="stale-batch", task_id="stale-task"))
    redis = ReclaimFirstRedisStreams()
    queue = RedisStreamsTaskQueue(store, client=redis, stream="audits", group="workers", consumer="worker-1")

    task = queue.dequeue()

    assert task is not None
    assert task.task_id == "stale-task"
    assert redis.calls == ["claim"]


def test_worker_reconstructs_missing_reclaimed_task_state_and_acknowledges(monkeypatch) -> None:
    store = InMemoryTaskStore()
    redis = ReclaimFirstRedisStreams(reclaimed_task_id="lost-task")
    redis.xreadgroup = lambda **kwargs: []
    queue = RedisStreamsTaskQueue(store, client=redis, stream="audits", group="workers", consumer="worker-1")
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: {"schema_valid_rate": 1.0, "duplicate_rate": 0.0},
    )

    assert worker.run_once() is True

    assert store.progress("lost-task").status is TaskStatus.COMPLETED
    assert redis.acked == [("audits", "workers", "stale-1")]


def test_worker_marks_reclaimed_running_task_failed_without_retrying(monkeypatch) -> None:
    store = InMemoryTaskStore()
    task = AuditTask(batch_id="batch-1", task_id="running-task")
    store.create(task)
    store.start(task.task_id)
    redis = ReclaimFirstRedisStreams(reclaimed_task_id=task.task_id)
    redis.xreadgroup = lambda **kwargs: []
    queue = RedisStreamsTaskQueue(store, client=redis, stream="audits", group="workers", consumer="worker-1")
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    called = False

    def quality_check(repository):
        nonlocal called
        called = True
        return {"schema_valid_rate": 1.0}

    monkeypatch.setattr("dataops_agent.tasks.worker.run_quality_checks", quality_check)

    assert worker.run_once() is True

    assert called is False
    assert store.progress(task.task_id).status is TaskStatus.FAILED
    assert redis.acked == [("audits", "workers", "stale-1")]
