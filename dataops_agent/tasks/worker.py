"""Synchronous worker path shared by local and Redis-backed queues."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from dataops_agent.data import run_quality_checks

from .models import AuditTask, TaskProgress, TaskStatus
from .queue import TaskQueue, TaskStore


class AuditWorker:
    def __init__(self, *, queue: TaskQueue, store: TaskStore, repository: Any) -> None:
        self._queue = queue
        self._store = store
        self._repository = repository

    def run_once(self) -> bool:
        """Process one task while preventing a reclaimed running audit from retrying."""
        task = self._queue.dequeue()
        if task is None:
            return False
        try:
            progress = self._ensure_progress(task)
            if progress.status is TaskStatus.RUNNING:
                self._store.fail(
                    task.task_id,
                    error="Recovered task cannot be retried after execution began",
                )
                return True
            if progress.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                return True

            self._store.start(task.task_id)
            report = run_quality_checks(self._repository)
            result = _as_mapping(report)
            self._store.complete(task.task_id, result=result)
        except Exception as error:
            self._fail_running_task(task.task_id, str(error))
        finally:
            self._queue.acknowledge(task)
        return True

    def _ensure_progress(self, task: AuditTask) -> TaskProgress:
        try:
            return self._store.progress(task.task_id)
        except KeyError:
            try:
                return self._store.create(task)
            except ValueError:
                return self._store.progress(task.task_id)

    def _fail_running_task(self, task_id: str, error: str) -> None:
        try:
            if self._store.progress(task_id).status is TaskStatus.RUNNING:
                self._store.fail(task_id, error=error)
        except (KeyError, ValueError):
            return


def _as_mapping(value: object) -> Mapping[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("Quality checks must return a mapping or dataclass")
