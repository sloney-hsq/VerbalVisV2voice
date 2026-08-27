from backend.runtime.interruption import InterruptionDecision
from backend.runtime.transactions import ResponseTransactionManager


def test_backchannel_keeps_current_response_and_epoch() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("yes, continue")

    assert decision is InterruptionDecision.BACKCHANNEL
    assert manager.intent_epoch == 0
    assert manager.can_admit("response-1")


def test_stop_only_cancels_current_response_without_advancing_epoch() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("stop")

    assert decision is InterruptionDecision.STOP_ONLY
    assert manager.intent_epoch == 0
    assert not manager.can_admit("response-1")


def test_analytical_revision_advances_epoch_and_permits_replacement() -> None:
    manager = ResponseTransactionManager()
    manager.begin_response("response-1", base_revision=4)
    manager.mark_overlap("response-1")

    decision = manager.resolve_overlap("instead, show monthly revenue")
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
