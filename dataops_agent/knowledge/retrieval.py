"""Dependency-free hybrid retrieval primitives."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from .models import KnowledgeChunk


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


@runtime_checkable
class Reranker(Protocol):
    """Ranks a preselected candidate set for one query."""

    def rank(self, query: str, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        """Return the same candidates in descending relevance order."""


def rrf_fuse(rankings: Iterable[Iterable[str]], *, k: int = 60) -> list[str]:
    """Fuse ranked identifiers using deterministic reciprocal-rank fusion."""
    if k < 1:
        raise ValueError("k must be positive")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    seen_count = 0
    for ranking in rankings:
        seen_in_ranking: set[str] = set()
        for identifier in ranking:
            if identifier in seen_in_ranking:
                continue
            seen_in_ranking.add(identifier)
            rank = len(seen_in_ranking)
            if identifier not in first_seen:
                first_seen[identifier] = seen_count
                seen_count += 1
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda identifier: (-scores[identifier], first_seen[identifier]))


class HybridRetriever:
    """An in-memory lexical and metadata-token hybrid retriever."""

    def __init__(
        self,
        chunks: Iterable[KnowledgeChunk],
        *,
        reranker: Reranker | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self._by_id = {chunk.id: chunk for chunk in self._chunks}
        if len(self._by_id) != len(self._chunks):
            raise ValueError("chunk identifiers must be unique")
        self._reranker = reranker

    def search(
        self,
        query: str,
        *,
        filters: Mapping[str, object] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeChunk]:
        """Return filtered chunks, fusing lexical and metadata-aware rankings."""
        if limit <= 0:
            return []
        candidates = [
            chunk
            for chunk in self._chunks
            if _matches_filters(chunk.metadata, filters or {})
        ]
        if not query.strip():
            return candidates[:limit]

        query_tokens = _tokens(query)
        lexical = _rank(candidates, lambda chunk: _overlap(query_tokens, _tokens(chunk.content)))
        metadata = _rank(candidates, lambda chunk: _overlap(query_tokens, _metadata_tokens(chunk)))
        exact_ids = [chunk.id for chunk in candidates if _is_exact_identifier(query, chunk)]
        fused_ids = rrf_fuse([lexical, metadata])
        ordered_ids = _deduplicate([*exact_ids, *fused_ids])
        ordered = [self._by_id[identifier] for identifier in ordered_ids]

        if self._reranker is not None and ordered:
            ranked = self._reranker.rank(query, ordered)
            allowed = {chunk.id for chunk in ordered}
            ranked_ids = [chunk.id for chunk in ranked if chunk.id in allowed]
            ordered = [self._by_id[identifier] for identifier in _deduplicate(ranked_ids)]
            ordered.extend(chunk for chunk in candidates if chunk.id in allowed and chunk not in ordered)

        exact = [chunk for chunk in ordered if _is_exact_identifier(query, chunk)]
        non_exact = [chunk for chunk in ordered if not _is_exact_identifier(query, chunk)]
        return [*exact, *non_exact][:limit]


def _rank(chunks: Sequence[KnowledgeChunk], score_for: object) -> list[str]:
    scorer = score_for  # Keeps the public search flow compact without exposing rankers.
    scored = [
        (index, chunk.id, scorer(chunk))  # type: ignore[operator]
        for index, chunk in enumerate(chunks)
    ]
    return [
        identifier
        for _, identifier, score in sorted(scored, key=lambda item: (-item[2], item[0]))
        if score > 0
    ]


def _matches_filters(metadata: Mapping[str, object], filters: Mapping[str, object]) -> bool:
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(actual, (list, tuple, set, frozenset)):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def _tokens(value: object) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(str(value))}


def _metadata_tokens(chunk: KnowledgeChunk) -> set[str]:
    values: list[object] = []
    for value in chunk.metadata.values():
        if isinstance(value, Mapping):
            values.extend(value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            values.extend(value)
        else:
            values.append(value)
    return _tokens(" ".join(map(str, values)))


def _overlap(query_tokens: set[str], candidate_tokens: set[str]) -> int:
    return len(query_tokens & candidate_tokens)


def _is_exact_identifier(query: str, chunk: KnowledgeChunk) -> bool:
    expected = query.strip().casefold()
    if not expected:
        return False
    identifiers: list[object] = [chunk.id]
    for key in ("identifier", "identifiers"):
        value = chunk.metadata.get(key)
        if isinstance(value, (list, tuple, set, frozenset)):
            identifiers.extend(value)
        elif value is not None:
            identifiers.append(value)
    return any(str(identifier).casefold() == expected for identifier in identifiers)


def _deduplicate(identifiers: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(identifiers))
