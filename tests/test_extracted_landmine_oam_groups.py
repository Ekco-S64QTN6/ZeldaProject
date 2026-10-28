"""Regression tests for the source-only Landmine OAM group table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import (
    load_extracted_asset,
    load_source_export,
    parse_mixed_data_table,
)

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "landmine-oam-groups.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_landmine.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "Landmine_Draw_OAM_groups"
TABLE_FILE_OFFSET = 0x0E80FC


def test_committed_landmine_oam_groups_preserve_mixed_width_layout() -> None:
    payload = load_source_export(EXPORT_PATH)
    assert payload["format"] == "zelda-suite-mixed-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_landmine.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["table_label"] == TABLE_LABEL
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["record_count"] == 2
    assert payload["byte_count"] == 16
    assert [record["record_file_offset"] for record in payload["records"]] == [
        0x0E80FC,
        0x0E8104,
    ]
    assert [record["byte_length"] for record in payload["records"]] == [8, 8]
    assert [
        (field["directive"], field["entry_count"])
        for record in payload["records"]
        for field in record["fields"]
    ] == [("dw", 2), ("db", 4), ("dw", 2), ("db", 4)]
    assert payload["records"][-1]["fields"][-1]["entries"][-1]["entry_file_offset"] == 0x0E810B


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_landmine_oam_export_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    table = parse_mixed_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        expected_record_count=2,
    )

    assert payload["records"] == [record.to_dict() for record in table.records]
    assert "; $0E80FC-$0E810B DATA" in source
    assert any(
        line.strip() == "dw 0, 4 : db $70, $00, $00, $00"
        for line in source.splitlines()
    )
    assert any(
        line.strip() == "dw 8, 4 : db $70, $40, $00, $00"
        for line in source.splitlines()
    )


def test_registered_landmine_oam_asset_matches_source_export() -> None:
    payload = load_extracted_asset("landmine-oam-groups")
    assert payload["record_count"] == 2
    assert payload["byte_count"] == 16
