"""Opt-in stdio MCP server bound to one ZeldaProject database and asset registry.

The server deliberately binds both paths at startup; model-provided tool
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
    audit_project_dungeon_chest_room_references,
    create_custom_overworld_hidden_item,
    delete_custom_overworld_hidden_item,
    get_dungeon_chest_model,
    get_overworld_hidden_item_model,
    get_source_asset,
    list_source_assets,
    update_custom_overworld_hidden_item,
    update_dungeon_chest_record,
    update_overworld_hidden_item,
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


def _require_preview_revision(
    apply: bool,
    expected_project_revision: str | None,
) -> None:
    """Require every MCP apply to carry the fingerprint from its approved preview."""
    if apply and expected_project_revision is None:
        raise ValueError(
            "apply=true requires expected_project_revision from the current preview"
        )
    if not apply and expected_project_revision is not None:
        raise ValueError(
            "expected_project_revision may only be supplied with apply=true"
        )


def create_server(
    database_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
) -> FastMCP:
    """Build an MCP server bound to one project database and asset registry."""
    db_path = Path(database_path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    asset_registry_path = Path(registry_path).expanduser().resolve()
    if not asset_registry_path.is_file():
        raise FileNotFoundError(f"asset registry not found: {asset_registry_path}")

    server = FastMCP(
        "zelda-suite-project",
        instructions=(
            "You are connected to one explicitly configured ZeldaProject SQLite "
            "database. Read tools inspect the project and source metadata only. "
            "Project-authored custom hidden-item changes and packed dungeon-chest "
            "field edits preview by default; set apply=true only when the user has "
            "approved persisting that project-local change. Imported overworld "
            "record edits preserve source fields and area aliases; chest edits "
            "preserve their source baseline. These tools never read, patch, "
            "rebuild, or write a ROM."
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
    def overworld_find_hidden_items(
        area_index: Annotated[int, Field(strict=True, ge=0, le=127)] | None = None,
        record_index: Annotated[int, Field(strict=True, ge=0, le=350)] | None = None,
        custom_record_id: Annotated[int, Field(strict=True, ge=1)] | None = None,
        coordinate_word: Annotated[int, Field(strict=True, ge=0, le=65534)] | None = None,
        value_byte: Annotated[int, Field(strict=True, ge=0, le=255)] | None = None,
    ) -> str:
        """Find imported or project-authored hidden items by bounded raw fields.

        At least one filter is required. Source and custom record identifiers
        are mutually exclusive. Other supplied filters combine with AND logic.
        Results retain source order, provenance, and raw semantic annotations;
        the tool never changes project files or accesses a ROM.
        """
        if all(
            value is None
            for value in (
                area_index,
                record_index,
                custom_record_id,
                coordinate_word,
                value_byte,
            )
        ):
            raise ValueError("supply at least one hidden-item filter")
        if record_index is not None and custom_record_id is not None:
            raise ValueError("record_index and custom_record_id are mutually exclusive")

        model = get_overworld_hidden_item_model(db_path)
        if model is None:
            raise ValueError("no overworld hidden-item model has been imported")

        def matches(record: dict[str, Any]) -> bool:
            return (
                (area_index is None or area_index in record["area_indices"])
                and (
                    coordinate_word is None
                    or record["coordinate_word"] == coordinate_word
                )
                and (value_byte is None or record["value_byte"] == value_byte)
            )

        source_records = (
            []
            if custom_record_id is not None
            else [
                record
                for record in model["records"]
                if (record_index is None or record["record_index"] == record_index)
                and matches(record)
            ]
        )
        custom_records = (
            []
            if record_index is not None
            else [
                record
                for record in model["custom_records"]
                if (
                    custom_record_id is None
                    or record["custom_record_id"] == custom_record_id
                )
                and matches(record)
            ]
        )
        return _render_json(
            {
                "format": model["format"],
                "format_version": model["format_version"],
                "source_file": model["source_file"],
                "source_revision": model["source_revision"],
                "source_sha256": model["source_sha256"],
                "filters": {
                    "area_index": area_index,
                    "record_index": record_index,
                    "custom_record_id": custom_record_id,
                    "coordinate_word": coordinate_word,
                    "value_byte": value_byte,
                },
                "summary": {
                    "matched_count": len(source_records) + len(custom_records),
                    "source_record_count": len(source_records),
                    "custom_record_count": len(custom_records),
                    "total_source_record_count": len(model["records"]),
                    "total_custom_record_count": len(model["custom_records"]),
                },
                "records": source_records,
                "custom_records": custom_records,
                "evidence": model["evidence"],
            }
        )

    @server.tool()
    def overworld_update_hidden_item_record(
        record_index: Annotated[int, Field(strict=True, ge=0, le=350)],
        coordinate_word: Annotated[int, Field(strict=True, ge=0, le=65534)] | None = None,
        value_byte: Annotated[int, Field(strict=True, ge=0, le=255)] | None = None,
        apply: Annotated[bool, Field(strict=True)] = False,
        expected_project_revision: Annotated[
            str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")
        ] | None = None,
    ) -> str:
        """Preview an edit to an imported overworld row; set apply=true to persist it.

        The source coordinate/value fields and existing area aliases remain
        immutable. Consumer classification is recalculated for the proposed
        value byte. $FFFF is reserved as the list sentinel; the byte is raw
        source data, not a canonical item ID. This tool changes SQLite/JSON only.
        """
        _require_preview_revision(apply, expected_project_revision)
        result = update_overworld_hidden_item(
            db_path,
            record_index,
            coordinate_word=coordinate_word,
            value_byte=value_byte,
            expected_project_revision=expected_project_revision,
            dry_run=not apply,
        )
        return _render_json(result)

    @server.tool()
    def dungeon_audit_chest_room_references() -> str:
        """Audit current project chest room values against registered source pointer tables.

        The report preserves source room baselines and surfaces out-of-range or
        mismatched object/door target labels. It reads only project metadata and
        the asset registry fixed at server startup; candidate offsets and room
        payload bytes are not verified, and no ROM is read or modified.
        """
        report = audit_project_dungeon_chest_room_references(
            db_path, asset_registry_path
        )
        return _render_json(report)

    @server.tool()
    def dungeon_list_chest_records(
        table_index: Annotated[int, Field(strict=True, ge=0, le=167)] | None = None,
    ) -> str:
        """Read the imported chest model, optionally selecting one source table index.

        Omitting table_index returns the complete 168-entry model. Supplying an
        index returns that entry with the model's source provenance and evidence.
        """
        model = get_dungeon_chest_model(db_path)
        if model is None:
            raise ValueError(
                "no dungeon chest model has been imported into this project"
            )
        if table_index is None:
            return _render_json(model)

        entry = next(
            (
                record for record in model["entries"]
                if record["table_index"] == table_index
            ),
            None,
        )
        if entry is None:
            raise KeyError(f"dungeon chest record not found: {table_index}")
        return _render_json(
            {
                "format": model["format"],
                "format_version": model["format_version"],
                "source_file": model["source_file"],
                "source_revision": model["source_revision"],
                "source_sha256": model["source_sha256"],
                "entry": entry,
                "evidence": model["evidence"],
            }
        )

    @server.tool()
    def dungeon_find_chest_records(
        item_value: Annotated[int, Field(strict=True, ge=0, le=255)] | None = None,
        room_value: Annotated[int, Field(strict=True, ge=0, le=32767)] | None = None,
        is_big_chest: Annotated[bool, Field(strict=True)] | None = None,
    ) -> str:
        """Find chest entries by one or more bounded raw packed fields.

        At least one filter is required. Results retain source-order indexes,
        source baselines, provenance, and evidence; this tool is read-only.
        Item bytes and room values remain raw fields, not resolved game entities.
        """
        if item_value is None and room_value is None and is_big_chest is None:
            raise ValueError("supply item_value, room_value, or is_big_chest")
        model = get_dungeon_chest_model(db_path)
        if model is None:
            raise ValueError("no dungeon chest model has been imported")
        entries = [
            record
            for record in model["entries"]
            if (item_value is None or record["item_value"] == item_value)
            and (room_value is None or record["room_value"] == room_value)
            and (
                is_big_chest is None
                or record["is_big_chest"] is is_big_chest
            )
        ]
        return _render_json(
            {
                "format": model["format"],
                "format_version": model["format_version"],
                "source_file": model["source_file"],
                "source_revision": model["source_revision"],
                "source_sha256": model["source_sha256"],
                "filters": {
                    "item_value": item_value,
                    "room_value": room_value,
                    "is_big_chest": is_big_chest,
                },
                "summary": {
                    "matched_count": len(entries),
                    "total_count": len(model["entries"]),
                },
                "entries": entries,
                "evidence": model["evidence"],
            }
        )

    @server.tool()
    def dungeon_update_chest_record(
        table_index: Annotated[int, Field(strict=True, ge=0, le=167)],
        item_value: Annotated[int, Field(strict=True, ge=0, le=255)] | None = None,
        room_value: Annotated[int, Field(strict=True, ge=0, le=32767)] | None = None,
        is_big_chest: Annotated[bool, Field(strict=True)] | None = None,
        apply: Annotated[bool, Field(strict=True)] = False,
        expected_project_revision: Annotated[
            str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")
        ] | None = None,
    ) -> str:
        """Preview a packed chest-field edit; set apply=true to persist it.

        The item byte, room value, and big-chest flag are bounded project fields.
        The recomposed 24-bit value is stored only in SQLite/JSON; source literal
        and source field baselines remain unchanged. This tool does not resolve
        canonical item names or playable-room semantics and never writes a ROM.
        """
        _require_preview_revision(apply, expected_project_revision)
        result = update_dungeon_chest_record(
            db_path,
            table_index,
            item_value=item_value,
            room_value=room_value,
            is_big_chest=is_big_chest,
            expected_project_revision=expected_project_revision,
            dry_run=not apply,
        )
        return _render_json(result)

    @server.tool()
    def overworld_create_custom_hidden_item(
        area_indices: Annotated[
            list[Annotated[int, Field(strict=True, ge=0, le=127)]],
            Field(min_length=1, max_length=128),
        ],
        coordinate_word: Annotated[int, Field(strict=True, ge=0, le=65534)],
        value_byte: Annotated[int, Field(strict=True, ge=0, le=255)],
        apply: Annotated[bool, Field(strict=True)] = False,
        expected_project_revision: Annotated[
            str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")
        ] | None = None,
    ) -> str:
        """Preview a project-authored hidden-item addition; set apply=true to persist it.

        The entry is separate from imported source rows and has no source offset
        or canonical item ID. Multiple area indexes create an alias-aware project
        relationship. The default is a read-only preview.
        """
        _require_preview_revision(apply, expected_project_revision)
        result = create_custom_overworld_hidden_item(
            db_path,
            area_indices=area_indices,
            coordinate_word=coordinate_word,
            value_byte=value_byte,
            expected_project_revision=expected_project_revision,
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
        expected_project_revision: Annotated[
            str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")
        ] | None = None,
    ) -> str:
        """Preview an edit to a project-authored hidden item; set apply=true to persist it.

        Omitted fields retain their current value. When area_indices is supplied,
        it replaces the complete many-to-many area-link set. Imported source
        records cannot be edited through this tool. The default is a read-only
        preview.
        """
        _require_preview_revision(apply, expected_project_revision)
        result = update_custom_overworld_hidden_item(
            db_path,
            custom_record_id,
            area_indices=area_indices,
            coordinate_word=coordinate_word,
            value_byte=value_byte,
            expected_project_revision=expected_project_revision,
            dry_run=not apply,
        )
        return _render_json(result)

    @server.tool()
    def overworld_delete_custom_hidden_item(
        custom_record_id: Annotated[int, Field(strict=True, ge=1)],
        apply: Annotated[bool, Field(strict=True)] = False,
        expected_project_revision: Annotated[
            str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")
        ] | None = None,
    ) -> str:
        """Preview deletion of a project-authored hidden item; set apply=true to persist it.

        Only a custom record ID is accepted. Source record indexes cannot be
        deleted. The default is a read-only preview.
        """
        _require_preview_revision(apply, expected_project_revision)
        result = delete_custom_overworld_hidden_item(
            db_path,
            custom_record_id,
            expected_project_revision=expected_project_revision,
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
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help=(
            "Registered source-asset manifest used by the read-only chest/room "
            "audit. May also be supplied through ZELDA_SUITE_ASSET_REGISTRY."
        ),
    )
    args = parser.parse_args()
    database_path = args.database or os.environ.get("ZELDA_SUITE_PROJECT_DB")
    registry_path = (
        args.registry
        or os.environ.get("ZELDA_SUITE_ASSET_REGISTRY")
        or Path("data/extracted/manifest.json")
    )
    if database_path is None:
        parser.error(
            "provide --database PATH or set ZELDA_SUITE_PROJECT_DB; "
            "the server never guesses which project to open"
        )
    try:
        server = create_server(database_path, registry_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        parser.error(str(exc))
    server.run(transport="stdio")
