"""
VerbalVis tool layer.
Defines tool schemas, executes tool calls, rebuilds dashboard context.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db import (
    FIELDS,
    OPERATORS,
    aggregate_query,
    build_where,
    get_connection,
    resolve_column,
    stats_query,
    total_rows,
)

log = logging.getLogger(__name__)

COUNT_MEASURE = "order_count"
LOW_SCORE_RATIO = "low_score_ratio"
LATE_RATIO = "late_ratio"
ON_TIME_RATIO = "on_time_ratio"
HIGH_SCORE_RATIO = "high_score_ratio"
AVG_FREIGHT_RATIO = "avg_freight_ratio"
COUNTED_RATIO_MEASURES = {LOW_SCORE_RATIO, LATE_RATIO, ON_TIME_RATIO, HIGH_SCORE_RATIO}
DERIVED_MEASURES = [LOW_SCORE_RATIO, LATE_RATIO, ON_TIME_RATIO, HIGH_SCORE_RATIO, AVG_FREIGHT_RATIO]
APPEND_Y_FIELDS = FIELDS + [COUNT_MEASURE, *DERIVED_MEASURES]
SORT_FIELDS = APPEND_Y_FIELDS
TIME_FIELDS = {"order_month", "order_week", "order_date", "order_dow", "order_hour"}
NUMERIC_AVG_FIELDS = {
    "estimated_delivery_days",
    "delivery_delay_days",
    "item_count",
    "product_count",
    "category_count",
    "seller_count",
    "avg_item_price",
    "freight_ratio",
    "payment_method_count",
    "max_payment_installments",
    "primary_payment_installments",
}
ALLOWED_CHART_TYPES = {"scatter", "bar", "line", "histogram", "pie", "table"}
ALLOWED_COLOR_FIELDS = {
    "customer_state",
    "product_category",
    "review_score",
    "review_bucket",
    "delivery_status_bucket",
    "order_size_bucket",
    "primary_payment_type",
}
RATIO_COUNT_ALIASES = {
    LOW_SCORE_RATIO: "low_score_count",
    LATE_RATIO: "late_count",
    ON_TIME_RATIO: "on_time_count",
    HIGH_SCORE_RATIO: "high_score_count",
}
RATIO_STAT_ALIASES = {
    LOW_SCORE_RATIO: "low_score_orders",
    LATE_RATIO: "late_orders",
    ON_TIME_RATIO: "on_time_orders",
    HIGH_SCORE_RATIO: "high_score_orders",
}
MAX_VIEW_LIMIT = 100
LOW_SCORE_THRESHOLD_DEFAULT = 2

# ------------------------------------------------------------------
# Runtime state (per-session; single-user prototype)
# ------------------------------------------------------------------

active_filters: list[dict[str, Any]] = []
workspace_counter: int = 0          # workspace1, workspace2, …
views: list[dict[str, Any]] = []    # all views (base + workspace)
highlighted_view: str | None = None
low_score_threshold: int = LOW_SCORE_THRESHOLD_DEFAULT

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------------
# Base views (initialised once)
# ------------------------------------------------------------------

BASE_VIEWS_DEFS = [
    {
        "id": "view-trend",
        "label": "view 1-trend",
        "chart_type": "line",
        "title": "Monthly Orders Trend",
        "x_field": "order_month",
        "y_field": "order_count",
        "group_field": "order_month",
        "agg_expr": "COUNT(*)",
        "agg_alias": "order_count",
        "order_by": "order_month",
        "source_table": "fact_order",
    },
    {
        "id": "view-review",
        "label": "view 2-review",
        "chart_type": "bar",
        "title": "Review Score Distribution",
        "x_field": "review_score",
        "y_field": "order_count",
        "group_field": "review_score",
        "agg_expr": "COUNT(*)",
        "agg_alias": "order_count",
        "order_by": "review_score",
        "source_table": "fact_order",
    },
    {
        "id": "view-map",
        "label": "view 3-map",
        "chart_type": "bar",
        "title": "Orders by State",
        "x_field": "customer_state",
        "y_field": "order_count",
        "group_field": "customer_state",
        "agg_expr": "COUNT(*)",
        "agg_alias": "order_count",
        "order_by": "order_count DESC",
        "source_table": "fact_order",
    },
    {
        # NOTE: queries fact_item (item grain). Revenue is SUM of per-item
        # (price + freight) — not the previous "whole-order payment misallocated
        # to alphabetically-first category" bug.
        "id": "view-category",
        "label": "view 4-category",
        "chart_type": "bar",
        "title": "Category Revenue (Top 15)",
        "x_field": "product_category",
        "y_field": "revenue",
        "group_field": "product_category",
        "agg_expr": "ROUND(SUM(item_revenue), 2)",
        "agg_alias": "revenue",
        "order_by": "revenue DESC",
        "limit": 15,
        "source_table": "fact_item",
    },
]


def init_views() -> None:
    """Reset state and populate base views with data."""
    global active_filters, workspace_counter, views, highlighted_view, low_score_threshold
    active_filters = []
    workspace_counter = 0
    highlighted_view = None
    low_score_threshold = LOW_SCORE_THRESHOLD_DEFAULT
    views = []
    for defn in BASE_VIEWS_DEFS:
        view = {**defn, "data": [], "statistics": {}}
        views.append(view)
    _refresh_all_views()


# ------------------------------------------------------------------
# Tool Schemas
# ------------------------------------------------------------------

def _tool(name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }


TOOL_SCHEMAS = [
    _tool(
        "filter_data",
        "Apply a filter to the global dataset. All dashboard views update automatically. "
        "Pass field='__all__' to clear all filters.",
        {
            "type": "object",
            "properties": {
                "field": {
                    "type": ["string", "null"],
                    "enum": FIELDS + ["__all__", None],
                    "description": "Field to filter on. Use '__all__' to clear all filters.",
                },
                "operator": {
                    "type": "string",
                    "enum": list(OPERATORS),
                    "description": "Comparison operator.",
                },
                "value": {
                    "description": "Filter value. Use a string/number, or an array for 'in' and 'between'.",
                },
                "append": {
                    "type": "boolean",
                    "description": "true = add to existing filters; false = replace all.",
                },
            },
            "required": ["field"],
        },
    ),
    _tool(
        "highlight_visual",
        "Highlight a dashboard view to direct user attention. Other views are dimmed.",
        {
            "type": "object",
            "properties": {
                "view_id": {
                    "type": "string",
                    "description": "ID of the view to highlight.",
                },
                "highlight_element": {
                    "type": ["string", "null"],
                    "description": "Optional data point to emphasise inside the view (e.g. '2017-11', 'review_score=1').",
                },
                "dim_others": {
                    "type": "boolean",
                    "description": "Whether to dim other views. Default true.",
                },
            },
            "required": ["view_id"],
        },
    ),
    _tool(
        "remove_filter",
        "Remove active filters for one field while preserving all other filters.",
        {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": FIELDS,
                    "description": "Field whose active filters should be removed.",
                },
            },
            "required": ["field"],
        },
    ),
    _tool(
        "append_visual",
        (
            "Create a new chart and append it to the dashboard grid. "
                        "The backend automatically aggregates non-scatter charts from x/y: "
                        "order_count means grouped order count, revenue means grouped sum, "
                        "delivery_days means grouped average; low_score_ratio, late_ratio, "
                        "on_time_ratio, high_score_ratio, and avg_freight_ratio are derived. "
            "For row-level Top N requests, pass limit as a real argument. "
            "For Top N series in multi-series line charts, pass series_limit, "
            "series_sort_by, and series_sort_order. For worst/bottom Top N or "
            "explicit sorting requests, pass sort_by and sort_order."
        ),
        {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["scatter", "bar", "line", "histogram", "pie", "table"],
                },
                "x": {
                    "type": "string",
                    "enum": FIELDS,
                    "description": "X-axis field.",
                },
                "y": {
                    "type": "string",
                    "enum": APPEND_Y_FIELDS,
                    "description": (
                        "Y-axis field, order_count for count aggregations, or "
                        "a derived ratio such as low_score_ratio, late_ratio, "
                        "on_time_ratio, high_score_ratio, or avg_freight_ratio."
                    ),
                },
                "color": {
                    "type": ["string", "null"],
                    "enum": sorted(ALLOWED_COLOR_FIELDS) + [None],
                    "description": "Optional color encoding field.",
                },
                "title": {
                    "type": "string",
                    "description": "Human-readable chart title.",
                },
                "limit": {
                    "type": ["integer", "null"],
                    "description": (
                        "Optional Top N row limit after backend aggregation and sorting. "
                        "Required for user requests like Top 15, 前十五个, 保留15个, "
                        "只显示前N项. Do not express Top N only in the title."
                    ),
                },
                "sort_by": {
                    "type": ["string", "null"],
                    "enum": SORT_FIELDS + [None],
                    "description": (
                        "Optional metric/field used to sort aggregated rows before limit. "
                        "Use delivery_days for '按配送时间排序', review_score for score ranking, "
                        "low_score_ratio for low-score-rate ranking, late_ratio for delay-rate "
                        "ranking, avg_freight_ratio for freight-share ranking, and order_count "
                        "for count ranking."
                    ),
                },
                "sort_order": {
                    "type": ["string", "null"],
                    "enum": ["asc", "desc", None],
                    "description": (
                        "Sort direction before applying limit. asc means low-to-high/short-to-long; "
                        "desc means high-to-low/long-to-short. For worst Top N choose the bad direction "
                        "for the metric, e.g. review_score asc, delivery_days desc, late_ratio desc, "
                        "low_score_ratio desc."
                    ),
                },
                "series_limit": {
                    "type": ["integer", "null"],
                    "description": "For multi-series line/bar charts and state/category tables: keep Top N series values.",
                },
                "series_sort_by": {
                    "type": ["string", "null"],
                    "enum": SORT_FIELDS + [None],
                    "description": "Metric used to rank series values, e.g. revenue for top revenue categories.",
                },
                "series_sort_order": {
                    "type": ["string", "null"],
                    "enum": ["asc", "desc", None],
                },
                "low_score_threshold": {
                    "type": ["integer", "null"],
                    "description": (
                        "Threshold for low_score_ratio. Default is current dashboard low-score threshold "
                        "(initially 2). Use 3 when the user defines low-score as review_score <= 3."
                    ),
                },
                "filters": {
                    "type": ["array", "null"],
                    "description": (
                        "Optional chart-local filters applied only to this new view. "
                        "Each filter has field, operator, and value."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "enum": FIELDS},
                            "operator": {"type": "string", "enum": list(OPERATORS)},
                            "value": {
                                "description": "Filter value. Use an array for 'in' and 'between'.",
                            },
                        },
                        "required": ["field", "operator", "value"],
                    },
                },
                "inherit_global_filters": {
                    "type": "boolean",
                    "description": (
                        "Whether the new view should also use current global filters. "
                        "Default true. Set false for independent comparison charts."
                    ),
                },
                "freeze": {
                    "type": "boolean",
                    "description": (
                        "If true, keep this view's data snapshot fixed when global "
                        "filters later change."
                    ),
                },
            },
            "required": ["chart_type", "x", "y", "title"],
        },
    ),
    _tool(
        "set_low_score_threshold",
        (
            "Set the dashboard-wide definition of low-score orders for low_score_ratio. "
            "For example threshold=3 means review_score <= 3. Existing low_score_ratio "
            "views refresh automatically unless they were frozen."
        ),
        {
            "type": "object",
            "properties": {
                "threshold": {
                    "type": "integer",
                    "description": "Low-score maximum review_score, from 1 to 5.",
                },
            },
            "required": ["threshold"],
        },
    ),
    _tool(
        "delete_visual",
        "Delete a chart/view from the dashboard grid by its view_id. "
        "Use this to remove a view the user no longer wants. The remaining views are unaffected.",
        {
            "type": "object",
            "properties": {
                "view_id": {
                    "type": "string",
                    "description": "ID of the view to delete (e.g. 'workspace1', 'view-trend').",
                },
            },
            "required": ["view_id"],
        },
    ),
]


# ------------------------------------------------------------------
# Tool execution
# ------------------------------------------------------------------

def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool and return a unified result dict."""
    try:
        if name == "filter_data":
            return _exec_filter_data(arguments)
        elif name == "highlight_visual":
            return _exec_highlight_visual(arguments)
        elif name == "remove_filter":
            return _exec_remove_filter(arguments)
        elif name == "append_visual":
            return _exec_append_visual(arguments)
        elif name == "set_low_score_threshold":
            return _exec_set_low_score_threshold(arguments)
        elif name == "delete_visual":
            return _exec_delete_visual(arguments)
        else:
            return {"tool": name, "success": False, "error": f"Unknown tool: {name}"}
    except Exception as exc:
        log.exception("Tool execution error: %s", name)
        return {"tool": name, "success": False, "error": str(exc)}


