"""Tests for the source-only Crystal Maiden palette-word table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "crystal-maiden-palette-words.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_crystal_maiden.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "CrystalMaiden_Configure_palette"
TABLE_FILE_OFFSET = 0x0F4CD3
EXPECTED_VALUES = [
    0x0000,
    0x3821,
    0x4463,
    0x54A5,
    0x5CE7,
    0x6D29,
    0x79AD,
    0x7E10,
]


def test_committed_crystal_maiden_palette_words_have_traceable_baseline() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_crystal_maiden.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == TABLE_LABEL
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["directive"] == "dw"
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 8
    assert [entry["table_index"] for entry in payload["entries"]] == list(range(8))
    assert [entry["entry_file_offset"] for entry in payload["entries"]] == [
        TABLE_FILE_OFFSET + index * 2 for index in range(8)
    ]
    assert [entry["expression"] for entry in payload["entries"]] == [
        "$0000",
        "$3821",
        "$4463",
        "$54A5",
        "$5CE7",
        "$6D29",
        "$79AD",
        "$7E10",
    ]
    assert [entry["literal_value"] for entry in payload["entries"]] == EXPECTED_VALUES
    assert all(
        entry["source_label"] == TABLE_LABEL
        and entry["source_revision"] == PINNED_REVISION
        for entry in payload["entries"]
    )


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_crystal_maiden_palette_words_match_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        directive="dw",
        source_revision=PINNED_REVISION,
        expected_entry_count=8,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert "; $0F4CD3-$0F4CE2 DATA" in source
    assert "LDA.l .palette+$00 : STA.l $7EC5E0" in source
    assert "LDA.l .palette+$0E : STA.l $7EC5EE" in source
