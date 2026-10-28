"""Tests for the source-only dungeon room object pointer inventory."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import (
    load_extracted_asset,
    load_source_export,
    parse_dl_pointer_table,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1F.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-object-pointers.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_OFFSET = 0x0F8000
TABLE_LABEL = "RoomData_ObjectDataPointers"


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_dungeon_pointer_export_matches_pinned_source() -> None:
    committed = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    parsed = parse_dl_pointer_table(
        source,
        TABLE_LABEL,
        TABLE_OFFSET,
        source_revision=PINNED_REVISION,
    )

    assert committed["format"] == "zelda-suite-pointer-table"
    assert committed["format_version"] == 1
    assert committed["source_file"] == "Bank1F.asm"
    assert committed["source_revision"] == PINNED_REVISION
    assert committed["table_label"] == TABLE_LABEL
    assert committed["table_file_offset"] == TABLE_OFFSET
    assert committed["entry_width"] == 3
    assert committed["entry_count"] == 320
    assert committed["entries"] == [entry.to_dict() for entry in parsed]
    assert committed["entries"][0]["pointer_entry_file_offset"] == 0x0F8000
    assert committed["entries"][5]["is_empty_target"] is True
    assert committed["entries"][-1]["table_index"] == 319
    assert committed["entries"][-1]["pointer_entry_file_offset"] == 0x0F83BD


def test_dungeon_pointer_export_is_registered_and_loadable() -> None:
    payload = load_extracted_asset("dungeon-room-object-pointers", REGISTRY_PATH)

    assert payload["entry_count"] == 320
    assert payload["table_label"] == TABLE_LABEL
    assert payload["entries"][5]["target_label"] == "RoomDataTiles_Empty"
