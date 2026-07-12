"""Offline validation for the final VerbalVis tool service.

Run from backend/ after installing requirements:

    python demo_validation.py

No Qwen API call is made.
"""

from __future__ import annotations

import json
from typing import Any

from db import build_where, get_connection, initialize_db
import tools

EXPECTED_TOOLS = {
    "update_analysis_scope",
    "aggregate_data",
    "compare_selected_groups",
    "compare_category_metrics",
    "create_visual",
    "update_visual",
    "delete_visual",
    "highlight_visual",
    "inspect_visual",
    "summarize_dashboard",
    "undo_last_action",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def view(view_id: str) -> dict[str, Any]:
    match = next((item for item in tools.views if item.get("id") == view_id), None)
    require(match is not None, f"Missing view: {view_id}")
    assert match is not None
    return match


def schema_names() -> set[str]:
    return {
        str(schema.get("name"))
        for schema in tools.TOOL_SCHEMAS
        if isinstance(schema, dict) and schema.get("name")
    }


def validate_tool_surface() -> dict[str, Any]:
    tools.init_views()
    names = schema_names()
    require(names == EXPECTED_TOOLS, f"Unexpected tool surface: {sorted(names)}")
    require(len(tools.views) == 4, "Four base views are required")
    category_view = view("view4")
    require(category_view["y_field"] == "product_revenue", "Base category view uses wrong revenue field")
    require(category_view["data"], "Base category view has no data")
    require("product_revenue" in category_view["data"][0], "Base category data is missing product_revenue")
    return {"tools": sorted(names), "base_views": [item["id"] for item in tools.views]}


def validate_general_tools() -> dict[str, Any]:
    tools.init_views()

    aggregate = tools.execute_tool(
        "aggregate_data",
        {
            "group_by": ["customer_state"],
            "metrics": ["order_count", "low_score_ratio", "delivery_days"],
            "sort_by": "order_count",
            "sort_order": "desc",
            "limit": 5,
        },
    )
    require(aggregate.get("success") is True, f"aggregate_data failed: {aggregate}")
    require(len(aggregate["payload"]["rows"]) == 5, "aggregate_data limit failed")

    selected = tools.execute_tool(
        "compare_selected_groups",
        {
            "dimension": "customer_state",
            "values": ["SP", "RJ"],
            "metrics": ["order_count", "low_score_ratio", "delivery_days"],
            "time_grain": "order_month",
        },
    )
    require(selected.get("success") is True, f"compare_selected_groups failed: {selected}")
    require(selected["payload"]["rows"], "Selected-group comparison is empty")

    created = tools.execute_tool(
        "create_visual",
        {
            "chart_type": "scatter",
            "x": "review_score",
            "y": "delivery_days",
            "series": "customer_state",
            "title": "Review score and delivery time",
        },
    )
    require(created.get("success") is True, f"create_visual failed: {created}")
    view_id = created["payload"]["view_id"]

    updated = tools.execute_tool(
        "update_visual",
        {
            "view_id": view_id,
            "chart_type": "bar",
            "x": "customer_state",
            "y": "order_count",
            "series": "none",
            "title": "Orders by state",
            "top_n": 10,
        },
    )
    require(updated.get("success") is True, f"update_visual failed: {updated}")
    require(view(view_id)["chart_type"] == "bar", "View type was not updated")
    require(view(view_id)["sort_by"] == "order_count", "Updated view kept stale sorting")
    require(view(view_id)["sort_order"] == "desc", "Updated view kept stale sort order")

    highlighted = tools.execute_tool(
        "highlight_visual",
        {
            "action": "highlight",
            "view_ids": [view_id],
            "highlight_element": "SP",
            "dim_others": True,
        },
    )
    require(highlighted.get("success") is True, f"highlight_visual failed: {highlighted}")

    inspected = tools.execute_tool(
        "inspect_visual",
        {"view_id": view_id, "x_values": ["SP"], "top_k": 5},
    )
    require(inspected.get("success") is True, f"inspect_visual failed: {inspected}")
    require(inspected["payload"]["returned_data_points"] >= 1, "Focused inspection returned no rows")

    summary = tools.execute_tool("summarize_dashboard", {})
    require(summary.get("success") is True, f"summarize_dashboard failed: {summary}")
    require(summary["payload"]["highlighted_views"] == [view_id], "Dashboard summary lost highlight")

    undo_highlight = tools.execute_tool("undo_last_action", {})
    require(undo_highlight.get("success") is True, "Unable to undo highlight")
    require(not tools.highlighted_views, "Undo did not restore highlight state")

    deleted = tools.execute_tool("delete_visual", {"view_id": view_id})
    require(deleted.get("success") is True, f"delete_visual failed: {deleted}")
    require(not any(item["id"] == view_id for item in tools.views), "View was not deleted")

    undo_delete = tools.execute_tool("undo_last_action", {})
    require(undo_delete.get("success") is True, "Unable to undo deletion")
    require(any(item["id"] == view_id for item in tools.views), "Undo did not restore deleted view")

    return {
        "aggregate_rows": aggregate["payload"]["row_count"],
        "comparison_rows": selected["payload"]["row_count"],
        "created_view": view_id,
    }


def validate_scope_argument_recovery() -> dict[str, Any]:
    tools.init_views()
    recovered = tools.execute_tool(
        "update_analysis_scope",
        {
            "operation": "replace",
            "filters": [
                {"field": "customer_state", "value": "sp"},
                {
                    "field": "order_date",
                    "value": "2017-10-01 2018-05-31",
                },
            ],
        },
    )
    require(recovered.get("success") is True, f"Scope recovery failed: {recovered}")
    filters = recovered["payload"]["active_filters"]
    require(
        filters
        == [
            {"field": "customer_state", "operator": "eq", "value": "SP"},
            {
                "field": "order_date",
                "operator": "between",
                "value": ["2017-10-01", "2018-05-31"],
            },
        ],
        f"Recovered scope is wrong: {filters}",
    )

    alias = tools.execute_tool(
        "aggregate_data",
        {
            "metrics": ["order_count"],
            "filters": [
                {"field": "customer_state", "operator": "==", "value": "SP"},
            ],
        },
    )
    require(alias.get("success") is True, f"Operator alias failed: {alias}")
    in_string = tools.execute_tool(
        "aggregate_data",
        {
            "metrics": ["order_count"],
            "filters": [
                {
                    "field": "customer_state",
                    "operator": "in",
                    "value": "SP,RJ",
                },
            ],
        },
    )
    require(in_string.get("success") is True, f"String in-filter failed: {in_string}")
    return {
        "active_filters": filters,
        "filtered_rows": recovered["payload"]["filtered_rows"],
    }


def validate_normalized_rating_chart() -> dict[str, Any]:
    tools.init_views()
    result = tools.execute_tool(
        "create_visual",
        {
            "chart_type": "bar",
            "x": "customer_state",
            "y": "order_count",
            "series": "review_score",
            "normalize": True,
            "sort_by": "customer_state",
            "sort_order": "asc",
            "title": "Rating share by state",
        },
    )
    require(result.get("success") is True, f"Normalized chart failed: {result}")
    item = view(result["payload"]["view_id"])
    require(item["normalize"] is True, "Normalized chart metadata was lost")
    require(item["normalized_field"] == "normalized_value", "Normalized field is missing")

    scores = {row.get("review_score") for row in item["data"]}
    require(scores == {None, 1, 2, 3, 4, 5}, f"Unexpected rating domain: {scores}")
    totals: dict[str, float] = {}
    for row in item["data"]:
        state = str(row["customer_state"])
        totals[state] = totals.get(state, 0.0) + float(row["normalized_value"])
    require(len(totals) == 27, f"Expected 27 states, found {len(totals)}")
    require(
        all(abs(total - 1.0) < 0.00001 for total in totals.values()),
        f"State rating shares are not normalized: {totals}",
    )
    return {
        "view_id": item["id"],
        "states": len(totals),
        "rating_domain": sorted("null" if value is None else str(value) for value in scores),
    }


def validate_verified_order_and_revision() -> dict[str, Any]:
    tools.init_views()
    initial_revision = tools.realtime_state().get("dashboard_revision")
    aggregated = tools.execute_tool(
        "aggregate_data",
        {
            "group_by": ["customer_state"],
            "metrics": ["low_score_ratio"],
            "sort_by": "order_count",
            "sort_order": "desc",
            "limit": 3,
        },
    )
    require(aggregated.get("success") is True, f"Cross-metric aggregate failed: {aggregated}")
    require(
        [row["customer_state"] for row in aggregated["payload"]["rows"]]
        == ["SP", "RJ", "MG"],
        f"Cross-metric aggregate order is wrong: {aggregated['payload']['rows']}",
    )
    require(
        all("order_count" in row for row in aggregated["payload"]["rows"]),
        "Cross-metric aggregate did not materialize order_count",
    )
    created = tools.execute_tool(
        "create_visual",
        {
            "chart_type": "bar",
            "x": "customer_state",
            "y": "low_score_ratio",
            "sort_by": "order_count",
            "sort_order": "desc",
            "title": "Low score by order volume",
        },
    )
    require(created.get("success") is True, f"Cross-metric visual failed: {created}")
    item = view(created["payload"]["view_id"])
    order_contract = item.get("order_contract")
    require(isinstance(order_contract, dict), "Cross-metric visual is missing order_contract")
    require(order_contract.get("verified") is True, "Cross-metric order was not verified")
    require(
        order_contract.get("values", [])[:3] == ["SP", "RJ", "MG"],
        f"Cross-metric order is wrong: {order_contract.get('values')}",
    )
    require(
        all("order_count" in row for row in item["data"]),
        "Cross-metric visual did not materialize order_count",
    )

    created_revision = created["payload"].get("dashboard_revision")
    require(isinstance(initial_revision, int), "Realtime state is missing dashboard_revision")
    require(isinstance(created_revision, int), "Mutating payload is missing dashboard_revision")
    require(created_revision > initial_revision, "dashboard_revision did not advance after create_visual")
    require(
        tools.realtime_state().get("dashboard_revision") == created_revision,
        "Realtime state revision does not match create_visual payload",
    )

    updated = tools.execute_tool(
        "update_visual",
        {
            "view_id": item["id"],
            "title": "Low score by order volume (verified)",
        },
    )
    require(updated.get("success") is True, f"Revision update failed: {updated}")
    updated_revision = updated["payload"].get("dashboard_revision")
    require(isinstance(updated_revision, int), "Updated payload is missing dashboard_revision")
    require(updated_revision > created_revision, "dashboard_revision is not monotonic")
    require(
        tools.realtime_state().get("dashboard_revision") == updated_revision,
        "Realtime state revision does not match update_visual payload",
    )
    return {
        "view_id": item["id"],
        "order_values": order_contract["values"],
        "dashboard_revision": updated_revision,
    }


def validate_task_a() -> dict[str, Any]:
    tools.init_views()
    result = tools.execute_tool(
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
            "customer_state": "SP",
            "start_date": "2017-10-01",
            "end_date": "2018-05-31",
        },
    )
    require(result.get("success") is True, f"Task A failed: {result}")
    payload = result["payload"]
    require(len(payload["view_ids"]) == 4, "Task A should create four views")
    require(len(payload["top_categories"]) == 5, "Task A should use five categories")
    require(len(payload["evidence"]) == 5, "Task A should return five evidence rows")
    require(payload["scope_applied"] is True, "Task A scope was not applied atomically")
    require(payload["filtered_rows"] > 0, "Task A scope is empty")
    require(payload["active_filters"] == _expected_scope("SP"), "Task A scope is wrong")

    expected_categories = {item["product_category"] for item in payload["top_categories"]}
    expected_metrics = {"order_count", "low_score_ratio", "delivery_days", "late_ratio"}
    for view_id in payload["view_ids"]:
        item = view(view_id)
        require(item["chart_type"] == "line", f"{view_id} is not a line chart")
        require(item["x_field"] == "order_week", f"{view_id} is not weekly")
        require(item["color"] == "product_category", f"{view_id} is not multi-series")
        require(set(item["comparison_categories"]) == expected_categories, "Views use different category sets")
        require(
            all(_week_in_task_range(row["order_week"]) for row in item["data"]),
            f"{view_id} contains out-of-scope points",
        )

    for row in payload["evidence"]:
        require(set(row["metrics"]) == expected_metrics, f"Incomplete Task A evidence: {row}")
        for metric in expected_metrics:
            require(row["metrics"][metric]["focus_week"] == "2017-W48", "Missing focus week")
            require(row["metrics"][metric]["peak_week"] is not None, "Missing peak week")
            peak_week = row["metrics"][metric]["peak_week"]
            require(
                _week_in_task_range(peak_week),
                f"Task A evidence escaped the requested scope: {peak_week}",
            )

    return {
        "active_filters": payload["active_filters"],
        "view_ids": payload["view_ids"],
        "top_categories": payload["top_categories"],
    }


