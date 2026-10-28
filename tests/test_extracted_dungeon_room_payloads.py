"""Tests for the source-only Bank0A dungeon room payload inventory."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import (
    load_extracted_asset,
    load_source_export,
    parse_incbin_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0A.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-payload-inventory.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_room_payload_inventory_matches_pinned_source() -> None:
    committed = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    parsed = parse_incbin_inventory(
        source,
        source_file="Bank0A.asm",
        source_revision=PINNED_REVISION,
    )
    records = [record.to_dict() for record in parsed]

    assert committed["format"] == "zelda-suite-incbin-inventory"
    assert committed["format_version"] == 1
    assert committed["source_file"] == "Bank0A.asm"
    assert committed["source_revision"] == PINNED_REVISION
    assert committed["declaration_count"] == 75
    assert committed["declarations"] == records
    assert all(record["incbin_path"].startswith("bin/rooms/") for record in records)
    assert len({record["label"] for record in records}) == 75
    assert len({record["incbin_path"] for record in records}) == 75

    # Bank0A source comments provide starts and Size annotations, but no explicit
    # end offsets. Computed ends remain diagnostics, not independently verified ranges.
    assert all(record["source_file_offset_start"] is not None for record in records)
    assert all(record["declared_size_bytes"] is not None for record in records)
    assert all(record["source_file_offset_end"] is None for record in records)
    assert all(record["source_range_size_matches"] is None for record in records)
    assert all(record["computed_file_offset_end"] is not None for record in records)


def test_room_payload_inventory_is_registered_and_loadable() -> None:
    payload = load_extracted_asset("dungeon-room-payload-inventory", REGISTRY_PATH)

    assert payload["declaration_count"] == 75
    assert payload["source_file"] == "Bank0A.asm"
    assert payload["declarations"][0]["label"] == "RoomDataTiles_0104"
    assert payload["declarations"][0]["incbin_path"] == "bin/rooms/room0104.bin"
