"""Local validation for the two VerbalVis study demos.

Run from backend/ after installing requirements:

    python demo_validation.py

The script does not call Qwen. It validates the model-facing tool surface,
product-revenue definition, order-category delivery grain, coordinated views,
and the evidence payloads required by Task A/B.
"""

from __future__ import annotations

import json
from typing import Any

import realtime as base_realtime
import tools
from db import build_where, get_connection, initialize_db
from demo_tools import execute_demo_tool, register_demo_tool_schemas

DATE_FILTER = {
    "field": "order_date",
    "operator": "between",
    "value": ["2017-10-01", "2018-05-31"],
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _view(view_id: str) -> dict[str, Any]:
    match = next((view for view in tools.views if view.get("id") == view_id), None)
    _require(match is not None, f"Missing generated view: {view_id}")
    assert match is not None
    return match


def _schema_names() -> set[str]:
    names: set[str] = set()
    for schema in base_realtime.TOOL_SCHEMAS:
        function = schema.get("function") if isinstance(schema, dict) else None
        name = function.get("name") if isinstance(function, dict) else schema.get("name")
        if name:
            names.add(str(name))
    return names


def validate_tool_surface() -> dict[str, Any]:
    register_demo_tool_schemas()
    names = _schema_names()
    expected = {
        "update_analysis_scope",
        "create_visual",
        "compare_category_metrics",
        "delete_visual",
        "highlight_visual",
        "inspect_visual",
    }
    hidden = {
        "filter_data",
        "remove_filter",
        "append_visual",
        "set_low_score_threshold",
        "set_analysis_scope",
    }
    _require(expected.issubset(names), f"Missing model-facing tools: {expected - names}")
    _require(not (hidden & names), f"Ambiguous/internal tools are still exposed: {hidden & names}")

    view4 = _view("view4")
    _require(
        view4.get("agg_expr") == "ROUND(SUM(price), 2)",
        f"view4 does not use product price revenue: {view4.get('agg_expr')}",
    )
    return {"model_tools": sorted(names)}


def _set_scope(state: str) -> dict[str, Any]:
    result = execute_demo_tool(
        "update_analysis_scope",
        {
            "operation": "replace",
            "filters": [
                {"field": "customer_state", "operator": "eq", "value": state},
                DATE_FILTER,
            ],
        },
    )
    _require(result.get("success") is True, f"Unable to set {state} scope: {result}")
    payload = result.get("payload", {})
    _require(len(payload.get("active_filters", [])) == 2, f"Expected two filters for {state}")
    _require(int(payload.get("filtered_rows", 0)) > 0, f"The {state} scope is empty")
    _require(
        payload.get("low_score_definition") == "review_score <= 2",
        "The study low-score definition must remain fixed at <=2",
    )
    return result


def validate_task_a() -> dict[str, Any]:
    tools.init_views()
    register_demo_tool_schemas()
    scope = _set_scope("SP")
    result = execute_demo_tool(
        "compare_category_metrics",
        {
            "mode": "weekly_trends",
            "top_n": 5,
            "rank_by": "product_revenue",
            "metrics": [
                "order_count",
                "low_score_ratio",
                "delivery_days",
                "late_ratio",
            ],
            "focus_week": "2017-W48",
            "title_prefix": "SP",
        },
    )
    _require(result.get("success") is True, f"Task A comparison failed: {result}")

    payload = result.get("payload", {})
    view_ids = payload.get("view_ids", [])
    categories = payload.get("top_categories", [])
    evidence = payload.get("evidence", [])

    _require(len(view_ids) == 4, f"Task A should create four views, got {view_ids}")
    _require(len(categories) == 5, f"Task A should use five categories, got {categories}")
    _require(len(evidence) == 5, "Task A should return evidence for five categories")
    _require(payload.get("revenue_definition") == "SUM(price), freight excluded", "Wrong revenue definition")
    _require(
        payload.get("delivery_grain") == "one row per order and product category",
        "Wrong delivery grain",
    )

    expected_metrics = {
        "order_count",
        "low_score_ratio",
        "delivery_days",
        "late_ratio",
    }
    expected_categories = {item["product_category"] for item in categories}

    for view_id in view_ids:
        view = _view(view_id)
        _require(view.get("chart_type") == "line", f"{view_id} is not a line chart")
        _require(view.get("x_field") == "order_week", f"{view_id} is not weekly")
        _require(view.get("color") == "product_category", f"{view_id} is not multi-series")
        _require(
            set(view.get("comparison_categories", [])) == expected_categories,
            f"{view_id} does not use the common Top-5 set",
        )

    for item in evidence:
        metrics = item.get("metrics", {})
        _require(set(metrics) == expected_metrics, f"Incomplete Task A evidence: {item}")
        for metric in expected_metrics:
            metric_evidence = metrics[metric]
            _require(metric_evidence.get("focus_week") == "2017-W48", "Missing focus week")
            _require(metric_evidence.get("peak_week") is not None, "Missing peak week")

    return {
        "scope_rows": scope["payload"]["filtered_rows"],
        "top_categories": categories,
        "view_ids": view_ids,
        "focus_week": payload.get("focus_week"),
    }


def validate_task_b() -> dict[str, Any]:
    tools.init_views()
    register_demo_tool_schemas()
    scope = _set_scope("RJ")
    result = execute_demo_tool(
        "compare_category_metrics",
        {
            "mode": "category_summary",
            "top_n": 15,
            "rank_by": "product_revenue",
            "metrics": [
                "low_score_ratio",
                "delivery_days",
                "product_revenue",
                "order_count",
            ],
            "title_prefix": "RJ",
        },
    )
    _require(result.get("success") is True, f"Task B comparison failed: {result}")

    payload = result.get("payload", {})
    view_ids = payload.get("view_ids", [])
    categories = payload.get("top_categories", [])
    evidence = payload.get("evidence", [])

    _require(len(view_ids) == 4, f"Task B should create four views, got {view_ids}")
    _require(len(categories) == 15, "Task B should use fifteen categories")
    _require(len(evidence) == 15, "Task B should return fifteen comparison rows")

    expected_categories = {item["product_category"] for item in categories}
    _require(
        "office_furniture" in expected_categories,
        "office_furniture is not in RJ product-revenue Top 15",
    )

    expected_metrics = {
        "low_score_ratio",
        "delivery_days",
        "product_revenue",
        "order_count",
    }
    for item in evidence:
        _require(
            expected_metrics.issubset(item),
            f"Incomplete Task B evidence for {item.get('product_category')}: {item}",
        )

    for view_id in view_ids:
        view = _view(view_id)
        _require(view.get("chart_type") == "bar", f"{view_id} is not a bar chart")
        _require(
            set(view.get("comparison_categories", [])) == expected_categories,
            f"{view_id} does not use the common Top-15 set",
        )

    office = next(item for item in evidence if item.get("product_category") == "office_furniture")
    _validate_office_furniture_semantics(office)

    return {
        "scope_rows": scope["payload"]["filtered_rows"],
        "top_categories": categories,
        "view_ids": view_ids,
        "office_furniture": office,
    }


def _validate_office_furniture_semantics(office: dict[str, Any]) -> None:
    filters = [
        *tools.active_filters,
        {
            "field": "product_category",
            "operator": "eq",
            "value": "office_furniture",
        },
    ]
    where = build_where(filters, table="fact_item")
    con = get_connection()

    expected_revenue = con.execute(
        f"SELECT ROUND(SUM(price), 2) FROM fact_item WHERE {where}"
    ).fetchone()[0]
    expected_delivery = con.execute(
        f"""
        WITH order_category AS (
            SELECT DISTINCT order_id, product_category, delivery_days
            FROM fact_item
            WHERE {where}
        )
        SELECT ROUND(AVG(delivery_days), 2)
        FROM order_category
        """
    ).fetchone()[0]

    _require(
        abs(float(office["product_revenue"]) - float(expected_revenue)) < 0.01,
        f"Product revenue includes the wrong values: {office['product_revenue']} vs {expected_revenue}",
    )
    _require(
        abs(float(office["delivery_days"]) - float(expected_delivery)) < 0.01,
        f"Delivery average is not order-category grain: {office['delivery_days']} vs {expected_delivery}",
    )


def main() -> None:
    initialize_db()
    tools.init_views()
    tool_surface = validate_tool_surface()
    task_a = validate_task_a()
    task_b = validate_task_b()
    print("Tool surface validation: PASS")
    print(json.dumps(tool_surface, ensure_ascii=False, indent=2, default=str))
    print("Task A validation: PASS")
    print(json.dumps(task_a, ensure_ascii=False, indent=2, default=str))
    print("Task B validation: PASS")
    print(json.dumps(task_b, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
