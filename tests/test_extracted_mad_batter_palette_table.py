"""Tests for the source-only Mad Batter pseudo-attack palette selector table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "mad-batter-pseudo-attack-palettes.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_mad_batter.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "MadBatter_PseudoAttackPlayer_palettes"
TABLE_FILE_OFFSET = 0x02FB86
EXPECTED_VALUES = [0x0A, 0x04, 0x02, 0x04, 0x02, 0x0A, 0x04, 0x02]


def test_committed_palette_selector_has_traceable_eight_byte_baseline() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_mad_batter.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == TABLE_LABEL
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["directive"] == "db"
    assert payload["entry_width"] == 1
    assert payload["entry_count"] == 8
    assert [entry["table_index"] for entry in payload["entries"]] == list(range(8))
    assert [entry["entry_file_offset"] for entry in payload["entries"]] == list(
        range(TABLE_FILE_OFFSET, TABLE_FILE_OFFSET + 8)
    )
    assert [entry["expression"] for entry in payload["entries"]] == [
        "$0A", "$04", "$02", "$04", "$02", "$0A", "$04", "$02"
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
def test_committed_palette_selector_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        directive="db",
        source_revision=PINNED_REVISION,
        expected_entry_count=8,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert "; $02FB86-$02FB8D DATA" in source
    assert "LSR : AND.b #$07 : TAY" in source
    assert "ORA .palettes, Y" in source
