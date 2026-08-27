"""Lifecycle ownership for model responses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .interruption import InterruptionDecision, classify_completed_utterance


class ResponseStatus(str, Enum):
    STREAMING = "STREAMING"
    OVERLAP_PENDING = "OVERLAP_PENDING"
    PROPOSING = "PROPOSING"
    EXECUTING_DRAFT = "EXECUTING_DRAFT"
    COMMITTED = "COMMITTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class ResponseTransaction:
    response_id: str
    intent_epoch: int
    base_revision: int
    status: ResponseStatus = ResponseStatus.STREAMING
    cancelled: bool = False
    proposed_tool_calls: tuple[object, ...] = ()
    overlap_return_status: ResponseStatus | None = None


class ResponseTransactionManager:
    """Keeps only the active, semantically current response admissible."""

    def __init__(self) -> None:
        self.intent_epoch = 0
        self._transactions: dict[str, ResponseTransaction] = {}
        self._current_response_id: str | None = None
        self._overlap_response_id: str | None = None

    def begin_response(self, response_id: str, base_revision: int) -> ResponseTransaction:
        if self._current_response_id is not None:
            self.supersede_current()
        transaction = ResponseTransaction(
            response_id=response_id,
            intent_epoch=self.intent_epoch,
            base_revision=base_revision,
        )
        self._transactions[response_id] = transaction
        self._current_response_id = response_id
        return transaction

    @property
    def current_response_id(self) -> str | None:
        return self._current_response_id

    def get(self, response_id: str) -> ResponseTransaction | None:
        return self._transactions.get(response_id)

    def mark_overlap(self, response_id: str) -> None:
        transaction = self._current_transaction(response_id)
        if transaction.status not in {
            ResponseStatus.STREAMING,
            ResponseStatus.EXECUTING_DRAFT,
        }:
            raise ValueError("response cannot accept overlap in its current state")
        transaction.overlap_return_status = transaction.status
        transaction.status = ResponseStatus.OVERLAP_PENDING
        self._overlap_response_id = response_id

    def resolve_overlap(
        self, response_id: str, text: str
    ) -> InterruptionDecision | None:
        if (
            response_id != self._overlap_response_id
            or response_id != self._current_response_id
        ):
            return None
        transaction = self._transactions[response_id]
        if transaction.status is not ResponseStatus.OVERLAP_PENDING:
            return None
        decision = classify_completed_utterance(text)
        self._overlap_response_id = None
        if decision in {
            InterruptionDecision.BACKCHANNEL,
            InterruptionDecision.RECOGNITION_REPAIR,
        }:
            transaction.status = (
                transaction.overlap_return_status or ResponseStatus.STREAMING
            )
            transaction.overlap_return_status = None
        elif decision is InterruptionDecision.STOP_ONLY:
            transaction.cancelled = True
            transaction.status = ResponseStatus.CANCELLED
            self._current_response_id = None
        else:
            self.supersede_current()
        return decision

    def start_draft_execution(self, response_id: str) -> ResponseTransaction:
        """Transition an admissible response into private tool execution."""
        if not self.can_admit(response_id):
            raise ValueError("response is not eligible to execute a draft")
        transaction = self._current_transaction(response_id)
        transaction.status = ResponseStatus.EXECUTING_DRAFT
        return transaction

    def mark_committed(self, response_id: str) -> ResponseTransaction:
        transaction = self._current_transaction(response_id)
        if transaction.cancelled:
            raise ValueError("cancelled response cannot commit")
        transaction.status = ResponseStatus.COMMITTED
        self._current_response_id = None
        self._overlap_response_id = None
        return transaction

    def mark_failed(self, response_id: str) -> ResponseTransaction | None:
        transaction = self._transactions.get(response_id)
        if transaction is None:
            return None
        if transaction.status not in {
            ResponseStatus.CANCELLED,
            ResponseStatus.SUPERSEDED,
        }:
            transaction.status = ResponseStatus.FAILED
        if self._current_response_id == response_id:
            self._current_response_id = None
        if self._overlap_response_id == response_id:
            self._overlap_response_id = None
        return transaction

    def supersede_current(self) -> ResponseTransaction | None:
        if self._current_response_id is None:
            return None
        transaction = self._current_transaction()
        transaction.cancelled = True
        transaction.status = ResponseStatus.SUPERSEDED
        self._overlap_response_id = None
        self._current_response_id = None
        self.intent_epoch += 1
        return transaction

    def can_admit(self, response_id: str) -> bool:
        transaction = self._transactions.get(response_id)
        return bool(
            transaction
            and response_id == self._current_response_id
            and transaction.intent_epoch == self.intent_epoch
            and transaction.status is ResponseStatus.STREAMING
            and not transaction.cancelled
        )

    def _current_transaction(
        self, response_id: str | None = None
    ) -> ResponseTransaction:
        current_id = self._current_response_id
        if current_id is None or (response_id is not None and response_id != current_id):
            raise ValueError("response is not current")
        return self._transactions[current_id]
