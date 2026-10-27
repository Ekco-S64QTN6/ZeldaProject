"""Integration tests for raw data tables in the pinned disassembly."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import parse_data_table

ROOT = Path(__file__).resolve().parents[1]
ANCILLA_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Ancilla" / "ancilla_init.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not ANCILLA_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_falling_prize_item_values_table() -> None:
    source = ANCILLA_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        ".item_values",
        0x048B90,
        directive="db",
        parent_label="Pool_AddPendantOrCrystal",
        end_label=".fall_height",
        source_revision=PINNED_REVISION,
    )

    assert len(entries) == 7
    assert [entry.literal_value for entry in entries] == [
        0x10,
        0x37,
        0x39,
        0x38,
        0x26,
        0x0F,
        0x20,
    ]
    assert [entry.entry_file_offset for entry in entries] == [
        0x048B90,
        0x048B91,
        0x048B92,
        0x048B93,
        0x048B94,
        0x048B95,
        0x048B96,
    ]
    assert entries[0].source_label == ".ether_medallion"
    assert entries[1].source_label == ".pendants"
    assert entries[-1].source_label == ".crystal"
    assert all(entry.source_revision == PINNED_REVISION for entry in entries)


@pytest.mark.skipif(
    not ANCILLA_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_falling_prize_adjacent_tables_keep_their_own_widths() -> None:
    source = ANCILLA_PATH.read_text(encoding="utf-8")

    fall_heights = parse_data_table(
        source,
        ".fall_height",
        0x048B97,
        directive="db",
        parent_label="Pool_AddPendantOrCrystal",
        end_label=".y_offsets",
        source_revision=PINNED_REVISION,
    )
    y_offsets = parse_data_table(
        source,
        ".y_offsets",
        0x048B9E,
        directive="dw",
        parent_label="Pool_AddPendantOrCrystal",
        end_label=".x_offsets",
        source_revision=PINNED_REVISION,
    )

    assert [entry.literal_value for entry in fall_heights] == [0x60, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80]
    assert [entry.entry_file_offset for entry in fall_heights] == [
        0x048B97,
        0x048B98,
        0x048B99,
        0x048B9A,
        0x048B9B,
        0x048B9C,
        0x048B9D,
    ]
    assert [entry.literal_value for entry in y_offsets] == [
        0x0048,
        0x0078,
        0x0078,
        0x0078,
        0x0078,
        0x0068,
        0x0078,
    ]
    assert y_offsets[0].entry_file_offset == 0x048B9E
    assert y_offsets[-1].entry_file_offset == 0x048BAA
