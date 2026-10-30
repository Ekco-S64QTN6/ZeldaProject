"""Contract tests for the opt-in project-bound MCP server."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from zelda_suite.mcp.server import create_server
from zelda_suite.project import initialize_project


def _tool_text(result: Any) -> str:
    assert isinstance(result, list)
    assert result
    assert hasattr(result[0], "text")
    return str(result[0].text)


def test_mcp_server_binds_project_path_and_exposes_bounded_tool_surface(
    tmp_path: Path,
) -> None:
    database, _ = initialize_project("mcp_contract", tmp_path)
    server = create_server(database)

    tools = asyncio.run(server.list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    assert set(schemas) == {
        "project_validate",
        "project_list_source_assets",
        "project_get_source_asset",
        "overworld_list_hidden_items",
        "dungeon_list_chest_records",
        "overworld_create_custom_hidden_item",
        "overworld_delete_custom_hidden_item",
    }
    assert all("database" not in schema.get("properties", {}) for schema in schemas.values())

    create_schema = schemas["overworld_create_custom_hidden_item"]
    assert create_schema["properties"]["apply"]["default"] is False
    assert create_schema["properties"]["coordinate_word"]["minimum"] == 0
    assert create_schema["properties"]["coordinate_word"]["maximum"] == 65534
    assert create_schema["properties"]["value_byte"]["maximum"] == 255
    assert create_schema["properties"]["area_indices"]["minItems"] == 1
    assert create_schema["properties"]["area_indices"]["maxItems"] == 128

    delete_schema = schemas["overworld_delete_custom_hidden_item"]
    assert delete_schema["properties"]["apply"]["default"] is False


def test_mcp_read_tools_validate_and_list_project_without_mutation(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_readonly", tmp_path)
    original_database = database.read_bytes()
    original_export = json_export.read_bytes()
    server = create_server(database)

    validation = json.loads(
        _tool_text(asyncio.run(server.call_tool("project_validate", {})))
    )
    assets = json.loads(
        _tool_text(asyncio.run(server.call_tool("project_list_source_assets", {})))
    )

    assert validation == {"problems": [], "valid": True}
    assert assets == []
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export


def test_mcp_server_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="project database not found"):
        create_server(tmp_path / "missing.db")


def test_mcp_schema_does_not_offer_rom_or_import_tools(tmp_path: Path) -> None:
    database, _ = initialize_project("mcp_scope", tmp_path)
    server = create_server(database)
    names = {tool.name for tool in asyncio.run(server.list_tools())}

    assert not any("rom" in name.lower() for name in names)
    assert not any("import" in name.lower() for name in names)
    assert "update_overworld_hidden_item" not in names
    assert "update_dungeon_chest_record" not in names
