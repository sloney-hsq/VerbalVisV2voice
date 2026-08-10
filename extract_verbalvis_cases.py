#!/usr/bin/env python3
"""Export the two Olist evidence datasets used by the VerbalVis case studies.

The script reads only the six standard Olist CSV files supplied through
``--data-dir`` and writes seven CSV files to ``--output-dir``.  It never reads
or modifies the paper, TeX sources, or application database.

Definitions
-----------
* Time-window filtering and ISO-week assignment use ``order_purchase_timestamp``.
* Revenue: sum of ``price`` only; ``freight_value`` is excluded.
* Order count: distinct ``order_id`` in a product category.
* Low score: an order with at least one review whose ``review_score <= 2``.
* Low-score ratio: low-score orders / orders having a numeric review score.
* Delivery time: delivered-customer timestamp - purchase timestamp, in days.
* Late order: delivered-customer timestamp later than estimated-delivery
  timestamp.

``case2_candidate_ranking.csv`` is a transparent convenience ranking for
inspection, not a business recommendation: it takes the equal-weight mean of
the available descending ranks for revenue, order volume, low-score ratio,
delivery time, and lateness ratio within the RJ revenue Top 15.  Lower scores
indicate higher combined scale/risk attention.

An order that contains multiple items from the same category is first reduced
to one ``order_id × product_category`` row.  Consequently, duplicate items do
not inflate order, review, delivery, or lateness counts.  If Olist contains
multiple review rows for one order, the order is counted once; it is low-score
if any numeric review score is at most two.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional


REQUIRED_FILES = (
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "product_category_name_translation.csv",
)

CASE1_START = date(2017, 10, 1)
CASE1_END = date(2018, 3, 31)
CASE2_START = date(2017, 10, 1)
CASE2_END = date(2018, 5, 31)
CASE1_TARGET_WEEK = (2017, 48)
OFFICE_FURNITURE = "office_furniture"

CASE1_WEEKLY_FIELDS = [
    "product_category",
    "iso_year",
    "iso_week",
    "iso_week_label",
    "order_count",
    "low_score_order_count",
    "scored_order_count",
    "low_score_ratio",
    "avg_delivery_days",
    "valid_delivery_order_count",
    "late_order_count",
    "lateness_eligible_order_count",
    "late_order_ratio",
]

CASE1_METRICS = (
    "order_count",
    "low_score_ratio",
    "avg_delivery_days",
    "late_order_ratio",
)


class InputDataError(Exception):
    """Raised when a required input file or column is unavailable."""


@dataclass(frozen=True)
class OrderInfo:
    order_id: str
    purchase_at: datetime
    delivered_at: Optional[datetime]
    estimated_at: Optional[datetime]
    has_score: bool
    has_low_score: bool


@dataclass(frozen=True)
class OrderCategory:
    order_id: str
    product_category: str
    revenue: float
    purchase_at: datetime
    delivered_at: Optional[datetime]
    estimated_at: Optional[datetime]
    has_score: bool
    has_low_score: bool


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an Olist timestamp, returning None for empty values."""
    if not value or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise InputDataError(f"Invalid timestamp: {value!r}") from exc


def parse_number(value: Optional[str]) -> Optional[float]:
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise InputDataError(f"Invalid numeric value: {value!r}") from exc


def read_rows(path: Path, required_columns: Iterable[str]) -> Iterable[dict[str, str]]:
    """Yield CSV rows after checking that the expected headers exist."""
    try:
        handle = path.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InputDataError(f"Required input file not found: {path}") from exc

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise InputDataError(f"Input file has no header row: {path}")
        missing = set(required_columns).difference(reader.fieldnames)
        if missing:
            raise InputDataError(
                f"Input file {path.name} is missing column(s): {', '.join(sorted(missing))}"
            )
        yield from reader


def validate_data_dir(data_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (data_dir / name).is_file()]
    if missing:
        raise InputDataError(
            "Missing required Olist CSV file(s) in --data-dir: " + ", ".join(missing)
        )


def load_customer_states(data_dir: Path) -> dict[str, str]:
    return {
        row["customer_id"]: row["customer_state"].strip()
        for row in read_rows(
            data_dir / "olist_customers_dataset.csv",
            ("customer_id", "customer_state"),
        )
        if row["customer_id"]
    }


