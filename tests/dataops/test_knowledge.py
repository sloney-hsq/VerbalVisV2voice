from __future__ import annotations

import importlib

import pytest

from dataops_agent import knowledge
from dataops_agent.knowledge.chunking import chunk_markdown
from dataops_agent.knowledge import DEFAULT_KNOWLEDGE_INDEX_MAPPING
from dataops_agent.knowledge import elastic
from dataops_agent.knowledge.elastic import ElasticsearchHybridRetriever
from dataops_agent.knowledge.models import KnowledgeChunk
from dataops_agent.knowledge.retrieval import HybridRetriever, rrf_fuse


def chunk(chunk_id: str, content: str, **metadata: object) -> KnowledgeChunk:
    return KnowledgeChunk(id=chunk_id, content=content, metadata=metadata)


def test_chunk_markdown_preserves_heading_path_and_source_metadata() -> None:
    chunks = chunk_markdown(
        "runbook",
        "# Incident runbook\n\nOverview.\n\n## Triage\n\nCheck alerts.",
        metadata={"source": "ops"},
    )

    assert [item.content for item in chunks] == ["Overview.", "Check alerts."]
    assert [item.metadata["section_path"] for item in chunks] == [
        ("Incident runbook",),
        ("Incident runbook", "Triage"),
    ]
    assert [item.metadata["source"] for item in chunks] == ["ops", "ops"]


def test_chunk_markdown_drops_deeper_heading_when_parent_depth_decreases() -> None:
    chunks = chunk_markdown("runbook", "### Deep\n\nDeep text.\n\n## Parent\n\nParent text.")

    assert [item.metadata["section_path"] for item in chunks] == [
        ("Deep",),
        ("Parent",),
    ]


def test_search_filters_metadata_before_ranking() -> None:
    retriever = HybridRetriever(
        [
            chunk("ops", "restart the service", source="runbook", team="ops"),
            chunk("sales", "restart the service", source="playbook", team="sales"),
        ]
    )

    result = retriever.search("restart service", filters={"team": "ops"}, limit=5)

    assert [item.id for item in result] == ["ops"]


def test_search_prioritizes_an_exact_identifier_over_textual_matches() -> None:
    retriever = HybridRetriever(
        [
            chunk("guide", "INC-42 is mentioned in this long incident guide"),
            chunk("incident-42", "resolved incident", identifiers=["INC-42"]),
        ]
    )

    result = retriever.search("INC-42", filters={}, limit=2)

    assert [item.id for item in result] == ["incident-42", "guide"]


def test_rrf_fuse_is_deterministic_and_deduplicates_each_ranking() -> None:
    fused = rrf_fuse([["a", "b", "b", "c"], ["b", "c", "a"]], k=60)

    assert fused == ["b", "a", "c"]


def test_rrf_fuse_deduplicates_before_assigning_a_rank_position() -> None:
    fused = rrf_fuse([["a", "b"], ["b", "b", "a"]], k=1)

    assert fused == ["a", "b"]


def test_search_applies_reranker_to_the_fused_candidate_set() -> None:
    class ReverseReranker:
        def rank(self, query: str, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
            assert query == "deploy"
            return list(reversed(chunks))

    retriever = HybridRetriever(
        [chunk("first", "deploy application"), chunk("second", "deploy service")],
        reranker=ReverseReranker(),
    )

    result = retriever.search("deploy", filters={}, limit=2)

    assert [item.id for item in result] == ["second", "first"]


def test_elasticsearch_adapter_stays_lazy_without_a_client_or_server() -> None:
    retriever = ElasticsearchHybridRetriever(index="knowledge")

    assert retriever.search("deploy", filters={}, limit=3) == []


def test_elasticsearch_adapter_keeps_a_natural_language_single_token_on_the_rrf_path() -> None:
    requests: list[dict[str, object]] = []

    class Client:
        def search(self, **request: object) -> dict[str, object]:
            requests.append(request)
            assert request["index"] == "knowledge"
            assert "pinned" not in str(request)
            assert request["retriever"]["rrf"]
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "deploy-1",
                            "_source": {
                                "content": "Deploy from the runbook.",
                                "metadata": {"team": "ops"},
                            },
                        }
                    ]
                }
            }

    result = ElasticsearchHybridRetriever(
        client=Client(), index="knowledge", embed_query=lambda _: [0.25, 0.75]
    ).search(
        "deploy", filters={"team": "ops"}, limit=1
    )

    assert len(requests) == 1
    assert [(item.id, item.content, dict(item.metadata)) for item in result] == [
        ("deploy-1", "Deploy from the runbook.", {"team": "ops"})
    ]


