"""Source-parity coverage for the registered OAM allocator table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "oam-buffer-position-table.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_oam_allocation.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "Pool_OAM_GetBufferPosition"
TABLE_FILE_OFFSET = 0x06BA9E
LIMIT_VALUES = [0x0171, 0x0201, 0x0031, 0x00C1, 0x0141, 0x01D1]
FALLBACK_ROWS = [
    [0x0030, 0x0050, 0x0080, 0x00B0, 0x00E0, 0x0110, 0x0140, 0x0170],
    [0x01D0, 0x01D4, 0x01DC, 0x01E0, 0x01E4, 0x01EC, 0x01F0, 0x01F8],
    [0x0000, 0x0004, 0x0008, 0x000C, 0x0010, 0x0014, 0x0018, 0x001C],
    [0x0030, 0x0038, 0x0050, 0x0068, 0x0080, 0x0098, 0x00B0, 0x00C8],
    [0x0120, 0x0124, 0x0128, 0x012C, 0x0130, 0x0134, 0x0138, 0x013C],
    [0x0140, 0x0150, 0x0160, 0x0170, 0x0180, 0x0190, 0x01A0, 0x01B8],
]


def test_committed_oam_table_has_54_sequential_word_entries() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_oam_allocation.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == TABLE_LABEL
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["directive"] == "dw"
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 54
    assert [entry["table_index"] for entry in payload["entries"]] == list(range(54))
    assert [entry["entry_file_offset"] for entry in payload["entries"]] == [
        TABLE_FILE_OFFSET + 2 * index for index in range(54)
    ]
    assert [entry["literal_value"] for entry in payload["entries"][:6]] == LIMIT_VALUES
    assert [
        [entry["literal_value"] for entry in payload["entries"][6 + 8 * region:14 + 8 * region]]
        for region in range(6)
    ] == FALLBACK_ROWS
    assert [entry["source_label"] for entry in payload["entries"][:6]] == [".limits"] * 6
    assert [entry["source_label"] for entry in payload["entries"][6:]] == [
        ".fallback_points"
    ] * 48


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_oam_table_matches_pinned_source_and_lookup_consumer() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        directive="dw",
        source_revision=PINNED_REVISION,
        expected_entry_count=54,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert "; $06BA9E-$06BB09 DATA TABLE" in source
    assert "Upper limits for each OAM region" in source
    assert "fall back points for each OAM region" in source
    assert "LDA.w .limits, Y" in source
    assert "LDA.w .fallback_points, Y : STA.b $90" in source
    assert "LDA.b $0C : ASL #3 : ADC.b $0E : TAY" in source

    region_y_values = ["$00", "$02", "$04", "$06", "$08", "$0A"]
    for name, y_value in zip("ABCDEF", region_y_values, strict=True):
        assert f"OAM_AllocateFromRegion{name}:" in source
        assert f"LDY.b #{y_value}" in source
