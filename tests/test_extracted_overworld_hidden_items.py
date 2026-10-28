"""Tests for the source-only overworld hidden-item pointer export."""
from __future__ import annotations

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
