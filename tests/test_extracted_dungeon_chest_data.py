"""Regression baseline for Bank01.asm Dungeon_ChestData."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_dungeon_chest_data

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "dungeon-chest-data.json"
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank01.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_committed_chest_export_pins_168_records_and_packed_fields() -> None:
    payload = load_source_export(EXPORT_PATH)
    entries = payload["entries"]

    assert payload["source_file"] == "Bank01.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["table_label"] == "Dungeon_ChestData"
    assert payload["source_range_annotation"] == "$00E96E-$00EB65"
    assert payload["source_annotated_start_offset"] == 0x00E96E
    assert payload["source_annotated_end_offset"] == 0x00EB65
    assert payload["table_size_bytes"] == 504
    assert payload["entry_width_bytes"] == 3
    assert payload["entry_count"] == 168
    assert [entry["table_index"] for entry in entries] == list(range(168))
    assert [entry["candidate_entry_offset"] for entry in entries] == [
        0x00E96E + 3 * index for index in range(168)
    ]
    assert entries[0]["expression"] == "$240032"
    assert entries[0]["item_value"] == 0x24
    assert entries[0]["room_value"] == 0x32
    assert entries[0]["is_big_chest"] is False
    assert entries[-1]["expression"] == "$440011"
    assert entries[-1]["item_value"] == 0x44
    assert entries[-1]["room_value"] == 0x11
    assert not entries[-1]["is_big_chest"]
    assert sum(entry["is_big_chest"] for entry in entries) == 11
    assert {entry["item_value"] for entry in entries} == {
        0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x12, 0x15, 0x16,
        0x17, 0x18, 0x19, 0x1B, 0x1C, 0x1F, 0x22, 0x23, 0x24, 0x25,
        0x28, 0x2A, 0x32, 0x33, 0x34, 0x35, 0x36, 0x3F, 0x40,
        0x41, 0x43, 0x44, 0x46,
    }
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "source_range_offsets_verified": False,
        "item_value_names_resolved": False,
        "room_values_verified_against_rom": False,
    }


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_chest_export_matches_pinned_source_and_consumer() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    payload = load_source_export(EXPORT_PATH)
    table = parse_dungeon_chest_data(
        source,
        source_revision=PINNED_REVISION,
        source_file="Bank01.asm",
    )

    assert payload == table.to_dict()
    assert "; Top byte of each entry is the item to give, bottom 15 bits are the room." in source
    assert "; if bit 15 (0x8000) is set, it's for a big chest." in source
    assert "LDA Dungeon_ChestData, X : AND.w #$7FFF : CMP.b $A0" in source
    assert "LDA Dungeon_ChestData+2, X : STA.b $0C" in source
    assert "LDA Dungeon_ChestData, X : ASL : BCC .smallChest" in source
    assert "INX #3 : CPX.w #$01F8" in source
