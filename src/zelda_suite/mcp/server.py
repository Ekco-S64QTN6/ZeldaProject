"""Opt-in stdio MCP server for a single ZeldaProject SQLite database.

The server deliberately binds one database at startup; model-provided tool
arguments cannot select arbitrary filesystem paths. ROM bytes are never read
or written by these tools.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from zelda_suite.project import (
    create_custom_overworld_hidden_item,
    delete_custom_overworld_hidden_item,
    get_dungeon_chest_model,
    get_overworld_hidden_item_model,
    get_source_asset,
    list_source_assets,
    update_custom_overworld_hidden_item,
    validate_project,
)


def _render_json(payload: Any) -> str:
    """Render tool results as deterministic, human-readable JSON text."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


def create_server(database_path: str | Path) -> FastMCP:
    """Build an MCP server bound to one existing project database."""
    db_path = Path(database_path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    server = FastMCP(
        "zelda-suite-project",
        instructions=(
            "You are connected to one explicitly configured ZeldaProject SQLite "
            "database. Read tools inspect the project and source metadata only. "
            "Project-authored custom hidden-item create/update/delete tools preview by "
            "default; set apply=true only when the user has approved persisting "
            "that project-local change. These tools never read, patch, rebuild, "
            "or write a ROM. Imported source rows and their source baselines are "
            "not editable through this MCP surface."
        ),
    )

    @server.tool()
    def project_validate() -> str:
        """Validate the bound SQLite project and canonical JSON sidecar without changing either."""
        problems = validate_project(db_path)
        return _render_json({"valid": not problems, "problems": problems})

    @server.tool()
    def project_list_source_assets() -> str:
        """List imported source-asset metadata in the bound project."""
        return _render_json(list_source_assets(db_path))

    @server.tool()
    def project_get_source_asset(asset_key: str) -> str:
        """Return one validated source-asset snapshot by its registered project key."""
        return _render_json(get_source_asset(db_path, asset_key))

    @server.tool()
    def overworld_list_hidden_items(
        area_index: Annotated[int, Field(strict=True, ge=0, le=127)] | None = None,
    ) -> str:
        """Read the imported overworld hidden-item model, optionally scoped to one area index."""
        model = get_overworld_hidden_item_model(db_path)
        if model is None:
            raise ValueError(
                "no overworld hidden-item model has been imported into this project"
            )
        if area_index is None:
            return _render_json(model)

        area = next(
            (entry for entry in model["areas"] if entry["area_index"] == area_index),
            None,
        )
        if area is None:
            raise KeyError(f"overworld area not found: {area_index}")
        records_by_index = {
            int(record["record_index"]): record for record in model["records"]
        }
        custom_records_by_id = {
            int(record["custom_record_id"]): record
            for record in model["custom_records"]
        }
        payload = {
            "format": model["format"],
            "format_version": model["format_version"],
            "source_file": model["source_file"],
            "source_revision": model["source_revision"],
            "source_sha256": model["source_sha256"],
            "area": area,
            "records": [
                records_by_index[index] for index in area["record_indices"]
            ],
            "custom_records": [
                custom_records_by_id[index] for index in area["custom_record_ids"]
            ],
            "evidence": model["evidence"],
        }
        return _render_json(payload)

    @server.tool()
    def dungeon_list_chest_records() -> str:
        """Read the imported 168-entry packed dungeon-chest model and its source baselines."""
        model = get_dungeon_chest_model(db_path)
        if model is None:
            raise ValueError(
                "no dungeon chest model has been imported into this project"
            )
        return _render_json(model)

    @server.tool()
    def overworld_create_custom_hidden_item(
        area_indices: Annotated[
            list[Annotated[int, Field(strict=True, ge=0, le=127)]],
            Field(min_length=1, max_length=128),
        ],
        coordinate_word: Annotated[int, Field(strict=True, ge=0, le=65534)],
        value_byte: Annotated[int, Field(strict=True, ge=0, le=255)],
        apply: Annotated[bool, Field(strict=True)] = False,
    ) -> str:
        """Preview a project-authored hidden-item addition; set apply=true to persist it.

        The entry is separate from imported source rows and has no source offset
        or canonical item ID. Multiple area indexes create an alias-aware project
        relationship. The default is a read-only preview.
        """
        result = create_custom_overworld_hidden_item(
            db_path,
            area_indices=area_indices,
            coordinate_word=coordinate_word,
            value_byte=value_byte,
            dry_run=not apply,
        )
        return _render_json(result)

    @server.tool()
    def overworld_update_custom_hidden_item(
        custom_record_id: Annotated[int, Field(strict=True, ge=1)],
        area_indices: Annotated[
            list[Annotated[int, Field(strict=True, ge=0, le=127)]],
            Field(min_length=1, max_length=128),
        ] | None = None,
        coordinate_word: Annotated[int, Field(strict=True, ge=0, le=65534)] | None = None,
        value_byte: Annotated[int, Field(strict=True, ge=0, le=255)] | None = None,
        apply: Annotated[bool, Field(strict=True)] = False,
    ) -> str:
        """Preview an edit to a project-authored hidden item; set apply=true to persist it.

        Omitted fields retain their current value. When area_indices is supplied,
        it replaces the complete many-to-many area-link set. Imported source
        records cannot be edited through this tool. The default is a read-only
        preview.
        """
        result = update_custom_overworld_hidden_item(
            db_path,
            custom_record_id,
            area_indices=area_indices,
            coordinate_word=coordinate_word,
            value_byte=value_byte,
            dry_run=not apply,
        )
        return _render_json(result)

    @server.tool()
    def overworld_delete_custom_hidden_item(
        custom_record_id: Annotated[int, Field(strict=True, ge=1)],
        apply: Annotated[bool, Field(strict=True)] = False,
    ) -> str:
        """Preview deletion of a project-authored hidden item; set apply=true to persist it.

        Only a custom record ID is accepted. Source record indexes cannot be
        deleted. The default is a read-only preview.
        """
        result = delete_custom_overworld_hidden_item(
            db_path,
            custom_record_id,
            dry_run=not apply,
        )
        return _render_json(result)

    return server


def main() -> None:
    """Run the bound project MCP server over stdio."""
    parser = argparse.ArgumentParser(
        description="Expose bounded ZeldaProject APIs as an opt-in stdio MCP server."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=(
            "Existing project SQLite database. May also be supplied through "
            "ZELDA_SUITE_PROJECT_DB."
        ),
    )
    args = parser.parse_args()
    database_path = args.database or os.environ.get("ZELDA_SUITE_PROJECT_DB")
    if database_path is None:
        parser.error(
            "provide --database PATH or set ZELDA_SUITE_PROJECT_DB; "
            "the server never guesses which project to open"
        )
    try:
        server = create_server(database_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        parser.error(str(exc))
    server.run(transport="stdio")
