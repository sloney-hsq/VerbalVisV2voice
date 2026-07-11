"""VerbalVis dashboard tools.

This module is the single source of truth for dashboard state and the eleven
model-facing tools used by FD-Voice. Metric semantics are explicit:

- low score: review_score <= 2
- product revenue: SUM(price), freight excluded
- category delivery metrics: one row per order and product category

Undo restores completed dashboard actions. This module does not implement
transactional rollback, stale-tool epochs, or cancellation of running tools.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from db import FIELDS, OPERATORS, build_where, get_connection, total_rows

log = logging.getLogger(__name__)

LOW_SCORE_THRESHOLD = 2
MAX_HISTORY = 20
MAX_ROWS = 100
MAX_INSPECT_ROWS = 80
MAX_SCATTER_ROWS = 1200
BASE_VIEW_COUNT = 4

DIMENSIONS = [
    "order_month",
    "order_week",
    "order_date",
    "customer_state",
    "product_category",
    "review_score",
]
TIME_DIMENSIONS = {"order_month", "order_week", "order_date"}
SERIES_FIELDS = ["customer_state", "product_category", "review_score"]
METRICS = [
    "order_count",
    "product_revenue",
    "low_score_ratio",
    "delivery_days",
    "late_ratio",
    "review_score",
]
CHART_TYPES = ["line", "bar", "scatter"]
SCATTER_FIELDS = ["review_score", "delivery_days"]
FILTER_FIELDS = list(dict.fromkeys([*FIELDS, "product_category"]))

active_filters: list[dict[str, Any]] = []
views: list[dict[str, Any]] = []
highlighted_views: list[str] = []
highlight_element: Any = None
dim_others: bool = True
view_counter = BASE_VIEW_COUNT
_history: list[dict[str, Any]] = []

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


FILTER_SCHEMA = {
    "type": "object",
    "properties": {
        "field": {"type": "string", "enum": FILTER_FIELDS},
        "operator": {"type": "string", "enum": sorted(OPERATORS)},
        "value": {
            "description": "Scalar value, list for in, or two-value list for between."
        },
    },
    "required": ["field", "operator", "value"],
}

TOOL_SCHEMAS = [
    _tool(
        "update_analysis_scope",
        "Replace, add, remove, or clear the shared global analysis filters.",
        {
            "operation": {
                "type": "string",
                "enum": ["replace", "add", "remove", "clear"],
            },
            "filters": {"type": "array", "items": FILTER_SCHEMA},
            "fields": {
                "type": "array",
                "items": {"type": "string", "enum": FILTER_FIELDS},
            },
        },
        ["operation"],
    ),
    _tool(
        "aggregate_data",
        "Compute grouped metrics from the current scope without creating a chart.",
        {
            "group_by": {
                "type": "array",
                "items": {"type": "string", "enum": DIMENSIONS},
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string", "enum": METRICS},
            },
            "filters": {"type": "array", "items": FILTER_SCHEMA},
            "sort_by": {
                "type": "string",
                "enum": [*DIMENSIONS, *METRICS],
            },
            "sort_order": {"type": "string", "enum": ["asc", "desc"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS},
        },
        ["metrics"],
    ),
    _tool(
        "compare_selected_groups",
        "Compare explicitly named states, categories, scores, or time values using common metrics.",
        {
            "dimension": {"type": "string", "enum": DIMENSIONS},
            "values": {"type": "array"},
            "metrics": {
                "type": "array",
                "items": {"type": "string", "enum": METRICS},
            },
            "time_grain": {
                "type": "string",
                "enum": ["none", "order_week", "order_month"],
            },
            "filters": {"type": "array", "items": FILTER_SCHEMA},
        },
        ["dimension", "values", "metrics"],
    ),
    _tool(
        "compare_category_metrics",
        "Create coordinated views for one common Top-N product-category set and return compact evidence.",
        {
            "mode": {
                "type": "string",
                "enum": ["weekly_trends", "category_summary"],
            },
            "top_n": {"type": "integer", "minimum": 1, "maximum": 30},
            "rank_by": {
                "type": "string",
                "enum": ["product_revenue", "order_count"],
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string", "enum": METRICS},
            },
            "focus_week": {"type": "string"},
            "title_prefix": {"type": "string"},
            "replace_previous": {"type": "boolean"},
        },
        ["mode", "top_n", "metrics"],
    ),
    _tool(
        "create_visual",
        "Create one line, bar, or scatter visualization from the current scope.",
        {
            "chart_type": {"type": "string", "enum": CHART_TYPES},
            "x": {
                "type": "string",
                "enum": list(dict.fromkeys([*DIMENSIONS, *SCATTER_FIELDS])),
            },
            "y": {"type": "string", "enum": METRICS},
            "series": {
                "type": "string",
                "enum": [*SERIES_FIELDS, "none"],
            },
            "title": {"type": "string"},
            "top_n": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS},
            "sort_by": {
                "type": "string",
                "enum": [*DIMENSIONS, *METRICS],
            },
            "sort_order": {"type": "string", "enum": ["asc", "desc"]},
            "filters": {"type": "array", "items": FILTER_SCHEMA},
        },
        ["chart_type", "x", "y", "title"],
    ),
    _tool(
        "update_visual",
        "Modify an existing visualization while preserving its view id.",
        {
            "view_id": {"type": "string"},
            "chart_type": {"type": "string", "enum": CHART_TYPES},
            "x": {
                "type": "string",
                "enum": list(dict.fromkeys([*DIMENSIONS, *SCATTER_FIELDS])),
            },
            "y": {"type": "string", "enum": METRICS},
            "series": {
                "type": "string",
                "enum": [*SERIES_FIELDS, "none"],
            },
            "title": {"type": "string"},
            "top_n": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS},
            "sort_by": {
                "type": "string",
                "enum": [*DIMENSIONS, *METRICS],
            },
            "sort_order": {"type": "string", "enum": ["asc", "desc"]},
            "filters": {"type": "array", "items": FILTER_SCHEMA},
        },
        ["view_id"],
    ),
    _tool(
        "delete_visual",
        "Delete one dashboard visualization.",
        {"view_id": {"type": "string"}},
        ["view_id"],
    ),
    _tool(
        "highlight_visual",
        "Focus one or more views and optionally highlight a real data value inside them.",
        {
            "action": {"type": "string", "enum": ["highlight", "clear"]},
            "view_ids": {"type": "array", "items": {"type": "string"}},
            "view_id": {"type": "string"},
            "highlight_element": {
                "description": "Exact value or field=value expression."
            },
            "dim_others": {"type": "boolean"},
        },
        ["action"],
    ),
    _tool(
        "inspect_visual",
        "Read one current view, optionally focusing on a series or x-axis values.",
        {
            "view_id": {"type": "string"},
            "series_value": {"description": "Optional exact series value."},
            "x_values": {"type": "array"},
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_INSPECT_ROWS,
            },
        },
        ["view_id"],
    ),
    _tool(
        "summarize_dashboard",
        "Return the current filters, views, encodings, highlights, and compact statistics.",
        {},
    ),
    _tool(
        "undo_last_action",
        "Undo the most recent completed dashboard-changing action.",
        {},
    ),
]


def init_views() -> None:
    global active_filters
    global views
    global highlighted_views
    global highlight_element
    global dim_others
    global view_counter
    global _history

    active_filters = []
    highlighted_views = []
    highlight_element = None
    dim_others = True
    view_counter = BASE_VIEW_COUNT
    _history = []
    views = [
        _make_view(
            "view1",
            "line",
            "Monthly Orders Trend",
            "order_month",
            "order_count",
            sort_by="order_month",
            sort_order="asc",
        ),
        _make_view(
            "view2",
            "bar",
            "Review Score Distribution",
            "review_score",
            "order_count",
            sort_by="review_score",
            sort_order="asc",
        ),
        _make_view(
            "view3",
            "bar",
            "Orders by State",
            "customer_state",
            "order_count",
            sort_by="order_count",
            sort_order="desc",
        ),
        _make_view(
            "view4",
            "bar",
            "Category Product Revenue (Top 15)",
            "product_category",
            "product_revenue",
            top_n=15,
            sort_by="product_revenue",
            sort_order="desc",
        ),
    ]
    _refresh_all_views()


def execute_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args = normalize_tool_arguments(name, arguments or {})
    handlers = {
        "update_analysis_scope": _exec_update_analysis_scope,
        "aggregate_data": _exec_aggregate_data,
        "compare_selected_groups": _exec_compare_selected_groups,
        "compare_category_metrics": _exec_compare_category_metrics,
        "create_visual": _exec_create_visual,
        "update_visual": _exec_update_visual,
        "delete_visual": _exec_delete_visual,
        "highlight_visual": _exec_highlight_visual,
        "inspect_visual": _exec_inspect_visual,
        "summarize_dashboard": _exec_summarize_dashboard,
        "undo_last_action": _exec_undo_last_action,
    }
    handler = handlers.get(name)
    if not handler:
        return _error(name, f"Unknown tool: {name}")
    try:
        return handler(args)
    except Exception as exc:
        log.exception("Tool %s failed", name)
        return _error(name, str(exc))


def normalize_tool_arguments(
    name: str,
    arguments: dict[str, Any],
    *,
    user_transcript: str = "",
) -> dict[str, Any]:
    """Perform structural normalization only; do not infer intent from keywords."""
    normalized = dict(arguments or {})
    if "filters" in normalized:
        normalized["filters"] = _coerce_filters(normalized.get("filters"))
    if name in {"update_visual", "delete_visual", "inspect_visual"}:
        if normalized.get("view_id"):
            normalized["view_id"] = _resolve_view_id(normalized["view_id"])
    if name == "highlight_visual":
        ids = normalized.get("view_ids") or []
        if not isinstance(ids, list):
            ids = [ids]
        if normalized.get("view_id"):
            ids = [normalized["view_id"], *ids]
        normalized["view_ids"] = [
            _resolve_view_id(value)
            for value in ids
            if value
        ]
    return normalized


def get_views_for_frontend() -> list[dict[str, Any]]:
    selected = set(highlighted_views)
    return [
        {
            **deepcopy(view),
            "highlighted": view.get("id") in selected,
        }
        for view in views
    ]


def realtime_state() -> dict[str, Any]:
    return {
        "filters": deepcopy(active_filters),
        "highlighted": list(highlighted_views),
        "highlight_element": deepcopy(highlight_element),
        "dim_others": dim_others,
        "low_score_threshold": LOW_SCORE_THRESHOLD,
        "views": [
            {
                "id": view["id"],
                "title": view["title"],
                "chart_type": view["chart_type"],
                "x": view["x_field"],
                "y": view["y_field"],
                "series": view.get("color"),
                "data_points": len(view.get("data") or []),
            }
            for view in views
        ],
        "undo_available": bool(_history),
    }


def get_dashboard_context() -> str:
    return json.dumps(realtime_state(), ensure_ascii=False, default=str)


def log_tool_call(
    session_id: str,
    tool_name: str,
    params: dict[str, Any],
    *,
    analysis_id: str | None = None,
    response_id: str | None = None,
    call_id: str | None = None,
    result_success: bool | None = None,
    metrics: dict[str, Any] | None = None,
    log_dir: Path | None = None,
    **_: Any,
) -> None:
    directory = Path(log_dir) if log_dir else LOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "tool_call",
        "session_id": session_id,
        "analysis_id": analysis_id,
        "response_id": response_id,
        "call_id": call_id,
        "tool": tool_name,
        "parameters": params,
        "success": result_success,
        "metrics": metrics or {},
    }
    with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _exec_update_analysis_scope(args: dict[str, Any]) -> dict[str, Any]:
    global active_filters

    operation = str(args.get("operation") or "replace").lower()
    if operation not in {"replace", "add", "remove", "clear"}:
        return _error(
            "update_analysis_scope",
            "operation must be replace, add, remove, or clear",
        )

    if operation in {"replace", "add"}:
        filters, error = _normalize_filters(args.get("filters") or [])
        if error:
            return _error("update_analysis_scope", error)
        if not filters:
            return _error("update_analysis_scope", "filters are required")
    else:
        filters = []

    _push_history("update_analysis_scope")
    if operation == "replace":
        active_filters = filters
    elif operation == "add":
        active_filters = _merge_filters(active_filters, filters)
    elif operation == "remove":
        fields = args.get("fields") or []
        if isinstance(fields, str):
            fields = [fields]
        field_set = {field for field in fields if field in FILTER_FIELDS}
        if not field_set:
            _history.pop()
            return _error(
                "update_analysis_scope",
                "fields are required for remove",
            )
        active_filters = [
            item
            for item in active_filters
            if item["field"] not in field_set
        ]
    else:
        active_filters = []

    _refresh_all_views()
    return _success(
        "update_analysis_scope",
        operation=operation,
        active_filters=deepcopy(active_filters),
        filtered_rows=total_rows(active_filters),
        low_score_definition=f"review_score <= {LOW_SCORE_THRESHOLD}",
    )


def _exec_aggregate_data(args: dict[str, Any]) -> dict[str, Any]:
    group_by = _valid_list(args.get("group_by") or [], DIMENSIONS)
    metrics = _valid_list(args.get("metrics") or [], METRICS)
    if not metrics:
        return _error("aggregate_data", "At least one metric is required")

    filters, error = _normalize_filters(args.get("filters") or [])
    if error:
        return _error("aggregate_data", error)

    rows = _aggregate(group_by, metrics, [*active_filters, *filters])
    rows = _sort_and_limit(
        rows,
        args.get("sort_by") or metrics[0],
        args.get("sort_order") or "desc",
        _limit(args.get("limit"), default=MAX_ROWS),
    )
    return _success(
        "aggregate_data",
        group_by=group_by,
        metrics=metrics,
        rows=rows,
        row_count=len(rows),
        active_filters=deepcopy(active_filters),
    )


def _exec_compare_selected_groups(args: dict[str, Any]) -> dict[str, Any]:
    dimension = args.get("dimension")
    values = args.get("values") or []
    metrics = _valid_list(args.get("metrics") or [], METRICS)
    if dimension not in DIMENSIONS:
        return _error(
            "compare_selected_groups",
            "Invalid comparison dimension",
        )
    if not isinstance(values, list) or not values:
        return _error(
            "compare_selected_groups",
            "values must be a non-empty array",
        )
    if not metrics:
        return _error(
            "compare_selected_groups",
            "At least one metric is required",
        )

    local_filters, error = _normalize_filters(args.get("filters") or [])
    if error:
        return _error("compare_selected_groups", error)

    comparison_filter = {
        "field": dimension,
        "operator": "in",
        "value": values,
    }
    time_grain = args.get("time_grain") or "none"
    group_by = [dimension]
    if time_grain in {"order_week", "order_month"}:
        if time_grain != dimension:
            group_by.insert(0, time_grain)

    rows = _aggregate(
        group_by,
        metrics,
        [*active_filters, *local_filters, comparison_filter],
    )
    rows = _sort_and_limit(rows, group_by[0], "asc", MAX_ROWS)
    return _success(
        "compare_selected_groups",
        dimension=dimension,
        values=values,
        time_grain=time_grain,
        metrics=metrics,
        rows=rows,
        row_count=len(rows),
    )


def _exec_compare_category_metrics(args: dict[str, Any]) -> dict[str, Any]:
    global views
    global view_counter

    mode = args.get("mode")
    if mode not in {"weekly_trends", "category_summary"}:
        return _error("compare_category_metrics", "Invalid mode")

    top_n = _limit(args.get("top_n"), default=0, maximum=30)
    if not top_n:
        return _error(
            "compare_category_metrics",
            "top_n must be between 1 and 30",
        )

    metrics = _valid_list(args.get("metrics") or [], METRICS)
    if not metrics:
        return _error(
            "compare_category_metrics",
            "At least one metric is required",
        )

    rank_by = args.get("rank_by") or "product_revenue"
    if rank_by not in {"product_revenue", "order_count"}:
        return _error(
            "compare_category_metrics",
            "rank_by must be product_revenue or order_count",
        )

    ranked = _rank_dimension(
        "product_category",
        rank_by,
        active_filters,
        top_n,
    )
    categories = [row["product_category"] for row in ranked]
    if not categories:
        return _error(
            "compare_category_metrics",
            "No categories exist in the current scope",
        )

    comparison_id = f"comparison-{uuid4().hex[:10]}"
    title_prefix = str(args.get("title_prefix") or "").strip()
    focus_week = str(args.get("focus_week") or "").strip() or None
    category_filter = {
        "field": "product_category",
        "operator": "in",
        "value": categories,
    }
    candidate_views: list[dict[str, Any]] = []
    next_counter = view_counter

    for metric in metrics:
        next_counter += 1
        if mode == "weekly_trends":
            chart_type = "line"
            x = "order_week"
            series = "product_category"
            title = (
                f"{title_prefix + ' ' if title_prefix else ''}"
                f"Weekly {_metric_label(metric)} · "
                f"Top {top_n} by {_metric_label(rank_by)}"
            )
            sort_by = "order_week"
            sort_order = "asc"
        else:
            chart_type = "bar"
            x = "product_category"
            series = None
            title = (
                f"{title_prefix + ' ' if title_prefix else ''}"
                f"{_metric_label(metric)} · "
                f"Top {top_n} by {_metric_label(rank_by)}"
            )
            sort_by = metric
            sort_order = "desc"

        view = _make_view(
            f"view{next_counter}",
            chart_type,
            title,
            x,
            metric,
            series=series,
            top_n=None if series else top_n,
            sort_by=sort_by,
            sort_order=sort_order,
            local_filters=[category_filter],
        )
        view.update(
            {
                "managed_comparison": True,
                "comparison_id": comparison_id,
                "comparison_config": {
                    "mode": mode,
                    "top_n": top_n,
                    "rank_by": rank_by,
                    "metrics": metrics,
                    "focus_week": focus_week,
                    "title_prefix": title_prefix,
                },
                "comparison_categories": categories,
            }
        )
        _refresh_view(view)
        candidate_views.append(view)

    _push_history("compare_category_metrics")
    if _as_bool(args.get("replace_previous", True)):
        views = [
            view
            for view in views
            if not view.get("managed_comparison")
        ]
    views.extend(candidate_views)
    view_counter = next_counter

    evidence = _comparison_evidence(
        candidate_views,
        ranked,
        metrics,
        mode,
        focus_week,
    )
    return _success(
        "compare_category_metrics",
        comparison_id=comparison_id,
        mode=mode,
        top_n=top_n,
        rank_by=rank_by,
        top_categories=ranked,
        metrics=metrics,
        focus_week=focus_week,
        view_ids=[view["id"] for view in candidate_views],
        evidence=evidence,
        active_filters=deepcopy(active_filters),
        revenue_definition="SUM(price), freight excluded",
        delivery_grain="one row per order and product category",
    )


def _exec_create_visual(args: dict[str, Any]) -> dict[str, Any]:
    global view_counter

    candidate, error = _build_visual_candidate(args)
    if error:
        return _error("create_visual", error)
    assert candidate is not None

    _push_history("create_visual")
    view_counter += 1
    candidate["id"] = f"view{view_counter}"
    candidate["label"] = f"view {view_counter}"
    views.append(candidate)
    return _success(
        "create_visual",
        view_id=candidate["id"],
        view=deepcopy(candidate),
        active_filters=deepcopy(active_filters),
    )


def _exec_update_visual(args: dict[str, Any]) -> dict[str, Any]:
    view_id = _resolve_view_id(args.get("view_id"))
    index = next(
        (
            position
            for position, view in enumerate(views)
            if view["id"] == view_id
        ),
        None,
    )
    if index is None:
        return _error("update_visual", f"Unknown view_id: {view_id}")

    current = views[index]
    candidate_args = {
        "chart_type": args.get("chart_type", current["chart_type"]),
        "x": args.get("x", current["x_field"]),
        "y": args.get("y", current["y_field"]),
        "series": args.get("series", current.get("color")),
        "title": args.get("title", current["title"]),
        "top_n": args.get("top_n", current.get("top_n")),
        "sort_by": args.get("sort_by", current.get("sort_by")),
        "sort_order": args.get(
            "sort_order",
            current.get("sort_order"),
        ),
        "filters": args.get(
            "filters",
            current.get("local_filters") or [],
        ),
    }
    candidate, error = _build_visual_candidate(candidate_args)
    if error:
        return _error("update_visual", error)
    assert candidate is not None

    candidate["id"] = current["id"]
    candidate["label"] = current.get("label") or current["id"]
    _push_history("update_visual")
    views[index] = candidate
    return _success(
        "update_visual",
        view_id=view_id,
        view=deepcopy(candidate),
    )


def _exec_delete_visual(args: dict[str, Any]) -> dict[str, Any]:
    global views
    global highlighted_views

    view_id = _resolve_view_id(args.get("view_id"))
    if not any(view["id"] == view_id for view in views):
        return _error("delete_visual", f"Unknown view_id: {view_id}")

    _push_history("delete_visual")
    views = [view for view in views if view["id"] != view_id]
    highlighted_views = [
        value
        for value in highlighted_views
        if value != view_id
    ]
    return _success(
        "delete_visual",
        view_id=view_id,
        remaining_view_ids=[view["id"] for view in views],
    )


def _exec_highlight_visual(args: dict[str, Any]) -> dict[str, Any]:
    global highlighted_views
    global highlight_element
    global dim_others

    action = args.get("action") or "clear"
    if action == "clear":
        _push_history("highlight_visual")
        highlighted_views = []
        highlight_element = None
        dim_others = True
        return _success(
            "highlight_visual",
            action="clear",
            view_ids=[],
        )
    if action != "highlight":
        return _error(
            "highlight_visual",
            "action must be highlight or clear",
        )

    ids = list(dict.fromkeys(args.get("view_ids") or []))
    available = {view["id"] for view in views}
    unknown = [view_id for view_id in ids if view_id not in available]
    if unknown:
        return _error(
            "highlight_visual",
            f"Unknown view_id: {unknown[0]}",
        )
    if not ids:
        return _error(
            "highlight_visual",
            "At least one view id is required",
        )

    _push_history("highlight_visual")
    highlighted_views = ids
    highlight_element = deepcopy(args.get("highlight_element"))
    dim_others = _as_bool(args.get("dim_others", True))
    return _success(
        "highlight_visual",
        action="highlight",
        view_id=ids[0],
        view_ids=ids,
        highlighted_views=ids,
        highlight_element=deepcopy(highlight_element),
        dim_others=dim_others,
    )


def _exec_inspect_visual(args: dict[str, Any]) -> dict[str, Any]:
    view_id = _resolve_view_id(args.get("view_id"))
    view = next(
        (item for item in views if item["id"] == view_id),
        None,
    )
    if not view:
        return _error("inspect_visual", f"Unknown view_id: {view_id}")

    rows = deepcopy(view.get("data") or [])
    series_value = args.get("series_value")
    if series_value is not None and view.get("color"):
        rows = [
            row
            for row in rows
            if _same(row.get(view["color"]), series_value)
        ]

    x_values = args.get("x_values") or []
    if x_values:
        rows = [
            row
            for row in rows
            if any(
                _same(row.get(view["x_field"]), value)
                for value in x_values
            )
        ]

    top_k = _limit(
        args.get("top_k"),
        default=MAX_INSPECT_ROWS,
        maximum=MAX_INSPECT_ROWS,
    )
    returned = rows[:top_k]
    return _success(
        "inspect_visual",
        view_id=view_id,
        title=view["title"],
        chart_type=view["chart_type"],
        x=view["x_field"],
        y=view["y_field"],
        series=view.get("color"),
        active_filters=deepcopy(active_filters),
        local_filters=deepcopy(view.get("local_filters") or []),
        statistics=deepcopy(view.get("statistics") or {}),
        data_point_count=len(rows),
        returned_data_points=len(returned),
        truncated=len(returned) < len(rows),
        data=returned,
    )


def _exec_summarize_dashboard(
    _: dict[str, Any],
) -> dict[str, Any]:
    return _success(
        "summarize_dashboard",
        active_filters=deepcopy(active_filters),
        filtered_rows=total_rows(active_filters),
        highlighted_views=list(highlighted_views),
        highlight_element=deepcopy(highlight_element),
        undo_available=bool(_history),
        views=[
            {
                "id": view["id"],
                "title": view["title"],
                "chart_type": view["chart_type"],
                "x": view["x_field"],
                "y": view["y_field"],
                "series": view.get("color"),
                "data_points": len(view.get("data") or []),
                "statistics": deepcopy(view.get("statistics") or {}),
            }
            for view in views
        ],
    )


def _exec_undo_last_action(
    _: dict[str, Any],
) -> dict[str, Any]:
    global active_filters
    global views
    global highlighted_views
    global highlight_element
    global dim_others
    global view_counter

    if not _history:
        return _error(
            "undo_last_action",
            "There is no completed dashboard action to undo",
        )

    snapshot = _history.pop()
    active_filters = snapshot["active_filters"]
    views = snapshot["views"]
    highlighted_views = snapshot["highlighted_views"]
    highlight_element = snapshot["highlight_element"]
    dim_others = snapshot["dim_others"]
    view_counter = snapshot["view_counter"]
    return _success(
        "undo_last_action",
        undone_action=snapshot["action"],
        active_filters=deepcopy(active_filters),
        view_ids=[view["id"] for view in views],
        highlighted_views=list(highlighted_views),
    )


def _build_visual_candidate(
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    chart_type = args.get("chart_type")
    x = args.get("x")
    y = args.get("y")
    series = args.get("series")
    if series == "none":
        series = None
    title = str(args.get("title") or "").strip()

    if chart_type not in CHART_TYPES:
        return None, "chart_type must be line, bar, or scatter"
    if y not in METRICS:
        return None, "Invalid y metric"
    if series is not None and series not in SERIES_FIELDS:
        return None, "Invalid series field"
    if not title:
        return None, "title is required"

    if chart_type == "scatter":
        if x not in SCATTER_FIELDS:
            return None, (
                "Scatter requires x from review_score or delivery_days"
            )
        if y not in SCATTER_FIELDS or x == y:
            return None, (
                "Scatter requires two different fields from "
                "review_score and delivery_days"
            )
    elif x not in DIMENSIONS:
        return None, (
            "Line and bar charts require a dimension on x"
        )

    filters, error = _normalize_filters(args.get("filters") or [])
    if error:
        return None, error

    view = _make_view(
        "pending",
        chart_type,
        title,
        x,
        y,
        series=series,
        top_n=_limit(args.get("top_n"), default=None),
        sort_by=args.get("sort_by")
        or (x if x in TIME_DIMENSIONS else y),
        sort_order=args.get("sort_order")
        or ("asc" if x in TIME_DIMENSIONS else "desc"),
        local_filters=filters,
    )
    _refresh_view(view)
    return view, None


def _make_view(
    view_id: str,
    chart_type: str,
    title: str,
    x: str,
    y: str,
    *,
    series: str | None = None,
    top_n: int | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    local_filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": view_id,
        "label": view_id.replace("view", "view "),
        "chart_type": chart_type,
        "title": title,
        "x_field": x,
        "y_field": y,
        "color": series,
        "top_n": top_n,
        "limit": top_n if not series else None,
        "sort_by": sort_by or y,
        "sort_order": sort_order,
        "local_filters": deepcopy(local_filters or []),
        "filters": deepcopy(local_filters or []),
        "inherit_global_filters": True,
        "source_table": (
            "fact_item"
            if "product_category" in {x, series}
            or y == "product_revenue"
            else "fact_order"
        ),
        "low_score_threshold": LOW_SCORE_THRESHOLD,
        "data": [],
        "statistics": {},
    }


def _refresh_all_views() -> None:
    comparison_groups: dict[str, list[dict[str, Any]]] = {}
    normal: list[dict[str, Any]] = []

    for view in views:
        comparison_id = view.get("comparison_id")
        if comparison_id:
            comparison_groups.setdefault(
                str(comparison_id),
                [],
            ).append(view)
        else:
            normal.append(view)

    for view in normal:
        _refresh_view(view)
    for group in comparison_groups.values():
        _refresh_comparison_group(group)


def _refresh_comparison_group(
    group: list[dict[str, Any]],
) -> None:
    if not group:
        return

    config = group[0].get("comparison_config") or {}
    ranked = _rank_dimension(
        "product_category",
        config.get("rank_by", "product_revenue"),
        active_filters,
        int(config.get("top_n") or 5),
    )
    categories = [row["product_category"] for row in ranked]

    for view in group:
        view["comparison_categories"] = categories
        view["local_filters"] = [
            {
                "field": "product_category",
                "operator": "in",
                "value": categories,
            }
        ]
        view["filters"] = deepcopy(view["local_filters"])
        _refresh_view(view)


def _refresh_view(view: dict[str, Any]) -> None:
    filters = [
        *active_filters,
        *(view.get("local_filters") or []),
    ]

    if view["chart_type"] == "scatter":
        view["data"] = _scatter_rows(
            view["x_field"],
            view["y_field"],
            view.get("color"),
            filters,
        )
    else:
        group_by = [view["x_field"]]
        if view.get("color"):
            if view["color"] not in group_by:
                group_by.append(view["color"])

        effective_filters = filters
        if view.get("color") and view.get("top_n"):
            ranked = _rank_dimension(
                view["color"],
                view.get("sort_by") or view["y_field"],
                filters,
                view["top_n"],
            )
            values = [row[view["color"]] for row in ranked]
            effective_filters = [
                *filters,
                {
                    "field": view["color"],
                    "operator": "in",
                    "value": values,
                },
            ]

        rows = _aggregate(
            group_by,
            [view["y_field"]],
            effective_filters,
        )
        if not view.get("color"):
            rows = _sort_and_limit(
                rows,
                view.get("sort_by"),
                view.get("sort_order", "desc"),
                view.get("top_n"),
            )
        else:
            rows = _sort_and_limit(
                rows,
                view["x_field"],
                "asc",
                None,
            )
        view["data"] = rows

    view["statistics"] = _view_statistics(view)


def _aggregate(
    group_by: list[str],
    metrics: list[str],
    filters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    if not group_by:
        merged[()] = {}

    for metric in metrics:
        rows = _metric_rows(metric, group_by, filters)
        for row in rows:
            key = tuple(row.get(field) for field in group_by)
            target = merged.setdefault(
                key,
                {
                    field: row.get(field)
                    for field in group_by
                },
            )
            for name, value in row.items():
                if name not in group_by:
                    target[name] = value

    return list(merged.values())


def _metric_rows(
    metric: str,
    group_by: list[str],
    filters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    connection = get_connection()
    group_sql = ", ".join(group_by)
    select_group = f"{group_sql}," if group_sql else ""
    group_clause = f"GROUP BY {group_sql}" if group_sql else ""

    if metric == "product_revenue":
        where = build_where(filters, table="fact_item")
        sql = f"""
            SELECT
                {select_group}
                ROUND(SUM(price), 2) AS product_revenue
            FROM fact_item
            WHERE {where}
            {group_clause}
        """
    elif "product_category" in group_by:
        where = build_where(filters, table="fact_item")
        grain_fields = list(
            dict.fromkeys(
                [
                    "order_id",
                    *group_by,
                    "review_score",
                    "delivery_days",
                    "is_late",
                ]
            )
        )
        expression = _metric_expression(metric)
        sql = f"""
            WITH order_category AS (
                SELECT DISTINCT {', '.join(grain_fields)}
                FROM fact_item
                WHERE {where}
            )
            SELECT
                {select_group}
                {expression}
            FROM order_category
            {group_clause}
        """
    else:
        where = build_where(filters, table="fact_order")
        expression = _metric_expression(metric)
        sql = f"""
            SELECT
                {select_group}
                {expression}
            FROM fact_order
            WHERE {where}
            {group_clause}
        """

    result = connection.execute(sql)
    columns = [item[0] for item in result.description]
    return [
        dict(zip(columns, row))
        for row in result.fetchall()
    ]


def _metric_expression(metric: str) -> str:
    expressions = {
        "order_count": (
            "COUNT(DISTINCT order_id) AS order_count"
        ),
        "low_score_ratio": (
            f"ROUND("
            f"COUNT(DISTINCT order_id) FILTER "
            f"(WHERE review_score <= {LOW_SCORE_THRESHOLD})::DOUBLE "
            f"/ NULLIF("
            f"COUNT(DISTINCT order_id) FILTER "
            f"(WHERE review_score IS NOT NULL), 0), 4) "
            f"AS low_score_ratio"
        ),
        "delivery_days": (
            "ROUND(AVG(delivery_days), 2) AS delivery_days"
        ),
        "late_ratio": (
            "ROUND("
            "COUNT(DISTINCT order_id) FILTER "
            "(WHERE is_late = TRUE)::DOUBLE "
            "/ NULLIF("
            "COUNT(DISTINCT order_id) FILTER "
            "(WHERE is_late IS NOT NULL), 0), 4) "
            "AS late_ratio"
        ),
        "review_score": (
            "ROUND(AVG(review_score), 2) AS review_score"
        ),
    }
    if metric not in expressions:
        raise ValueError(f"Unsupported metric: {metric}")
    return expressions[metric]


def _scatter_rows(
    x: str,
    y: str,
    series: str | None,
    filters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    use_items = series == "product_category"
    table = "fact_item" if use_items else "fact_order"
    where = build_where(filters, table=table)
    fields = ["order_id", x, y]
    if series and series not in fields:
        fields.append(series)
    distinct = "DISTINCT" if use_items else ""

    result = get_connection().execute(
        f"""
        SELECT {distinct} {', '.join(fields)}
        FROM {table}
        WHERE {where}
          AND {x} IS NOT NULL
          AND {y} IS NOT NULL
        LIMIT {MAX_SCATTER_ROWS}
        """
    )
    columns = [item[0] for item in result.description]
    return [
        dict(zip(columns, row))
        for row in result.fetchall()
    ]


def _rank_dimension(
    dimension: str,
    metric: str,
    filters: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    rows = _aggregate([dimension], [metric], filters)
    rows = _sort_and_limit(rows, metric, "desc", top_n)
    return [
        {"rank": index + 1, **row}
        for index, row in enumerate(rows)
    ]


def _comparison_evidence(
    candidate_views: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    metrics: list[str],
    mode: str,
    focus_week: str | None,
) -> list[dict[str, Any]]:
    evidence = {
        row["product_category"]: {
            "rank": row["rank"],
            "product_category": row["product_category"],
            "rank_value": row.get(
                "product_revenue",
                row.get("order_count"),
            ),
        }
        for row in ranked
    }

    for metric, view in zip(metrics, candidate_views):
        if mode == "category_summary":
            for row in view["data"]:
                category = row.get("product_category")
                if category in evidence:
                    evidence[category][metric] = row.get(metric)
            continue

        for category in evidence:
            points = [
                (
                    str(row.get("order_week")),
                    _number(row.get(metric)),
                )
                for row in view["data"]
                if row.get("product_category") == category
                and _number(row.get(metric)) is not None
            ]
            points = [
                (week, value)
                for week, value in points
                if value is not None
            ]
            points.sort(key=lambda item: (-item[1], item[0]))
            focus_value = next(
                (
                    value
                    for week, value in points
                    if focus_week and week == focus_week
                ),
                None,
            )
            evidence[category].setdefault("metrics", {})[metric] = {
                "peak_week": points[0][0] if points else None,
                "peak_value": points[0][1] if points else None,
                "focus_week": focus_week,
                "focus_value": focus_value,
                "top_weeks": [
                    {"week": week, "value": value}
                    for week, value in points[:3]
                ],
            }

    return sorted(
        evidence.values(),
        key=lambda row: row["rank"],
    )


def _push_history(action: str) -> None:
    _history.append(
        {
            "action": action,
            "active_filters": deepcopy(active_filters),
            "views": deepcopy(views),
            "highlighted_views": list(highlighted_views),
            "highlight_element": deepcopy(highlight_element),
            "dim_others": dim_others,
            "view_counter": view_counter,
        }
    )
    if len(_history) > MAX_HISTORY:
        del _history[0]


def _normalize_filters(
    raw_filters: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    normalized = []
    for raw in raw_filters:
        if not isinstance(raw, dict):
            return [], "Each filter must be an object"
        field = raw.get("field")
        operator = raw.get("operator")
        value = _coerce_json(raw.get("value"))
        if field not in FILTER_FIELDS:
            return [], f"Unknown filter field: {field}"
        if operator not in OPERATORS:
            return [], f"Unknown operator: {operator}"
        if operator == "between":
            if not isinstance(value, list) or len(value) != 2:
                return [], "between requires a two-value array"
        if operator == "in" and not isinstance(value, list):
            return [], "in requires an array"
        normalized.append(
            {
                "field": field,
                "operator": operator,
                "value": value,
            }
        )
    return normalized, None


def _coerce_filters(value: Any) -> list[Any]:
    value = _coerce_json(value)
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def _coerce_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return text
    if text[0] in "[{\"" or text in {"true", "false", "null"}:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _merge_filters(
    existing: list[dict[str, Any]],
    additions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    replaced_fields = {item["field"] for item in additions}
    return [
        item
        for item in existing
        if item["field"] not in replaced_fields
    ] + additions


def _resolve_view_id(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    if text.startswith("view") and text[4:].isdigit():
        return f"view{int(text[4:])}"
    if text.isdigit():
        return f"view{int(text)}"
    return str(value or "").strip()


def _valid_list(value: Any, allowed: list[str]) -> list[str]:
    source = value if isinstance(value, list) else [value]
    return list(
        dict.fromkeys(
            item
            for item in source
            if item in allowed
        )
    )


def _limit(
    value: Any,
    *,
    default: int | None,
    maximum: int = MAX_ROWS,
) -> int | None:
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if 1 <= number <= maximum else default


def _sort_and_limit(
    rows: list[dict[str, Any]],
    field: str | None,
    order: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    if field:
        present = [
            row
            for row in rows
            if row.get(field) is not None
        ]
        missing = [
            row
            for row in rows
            if row.get(field) is None
        ]
        present.sort(
            key=lambda row: _sortable(row.get(field)),
            reverse=order != "asc",
        )
        rows = [*present, *missing]
    return rows[:limit] if limit else rows


def _sortable(value: Any) -> Any:
    number = _number(value)
    return number if number is not None else str(value or "")


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _same(left: Any, right: Any) -> bool:
    return str(left).strip().lower() == str(right).strip().lower()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _view_statistics(view: dict[str, Any]) -> dict[str, Any]:
    data = view.get("data") or []
    metric = view.get("y_field")
    values = [_number(row.get(metric)) for row in data]
    values = [value for value in values if value is not None]
    return {
        "data_points": len(data),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": (
            round(sum(values) / len(values), 4)
            if values
            else None
        ),
    }


def _metric_label(metric: str) -> str:
    return {
        "order_count": "Order count",
        "product_revenue": "Product revenue",
        "low_score_ratio": "Low-score ratio",
        "delivery_days": "Delivery days",
        "late_ratio": "Late ratio",
        "review_score": "Review score",
    }.get(metric, metric)


def _success(tool: str, **payload: Any) -> dict[str, Any]:
    return {
        "tool": tool,
        "success": True,
        "payload": payload,
    }


def _error(tool: str, message: str) -> dict[str, Any]:
    return {
        "tool": tool,
        "success": False,
        "payload": None,
        "error": message,
    }
