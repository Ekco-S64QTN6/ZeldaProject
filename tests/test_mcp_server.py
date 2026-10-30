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

PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
REPLACEMENTS = [
    (0, 2813, 0x0DC89C, 0, "dw $0DCC", 0x0DCC, "Hole"),
    (1, 2814, 0x0DC89E, 2, "dw $0212", 0x0212, "Portal"),
    (2, 2815, 0x0DC8A0, 4, "dw $FFFF", 0xFFFF, "Garbage"),
    (3, 2816, 0x0DC8A2, 6, "dw $0DB4", 0x0DB4, "Bomb hole"),
]


def _tool_text(result: Any) -> str:
    assert isinstance(result, list)
    assert result
    assert hasattr(result[0], "text")
    return str(result[0].text)


def _seed_semantic_model(database: Path) -> None:
    """Seed a complete source-preserving model without requiring the disassembly submodule."""
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute(
                """INSERT INTO overworld_hidden_item_model (
                       singleton, source_file, source_revision, source_sha256,
                       imported_at, consumer_label, replacement_table_label
                   ) VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    "Bank1B.asm",
                    PINNED_REVISION,
                    "0" * 64,
                    "2026-10-30T00:00:00Z",
                    "Overworld_RevealSecret",
                    "Overworld_SecretTileType",
                ),
            )
            connection.executemany(
                """INSERT INTO overworld_hidden_item_replacement_word (
                       table_index, source_line, file_offset, selector_byte_offset,
                       expression, value, comment
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                REPLACEMENTS,
            )
            for record_index in range(351):
                coordinate = record_index + 1
                label = (
                    "OverworldData_HiddenItems_Screen_"
                    + format(record_index % 80, "02X")
                )
                source_expression = (
                    "dw $" + format(coordinate, "04X") + " : db $05"
                )
                connection.execute(
                    """INSERT INTO overworld_hidden_item_record (
                           record_index, source_label, source_line, source_file_offset,
                           source_expression, source_coordinate_word, coordinate_word,
                           source_value_byte, value_byte, consumer_class, consumer_operation,
                           selector_byte_offset, replacement_table_index,
                           replacement_word_value, replacement_word_comment, special_case
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)""",
                    (
                        record_index,
                        label,
                        500 + record_index,
                        0x0DC3F9 + record_index * 3,
                        source_expression,
                        coordinate,
                        coordinate,
                        0x05,
                        0x05,
                        "ordinary_secret_mask",
                        "TSB $0B9C combines this value with secret-state flags",
                    ),
                )

            for area_index in range(128):
                record_index = 0 if area_index < 2 else area_index - 1
                target_label = (
                    "OverworldData_HiddenItems_Screen_00"
                    if area_index < 2
                    else "OverworldData_HiddenItems_Screen_"
                    + format(record_index % 80, "02X")
                )
                target_offset = (
                    0x0DC3F9
                    if area_index < 2
                    else 0x0DC3F9 + record_index * 3
                )
                connection.execute(
                    """INSERT INTO overworld_hidden_item_area (
                           area_index, pointer_entry_file_offset, target_label,
                           target_file_offset, sentinel_file_offset, record_count
                       ) VALUES (?, ?, ?, ?, ?, 1)""",
                    (
                        area_index,
                        0x0DC2F9 + area_index * 2,
                        target_label,
                        target_offset,
                        0x0DC450 + area_index,
                    ),
                )
                connection.execute(
                    """INSERT INTO overworld_hidden_item_area_record (
                           area_index, ordinal, record_index
                       ) VALUES (?, 0, ?)""",
                    (area_index, record_index),
                )


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


def test_mcp_custom_hidden_item_tools_preview_and_apply_explicitly(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_custom_crud", tmp_path)
    _seed_semantic_model(database)
    server = create_server(database)
    original_database = database.read_bytes()
    original_export = json_export.read_bytes()

    create_arguments = {
        "area_indices": [4, 5],
        "coordinate_word": 0x1234,
        "value_byte": 0x05,
    }
    preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_create_custom_hidden_item", create_arguments
                )
            )
        )
    )
    assert preview["dry_run"] is True
    assert preview["custom_record_id"] is None
    assert preview["area_indices"] == [4, 5]
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_create_custom_hidden_item",
                    {**create_arguments, "apply": True},
                )
            )
        )
    )
    custom_id = applied["record"]["custom_record_id"]
    assert applied["dry_run"] is False
    assert applied["record"]["record_kind"] == "project_authored"
    assert applied["record"]["source_record_index"] is None
    assert applied["record"]["area_indices"] == [4, 5]

    area_result = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_list_hidden_items", {"area_index": 4})
            )
        )
    )
    assert area_result["custom_records"][0]["custom_record_id"] == custom_id
    assert area_result["area"]["custom_record_ids"] == [custom_id]

    delete_arguments = {"custom_record_id": custom_id}
    delete_preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_delete_custom_hidden_item", delete_arguments)
            )
        )
    )
    assert delete_preview["dry_run"] is True
    assert delete_preview["record"]["area_indices"] == [4, 5]

    deleted = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_delete_custom_hidden_item",
                    {**delete_arguments, "apply": True},
                )
            )
        )
    )
    assert deleted["dry_run"] is False
    assert deleted["deleted"]["custom_record_id"] == custom_id

    final_model = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("overworld_list_hidden_items", {}))
        )
    )
    assert final_model["summary"]["record_count"] == 351
    assert final_model["summary"]["custom_record_count"] == 0
    assert final_model["custom_records"] == []
    validation = json.loads(
        _tool_text(asyncio.run(server.call_tool("project_validate", {})))
    )
    assert validation == {"problems": [], "valid": True}


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