def normalize_tool_arguments(
    name: str,
    arguments: dict[str, Any],
    *,
    user_transcript: str = "",
) -> dict[str, Any]:
    """Normalize small speech-model argument slips before executing a tool."""
    normalized = dict(arguments or {})
    if user_transcript:
        normalized["_user_transcript"] = user_transcript
    if name in {"filter_data", "append_visual"} and "value" in normalized:
        normalized["value"] = _coerce_jsonish(normalized["value"])
    append_text = ""
    wants_state_category_table = False
    if name == "append_visual":
        append_text = " ".join(str(v or "") for v in (normalized.get("title"), user_transcript))
        wants_state_category_table = _wants_state_category_table(append_text)
    if (
        name == "append_visual"
        and not wants_state_category_table
        and normalized.get("limit") in (None, "")
        and normalized.get("series_limit") in (None, "")
    ):
        inferred_limit = _infer_limit_from_text(
            normalized.get("title", ""),
            user_transcript,
        )
        if inferred_limit is not None:
            normalized["limit"] = inferred_limit
    if name == "append_visual":
        text = append_text
        if wants_state_category_table:
            normalized["chart_type"] = "table"
            normalized["x"] = "customer_state"
            normalized["y"] = "revenue"
            normalized["color"] = "product_category"
            if normalized.get("limit") in (None, ""):
                normalized["limit"] = _infer_state_limit_from_text(text) or 10
            if normalized.get("series_limit") in (None, ""):
                normalized["series_limit"] = _infer_category_rank_limit_from_text(text) or 3
            if normalized.get("sort_by") in (None, ""):
                normalized["sort_by"] = "revenue"
            if normalized.get("sort_order") in (None, ""):
                normalized["sort_order"] = "desc"
            if normalized.get("series_sort_by") in (None, ""):
                normalized["series_sort_by"] = "revenue"
            if normalized.get("series_sort_order") in (None, ""):
                normalized["series_sort_order"] = "desc"
        if _wants_pie_chart(text) and normalized.get("chart_type") in (None, "", "bar"):
            normalized["chart_type"] = "pie"
        if _wants_delivery_speed_bucket(text) and normalized.get("x") in (None, "", "delivery_days"):
            normalized["x"] = "delivery_speed_bucket"
        if normalized.get("sort_by") in (None, ""):
            inferred_sort_by = _infer_sort_by_from_text(text)
            if inferred_sort_by:
                normalized["sort_by"] = inferred_sort_by
        if normalized.get("sort_order") in (None, ""):
            inferred_sort_order = _infer_sort_order_from_text(
                text,
                normalized.get("sort_by") or normalized.get("y"),
            )
            if inferred_sort_order:
                normalized["sort_order"] = inferred_sort_order
        if normalized.get("low_score_threshold") in (None, ""):
            inferred_threshold = _infer_low_score_threshold_from_text(user_transcript)
            if inferred_threshold is not None:
                normalized["low_score_threshold"] = inferred_threshold
    if name == "set_low_score_threshold" and normalized.get("threshold") in (None, ""):
        inferred_threshold = _infer_low_score_threshold_from_text(user_transcript)
        if inferred_threshold is not None:
            normalized["threshold"] = inferred_threshold
    if name != "filter_data":
        return normalized

    transcript = user_transcript.strip()
    if (
        normalized.get("field") == "review_score"
        and str(normalized.get("operator", "")).lower() == "lte"
        and str(normalized.get("value", "")).strip() in {"3", "3.0"}
        and any(phrase in transcript for phrase in ("低于三分", "小于三分", "低于3分", "小于3分"))
        and not any(phrase in transcript for phrase in ("及以下", "以下含", "包含三", "包括三"))
    ):
        normalized["value"] = "2"

    return normalized


# --- filter_data ---

