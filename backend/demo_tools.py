"""Compatibility layer for code written before the unified tool service.

All model-facing tool schemas and implementations now live in ``tools.py``.
"""

from __future__ import annotations

from typing import Any

from tools import TOOL_SCHEMAS, execute_tool

FINAL_TOOL_NAMES = {
    schema.get("name")
    for schema in TOOL_SCHEMAS
    if isinstance(schema, dict) and schema.get("name")
}


def register_demo_tool_schemas() -> None:
    """No-op retained for older imports."""


def is_demo_tool(name: str) -> bool:
    return name in FINAL_TOOL_NAMES


def execute_demo_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return execute_tool(name, arguments)
