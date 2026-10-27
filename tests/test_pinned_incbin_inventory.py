"""Integration tests for incbin declarations in the pinned disassembly."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract.incbin_inventory import parse_incbin_inventory

ROOT = Path(__file__).resolve().parents[1]
BANK0B_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0B.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not BANK0B_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_overworld_incbin_inventory_matches_pinned_source_annotations() -> None:
    source = BANK0B_PATH.read_text(encoding="utf-8")
    records = parse_incbin_inventory(
        source,
        source_file="Bank0B.asm",
        source_revision=PINNED_REVISION,
    )
    by_label = {record.label: record for record in records}

    high = by_label["OverworldMap32_Screen00_High"]
    assert high.incbin_path == "bin/ow/screen00-h.bin"
    assert high.source_file_offset_start == 0x058000
    assert high.source_file_offset_end == 0x058003
    assert high.declared_size_bytes == 4
    assert high.source_range_size_matches is True

    low = by_label["OverworldMap32_Screen00_Low"]
    assert low.incbin_path == "bin/ow/screen00-l.bin"
    assert low.source_file_offset_start == 0x058004
    assert low.source_file_offset_end == 0x0580D5
    assert low.declared_size_bytes == 0xD2
    assert low.source_range_size_matches is True

    next_high = by_label["OverworldMap32_Screen01_High"]
    assert next_high.source_file_offset_start == 0x0580D6
    assert next_high.source_range_size_matches is True
    assert high.source_revision == PINNED_REVISION
