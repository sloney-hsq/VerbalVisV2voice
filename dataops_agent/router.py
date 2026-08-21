"""Deterministic routing for the narrow DataOps request surface."""

from __future__ import annotations

from enum import StrEnum
import re


class Route(StrEnum):
    LOOKUP = "lookup"
    SQL = "sql"
    KNOWLEDGE = "knowledge"
    AUDIT = "audit"
    PLAN = "plan"


def route_request(text: str) -> Route:
    """Select the least-surprising handler for a user request."""
    normalized = " ".join(text.casefold().split())
    if _contains_any(
        normalized,
        (
            "plan",
            "roadmap",
            "steps to",
            "step by step",
            "multiple steps",
            "and then",
            "workflow",
            "migration",
        ),
    ) or re.search(r"\bfirst\b.+\bthen\b", normalized):
        return Route.PLAN
    if normalized.startswith(("select ", "with ")) or _contains_phrase(normalized, "sql") or _contains_any(
        normalized,
        (
            "count",
            "how many",
            "sum",
            "average",
            "minimum",
            "maximum",
            "group by",
            "grouped by",
            "rows where",
            "records where",
            "show records",
            "list records",
            "find rows",
        ),
    ):
        return Route.SQL
    if _contains_any(
        normalized,
        (
            "audit",
            "data quality",
            "quality check",
            "validate data",
            "inspect batch",
            "inspect the batch",
            "check batch",
            "batch inspection",
            "batch anomalies",
        ),
    ):
        return Route.AUDIT
    if _contains_any(
        normalized,
        (
            "search",
            "runbook",
            "documentation",
            "knowledge base",
            "guide",
            "definition",
            "define",
            "what is",
            "history",
            "historical context",
        ),
    ):
        return Route.KNOWLEDGE
    return Route.LOOKUP


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))
