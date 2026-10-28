"""Parser-parity tests for source-only dungeon room payload inventories."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import (
    load_extracted_asset,
    load_source_export,
    parse_incbin_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "AsarUSALTTPDisassembly"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

CASES = (
    ("Bank03.asm", "dungeon-room-payloads-bank03", 34, "RoomDataTiles_0100"),
    ("Bank0A.asm", "dungeon-room-payload-inventory", 75, "RoomDataTiles_0104"),
    ("Bank1F.asm", "dungeon-room-payloads-bank1f", 157, "RoomDataTiles_Empty"),
)


@pytest.mark.parametrize(
    ("source_name", "asset_name", "expected_count", "first_label"),
    CASES,
)
def test_committed_room_payload_inventory_matches_pinned_source(
    source_name: str,
    asset_name: str,
    expected_count: int,
    first_label: str,
) -> None:
    source_path = REFERENCE / source_name
    if not source_path.is_file():
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")

    export_path = ROOT / "data" / "extracted" / f"{asset_name}.json"
    committed = load_source_export(export_path)
    source = source_path.read_text(encoding="utf-8")
    parsed = parse_incbin_inventory(
        source,
        source_file=source_name,
        source_revision=PINNED_REVISION,
    )
    records = [record.to_dict() for record in parsed]

    assert committed["format"] == "zelda-suite-incbin-inventory"
    assert committed["format_version"] == 1
    assert committed["source_file"] == source_name
    assert committed["source_revision"] == PINNED_REVISION
    assert committed["declaration_count"] == expected_count
    assert committed["declarations"] == records
    assert all(record["incbin_path"].startswith("bin/rooms/") for record in records)
    assert len({record["label"] for record in records}) == expected_count
    assert len({record["incbin_path"] for record in records}) == expected_count
    assert all(record["source_file_offset_start"] is not None for record in records)
    assert all(record["declared_size_bytes"] is not None for record in records)
    # Source comments give start address and size but no end address.
    assert all(record["source_file_offset_end"] is None for record in records)
    assert all(record["source_range_size_matches"] is None for record in records)
    assert all(record["computed_file_offset_end"] is not None for record in records)
    assert records[0]["label"] == first_label


@pytest.mark.parametrize(
    ("asset_name", "expected_count"),
    (
        ("dungeon-room-payloads-bank03", 34),
        ("dungeon-room-payload-inventory", 75),
        ("dungeon-room-payloads-bank1f", 157),
    ),
)
def test_room_payload_inventories_are_registered_and_loadable(
    asset_name: str, expected_count: int
) -> None:
    payload = load_extracted_asset(asset_name, REGISTRY_PATH)

    assert payload["declaration_count"] == expected_count
    assert all(
        declaration["incbin_path"].startswith("bin/rooms/")
        for declaration in payload["declarations"]
    )