def test_elasticsearch_adapter_uses_rrf_and_filters_both_bm25_and_vector_candidates() -> None:
    class Client:
        def search(self, **request: object) -> dict[str, object]:
            assert "query" not in request
            assert request["retriever"] == {
                "rrf": {
                    "retrievers": [
                        {
                            "standard": {
                                "query": {
                                    "bool": {
                                        "must": [{"match": {"content": "deploy application"}}],
                                        "filter": [{"term": {"metadata.team": "ops"}}],
                                    }
                                }
                            }
                        },
                        {
                            "knn": {
                                "field": "embedding",
                                "query_vector": [0.25, 0.75],
                                "k": 10,
                                "num_candidates": 40,
                                "filter": [{"term": {"metadata.team": "ops"}}],
                            }
                        },
                    ],
                    "rank_constant": 60,
                    "rank_window_size": 10,
                }
            }
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "deploy-1",
                            "_source": {
                                "content": "Deploy from the runbook.",
                                "metadata": {"team": "ops"},
                            },
                        }
                    ]
                }
            }

    result = ElasticsearchHybridRetriever(
        client=Client(), index="knowledge", embed_query=lambda _: [0.25, 0.75]
        ).search("deploy application", filters={"team": "ops"}, limit=2)

    assert [item.id for item in result] == ["deploy-1"]


def test_elasticsearch_adapter_fetches_identifier_aliases_before_hybrid_results() -> None:
    requests: list[dict[str, object]] = []

    class Client:
        def search(self, **request: object) -> dict[str, object]:
            requests.append(request)
            if len(requests) == 1:
                assert request["query"] == {
                    "bool": {
                        "should": [
                            {"term": {"_id": "bar_02_q03"}},
                            {"term": {"metadata.identifier": "bar_02_q03"}},
                            {"term": {"metadata.identifiers": "bar_02_q03"}},
                            {"term": {"metadata.aliases": "bar_02_q03"}},
                        ],
                        "minimum_should_match": 1,
                        "filter": [],
                    }
                }
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "bar_02_q03",
                                "_source": {"content": "direct id", "metadata": {}},
                            },
                            {
                                "_id": "identifier-doc",
                                "_source": {
                                    "content": "direct identifier",
                                    "metadata": {"identifier": "bar_02_q03"},
                                },
                            },
                            {
                                "_id": "identifiers-doc",
                                "_source": {
                                    "content": "direct identifiers",
                                    "metadata": {"identifiers": ["bar_02_q03"]},
                                },
                            },
                            {
                                "_id": "alias-doc",
                                "_source": {
                                    "content": "direct alias",
                                    "metadata": {"aliases": ["bar_02_q03"]},
                                },
                            },
                        ]
                    }
                }
            assert request["retriever"]["rrf"]
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "hybrid-only",
                            "_source": {"content": "ordinary result", "metadata": {}},
                        }
                    ]
                }
            }

    result = ElasticsearchHybridRetriever(
        client=Client(), index="knowledge", embed_query=lambda _: [0.25, 0.75]
    ).search("bar_02_q03", filters={}, limit=5)

    assert len(requests) == 2
    assert [item.id for item in result] == [
        "bar_02_q03",
        "identifier-doc",
        "identifiers-doc",
        "alias-doc",
        "hybrid-only",
    ]


