"""Optional Elasticsearch-backed retrieval adapter."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from .models import KnowledgeChunk


_IDENTIFIER_QUERY = re.compile(r"^[A-Za-z0-9]+(?:[-_.:/][A-Za-z0-9]+)+$")

DEFAULT_KNOWLEDGE_INDEX_MAPPING: dict[str, object] = {
    "properties": {
        "content": {"type": "text"},
        "metadata": {
            "properties": {
                "identifier": {"type": "keyword"},
                "identifiers": {"type": "keyword"},
                "aliases": {"type": "keyword"},
            }
        },
    }
}


class ElasticsearchHybridRetriever:
    """Search Elasticsearch only after a client or endpoint is configured."""

    def __init__(
        self,
        *,
        index: str,
        client: Any | None = None,
        url: str | None = None,
        embed_query: Callable[[str], list[float]] | None = None,
        content_field: str = "content",
        metadata_field: str = "metadata",
        vector_field: str = "embedding",
    ) -> None:
        self._index = index
        self._client = client
        self._url = url
        self._embed_query = embed_query
        self._content_field = content_field
        self._metadata_field = metadata_field
        self._vector_field = vector_field

    def search(
        self,
        query: str,
        *,
        filters: Mapping[str, object] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeChunk]:
        """Issue BM25 and optional vector retrieval only when configured."""
        if limit <= 0 or (self._client is None and self._url is None):
            return []
        client = self._client or self._create_client()
        filter_clauses = _elastic_filters(filters or {}, self._metadata_field)
        direct_chunks: list[KnowledgeChunk] = []
        if _looks_like_identifier(query):
            direct_response = client.search(
                index=self._index,
                size=limit,
                query=_identifier_lookup_query(query, filter_clauses, self._metadata_field),
            )
            direct_chunks = _filter_chunks(
                _chunks_from_response(direct_response, self._content_field, self._metadata_field),
                filters or {},
            )
            direct_chunks = _sort_exact_chunks(query, direct_chunks)
        lexical_query = {
            "bool": {
                "must": [{"match": {self._content_field: query}}],
                "filter": filter_clauses,
            }
        }
        request: dict[str, object] = {
            "index": self._index,
            "size": limit,
        }
        if self._embed_query is not None:
            rank_window_size = max(limit * 4, 10)
            request["retriever"] = {
                "rrf": {
                    "retrievers": [
                        {"standard": {"query": lexical_query}},
                        {
                            "knn": {
                                "field": self._vector_field,
                                "query_vector": self._embed_query(query),
                                "k": rank_window_size,
                                "num_candidates": rank_window_size * 4,
                                "filter": filter_clauses,
                            }
                        },
                    ],
                    "rank_constant": 60,
                    "rank_window_size": rank_window_size,
                }
            }
        else:
            request["query"] = lexical_query
        response = client.search(**request)
        hybrid_chunks = _filter_chunks(
            _chunks_from_response(response, self._content_field, self._metadata_field), filters or {}
        )
        return _deduplicate_chunks([*direct_chunks, *_sort_exact_chunks(query, hybrid_chunks)])[:limit]

    def _create_client(self) -> Any:
        try:
            from elasticsearch import Elasticsearch
        except ImportError as error:
            raise RuntimeError(
                "Elasticsearch is configured but its optional client is not installed"
            ) from error
        return Elasticsearch(self._url)


def _elastic_filters(filters: Mapping[str, object], metadata_field: str) -> list[dict[str, object]]:
    return [
        {"term": {f"{metadata_field}.{key}": value}}
        for key, value in filters.items()
    ]


def _identifier_lookup_query(
    query: str, filters: list[dict[str, object]], metadata_field: str
) -> dict[str, object]:
    return {
        "bool": {
            "should": [
                {"term": {"_id": query}},
                {"term": {f"{metadata_field}.identifier": query}},
                {"term": {f"{metadata_field}.identifiers": query}},
                {"term": {f"{metadata_field}.aliases": query}},
            ],
            "minimum_should_match": 1,
            "filter": filters,
        }
    }


def _chunks_from_response(
    response: Mapping[str, object], content_field: str, metadata_field: str
) -> list[KnowledgeChunk]:
    hits = response.get("hits", {})
    if not isinstance(hits, Mapping):
        return []
    raw_hits = hits.get("hits", [])
    if not isinstance(raw_hits, list):
        return []
    chunks: list[KnowledgeChunk] = []
    for hit in raw_hits:
        if not isinstance(hit, Mapping):
            continue
        source = hit.get("_source", {})
        if not isinstance(source, Mapping):
            continue
        identifier = str(hit.get("_id", source.get("id", "")))
        content = source.get(content_field, "")
        metadata = source.get(metadata_field, {})
        if identifier and isinstance(content, str) and isinstance(metadata, Mapping):
            chunks.append(KnowledgeChunk(identifier, content, dict(metadata)))
    return chunks


def _sort_exact_chunks(query: str, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    expected = query.strip().casefold()
    if not expected:
        return chunks
    return sorted(chunks, key=lambda chunk: (_exact_match_priority(expected, chunk), chunk.id))


def _exact_match_priority(expected: str, chunk: KnowledgeChunk) -> int:
    if chunk.id.casefold() == expected:
        return 0
    if _metadata_value_matches(chunk.metadata.get("identifier"), expected):
        return 1
    if _metadata_value_matches(chunk.metadata.get("identifiers"), expected):
        return 2
    if _metadata_value_matches(chunk.metadata.get("aliases"), expected):
        return 3
    return 4


def _metadata_value_matches(value: object, expected: str) -> bool:
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(str(item).casefold() == expected for item in value)
    return value is not None and str(value).casefold() == expected


def _filter_chunks(
    chunks: list[KnowledgeChunk], filters: Mapping[str, object]
) -> list[KnowledgeChunk]:
    return [chunk for chunk in chunks if _matches_metadata_filters(chunk.metadata, filters)]


def _deduplicate_chunks(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    unique: dict[str, KnowledgeChunk] = {}
    for chunk in chunks:
        unique.setdefault(chunk.id, chunk)
    return list(unique.values())


def _matches_metadata_filters(
    metadata: Mapping[str, object], filters: Mapping[str, object]
) -> bool:
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(actual, (list, tuple, set, frozenset)):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def _looks_like_identifier(query: str) -> bool:
    return bool(_IDENTIFIER_QUERY.fullmatch(query.strip()))