def _exec_filter_data(args: dict) -> dict:
    global active_filters

    field = args.get("field")
    if field in (None, "__all__"):
        active_filters = []
        _refresh_all_views()
        return {
            "tool": "filter_data",
            "success": True,
            "payload": {
                "action": "cleared",
                "active_filters": [],
                "filtered_rows": total_rows([]),
            },
        }

    new_filter, error = _normalize_filter(args, tool_name="filter_data")
    if error:
        return error
    assert new_filter is not None

    append = args.get("append", False)
    append = bool(append) if isinstance(append, bool) else str(append).lower() == "true"

    if append:
        active_filters.append(new_filter)
    else:
        active_filters = [new_filter]

    _refresh_all_views()

    rows = total_rows(active_filters)
    result: dict[str, Any] = {
        "tool": "filter_data",
        "success": True,
        "payload": {
            "active_filters": active_filters.copy(),
            "filtered_rows": rows,
        },
    }
    if rows == 0:
        result["warning"] = (
            f"Filter returned 0 rows. Current filters: "
            f"{_filters_summary()}. Consider relaxing filters."
        )
    return result


# --- remove_filter ---

def _exec_remove_filter(args: dict) -> dict:
    global active_filters

    field = args.get("field")
    if field not in FIELDS:
        return {
            "tool": "remove_filter",
            "success": False,
            "error": f"Unknown field: '{field}'. Available: {', '.join(FIELDS)}",
        }

    before = len(active_filters)
    active_filters = [f for f in active_filters if f.get("field") != field]
    removed_count = before - len(active_filters)
    _refresh_all_views()

    return {
        "tool": "remove_filter",
        "success": True,
        "payload": {
            "removed_field": field,
            "removed_count": removed_count,
            "active_filters": active_filters.copy(),
            "filtered_rows": total_rows(active_filters),
        },
    }


# --- set_low_score_threshold ---

def _exec_set_low_score_threshold(args: dict) -> dict:
    global low_score_threshold

    threshold = _coerce_low_score_threshold(args.get("threshold"))
    if threshold is None:
        return {
            "tool": "set_low_score_threshold",
            "success": False,
            "error": "threshold must be an integer from 1 to 5.",
        }

    low_score_threshold = threshold
    _refresh_all_views()

    return {
        "tool": "set_low_score_threshold",
        "success": True,
        "payload": {
            "low_score_threshold": low_score_threshold,
            "definition": f"review_score <= {low_score_threshold}",
            "active_filters": active_filters.copy(),
            "filtered_rows": total_rows(active_filters),
        },
    }


# --- highlight_visual ---

def _exec_highlight_visual(args: dict) -> dict:
    global highlighted_view

    view_id = args.get("view_id")
    view_ids = [v["id"] for v in views]
    if view_id not in view_ids:
        return {
            "tool": "highlight_visual",
            "success": False,
            "error": f"Unknown view_id: '{view_id}'. Available: {', '.join(view_ids)}",
        }

    dim_others = args.get("dim_others", True)
    highlight_element = args.get("highlight_element")
    highlighted_view = view_id

    return {
        "tool": "highlight_visual",
        "success": True,
        "payload": {
            "view_id": view_id,
            "highlight_element": highlight_element,
            "dim_others": dim_others,
        },
    }


# --- append_visual ---

def _exec_append_visual(args: dict) -> dict:
    global workspace_counter

    x = args.get("x")
    y = args.get("y")
    color = args.get("color")
    title = args.get("title") or f"{y} by {x}"
    chart_type = args.get("chart_type")
    user_text = args.get("_user_transcript") or args.get("user_transcript") or ""
    if chart_type in {"bar", None, ""} and _wants_pie_chart(title, user_text):
        chart_type = "pie"
    sort_by = args.get("sort_by")
    if sort_by in ("", None):
        sort_by = None
    sort_order = args.get("sort_order")
    if sort_order in ("", None):
        sort_order = None
    series_limit_arg = args.get("series_limit")
    explicit_series_limit = series_limit_arg not in (None, "")
    if not explicit_series_limit:
        series_limit_arg = None
    series_limit = _coerce_limit(series_limit_arg)
    series_sort_by = args.get("series_sort_by")
    if series_sort_by in ("", None):
        series_sort_by = None
    series_sort_order = args.get("series_sort_order") or "desc"
    limit_arg = args.get("limit")
    explicit_limit = limit_arg not in (None, "")
    is_state_category_table_candidate = (
        chart_type == "table" and x == "customer_state" and y == "revenue"
    )
    if not explicit_limit and series_limit is None and not is_state_category_table_candidate:
        limit_arg = _infer_limit_from_text(title)
    limit = _coerce_limit(limit_arg)
    low_score_threshold_arg = args.get("low_score_threshold")
    low_score_threshold_for_view = _coerce_low_score_threshold(low_score_threshold_arg)
    inherit_global_filters = _as_bool(args.get("inherit_global_filters", True))
    freeze = _as_bool(args.get("freeze", args.get("frozen", False)))
    local_filters, filter_error = _normalize_local_filters(
        args.get("filters") if args.get("filters") is not None else args.get("view_filters"),
        tool_name="append_visual",
    )
    if filter_error:
        return filter_error

    if is_state_category_table_candidate:
        color = color or "product_category"
        if not explicit_series_limit:
            series_limit = 3
        series_sort_by = series_sort_by or "revenue"
        series_sort_order = series_sort_order or "desc"
        if not explicit_limit:
            limit = _infer_state_limit_from_text(title, user_text) or 10
        sort_by = sort_by or "revenue"
        sort_order = sort_order or "desc"

    # Validate (the JSON schema enums constrain a well-behaved model, but the
    # Realtime API does not guarantee enum adherence at runtime — without
    # this check a hallucinated field/chart_type goes straight into raw SQL
    # f-strings in aggregate_query()/_scatter_data() and surfaces as a
    # confusing DuckDB parser error instead of a clean tool error).
    if chart_type not in ALLOWED_CHART_TYPES:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown chart_type: '{chart_type}'. Available: {', '.join(sorted(ALLOWED_CHART_TYPES))}",
        }
    if x not in FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for x: '{x}'. Available: {', '.join(FIELDS)}",
        }
    if y not in APPEND_Y_FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for y: '{y}'. Available: {', '.join(APPEND_Y_FIELDS)}",
        }
    if sort_by is not None and sort_by not in SORT_FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for sort_by: '{sort_by}'. Available: {', '.join(SORT_FIELDS)}",
        }
    if sort_order is not None and sort_order not in {"asc", "desc"}:
        return {
            "tool": "append_visual",
            "success": False,
            "error": "sort_order must be 'asc' or 'desc'.",
        }
    if series_limit_arg is not None and series_limit is None:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"series_limit must be an integer between 1 and {MAX_VIEW_LIMIT}.",
        }
    if series_sort_by is not None and series_sort_by not in SORT_FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for series_sort_by: '{series_sort_by}'. Available: {', '.join(SORT_FIELDS)}",
        }
    if series_sort_order not in {"asc", "desc"}:
        return {
            "tool": "append_visual",
            "success": False,
            "error": "series_sort_order must be 'asc' or 'desc'.",
        }
    if low_score_threshold_arg is not None and low_score_threshold_for_view is None:
        return {
            "tool": "append_visual",
            "success": False,
            "error": "low_score_threshold must be an integer from 1 to 5.",
        }
    if chart_type == "scatter" and y == COUNT_MEASURE:
        return {
            "tool": "append_visual",
            "success": False,
            "error": "Scatter plots require a raw numeric y field, not order_count. Use a bar or line chart for order_count.",
        }
    if chart_type == "scatter" and y in DERIVED_MEASURES:
        return {
            "tool": "append_visual",
            "success": False,
            "error": "Scatter plots require raw numeric fields. Use a bar or line chart for derived metrics like low_score_ratio.",
        }
    if color is not None and color not in ALLOWED_COLOR_FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for color: '{color}'. Available: {', '.join(sorted(ALLOWED_COLOR_FIELDS))}",
        }
    if chart_type == "table" and not (
        x == "customer_state" and y == "revenue" and color == "product_category"
    ):
        return {
            "tool": "append_visual",
            "success": False,
            "error": (
                "Table visuals currently support state/category revenue tables only: "
                "use x=customer_state, y=revenue, color=product_category."
            ),
        }
    if limit_arg is not None and limit is None:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"limit must be an integer between 1 and {MAX_VIEW_LIMIT}.",
        }

    workspace_counter += 1
    view_id = f"workspace{workspace_counter}"

    # Route to fact_item whenever product_category is involved (x / y / color);
    # otherwise stay on fact_order. Keeps revenue at item grain when grouping
    # by category, and avoids cross-grain joins when not needed.
    source_table = _decide_table(x, y, color, sort_by, series_sort_by)
    low_score_threshold_for_view = low_score_threshold_for_view or low_score_threshold

    # Determine aggregation
    agg_expr, agg_alias, group_field, order_by = _infer_agg(
        chart_type,
        x,
        y,
        source_table,
        low_score_threshold_for_view,
    )
    sort_by = sort_by or _default_sort_by(chart_type, x, y)
    sort_order = sort_order or _default_sort_order(chart_type, x, sort_by)

    # color is only meaningful as a *grouping* dimension for bar/line charts.
    # Scatter draws raw rows (color column requested directly); histogram
    # bins client-side in Vega-Lite and never had a color encoding to begin
    # with. Without this, a bar/line chart with a color encoding would query
    # data that never contains the color column, so the chart silently
    # renders with no color at all.
    extra_group_fields = [color] if (color and chart_type in ("bar", "line")) else None

    view_def: dict[str, Any] = {
        "id": view_id,
        "chart_type": chart_type,
        "title": title,
        "x_field": x,
        "y_field": y,
        "color": color,
        "group_field": group_field,
        "agg_expr": agg_expr,
        "agg_alias": agg_alias,
        "order_by": order_by,
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "series_limit": series_limit,
        "series_sort_by": series_sort_by,
        "series_sort_order": series_sort_order,
        "low_score_threshold": low_score_threshold_for_view,
        "filters": local_filters,
        "inherit_global_filters": inherit_global_filters,
        "freeze": freeze,
        "snapshot_filters": [],
        "source_table": source_table,
        "data": [],
        "statistics": {},
    }
    if _is_state_category_table(view_def):
        view_def["table_columns"] = _state_category_table_columns(series_limit or 3)

    effective_filters = _effective_filters_for_view(view_def)
    if freeze:
        view_def["snapshot_filters"] = [*effective_filters]

    # Query data
    if chart_type == "scatter":
        view_def["data"] = _scatter_data(x, y, color, source_table, filters=effective_filters)
    elif _is_state_category_table(view_def):
        view_def["data"] = _state_category_table_data(view_def, filters=effective_filters)
    else:
        data = _aggregate_visual_data(
            view_def,
            filters=effective_filters,
            extra_group_fields=extra_group_fields,
        )
        if limit and not _uses_series_limit(view_def):
            data = data[:limit]
        _attach_rank(data)
        view_def["data"] = data

    view_def["statistics"] = _compute_view_stats(view_def)
    views.append(view_def)

    return {
        "tool": "append_visual",
        "success": True,
        "payload": {
            "view_id": view_id,
            "chart_type": chart_type,
            "x": x,
            "y": y,
            "color": color,
            "title": title,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "series_limit": series_limit,
            "series_sort_by": series_sort_by,
            "series_sort_order": series_sort_order,
            "low_score_threshold": low_score_threshold_for_view,
            "filters": local_filters,
            "inherit_global_filters": inherit_global_filters,
            "freeze": freeze,
            "filter_scope": _filter_scope(view_def),
            "effective_filters": effective_filters,
            "snapshot_filters": view_def.get("snapshot_filters", []),
            "table_columns": view_def.get("table_columns"),
            "data": view_def["data"],
            "statistics": view_def["statistics"],
            "filtered_rows": total_rows(effective_filters),
        },
    }


