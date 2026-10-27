"""Integration checks against the pinned source tree, when the submodule is available."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import parse_dl_pointer_table, parse_dw_pointer_table

ROOT = Path(__file__).resolve().parents[1]
BANK1F_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1F.asm"
BANK1B_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not BANK1F_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_dungeon_room_pointer_table_matches_documented_extent() -> None:
    source = BANK1F_PATH.read_text(encoding="utf-8")
    entries = parse_dl_pointer_table(
        source,
        "RoomData_ObjectDataPointers",
        0x0F8000,
        source_revision=PINNED_REVISION,
    )

    # The disassembly labels the inclusive extent $0F8000-$0F83BF:
    # 0x3C0 bytes / three-byte dl entries = 320 table indices.
    assert len(entries) == 320
    assert entries[0].table_index == 0
    assert entries[0].pointer_entry_file_offset == 0x0F8000
    assert entries[0].pointer_expression == "RoomDataTiles_0000"
    assert entries[5].is_empty_target
    assert entries[-1].table_index == 319
    assert entries[-1].pointer_entry_file_offset == 0x0F83BD
    assert entries[-1].source_revision == PINNED_REVISION



@pytest.mark.skipif(
    not BANK1B_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_overworld_hidden_item_pointer_table_has_128_words() -> None:
    source = BANK1B_PATH.read_text(encoding="utf-8")
    entries = parse_dw_pointer_table(
        source,
        "OverworldData_HiddenItems",
        0x0DC2F9,
        source_revision=PINNED_REVISION,
    )

    # The pinned source log describes 0x80 two-byte area pointers at $0DC2F9.
    assert len(entries) == 128
    assert entries[0].table_index == 0
    assert entries[0].pointer_entry_file_offset == 0x0DC2F9
    assert entries[0].pointer_expression == "OverworldData_HiddenItems_Screen_00"
    assert entries[-1].table_index == 127
    assert entries[-1].pointer_entry_file_offset == 0x0DC3F7
    assert entries[-1].source_revision == PINNED_REVISION
