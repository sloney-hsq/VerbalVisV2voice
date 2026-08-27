import pytest

from backend.runtime.contracts import ToolContract, ToolProposal
from backend.runtime.dashboard_store import DashboardStore
from backend.runtime.transactions import ResponseStatus, ResponseTransaction
from backend.tool_contracts import (
    TOOL_CONTRACTS,
    changes_dashboard,
    materialize_tool_contract,
)
from backend.tools import TOOL_SCHEMAS


def _executing_transaction(
    *, intent_epoch: int = 3, base_revision: int = 7
) -> ResponseTransaction:
    return ResponseTransaction(
        response_id="response-1",
        intent_epoch=intent_epoch,
        base_revision=base_revision,
        status=ResponseStatus.EXECUTING_DRAFT,
    )


def test_draft_mutation_does_not_change_committed_snapshot() -> None:
    """Catches a shallow draft copy that leaks nested changes into public state."""
    store = DashboardStore(
        {
            "dashboard_revision": 7,
            "views": [{"id": "view-1", "title": "Original"}],
        },
        intent_epoch=3,
    )
    transaction = _executing_transaction()

    draft = store.begin_draft(transaction)
    draft.state["views"][0]["title"] = "Draft title"

    assert store.snapshot()["views"][0]["title"] == "Original"
    assert draft.snapshot()["views"][0]["title"] == "Draft title"


def test_stale_epoch_rejects_commit_without_incrementing_revision() -> None:
    """Catches committing a proposal after a later analytical revision."""
    store = DashboardStore({"dashboard_revision": 7, "views": []}, intent_epoch=4)
    transaction = _executing_transaction(intent_epoch=3)
    draft = store.begin_draft(transaction)
    draft.state["views"].append({"id": "view-2"})

    result = store.commit(draft, transaction)

    assert not result.committed
    assert result.status == "stale_discarded"
    assert result.revision == 7
    assert store.snapshot() == {"dashboard_revision": 7, "views": []}


def test_mismatched_base_revision_rejects_commit_without_incrementing_revision() -> None:
    """Catches committing a draft that was rooted in an obsolete dashboard."""
    store = DashboardStore({"dashboard_revision": 7, "views": []}, intent_epoch=3)
    transaction = _executing_transaction(base_revision=6)
    draft = store.begin_draft(transaction)
    draft.state["views"].append({"id": "view-2"})

    result = store.commit(draft, transaction)

    assert not result.committed
    assert result.status == "stale_discarded"
    assert result.revision == 7
    assert store.snapshot() == {"dashboard_revision": 7, "views": []}


def test_valid_draft_commit_increments_revision_exactly_once() -> None:
    """Catches a successful batch that omits or double-applies its revision."""
    store = DashboardStore({"dashboard_revision": 7, "views": []}, intent_epoch=3)
    transaction = _executing_transaction()
    draft = store.begin_draft(transaction)
    draft.state["views"].append({"id": "view-2"})

    result = store.commit(draft, transaction)

    assert result.committed
    assert result.status == "committed"
    assert result.revision == 8
    assert store.snapshot() == {
        "dashboard_revision": 8,
        "views": [{"id": "view-2"}],
    }


def test_every_existing_olist_tool_has_transaction_contract_metadata() -> None:
    """Catches an Olist tool that cannot be admitted into a transactional batch."""
    required_fields = {
        "mode",
        "idempotent",
        "cancellable",
        "dependencies",
        "effect_detail",
    }

    for name, contract in TOOL_CONTRACTS.items():
        assert required_fields <= contract.keys()
        assert contract["mode"] == (
            "DRAFT_MUTATION" if changes_dashboard(name) else "READ_ONLY"
        )
        assert isinstance(contract["idempotent"], bool)
        assert isinstance(contract["cancellable"], bool)
        assert isinstance(contract["dependencies"], tuple)
        assert contract["effect_detail"]


def test_registered_contracts_bind_their_actual_tool_schema() -> None:
    """Catches a contract whose admission schema diverges from its registered tool."""
    schemas_by_name = {
        schema["name"]: schema["parameters"] for schema in TOOL_SCHEMAS
    }

    assert TOOL_CONTRACTS.keys() == schemas_by_name.keys()
    for name, schema in schemas_by_name.items():
        assert TOOL_CONTRACTS[name]["input_schema"] == schema
        contract = materialize_tool_contract(name)
        assert isinstance(contract, ToolContract)
        assert contract.input_schema == schema


def test_contract_schema_and_proposal_arguments_are_recursively_immutable() -> None:
    """Catches nested mappings that can change after validation or admission."""
    contract = materialize_tool_contract("update_analysis_scope")
    proposal = ToolProposal(
        response_id="response-1",
        intent_epoch=3,
        base_revision=7,
        call_id="call-1",
        tool_name="update_analysis_scope",
        arguments={"filters": [{"field": "customer_state", "value": "SP"}]},
    )

    with pytest.raises(TypeError):
        contract.input_schema["properties"]["operation"]["type"] = "integer"
    with pytest.raises(TypeError):
        proposal.arguments["filters"][0]["value"] = "RJ"
