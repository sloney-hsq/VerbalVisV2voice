"""Knowledge-layer contracts and local retrieval implementations."""

from .chunking import chunk_markdown
from .elastic import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_KNOWLEDGE_INDEX_MAPPING,
    ElasticsearchHybridRetriever,
    bootstrap_knowledge_index,
    build_knowledge_index_mapping,
)
from .models import KnowledgeChunk
from .retrieval import HybridRetriever, Reranker, rrf_fuse

__all__ = [
    "ElasticsearchHybridRetriever",
    "DEFAULT_EMBEDDING_DIMENSIONS",
    "DEFAULT_KNOWLEDGE_INDEX_MAPPING",
    "HybridRetriever",
    "KnowledgeChunk",
    "Reranker",
    "bootstrap_knowledge_index",
    "build_knowledge_index_mapping",
    "chunk_markdown",
    "rrf_fuse",
]
