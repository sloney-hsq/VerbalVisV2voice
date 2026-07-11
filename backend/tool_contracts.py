"""Runtime contracts for VerbalVis tools.

The contracts describe tool roles and provide user-facing labels. They do not
limit the number of tool calls and do not implement cancellation, rollback,
transactions, epochs, or stale-result invalidation.
"""

from __future__ import annotations

from typing import Any, Iterable

TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "set_analysis_scope": {
        "label": "Set analysis scope",
        "category": "data_scope",
        "changes_dashboard": True,
        "description": "Apply several global scope filters together.",
    },
    "compare_category_metrics": {
        "label": "Compare category metrics",
        "category": "analytical_comparison",
        "changes_dashboard": True,
        "description": "Create coordinated views for one common Top-N category set.",
    },
    "filter_data": {
        "label": "Apply data filter",
        "category": "data_scope",
        "changes_dashboard": True,
        "description": "Replace or extend the global analysis scope with one filter.",
    },
    "remove_filter": {
        "label": "Remove data filter",
        "category": "data_scope",
        "changes_dashboard": True,
        "description": "Remove the global filter for one field.",
    },
    "set_low_score_threshold": {
        "label": "Set low-score definition",
        "category": "data_definition",
        "changes_dashboard": True,
        "description": "Change the dashboard-wide low-score threshold.",
    },
    "append_visual": {
        "label": "Create visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "description": "Create one new evidence view from the current scope.",
    },
    "delete_visual": {
        "label": "Delete visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "description": "Remove one existing view.",
    },
    "highlight_visual": {
        "label": "Highlight visualization",
        "category": "attention",
        "changes_dashboard": True,
        "description": "Direct attention to existing views or clear highlighting.",
    },
    "inspect_visual": {
        "label": "Inspect visualization",
        "category": "evidence_reading",
        "changes_dashboard": False,
        "description": "Read authoritative values and statistics from one view.",
    },
}

CORE_TOOL_NAMES = frozenset(TOOL_CONTRACTS)


def contract_for(name: str) -> dict[str, Any]:
    """Return a stable metadata object for a tool name."""
    contract = TOOL_CONTRACTS.get(name)
    if contract:
        return {"name": name, **contract}
    return {
        "name": name,
        "label": name.replace("_", " ").strip() or "Tool",
        "category": "unknown",
        "changes_dashboard": False,
        "description": "Unrecognized tool.",
    }


def batch_metadata(names: Iterable[str]) -> list[dict[str, Any]]:
    """Return compact metadata for a tool batch, preserving order."""
    return [contract_for(name) for name in names]


def changes_dashboard(name: str) -> bool:
    return bool(contract_for(name).get("changes_dashboard"))


def _format_count(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,}"


def result_summary(name: str, result: dict[str, Any]) -> str:
    """Create a short, non-speculative UI summary for a completed tool call."""
    label = str(contract_for(name).get("label") or name)
    if result.get("success"):
        payload = result.get("payload")
        if isinstance(payload, dict):
            if name in {"filter_data", "remove_filter", "set_analysis_scope"}:
                rows = payload.get("filtered_rows")
                if rows is not None:
                    return f"{label} completed · {_format_count(rows)} rows in scope"
            if name == "compare_category_metrics":
                views = payload.get("view_ids") or []
                top_n = payload.get("top_n")
                return (
                    f"{label} completed · {len(views)} views"
                    + (f" for Top {top_n}" if top_n else "")
                )
            if name == "append_visual" and payload.get("view_id"):
                return f"{label} completed · {payload['view_id']}"
            if name == "delete_visual" and payload.get("view_id"):
                return f"{label} completed · removed {payload['view_id']}"
            if name == "set_low_score_threshold" and payload.get("definition"):
                return f"{label} completed · {payload['definition']}"
            if name == "inspect_visual" and payload.get("view_id"):
                return f"{label} completed · {payload['view_id']}"
        return f"{label} completed"

    error = str(result.get("error") or "Tool execution failed").strip()
    return f"{label} failed · {error}"
