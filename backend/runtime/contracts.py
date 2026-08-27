"""Immutable descriptions of tools and response-scoped tool proposals."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


class _FrozenSequence(tuple[Any, ...]):
    """An immutable sequence that still compares equal to JSON lists."""

    __hash__ = tuple.__hash__

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return list(self) == other
        return super().__eq__(other)


def _freeze(value: Any) -> Any:
    """Copy a JSON-like value into recursively immutable containers."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {deepcopy(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return _FrozenSequence(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


class ToolMode(str, Enum):
    """Where a tool is allowed to make its effects visible."""

    READ_ONLY = "READ_ONLY"
    DRAFT_MUTATION = "DRAFT_MUTATION"
    PERSISTENT_WRITE = "PERSISTENT_WRITE"


@dataclass(frozen=True)
class ToolContract:
    """Runtime admission metadata for one registered tool."""

    name: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    mode: ToolMode = ToolMode.READ_ONLY
    dependencies: tuple[str, ...] = ()
    precondition: str = "valid arguments"
    idempotent: bool = False
    cancellable: bool = False
    effect_detail: str = "Does not change the dashboard."

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_schema",
            _freeze(self.input_schema),
        )
        object.__setattr__(self, "dependencies", tuple(self.dependencies))


@dataclass(frozen=True)
class ToolProposal:
    """A model-proposed call bound to one response transaction."""

    response_id: str
    intent_epoch: int
    base_revision: int
    call_id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    cancellation_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            _freeze(self.arguments),
        )
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