def load_product_categories(data_dir: Path) -> dict[str, str]:
    translations = {
        row["product_category_name"].strip(): row["product_category_name_english"].strip()
        for row in read_rows(
            data_dir / "product_category_name_translation.csv",
            ("product_category_name", "product_category_name_english"),
        )
        if row["product_category_name"] and row["product_category_name_english"]
    }
    categories: dict[str, str] = {}
    for row in read_rows(
        data_dir / "olist_products_dataset.csv",
        ("product_id", "product_category_name"),
    ):
        product_id = row["product_id"]
        original_category = (row["product_category_name"] or "").strip()
        if product_id:
            categories[product_id] = translations.get(original_category, original_category or "unclassified")
    return categories


def load_case_orders(
    data_dir: Path,
    state: str,
    start: date,
    end: date,
) -> dict[str, dict[str, Any]]:
    customer_states = load_customer_states(data_dir)
    selected: dict[str, dict[str, Any]] = {}
    for row in read_rows(
        data_dir / "olist_orders_dataset.csv",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
    ):
        if row["order_status"].strip() != "delivered":
            continue
        if customer_states.get(row["customer_id"]) != state:
            continue
        purchase_at = parse_timestamp(row["order_purchase_timestamp"])
        if purchase_at is None or not start <= purchase_at.date() <= end:
            continue
        selected[row["order_id"]] = {
            "purchase_at": purchase_at,
            "delivered_at": parse_timestamp(row["order_delivered_customer_date"]),
            "estimated_at": parse_timestamp(row["order_estimated_delivery_date"]),
        }
    return selected


def add_review_flags(data_dir: Path, selected_orders: dict[str, dict[str, Any]]) -> None:
    review_flags = {order_id: [False, False] for order_id in selected_orders}
    for row in read_rows(
        data_dir / "olist_order_reviews_dataset.csv",
        ("order_id", "review_score"),
    ):
        flags = review_flags.get(row["order_id"])
        if flags is None:
            continue
        score = parse_number(row["review_score"])
        if score is not None:
            flags[0] = True
            if score <= 2:
                flags[1] = True
    for order_id, flags in review_flags.items():
        selected_orders[order_id]["has_score"] = flags[0]
        selected_orders[order_id]["has_low_score"] = flags[1]


def build_order_categories(
    data_dir: Path,
    selected_orders: dict[str, dict[str, Any]],
) -> list[OrderCategory]:
    product_categories = load_product_categories(data_dir)
    revenue_by_order_category: dict[tuple[str, str], float] = defaultdict(float)
    for row in read_rows(
        data_dir / "olist_order_items_dataset.csv",
        ("order_id", "product_id", "price"),
    ):
        order_id = row["order_id"]
        if order_id not in selected_orders:
            continue
        price = parse_number(row["price"])
        if price is None:
            continue
        category = product_categories.get(row["product_id"], "unclassified")
        revenue_by_order_category[(order_id, category)] += price

    records: list[OrderCategory] = []
    for (order_id, category), revenue in revenue_by_order_category.items():
        order = selected_orders[order_id]
        records.append(
            OrderCategory(
                order_id=order_id,
                product_category=category,
                revenue=revenue,
                purchase_at=order["purchase_at"],
                delivered_at=order["delivered_at"],
                estimated_at=order["estimated_at"],
                has_score=order.get("has_score", False),
                has_low_score=order.get("has_low_score", False),
            )
        )
    return records


def load_case_records(
    data_dir: Path,
    state: str,
    start: date,
    end: date,
) -> list[OrderCategory]:
    orders = load_case_orders(data_dir, state, start, end)
    add_review_flags(data_dir, orders)
    return build_order_categories(data_dir, orders)


