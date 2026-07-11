"""Model-facing analytical tools for VerbalVis.

This module deliberately keeps the realtime model's tool surface small while
reusing the existing dashboard engine internally. It also owns the two metric
semantics that matter most for the study demos:

* category revenue means product revenue: ``SUM(price)`` (freight excluded);
* category delivery metrics are computed at one row per order and category,
  rather than weighting an order once per item row.

The runtime remains non-preemptive once a tool batch starts. This module does
not add stale-result invalidation, epochs, rollback, or transactions.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable
from uuid import uuid4

import realtime as base_realtime
import tools
from db import FIELDS, OPERATORS, build_where, get_connection, total_rows

SCOPE_TOOL = "update_analysis_scope"
LEGACY_SCOPE_TOOL = "set_analysis_scope"
CREATE_VISUAL_TOOL = "create_visual"
COMPARISON_TOOL = "compare_category_metrics"

MODEL_WRAPPER_TOOL_NAMES = {
    SCOPE_TOOL,
    LEGACY_SCOPE_TOOL,
    CREATE_VISUAL_TOOL,
    COMPARISON_TOOL,
}

# These primitive schemas remain available inside Python, but are hidden from
# Qwen to avoid overlapping choices and an inconsistent low-score definition.
HIDDEN_MODEL_TOOL_NAMES = {
    "filter_data",
    "remove_filter",
    "append_visual",
    "set_low_score_threshold",
    LEGACY_SCOPE_TOOL,
}

COMPARISON_METRICS = [
    "order_count",
    "product_revenue",
    "revenue",  # accepted alias; returned field remains revenue for frontend compatibility
    "low_score_ratio",
    "delivery_days",
    "late_ratio",
]

FIXED_LOW_SCORE_THRESHOLD = 2
ORDER_GRAIN_METRICS = {
    "order_count",
    "low_score_ratio",
    "delivery_days",
    "late_ratio",
}

_FILTER_SCHEMA = {
    "type": "object",
    "properties": {
        "field": {"type": "string", "enum": FIELDS},
        "operator": {"type": "string", "enum": sorted(OPERATORS)},
        "value": {
            "description": (
                "Scalar value, an array for 'in', or a two-value array for 'between'."
            )
        },
    },
    "required": ["field", "operator", "value"],
}

MODEL_TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": SCOPE_TOOL,
        "description": (
            "Update the shared analysis scope in one operation. Use replace or add "
            "for filters, remove to remove filters by field, and clear to reset the scope."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["replace", "add", "remove", "clear"],
                    "description": "How to change the current global scope.",
                },
                "filters": {
                    "type": "array",
                    "items": _FILTER_SCHEMA,
                    "description": "Filters used by replace/add; field names may also be used by remove.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": FIELDS},
                    "description": "Fields whose filters should be removed when operation=remove.",
                },
            },
            "required": ["operation"],
        },
    },
    {
        "type": "function",
        "name": CREATE_VISUAL_TOOL,
        "description": (
            "Create one visualization from the current scope. Use compare_category_metrics "
            "instead when several metrics must share one common Top-N category set."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "scatter", "histogram", "pie"],
                },
                "x": {"type": "string", "enum": FIELDS},
                "y": {"type": "string", "enum": tools.APPEND_Y_FIELDS},
                "series": {
                    "type": ["string", "null"],
                    "enum": sorted(tools.ALLOWED_COLOR_FIELDS) + [None],
                    "description": "Optional series/color field.",
                },
                "title": {"type": "string"},
                "top_n": {
                    "type": ["integer", "null"],
                    "description": "Top-N rows, or Top-N series for a multi-series line chart.",
                },
                "sort_by": {
                    "type": ["string", "null"],
                    "enum": tools.SORT_FIELDS + [None],
                },
                "sort_order": {
                    "type": ["string", "null"],
                    "enum": ["asc", "desc", None],
                },
                "filters": {
                    "type": ["array", "null"],
                    "items": _FILTER_SCHEMA,
                    "description": "Optional filters local to this new view.",
                },
                "inherit_global_filters": {"type": "boolean"},
                "freeze": {"type": "boolean"},
                "include_overall": {"type": "boolean"},
            },
            "required": ["chart_type", "x", "y", "title"],
        },
    },
    {
        "type": "function",
        "name": COMPARISON_TOOL,
        "description": (
            "Create coordinated views for the same Top-N product categories. Revenue ranking "
            "uses product price only, excluding freight. Delivery metrics count each order once "
            "per category. The tool returns compact evidence as well as the views."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["weekly_trends", "category_summary"],
                },
                "top_n": {"type": "integer"},
                "rank_by": {
                    "type": "string",
                    "enum": ["product_revenue", "revenue", "order_count"],
                    "description": "Metric used to select the common category set.",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "enum": COMPARISON_METRICS},
                },
                "focus_week": {
                    "type": ["string", "null"],
                    "description": "Optional ISO week such as 2017-W48.",
                },
                "title_prefix": {"type": ["string", "null"]},
                "replace_previous": {
                    "type": "boolean",
                    "description": "Replace earlier coordinated comparison views. Default true.",
                },
            },
            "required": ["mode", "top_n", "metrics"],
        },
    },
]


def register_demo_tool_schemas() -> None:
    """Expose one unambiguous model-facing tool set and fix base metric semantics."""
    _configure_fixed_semantics()

    retained = []
    for schema in base_realtime.TOOL_SCHEMAS:
        name = _schema_name(schema)
        if name in HIDDEN_MODEL_TOOL_NAMES or name in {
            SCOPE_TOOL,
            CREATE_VISUAL_TOOL,
            COMPARISON_TOOL,
        }:
            continue
        retained.append(schema)

    base_realtime.TOOL_SCHEMAS[:] = [*retained, *deepcopy(MODEL_TOOL_SCHEMAS)]


def is_demo_tool(name: str) -> bool:
    return name in MODEL_WRAPPER_TOOL_NAMES


def execute_demo_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == SCOPE_TOOL:
        return _exec_update_analysis_scope(arguments)
    if name == LEGACY_SCOPE_TOOL:
        legacy = dict(arguments or {})
        legacy["operation"] = "add" if legacy.pop("mode", "replace") == "append" else "replace"
        return _exec_update_analysis_scope(legacy, result_tool=LEGACY_SCOPE_TOOL)
    if name == CREATE_VISUAL_TOOL:
        return _exec_create_visual(arguments)
    if name == COMPARISON_TOOL:
        return _exec_compare_category_metrics(arguments)
    return {
        "tool": name,
        "success": False,
        "error": f"Unknown model-facing tool: {name}",
    }


# ---------------------------------------------------------------------------
# Tool registration and fixed study semantics
# ---------------------------------------------------------------------------


def _schema_name(schema: dict[str, Any]) -> str:
    if not isinstance(schema, dict):
        return ""
    function = schema.get("function")
    if isinstance(function, dict):
        return str(function.get("name") or "")
    return str(schema.get("name") or "")


def _configure_fixed_semantics() -> None:
    """Keep the study definition stable and make the base revenue view truthful."""
    tools.low_score_threshold = FIXED_LOW_SCORE_THRESHOLD

    for collection in (tools.BASE_VIEWS_DEFS, tools.views):
        for view in collection:
            if view.get("id") != "view4":
                continue
            view["title"] = "Category Product Revenue (Top 15)"
            view["agg_expr"] = "ROUND(SUM(price), 2)"
            view["agg_alias"] = "revenue"
            view["revenue_definition"] = "product_price_excluding_freight"

    if tools.views:
        tools._refresh_all_views()
        _refresh_managed_comparisons()


# ---------------------------------------------------------------------------
# Scope management
# ---------------------------------------------------------------------------


def _exec_update_analysis_scope(
    arguments: dict[str, Any],
    *,
    result_tool: str = SCOPE_TOOL,
) -> dict[str, Any]:
    operation = str(arguments.get("operation") or "replace").strip().lower()
    if operation not in {"replace", "add", "remove", "clear"}:
        return _error(result_tool, "operation must be replace, add, remove, or clear.")

    raw_filters = arguments.get("filters") or []
    if isinstance(raw_filters, dict):
        raw_filters = [raw_filters]
    if not isinstance(raw_filters, list):
        return _error(result_tool, "filters must be an array of filter objects.")

    normalized_filters: list[dict[str, Any]] = []
    if operation in {"replace", "add"}:
        if not raw_filters:
            return _error(result_tool, f"filters are required for operation={operation}.")
        normalized_filters, error = _normalize_filters(raw_filters, result_tool)
        if error:
            return error

    if operation == "replace":
        next_filters = normalized_filters
    elif operation == "add":
        next_filters = _dedupe_filters([*tools.active_filters, *normalized_filters])
    elif operation == "remove":
        fields = arguments.get("fields") or []
        if isinstance(fields, str):
            fields = [fields]
        fields = [str(field) for field in fields if str(field) in FIELDS]
        fields.extend(
            str(item.get("field"))
            for item in raw_filters
            if isinstance(item, dict) and item.get("field") in FIELDS
        )
        fields = list(dict.fromkeys(fields))
        if not fields:
            return _error(result_tool, "fields or filters are required for operation=remove.")
        field_set = set(fields)
        next_filters = [
            item for item in tools.active_filters
            if item.get("field") not in field_set
        ]
    else:
        next_filters = []

    tools.active_filters = _dedupe_filters(next_filters)
    tools._refresh_all_views()
    _refresh_managed_comparisons()

    rows = total_rows(tools.active_filters)
    result: dict[str, Any] = {
        "tool": result_tool,
        "success": True,
        "payload": {
            "operation": operation,
            "active_filters": deepcopy(tools.active_filters),
            "filtered_rows": rows,
            "low_score_definition": f"review_score <= {FIXED_LOW_SCORE_THRESHOLD}",
        },
    }
    if rows == 0:
        result["warning"] = "The requested scope contains 0 orders."
    return result


def _normalize_filters(
    raw_filters: Iterable[dict[str, Any]],
    tool_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    normalized_filters: list[dict[str, Any]] = []
    for raw_filter in raw_filters:
        if not isinstance(raw_filter, dict):
            return [], _error(tool_name, "Each filter must be an object.")
        normalized, error = tools._normalize_filter(raw_filter, tool_name=tool_name)
        if error:
            return [], _error(tool_name, error.get("error") or "Invalid filter.")
        assert normalized is not None
        normalized_filters.append(normalized)
    return normalized_filters, None


# ---------------------------------------------------------------------------
# Single-view creation wrapper
# ---------------------------------------------------------------------------


def _exec_create_visual(arguments: dict[str, Any]) -> dict[str, Any]:
    chart_type = str(arguments.get("chart_type") or "").strip()
    series = arguments.get("series")
    top_n = arguments.get("top_n")

    append_args: dict[str, Any] = {
        "chart_type": chart_type,
        "x": arguments.get("x"),
        "y": "revenue" if arguments.get("y") == "product_revenue" else arguments.get("y"),
        "color": series,
        "title": arguments.get("title"),
        "sort_by": (
            "revenue" if arguments.get("sort_by") == "product_revenue"
            else arguments.get("sort_by")
        ),
        "sort_order": arguments.get("sort_order"),
        "filters": arguments.get("filters"),
        "inherit_global_filters": arguments.get("inherit_global_filters", True),
        "freeze": arguments.get("freeze", False),
        "include_overall": arguments.get("include_overall", False),
    }

    if top_n not in (None, ""):
        if chart_type == "line" and series:
            append_args["series_limit"] = top_n
            append_args["series_sort_by"] = append_args.get("sort_by") or append_args["y"]
            append_args["series_sort_order"] = append_args.get("sort_order") or "desc"
        else:
            append_args["limit"] = top_n

    result = tools.execute_tool("append_visual", append_args)
    result = deepcopy(result)
    result["tool"] = CREATE_VISUAL_TOOL
    if not result.get("success"):
        return result

    view_id = (result.get("payload") or {}).get("view_id")
    view = next((item for item in tools.views if item.get("id") == view_id), None)
    if view is not None:
        view["created_by"] = CREATE_VISUAL_TOOL
        if view.get("y_field") == "revenue" and view.get("source_table") == "fact_item":
            view["agg_expr"] = "ROUND(SUM(price), 2)"
            view["revenue_definition"] = "product_price_excluding_freight"
            _refresh_one_view(view)
            _replace_result_view_payload(result, view)
        elif _needs_order_category_grain(view):
            view["order_grain_definition"] = "one_row_per_order_and_category"
            _refresh_one_view(view)
            _replace_result_view_payload(result, view)

    return result


def _replace_result_view_payload(result: dict[str, Any], view: dict[str, Any]) -> None:
    payload = result.setdefault("payload", {})
    payload["data"] = deepcopy(view.get("data") or [])
    payload["statistics"] = deepcopy(view.get("statistics") or {})
    if view.get("revenue_definition"):
        payload["revenue_definition"] = view["revenue_definition"]
    if view.get("order_grain_definition"):
        payload["order_grain_definition"] = view["order_grain_definition"]


# ---------------------------------------------------------------------------
# Coordinated category comparison
# ---------------------------------------------------------------------------


def _exec_compare_category_metrics(arguments: dict[str, Any]) -> dict[str, Any]:
    mode = str(arguments.get("mode") or "").strip()
    if mode not in {"weekly_trends", "category_summary"}:
        return _error(COMPARISON_TOOL, "mode must be weekly_trends or category_summary.")

    try:
        top_n = int(arguments.get("top_n"))
    except (TypeError, ValueError):
        top_n = 0
    if top_n < 1 or top_n > 30:
        return _error(COMPARISON_TOOL, "top_n must be an integer from 1 to 30.")

    rank_by = _canonical_metric(arguments.get("rank_by") or "product_revenue")
    if rank_by not in {"revenue", "order_count"}:
        return _error(COMPARISON_TOOL, "rank_by must be product_revenue/revenue or order_count.")

    raw_metrics = arguments.get("metrics") or []
    if not isinstance(raw_metrics, list):
        raw_metrics = [raw_metrics]
    metrics = list(dict.fromkeys(
        _canonical_metric(metric)
        for metric in raw_metrics
        if _canonical_metric(metric) in {
            "order_count", "revenue", "low_score_ratio", "delivery_days", "late_ratio"
        }
    ))
    if not metrics:
        metrics = (
            ["order_count", "low_score_ratio", "delivery_days", "late_ratio"]
            if mode == "weekly_trends"
            else ["low_score_ratio", "delivery_days", "revenue", "order_count"]
        )

    focus_week = str(arguments.get("focus_week") or "").strip() or None
    title_prefix = str(arguments.get("title_prefix") or "").strip()
    replace_previous = _as_bool(arguments.get("replace_previous", True), default=True)

    top_categories = _top_categories(top_n, rank_by)
    if not top_categories:
        return _error(COMPARISON_TOOL, "No product categories exist in the current scope.")

    comparison_id = f"comparison-{uuid4().hex[:10]}"
    config = {
        "mode": mode,
        "top_n": top_n,
        "rank_by": rank_by,
        "metrics": metrics,
        "focus_week": focus_week,
        "title_prefix": title_prefix,
    }

    # Prepare every query and view first. No dashboard state changes until the
    # complete coordinated group is valid.
    candidate_views: list[dict[str, Any]] = []
    next_counter = tools.view_counter
    try:
        for metric in metrics:
            next_counter += 1
            view = _build_comparison_view(
                view_id=f"view{next_counter}",
                comparison_id=comparison_id,
                config=config,
                metric=metric,
                top_categories=top_categories,
            )
            candidate_views.append(view)
    except Exception as exc:
        return _error(COMPARISON_TOOL, f"Unable to prepare coordinated comparison: {exc}")

    if replace_previous:
        removed_ids = {
            view.get("id") for view in tools.views
            if view.get("managed_comparison")
        }
        tools.views = [
            view for view in tools.views
            if not view.get("managed_comparison")
        ]
        tools.highlighted_views = [
            view_id for view_id in tools.highlighted_views
            if view_id not in removed_ids
        ]

    tools.views.extend(candidate_views)
    tools.view_counter = next_counter

    evidence = _comparison_evidence(
        candidate_views,
        top_categories,
        metrics,
        mode,
        focus_week,
    )
    return {
        "tool": COMPARISON_TOOL,
        "success": True,
        "payload": {
            "comparison_id": comparison_id,
            "mode": mode,
            "rank_by": "product_revenue" if rank_by == "revenue" else rank_by,
            "top_n": top_n,
            "top_categories": top_categories,
            "metrics": ["product_revenue" if metric == "revenue" else metric for metric in metrics],
            "focus_week": focus_week,
            "view_ids": [view["id"] for view in candidate_views],
            "evidence": evidence,
            "active_filters": deepcopy(tools.active_filters),
            "filtered_rows": total_rows(tools.active_filters),
            "revenue_definition": "SUM(price), freight excluded",
            "delivery_grain": "one row per order and product category",
        },
    }


def _build_comparison_view(
    *,
    view_id: str,
    comparison_id: str,
    config: dict[str, Any],
    metric: str,
    top_categories: list[dict[str, Any]],
) -> dict[str, Any]:
    mode = config["mode"]
    top_n = config["top_n"]
    rank_by = config["rank_by"]
    title_prefix = config["title_prefix"]
    prefix = f"{title_prefix} " if title_prefix else ""
    rank_label = "Product revenue" if rank_by == "revenue" else "Order count"
    metric_label = {
        "order_count": "Order count",
        "revenue": "Product revenue",
        "low_score_ratio": "Low-score ratio",
        "delivery_days": "Average delivery time",
        "late_ratio": "Late-order ratio",
    }[metric]

    categories = [item["product_category"] for item in top_categories]
    data = _comparison_rows(mode, metric, categories)
    category_filter = {
        "field": "product_category",
        "operator": "in",
        "value": categories,
    }

    if mode == "weekly_trends":
        title = f"{prefix}Weekly {metric_label} · {rank_label} Top {top_n}"
        chart_type = "line"
        x_field = "order_week"
        color = "product_category"
        limit = None
        series_limit = top_n
        sort_by = "order_week"
        sort_order = "asc"
    else:
        title = f"{prefix}{metric_label} · {rank_label} Top {top_n}"
        chart_type = "bar"
        x_field = "product_category"
        color = None
        limit = top_n
        series_limit = None
        sort_by = metric
        sort_order = "desc"

    view: dict[str, Any] = {
        "id": view_id,
        "label": tools._view_label(view_id),
        "chart_type": chart_type,
        "title": title,
        "x_field": x_field,
        "y_field": metric,
        "color": color,
        "group_field": x_field,
        "agg_expr": _metric_description(metric),
        "agg_alias": metric,
        "order_by": x_field if mode == "weekly_trends" else f"{metric} DESC",
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "series_limit": series_limit,
        "series_sort_by": rank_by,
        "series_sort_order": "desc",
        "include_overall": False,
        "low_score_threshold": FIXED_LOW_SCORE_THRESHOLD,
        "filters": [category_filter],
        "inherit_global_filters": True,
        "freeze": False,
        "snapshot_filters": [],
        "source_table": "fact_item",
        "data": data,
        "statistics": {},
        "managed_comparison": True,
        "comparison_id": comparison_id,
        "comparison_config": deepcopy(config),
        "comparison_mode": mode,
        "comparison_metric": metric,
        "comparison_rank_by": rank_by,
        "comparison_top_n": top_n,
        "comparison_categories": categories,
        "revenue_definition": "product_price_excluding_freight",
        "order_grain_definition": "one_row_per_order_and_category",
    }
    tools._attach_rank(view["data"])
    view["statistics"] = tools._compute_view_stats(view)
    return view


def _comparison_rows(
    mode: str,
    metric: str,
    categories: list[str],
) -> list[dict[str, Any]]:
    filters = [
        *tools.active_filters,
        {"field": "product_category", "operator": "in", "value": categories},
    ]
    where = build_where(filters, table="fact_item")
    con = get_connection()

    group_fields = ["product_category"]
    if mode == "weekly_trends":
        group_fields.insert(0, "order_week")
    select_groups = ", ".join(group_fields)
    order_sql = (
        "order_week ASC, product_category ASC"
        if mode == "weekly_trends"
        else f"{metric} DESC NULLS LAST, product_category ASC"
    )

    if metric == "revenue":
        sql = f"""
            SELECT
                {select_groups},
                ROUND(SUM(price), 2) AS revenue
            FROM fact_item
            WHERE {where}
              AND product_category IS NOT NULL
            GROUP BY {select_groups}
            ORDER BY {order_sql}
        """
    else:
        grain_fields = [
            "order_id",
            "product_category",
            "review_score",
            "delivery_days",
            "is_late",
        ]
        if mode == "weekly_trends":
            grain_fields.insert(1, "order_week")
        grain_sql = ", ".join(grain_fields)

        metric_select = {
            "order_count": "COUNT(*) AS order_count",
            "low_score_ratio": (
                f"COUNT(*) FILTER (WHERE review_score <= {FIXED_LOW_SCORE_THRESHOLD}) "
                "AS low_score_count, "
                "COUNT(*) FILTER (WHERE review_score IS NOT NULL) AS order_count, "
                f"ROUND(COUNT(*) FILTER (WHERE review_score <= {FIXED_LOW_SCORE_THRESHOLD})::DOUBLE "
                "/ NULLIF(COUNT(*) FILTER (WHERE review_score IS NOT NULL), 0), 4) "
                "AS low_score_ratio"
            ),
            "delivery_days": "ROUND(AVG(delivery_days), 2) AS delivery_days",
            "late_ratio": (
                "COUNT(*) FILTER (WHERE is_late = TRUE) AS late_count, "
                "COUNT(*) FILTER (WHERE is_late IS NOT NULL) AS order_count, "
                "ROUND(COUNT(*) FILTER (WHERE is_late = TRUE)::DOUBLE "
                "/ NULLIF(COUNT(*) FILTER (WHERE is_late IS NOT NULL), 0), 4) "
                "AS late_ratio"
            ),
        }[metric]

        sql = f"""
            WITH order_category AS (
                SELECT DISTINCT {grain_sql}
                FROM fact_item
                WHERE {where}
                  AND product_category IS NOT NULL
            )
            SELECT
                {select_groups},
                {metric_select}
            FROM order_category
            GROUP BY {select_groups}
            ORDER BY {order_sql}
        """

    result = con.execute(sql)
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _top_categories(top_n: int, rank_by: str) -> list[dict[str, Any]]:
    where = build_where(tools.active_filters, table="fact_item")
    rank_expr = (
        "COUNT(DISTINCT order_id)"
        if rank_by == "order_count"
        else "ROUND(SUM(price), 2)"
    )
    con = get_connection()
    result = con.execute(
        f"""
        SELECT
            product_category,
            {rank_expr} AS rank_value
        FROM fact_item
        WHERE {where}
          AND product_category IS NOT NULL
        GROUP BY product_category
        ORDER BY rank_value DESC, product_category ASC
        LIMIT {top_n}
        """
    )
    return [
        {
            "rank": index + 1,
            "product_category": row[0],
            "rank_value": row[1],
        }
        for index, row in enumerate(result.fetchall())
    ]


def _comparison_evidence(
    views: list[dict[str, Any]],
    top_categories: list[dict[str, Any]],
    metrics: list[str],
    mode: str,
    focus_week: str | None,
) -> list[dict[str, Any]]:
    by_category: dict[str, dict[str, Any]] = {
        item["product_category"]: {
            "rank": item["rank"],
            "product_category": item["product_category"],
            "rank_value": item["rank_value"],
        }
        for item in top_categories
    }

    for metric, view in zip(metrics, views):
        rows = list(view.get("data") or [])
        if mode == "weekly_trends":
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                category = row.get("product_category")
                if category in by_category:
                    grouped[str(category)].append(row)
            for category, category_rows in grouped.items():
                points: list[tuple[str, float]] = []
                for row in category_rows:
                    value = _numeric_value(row.get(metric))
                    week = str(row.get("order_week") or "")
                    if value is not None and week:
                        points.append((week, value))
                points.sort(key=lambda item: (-item[1], item[0]))
                focus_value = next(
                    (value for week, value in points if focus_week and week == focus_week),
                    None,
                )
                by_category[category].setdefault("metrics", {})[metric] = {
                    "peak_week": points[0][0] if points else None,
                    "peak_value": round(points[0][1], 4) if points else None,
                    "focus_week": focus_week,
                    "focus_value": round(focus_value, 4) if focus_value is not None else None,
                    "top_weeks": [
                        {"week": week, "value": round(value, 4)}
                        for week, value in points[:3]
                    ],
                }
        else:
            for row in rows:
                category = row.get("product_category")
                if category not in by_category:
                    continue
                value = _numeric_value(row.get(metric))
                by_category[str(category)][metric] = (
                    round(value, 4) if value is not None else None
                )

    evidence = sorted(by_category.values(), key=lambda item: item["rank"])
    for item in evidence:
        if "revenue" in item:
            item["product_revenue"] = item.pop("revenue")
        metrics_payload = item.get("metrics")
        if isinstance(metrics_payload, dict) and "revenue" in metrics_payload:
            metrics_payload["product_revenue"] = metrics_payload.pop("revenue")
    return evidence


# ---------------------------------------------------------------------------
# Refresh corrected/managed views after scope changes
# ---------------------------------------------------------------------------


def _refresh_managed_comparisons() -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for view in tools.views:
        if view.get("managed_comparison") and view.get("comparison_id"):
            groups[str(view["comparison_id"])].append(view)

    for group_views in groups.values():
        config = deepcopy(group_views[0].get("comparison_config") or {})
        if not config:
            continue
        top_categories = _top_categories(config["top_n"], config["rank_by"])
        categories = [item["product_category"] for item in top_categories]
        category_filter = {
            "field": "product_category",
            "operator": "in",
            "value": categories,
        }
        for view in group_views:
            metric = view["comparison_metric"]
            view["data"] = _comparison_rows(config["mode"], metric, categories) if categories else []
            tools._attach_rank(view["data"])
            view["filters"] = [category_filter]
            view["comparison_categories"] = categories
            view["statistics"] = tools._compute_view_stats(view)


def _refresh_one_view(view: dict[str, Any]) -> None:
    if view.get("managed_comparison"):
        _refresh_managed_comparisons()
        return

    if view.get("y_field") == "revenue" and view.get("source_table") == "fact_item":
        view["agg_expr"] = "ROUND(SUM(price), 2)"
        _refresh_using_existing_engine(view)
        return

    if _needs_order_category_grain(view):
        view["data"] = _order_category_view_rows(view)
        limit = view.get("limit")
        if limit and not view.get("series_limit"):
            view["data"] = view["data"][: int(limit)]
        tools._attach_rank(view["data"])
        view["statistics"] = tools._compute_view_stats(view)
        return

    _refresh_using_existing_engine(view)


def _refresh_using_existing_engine(view: dict[str, Any]) -> None:
    filters = tools._effective_filters_for_view(view)
    color = view.get("color")
    extra_group_fields = [color] if color and view.get("chart_type") in {"bar", "line"} else None
    data = tools._aggregate_visual_data(view, filters, extra_group_fields)
    limit = view.get("limit")
    if limit and not tools._uses_series_limit(view) and not tools._uses_overall_series(view):
        data = data[: int(limit)]
    tools._attach_rank(data)
    view["data"] = data
    view["statistics"] = tools._compute_view_stats(view)


def _needs_order_category_grain(view: dict[str, Any]) -> bool:
    return (
        view.get("source_table") == "fact_item"
        and view.get("y_field") in {"delivery_days", "estimated_delivery_days", "delivery_delay_days"}
        and "product_category" in {
            view.get("x_field"),
            view.get("color"),
            *(item.get("field") for item in view.get("filters") or []),
        }
    )


def _order_category_view_rows(view: dict[str, Any]) -> list[dict[str, Any]]:
    group_fields = [view["group_field"]]
    color = view.get("color")
    if color and color not in group_fields:
        group_fields.append(color)

    filters = tools._effective_filters_for_view(view)
    where = build_where(filters, table="fact_item")
    y = view["y_field"]
    select_groups = ", ".join(group_fields)
    grain_fields = ", ".join(["order_id", *group_fields, y])
    order_sql = (
        f"{view['group_field']} ASC, {color} ASC"
        if color
        else f"{y} {str(view.get('sort_order') or 'desc').upper()} NULLS LAST"
    )
    con = get_connection()
    result = con.execute(
        f"""
        WITH order_category AS (
            SELECT DISTINCT {grain_fields}
            FROM fact_item
            WHERE {where}
        )
        SELECT
            {select_groups},
            ROUND(AVG({y}), 2) AS {y}
        FROM order_category
        GROUP BY {select_groups}
        ORDER BY {order_sql}
        """
    )
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _canonical_metric(value: Any) -> str:
    metric = str(value or "").strip()
    return "revenue" if metric == "product_revenue" else metric


def _metric_description(metric: str) -> str:
    return {
        "order_count": "COUNT(DISTINCT order_id)",
        "revenue": "ROUND(SUM(price), 2)",
        "low_score_ratio": "distinct-order low-score ratio",
        "delivery_days": "order-category average delivery days",
        "late_ratio": "distinct-order late ratio",
    }[metric]


def _dedupe_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in filters:
        key = repr((item.get("field"), item.get("operator"), item.get("value")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _numeric_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _error(tool_name: str, message: str) -> dict[str, Any]:
    return {"tool": tool_name, "success": False, "error": message}
