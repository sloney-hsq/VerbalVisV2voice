"""Synchronous worker path shared by local and Redis-backed queues."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from threading import RLock
from time import sleep as default_sleep
from typing import Any, Mapping

from dataops_agent.data import run_quality_checks

from .models import AuditTask, TaskProgress, TaskStatus
from .queue import TaskQueue, TaskStore


class AuditWorker:
    def __init__(self, *, queue: TaskQueue, store: TaskStore, repository: Any) -> None:
        self._queue = queue
        self._store = store
        self._repository = repository
        self._run_lock = RLock()

    def run_once(self) -> bool:
        """Process one task and ACK only after durable terminal state is confirmed."""
        with self._run_lock:
            self._recover_pending_publications()
            task = self._queue.dequeue()
            if task is None:
                return False
            try:
                progress = self._ensure_progress(task)
                if progress.status is TaskStatus.RUNNING:
                    if task.reclaimed:
                        # A begun audit is deliberately never executed again. Once
                        # Redis reclaims its delivery, record a terminal result and
                        # ACK it so a dead worker cannot leave it pending forever.
                        self._fail_running_task(
                            task.task_id,
                            "Audit delivery was reclaimed after the worker lease expired; execution was not retried.",
                        )
                        self._acknowledge_if_terminal(task)
                    return True
                if progress.status in _TERMINAL_STATUSES:
                    self._acknowledge_if_terminal(task)
                    return True

                self._store.start(task.task_id)
                report = run_quality_checks(self._repository)
                result = _as_mapping(report)
                self._store.complete(task.task_id, result=result)
            except Exception as error:
                self._fail_running_task(task.task_id, str(error))
            self._acknowledge_if_terminal(task)
            return True

    def _recover_pending_publications(self) -> None:
        recovery = getattr(self._queue, "recover_pending", None)
        if callable(recovery):
            recovery()

    def run_until_empty(self) -> int:
        """Drain currently available work, returning the number of deliveries handled."""
        handled = 0
        while self.run_once():
            handled += 1
        return handled

    def run_forever(
        self,
        *,
        poll_interval_seconds: float = 0.25,
        should_continue: Callable[[], bool] | None = None,
        sleep: Callable[[float], None] = default_sleep,
    ) -> None:
        """Poll from the owning API process; do not use with a second DuckDB writer process."""
        if poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must not be negative")
        keep_running = should_continue or (lambda: True)
        while keep_running():
            if not self.run_once():
                sleep(poll_interval_seconds)

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
        except Exception:
            return

    def _acknowledge_if_terminal(self, task: AuditTask) -> None:
        try:
            if self._store.progress(task.task_id).status in _TERMINAL_STATUSES:
                self._queue.acknowledge(task)
        except Exception:
            return


def _as_mapping(value: object) -> Mapping[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("Quality checks must return a mapping or dataclass")


_TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED}