# --- delete_visual ---

def _exec_delete_visual(args: dict) -> dict:
    global views, highlighted_view

    view_id = args.get("view_id")
    view_ids = [v["id"] for v in views]
    if view_id not in view_ids:
        return {
            "tool": "delete_visual",
            "success": False,
            "error": f"Unknown view_id: '{view_id}'. Available: {', '.join(view_ids)}",
        }

    deleted = next(v for v in views if v["id"] == view_id)
    views = [v for v in views if v["id"] != view_id]

    # Clear highlight if the deleted view was the highlighted one.
    if highlighted_view == view_id:
        highlighted_view = None

    return {
        "tool": "delete_visual",
        "success": True,
        "payload": {
            "view_id": view_id,
            "title": deleted.get("title"),
            "remaining_view_ids": [v["id"] for v in views],
        },
    }


def _decide_table(
    x: str,
    y: str,
    color: str | None,
    sort_by: str | None = None,
    series_sort_by: str | None = None,
) -> str:
    """Choose source table for an append_visual call.

    Any reference to product_category forces fact_item (item grain). Otherwise
    fact_order is enough — all order-level filter fields exist on it.
    """
    if "product_category" in (x, y, color, sort_by, series_sort_by):
        return "fact_item"
    return "fact_order"


def _infer_agg(chart_type: str, x: str, y: str, table: str, threshold: int | None = None):
    """Infer SQL aggregation from chart type, fields, and source table."""
    if chart_type == "scatter":
        return y, y, x, x  # no aggregation needed
    if chart_type == "histogram":
        return "COUNT(*)", "count", x, x
    # bar / line / pie
    expr, alias = _measure_expr(y, table, threshold or low_score_threshold)
    return expr, alias, x, _default_order_by(chart_type, x, alias)


def _is_state_category_table(view: dict[str, Any]) -> bool:
    return (
        view.get("chart_type") == "table"
        and view.get("x_field") == "customer_state"
        and view.get("y_field") == "revenue"
        and view.get("color") == "product_category"
    )


def _state_category_table_columns(series_limit: int) -> list[dict[str, str]]:
    columns = [
        {"key": "customer_state", "label": "州"},
        {"key": "state_revenue", "label": "州销售额"},
    ]
    for idx in range(1, series_limit + 1):
        columns.append({"key": f"top_{idx}", "label": f"第{idx}名品类"})
    return columns


