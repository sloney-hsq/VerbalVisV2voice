"""High-level analytical tools for the two VerbalVis study scenarios.

These tools complement, rather than replace, the primitive dashboard tools. They
make two common multi-step operations reliable for a realtime model:

1. apply several global scope filters in one call;
2. create a consistent Top-N category comparison across several metrics.

The implementation reuses the existing tool layer and current dashboard state.
It does not add cancellation, rollback, transactions, epochs, or stale-tool
invalidation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import realtime as base_realtime
import tools
from db import FIELDS, OPERATORS, build_where, get_connection, total_rows

SCOPE_TOOL = "set_analysis_scope"
COMPARISON_TOOL = "compare_category_metrics"
DEMO_TOOL_NAMES = {SCOPE_TOOL, COMPARISON_TOOL}

COMPARISON_METRICS = [
    "order_count",
    "revenue",
    "low_score_ratio",
    "delivery_days",
    "late_ratio",
]

DEMO_TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": SCOPE_TOOL,
        "description": (
            "Apply several global analysis filters together. Use this when a request "
            "contains a state plus a date range or several scope conditions. Existing "
            "dashboard views refresh automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["replace", "append"],
                    "description": (
                        "replace starts a new global scope; append adds conditions to "
                        "the current global scope. Default replace."
                    ),
                },
                "filters": {
                    "type": "array",
                    "description": (
                        "All scope filters to apply together. For the study date range, "
                        "use order_date between ['2017-10-01','2018-05-31']."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "enum": FIELDS},
                            "operator": {"type": "string", "enum": sorted(OPERATORS)},
                            "value": {
                                "description": (
                                    "A scalar value, or a two-value array for between, "
                                    "or an array for in."
                                )
                            },
                        },
                        "required": ["field", "operator", "value"],
                    },
                },
            },
            "required": ["filters"],
        },
    },
    {
        "type": "function",
        "name": COMPARISON_TOOL,
        "description": (
            "Create several coordinated views for the same revenue-ranked Top-N "
            "product categories. Use weekly_trends for multi-series weekly line charts, "
            "or category_summary for category-level metric bar charts. The tool returns "
            "compact evidence summaries in addition to creating the views."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["weekly_trends", "category_summary"],
                    "description": (
                        "weekly_trends creates one multi-series weekly line chart per "
                        "metric; category_summary creates one category bar chart per metric."
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of categories ranked by rank_by within the current scope.",
                },
                "rank_by": {
                    "type": "string",
                    "enum": ["revenue", "order_count"],
                    "description": "Metric used to select the common category set. Default revenue.",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "enum": COMPARISON_METRICS},
                    "description": (
                        "Metrics to compare. Task A commonly uses order_count, "
                        "low_score_ratio, delivery_days, late_ratio. Task B commonly "
                        "uses low_score_ratio, delivery_days, revenue, order_count."
                    ),
                },
                "focus_week": {
                    "type": ["string", "null"],
                    "description": (
                        "Optional ISO week to compare with metric peaks, e.g. 2017-W48. "
                        "Used only in weekly_trends evidence summaries."
                    ),
                },
                "title_prefix": {
                    "type": ["string", "null"],
                    "description": "Optional short prefix for the generated view titles.",
                },
            },
            "required": ["mode", "top_n", "metrics"],
        },
    },
]


def register_demo_tool_schemas() -> None:
    """Append high-level schemas to the list used by the base realtime bridge."""
    existing = {
        str((tool.get("function") or tool).get("name") or "")
        for tool in base_realtime.TOOL_SCHEMAS
        if isinstance(tool, dict)
    }
    for schema in DEMO_TOOL_SCHEMAS:
        if schema["name"] not in existing:
            base_realtime.TOOL_SCHEMAS.append(schema)


def is_demo_tool(name: str) -> bool:
    return name in DEMO_TOOL_NAMES


def execute_demo_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == SCOPE_TOOL:
        return _exec_set_analysis_scope(arguments)
    if name == COMPARISON_TOOL:
        return _exec_compare_category_metrics(arguments)
    return {
        "tool": name,
        "success": False,
        "error": f"Unknown high-level tool: {name}",
    }


def _exec_set_analysis_scope(arguments: dict[str, Any]) -> dict[str, Any]:
    mode = str(arguments.get("mode") or "replace").strip().lower()
    if mode not in {"replace", "append"}:
        return {
            "tool": SCOPE_TOOL,
            "success": False,
            "error": "mode must be 'replace' or 'append'.",
        }

    raw_filters = arguments.get("filters") or []
    if not isinstance(raw_filters, list) or not raw_filters:
        return {
            "tool": SCOPE_TOOL,
            "success": False,
            "error": "filters must contain at least one filter object.",
        }

    normalized_filters: list[dict[str, Any]] = []
    for raw_filter in raw_filters:
        if not isinstance(raw_filter, dict):
            return {
                "tool": SCOPE_TOOL,
                "success": False,
                "error": "Each scope filter must be an object.",
            }
        normalized, error = tools._normalize_filter(
            raw_filter,
            tool_name=SCOPE_TOOL,
        )
        if error:
            return {
                "tool": SCOPE_TOOL,
                "success": False,
                "error": error.get("error") or "Invalid scope filter.",
            }
        assert normalized is not None
        normalized_filters.append(normalized)

    next_filters = (
        [*tools.active_filters, *normalized_filters]
        if mode == "append"
        else normalized_filters
    )
    next_filters = _dedupe_filters(next_filters)

    tools.active_filters = next_filters
    tools._refresh_all_views()
    rows = total_rows(tools.active_filters)

    result: dict[str, Any] = {
        "tool": SCOPE_TOOL,
        "success": True,
        "payload": {
            "mode": mode,
            "active_filters": tools.active_filters.copy(),
            "filtered_rows": rows,
        },
    }
    if rows == 0:
        result["warning"] = "The requested scope contains 0 orders."
    return result


def _exec_compare_category_metrics(arguments: dict[str, Any]) -> dict[str, Any]:
    mode = str(arguments.get("mode") or "").strip()
    if mode not in {"weekly_trends", "category_summary"}:
        return {
            "tool": COMPARISON_TOOL,
            "success": False,
            "error": "mode must be 'weekly_trends' or 'category_summary'.",
        }

    try:
        top_n = int(arguments.get("top_n") or (5 if mode == "weekly_trends" else 15))
    except (TypeError, ValueError):
        top_n = 0
    if top_n < 1 or top_n > 30:
        return {
            "tool": COMPARISON_TOOL,
            "success": False,
            "error": "top_n must be an integer from 1 to 30.",
        }

    rank_by = str(arguments.get("rank_by") or "revenue").strip()
    if rank_by not in {"revenue", "order_count"}:
        return {
            "tool": COMPARISON_TOOL,
            "success": False,
            "error": "rank_by must be 'revenue' or 'order_count'.",
        }

    metrics = arguments.get("metrics") or []
    if not isinstance(metrics, list):
        metrics = [metrics]
    metrics = [str(metric) for metric in metrics if str(metric) in COMPARISON_METRICS]
    metrics = list(dict.fromkeys(metrics))
    if not metrics:
        metrics = (
            ["order_count", "low_score_ratio", "delivery_days", "late_ratio"]
            if mode == "weekly_trends"
            else ["low_score_ratio", "delivery_days", "revenue", "order_count"]
        )

    top_categories = _top_categories(top_n, rank_by)
    if not top_categories:
        return {
            "tool": COMPARISON_TOOL,
            "success": False,
            "error": "No product categories are available in the current analysis scope.",
        }

    focus_week = str(arguments.get("focus_week") or "").strip() or None
    title_prefix = str(arguments.get("title_prefix") or "").strip()
    category_filter = {
        "field": "product_category",
        "operator": "in",
        "value": [item["product_category"] for item in top_categories],
    }

    created_results: list[dict[str, Any]] = []
    for metric in metrics:
        append_args = _comparison_view_args(
            mode=mode,
            metric=metric,
            top_n=top_n,
            rank_by=rank_by,
            category_filter=category_filter,
            title_prefix=title_prefix,
        )
        result = tools.execute_tool("append_visual", append_args)
        if not result.get("success"):
            return {
                "tool": COMPARISON_TOOL,
                "success": False,
                "error": result.get("error") or f"Unable to create the {metric} comparison view.",
                "payload": {
                    "created_view_ids": [
                        item.get("payload", {}).get("view_id")
                        for item in created_results
                        if item.get("payload", {}).get("view_id")
                    ],
                    "top_categories": top_categories,
                },
            }

        created_results.append(result)
        payload = result.get("payload") or {}
        view_id = payload.get("view_id")
        view = next((item for item in tools.views if item.get("id") == view_id), None)
        if view is not None:
            view["comparison_mode"] = mode
            view["comparison_metric"] = metric
            view["comparison_rank_by"] = rank_by
            view["comparison_top_n"] = top_n
            view["comparison_categories"] = [
                item["product_category"] for item in top_categories
            ]

    evidence = (
        _weekly_evidence(created_results, top_categories, metrics, focus_week)
        if mode == "weekly_trends"
        else _category_summary_evidence(created_results, top_categories, metrics)
    )

    return {
        "tool": COMPARISON_TOOL,
        "success": True,
        "payload": {
            "mode": mode,
            "rank_by": rank_by,
            "top_n": top_n,
            "top_categories": top_categories,
            "metrics": metrics,
            "focus_week": focus_week,
            "view_ids": [
                item.get("payload", {}).get("view_id")
                for item in created_results
                if item.get("payload", {}).get("view_id")
            ],
            "evidence": evidence,
            "active_filters": tools.active_filters.copy(),
            "filtered_rows": total_rows(tools.active_filters),
        },
    }


def _comparison_view_args(
    *,
    mode: str,
    metric: str,
    top_n: int,
    rank_by: str,
    category_filter: dict[str, Any],
    title_prefix: str,
) -> dict[str, Any]:
    label = {
        "order_count": "Order count",
        "revenue": "Revenue",
        "low_score_ratio": "Low-score ratio",
        "delivery_days": "Average delivery time",
        "late_ratio": "Late-order ratio",
    }[metric]
    prefix = f"{title_prefix} " if title_prefix else ""

    if mode == "weekly_trends":
        return {
            "chart_type": "line",
            "x": "order_week",
            "y": metric,
            "color": "product_category",
            "title": f"{prefix}Weekly {label} · Top {top_n} categories",
            "series_limit": top_n,
            "series_sort_by": rank_by,
            "series_sort_order": "desc",
            "filters": [category_filter],
            "inherit_global_filters": True,
            "freeze": False,
        }

    return {
        "chart_type": "bar",
        "x": "product_category",
        "y": metric,
        "color": None,
        "title": f"{prefix}{label} · Revenue Top {top_n} categories",
        "limit": top_n,
        "sort_by": metric,
        "sort_order": "desc",
        "filters": [category_filter],
        "inherit_global_filters": True,
        "freeze": False,
    }


def _top_categories(top_n: int, rank_by: str) -> list[dict[str, Any]]:
    where = build_where(tools.active_filters, table="fact_item")
    rank_expr = (
        "COUNT(DISTINCT order_id)"
        if rank_by == "order_count"
        else "ROUND(SUM(item_revenue), 2)"
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


def _weekly_evidence(
    results: list[dict[str, Any]],
    top_categories: list[dict[str, Any]],
    metrics: list[str],
    focus_week: str | None,
) -> list[dict[str, Any]]:
    by_category: dict[str, dict[str, Any]] = {
        item["product_category"]: {
            "rank": item["rank"],
            "product_category": item["product_category"],
            "rank_value": item["rank_value"],
            "metrics": {},
        }
        for item in top_categories
    }

    for metric, result in zip(metrics, results):
        rows = list((result.get("payload") or {}).get("data") or [])
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
            by_category[category]["metrics"][metric] = {
                "peak_week": points[0][0] if points else None,
                "peak_value": round(points[0][1], 4) if points else None,
                "focus_week": focus_week,
                "focus_value": round(focus_value, 4) if focus_value is not None else None,
                "top_weeks": [
                    {"week": week, "value": round(value, 4)}
                    for week, value in points[:3]
                ],
            }

    return sorted(by_category.values(), key=lambda item: item["rank"])


def _category_summary_evidence(
    results: list[dict[str, Any]],
    top_categories: list[dict[str, Any]],
    metrics: list[str],
) -> list[dict[str, Any]]:
    by_category: dict[str, dict[str, Any]] = {
        item["product_category"]: {
            "rank": item["rank"],
            "product_category": item["product_category"],
            "rank_value": item["rank_value"],
        }
        for item in top_categories
    }

    for metric, result in zip(metrics, results):
        rows = list((result.get("payload") or {}).get("data") or [])
        for row in rows:
            category = row.get("product_category")
            if category not in by_category:
                continue
            value = _numeric_value(row.get(metric))
            by_category[str(category)][metric] = (
                round(value, 4) if value is not None else None
            )

    return sorted(by_category.values(), key=lambda item: item["rank"])


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
