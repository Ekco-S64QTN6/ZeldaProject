"""Tests for source-only overworld hidden-item pointer and layout evidence."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from zelda_suite.extract import load_extracted_asset, load_source_export, parse_dw_pointer_table

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "overworld-hidden-item-pointers.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_hidden_item_pointer_export_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_dw_pointer_table(
        source,
        "OverworldData_HiddenItems",
        0x0DC2F9,
        source_revision=PINNED_REVISION,
    )

    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "Bank1B.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["table_label"] == "OverworldData_HiddenItems"
    assert payload["table_file_offset"] == 0x0DC2F9
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 128
    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert payload["entries"][0]["pointer_entry_file_offset"] == 0x0DC2F9
    assert payload["entries"][-1]["pointer_entry_file_offset"] == 0x0DC3F7
    assert len({entry["target_label"] for entry in payload["entries"]}) == 80


def test_hidden_item_pointer_export_is_registered_by_name() -> None:
    payload = load_extracted_asset("overworld-hidden-item-pointers", REGISTRY_PATH)
    assert payload["entry_count"] == 128
    assert payload["table_label"] == "OverworldData_HiddenItems"


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_hidden_item_source_range_accounts_for_sentinels() -> None:
    """Count declared record widths and terminators in the pinned source region."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    start = source.index("; $0DC3F9-$0DC89B Overworld secrets data")
    end = source.index("; $0DC89C-$0DC8A3 DATA", start)
    region_lines = source[start:end].splitlines()

    record_re = re.compile(
        r"^\s*dw\s+\$[0-9A-Fa-f]{4}\s*:\s*db\s+\$[0-9A-Fa-f]{2}\b"
    )
    sentinel_re = re.compile(r"^\s*dw\s+\$FFFF\b")
    label_re = re.compile(
        r"^\s*OverworldData_HiddenItems_Screen_[0-9A-Fa-f]{2}:\s*$"
    )
    record_count = sum(1 for line in region_lines if record_re.match(line))
    sentinel_count = sum(1 for line in region_lines if sentinel_re.match(line))
    label_positions = [
        index for index, line in enumerate(region_lines) if label_re.match(line)
    ]

    assert len(label_positions) == 80
    assert record_count == 351
    assert sentinel_count == 67
    assert (
        record_count * 3 + sentinel_count * 2
        == 0x0DC89B - 0x0DC3F9 + 1
    )

    # A screen label is not necessarily followed by a local sentinel. The reader
    # scans the byte stream until $FFFF, so the next label does not stop it.
    blocks_without_local_sentinel = 0
    for position_index, position in enumerate(label_positions):
        end_index = (
            label_positions[position_index + 1]
            if position_index + 1 < len(label_positions)
            else len(region_lines)
        )
        block = region_lines[position:end_index]
        if not any(sentinel_re.match(line) for line in block):
            blocks_without_local_sentinel += 1
    assert blocks_without_local_sentinel == 13


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_overworld_reveal_secret_uses_sentinel_terminated_three_byte_entries() -> None:
    """Guard the source reader's stride, sentinel, and value-byte access."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    start = source.index("Overworld_RevealSecret:\n{")
    end = source.index("\n}\n", start)
    reader = source[start:end]

    assert "ASL : TAX" in reader
    assert "LDA.l OverworldData_HiddenItems, X : STA.b $00" in reader
    assert "LDY.w #$FFFD" in reader
    assert "INY #3" in reader
    assert "LDA.b [$00], Y : CMP.w #$FFFF : BEQ .failure" in reader
    assert "INY : INY" in reader
    assert "LDA.b [$00], Y : AND.w #$00FF" in reader
