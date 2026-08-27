"""Private dashboard drafts and atomic public dashboard commits."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping


@dataclass
class DashboardDraft:
    """A mutable, private dashboard snapshot rooted at one revision."""

    base_revision: int
    state: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        """Return an isolated copy of the draft's current state."""
        return deepcopy(self.state)

    def replace(self, state: Mapping[str, Any]) -> None:
        """Replace the draft contents without publishing them."""
        self.state = deepcopy(dict(state))


@dataclass(frozen=True)
class CommitResult:
    """The observable outcome of one conditional dashboard commit."""

    committed: bool
    status: str
    revision: int
    snapshot: dict[str, Any]
    reason: str | None = None


class DashboardStore:
    """Owns the committed dashboard mapping and its monotonic revision."""

    def __init__(
        self,
        initial_snapshot: Mapping[str, Any] | None = None,
        *,
        intent_epoch: int = 0,
    ) -> None:
        state = deepcopy(dict(initial_snapshot or {}))
        self._revision = int(state.get("dashboard_revision") or 0)
        state["dashboard_revision"] = self._revision
        self._state = state
        self.intent_epoch = intent_epoch
        self._lock = RLock()

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def set_intent_epoch(self, intent_epoch: int) -> None:
        """Set the epoch against which later commits are conditionally checked."""
        with self._lock:
            self.intent_epoch = intent_epoch

    def snapshot(self) -> dict[str, Any]:
        """Return a copy that callers cannot use to mutate committed state."""
        with self._lock:
            return deepcopy(self._state)

    def begin_draft(self, transaction: object) -> DashboardDraft:
        """Clone committed state for a transaction without changing public state."""
        base_revision = int(getattr(transaction, "base_revision"))
        with self._lock:
            return DashboardDraft(base_revision=base_revision, state=deepcopy(self._state))

    def commit(
        self,
        draft: DashboardDraft,
        transaction: object,
        current_epoch: int | None = None,
    ) -> CommitResult:
        """Publish a draft only if its response transaction remains current."""
        with self._lock:
            active_epoch = self.intent_epoch if current_epoch is None else current_epoch
            reason = self._rejection_reason(draft, transaction, active_epoch)
            if reason is not None:
                return CommitResult(
                    committed=False,
                    status="stale_discarded",
                    revision=self._revision,
                    snapshot=deepcopy(self._state),
                    reason=reason,
                )

            self._revision += 1
            self._state = deepcopy(draft.state)
            self._state["dashboard_revision"] = self._revision
            return CommitResult(
                committed=True,
                status="committed",
                revision=self._revision,
                snapshot=deepcopy(self._state),
            )

    def _rejection_reason(
        self,
        draft: DashboardDraft,
        transaction: object,
        current_epoch: int,
    ) -> str | None:
        if getattr(transaction, "intent_epoch", None) != current_epoch:
            return "stale_epoch"
        if getattr(transaction, "base_revision", None) != self._revision:
            return "stale_base_revision"
        if draft.base_revision != getattr(transaction, "base_revision", None):
            return "draft_base_revision_mismatch"
        status = getattr(getattr(transaction, "status", None), "value", None)
        if status != "EXECUTING_DRAFT":
            return "transaction_not_executing_draft"
        if bool(getattr(transaction, "cancelled", False)):
            return "transaction_cancelled"
        return None
