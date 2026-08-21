"""Explicit one-time Elasticsearch index bootstrap command."""

from __future__ import annotations

import json
import os
from typing import Any

from .elastic import DEFAULT_EMBEDDING_DIMENSIONS, bootstrap_knowledge_index


def main(*, client: Any | None = None) -> dict[str, object]:
    """Create/check the configured index and seed the deterministic demo rule."""
    url = os.getenv("DATAOPS_ELASTICSEARCH_URL", "http://localhost:9200")
    index = os.getenv("DATAOPS_ELASTICSEARCH_INDEX", "dataops-knowledge")
    dimensions = int(
        os.getenv(
            "DATAOPS_ELASTICSEARCH_EMBEDDING_DIMENSIONS",
            str(DEFAULT_EMBEDDING_DIMENSIONS),
        )
    )
    if client is None:
        from elasticsearch import Elasticsearch

        client = Elasticsearch(url)
    result = bootstrap_knowledge_index(
        client,
        index=index,
        embedding_dimensions=dimensions,
    )
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