def validate_task_b() -> dict[str, Any]:
    tools.init_views()
    result = tools.execute_tool(
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
            "customer_state": "RJ",
            "start_date": "2017-10-01",
            "end_date": "2018-05-31",
        },
    )
    require(result.get("success") is True, f"Task B failed: {result}")
    payload = result["payload"]
    require(len(payload["view_ids"]) == 4, "Task B should create four views")
    require(len(payload["top_categories"]) == 15, "Task B should use fifteen categories")
    require(len(payload["evidence"]) == 15, "Task B should return fifteen evidence rows")
    require(payload["scope_applied"] is True, "Task B scope was not applied atomically")
    require(payload["filtered_rows"] > 0, "Task B scope is empty")
    require(payload["active_filters"] == _expected_scope("RJ"), "Task B scope is wrong")

    categories = {item["product_category"] for item in payload["top_categories"]}
    require("office_furniture" in categories, "office_furniture is outside RJ Top 15")
    office = next(item for item in payload["evidence"] if item["product_category"] == "office_furniture")
    for metric in ("low_score_ratio", "delivery_days", "product_revenue", "order_count"):
        require(metric in office, f"office_furniture evidence is missing {metric}")
    validate_office_semantics(office)

    expected_order = [item["product_category"] for item in payload["top_categories"]]
    for view_id in payload["view_ids"]:
        order_contract = view(view_id).get("order_contract") or {}
        require(
            order_contract.get("values") == expected_order,
            f"{view_id} does not preserve the shared revenue order",
        )
    expected_metrics = {"low_score_ratio", "delivery_days", "product_revenue", "order_count"}
    for row in payload["evidence"]:
        require(
            set(row.get("metric_ranks") or {}) == expected_metrics,
            f"Task B evidence has incomplete metric ranks: {row}",
        )

    refreshed = tools.execute_tool(
        "update_analysis_scope",
        {
            "operation": "add",
            "filters": [
                {"field": "review_score", "operator": "gte", "value": 1},
            ],
        },
    )
    require(refreshed.get("success") is True, "Comparison refresh after scope change failed")
    for view_id in payload["view_ids"]:
        require(view(view_id).get("managed_comparison") is True, "Managed comparison was lost")

    return {
        "active_filters": payload["active_filters"],
        "view_ids": payload["view_ids"],
        "office_furniture": office,
    }


