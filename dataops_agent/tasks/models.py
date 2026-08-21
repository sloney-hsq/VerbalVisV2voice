"""Task value objects and status transitions for asynchronous audits."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping
from uuid import uuid4


class TaskStatus(StrEnum):
    PENDING_PUBLISH = "pending_publish"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class AuditTask:
    batch_id: str
    task_id: str = field(default_factory=lambda: str(uuid4()))
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, object] = field(default_factory=dict)
    idempotency_key: str | None = None
    reclaimed: bool = False


@dataclass(frozen=True, slots=True)
class TaskProgress:
    task_id: str
    status: TaskStatus
    completed: int = 0
    total: int = 1
    result: Mapping[str, object] | None = None
    error: str | None = None

    @property
    def percent(self) -> int:
        """Return a bounded whole-number representation suitable for clients."""
        if self.total <= 0:
            return 0
        return min(100, int(self.completed * 100 / self.total))
