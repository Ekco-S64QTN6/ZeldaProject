"""Subprocess-level MCP stdio transport tests."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

from zelda_suite.project import import_dungeon_chest_data, initialize_project

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"


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
            assert "project_validate" in tool_names
            assert "dungeon_update_chest_record" in tool_names
            assert "dungeon_list_chest_records" in tool_names

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

            final_validation = _tool_json(
                await session.call_tool("project_validate", {})
            )
            assert final_validation == {"problems": [], "valid": True}


def test_mcp_stdio_client_session_lists_tools_and_applies_revision_bound_edit(
    tmp_path: Path,
) -> None:
    database, _json_export = initialize_project("mcp_stdio_integration", tmp_path)
    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168

    asyncio.run(_exercise_stdio_session(database))
