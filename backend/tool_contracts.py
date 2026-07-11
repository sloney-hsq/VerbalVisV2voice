"""Runtime contracts for VerbalVis tools.

The contracts describe tool roles and provide user-facing labels. They do not
limit tool-call count and do not implement cancellation, rollback, epochs,
transactions, or stale-result invalidation.
"""

from __future__ import annotations

from typing import Any, Iterable

TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "update_analysis_scope": {
        "label": "Update analysis scope",
        "category": "data_scope",
        "changes_dashboard": True,
        "description": "Replace, add, remove, or clear global analysis filters.",
    },
    "set_analysis_scope": {
        "label": "Set analysis scope",
        "category": "data_scope",
        "changes_dashboard": True,
        "description": "Compatibility alias for updating the global scope.",
    },
    "create_visual": {
        "label": "Create visualization",
        "category": "visualization",
        "changes_dashboard": True,
        "description": "Create one evidence view from the current scope.",
    },
    "compare_category_metrics": {
        "label": "Compare category metrics",
        "category": "analytical_comparison",
        "changes_dashboard": True,
        "description": "Create coordinated views for one common Top-N category set.",
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
        "description": "Focus views and optionally highlight real data marks within them.",
    },
    "inspect_visual": {
        "label": "Inspect visualization",
        "category": "evidence_reading",
        "changes_dashboard": False,
        "description": "Read current values, statistics, and truncation metadata from one view.",
    },
    # Internal compatibility contracts. These are not exposed to the realtime
    # model after demo_tools.register_demo_tool_schemas() runs.
    "filter_data": {
        "label": "Apply data filter",
        "category": "internal_data_scope",
        "changes_dashboard": True,
        "description": "Internal primitive used by the dashboard engine.",
    },
    "remove_filter": {
        "label": "Remove data filter",
        "category": "internal_data_scope",
        "changes_dashboard": True,
        "description": "Internal primitive used by the dashboard engine.",
    },
    "append_visual": {
        "label": "Create visualization",
        "category": "internal_visualization",
        "changes_dashboard": True,
        "description": "Internal visualization engine used by create_visual.",
    },
    "set_low_score_threshold": {
        "label": "Set low-score definition",
        "category": "internal_data_definition",
        "changes_dashboard": True,
        "description": "Internal primitive; the study model uses the fixed <=2 definition.",
    },
}

CORE_TOOL_NAMES = frozenset(TOOL_CONTRACTS)


def contract_for(name: str) -> dict[str, Any]:
    """Return stable metadata for a tool name."""
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
    """Return compact metadata for one tool batch, preserving order."""
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
            if name in {
                "update_analysis_scope",
                "set_analysis_scope",
                "filter_data",
                "remove_filter",
            }:
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
            if name in {"create_visual", "append_visual"} and payload.get("view_id"):
                return f"{label} completed · {payload['view_id']}"
            if name == "delete_visual" and payload.get("view_id"):
                return f"{label} completed · removed {payload['view_id']}"
            if name == "inspect_visual" and payload.get("view_id"):
                points = payload.get("returned_data_points")
                suffix = f" · {points} points returned" if points is not None else ""
                return f"{label} completed · {payload['view_id']}{suffix}"
        return f"{label} completed"

    error = str(result.get("error") or "Tool execution failed").strip()
    return f"{label} failed · {error}"
