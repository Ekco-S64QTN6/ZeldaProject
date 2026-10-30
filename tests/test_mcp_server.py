"""Contract tests for the opt-in project-bound MCP server."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from zelda_suite.mcp.server import create_server
from zelda_suite.project import (
    get_dungeon_chest_model,
    get_overworld_hidden_item_model,
    import_dungeon_chest_data,
    initialize_project,
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

    assert set(schemas) == {
        "project_validate",
        "project_list_source_assets",
        "project_get_source_asset",
        "overworld_list_hidden_items",
        "overworld_update_hidden_item_record",
        "dungeon_list_chest_records",
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

    chest_schema = schemas["dungeon_update_chest_record"]
    assert chest_schema["properties"]["apply"]["default"] is False
    assert chest_schema["properties"]["table_index"]["minimum"] == 0
    assert chest_schema["properties"]["table_index"]["maximum"] == 167
    assert chest_schema["properties"]["item_value"]["anyOf"][0]["maximum"] == 255
    assert chest_schema["properties"]["room_value"]["anyOf"][0]["maximum"] == 32767


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
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_update_hidden_item_record",
                    {**arguments, "apply": True},
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

    edit = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {"table_index": 0, "room_value": 0x1234, "apply": True},
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
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_export.read_bytes() == original_export

    applied = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "dungeon_update_chest_record",
                    {**arguments, "apply": True},
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
    assert update_preview["proposed"]["coordinate_word"] == 0x2345
    assert update_preview["proposed"]["value_byte"] == 0x84
    assert database.read_bytes() == database_after_create
    assert json_export.read_bytes() == export_after_create

    updated = json.loads(
        _tool_text(
            asyncio.run(
                server.call_tool(
                    "overworld_update_custom_hidden_item",
                    {**update_arguments, "apply": True},
                )
            )
        )
    )
    assert updated["dry_run"] is False
    assert updated["record"]["area_indices"] == [6, 7]
    assert updated["record"]["coordinate_word"] == 0x2345
    assert updated["record"]["value_byte"] == 0x84

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
