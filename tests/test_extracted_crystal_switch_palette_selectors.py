"""Tests for the source-only Crystal Switch palette-selector table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "crystal-switch-palette-selectors.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_crystal_switch.asm"
)
PREP_SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_prep.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "Sprite_CrystalSwitch_palettes"
TABLE_FILE_OFFSET = 0x0338CE
EXPECTED_VALUES = [0x02, 0x04]


def test_committed_crystal_switch_selector_has_traceable_baseline() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_crystal_switch.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == TABLE_LABEL
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["directive"] == "db"
    assert payload["entry_width"] == 1
    assert payload["entry_count"] == 2
    assert [entry["table_index"] for entry in payload["entries"]] == [0, 1]
    assert [entry["entry_file_offset"] for entry in payload["entries"]] == [
        TABLE_FILE_OFFSET,
        TABLE_FILE_OFFSET + 1,
    ]
    assert [entry["expression"] for entry in payload["entries"]] == ["$02", "$04"]
    assert [entry["literal_value"] for entry in payload["entries"]] == EXPECTED_VALUES
    assert all(
        entry["source_label"] == TABLE_LABEL
        and entry["source_revision"] == PINNED_REVISION
        for entry in payload["entries"]
    )


@pytest.mark.skipif(
    not SOURCE_PATH.is_file() or not PREP_SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_crystal_switch_selector_matches_pinned_table_and_consumer() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        directive="db",
        source_revision=PINNED_REVISION,
        expected_entry_count=2,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert "; $0338CE-$0338CF DATA" in source

    prep_source = PREP_SOURCE_PATH.read_text(encoding="utf-8")
    assert "LDA.l $7EC172 : AND.b #$01 : TAY" in prep_source
    assert (
        "LDA.w Sprite_CrystalSwitch_palettes, Y : ORA.w $0F50, X "
        ": STA.w $0F50, X"
    ) in prep_source
