"""Contract tests for the opt-in project-bound MCP server."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from zelda_suite.mcp.server import create_server
from zelda_suite.project import (
    get_dungeon_chest_model,
    get_overworld_hidden_item_model,
    get_project_context,
    import_dungeon_chest_data,
    initialize_project,
    update_overworld_hidden_item,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"

PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
REPLACEMENTS = [
    (0, 2813, 0x0DC89C, 0, "dw $0DCC", 0x0DCC, "Hole"),
    (1, 2814, 0x0DC89E, 2, "dw $0212", 0x0212, "Portal"),
    (2, 2815, 0x0DC8A0, 4, "dw $FFFF", 0xFFFF, "Garbage"),
    (3, 2816, 0x0DC8A2, 6, "dw $0DB4", 0x0DB4, "Bomb hole"),
]


def _tool_text(result: Any) -> str:
    # FastMCP v1.28+ returns (content_blocks, structured_content).
    content = result[0] if isinstance(result, tuple) else result
    assert isinstance(content, list)
    assert content
    assert hasattr(content[0], "text")
    return str(content[0].text)


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
    descriptions = {tool.name: tool.description or "" for tool in tools}

    assert "source_references" in descriptions["overworld_update_hidden_item_record"]
    assert "source_references" in descriptions["dungeon_update_chest_record"]

    assert set(schemas) == {
        "project_get_context",
        "project_validate",
        "project_list_source_assets",
        "project_get_source_asset",
        "overworld_list_hidden_items",
        "overworld_find_hidden_items",
        "overworld_update_hidden_item_record",
        "dungeon_list_chest_records",
        "dungeon_find_chest_records",
        "dungeon_audit_chest_room_references",
        "dungeon_update_chest_record",
        "overworld_create_custom_hidden_item",
        "overworld_update_custom_hidden_item",
        "overworld_delete_custom_hidden_item",
    }
    assert all(
        "database" not in schema.get("properties", {})
        and "registry" not in schema.get("properties", {})
        for schema in schemas.values()
    )

    create_schema = schemas["overworld_create_custom_hidden_item"]
    assert create_schema["properties"]["apply"]["default"] is False
    assert create_schema["properties"]["coordinate_word"]["minimum"] == 0
    assert create_schema["properties"]["coordinate_word"]["maximum"] == 65534
    assert create_schema["properties"]["value_byte"]["maximum"] == 255
    assert create_schema["properties"]["area_indices"]["minItems"] == 1
    assert create_schema["properties"]["area_indices"]["maxItems"] == 128

    update_schema = schemas["overworld_update_custom_hidden_item"]
    assert update_schema["properties"]["apply"]["default"] is False
    assert update_schema["properties"]["custom_record_id"]["minimum"] == 1
    assert update_schema["properties"]["coordinate_word"]["anyOf"][0]["maximum"] == 65534
    assert update_schema["properties"]["value_byte"]["anyOf"][0]["maximum"] == 255
    assert update_schema["properties"]["area_indices"]["anyOf"][0]["items"]["maximum"] == 127

    delete_schema = schemas["overworld_delete_custom_hidden_item"]
    assert delete_schema["properties"]["apply"]["default"] is False

    overworld_find_schema = schemas["overworld_find_hidden_items"]
    assert overworld_find_schema["properties"]["area_index"]["anyOf"][0]["minimum"] == 0
    assert overworld_find_schema["properties"]["area_index"]["anyOf"][0]["maximum"] == 127
    assert overworld_find_schema["properties"]["record_index"]["anyOf"][0]["minimum"] == 0
    assert overworld_find_schema["properties"]["record_index"]["anyOf"][0]["maximum"] == 350
    assert overworld_find_schema["properties"]["custom_record_id"]["anyOf"][0]["minimum"] == 1
    assert overworld_find_schema["properties"]["coordinate_word"]["anyOf"][0]["maximum"] == 65534
    assert overworld_find_schema["properties"]["value_byte"]["anyOf"][0]["maximum"] == 255

    overworld_schema = schemas["overworld_update_hidden_item_record"]
    assert overworld_schema["properties"]["apply"]["default"] is False
    assert overworld_schema["properties"]["record_index"]["minimum"] == 0
    assert overworld_schema["properties"]["record_index"]["maximum"] == 350
    assert overworld_schema["properties"]["coordinate_word"]["anyOf"][0]["maximum"] == 65534
    assert overworld_schema["properties"]["value_byte"]["anyOf"][0]["maximum"] == 255

    chest_list_schema = schemas["dungeon_list_chest_records"]
    table_index_schema = chest_list_schema["properties"]["table_index"]["anyOf"][0]
    assert table_index_schema["minimum"] == 0
    assert table_index_schema["maximum"] == 167

    chest_find_schema = schemas["dungeon_find_chest_records"]
    assert chest_find_schema["properties"]["item_value"]["anyOf"][0]["minimum"] == 0
    assert chest_find_schema["properties"]["item_value"]["anyOf"][0]["maximum"] == 255
    assert chest_find_schema["properties"]["room_value"]["anyOf"][0]["minimum"] == 0
    assert chest_find_schema["properties"]["room_value"]["anyOf"][0]["maximum"] == 32767
    assert chest_find_schema["properties"]["is_big_chest"]["anyOf"][0]["type"] == "boolean"

    for mutation_name in (
        "overworld_update_hidden_item_record",
        "dungeon_update_chest_record",
        "overworld_create_custom_hidden_item",
        "overworld_update_custom_hidden_item",
        "overworld_delete_custom_hidden_item",
    ):
        revision_schema = schemas[mutation_name]["properties"][
            "expected_project_revision"
        ]["anyOf"][0]
        assert revision_schema["type"] == "string"
        assert revision_schema["pattern"] == "^[0-9a-f]{64}$"
        assert "exact project_revision" in revision_schema["description"].lower()
        apply_schema = schemas[mutation_name]["properties"]["apply"]
        assert apply_schema["default"] is False
        assert "explicit user approval" in apply_schema["description"]

    chest_schema = schemas["dungeon_update_chest_record"]
    assert chest_schema["properties"]["apply"]["default"] is False
    assert chest_schema["properties"]["table_index"]["minimum"] == 0
    assert chest_schema["properties"]["table_index"]["maximum"] == 167
    assert chest_schema["properties"]["item_value"]["anyOf"][0]["maximum"] == 255
    assert chest_schema["properties"]["room_value"]["anyOf"][0]["maximum"] == 32767


def test_mcp_project_context_is_compact_consistent_and_read_only(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_project_context", tmp_path)
    server = create_server(database)
    original_database = database.read_bytes()
    original_export = json_export.read_bytes()

    empty_context = json.loads(
        _tool_text(asyncio.run(server.call_tool("project_get_context", {})))
    )
    assert empty_context["valid"] is True
    assert empty_context["problems"] == []
    assert empty_context["format"] == "zelda-suite-project"
    assert empty_context["format_version"] == 5
    assert empty_context["schema_version"] == 5
    assert empty_context["project"]["name"] == "mcp_project_context"
    empty_revision = empty_context["project_revision"]
    assert isinstance(empty_revision, str) and len(empty_revision) == 64
    assert set(empty_revision) <= set("0123456789abcdef")
    assert empty_context["source_asset_count"] == 0
    assert empty_context["source_assets"] == []
    assert empty_context["semantic_models"] == {
        "overworld_hidden_items": None,
        "dungeon_chests": None,
    }
    assert empty_context["evidence"] == {
        "sqlite_snapshot_read_only": True,
        "full_payloads_omitted": True,
        "rom_bytes_read": False,
        "rom_modified": False,
    }
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    _seed_semantic_model(database)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    populated_database = database.read_bytes()
    populated_export = json_export.read_bytes()

    populated_context = json.loads(
        _tool_text(asyncio.run(server.call_tool("project_get_context", {})))
    )
    assert populated_context["valid"] is True
    assert populated_context["problems"] == []
    assert populated_context["project_revision"] != empty_revision
    assert populated_context["source_asset_count"] == len(
        populated_context["source_assets"]
    )
    assert all("payload" not in asset for asset in populated_context["source_assets"])
    assert all(
        "path" not in asset and "absolute_path" not in asset
        for asset in populated_context["source_assets"]
    )
    overworld = populated_context["semantic_models"]["overworld_hidden_items"]
    assert overworld["summary"]["record_count"] == 351
    assert overworld["source_revision"] == PINNED_REVISION
    assert overworld["source_sha256"] == "0" * 64
    assert "records" not in overworld
    assert "custom_records" not in overworld
    chests = populated_context["semantic_models"]["dungeon_chests"]
    assert chests["summary"]["entry_count"] == 168
    assert chests["source_revision"] == imported["source_revision"]
    assert chests["source_sha256"] == imported["source_sha256"]
    assert "entries" not in chests
    assert "source_entries" not in chests
    assert populated_context["evidence"]["rom_bytes_read"] is False
    assert populated_context["evidence"]["rom_modified"] is False

    preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {"table_index": 0, "item_value": 0xAA},
                )
            )
        )
    )
    assert preview["project_revision"] == populated_context["project_revision"]
    assert database.read_bytes() == populated_database
    assert json_export.read_bytes() == populated_export


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


def test_mcp_overworld_find_searches_source_and_custom_records_without_mutation(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_find_overworld_items", tmp_path)
    _seed_semantic_model(database)
    server = create_server(database)

    create_arguments = {
        "area_indices": [0, 3],
        "coordinate_word": 1,
        "value_byte": 0x05,
    }
    create_preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_create_custom_hidden_item", create_arguments)
            )
        )
    )
    created = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_create_custom_hidden_item",
                    {
                        **create_arguments,
                        "expected_project_revision": create_preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    custom_id = created["record"]["custom_record_id"]
    database_before = database.read_bytes()
    export_before = json_export.read_bytes()

    result = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_find_hidden_items",
                    {
                        "area_index": 0,
                        "coordinate_word": 1,
                        "value_byte": 0x05,
                    },
                )
            )
        )
    )
    assert result["format"] == "zelda-suite-overworld-hidden-item-model"
    assert result["source_revision"] == PINNED_REVISION
    assert result["filters"] == {
        "area_index": 0,
        "record_index": None,
        "custom_record_id": None,
        "coordinate_word": 1,
        "value_byte": 0x05,
    }
    assert result["summary"]["matched_count"] == 2
    assert result["summary"]["source_record_count"] == 1
    assert result["summary"]["custom_record_count"] == 1
    assert [record["record_index"] for record in result["records"]] == [0]
    assert [record["custom_record_id"] for record in result["custom_records"]] == [
        custom_id
    ]
    assert result["evidence"]["rom_bytes_read"] is False
    assert result["evidence"]["rom_modified"] is False
    assert database.read_bytes() == database_before
    assert json_export.read_bytes() == export_before

    source_only = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_find_hidden_items",
                    {"record_index": 0},
                )
            )
        )
    )
    assert [record["record_index"] for record in source_only["records"]] == [0]
    assert source_only["custom_records"] == []

    custom_only = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_find_hidden_items",
                    {"custom_record_id": custom_id},
                )
            )
        )
    )
    assert custom_only["records"] == []
    assert [record["custom_record_id"] for record in custom_only["custom_records"]] == [
        custom_id
    ]
    assert database.read_bytes() == database_before
    assert json_export.read_bytes() == export_before


def test_mcp_overworld_row_update_previews_then_applies_explicitly(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_overworld_row_edit", tmp_path)
    _seed_semantic_model(database)
    server = create_server(database)
    original_database = database.read_bytes()
    original_export = json_export.read_bytes()

    arguments = {
        "record_index": 0,
        "coordinate_word": 0x1234,
        "value_byte": 0x84,
    }
    preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_update_hidden_item_record", arguments)
            )
        )
    )
    assert preview["action"] == "update_overworld_hidden_item"
    assert preview["dry_run"] is True
    assert preview["record_index"] == 0
    assert preview["before"]["coordinate_word"] == 1
    assert preview["before"]["value_byte"] == 0x05
    assert preview["proposed"]["coordinate_word"] == 0x1234
    assert preview["proposed"]["value_byte"] == 0x84
    assert preview["proposed"]["consumer_class"] == "extended_secret_selector"
    assert preview["proposed"]["selector_byte_offset"] == 4
    assert preview["proposed"]["replacement_table_index"] == 2
    assert preview["changed_fields"] == ["coordinate_word", "value_byte"]
    source_references = preview["source_references"]
    source_record_reference = source_references["record"]
    assert source_record_reference["record_kind"] == "imported_overworld_hidden_item"
    assert source_record_reference["record_index"] == 0
    assert source_record_reference["source_file"] == "Bank1B.asm"
    assert source_record_reference["source_revision"] == PINNED_REVISION
    assert source_record_reference["source_sha256"] == "0" * 64
    assert source_record_reference["source_label"] == "OverworldData_HiddenItems_Screen_00"
    assert source_record_reference["source_line"] == 500
    assert source_record_reference["source_file_offset_annotation"] == 0x0DC3F9
    assert source_record_reference["rom_offsets_verified"] is False
    assert source_record_reference["rom_bytes_read"] is False
    assert [reference["area_index"] for reference in source_references["areas"]] == [0, 1]
    assert [reference["target_label"] for reference in source_references["areas"]] == [
        "OverworldData_HiddenItems_Screen_00",
        "OverworldData_HiddenItems_Screen_00",
    ]
    assert source_references["areas"][0]["pointer_entry_file_offset_annotation"] == 0x0DC2F9
    assert source_references["areas"][1]["pointer_entry_file_offset_annotation"] == 0x0DC2FB
    assert source_references["areas"][0]["target_file_offset_annotation"] == 0x0DC3F9
    assert source_references["areas"][1]["target_file_offset_annotation"] == 0x0DC3F9
    assert source_references["areas"][0]["sentinel_file_offset_annotation"] == 0x0DC450
    assert source_references["areas"][1]["sentinel_file_offset_annotation"] == 0x0DC451
    assert [reference["source_record_count"] for reference in source_references["areas"]] == [1, 1]
    assert all(
        reference["rom_offsets_verified"] is False
        and reference["rom_bytes_read"] is False
        for reference in source_references["areas"]
    )
    assert source_references["rom_offsets_verified"] is False
    assert source_references["rom_bytes_read"] is False
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_update_hidden_item_record",
                    {
                        **arguments,
                        "expected_project_revision": preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert applied["record_index"] == 0
    assert applied["source_coordinate_word"] == 1
    assert applied["source_value_byte"] == 0x05
    assert applied["coordinate_word"] == 0x1234
    assert applied["value_byte"] == 0x84
    assert applied["consumer_class"] == "extended_secret_selector"
    assert applied["replacement_table_index"] == 2
    assert applied["replacement_word_value"] == 0xFFFF
    assert applied["canonical_item_id_resolved"] is False
    assert applied["is_modified"] is True
    assert applied["source_references"] == source_references

    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["summary"]["record_count"] == 351
    assert model["summary"]["modified_record_count"] == 1
    assert model["records"][0]["area_indices"] == [0, 1]
    assert model["areas"][0]["record_indices"] == [0]
    assert model["areas"][1]["record_indices"] == [0]
    exported = json.loads(json_export.read_text(encoding="utf-8"))
    assert exported["overworld_hidden_items"] == model


def test_mcp_dungeon_chest_list_can_select_one_source_entry(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_single_chest_read", tmp_path)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    server = create_server(database, REGISTRY_PATH)
    database_before = database.read_bytes()
    export_before = json_export.read_bytes()

    selected = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("dungeon_list_chest_records", {"table_index": 5})
            )
        )
    )
    assert selected["format"] == "zelda-suite-dungeon-chest-model"
    assert selected["source_revision"] == PINNED_REVISION
    assert selected["source_sha256"] == imported["source_sha256"]
    selected_entry = selected["entry"]
    source_entry = imported["entries"][5]
    assert selected_entry["table_index"] == 5
    assert selected_entry["source_literal_value"] == source_entry["source_literal_value"]
    assert selected_entry["source_room_value"] == source_entry["source_room_value"]
    assert selected["evidence"]["rom_modified"] is False

    full = json.loads(
        _tool_text(asyncio.run(server.call_tool("dungeon_list_chest_records", {})))
    )
    assert len(full["entries"]) == 168
    assert full["summary"]["entry_count"] == 168
    assert database.read_bytes() == database_before
    assert json_export.read_bytes() == export_before


def test_mcp_dungeon_chest_find_filters_raw_fields_without_mutation(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_find_chests", tmp_path)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    server = create_server(database, REGISTRY_PATH)
    database_before = database.read_bytes()
    export_before = json_export.read_bytes()

    target = imported["entries"][5]
    arguments = {
        "item_value": target["item_value"],
        "room_value": target["room_value"],
        "is_big_chest": target["is_big_chest"],
    }
    result = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_find_chest_records", arguments))
        )
    )
    expected = [
        record
        for record in imported["entries"]
        if record["item_value"] == arguments["item_value"]
        and record["room_value"] == arguments["room_value"]
        and record["is_big_chest"] is arguments["is_big_chest"]
    ]

    assert result["format"] == "zelda-suite-dungeon-chest-model"
    assert result["source_revision"] == PINNED_REVISION
    assert result["source_sha256"] == imported["source_sha256"]
    assert result["filters"] == arguments
    assert result["summary"] == {
        "matched_count": len(expected),
        "total_count": 168,
    }
    assert result["entries"] == expected
    assert [entry["table_index"] for entry in result["entries"]] == sorted(
        entry["table_index"] for entry in result["entries"]
    )
    assert result["evidence"]["rom_bytes_read"] is False
    assert result["evidence"]["rom_modified"] is False
    assert database.read_bytes() == database_before
    assert json_export.read_bytes() == export_before

    by_big_chest_flag = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_find_chest_records",
                    {"is_big_chest": target["is_big_chest"]},
                )
            )
        )
    )
    assert by_big_chest_flag["entries"] == [
        record
        for record in imported["entries"]
        if record["is_big_chest"] is target["is_big_chest"]
    ]
    assert database.read_bytes() == database_before
    assert json_export.read_bytes() == export_before


def test_mcp_chest_room_reference_audit_is_read_only_and_tracks_project_edits(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_chest_room_audit", tmp_path)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    server = create_server(database, REGISTRY_PATH)

    database_before_audit = database.read_bytes()
    export_before_audit = json_export.read_bytes()
    clean = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_audit_chest_room_references", {}))
        )
    )
    assert clean["format"] == "zelda-suite-project-dungeon-chest-room-reference-audit"
    assert clean["summary"]["chest_entry_count"] == 168
    assert clean["summary"]["chest_entries_with_pointer_slots"] == 168
    assert clean["summary"]["chest_entries_without_pointer_slots"] == 0
    assert clean["summary"]["error_count"] == 0
    assert clean["entries"][0]["source_room_value"] == 0x32
    assert clean["entries"][0]["room_value"] == 0x32
    assert clean["entries"][0]["room_value_in_pointer_tables"] is True
    assert clean["evidence"]["rom_bytes_read"] is False
    assert clean["evidence"]["rom_modified"] is False
    assert database.read_bytes() == database_before_audit
    assert json_export.read_bytes() == export_before_audit

    edit_arguments = {"table_index": 0, "room_value": 0x1234}
    edit_preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("dungeon_update_chest_record", edit_arguments)
            )
        )
    )
    edit = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {
                        **edit_arguments,
                        "expected_project_revision": edit_preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert edit["room_value"] == 0x1234
    database_after_edit = database.read_bytes()
    export_after_edit = json_export.read_bytes()

    edited = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_audit_chest_room_references", {}))
        )
    )
    first = edited["entries"][0]
    assert first["source_room_value"] == 0x32
    assert first["room_value"] == 0x1234
    assert first["is_modified"] is True
    assert first["room_pointer_table_index"] is None
    assert first["room_value_in_pointer_tables"] is False
    assert edited["summary"]["modified_record_count"] == 1
    assert edited["summary"]["chest_entries_without_pointer_slots"] == 1
    assert edited["findings"][0]["code"] == "room_value_out_of_pointer_range"
    assert edited["evidence"]["candidate_pointer_offsets_verified"] is False
    assert edited["evidence"]["room_payload_bytes_verified"] is False
    assert edited["evidence"]["rom_bytes_read"] is False
    assert edited["evidence"]["rom_modified"] is False
    assert database.read_bytes() == database_after_edit
    assert json_export.read_bytes() == export_after_edit


def test_mcp_dungeon_chest_update_previews_then_applies_explicitly(
    tmp_path: Path,
) -> None:
    database, json_export = initialize_project("mcp_dungeon_chest_edit", tmp_path)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    server = create_server(database)
    original_database = database.read_bytes()
    original_export = json_export.read_bytes()

    arguments = {
        "table_index": 0,
        "item_value": 0xAA,
        "room_value": 0x1234,
        "is_big_chest": True,
    }
    preview = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_update_chest_record", arguments))
        )
    )
    assert preview["action"] == "update_dungeon_chest_record"
    assert preview["dry_run"] is True
    assert preview["before"]["literal_value"] == 0x240032
    assert preview["proposed"]["literal_value"] == 0xAA9234
    assert preview["proposed"]["room_pointer_table_byte_displacement"] == 0x1234 * 3
    assert preview["changed_fields"] == ["item_value", "room_value", "is_big_chest"]
    source_references = preview["source_references"]
    source_record_reference = source_references["record"]
    assert source_record_reference["record_kind"] == "dungeon_chest_source_entry"
    assert source_record_reference["table_index"] == 0
    assert source_record_reference["source_file"] == imported["source_file"]
    assert source_record_reference["source_revision"] == imported["source_revision"]
    assert source_record_reference["source_sha256"] == imported["source_sha256"]
    assert source_record_reference["table_label"] == imported["table_label"]
    assert source_record_reference["source_line"] == preview["before"]["source_line"]
    assert source_record_reference["source_expression"] == preview["before"]["expression"]
    assert source_record_reference["candidate_entry_offset_annotation"] == (
        preview["before"]["candidate_entry_offset"]
    )
    assert source_record_reference["source_annotated_start_offset"] == (
        imported["source_annotated_start_offset"]
    )
    assert source_record_reference["rom_offsets_verified"] is False
    assert source_record_reference["rom_bytes_read"] is False
    assert source_references["rom_offsets_verified"] is False
    assert source_references["rom_bytes_read"] is False
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {
                        **arguments,
                        "expected_project_revision": preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert applied["table_index"] == 0
    assert applied["source_literal_value"] == 0x240032
    assert applied["source_item_value"] == 0x24
    assert applied["source_room_value"] == 0x32
    assert applied["source_is_big_chest"] is False
    assert applied["literal_value"] == 0xAA9234
    assert applied["expression"] == "$AA9234"
    assert applied["is_modified"] is True
    assert applied["source_references"] == source_references

    model = get_dungeon_chest_model(database)
    assert model is not None
    assert model["summary"]["modified_record_count"] == 1
    assert model["entries"][0]["literal_value"] == 0xAA9234
    assert json.loads(json_export.read_text(encoding="utf-8"))["dungeon_chests"] == model


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
    create_refs = preview["area_source_references"]
    assert [reference["area_index"] for reference in create_refs] == [4, 5]
    assert [reference["target_label"] for reference in create_refs] == [
        "OverworldData_HiddenItems_Screen_03",
        "OverworldData_HiddenItems_Screen_04",
    ]
    assert create_refs[0]["source_file"] == "Bank1B.asm"
    assert create_refs[0]["source_revision"] == PINNED_REVISION
    assert create_refs[0]["source_sha256"] == "0" * 64
    assert create_refs[0]["pointer_entry_file_offset_annotation"] == 0x0DC301
    assert create_refs[0]["target_file_offset_annotation"] == 0x0DC402
    assert create_refs[0]["sentinel_file_offset_annotation"] == 0x0DC454
    assert create_refs[0]["source_record_count"] == 1
    assert all(reference["rom_offsets_verified"] is False for reference in create_refs)
    assert all(reference["rom_bytes_read"] is False for reference in create_refs)
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_create_custom_hidden_item",
                    {
                        **create_arguments,
                        "expected_project_revision": preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    custom_id = applied["record"]["custom_record_id"]
    assert applied["dry_run"] is False
    assert applied["record"]["record_kind"] == "project_authored"
    assert applied["record"]["source_record_index"] is None
    assert applied["record"]["area_indices"] == [4, 5]
    assert applied["area_source_references"] == create_refs

    area_result = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_list_hidden_items", {"area_index": 4})
            )
        )
    )
    assert area_result["custom_records"][0]["custom_record_id"] == custom_id
    assert area_result["area"]["custom_record_ids"] == [custom_id]

    database_after_create = database.read_bytes()
    export_after_create = json_export.read_bytes()
    update_arguments = {
        "custom_record_id": custom_id,
        "area_indices": [6, 7],
        "coordinate_word": 0x2345,
        "value_byte": 0x84,
    }
    update_preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_update_custom_hidden_item", update_arguments)
            )
        )
    )
    assert update_preview["dry_run"] is True
    assert update_preview["before"]["area_indices"] == [4, 5]
    assert update_preview["proposed"]["area_indices"] == [6, 7]
    assert [
        reference["area_index"]
        for reference in update_preview["before_area_source_references"]
    ] == [4, 5]
    assert [
        reference["area_index"]
        for reference in update_preview["proposed_area_source_references"]
    ] == [6, 7]
    assert [
        reference["target_label"]
        for reference in update_preview["proposed_area_source_references"]
    ] == [
        "OverworldData_HiddenItems_Screen_05",
        "OverworldData_HiddenItems_Screen_06",
    ]
    assert all(
        reference["rom_offsets_verified"] is False
        and reference["rom_bytes_read"] is False
        for reference in (
            update_preview["before_area_source_references"]
            + update_preview["proposed_area_source_references"]
        )
    )
    assert update_preview["proposed"]["coordinate_word"] == 0x2345
    assert update_preview["proposed"]["value_byte"] == 0x84
    assert database.read_bytes() == database_after_create
    assert json_export.read_bytes() == export_after_create

    updated = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_update_custom_hidden_item",
                    {
                        **update_arguments,
                        "expected_project_revision": update_preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert updated["dry_run"] is False
    assert updated["record"]["area_indices"] == [6, 7]
    assert updated["record"]["coordinate_word"] == 0x2345
    assert updated["record"]["value_byte"] == 0x84
    assert updated["before_area_source_references"] == create_refs
    assert [
        reference["area_index"] for reference in updated["area_source_references"]
    ] == [6, 7]

    area_result = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("overworld_list_hidden_items", {"area_index": 6}))
        )
    )
    assert area_result["area"]["custom_record_ids"] == [custom_id]
    assert area_result["custom_records"][0]["consumer_class"] == "extended_secret_selector"

    delete_arguments = {"custom_record_id": custom_id}
    delete_preview = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool("overworld_delete_custom_hidden_item", delete_arguments)
            )
        )
    )
    assert delete_preview["dry_run"] is True
    assert delete_preview["record"]["area_indices"] == [6, 7]
    assert [
        reference["area_index"]
        for reference in delete_preview["area_source_references"]
    ] == [6, 7]
    assert all(
        reference["rom_offsets_verified"] is False
        for reference in delete_preview["area_source_references"]
    )

    deleted = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_delete_custom_hidden_item",
                    {
                        **delete_arguments,
                        "expected_project_revision": delete_preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert deleted["dry_run"] is False
    assert deleted["deleted"]["custom_record_id"] == custom_id
    assert deleted["area_source_references"] == delete_preview["area_source_references"]

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


def test_mcp_apply_rejects_stale_project_revision(tmp_path: Path) -> None:
    database, json_export = initialize_project("mcp_stale_revision", tmp_path)
    _seed_semantic_model(database)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    server = create_server(database, REGISTRY_PATH)

    arguments = {"table_index": 0, "item_value": 0xAA}
    preview = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_update_chest_record", arguments))
        )
    )
    revision = preview["project_revision"]
    assert len(revision) == 64
    assert all(character in "0123456789abcdef" for character in revision)

    # A separate edit to the overworld model invalidates the complete-project
    # revision even though the chest row being edited has not changed.
    update_overworld_hidden_item(
        database, 1, coordinate_word=0x4321, dry_run=False
    )
    database_after_other_edit = database.read_bytes()
    export_after_other_edit = json_export.read_bytes()

    with pytest.raises(ToolError, match="project revision changed since preview"):
        asyncio.run(
            server.call_tool(
                "dungeon_update_chest_record",
                {
                    **arguments,
                    "expected_project_revision": revision,
                    "apply": True,
                },
            )
        )
    assert database.read_bytes() == database_after_other_edit
    assert json_export.read_bytes() == export_after_other_edit

    # A current preview can be applied, and omission of the revision is refused.
    with pytest.raises(ToolError, match="expected_project_revision"):
        asyncio.run(
            server.call_tool(
                "dungeon_update_chest_record",
                {**arguments, "apply": True},
            )
        )
    assert database.read_bytes() == database_after_other_edit
    assert json_export.read_bytes() == export_after_other_edit

    current_preview = json.loads(
        _tool_text(
            asyncio.run(server.call_tool("dungeon_update_chest_record", arguments))
        )
    )
    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {
                        **arguments,
                        "expected_project_revision": current_preview["project_revision"],
                        "apply": True,
                    },
                )
            )
        )
    )
    assert applied["item_value"] == 0xAA
    assert applied["is_modified"] is True


def test_mcp_server_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="project database not found"):
        create_server(tmp_path / "missing.db")


def test_mcp_server_rejects_missing_asset_registry(tmp_path: Path) -> None:
    database, _json_export = initialize_project("mcp_missing_registry", tmp_path)
    with pytest.raises(FileNotFoundError, match="asset registry not found"):
        create_server(database, tmp_path / "missing-manifest.json")


def test_mcp_schema_does_not_offer_rom_or_import_tools(tmp_path: Path) -> None:
    database, _ = initialize_project("mcp_scope", tmp_path)
    server = create_server(database)
    names = {tool.name for tool in asyncio.run(server.list_tools())}

    assert not any("rom" in name.lower() for name in names)
    assert not any("import" in name.lower() for name in names)
    assert "update_overworld_hidden_item" not in names
    assert "update_dungeon_chest_record" not in names
