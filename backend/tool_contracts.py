"""Small runtime metadata for the final VerbalVis tool set."""

from __future__ import annotations

import sys
from typing import Any, Iterable

if __package__:
    # The legacy tool module is executable from ``backend/`` and therefore
    # imports siblings absolutely.  Keep that execution path intact while
    # also making its registered schemas available to package-based tests.
    from . import db as _db
    from . import view_titles as _view_titles

    sys.modules.setdefault("db", _db)
    sys.modules.setdefault("view_titles", _view_titles)
    from .tools import TOOL_SCHEMAS
    from .runtime.contracts import ToolContract, ToolMode
else:
    from tools import TOOL_SCHEMAS
    from runtime.contracts import ToolContract, ToolMode

TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "update_analysis_scope": {
        "label": "Update analysis scope",
        "category": "scope",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Replaces the shared dashboard analysis filters.",
    },
    "aggregate_data": {
        "label": "Aggregate data",
        "category": "analysis",
        "changes_dashboard": False,
        "mode": "READ_ONLY",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Computes grouped metrics without changing the dashboard.",
    },
    "compare_selected_groups": {
        "label": "Compare selected groups",
        "category": "analysis",
        "changes_dashboard": False,
        "mode": "READ_ONLY",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Compares selected groups without changing the dashboard.",
    },
    "compare_category_metrics": {
        "label": "Compare category metrics",
        "category": "analysis",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": False,
        "cancellable": False,
        "effect_detail": "Creates coordinated comparison views in the dashboard draft.",
    },
    "create_visual": {
        "label": "Create visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": False,
        "cancellable": False,
        "effect_detail": "Adds a visualization to the dashboard draft.",
    },
    "update_visual": {
        "label": "Update visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Updates an existing visualization in the dashboard draft.",
    },
    "delete_visual": {
        "label": "Delete visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": False,
        "cancellable": False,
        "effect_detail": "Removes a visualization from the dashboard draft.",
    },
    "highlight_visual": {
        "label": "Highlight evidence",
        "category": "attention",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Changes dashboard highlight state in the draft.",
    },
    "inspect_visual": {
        "label": "Inspect visualization",
        "category": "evidence",
        "changes_dashboard": False,
        "mode": "READ_ONLY",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Inspects an existing visualization without changing the dashboard.",
    },
    "summarize_dashboard": {
        "label": "Summarize dashboard",
        "category": "evidence",
        "changes_dashboard": False,
        "mode": "READ_ONLY",
        "dependencies": (),
        "precondition": "valid arguments",
        "idempotent": True,
        "cancellable": False,
        "effect_detail": "Summarizes dashboard state without changing it.",
    },
    "undo_last_action": {
        "label": "Undo last action",
        "category": "recovery",
        "changes_dashboard": True,
        "mode": "DRAFT_MUTATION",
        "dependencies": (),
        "precondition": "a completed dashboard action exists",
        "idempotent": False,
        "cancellable": False,
        "effect_detail": "Restores the previous dashboard action in the draft.",
    },
}


def _bind_registered_input_schemas() -> None:
    """Attach each contract to the one schema registered with the model."""
    schemas_by_name = {
        str(schema["name"]): schema["parameters"] for schema in TOOL_SCHEMAS
    }
    if TOOL_CONTRACTS.keys() != schemas_by_name.keys():
        raise RuntimeError("Tool contract metadata and registered schemas differ")
    for name, contract in TOOL_CONTRACTS.items():
        contract["input_schema"] = schemas_by_name[name]


_bind_registered_input_schemas()


def contract_for(name: str) -> dict[str, Any]:
    contract = TOOL_CONTRACTS.get(name)
    if contract:
        return {"name": name, **contract}
    return {
        "name": name,
        "label": str(name or "tool").replace("_", " "),
        "category": "unknown",
        "changes_dashboard": False,
        "mode": "READ_ONLY",
        "dependencies": (),
        "precondition": "tool is registered",
        "idempotent": False,
        "cancellable": False,
        "effect_detail": "Unknown tools are rejected without changing the dashboard.",
    }


def materialize_tool_contract(name: str) -> ToolContract:
    """Return immutable runtime admission metadata for a registered tool."""
    contract = TOOL_CONTRACTS.get(name)
    if contract is None:
        raise KeyError(f"Unknown tool contract: {name}")
    return ToolContract(
        name=name,
        input_schema=contract["input_schema"],
        mode=ToolMode(contract["mode"]),
        dependencies=contract["dependencies"],
        precondition=contract["precondition"],
        idempotent=contract["idempotent"],
        cancellable=contract["cancellable"],
        effect_detail=contract["effect_detail"],
    )


def batch_metadata(names: Iterable[str]) -> list[dict[str, Any]]:
    return [contract_for(name) for name in names]


def changes_dashboard(name: str) -> bool:
    return bool(contract_for(name).get("changes_dashboard"))


def result_summary(name: str, result: dict[str, Any]) -> str:
    label = str(contract_for(name).get("label") or name)
    if result.get("success") is False:
        return f"{label} failed"

    payload = result.get("payload") or {}
    if name == "update_analysis_scope":
        rows = payload.get("filtered_rows")
        return f"{label} · {int(rows):,} orders" if rows is not None else label
    if name == "compare_category_metrics":
        summary = f"{label} · {len(payload.get('view_ids') or [])} views"
        rows = payload.get("filtered_rows")
        return f"{summary} · {int(rows):,} orders" if rows is not None else summary
    if name in {"create_visual", "update_visual"} and payload.get("view_id"):
        return f"{label} · {payload['view_id']}"
    if name == "delete_visual" and payload.get("view_id"):
        return f"{label} · {payload['view_id']}"
    if name in {"aggregate_data", "compare_selected_groups"}:
        return f"{label} · {payload.get('row_count', 0)} rows"
    if name == "inspect_visual" and payload.get("view_id"):
        return f"{label} · {payload['view_id']}"
    if name == "undo_last_action" and payload.get("undone_action"):
        return f"{label} · {payload['undone_action']}"
    return label