def validate_preserved_comparison_scope() -> dict[str, Any]:
    tools.init_views()
    first = tools.execute_tool(
        "compare_category_metrics",
        {
            "mode": "category_summary",
            "top_n": 3,
            "rank_by": "product_revenue",
            "metrics": ["product_revenue"],
            "title_prefix": "SP",
            "customer_state": "SP",
            "start_date": "2017-10-01",
            "end_date": "2018-05-31",
        },
    )
    require(first.get("success") is True, f"Unable to create SP comparison: {first}")
    first_id = first["payload"]["view_ids"][0]
    first_categories = list(view(first_id)["comparison_categories"])

    second = tools.execute_tool(
        "compare_category_metrics",
        {
            "mode": "category_summary",
            "top_n": 3,
            "rank_by": "product_revenue",
            "metrics": ["product_revenue"],
            "title_prefix": "RJ",
            "replace_previous": False,
            "customer_state": "RJ",
            "start_date": "2017-10-01",
            "end_date": "2018-05-31",
        },
    )
    require(second.get("success") is True, f"Unable to create RJ comparison: {second}")
    preserved = view(first_id)
    require(
        preserved["comparison_categories"] == first_categories,
        "Retained SP comparison was rewritten with the RJ scope",
    )
    require(
        preserved["inherit_global_filters"] is False,
        "Retained comparison did not freeze its original scope",
    )
    require(
        preserved["local_filters"][:2] == _expected_scope("SP"),
        "Retained comparison lost its original scope filters",
    )
    return {
        "preserved_view": first_id,
        "preserved_categories": first_categories,
        "new_view": second["payload"]["view_ids"][0],
    }


