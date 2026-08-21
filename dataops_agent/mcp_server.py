"""Optional read-only MCP stdio server for the DataOps Agent.

The module deliberately keeps MCP at the outermost boundary: callers can use
the same registry and handlers in tests without importing the optional SDK or
starting a transport.  It exposes only deterministic reads; ingestion and
audits remain HTTP/worker operations guarded by idempotency and task state.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Callable

from pydantic import Field

from .data import DuckDBRepository, execute_readonly_sql, run_quality_checks
from .router import Route, route_request as _route_request
from .runtime import ToolRegistry, ToolSpec
from .settings import Settings

if TYPE_CHECKING:  # Keep importing this module independent of the optional MCP SDK.
    from mcp.server import MCPServer


_READ_ONLY_TOOL_NAMES = (
    "inspect_schema",
    "quality_report",
    "execute_readonly_sql",
    "deterministic_lookup",
    "route_request",
)
_SCHEMA_TABLES = ("records", "quarantine_records", "load_batches")
_RecordId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=512,
        description="Exact record_id from the records table; this is not a semantic search query.",
    ),
]
_SqlText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=10_000,
        description="One allow-listed, read-only SELECT or WITH statement.",
    ),
]
_RequestText = Annotated[
    str,
    Field(min_length=1, max_length=4_000, description="Natural-language DataOps request to classify."),
]


@dataclass(frozen=True, slots=True)
class MCPDependencies:
    """Dependencies for the read-only MCP surface.

    The repository stays injectable so unit tests and hosts can share their
    configured DuckDB store without requiring Redis, Elasticsearch, or an MCP
    transport process.
    """

    repository: DuckDBRepository
    route: Callable[[str], Route] = _route_request


def build_readonly_tool_registry(dependencies: MCPDependencies) -> ToolRegistry:
    """Build the small, explicit public capability set for MCP clients."""
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="inspect_schema",
            description="Inspect the fixed DataOps DuckDB schemas and row counts.",
            handler=lambda: _inspect_schema(dependencies.repository),
            input_schema={"type": "object", "properties": {}},
        )
    )
    registry.register(
        ToolSpec(
            name="quality_report",
            description="Return deterministic quality metrics for completed ingestion batches.",
            handler=lambda: asdict(run_quality_checks(dependencies.repository)),
            input_schema={"type": "object", "properties": {}},
        )
    )
    registry.register(
        ToolSpec(
            name="execute_readonly_sql",
            description="Execute an allow-listed SELECT or WITH query in the isolated SQL sandbox.",
            handler=lambda sql: {"rows": execute_readonly_sql(dependencies.repository, sql)},
            input_schema={
                "type": "object",
                "properties": {"sql": {"type": "string", "minLength": 1}},
                "required": ["sql"],
            },
        )
    )
    registry.register(
        ToolSpec(
            name="deterministic_lookup",
            description="Look up one record by exact record_id without vector or lexical retrieval.",
            handler=lambda record_id: _deterministic_lookup(dependencies.repository, record_id),
            input_schema={
                "type": "object",
                "properties": {"record_id": {"type": "string", "minLength": 1}},
                "required": ["record_id"],
            },
        )
    )
    registry.register(
        ToolSpec(
            name="route_request",
            description="Classify a DataOps request into the deterministic runtime route.",
            handler=lambda text: {"route": dependencies.route(text).value},
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string", "minLength": 1}},
                "required": ["text"],
            },
        )
    )
    return registry


def create_mcp_server(dependencies: MCPDependencies | None = None) -> "MCPServer[Any]":
    """Create an official Python SDK MCPServer without starting a transport.

    Importing this module never imports ``mcp``.  The dependency error is raised
    only when a host actually asks to construct the protocol server.
    """
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as error:  # pragma: no cover - environment-specific branch
        raise RuntimeError(
            "MCP support is optional. Install it with: pip install 'mcp>=2,<3'"
        ) from error

    resolved_dependencies = dependencies or _default_dependencies()
    registry = build_readonly_tool_registry(resolved_dependencies)
    annotations = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    server = MCPServer(
        "DataOps Agent",
        version="0.1.0",
        instructions=(
            "Use only these read-only DataOps tools. Prefer deterministic_lookup for an "
            "exact record_id and execute_readonly_sql only for structured aggregate facts."
        ),
    )

    @server.tool(
        name="inspect_schema",
        description=registry.get("inspect_schema").description,
        annotations=annotations,
    )
    def inspect_schema() -> dict[str, Any]:
        """Inspect DataOps tables, columns, and row counts without modifying data."""
        return registry.get("inspect_schema").handler()  # type: ignore[no-any-return]

    @server.tool(
        name="quality_report",
        description=registry.get("quality_report").description,
        annotations=annotations,
    )
    def quality_report() -> dict[str, float]:
        """Report deterministic schema-valid and duplicate rates."""
        return registry.get("quality_report").handler()  # type: ignore[no-any-return]

    @server.tool(
        name="execute_readonly_sql",
        description=registry.get("execute_readonly_sql").description,
        annotations=annotations,
    )
    def readonly_sql(sql: _SqlText) -> dict[str, list[dict[str, object]]]:
        """Run one constrained SQL read against isolated allow-listed tables."""
        return registry.get("execute_readonly_sql").handler(sql)  # type: ignore[no-any-return]

    @server.tool(
        name="deterministic_lookup",
        description=registry.get("deterministic_lookup").description,
        annotations=annotations,
    )
    def deterministic_lookup(record_id: _RecordId) -> dict[str, object]:
        """Fetch one exact record_id; no RAG fallback is attempted."""
        return registry.get("deterministic_lookup").handler(record_id)  # type: ignore[no-any-return]

    @server.tool(
        name="route_request",
        description=registry.get("route_request").description,
        annotations=annotations,
    )
    def route_request(text: _RequestText) -> dict[str, str]:
        """Classify a request for the runtime router without executing a mutation."""
        return registry.get("route_request").handler(text)  # type: ignore[no-any-return]

    return server


def main() -> int:
    """Run the optional MCP server over stdio for desktop hosts and inspectors."""
    try:
        server = create_mcp_server()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    server.run(transport="stdio")
    return 0


def _default_dependencies() -> MCPDependencies:
    settings = Settings.from_env()
    if settings.database_path != ":memory:":
        Path(settings.database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return MCPDependencies(repository=DuckDBRepository(settings.database_path))


def _inspect_schema(repository: DuckDBRepository) -> dict[str, list[dict[str, object]]]:
    tables: list[dict[str, object]] = []
    for table in _SCHEMA_TABLES:
        description = repository.connection.execute(f"DESCRIBE {table}").fetchall()
        tables.append(
            {
                "name": table,
                "row_count": repository.count_rows(table),
                "columns": [
                    {"name": row[0], "type": row[1], "nullable": row[2]}
                    for row in description
                ],
            }
        )
    return {"tables": tables}


def _deterministic_lookup(repository: DuckDBRepository, record_id: str) -> dict[str, object]:
    normalized_id = record_id.strip()
    if not normalized_id:
        raise ValueError("record_id must not be blank")
    row = repository.connection.execute(
        "SELECT record_id, source, payload, batch_id FROM records WHERE record_id = ?",
        [normalized_id],
    ).fetchone()
    if row is None:
        return {"found": False, "record": None}
    payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
    return {
        "found": True,
        "record": {
            "record_id": row[0],
            "source": row[1],
            "batch_id": row[3],
            "payload": payload,
        },
    }


if __name__ == "__main__":  # pragma: no cover - exercised by a host subprocess.
    raise SystemExit(main())