def ratio(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def aggregate_category(records: Iterable[OrderCategory]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for record in records:
        metrics = aggregated.setdefault(
            record.product_category,
            {
                "total_revenue": 0.0,
                "order_ids": set(),
                "low_score_order_count": 0,
                "scored_order_count": 0,
                "delivery_days": [],
                "valid_delivery_order_count": 0,
                "late_order_count": 0,
                "lateness_eligible_order_count": 0,
            },
        )
        metrics["total_revenue"] += record.revenue
        metrics["order_ids"].add(record.order_id)
        metrics["low_score_order_count"] += int(record.has_low_score)
        metrics["scored_order_count"] += int(record.has_score)
        if record.delivered_at is not None:
            metrics["delivery_days"].append(
                (record.delivered_at - record.purchase_at).total_seconds() / 86400
            )
            metrics["valid_delivery_order_count"] += 1
        if record.delivered_at is not None and record.estimated_at is not None:
            metrics["lateness_eligible_order_count"] += 1
            metrics["late_order_count"] += int(record.delivered_at > record.estimated_at)

    for metrics in aggregated.values():
        metrics["order_count"] = len(metrics.pop("order_ids"))
        delivery_days = metrics.pop("delivery_days")
        metrics["avg_delivery_days"] = (
            sum(delivery_days) / len(delivery_days) if delivery_days else None
        )
        metrics["low_score_ratio"] = ratio(
            metrics["low_score_order_count"], metrics["scored_order_count"]
        )
        metrics["late_order_ratio"] = ratio(
            metrics["late_order_count"], metrics["lateness_eligible_order_count"]
        )
        metrics["avg_product_revenue_per_order"] = (
            metrics["total_revenue"] / metrics["order_count"] if metrics["order_count"] else None
        )
    return aggregated


def top_categories(records: Iterable[OrderCategory], limit: int) -> list[str]:
    aggregated = aggregate_category(records)
    ordered = sorted(
        aggregated.items(),
        key=lambda item: (-item[1]["total_revenue"], -item[1]["order_count"], item[0]),
    )
    return [category for category, _ in ordered[:limit]]


def iso_weeks_intersecting(start: date, end: date) -> Iterable[tuple[int, int, str]]:
    """Yield every ISO week that has at least one date in the given range."""
    week_start = start - timedelta(days=start.weekday())
    final_week_start = end - timedelta(days=end.weekday())
    while week_start <= final_week_start:
        iso = week_start.isocalendar()
        yield iso.year, iso.week, f"{iso.year}-W{iso.week:02d}"
        week_start += timedelta(days=7)


def empty_weekly_metrics() -> dict[str, Any]:
    return {
        "order_count": 0,
        "low_score_order_count": 0,
        "scored_order_count": 0,
        "low_score_ratio": None,
        "avg_delivery_days": None,
        "valid_delivery_order_count": 0,
        "late_order_count": 0,
        "lateness_eligible_order_count": 0,
        "late_order_ratio": None,
    }


def aggregate_weekly(
    records: Iterable[OrderCategory],
    categories: Iterable[str],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, int], list[OrderCategory]] = defaultdict(list)
    for record in records:
        iso = record.purchase_at.isocalendar()
        groups[(record.product_category, iso.year, iso.week)].append(record)

    output: list[dict[str, Any]] = []
    for category in categories:
        for iso_year, iso_week, iso_week_label in iso_weeks_intersecting(start, end):
            group_records = groups.get((category, iso_year, iso_week))
            metrics = (
                aggregate_category(group_records)[category]
                if group_records
                else empty_weekly_metrics()
            )
            output.append(
                {
                    "product_category": category,
                    "iso_year": iso_year,
                    "iso_week": iso_week,
                    "iso_week_label": iso_week_label,
                    **{field: metrics[field] for field in CASE1_WEEKLY_FIELDS if field in metrics},
                }
            )
    return sorted(output, key=lambda row: (row["product_category"], row["iso_year"], row["iso_week"]))


def descending_ranks(rows: list[dict[str, Any]], field: str) -> dict[tuple[str, int, int], Optional[int]]:
    """Return competition ranks (1, 2, 2, 4) within each category."""
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row[field] is not None:
            by_category[row["product_category"]].append(row)

    ranks: dict[tuple[str, int, int], Optional[int]] = {}
    for category_rows in by_category.values():
        ordered = sorted(
            category_rows,
            key=lambda row: (-row[field], row["iso_year"], row["iso_week"]),
        )
        previous_value: Optional[float] = None
        current_rank = 0
        for index, row in enumerate(ordered, start=1):
            if previous_value is None or row[field] != previous_value:
                current_rank = index
                previous_value = row[field]
            ranks[(row["product_category"], row["iso_year"], row["iso_week"])] = current_rank
    return ranks


def case1_peak_outputs(
    categories: list[str],
    weekly_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    peak_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    target_year, target_week = CASE1_TARGET_WEEK
    weekly_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in weekly_rows:
        weekly_by_category[row["product_category"]].append(row)

    for metric in CASE1_METRICS:
        ranks = descending_ranks(weekly_rows, metric)
        for category in categories:
            category_rows = weekly_by_category[category]
            valid_rows = [row for row in category_rows if row[metric] is not None]
            peak_value = max((row[metric] for row in valid_rows), default=None)
            tied_peaks = [row for row in valid_rows if row[metric] == peak_value]
            peak = tied_peaks[0] if tied_peaks else None
            peak_iso_weeks = "|".join(row["iso_week_label"] for row in tied_peaks)
            if peak is not None:
                peak_rows.append(
                    {
                        "product_category": category,
                        "metric": metric,
                        "peak_iso_year": peak["iso_year"],
                        "peak_iso_week_number": peak["iso_week"],
                        "peak_iso_week": peak["iso_week_label"],
                        "peak_value": peak[metric],
                        "peak_week_count": len(tied_peaks),
                        "peak_iso_weeks": peak_iso_weeks,
                    }
                )

            target = next(
                (
                    row
                    for row in category_rows
                    if row["iso_year"] == target_year and row["iso_week"] == target_week
                ),
                None,
            )
            target_value = target[metric] if target is not None else None
            target_rank = (
                ranks.get((category, target_year, target_week)) if target is not None else None
            )
            comparison_rows.append(
                {
                    "product_category": category,
                    "metric": metric,
                    "week48_value": target_value,
                    "week48_rank": target_rank,
                    "peak_iso_year": peak["iso_year"] if peak else None,
                    "peak_iso_week_number": peak["iso_week"] if peak else None,
                    "peak_iso_week": peak["iso_week_label"] if peak else None,
                    "peak_value": peak[metric] if peak else None,
                    "peak_week_count": len(tied_peaks) if peak else None,
                    "peak_iso_weeks": peak_iso_weeks if peak else None,
                    "week48_minus_peak": (
                        target_value - peak[metric]
                        if target_value is not None and peak is not None
                        else None
                    ),
                }
            )
    return peak_rows, comparison_rows


def rank_categories(metrics: dict[str, dict[str, Any]], field: str) -> dict[str, Optional[int]]:
    """Rank categories descending, leaving unavailable ratios/times unranked."""
    ordered = sorted(
        (
            (category, values[field])
            for category, values in metrics.items()
            if values[field] is not None
        ),
        key=lambda item: (-item[1], item[0]),
    )
    ranks: dict[str, Optional[int]] = {category: None for category in metrics}
    previous_value: Optional[float] = None
    current_rank = 0
    for index, (category, value) in enumerate(ordered, start=1):
        if previous_value is None or value != previous_value:
            current_rank = index
            previous_value = value
        ranks[category] = current_rank
    return ranks


def case2_outputs(records: list[OrderCategory]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    categories = top_categories(records, 15)
    all_metrics_by_category = aggregate_category(records)
    metrics_by_category = {
        category: all_metrics_by_category[category]
        for category in categories
    }
    rank_fields = (
        "total_revenue",
        "order_count",
        "low_score_ratio",
        "avg_delivery_days",
        "late_order_ratio",
    )
    ranks = {field: rank_categories(metrics_by_category, field) for field in rank_fields}

    metrics_rows: list[dict[str, Any]] = []
    for category in categories:
        values = metrics_by_category[category]
        metrics_rows.append(
            {
                "product_category": category,
                "total_revenue": values["total_revenue"],
                "revenue_rank": ranks["total_revenue"][category],
                "order_count": values["order_count"],
                "order_count_rank": ranks["order_count"][category],
                "low_score_order_count": values["low_score_order_count"],
                "scored_order_count": values["scored_order_count"],
                "low_score_ratio": values["low_score_ratio"],
                "low_score_ratio_rank": ranks["low_score_ratio"][category],
                "avg_delivery_days": values["avg_delivery_days"],
                "avg_delivery_days_rank": ranks["avg_delivery_days"][category],
                "valid_delivery_order_count": values["valid_delivery_order_count"],
                "late_order_count": values["late_order_count"],
                "lateness_eligible_order_count": values["lateness_eligible_order_count"],
                "late_order_ratio": values["late_order_ratio"],
                "late_order_ratio_rank": ranks["late_order_ratio"][category],
                "avg_product_revenue_per_order": values["avg_product_revenue_per_order"],
            }
        )

    # The requested Top 15 are ranked within their own set.  The comparison
    # baseline is nevertheless calculated from all RJ records, so the output
    # remains useful when office_furniture itself falls just outside the Top 15.
    office = all_metrics_by_category.get(OFFICE_FURNITURE)
    office_in_top15 = OFFICE_FURNITURE in metrics_by_category
    comparison_rows: list[dict[str, Any]] = []
    for row in metrics_rows:
        category = row["product_category"]
        comparison_rows.append(
            {
                "product_category": category,
                "office_furniture_in_top15": office_in_top15,
                "office_furniture_present_in_rj_data": office is not None,
                "revenue_difference_vs_office_furniture": (
                    row["total_revenue"] - office["total_revenue"] if office else None
                ),
                "order_count_difference_vs_office_furniture": (
                    row["order_count"] - office["order_count"] if office else None
                ),
                "low_score_ratio_difference_vs_office_furniture": difference(
                    row["low_score_ratio"], office["low_score_ratio"] if office else None
                ),
                "avg_delivery_days_difference_vs_office_furniture": difference(
                    row["avg_delivery_days"], office["avg_delivery_days"] if office else None
                ),
                "late_order_ratio_difference_vs_office_furniture": difference(
                    row["late_order_ratio"], office["late_order_ratio"] if office else None
                ),
                "avg_product_revenue_per_order_difference_vs_office_furniture": difference(
                    row["avg_product_revenue_per_order"],
                    office["avg_product_revenue_per_order"] if office else None,
                ),
            }
        )

    candidate_rows: list[dict[str, Any]] = []
    candidate_rank_fields = (
        "revenue_rank",
        "order_count_rank",
        "low_score_ratio_rank",
        "avg_delivery_days_rank",
        "late_order_ratio_rank",
    )
    for row in metrics_rows:
        available_ranks = [row[field] for field in candidate_rank_fields if row[field] is not None]
        attention_score = sum(available_ranks) / len(available_ranks) if available_ranks else None
        candidate_rows.append(
            {
                "product_category": row["product_category"],
                "resource_attention_score": attention_score,
                "available_metric_rank_count": len(available_ranks),
                **{field: row[field] for field in candidate_rank_fields},
            }
        )
    ordered_candidates = sorted(
        candidate_rows,
        key=lambda row: (
            row["resource_attention_score"] is None,
            row["resource_attention_score"] if row["resource_attention_score"] is not None else math.inf,
            row["product_category"],
        ),
    )
    previous_score: Optional[float] = None
    current_rank = 0
    for index, row in enumerate(ordered_candidates, start=1):
        if previous_score is None or row["resource_attention_score"] != previous_score:
            current_rank = index
            previous_score = row["resource_attention_score"]
        row["resource_attention_rank"] = current_rank if row["resource_attention_score"] is not None else None
    for row in ordered_candidates:
        row["ranking_method"] = "equal_weight_mean_of_available_metric_ranks"
    return metrics_rows, comparison_rows, ordered_candidates


def difference(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    return value - baseline if value is not None and baseline is not None else None


MONEY_FIELDS = {
    "total_revenue",
    "revenue_difference_vs_office_furniture",
}
SIX_DECIMAL_FIELDS = {
    "low_score_ratio",
    "avg_delivery_days",
    "late_order_ratio",
    "week48_value",
    "peak_value",
    "week48_minus_peak",
    "avg_product_revenue_per_order",
    "low_score_ratio_difference_vs_office_furniture",
    "avg_delivery_days_difference_vs_office_furniture",
    "late_order_ratio_difference_vs_office_furniture",
    "avg_product_revenue_per_order_difference_vs_office_furniture",
    "resource_attention_score",
}


def format_value(field: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if field in MONEY_FIELDS:
        return f"{value:.2f}"
    if field in SIX_DECIMAL_FIELDS:
        return f"{value:.6f}"
    return str(value)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_value(field, row.get(field)) for field in fieldnames})


def export_cases(data_dir: Path, output_dir: Path) -> None:
    validate_data_dir(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    case1_records = load_case_records(data_dir, "SP", CASE1_START, CASE1_END)
    case1_categories = top_categories(case1_records, 5)
    case1_top_metrics = aggregate_category(case1_records)
    case1_top_rows = [
        {
            "revenue_rank": index,
            "product_category": category,
            "total_revenue": case1_top_metrics[category]["total_revenue"],
            "order_count": case1_top_metrics[category]["order_count"],
        }
        for index, category in enumerate(case1_categories, start=1)
    ]
    case1_selected = [
        record for record in case1_records if record.product_category in set(case1_categories)
    ]
    case1_weekly = aggregate_weekly(case1_selected, case1_categories, CASE1_START, CASE1_END)
    case1_peaks, case1_comparison = case1_peak_outputs(case1_categories, case1_weekly)

    write_csv(
        output_dir / "case1_sp_top5_categories.csv",
        ["revenue_rank", "product_category", "total_revenue", "order_count"],
        case1_top_rows,
    )
    write_csv(output_dir / "case1_sp_weekly_metrics.csv", CASE1_WEEKLY_FIELDS, case1_weekly)
    write_csv(
        output_dir / "case1_sp_peak_weeks.csv",
        [
            "product_category",
            "metric",
            "peak_iso_year",
            "peak_iso_week_number",
            "peak_iso_week",
            "peak_value",
            "peak_week_count",
            "peak_iso_weeks",
        ],
        case1_peaks,
    )
    write_csv(
        output_dir / "case1_sp_week48_comparison.csv",
        [
            "product_category",
            "metric",
            "week48_value",
            "week48_rank",
            "peak_iso_year",
            "peak_iso_week_number",
            "peak_iso_week",
            "peak_value",
            "peak_week_count",
            "peak_iso_weeks",
            "week48_minus_peak",
        ],
        case1_comparison,
    )

    case2_records = load_case_records(data_dir, "RJ", CASE2_START, CASE2_END)
    case2_metrics, case2_comparison, case2_candidates = case2_outputs(case2_records)
    write_csv(
        output_dir / "case2_rj_top15_metrics.csv",
        [
            "product_category",
            "total_revenue",
            "revenue_rank",
            "order_count",
            "order_count_rank",
            "low_score_order_count",
            "scored_order_count",
            "low_score_ratio",
            "low_score_ratio_rank",
            "avg_delivery_days",
            "avg_delivery_days_rank",
            "valid_delivery_order_count",
            "late_order_count",
            "lateness_eligible_order_count",
            "late_order_ratio",
            "late_order_ratio_rank",
            "avg_product_revenue_per_order",
        ],
        case2_metrics,
    )
    write_csv(
        output_dir / "case2_office_furniture_comparison.csv",
        [
            "product_category",
            "office_furniture_in_top15",
            "office_furniture_present_in_rj_data",
            "revenue_difference_vs_office_furniture",
            "order_count_difference_vs_office_furniture",
            "low_score_ratio_difference_vs_office_furniture",
            "avg_delivery_days_difference_vs_office_furniture",
            "late_order_ratio_difference_vs_office_furniture",
            "avg_product_revenue_per_order_difference_vs_office_furniture",
        ],
        case2_comparison,
    )
    write_csv(
        output_dir / "case2_candidate_ranking.csv",
        [
            "resource_attention_rank",
            "product_category",
            "resource_attention_score",
            "available_metric_rank_count",
            "revenue_rank",
            "order_count_rank",
            "low_score_ratio_rank",
            "avg_delivery_days_rank",
            "late_order_ratio_rank",
            "ranking_method",
        ],
        case2_candidates,
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export SP weekly-guarantee and RJ delivery-resource Olist case data."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="Folder containing the six standard Olist CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Folder where the seven case CSV files will be written.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        export_cases(args.data_dir, args.output_dir)
    except InputDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote 7 case-data CSV files to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
