"""Value objects used by the knowledge retrieval layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A searchable piece of knowledge with source and structural metadata."""

    id: str
    content: str
    metadata: Mapping[str, object] = field(default_factory=dict)
