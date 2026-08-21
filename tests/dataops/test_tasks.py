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


def test_file_backed_duckdb_task_store_owns_connection_independently_of_repository(tmp_path) -> None:
    database_path = tmp_path / "independent-task-state.duckdb"
    repository = DuckDBRepository(str(database_path))
    store = tasks.DuckDBTaskStore(repository)
    repository.close()

    task = AuditTask(batch_id="batch-1", task_id="task-1")
    store.create(task)

    assert store.progress(task.task_id).status is TaskStatus.QUEUED


class RecordingQueue:
    def __init__(self, task: AuditTask) -> None:
        self.task = task
        self.acknowledged: list[str] = []

    def enqueue(self, task: AuditTask) -> str:
        raise AssertionError("enqueue is not used by this test")

    def dequeue(self) -> AuditTask | None:
        task, self.task = self.task, None
        return task

    def acknowledge(self, task: AuditTask) -> None:
        self.acknowledged.append(task.task_id)


class TerminalPersistenceFailureStore(InMemoryTaskStore):
    def complete(self, task_id: str, *, result):
        raise RuntimeError("complete persistence unavailable")

    def fail(self, task_id: str, *, error: str):
        raise RuntimeError("failure persistence unavailable")


def test_worker_leaves_message_pending_when_terminal_state_cannot_be_persisted(monkeypatch) -> None:
    task = AuditTask(batch_id="batch-1", task_id="task-1")
    store = TerminalPersistenceFailureStore()
    store.create(task)
    queue = RecordingQueue(task)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    monkeypatch.setattr(
        "dataops_agent.tasks.worker.run_quality_checks",
        lambda repository: {"schema_valid_rate": 1.0},
    )

    assert worker.run_once() is True

    assert store.progress(task.task_id).status is TaskStatus.RUNNING
    assert queue.acknowledged == []


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


def test_worker_marks_reclaimed_running_task_failed_and_acknowledges_without_retrying(monkeypatch) -> None:
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
    progress = store.progress(task.task_id)
    assert progress.status is TaskStatus.FAILED
    assert progress.error == "Audit delivery was reclaimed after the worker lease expired; execution was not retried."
    assert redis.acked == [("audits", "workers", "stale-1")]


def test_worker_run_forever_polls_until_its_stop_predicate_is_false(monkeypatch) -> None:
    """Removing the loop would leave the Redis deployment with only a one-shot worker."""
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=FakeRepository())
    outcomes = iter([False, False])
    keep_running = iter([True, True, False])
    pauses: list[float] = []
    monkeypatch.setattr(worker, "run_once", lambda: next(outcomes))

    worker.run_forever(
        poll_interval_seconds=0.25,
        should_continue=lambda: next(keep_running),
        sleep=pauses.append,
    )

    assert pauses == [0.25, 0.25]




class PublishFailsOnceRedis(FakeRedisStreams):
    def __init__(self) -> None:
        super().__init__()
        self.publish_attempts = 0

    def xadd(self, stream, fields) -> str:
        self.publish_attempts += 1
        if self.publish_attempts == 1:
            raise RuntimeError("redis unavailable")
        return super().xadd(stream, fields)


def test_redis_publication_failure_keeps_a_durable_outbox_entry_for_recovery() -> None:
    store = InMemoryTaskStore()
    redis = PublishFailsOnceRedis()
    queue = RedisStreamsTaskQueue(store, client=redis)
    first = AuditTask(batch_id="batch-1", task_id="task-1", idempotency_key="audit-key")

    task_id = queue.enqueue(first)

    assert store.progress(first.task_id).status.value == "pending_publish"
    assert task_id == first.task_id
    assert queue.recover_pending() == 1
    assert store.progress(first.task_id).status is TaskStatus.QUEUED
    assert redis.fields["batch_id"] == "batch-1"