def _state_category_table_data(
    view: dict[str, Any],
    filters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Top categories per state, formatted for compact table visuals."""
    con = get_connection()
    table = view.get("source_table", "fact_item")
    where = build_where(filters, table=table)
    state_limit = _coerce_limit(view.get("limit")) or 10
    category_limit = _coerce_limit(view.get("series_limit")) or 3
    sort_direction = "ASC" if view.get("sort_order") == "asc" else "DESC"
    series_direction = "ASC" if view.get("series_sort_order") == "asc" else "DESC"

    sql = f"""
        WITH base AS (
            SELECT customer_state, product_category, item_revenue
            FROM {table}
            WHERE {where}
              AND customer_state IS NOT NULL
              AND product_category IS NOT NULL
        ),
        state_totals AS (
            SELECT
                customer_state,
                ROUND(SUM(item_revenue), 2) AS state_revenue
            FROM base
            GROUP BY customer_state
        ),
        ranked_states AS (
            SELECT
                customer_state,
                state_revenue,
                ROW_NUMBER() OVER (
                    ORDER BY state_revenue {sort_direction}, customer_state ASC
                ) AS state_rank
            FROM state_totals
            ORDER BY state_revenue {sort_direction}, customer_state ASC
            LIMIT {state_limit}
        ),
        category_totals AS (
            SELECT
                customer_state,
                product_category,
                ROUND(SUM(item_revenue), 2) AS category_revenue
            FROM base
            GROUP BY customer_state, product_category
        ),
        ranked_categories AS (
            SELECT
                ct.customer_state,
                ct.product_category,
                ct.category_revenue,
                rs.state_revenue,
                rs.state_rank,
                ROW_NUMBER() OVER (
                    PARTITION BY ct.customer_state
                    ORDER BY ct.category_revenue {series_direction}, ct.product_category ASC
                ) AS category_rank
            FROM category_totals ct
            JOIN ranked_states rs USING (customer_state)
        )
        SELECT
            customer_state,
            product_category,
            category_revenue,
            state_revenue,
            state_rank,
            category_rank
        FROM ranked_categories
        WHERE category_rank <= {category_limit}
        ORDER BY state_rank ASC, category_rank ASC
    """
    result = con.execute(sql)
    col_names = [d[0] for d in result.description]
    detail_rows = [dict(zip(col_names, row)) for row in result.fetchall()]

    by_state: dict[str, dict[str, Any]] = {}
    for item in detail_rows:
        state = item["customer_state"]
        state_revenue_raw = float(item.get("state_revenue") or 0)
        category_revenue_raw = float(item.get("category_revenue") or 0)
        category_rank = int(item.get("category_rank") or 0)
        share_int = int(round((category_revenue_raw / state_revenue_raw) * 100)) if state_revenue_raw else 0
        state_revenue_int = int(round(state_revenue_raw))
        category_revenue_int = int(round(category_revenue_raw))
        row = by_state.setdefault(
            state,
            {
                "customer_state": state,
                "state_revenue": state_revenue_int,
                "state_rank": int(item.get("state_rank") or 0),
            },
        )
        row[f"top_{category_rank}"] = (
            f"{item['product_category']} ({category_revenue_int}, {share_int}%)"
        )
        row[f"top_{category_rank}_category"] = item["product_category"]
        row[f"top_{category_rank}_revenue"] = category_revenue_int
        row[f"top_{category_rank}_share"] = share_int

    rows = sorted(by_state.values(), key=lambda row: row.get("state_rank", 0))
    for row in rows:
        for idx in range(1, category_limit + 1):
            row.setdefault(f"top_{idx}", "")
    return rows


def _aggregate_visual_data(
    view: dict[str, Any],
    filters: list[dict[str, Any]],
    extra_group_fields: list[str] | None,
) -> list[dict[str, Any]]:
    if _uses_series_limit(view):
        return _series_limited_aggregate_data(view, filters, extra_group_fields)

    con = get_connection()
    table = view.get("source_table", "fact_order")
    group_field = view["group_field"]
    y = view["y_field"]
    agg_alias = view["agg_alias"]
    agg_expr = view["agg_expr"]
    has_view_sort = view.get("sort_by") not in (None, "")
    sort_by = view.get("sort_by") or _default_sort_by(view["chart_type"], view["x_field"], y)
    sort_order = view.get("sort_order") or _default_sort_order(view["chart_type"], view["x_field"], sort_by)
    threshold = view.get("low_score_threshold", low_score_threshold)

    where = build_where(filters, table=table)
    extra = extra_group_fields or []
    group_cols = [group_field, *extra]
    select_cols = ", ".join(group_cols)
    select_parts = [select_cols]
    if y in COUNTED_RATIO_MEASURES:
        numerator_expr, total_expr = _counted_ratio_count_exprs(y, table, threshold)
        numerator_alias = _ratio_count_alias(y)
        select_parts.extend([
            f"{numerator_expr} AS {numerator_alias}",
            f"{total_expr} AS order_count",
            f"{agg_expr} AS {agg_alias}",
        ])
    else:
        select_parts.append(f"{agg_expr} AS {agg_alias}")

    if not has_view_sort and view.get("order_by"):
        order_sql = view["order_by"]
    elif sort_by in (None, group_field):
        order_col = group_field
        order_sql = _order_sql(order_col, sort_order)
    elif sort_by == agg_alias or sort_by == y:
        order_col = agg_alias
        order_sql = _order_sql(order_col, sort_order)
    else:
        sort_expr, _ = _measure_expr(sort_by, table, threshold)
        order_col = "sort_value"
        select_parts.append(f"{sort_expr} AS {order_col}")
        order_sql = _order_sql(order_col, sort_order)
    sql = f"""
        SELECT {", ".join(select_parts)}
        FROM {table}
        WHERE {where}
        GROUP BY {select_cols}
        ORDER BY {order_sql}
    """
    result = con.execute(sql)
    col_names = [d[0] for d in result.description]
    return [dict(zip(col_names, row)) for row in result.fetchall()]


def _uses_series_limit(view: dict[str, Any]) -> bool:
    return (
        view.get("chart_type") == "line"
        and bool(view.get("color"))
        and bool(view.get("series_limit"))
    )


def _series_limited_aggregate_data(
    view: dict[str, Any],
    filters: list[dict[str, Any]],
    extra_group_fields: list[str] | None,
) -> list[dict[str, Any]]:
    con = get_connection()
    table = view.get("source_table", "fact_order")
    group_field = view["group_field"]
    color = view["color"]
    y = view["y_field"]
    agg_alias = view["agg_alias"]
    agg_expr = view["agg_expr"]
    threshold = view.get("low_score_threshold", low_score_threshold)
    series_limit = int(view["series_limit"])
    series_sort_by = view.get("series_sort_by") or y
    series_sort_order = view.get("series_sort_order") or "desc"
    series_direction = "ASC" if series_sort_order == "asc" else "DESC"

    where = build_where(filters, table=table)
    extra = extra_group_fields or [color]
    group_cols = [group_field, *extra]
    select_cols = ", ".join(group_cols)
    select_parts = [select_cols]
    if y in COUNTED_RATIO_MEASURES:
        numerator_expr, total_expr = _counted_ratio_count_exprs(y, table, threshold)
        numerator_alias = _ratio_count_alias(y)
        select_parts.extend([
            f"{numerator_expr} AS {numerator_alias}",
            f"{total_expr} AS order_count",
            f"{agg_expr} AS {agg_alias}",
        ])
    else:
        select_parts.append(f"{agg_expr} AS {agg_alias}")
    select_parts.append("ranked_series.series_sort_value AS series_sort_value")

    series_sort_expr, _ = _measure_expr(series_sort_by, table, threshold)
    sql = f"""
        WITH base AS (
            SELECT *
            FROM {table}
            WHERE {where}
        ),
        ranked_series AS (
            SELECT
                {color},
                {series_sort_expr} AS series_sort_value
            FROM base
            WHERE {color} IS NOT NULL
            GROUP BY {color}
            ORDER BY series_sort_value {series_direction}
            LIMIT {series_limit}
        )
        SELECT {", ".join(select_parts)}
        FROM base
        JOIN ranked_series USING ({color})
        GROUP BY {select_cols}, ranked_series.series_sort_value
        ORDER BY {group_field} ASC, ranked_series.series_sort_value {series_direction}, {color} ASC
    """
    result = con.execute(sql)
    col_names = [d[0] for d in result.description]
    return [dict(zip(col_names, row)) for row in result.fetchall()]


def _scatter_data(
    x: str,
    y: str,
    color: str | None = None,
    table: str = "fact_order",
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """Get raw rows for scatter plot (sampled to 2000 max).

    Filter-system names like "revenue" are resolved to the right physical
    column on the chosen table and aliased back so the returned rows carry
    the original field name the frontend expects.
    """
    con = get_connection()
    where = build_where(active_filters if filters is None else filters, table=table)

    def _proj(field: str) -> str:
        col = resolve_column(field, table)
        return f"{col} AS {field}" if col != field else field

    x_col = resolve_column(x, table)
    y_col = resolve_column(y, table)
    select_parts = [_proj(x), _proj(y)]
    if color:
        select_parts.append(_proj(color))
    cols_sql = ", ".join(select_parts)

    sql = f"""
        SELECT {cols_sql} FROM {table}
        WHERE {where} AND {x_col} IS NOT NULL AND {y_col} IS NOT NULL
        USING SAMPLE 2000
    """
    result = con.execute(sql)
    col_names = [d[0] for d in result.description]
    return [dict(zip(col_names, row)) for row in result.fetchall()]


# ------------------------------------------------------------------
# Data refresh
# ------------------------------------------------------------------

def _refresh_all_views() -> None:
    """Re-query data + stats for all views using current active_filters."""
    for view in views:
        if view.get("freeze"):
            continue
        table = view.get("source_table", "fact_order")
        effective_filters = _effective_filters_for_view(view)
        if view["chart_type"] == "scatter":
            view["data"] = _scatter_data(
                view["x_field"],
                view["y_field"],
                view.get("color"),
                table,
                filters=effective_filters,
            )
        elif _is_state_category_table(view):
            view["data"] = _state_category_table_data(view, filters=effective_filters)
        else:
            limit = view.get("limit")
            color = view.get("color")
            extra_group_fields = (
                [color] if (color and view["chart_type"] in ("bar", "line")) else None
            )
            data = _aggregate_visual_data(
                view,
                filters=effective_filters,
                extra_group_fields=extra_group_fields,
            )
            if limit and not _uses_series_limit(view):
                data = data[:limit]
            _attach_rank(data)
            view["data"] = data
        view["statistics"] = _compute_view_stats(view)


def _compute_view_stats(view: dict) -> dict:
    """Compute summary statistics for a view."""
    data = view["data"]
    if not data:
        return {"row_count": 0}

    vid = view["id"]
    y = view.get("agg_alias") or view["y_field"]

    stats: dict[str, Any] = {"row_count": len(data)}
    if view.get("chart_type") == "table":
        state_revenues = [
            d.get("state_revenue", 0) or 0
            for d in data
            if d.get("customer_state") is not None
        ]
        stats["state_count"] = len(data)
        stats["category_columns"] = max(int(view.get("series_limit") or 0), 0)
        if data and state_revenues:
            top = max(data, key=lambda d: d.get("state_revenue", 0) or 0)
            stats["top_state"] = top.get("customer_state")
            stats["top_state_revenue"] = top.get("state_revenue")
        return stats

    if y in COUNTED_RATIO_MEASURES:
        total_orders = sum(d.get("order_count", 0) or 0 for d in data)
        count_alias = _ratio_count_alias(y)
        stat_alias = _ratio_stat_alias(y)
        matching_orders = sum(d.get(count_alias, 0) or 0 for d in data)
        stats["total_orders"] = total_orders
        stats[stat_alias] = matching_orders
        stats[f"overall_{y}"] = round(matching_orders / total_orders, 4) if total_orders else 0

    try:
        if vid == "view-trend" or view["chart_type"] == "line":
            values = [(d.get(view["x_field"]), d.get(y, 0)) for d in data if d.get(y) is not None]
            if values:
                peak = max(values, key=lambda t: t[1])
                avg_val = sum(v[1] for v in values) / len(values)
                stats["peak_label"] = str(peak[0])
                stats["peak_value"] = peak[1]
                stats["avg_value"] = round(avg_val, 4 if y in DERIVED_MEASURES else 1)
                if view["x_field"] == "order_month":
                    stats["peak_month"] = str(peak[0])
                    stats["avg_monthly"] = round(avg_val, 1)

        elif vid == "view-review":
            total = sum(d.get(y, 0) for d in data)
            if total > 0:
                low = sum(d.get(y, 0) for d in data if d.get("review_score") is not None and d["review_score"] <= 2)
                stats["low_score_ratio"] = round(low / total, 3)
                dominant = max(data, key=lambda d: d.get(y, 0))
                stats["dominant_score"] = dominant.get("review_score")

        elif vid == "view-map":
            if data:
                top = data[0]
                bottom = min(data, key=lambda d: d.get(y, 0))
                total = sum(d.get(y, 0) for d in data)
                stats["top_state"] = top.get("customer_state")
                stats["top_state_count"] = top.get(y)
                stats["top_state_ratio"] = round(top.get(y, 0) / total, 3) if total else 0
                stats["bottom_state"] = bottom.get("customer_state")
                stats["bottom_state_count"] = bottom.get(y)
                stats["state_count"] = len(data)

        elif vid == "view-category":
            if data:
                top = data[0]
                stats["top_category"] = top.get("product_category")
                stats["top_revenue"] = top.get(y)
                stats["category_count"] = len(data)

        elif view["chart_type"] == "scatter":
            x_field = view["x_field"]
            y_field = view["y_field"]
            x_vals = [d[x_field] for d in data if d.get(x_field) is not None]
            y_vals = [d[y_field] for d in data if d.get(y_field) is not None]
            if x_vals:
                stats["mean_x"] = round(sum(x_vals) / len(x_vals), 2)
            if y_vals:
                stats["mean_y"] = round(sum(y_vals) / len(y_vals), 2)
            stats["sample_size"] = len(data)

        else:
            # Generic: find top bucket
            if data:
                top = max(data, key=lambda d: d.get(y, 0))
                bottom = min(data, key=lambda d: d.get(y, 0))
                stats["top_value"] = top.get(y)
                stats["top_label"] = top.get(view.get("group_field", view["x_field"]))
                stats["bottom_value"] = bottom.get(y)
                stats["bottom_label"] = bottom.get(view.get("group_field", view["x_field"]))
    except Exception as exc:
        log.warning("Stats computation error for %s: %s", vid, exc)

    return stats


# ------------------------------------------------------------------
# Dashboard context (injected into Realtime after each tool call)
# ------------------------------------------------------------------

def rebuild_context() -> dict[str, Any]:
    """Build compact context dict for the Realtime model."""
    ctx_views = []
    for v in views:
        view_context = {
            "id": v["id"],
            "chart_type": v["chart_type"],
            "title": v["title"],
            "x_field": v["x_field"],
            "y_field": v["y_field"],
            "color": v.get("color"),
            "limit": v.get("limit"),
            "sort_by": v.get("sort_by"),
            "sort_order": v.get("sort_order"),
            "series_limit": v.get("series_limit"),
            "series_sort_by": v.get("series_sort_by"),
            "series_sort_order": v.get("series_sort_order"),
            "table_columns": v.get("table_columns"),
            "low_score_threshold": v.get("low_score_threshold", low_score_threshold),
            "filters": v.get("filters", []),
            "inherit_global_filters": v.get("inherit_global_filters", True),
            "freeze": v.get("freeze", False),
            **_view_scope_payload(v),
            "statistics": v["statistics"],
        }
        if v.get("chart_type") == "table":
            view_context["data"] = v.get("data", [])
        ctx_views.append(view_context)

    return {
        "active_filters": active_filters.copy(),
        "low_score_threshold": low_score_threshold,
        "low_score_definition": f"review_score <= {low_score_threshold}",
        "highlighted_view": highlighted_view,
        "views": ctx_views,
        "available_view_ids": [v["id"] for v in views],
        "filtered_rows": total_rows(active_filters),
    }


def context_text() -> str:
    """Compact text summary for injection via conversation.item.create."""
    ctx = rebuild_context()

    filters = (
        "; ".join(f"{f['field']} {f['operator']} {f['value']}" for f in ctx["active_filters"])
        if ctx["active_filters"]
        else "none"
    )
    lines = [
        "Dashboard state:",
        f"filters={filters}",
        f"low_score_definition=review_score <= {ctx['low_score_threshold']}",
        f"rows={ctx['filtered_rows']}",
        f"highlighted={ctx['highlighted_view'] or 'none'}",
        "views:",
    ]
    for v in ctx["views"]:
        stat_str = ", ".join(f"{k}={v_}" for k, v_ in v["statistics"].items() if k != "row_count")
        meta = []
        if v.get("limit"):
            meta.append(f"limit={v['limit']}")
        if v.get("sort_by"):
            meta.append(f"sort={v.get('sort_by')} {v.get('sort_order') or ''}".strip())
        if v.get("series_limit"):
            series_sort = v.get("series_sort_by") or v.get("y_field")
            meta.append(
                f"series_limit={v['series_limit']} by {series_sort} {v.get('series_sort_order') or 'desc'}"
            )
        if v.get("low_score_threshold") and v.get("y_field") == LOW_SCORE_RATIO:
            meta.append(f"low_score<= {v['low_score_threshold']}")
        if v.get("filters"):
            meta.append("local_filters=" + _format_filters(v["filters"]))
        if not v.get("inherit_global_filters", True):
            meta.append("independent")
        if v.get("freeze"):
            meta.append("frozen")
        meta.append(f"scope={_filter_scope(v)}")
        if v.get("chart_type") == "table":
            if v.get("table_columns"):
                meta.append(
                    "table_columns="
                    + json.dumps(v["table_columns"], ensure_ascii=False, default=str)
                )
            if v.get("data"):
                meta.append("data=" + json.dumps(v["data"], ensure_ascii=False, default=str))
        meta_str = f" | {'; '.join(meta)}" if meta else ""
        lines.append(f"- {v['id']} | {v['title']} | {v['chart_type']}{meta_str} | {stat_str or 'no_stats'}")

    return "\n".join(lines)


def get_all_view_data() -> list[dict]:
    """Return view id + data for all views (sent to frontend)."""
    result = []
    for v in views:
        payload = {"id": v["id"], "data": v["data"]}
        if v.get("chart_type") == "table":
            payload["table_columns"] = v.get("table_columns")
        result.append(payload)
    return result


def get_views_for_frontend() -> list[dict]:
    """Full view info for frontend rendering."""
    result = []
    for v in views:
        result.append({
            "id": v["id"],
            "label": v.get("label"),
            "chart_type": v["chart_type"],
            "title": v["title"],
            "x_field": v["x_field"],
            "y_field": v["y_field"],
            "color": v.get("color"),
            "limit": v.get("limit"),
            "sort_by": v.get("sort_by"),
            "sort_order": v.get("sort_order"),
            "series_limit": v.get("series_limit"),
            "series_sort_by": v.get("series_sort_by"),
            "series_sort_order": v.get("series_sort_order"),
            "table_columns": v.get("table_columns"),
            "low_score_threshold": v.get("low_score_threshold", low_score_threshold),
            "filters": v.get("filters", []),
            "inherit_global_filters": v.get("inherit_global_filters", True),
            "freeze": v.get("freeze", False),
            **_view_scope_payload(v),
            "data": v["data"],
            "highlighted": v["id"] == highlighted_view,
        })
    return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _filters_summary() -> str:
    return _format_filters(active_filters) or "none"


def _format_filters(filters: list[dict[str, Any]]) -> str:
    parts = []
    for f in filters:
        parts.append(f"{f['field']} {f['operator']} {f['value']}")
    return " AND ".join(parts)


def _coerce_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _coerce_limit(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    if limit < 1 or limit > MAX_VIEW_LIMIT:
        return None
    return limit


def _coerce_low_score_threshold(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        threshold = int(value)
    except (TypeError, ValueError):
        return None
    if threshold < 1 or threshold > 5:
        return None
    return threshold


def _infer_limit_from_text(*texts: Any) -> int | None:
    text = " ".join(str(t or "") for t in texts)
    if not text:
        return None

    patterns = [
        r"top\s*(\d{1,3})(?=\D|$)",
        r"top\s*([一二两三四五六七八九十百零〇]{1,5})",
        r"(?:前|保留|只保留|显示|展示)\s*(\d{1,3})\s*(?:个|项|名|类|类别|品类)?",
        r"(?:前|保留|只保留|显示|展示)\s*([一二两三四五六七八九十百零〇]{1,5})\s*(?:个|项|名|类|类别|品类)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        value = int(raw) if raw.isdigit() else _parse_chinese_int(raw)
        if value is not None and 1 <= value <= MAX_VIEW_LIMIT:
            return value
    return None


def _infer_state_limit_from_text(*texts: Any) -> int | None:
    text = " ".join(str(t or "") for t in texts)
    if not text:
        return None
    range_patterns = [
        r"([一二两三四五六七八九十百零〇\d]{1,5})\s*(?:到|至|-|~)\s*([一二两三四五六七八九十百零〇\d]{1,5})\s*个?州",
        r"州.*?([一二两三四五六七八九十百零〇\d]{1,5})\s*(?:到|至|-|~)\s*([一二两三四五六七八九十百零〇\d]{1,5})",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        hi_raw = match.group(2)
        hi = int(hi_raw) if hi_raw.isdigit() else _parse_chinese_int(hi_raw)
        if hi is not None and 1 <= hi <= MAX_VIEW_LIMIT:
            return hi

    patterns = [
        r"(?:显示|展示|列出|前|top)\s*([一二两三四五六七八九十百零〇\d]{1,5})\s*个?州",
        r"([一二两三四五六七八九十百零〇\d]{1,5})\s*个?州",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        value = int(raw) if raw.isdigit() else _parse_chinese_int(raw)
        if value is not None and 1 <= value <= MAX_VIEW_LIMIT:
            return value
    return None


def _infer_category_rank_limit_from_text(*texts: Any) -> int | None:
    text = " ".join(str(t or "") for t in texts)
    if not text:
        return None
    patterns = [
        r"前\s*([一二两三四五六七八九十百零〇\d]{1,5})\s*(?:名|个|项)?\s*(?:商品)?(?:类别|品类|种类)",
        r"(?:类别|品类|种类).*?前\s*([一二两三四五六七八九十百零〇\d]{1,5})",
        r"top\s*([一二两三四五六七八九十百零〇\d]{1,5}).*?(?:category|categories|品类|类别)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        value = int(raw) if raw.isdigit() else _parse_chinese_int(raw)
        if value is not None and 1 <= value <= MAX_VIEW_LIMIT:
            return value
    return None


def _parse_chinese_int(text: str) -> int | None:
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    text = text.strip()
    if not text:
        return None
    if text == "十":
        return 10
    if "百" in text:
        parts = text.split("百", 1)
        hundreds = digits.get(parts[0], 1 if parts[0] == "" else None)
        if hundreds is None:
            return None
        rest = _parse_chinese_int(parts[1]) if parts[1] else 0
        return hundreds * 100 + rest if rest is not None else None
    if "十" in text:
        parts = text.split("十", 1)
        tens = digits.get(parts[0], 1 if parts[0] == "" else None)
        ones = digits.get(parts[1], 0 if parts[1] == "" else None)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    if len(text) == 1:
        return digits.get(text)
    value = 0
    for ch in text:
        digit = digits.get(ch)
        if digit is None:
            return None
        value = value * 10 + digit
    return value


def _infer_sort_by_from_text(text: str) -> str | None:
    lowered = text.lower()
    if any(phrase in text for phrase in ("配送时间", "配送天数", "送货时间", "物流时间")):
        return "delivery_days"
    if any(phrase in text for phrase in ("延迟率", "延迟占比", "超时率", "迟到率")) or any(
        phrase in lowered for phrase in ("late ratio", "late rate")
    ):
        return LATE_RATIO
    if any(phrase in text for phrase in ("准时率", "准时占比", "按时率")) or any(
        phrase in lowered for phrase in ("on-time ratio", "on time ratio", "on-time rate")
    ):
        return ON_TIME_RATIO
    if any(phrase in text for phrase in ("低分占比", "低评分占比", "差评占比", "低分比例", "低评分比例")):
        return LOW_SCORE_RATIO
    if any(phrase in text for phrase in ("高评分占比", "高分占比", "好评占比", "高分比例")) or "high score ratio" in lowered:
        return HIGH_SCORE_RATIO
    if any(phrase in text for phrase in ("运费占比", "运费比例")) or any(
        phrase in lowered for phrase in ("freight ratio", "freight share")
    ):
        return AVG_FREIGHT_RATIO
    if any(phrase in text for phrase in ("评分", "评价", "星级")):
        return "review_score"
    if any(phrase in text for phrase in ("订单量", "订单数", "数量", "count")):
        return COUNT_MEASURE
    if any(phrase in text for phrase in ("营收", "收入", "销售额", "金额", "revenue")):
        return "revenue"
    return None


def _infer_sort_order_from_text(text: str, sort_by: str | None) -> str | None:
    lowered = text.lower()
    if any(phrase in text for phrase in ("最差", "最坏", "表现差")) or "worst" in lowered:
        return _bad_direction_for_metric(sort_by)
    if any(phrase in text for phrase in ("最好", "最佳", "表现好")) or "best" in lowered:
        return _good_direction_for_metric(sort_by)
    if any(phrase in text for phrase in ("从短到长", "从低到高", "从少到多", "升序", "最低", "最少", "最小")):
        return "asc"
    if any(phrase in text for phrase in ("从长到短", "从高到低", "从多到少", "降序", "最高", "最多", "最大")):
        return "desc"
    if "bottom" in lowered:
        return "asc"
    if "top" in lowered:
        return "desc"
    return None


def _infer_low_score_threshold_from_text(text: str) -> int | None:
    if not text:
        return None
    patterns = [
        r"(?:低分|低评分|差评).*?(?:小于等于|不高于|低于等于|<=|≤)\s*([1-5])",
        r"(?:小于等于|不高于|低于等于|<=|≤)\s*([1-5])\s*分?.*?(?:低分|低评分|差评)",
        r"(?:低分|低评分|差评).*?([一二三四五])\s*分?(?:及以下|以下含|以内)",
        r"([一二三四五])\s*分?(?:及以下|以下含|以内).*?(?:低分|低评分|差评)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1)
        value = int(raw) if raw.isdigit() else _parse_chinese_int(raw)
        if value is not None and 1 <= value <= 5:
            return value
    return None


def _wants_pie_chart(*texts: Any) -> bool:
    text = " ".join(str(t or "") for t in texts).lower()
    return any(
        phrase in text
        for phrase in (
            "pie",
            "pie chart",
            "饼图",
            "圓餅",
            "圆饼",
            "占比图",
            "构成图",
            "组成",
            "share",
            "proportion",
            "composition",
        )
    )


def _wants_delivery_speed_bucket(*texts: Any) -> bool:
    text = " ".join(str(t or "") for t in texts).lower()
    return any(
        phrase in text
        for phrase in (
            "配送速度",
            "配送快慢",
            "送货速度",
            "delivery speed",
            "delivery bucket",
            "delivery band",
        )
    )


def _wants_state_category_table(*texts: Any) -> bool:
    text = " ".join(str(t or "") for t in texts).lower()
    wants_table = any(
        phrase in text
        for phrase in ("table", "list", "detail", "表格", "列表", "明细", "标格")
    )
    wants_state = any(
        phrase in text
        for phrase in ("state", "states", "州", "地区")
    )
    wants_category = any(
        phrase in text
        for phrase in ("category", "categories", "品类", "类别", "商品类别", "商品种类")
    )
    return wants_table and wants_state and wants_category


def _normalize_filter(args: dict[str, Any], *, tool_name: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    field = args.get("field")
    if field not in FIELDS:
        return None, {
            "tool": tool_name,
            "success": False,
            "error": f"Unknown field: '{field}'. Available: {', '.join(FIELDS)}",
        }
    operator = args.get("operator", "eq")
    if operator not in OPERATORS:
        return None, {
            "tool": tool_name,
            "success": False,
            "error": f"Invalid operator: '{operator}'. Supported: {', '.join(OPERATORS)}",
        }

    value = _coerce_jsonish(args.get("value"))
    if operator == "in" and not isinstance(value, list):
        value = [value]
    if operator == "between" and (
        not isinstance(value, list) or len(value) != 2
    ):
        return None, {
            "tool": tool_name,
            "success": False,
            "error": "Operator 'between' requires value to be a two-item array.",
        }

    return {"field": field, "operator": operator, "value": value}, None


def _normalize_local_filters(value: Any, *, tool_name: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    value = _coerce_jsonish(value)
    if value in (None, ""):
        return [], None
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return [], {
            "tool": tool_name,
            "success": False,
            "error": "filters must be an array of filter objects.",
        }

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return [], {
                "tool": tool_name,
                "success": False,
                "error": "Each filters item must be an object with field, operator, and value.",
            }
        filter_def, error = _normalize_filter(item, tool_name=tool_name)
        if error:
            return [], error
        assert filter_def is not None
        normalized.append(filter_def)
    return normalized, None


def _effective_filters_for_view(view: dict[str, Any]) -> list[dict[str, Any]]:
    base = active_filters if view.get("inherit_global_filters", True) else []
    return [*base, *view.get("filters", [])]


def _filter_scope(view: dict[str, Any]) -> str:
    if view.get("freeze"):
        return "frozen_snapshot"
    has_local_filters = bool(view.get("filters"))
    follows_global = view.get("inherit_global_filters", True)
    if has_local_filters and follows_global:
        return "local_plus_global"
    if has_local_filters and not follows_global:
        return "fixed_condition"
    if not follows_global:
        return "independent"
    return "global"


def _view_scope_payload(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "filter_scope": _filter_scope(view),
        "effective_filters": _effective_filters_for_view(view),
        "snapshot_filters": view.get("snapshot_filters", []),
    }


def _default_sort_by(chart_type: str, x: str, y: str) -> str:
    if chart_type == "line" or x in TIME_FIELDS:
        return x
    return y


def _default_sort_order(chart_type: str, x: str, sort_by: str | None) -> str:
    if chart_type == "line" or sort_by == x or sort_by in TIME_FIELDS:
        return "asc"
    return "desc"


def _default_order_by(chart_type: str, x: str, measure: str) -> str:
    if chart_type == "line" or x in TIME_FIELDS:
        return x
    return f"{measure} DESC"


def _bad_direction_for_metric(metric: str | None) -> str:
    if metric == "review_score":
        return "asc"
    if metric in {"delivery_days", LOW_SCORE_RATIO, LATE_RATIO, AVG_FREIGHT_RATIO}:
        return "desc"
    if metric in {ON_TIME_RATIO, HIGH_SCORE_RATIO}:
        return "asc"
    if metric in {COUNT_MEASURE, "revenue"}:
        return "asc"
    return "desc"


def _good_direction_for_metric(metric: str | None) -> str:
    return "asc" if _bad_direction_for_metric(metric) == "desc" else "desc"


def _order_sql(order_col: str, sort_order: str | None) -> str:
    direction = "ASC" if sort_order == "asc" else "DESC"
    return f"{order_col} {direction}"


def _measure_expr(measure: str, table: str, threshold: int) -> tuple[str, str]:
    if measure in COUNTED_RATIO_MEASURES:
        return _counted_ratio_expr(measure, table, threshold), measure
    if measure == AVG_FREIGHT_RATIO:
        return "ROUND(AVG(freight_ratio), 4)", AVG_FREIGHT_RATIO
    if measure == "revenue":
        col = "item_revenue" if table == "fact_item" else "order_revenue"
        return f"ROUND(SUM({col}), 2)", "revenue"
    if measure == "order_item_revenue":
        col = "item_revenue" if table == "fact_item" else "order_item_revenue"
        return f"ROUND(SUM({col}), 2)", "order_item_revenue"
    if measure == "freight_total":
        col = "freight_value" if table == "fact_item" else "freight_total"
        return f"ROUND(SUM({col}), 2)", "freight_total"
    if measure in {"delivery_days", "estimated_delivery_days", "delivery_delay_days"}:
        return f"ROUND(AVG({measure}), 1)", measure
    if measure == "freight_ratio":
        return "ROUND(AVG(freight_ratio), 4)", "freight_ratio"
    if measure in {"review_score", "avg_item_price"}:
        return f"ROUND(AVG({measure}), 2)", measure
    if measure == COUNT_MEASURE:
        count_expr = "COUNT(DISTINCT order_id)" if table == "fact_item" else "COUNT(*)"
        return count_expr, COUNT_MEASURE
    if measure in NUMERIC_AVG_FIELDS or measure in {"order_dow", "order_hour"}:
        return f"ROUND(AVG({measure}), 2)", measure
    return "COUNT(*)", COUNT_MEASURE


def _attach_rank(data: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(data, start=1):
        row["rank"] = idx


def _low_score_ratio_expr(table: str, threshold: int) -> str:
    return _counted_ratio_expr(LOW_SCORE_RATIO, table, threshold)


def _low_score_count_exprs(table: str, threshold: int) -> tuple[str, str]:
    return _counted_ratio_count_exprs(LOW_SCORE_RATIO, table, threshold)


def _counted_ratio_expr(measure: str, table: str, threshold: int) -> str:
    numerator, denominator = _counted_ratio_count_exprs(measure, table, threshold)
    return f"ROUND(({numerator})::DOUBLE / NULLIF({denominator}, 0), 4)"


def _counted_ratio_count_exprs(measure: str, table: str, threshold: int) -> tuple[str, str]:
    condition = _counted_ratio_condition(measure, threshold)
    if table == "fact_item":
        numerator = f"COUNT(DISTINCT CASE WHEN {condition} THEN order_id END)"
        denominator = "COUNT(DISTINCT order_id)"
    else:
        numerator = f"SUM(CASE WHEN {condition} THEN 1 ELSE 0 END)"
        denominator = "COUNT(*)"
    return numerator, denominator


def _counted_ratio_condition(measure: str, threshold: int) -> str:
    if measure == LOW_SCORE_RATIO:
        return f"review_score <= {threshold}"
    if measure == LATE_RATIO:
        return "is_late = TRUE"
    if measure == ON_TIME_RATIO:
        return "delivery_status_bucket = 'on_time'"
    if measure == HIGH_SCORE_RATIO:
        return "is_high_score = TRUE"
    raise ValueError(f"Unknown ratio measure: {measure}")


def _ratio_count_alias(measure: str) -> str:
    return RATIO_COUNT_ALIASES[measure]


def _ratio_stat_alias(measure: str) -> str:
    return RATIO_STAT_ALIASES[measure]


def _low_score_ratio_data(
    group_field: str,
    filters: list[dict[str, Any]],
    order_by: str | None,
    extra_group_fields: list[str] | None,
    table: str,
    threshold: int | None = None,
) -> list[dict[str, Any]]:
    con = get_connection()
    where = build_where(filters, table=table)
    extra = extra_group_fields or []
    group_cols = [group_field, *extra]
    select_cols = ", ".join(group_cols)
    threshold = threshold or low_score_threshold
    if table == "fact_item":
        low_expr = f"COUNT(DISTINCT CASE WHEN review_score <= {threshold} THEN order_id END)"
        total_expr = "COUNT(DISTINCT order_id)"
    else:
        low_expr = f"SUM(CASE WHEN review_score <= {threshold} THEN 1 ELSE 0 END)"
        total_expr = "COUNT(*)"
    ratio_expr = f"ROUND(({low_expr})::DOUBLE / NULLIF({total_expr}, 0), 4)"
    sql = f"""
        SELECT
            {select_cols},
            {low_expr} AS low_score_count,
            {total_expr} AS order_count,
            {ratio_expr} AS {LOW_SCORE_RATIO}
        FROM {table}
        WHERE {where}
        GROUP BY {select_cols}
        ORDER BY {order_by or group_field}
    """
    cols = [*group_cols, "low_score_count", "order_count", LOW_SCORE_RATIO]
    rows = con.execute(sql).fetchall()
    return [dict(zip(cols, row)) for row in rows]


# ------------------------------------------------------------------
# Experiment logging
# ------------------------------------------------------------------

def log_tool_call(
    session_id: str,
    tool_name: str,
    params: dict,
    mode: str = "barge_in",
    response_id: str | None = None,
    call_id: str | None = None,
    result_success: bool | None = None,
    cancelled: bool = False,
    metrics: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool": tool_name,
        "params": params,
        "response_id": response_id,
        "call_id": call_id,
        "result_success": result_success,
        "cancelled": cancelled,
        "metrics": metrics or {},
        "dashboard_context_snapshot": rebuild_context(),
        "mode": mode,
    }
    # Per-session dir is the real target; the flat path is kept only as a
    # backward-compat fallback in case any caller forgets to pass log_dir.
    target_dir = log_dir or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / ("tool_calls.jsonl" if log_dir else f"{session_id}.jsonl")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