def _week_in_task_range(value: str) -> bool:
    if value.startswith("2017-W"):
        return int(value[-2:]) >= 39
    if value.startswith("2018-W"):
        return int(value[-2:]) <= 22
    return False


def _expected_scope(state: str) -> list[dict[str, Any]]:
    return [
        {"field": "customer_state", "operator": "eq", "value": state},
        {
            "field": "order_date",
            "operator": "between",
            "value": ["2017-10-01", "2018-05-31"],
        },
    ]


def validate_office_semantics(office: dict[str, Any]) -> None:
    filters = [
        *tools.active_filters,
        {"field": "product_category", "operator": "eq", "value": "office_furniture"},
    ]
    where = build_where(filters, table="fact_item")
    connection = get_connection()
    expected_revenue = connection.execute(
        f"SELECT ROUND(SUM(price), 2) FROM fact_item WHERE {where}"
    ).fetchone()[0]
    expected_delivery = connection.execute(
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
    require(abs(float(office["product_revenue"]) - float(expected_revenue)) < 0.01, "Product revenue includes freight or wrong rows")
    require(abs(float(office["delivery_days"]) - float(expected_delivery)) < 0.01, "Delivery time is not order-category grain")


def main() -> None:
    initialize_db()
    results = {
        "tool_surface": validate_tool_surface(),
        "general_tools": validate_general_tools(),
        "scope_argument_recovery": validate_scope_argument_recovery(),
        "normalized_rating_chart": validate_normalized_rating_chart(),
        "verified_order_and_revision": validate_verified_order_and_revision(),
        "task_a": validate_task_a(),
        "task_b": validate_task_b(),
        "preserved_comparison_scope": validate_preserved_comparison_scope(),
    }
    print("VerbalVis validation: PASS")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
