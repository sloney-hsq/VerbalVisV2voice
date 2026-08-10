"""Budgeted context selection."""

from __future__ import annotations

from collections.abc import Sequence


class ContextManager:
    """Retains the newest whole messages without exceeding a character budget."""

    def __init__(self, max_characters: int) -> None:
        if max_characters < 1:
            raise ValueError("max_characters must be positive")
        self.max_characters = max_characters

    def compact(self, messages: Sequence[str]) -> list[str]:
        remaining = self.max_characters
        selected: list[str] = []
        for message in reversed(messages):
            if len(message) > remaining:
                break
            selected.append(message)
            remaining -= len(message)
        selected.reverse()
        return selected
