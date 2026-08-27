from backend.runtime.interruption import InterruptionDecision
from backend.runtime.transactions import ResponseStatus, ResponseTransactionManager


def test_backchannel_keeps_current_response_and_epoch() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("response-1", "yes, continue")

    assert decision is InterruptionDecision.BACKCHANNEL
    assert manager.intent_epoch == 0
    assert manager.can_admit("response-1")


def test_stop_only_cancels_current_response_without_advancing_epoch() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("response-1", "stop")

    assert decision is InterruptionDecision.STOP_ONLY
    assert manager.intent_epoch == 0
    assert not manager.can_admit("response-1")


def test_analytical_revision_advances_epoch_and_permits_replacement() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap(
        "response-1", "instead, show monthly revenue"
    )
    replacement = manager.begin_response("response-2", base_revision=4)

    assert decision is InterruptionDecision.ANALYTICAL_REVISION
    assert manager.intent_epoch == 1
    assert replacement.intent_epoch == 1
    assert manager.can_admit("response-2")


def test_superseded_response_is_rejected_from_admission() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)

    manager.supersede_current()

    assert not manager.can_admit("response-1")


def test_new_transaction_starts_with_no_tool_proposals() -> None:
    manager = ResponseTransactionManager()

    transaction = manager.begin_response("response-1", base_revision=4)

    assert transaction.proposed_tool_calls == ()


def test_recognition_repair_retains_current_response_and_epoch() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("response-1", "sorry, I mean 2024")

    assert decision is InterruptionDecision.RECOGNITION_REPAIR
    assert manager.intent_epoch == 0
    assert manager.can_admit("response-1")


def test_late_overlap_resolution_is_rejected_without_disturbing_replacement() -> None:
    class TextThatMustNotBeClassified(str):
        def lower(self) -> str:
            raise AssertionError("stale overlap was classified")

    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")
    replacement = manager.begin_response("response-2", base_revision=4)

    decision = manager.resolve_overlap(
        "response-1", TextThatMustNotBeClassified("instead, show monthly revenue")
    )

    assert decision is None
    assert manager.intent_epoch == 1
    assert replacement.status is ResponseStatus.STREAMING
    assert manager.can_admit("response-2")


def test_beginning_replacement_supersedes_existing_current_response() -> None:
    manager = ResponseTransactionManager()
    previous = manager.begin_response("response-1", base_revision=4)

    replacement = manager.begin_response("response-2", base_revision=4)

    assert previous.status is ResponseStatus.SUPERSEDED
    assert previous.cancelled
    assert manager.intent_epoch == 1
    assert replacement.intent_epoch == 1
    assert manager.can_admit("response-2")
