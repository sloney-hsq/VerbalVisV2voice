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
    if normalized.startswith(("select ", "with ")) or _contains_phrase(normalized, "sql"):
        return Route.SQL
    if _contains_any(normalized, ("audit", "data quality", "quality check", "validate data")):
        return Route.AUDIT
    if _contains_any(normalized, ("search", "runbook", "documentation", "knowledge base", "guide")):
        return Route.KNOWLEDGE
    if _contains_any(normalized, ("plan", "roadmap", "steps to", "migration")):
        return Route.PLAN
    return Route.LOOKUP


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))
