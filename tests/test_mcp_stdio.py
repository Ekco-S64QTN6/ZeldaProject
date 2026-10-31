"""Subprocess-level MCP stdio transport tests."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

from zelda_suite.project import (
    import_dungeon_chest_data,
    import_overworld_hidden_item_model,
    initialize_project,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
OVERWORLD_SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
)


def _tool_json(result: CallToolResult) -> dict[str, object]:
    assert not result.isError
    assert result.content
    content = result.content[0]
    assert isinstance(content, TextContent)
    return json.loads(content.text)


async def _exercise_stdio_session(database_path: Path) -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "zelda_suite.mcp.server",
            "--database",
            str(database_path),
            "--registry",
            str(REGISTRY_PATH),
        ],
        env={"PYTHONPATH": str(ROOT / "src")},
        cwd=ROOT,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tool_list = await session.list_tools()
        tool_names = {tool.name for tool in tool_list.tools}
        tool_descriptions = {
            tool.name: tool.description or "" for tool in tool_list.tools
        }
        assert "source_references" in tool_descriptions["overworld_update_hidden_item_record"]
        assert "source_references" in tool_descriptions["dungeon_update_chest_record"]
        assert "project_validate" in tool_names
        assert "dungeon_update_chest_record" in tool_names
        assert "dungeon_list_chest_records" in tool_names
        assert "overworld_update_hidden_item_record" in tool_names
        assert "overworld_create_custom_hidden_item" in tool_names
        assert "overworld_update_custom_hidden_item" in tool_names
        assert "overworld_delete_custom_hidden_item" in tool_names
        assert "overworld_find_hidden_items" in tool_names

        initial_validation = _tool_json(
            await session.call_tool("project_validate", {})
        )
        assert initial_validation == {"problems": [], "valid": True}

        arguments = {"table_index": 0, "item_value": 0xAA}
        preview = _tool_json(
            await session.call_tool("dungeon_update_chest_record", arguments)
        )
        assert preview["dry_run"] is True
        assert preview["rom_modified"] is False
        revision = preview["project_revision"]
        assert isinstance(revision, str) and len(revision) == 64

        missing_revision = await session.call_tool(
            "dungeon_update_chest_record",
            {**arguments, "apply": True},
        )
        assert missing_revision.isError is True
        assert missing_revision.content
        error_content = missing_revision.content[0]
        assert isinstance(error_content, TextContent)
        assert "expected_project_revision" in error_content.text

        applied = _tool_json(
            await session.call_tool(
                "dungeon_update_chest_record",
                {
                    **arguments,
                    "expected_project_revision": revision,
                    "apply": True,
                },
            )
        )
        assert applied["table_index"] == 0
        assert applied["item_value"] == 0xAA
        assert applied["is_modified"] is True

        selected = _tool_json(
            await session.call_tool(
                "dungeon_list_chest_records", {"table_index": 0}
            )
        )
        assert selected["entry"]["item_value"] == 0xAA
        assert selected["evidence"]["rom_modified"] is False
        chest_source_references = applied["source_references"]
        chest_source_record = chest_source_references["record"]
        assert chest_source_record["record_kind"] == "dungeon_chest_source_entry"
        assert chest_source_record["table_index"] == 0
        assert chest_source_record["source_file"] == imported["source_file"]
        assert chest_source_record["source_revision"] == imported["source_revision"]
        assert chest_source_record["source_sha256"] == imported["source_sha256"]
        assert chest_source_record["source_line"] > 0
        assert chest_source_record["source_expression"]
        assert chest_source_record["candidate_entry_offset_annotation"] > 0
        assert chest_source_references["rom_offsets_verified"] is False
        assert chest_source_references["rom_bytes_read"] is False
        assert chest_source_record["rom_offsets_verified"] is False
        assert chest_source_record["rom_bytes_read"] is False
        assert preview["source_references"] == applied["source_references"]

        # Imported source-row edit: keep the source identity and annotations
        # visible in the same stdio preview that supplies the apply fingerprint.
        overworld_arguments = {"record_index": 0, "coordinate_word": 0x1234}
        overworld_preview = _tool_json(
            await session.call_tool(
                "overworld_update_hidden_item_record", overworld_arguments
            )
        )
        assert overworld_preview["dry_run"] is True
        assert overworld_preview["before"]["record_index"] == 0
        assert overworld_preview["before"]["source_label"]
        assert overworld_preview["before"]["source_line"] > 0
        assert overworld_preview["before"]["source_file_offset"] > 0
        assert overworld_preview["proposed"]["coordinate_word"] == 0x1234
        overworld_source_references = overworld_preview["source_references"]
        source_record = overworld_source_references["record"]
        assert source_record["record_kind"] == "imported_overworld_hidden_item"
        assert source_record["record_index"] == 0
        assert source_record["source_file"] == "Bank1B.asm"
        assert source_record["source_revision"] == imported_overworld["source_revision"]
        assert source_record["source_sha256"] == imported_overworld["source_sha256"]
        assert source_record["source_label"] == overworld_preview["before"]["source_label"]
        assert source_record["source_line"] == overworld_preview["before"]["source_line"]
        assert source_record["source_file_offset_annotation"] == (
            overworld_preview["before"]["source_file_offset"]
        )
        assert [area["area_index"] for area in overworld_source_references["areas"]] == (
            overworld_preview["before"]["area_indices"]
        )
        assert all(area["target_label"] for area in overworld_source_references["areas"])
        assert all(
            area["rom_offsets_verified"] is False and area["rom_bytes_read"] is False
            for area in overworld_source_references["areas"]
        )
        assert source_record["rom_offsets_verified"] is False
        assert source_record["rom_bytes_read"] is False
        assert overworld_source_references["rom_offsets_verified"] is False
        assert overworld_source_references["rom_bytes_read"] is False
        overworld_applied = _tool_json(
            await session.call_tool(
                "overworld_update_hidden_item_record",
                {
                    **overworld_arguments,
                    "expected_project_revision": overworld_preview["project_revision"],
                    "apply": True,
                },
            )
        )
        assert overworld_applied["record_index"] == 0
        assert overworld_applied["coordinate_word"] == 0x1234
        assert overworld_applied["is_modified"] is True
        assert overworld_applied["source_references"] == overworld_source_references
        found_source = _tool_json(
            await session.call_tool(
                "overworld_find_hidden_items", {"record_index": 0}
            )
        )
        assert found_source["records"][0]["coordinate_word"] == 0x1234
        assert found_source["custom_records"] == []

        # Project-authored hidden-item create/update/delete: the stdio preview
        # carries source-area references, but clearly labels them as annotations.
        create_arguments = {
            "area_indices": [0, 1],
            "coordinate_word": 0x5678,
            "value_byte": 0x05,
        }
        create_preview = _tool_json(
            await session.call_tool(
                "overworld_create_custom_hidden_item", create_arguments
            )
        )
        assert create_preview["dry_run"] is True
        assert [
            reference["area_index"]
            for reference in create_preview["area_source_references"]
        ] == [0, 1]
        first_area_reference = create_preview["area_source_references"][0]
        assert first_area_reference["source_file"] == "Bank1B.asm"
        assert first_area_reference["source_revision"]
        assert first_area_reference["target_label"]
        assert first_area_reference["rom_offsets_verified"] is False
        assert first_area_reference["rom_bytes_read"] is False
        created = _tool_json(
            await session.call_tool(
                "overworld_create_custom_hidden_item",
                {
                    **create_arguments,
                    "expected_project_revision": create_preview["project_revision"],
                    "apply": True,
                },
            )
        )
        custom_id = created["record"]["custom_record_id"]
        assert (
            created["area_source_references"]
            == create_preview["area_source_references"]
        )
        found_custom = _tool_json(
            await session.call_tool(
                "overworld_find_hidden_items", {"custom_record_id": custom_id}
            )
        )
        assert found_custom["records"] == []
        assert found_custom["custom_records"][0]["custom_record_id"] == custom_id
        assert found_custom["custom_records"][0]["area_indices"] == [0, 1]

        update_arguments = {
            "custom_record_id": custom_id,
            "area_indices": [2, 3],
            "coordinate_word": 0x6789,
            "value_byte": 0x84,
        }
        update_preview = _tool_json(
            await session.call_tool(
                "overworld_update_custom_hidden_item", update_arguments
            )
        )
        assert [
            reference["area_index"]
            for reference in update_preview["before_area_source_references"]
        ] == [0, 1]
        assert [
            reference["area_index"]
            for reference in update_preview["proposed_area_source_references"]
        ] == [2, 3]
        updated = _tool_json(
            await session.call_tool(
                "overworld_update_custom_hidden_item",
                {
                    **update_arguments,
                    "expected_project_revision": update_preview["project_revision"],
                    "apply": True,
                },
            )
        )
        assert updated["record"]["area_indices"] == [2, 3]
        assert updated["before_area_source_references"] == (
            update_preview["before_area_source_references"]
        )
        assert updated["area_source_references"] == (
            update_preview["proposed_area_source_references"]
        )
        found_updated_custom = _tool_json(
            await session.call_tool(
                "overworld_find_hidden_items", {"custom_record_id": custom_id}
            )
        )
        assert found_updated_custom["custom_records"][0]["area_indices"] == [2, 3]
        assert [
            reference["area_index"]
            for reference in updated["area_source_references"]
        ] == [2, 3]

        delete_arguments = {"custom_record_id": custom_id}
        delete_preview = _tool_json(
            await session.call_tool(
                "overworld_delete_custom_hidden_item", delete_arguments
            )
        )
        assert [
            reference["area_index"]
            for reference in delete_preview["area_source_references"]
        ] == [2, 3]
        deleted = _tool_json(
            await session.call_tool(
                "overworld_delete_custom_hidden_item",
                {
                    **delete_arguments,
                    "expected_project_revision": delete_preview["project_revision"],
                    "apply": True,
                },
            )
        )
        assert deleted["deleted"]["custom_record_id"] == custom_id
        assert (
            deleted["area_source_references"]
            == delete_preview["area_source_references"]
        )
        not_found_custom = _tool_json(
            await session.call_tool(
                "overworld_find_hidden_items", {"custom_record_id": custom_id}
            )
        )
        assert not_found_custom["summary"]["matched_count"] == 0
        assert not_found_custom["records"] == []
        assert not_found_custom["custom_records"] == []

        final_overworld = _tool_json(
            await session.call_tool("overworld_list_hidden_items", {})
        )
        assert final_overworld["summary"]["record_count"] == 351
        assert final_overworld["summary"]["custom_record_count"] == 0
        final_validation = _tool_json(
            await session.call_tool("project_validate", {})
        )
        assert final_validation == {"problems": [], "valid": True}


def test_mcp_stdio_client_session_exercises_all_authoring_flows(
    tmp_path: Path,
) -> None:
    if not OVERWORLD_SOURCE_PATH.is_file():
        pytest.skip("pinned Asar submodule is not checked out")
    database, _json_export = initialize_project("mcp_stdio_integration", tmp_path)
    imported_overworld = import_overworld_hidden_item_model(
        database, OVERWORLD_SOURCE_PATH, dry_run=False
    )
    assert imported_overworld["summary"]["record_count"] == 351
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168

    asyncio.run(_exercise_stdio_session(database))
