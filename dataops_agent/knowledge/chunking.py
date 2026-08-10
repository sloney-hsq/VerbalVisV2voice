"""Structure-aware document chunking."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .models import KnowledgeChunk


_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.*?)\s*#*\s*$")


def chunk_markdown(
    document_id: str,
    text: str,
    *,
    metadata: Mapping[str, object] | None = None,
    max_chars: int = 1_000,
) -> list[KnowledgeChunk]:
    """Split Markdown into paragraph chunks while retaining heading ancestry."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    base_metadata = dict(metadata or {})
    headings: list[str | None] = []
    chunks: list[KnowledgeChunk] = []
    paragraph: list[str] = []

    def section_path() -> tuple[str, ...]:
        return tuple(heading for heading in headings if heading is not None)

    def emit(content: str) -> None:
        normalized = " ".join(content.split())
        if not normalized:
            return
        for start in range(0, len(normalized), max_chars):
            item_metadata = dict(base_metadata)
            item_metadata.update(
                {"document_id": document_id, "section_path": section_path()}
            )
            chunks.append(
                KnowledgeChunk(
                    id=f"{document_id}:{len(chunks):04d}",
                    content=normalized[start : start + max_chars],
                    metadata=item_metadata,
                )
            )

    def flush_paragraph() -> None:
        nonlocal paragraph
        emit("\n".join(paragraph))
        paragraph = []

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            level = len(heading.group("level"))
            title = heading.group("title").strip()
            if len(headings) < level:
                headings.extend([None] * (level - len(headings)))
            headings[level - 1] = title
            del headings[level:]
            continue
        if line.strip():
            paragraph.append(line)
        else:
            flush_paragraph()
    flush_paragraph()
    return chunks
