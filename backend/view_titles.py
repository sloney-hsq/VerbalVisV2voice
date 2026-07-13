"""Short English display titles for dashboard views."""

from __future__ import annotations

import re
from typing import Any

MAX_VIEW_TITLE_LENGTH = 40

_METRIC_LABELS = {
    "order_count": "Orders",
    "product_revenue": "Revenue",
    "low_score_ratio": "Low-score Share",
    "delivery_days": "Delivery Days",
    "late_ratio": "Late Share",
    "review_score": "Review Score",
}
_DIMENSION_LABELS = {
    "order_month": "Month",
    "order_week": "Week",
    "order_date": "Date",
    "customer_state": "State",
    "product_category": "Category",
    "review_score": "Review Score",
}
_TIME_LABELS = {
    "order_month": "Monthly",
    "order_week": "Weekly",
    "order_date": "Daily",
}


def short_view_title(
    requested_title: Any,
    *,
    chart_type: str,
    x: str,
    y: str,
    series: str | None = None,
    top_n: int | None = None,
    normalize: bool = False,
    state: str | None = None,
) -> str:
    requested = " ".join(str(requested_title or "").split())
    if _is_short_english(requested):
        return requested

    suffix = _top_suffix(top_n)
    metric = _METRIC_LABELS.get(y, _field_label(y))
    dimension = _DIMENSION_LABELS.get(x, _field_label(x))
    series_label = _DIMENSION_LABELS.get(series or "", _field_label(series or ""))

    if chart_type == "scatter":
        bases = [f"{metric} vs {dimension}"]
    elif chart_type == "line":
        grain = _TIME_LABELS.get(x, dimension)
        if series and not suffix:
            bases = [f"{grain} {metric} by {series_label}", f"{grain} {metric}"]
        else:
            bases = [f"{grain} {metric}"]
    elif normalize and series:
        bases = [f"{series_label} Share by {dimension}", f"Share by {dimension}"]
    else:
        bases = [f"{metric} by {dimension}", f"{metric} Chart"]

    state_prefix = _state_prefix(state)
    candidates = [
        f"{state_prefix}{base}{suffix}".strip()
        for base in bases
    ] + [
        f"{base}{suffix}".strip()
        for base in bases
    ] + [
        f"{state_prefix}{base}".strip()
        for base in bases
    ] + [
        base for base in bases
    ]
    return next(
        (title for title in candidates if _is_short_english(title)),
        "Analytical View",
    )


def _is_short_english(title: str) -> bool:
    return (
        bool(title)
        and len(title) <= MAX_VIEW_TITLE_LENGTH
        and title.isascii()
        and bool(re.search(r"[A-Za-z]", title))
    )


def _top_suffix(value: int | None) -> str:
    try:
        top_n = int(value) if value is not None else 0
    except (TypeError, ValueError):
        top_n = 0
    return f" (Top {top_n})" if top_n > 0 else ""


def _state_prefix(value: str | None) -> str:
    state = str(value or "").strip()
    return f"{state.upper()} " if re.fullmatch(r"[A-Za-z]{2}", state) else ""


def _field_label(value: str) -> str:
    return str(value or "View").replace("_", " ").title()
