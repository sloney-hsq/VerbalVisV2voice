"""Tool declarations and a validated registry for runtime dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import re
from typing import Any


_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """The public metadata and handler for one runtime tool."""

    name: str
    description: str
    handler: Callable[..., object]
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    mutates: bool = False

    def __post_init__(self) -> None:
        if not _TOOL_NAME.fullmatch(self.name):
            raise ValueError("tool name must contain lowercase letters, digits, and underscores")
        if not self.description.strip():
            raise ValueError("tool description must not be empty")
        if not callable(self.handler):
            raise TypeError("tool handler must be callable")


class ToolRegistry:
    """An explicit, collision-free mapping from tool names to specifications."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} is already registered")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)
