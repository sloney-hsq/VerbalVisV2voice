"""
VerbalVis tool layer.
Defines tool schemas, executes tool calls, rebuilds dashboard context.
"""

from __future__ import annotations

import json
import logging
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

# ------------------------------------------------------------------
# Runtime state (per-session; single-user prototype)
# ------------------------------------------------------------------

active_filters: list[dict[str, Any]] = []
workspace_counter: int = 0          # workspace-1, workspace-2, …
views: list[dict[str, Any]] = []    # all views (base + workspace)
highlighted_view: str | None = None

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
    global active_filters, workspace_counter, views, highlighted_view
    active_filters = []
    workspace_counter = 0
    highlighted_view = None
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
        "Pass field=null to clear all filters.",
        {
            "type": "object",
            "properties": {
                "field": {
                    "type": ["string", "null"],
                    "enum": FIELDS + [None],
                    "description": "Field to filter on. null clears all filters.",
                },
                "operator": {
                    "type": "string",
                    "enum": list(OPERATORS),
                    "description": "Comparison operator.",
                },
                "value": {
                    "description": "Filter value (string, number, null, or array for 'in').",
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
        "append_visual",
        "Create a new chart and append it to the dashboard grid.",
        {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["scatter", "bar", "line", "histogram"],
                },
                "x": {
                    "type": "string",
                    "enum": FIELDS,
                    "description": "X-axis field.",
                },
                "y": {
                    "type": "string",
                    "enum": FIELDS,
                    "description": "Y-axis field.",
                },
                "color": {
                    "type": ["string", "null"],
                    "enum": ["customer_state", "product_category", "review_score", None],
                    "description": "Optional color encoding field.",
                },
                "title": {
                    "type": "string",
                    "description": "Human-readable chart title.",
                },
            },
            "required": ["chart_type", "x", "y", "title"],
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
        elif name == "append_visual":
            return _exec_append_visual(arguments)
        else:
            return {"tool": name, "success": False, "error": f"Unknown tool: {name}"}
    except Exception as exc:
        log.exception("Tool execution error: %s", name)
        return {"tool": name, "success": False, "error": str(exc)}


# --- filter_data ---

def _exec_filter_data(args: dict) -> dict:
    global active_filters

    field = args.get("field")
    if field is None:
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

    # Validate
    if field not in FIELDS:
        return {
            "tool": "filter_data",
            "success": False,
            "error": f"Unknown field: '{field}'. Available: {', '.join(FIELDS)}",
        }
    operator = args.get("operator", "eq")
    if operator not in OPERATORS:
        return {
            "tool": "filter_data",
            "success": False,
            "error": f"Invalid operator: '{operator}'. Supported: {', '.join(OPERATORS)}",
        }
    value = args.get("value")
    append = args.get("append", False)

    new_filter = {"field": field, "operator": operator, "value": value}

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

ALLOWED_CHART_TYPES = {"scatter", "bar", "line", "histogram"}
ALLOWED_COLOR_FIELDS = {"customer_state", "product_category", "review_score"}


def _exec_append_visual(args: dict) -> dict:
    global workspace_counter

    chart_type = args.get("chart_type")
    x = args.get("x")
    y = args.get("y")
    color = args.get("color")
    title = args.get("title") or f"{y} by {x}"

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
    if y not in FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for y: '{y}'. Available: {', '.join(FIELDS)}",
        }
    if color is not None and color not in ALLOWED_COLOR_FIELDS:
        return {
            "tool": "append_visual",
            "success": False,
            "error": f"Unknown field for color: '{color}'. Available: {', '.join(sorted(ALLOWED_COLOR_FIELDS))}",
        }

    workspace_counter += 1
    view_id = f"workspace-{workspace_counter}"

    # Route to fact_item whenever product_category is involved (x / y / color);
    # otherwise stay on fact_order. Keeps revenue at item grain when grouping
    # by category, and avoids cross-grain joins when not needed.
    source_table = _decide_table(x, y, color)

    # Determine aggregation
    agg_expr, agg_alias, group_field, order_by = _infer_agg(chart_type, x, y, source_table)

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
        "source_table": source_table,
        "data": [],
        "statistics": {},
    }

    # Query data
    if chart_type == "scatter":
        view_def["data"] = _scatter_data(x, y, color, source_table)
    else:
        view_def["data"] = aggregate_query(
            group_field=group_field,
            agg_expr=agg_expr,
            agg_alias=agg_alias,
            filters=active_filters,
            order_by=order_by,
            extra_group_fields=extra_group_fields,
            table=source_table,
        )

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
            "data": view_def["data"],
        },
    }


