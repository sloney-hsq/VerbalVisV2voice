"""Knowledge-layer contracts and local retrieval implementations."""

from .chunking import chunk_markdown
from .elastic import DEFAULT_KNOWLEDGE_INDEX_MAPPING, ElasticsearchHybridRetriever
from .models import KnowledgeChunk
from .retrieval import HybridRetriever, Reranker, rrf_fuse

__all__ = [
    "ElasticsearchHybridRetriever",
    "DEFAULT_KNOWLEDGE_INDEX_MAPPING",
    "HybridRetriever",
    "KnowledgeChunk",
    "Reranker",
    "chunk_markdown",
    "rrf_fuse",
]
