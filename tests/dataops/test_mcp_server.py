from __future__ import annotations

import asyncio

import pytest

from dataops_agent.data import DuckDBRepository, load_records


def _repository_with_record() -> DuckDBRepository:
    repository = DuckDBRepository()
    load_records(
        [{"record_id": "invoice-1", "source": "demo", "amount": 42}],
        batch_id="mcp-demo",
        repository=repository,
    )
    return repository


def test_readonly_mcp_tool_contract_exposes_only_safe_tools() -> None:
    """The MCP boundary must not accidentally publish a mutating capability."""
    from dataops_agent.mcp_server import MCPDependencies, build_readonly_tool_registry

    registry = build_readonly_tool_registry(MCPDependencies(repository=_repository_with_record()))

    assert registry.names() == (
        "inspect_schema",
        "quality_report",
        "execute_readonly_sql",
        "deterministic_lookup",
        "route_request",
    )
    assert all(not registry.get(name).mutates for name in registry.names())


def test_readonly_mcp_handlers_delegate_to_real_dataops_primitives() -> None:
    from dataops_agent.mcp_server import MCPDependencies, build_readonly_tool_registry

    registry = build_readonly_tool_registry(MCPDependencies(repository=_repository_with_record()))

    schema = registry.get("inspect_schema").handler()
    quality = registry.get("quality_report").handler()
    rows = registry.get("execute_readonly_sql").handler(
        "SELECT record_id, source FROM records"
    )
    lookup = registry.get("deterministic_lookup").handler("invoice-1")
    route = registry.get("route_request").handler("count records by source")

    assert {table["name"] for table in schema["tables"]} == {
        "records",
        "quarantine_records",
        "load_batches",
    }
    assert quality == {"schema_valid_rate": 1.0, "duplicate_rate": 0.0}
    assert rows == {"rows": [{"record_id": "invoice-1", "source": "demo"}]}
    assert lookup == {
        "found": True,
        "record": {
            "record_id": "invoice-1",
            "source": "demo",
            "batch_id": "mcp-demo",
            "payload": {"record_id": "invoice-1", "source": "demo", "amount": 42},
        },
    }
    assert route == {"route": "sql"}


def test_deterministic_lookup_reports_absence_without_falling_back_to_rag() -> None:
    from dataops_agent.mcp_server import MCPDependencies, build_readonly_tool_registry

    registry = build_readonly_tool_registry(MCPDependencies(repository=_repository_with_record()))

    assert registry.get("deterministic_lookup").handler("missing-record") == {
        "found": False,
        "record": None,
    }


def test_deterministic_lookup_rejects_blank_identifier() -> None:
    from dataops_agent.mcp_server import MCPDependencies, build_readonly_tool_registry

    registry = build_readonly_tool_registry(MCPDependencies(repository=_repository_with_record()))

    with pytest.raises(ValueError, match="record_id must not be blank"):
        registry.get("deterministic_lookup").handler("  ")


def test_mcp_server_uses_the_sdk_in_memory_client_when_dependency_is_installed() -> None:
    """Exercise the registered schemas and tool execution without a transport process."""
    pytest.importorskip("mcp")
    from mcp import Client

    from dataops_agent.mcp_server import MCPDependencies, create_mcp_server

    server = create_mcp_server(MCPDependencies(repository=_repository_with_record()))

    async def verify() -> None:
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == {
                "inspect_schema",
                "quality_report",
                "execute_readonly_sql",
                "deterministic_lookup",
                "route_request",
            }
            result = await client.call_tool("deterministic_lookup", {"record_id": "invoice-1"})
            assert result.is_error is False
            assert result.structured_content == {
                "found": True,
                "record": {
                    "record_id": "invoice-1",
                    "source": "demo",
                    "batch_id": "mcp-demo",
                    "payload": {
                        "record_id": "invoice-1",
                        "source": "demo",
                        "amount": 42,
                    },
                },
            }

    asyncio.run(verify())
