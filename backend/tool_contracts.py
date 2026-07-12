"""Small runtime metadata for the final VerbalVis tool set."""

from __future__ import annotations

from typing import Any, Iterable

TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "update_analysis_scope": {
        "label": "Update analysis scope",
        "category": "scope",
        "changes_dashboard": True,
    },
    "aggregate_data": {
        "label": "Aggregate data",
        "category": "analysis",
        "changes_dashboard": False,
    },
    "compare_selected_groups": {
        "label": "Compare selected groups",
        "category": "analysis",
        "changes_dashboard": False,
    },
    "compare_category_metrics": {
        "label": "Compare category metrics",
        "category": "analysis",
        "changes_dashboard": True,
    },
    "create_visual": {
        "label": "Create visualization",
        "category": "visualization",
        "changes_dashboard": True,
    },
    "update_visual": {
        "label": "Update visualization",
        "category": "visualization",
        "changes_dashboard": True,
    },
    "delete_visual": {
        "label": "Delete visualization",
        "category": "visualization",
        "changes_dashboard": True,
    },
    "highlight_visual": {
        "label": "Highlight evidence",
        "category": "attention",
        "changes_dashboard": True,
    },
    "inspect_visual": {
        "label": "Inspect visualization",
        "category": "evidence",
        "changes_dashboard": False,
    },
    "summarize_dashboard": {
        "label": "Summarize dashboard",
        "category": "evidence",
        "changes_dashboard": False,
    },
    "undo_last_action": {
        "label": "Undo last action",
        "category": "recovery",
        "changes_dashboard": True,
    },
}


def contract_for(name: str) -> dict[str, Any]:
    contract = TOOL_CONTRACTS.get(name)
    if contract:
        return {"name": name, **contract}
    return {
        "name": name,
        "label": str(name or "tool").replace("_", " "),
        "category": "unknown",
        "changes_dashboard": False,
    }


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
