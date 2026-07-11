"""Local validation for the two VerbalVis study demos.

Run from backend/ after installing requirements:

    python demo_validation.py

This script does not call Qwen. It validates the database, high-level tool
contracts, generated dashboard views, and evidence payloads used by Task A/B.
"""

from __future__ import annotations

import json
from typing import Any

from db import initialize_db
from demo_tools import execute_demo_tool
import tools

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


def _set_scope(state: str) -> dict[str, Any]:
    result = execute_demo_tool(
        "set_analysis_scope",
        {
            "mode": "replace",
            "filters": [
                {"field": "customer_state", "operator": "eq", "value": state},
                DATE_FILTER,
            ],
        },
    )
    _require(result.get("success") is True, f"Unable to set {state} scope: {result}")
    _require(
        len(result.get("payload", {}).get("active_filters", [])) == 2,
        f"Expected two active filters for {state}",
    )
    _require(
        int(result.get("payload", {}).get("filtered_rows", 0)) > 0,
        f"The {state} study scope is empty",
    )
    return result


def validate_task_a() -> dict[str, Any]:
    tools.init_views()
    scope = _set_scope("SP")
    result = execute_demo_tool(
        "compare_category_metrics",
        {
            "mode": "weekly_trends",
            "top_n": 5,
            "rank_by": "revenue",
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
    _require(len(evidence) == 5, f"Task A should return evidence for five categories")

    expected_metrics = {
        "order_count",
        "low_score_ratio",
        "delivery_days",
        "late_ratio",
    }
    expected_categories = {
        item["product_category"] for item in categories
    }

    for view_id in view_ids:
        view = _view(view_id)
        _require(view.get("chart_type") == "line", f"{view_id} is not a line chart")
        _require(view.get("x_field") == "order_week", f"{view_id} is not weekly")
        _require(
            view.get("color") == "product_category",
            f"{view_id} is not a multi-category series",
        )
        _require(
            set(view.get("comparison_categories", [])) == expected_categories,
            f"{view_id} does not use the common Top-5 category set",
        )

    for item in evidence:
        metrics = item.get("metrics", {})
        _require(set(metrics) == expected_metrics, f"Incomplete Task A evidence: {item}")
        for metric in expected_metrics:
            metric_evidence = metrics[metric]
            _require(
                metric_evidence.get("focus_week") == "2017-W48",
                f"Missing focus week for {item['product_category']} / {metric}",
            )
            _require(
                metric_evidence.get("peak_week") is not None,
                f"Missing peak week for {item['product_category']} / {metric}",
            )

    return {
        "scope_rows": scope["payload"]["filtered_rows"],
        "top_categories": categories,
        "view_ids": view_ids,
        "focus_week": payload.get("focus_week"),
    }


def validate_task_b() -> dict[str, Any]:
    tools.init_views()
    scope = _set_scope("RJ")
    result = execute_demo_tool(
        "compare_category_metrics",
        {
            "mode": "category_summary",
            "top_n": 15,
            "rank_by": "revenue",
            "metrics": [
                "low_score_ratio",
                "delivery_days",
                "revenue",
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
    _require(len(categories) == 15, f"Task B should use fifteen categories")
    _require(len(evidence) == 15, f"Task B should return fifteen comparison rows")

    expected_categories = {
        item["product_category"] for item in categories
    }
    _require(
        "office_furniture" in expected_categories,
        "office_furniture is not in the RJ revenue Top 15 for the study scope",
    )

    expected_metrics = {
        "low_score_ratio",
        "delivery_days",
        "revenue",
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
            f"{view_id} does not use the common Top-15 category set",
        )

    office = next(
        item for item in evidence
        if item.get("product_category") == "office_furniture"
    )
    return {
        "scope_rows": scope["payload"]["filtered_rows"],
        "top_categories": categories,
        "view_ids": view_ids,
        "office_furniture": office,
    }


def main() -> None:
    initialize_db()
    task_a = validate_task_a()
    task_b = validate_task_b()
    print("Task A validation: PASS")
    print(json.dumps(task_a, ensure_ascii=False, indent=2, default=str))
    print("Task B validation: PASS")
    print(json.dumps(task_b, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
