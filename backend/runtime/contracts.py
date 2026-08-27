"""Immutable descriptions of tools and response-scoped tool proposals."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


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
            MappingProxyType(deepcopy(dict(self.input_schema))),
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
            MappingProxyType(deepcopy(dict(self.arguments))),
        )
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