def test_elasticsearch_adapter_direct_lookup_honors_metadata_filters() -> None:
    requests: list[dict[str, object]] = []

    class Client:
        def search(self, **request: object) -> dict[str, object]:
            requests.append(request)
            if len(requests) == 1:
                assert request["query"]["bool"]["filter"] == [
                    {"term": {"metadata.team": "ops"}}
                ]
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "bar_02_q03",
                                "_source": {
                                    "content": "wrong team",
                                    "metadata": {"team": "sales"},
                                }
                            }
                        ]
                    }
                }
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "ops-guide",
                            "_source": {
                                "content": "ordinary result",
                                "metadata": {"team": "ops"},
                            },
                        },
                    ]
                }
            }

    result = ElasticsearchHybridRetriever(
        client=Client(), index="knowledge", embed_query=lambda _: [0.25, 0.75]
    ).search("bar_02_q03", filters={"team": "ops"}, limit=2)

    assert len(requests) == 2
    assert [item.id for item in result] == ["ops-guide"]


def test_default_mapping_declares_the_exact_fields_used_by_identifier_lookup() -> None:
    metadata_properties = DEFAULT_KNOWLEDGE_INDEX_MAPPING["properties"]["metadata"][
        "properties"
    ]

    assert {
        field: metadata_properties[field]
        for field in ("identifier", "identifiers", "aliases")
    } == {
        "identifier": {"type": "keyword"},
        "identifiers": {"type": "keyword"},
        "aliases": {"type": "keyword"},
    }


def test_knowledge_mapping_supports_configurable_knn_and_exact_metadata_filters() -> None:
    mapping = elastic.build_knowledge_index_mapping(embedding_dimensions=2)

    assert mapping["properties"]["embedding"] == {
        "type": "dense_vector",
        "dims": 2,
        "index": True,
        "similarity": "cosine",
    }
    assert mapping["dynamic_templates"] == [
        {
            "metadata_strings_as_keywords": {
                "path_match": "metadata.*",
                "match_mapping_type": "string",
                "mapping": {"type": "keyword", "ignore_above": 256},
            }
        }
    ]
    assert DEFAULT_KNOWLEDGE_INDEX_MAPPING["properties"]["embedding"]["dims"] == (
        elastic.DEFAULT_EMBEDDING_DIMENSIONS
    )


def test_knowledge_mapping_rejects_nonpositive_embedding_dimensions() -> None:
    with pytest.raises(ValueError, match="embedding_dimensions must be positive"):
        elastic.build_knowledge_index_mapping(embedding_dimensions=0)


def test_bootstrap_creates_mapping_and_indexes_deterministic_sample_rule() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Indices:
        def exists(self, **request: object) -> bool:
            calls.append(("exists", request))
            return False

        def create(self, **request: object) -> None:
            calls.append(("create", request))

    class Client:
        indices = Indices()

        def index(self, **request: object) -> None:
            calls.append(("index", request))

    result = knowledge.bootstrap_knowledge_index(
        Client(), index="knowledge", embedding_dimensions=3
    )

    assert result == {
        "index": "knowledge",
        "created": True,
        "sample_document_id": "sample-audit-schema-rule",
    }
    assert calls[0] == ("exists", {"index": "knowledge"})
    assert calls[1][0] == "create"
    assert calls[1][1]["index"] == "knowledge"
    assert calls[1][1]["mappings"]["properties"]["embedding"]["dims"] == 3
    assert calls[2] == (
        "index",
        {
            "index": "knowledge",
            "id": "sample-audit-schema-rule",
            "document": {
                "content": "Audit rule: report schema validity for every completed ingestion batch.",
                "embedding": [1.0, 0.0, 0.0],
                "metadata": {
                    "identifier": "AUDIT-SCHEMA-001",
                    "aliases": ["schema-validity-rule"],
                    "kind": "audit-rule",
                    "source": "dataops-demo",
                },
            },
            "refresh": "wait_for",
        },
    )


