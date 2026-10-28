"""Tests for the source-only dungeon-room door-data pointer inventory."""
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
EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-room-door-pointers.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "RoomData_DoorDataPointers"
TABLE_FILE_OFFSET = 0x0F83C0


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_door_pointer_export_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_dl_pointer_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        source_revision=PINNED_REVISION,
    )

    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "Bank1F.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["table_label"] == TABLE_LABEL
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["entry_width"] == 3
    assert payload["entry_count"] == 320
    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert entries[0].pointer_expression == "RoomDataTiles_0000+$004D"
    assert entries[-1].pointer_entry_file_offset == 0x0F877D
    assert entries[-1].pointer_expression == "RoomDataTiles_Empty+$0008"


def test_committed_door_pointer_inventory_aligns_with_object_pointer_slots() -> None:
    door = load_extracted_asset("dungeon-room-door-pointers", REGISTRY_PATH)
    objects = load_extracted_asset("dungeon-room-object-pointers", REGISTRY_PATH)

    assert door["entry_count"] == 320
    assert door["table_label"] == TABLE_LABEL
    assert door["table_file_offset"] == TABLE_FILE_OFFSET
    assert door["entry_width"] == 3
    assert objects["entry_count"] == door["entry_count"]

    door_entries = door["entries"]
    object_entries = objects["entries"]
    assert [entry["target_label"] for entry in door_entries] == [
        entry["target_label"] for entry in object_entries
    ]
    assert len({entry["target_label"] for entry in door_entries}) == 263
    assert sum(entry["is_empty_target"] for entry in door_entries) == 39
    assert all(entry["target_addend"] is not None for entry in door_entries)
    assert door_entries[0]["pointer_entry_file_offset"] == TABLE_FILE_OFFSET
    assert door_entries[-1]["pointer_entry_file_offset"] == 0x0F877D


def test_door_pointer_addends_fit_source_annotated_payload_sizes() -> None:
    door = load_extracted_asset("dungeon-room-door-pointers", REGISTRY_PATH)
    asset_names = (
        "dungeon-room-payloads-bank03",
        "dungeon-room-payload-inventory",
        "dungeon-room-payloads-bank1f",
    )
    declarations_by_label: dict[str, dict[str, object]] = {}

    for asset_name in asset_names:
        inventory = load_extracted_asset(asset_name, REGISTRY_PATH)
        assert inventory["source_revision"] == door["source_revision"]
        for declaration in inventory["declarations"]:
            label = declaration["label"]
            assert label not in declarations_by_label, (
                f"duplicate room payload label: {label}"
            )
            declarations_by_label[label] = declaration

    assert len(declarations_by_label) == 266
    assert all(
        declaration["declared_size_bytes"] is not None
        for declaration in declarations_by_label.values()
    )

    for entry in door["entries"]:
        label = entry["target_label"]
        assert label in declarations_by_label, (
            f"door-pointer target has no payload declaration: {label}"
        )
        declaration = declarations_by_label[label]
        size = declaration["declared_size_bytes"]
        addend = entry["target_addend"]
        assert type(size) is int and size > 0
        assert type(addend) is int
        assert 0 <= addend < size, (
            f"slot {entry['table_index']} expression "
            f"{entry['pointer_expression']!r} has addend {addend}, "
            f"outside source-annotated payload size {size}"
        )
