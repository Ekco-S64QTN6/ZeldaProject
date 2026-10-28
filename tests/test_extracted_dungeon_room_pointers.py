"""Tests for the source-only dungeon room object pointer inventory."""
from __future__ import annotations

import re
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


BANK03_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank03.asm"
BANK0A_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0A.asm"
ROOM_PAYLOAD_EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-payload-inventory.json"
ROOM_PAYLOAD_BANK03_EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-payloads-bank03.json"
ROOM_PAYLOAD_BANK1F_EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-payloads-bank1f.json"


@pytest.mark.skipif(
    not all(path.is_file() for path in (BANK03_PATH, BANK0A_PATH, SOURCE_PATH)),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_all_dungeon_pointer_targets_have_pinned_source_definitions() -> None:
    pointers = load_source_export(EXPORT_PATH)
    room_payloads = load_source_export(ROOM_PAYLOAD_EXPORT_PATH)

    source_labels: set[str] = set()
    labels_by_file: dict[str, set[str]] = {}
    for path in (BANK03_PATH, BANK0A_PATH, SOURCE_PATH):
        labels = {
            match.group(1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if (
                match := re.fullmatch(
                    r"\s*(RoomDataTiles_[A-Za-z0-9_]+)\s*:\s*",
                    line.split(";", 1)[0],
                )
            )
        }
        labels_by_file[path.name] = labels
        source_labels.update(labels)

    target_labels = {entry["target_label"] for entry in pointers["entries"]}

    assert len(labels_by_file["Bank03.asm"]) == 34
    assert len(labels_by_file["Bank0A.asm"]) == 75
    assert len(labels_by_file["Bank1F.asm"]) == 157
    assert len(source_labels) == 266
    assert len(target_labels) == 263
    assert target_labels <= source_labels
    assert sorted(source_labels - target_labels) == [
        "RoomDataTiles_Orphan",
        "RoomDataTiles_Zarby89",
        "RoomDataTiles_Zarby90",
    ]
    payload_exports = [
        room_payloads,
        load_source_export(ROOM_PAYLOAD_BANK03_EXPORT_PATH),
        load_source_export(ROOM_PAYLOAD_BANK1F_EXPORT_PATH),
    ]
    payload_labels = {
        declaration["label"]
        for payload in payload_exports
        for declaration in payload["declarations"]
    }

    # The three registered payload inventories account for every source label.
    # All pointer targets are among those labels; only three definitions are not
    # referenced by the table. This remains source-symbol verification only.
    assert payload_labels == source_labels
    assert target_labels <= payload_labels
    assert payload_labels - target_labels == {
        "RoomDataTiles_Orphan",
        "RoomDataTiles_Zarby89",
        "RoomDataTiles_Zarby90",
    }
    assert {
        declaration["label"] for declaration in room_payloads["declarations"]
    } <= target_labels


def test_dungeon_pointer_export_is_registered_and_loadable() -> None:
    payload = load_extracted_asset("dungeon-room-object-pointers", REGISTRY_PATH)

    assert payload["entry_count"] == 320
    assert payload["table_label"] == TABLE_LABEL
    assert payload["entries"][5]["target_label"] == "RoomDataTiles_Empty"