def test_bootstrap_checks_compatible_existing_mapping_before_seeding() -> None:
    calls: list[str] = []

    class Indices:
        def exists(self, **request: object) -> bool:
            calls.append("exists")
            return True

        def get_mapping(self, **request: object) -> dict[str, object]:
            calls.append("get_mapping")
            return {
                "knowledge": {
                    "mappings": elastic.build_knowledge_index_mapping(
                        embedding_dimensions=3
                    )
                }
            }

    class Client:
        indices = Indices()

        def index(self, **request: object) -> None:
            calls.append("index")

    result = elastic.bootstrap_knowledge_index(
        Client(), index="knowledge", embedding_dimensions=3
    )

    assert calls == ["exists", "get_mapping", "index"]
    assert result["created"] is False


@pytest.mark.parametrize(
    "mutate_mapping",
    [
        lambda mapping: mapping["properties"]["embedding"].update({"dims": 2}),
        lambda mapping: mapping["properties"]["metadata"]["properties"].update(
            {"identifier": {"type": "text"}}
        ),
        lambda mapping: mapping.update({"dynamic_templates": []}),
    ],
    ids=["vector-dimensions", "identifier-type", "metadata-string-strategy"],
)
def test_bootstrap_rejects_an_incompatible_existing_mapping(mutate_mapping) -> None:
    mapping = elastic.build_knowledge_index_mapping(embedding_dimensions=3)
    mutate_mapping(mapping)

    class Indices:
        def exists(self, **request: object) -> bool:
            return True

        def get_mapping(self, **request: object) -> dict[str, object]:
            return {
                "knowledge": {
                    "mappings": mapping
                }
            }

    class Client:
        indices = Indices()

        def index(self, **request: object) -> None:
            raise AssertionError("an incompatible index must not be seeded")

    with pytest.raises(
        ValueError,
        match="knowledge index mapping is incompatible",
    ):
        elastic.bootstrap_knowledge_index(
            Client(), index="knowledge", embedding_dimensions=3
        )


def test_bootstrap_command_uses_environment_index_and_embedding_dimensions(
    monkeypatch,
) -> None:
    bootstrap_command = importlib.import_module("dataops_agent.knowledge.bootstrap")
    requests: list[tuple[str, dict[str, object]]] = []

    class Indices:
        def exists(self, **request: object) -> bool:
            return False

        def create(self, **request: object) -> None:
            requests.append(("create", request))

    class Client:
        indices = Indices()

        def index(self, **request: object) -> None:
            requests.append(("index", request))

    monkeypatch.setenv("DATAOPS_ELASTICSEARCH_INDEX", "demo-knowledge")
    monkeypatch.setenv("DATAOPS_ELASTICSEARCH_EMBEDDING_DIMENSIONS", "3")

    result = bootstrap_command.main(client=Client())

    assert result["index"] == "demo-knowledge"
    assert requests[0][1]["mappings"]["properties"]["embedding"]["dims"] == 3
    assert requests[1][1]["document"]["embedding"] == [1.0, 0.0, 0.0]


def test_elasticsearch_adapter_directly_looks_up_a_document_path_chunk_id() -> None:
    requests: list[dict[str, object]] = []

    class Client:
        def search(self, **request: object) -> dict[str, object]:
            requests.append(request)
            if len(requests) == 1:
                assert request["query"]["bool"]["should"][0] == {
                    "term": {"_id": "docs/runbook.md:0000"}
                }
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "docs/runbook.md:0000",
                                "_source": {"content": "direct path", "metadata": {}},
                            }
                        ]
                    }
                }
            assert request["retriever"]["rrf"]
            return {"hits": {"hits": []}}

    result = ElasticsearchHybridRetriever(
        client=Client(), index="knowledge", embed_query=lambda _: [0.25, 0.75]
    ).search("docs/runbook.md:0000", filters={}, limit=2)

    assert len(requests) == 2
    assert [item.id for item in result] == ["docs/runbook.md:0000"]