def _decide_table(x: str, y: str, color: str | None) -> str:
    """Choose source table for an append_visual call.

    Any reference to product_category forces fact_item (item grain). Otherwise
    fact_order is enough — all order-level filter fields exist on it.
    """
    if "product_category" in (x, y, color):
        return "fact_item"
    return "fact_order"


def _infer_agg(chart_type: str, x: str, y: str, table: str):
    """Infer SQL aggregation from chart type, fields, and source table."""
    if chart_type == "scatter":
        return y, y, x, x  # no aggregation needed
    if chart_type == "histogram":
        return "COUNT(*)", "count", x, x
    # bar / line
    if y == "revenue":
        # On fact_item revenue = SUM(price + freight); on fact_order it's the
        # per-order payment total. These are semantically different — pick the
        # column that matches the table the query will run against.
        col = "item_revenue" if table == "fact_item" else "order_revenue"
        return f"ROUND(SUM({col}), 2)", "revenue", x, "revenue DESC"
    if y == "delivery_days":
        return "ROUND(AVG(delivery_days), 1)", "delivery_days", x, x
    # default: count
    return "COUNT(*)", "order_count", x, x


def _scatter_data(
    x: str, y: str, color: str | None = None, table: str = "fact_order"
) -> list[dict]:
    """Get raw rows for scatter plot (sampled to 2000 max).

    Filter-system names like "revenue" are resolved to the right physical
    column on the chosen table and aliased back so the returned rows carry
    the original field name the frontend expects.
    """
    con = get_connection()
    where = build_where(active_filters, table=table)

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
        table = view.get("source_table", "fact_order")
        if view["chart_type"] == "scatter":
            view["data"] = _scatter_data(
                view["x_field"], view["y_field"], view.get("color"), table
            )
        else:
            limit = view.get("limit")
            color = view.get("color")
            extra_group_fields = (
                [color] if (color and view["chart_type"] in ("bar", "line")) else None
            )
            data = aggregate_query(
                group_field=view["group_field"],
                agg_expr=view["agg_expr"],
                agg_alias=view["agg_alias"],
                filters=active_filters,
                order_by=view.get("order_by"),
                extra_group_fields=extra_group_fields,
                table=table,
            )
            if limit:
                data = data[:limit]
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

    try:
        if vid == "view-trend" or view["chart_type"] == "line":
            values = [(d.get(view["x_field"]), d.get(y, 0)) for d in data if d.get(y) is not None]
            if values:
                peak = max(values, key=lambda t: t[1])
                avg_val = sum(v[1] for v in values) / len(values)
                stats["peak_month"] = str(peak[0])
                stats["peak_value"] = peak[1]
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
                total = sum(d.get(y, 0) for d in data)
                stats["top_state"] = top.get("customer_state")
                stats["top_state_count"] = top.get(y)
                stats["top_state_ratio"] = round(top.get(y, 0) / total, 3) if total else 0
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
                stats["top_value"] = top.get(y)
                stats["top_label"] = top.get(view.get("group_field", view["x_field"]))
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
        ctx_views.append({
            "id": v["id"],
            "chart_type": v["chart_type"],
            "title": v["title"],
            "x_field": v["x_field"],
            "y_field": v["y_field"],
            "statistics": v["statistics"],
        })

    return {
        "active_filters": active_filters.copy(),
        "highlighted_view": highlighted_view,
        "views": ctx_views,
        "available_view_ids": [v["id"] for v in views],
        "filtered_rows": total_rows(active_filters),
    }


def context_text() -> str:
    """Compact text summary for injection via conversation.item.create."""
    ctx = rebuild_context()

    lines = ["Dashboard updated.\n"]

    if ctx["highlighted_view"]:
        lines.append(f"Highlighted view: {ctx['highlighted_view']}")

    if ctx["active_filters"]:
        lines.append("Active filters:")
        for f in ctx["active_filters"]:
            lines.append(f"  {f['field']} {f['operator']} {f['value']}")
    else:
        lines.append("Active filters: none")

    lines.append(f"Total rows: {ctx['filtered_rows']}")
    lines.append("\nAvailable views:")
    for v in ctx["views"]:
        stat_str = ", ".join(f"{k}={v_}" for k, v_ in v["statistics"].items() if k != "row_count")
        lines.append(f"  {v['id']}: {v['title']} [{v['chart_type']}] ({stat_str})")

    return "\n".join(lines)


def get_all_view_data() -> list[dict]:
    """Return view id + data for all views (sent to frontend)."""
    return [{"id": v["id"], "data": v["data"]} for v in views]


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
            "data": v["data"],
            "highlighted": v["id"] == highlighted_view,
        })
    return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _filters_summary() -> str:
    parts = []
    for f in active_filters:
        parts.append(f"{f['field']} {f['operator']} {f['value']}")
    return " AND ".join(parts) if parts else "none"


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
