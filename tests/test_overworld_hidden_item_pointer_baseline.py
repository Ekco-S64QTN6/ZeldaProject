"""Submodule-independent regression baseline for hidden-item pointer metadata."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from zelda_suite.extract import load_extracted_asset, load_source_export

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "overworld-hidden-item-pointers.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

EXPECTED_QUADRUPLE_TARGETS = [
    "OverworldData_HiddenItems_Screen_00",
    "OverworldData_HiddenItems_Screen_03",
    "OverworldData_HiddenItems_Screen_05",
    "OverworldData_HiddenItems_Screen_18",
    "OverworldData_HiddenItems_Screen_1B",
    "OverworldData_HiddenItems_Screen_1E",
    "OverworldData_HiddenItems_Screen_30",
    "OverworldData_HiddenItems_Screen_35",
    "OverworldData_HiddenItems_Screen_40",
    "OverworldData_HiddenItems_Screen_43",
    "OverworldData_HiddenItems_Screen_45",
    "OverworldData_HiddenItems_Screen_58",
    "OverworldData_HiddenItems_Screen_5B",
    "OverworldData_HiddenItems_Screen_5E",
    "OverworldData_HiddenItems_Screen_70",
    "OverworldData_HiddenItems_Screen_75",
]


def test_committed_hidden_item_pointer_export_has_pinned_source_baseline() -> None:
    """Keep all pointer slots and repeated-label distribution checked without source checkout."""
    payload = load_source_export(EXPORT_PATH)
    registered = load_extracted_asset("overworld-hidden-item-pointers", REGISTRY_PATH)

    assert payload == registered
    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "Bank1B.asm"
    assert payload["source_revision"] == PINNED_SOURCE_REVISION
    assert payload["table_label"] == "OverworldData_HiddenItems"
    assert payload["table_file_offset"] == 0x0DC2F9
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 128

    entries = payload["entries"]
    assert len(entries) == 128
    assert entries[0]["pointer_entry_file_offset"] == 0x0DC2F9
    assert entries[-1]["pointer_entry_file_offset"] == 0x0DC3F7
    assert all(entry["table_index"] == index for index, entry in enumerate(entries))
    assert all(
        entry["pointer_entry_file_offset"] == 0x0DC2F9 + index * 2
        for index, entry in enumerate(entries)
    )
    assert all(entry["source_revision"] == PINNED_SOURCE_REVISION for entry in entries)
    assert all(entry["target_addend"] is None for entry in entries)
    assert all(entry["is_empty_target"] is False for entry in entries)
    assert all(
        entry["pointer_expression"] == entry["target_label"]
        for entry in entries
    )
    assert all(
        re.fullmatch(r"OverworldData_HiddenItems_Screen_[0-9A-F]{2}", entry["target_label"])
        for entry in entries
    )

    target_counts = Counter(entry["target_label"] for entry in entries)
    assert len(target_counts) == 80
    assert Counter(target_counts.values()) == Counter({1: 64, 4: 16})
    assert sorted(
        label for label, count in target_counts.items() if count == 4
    ) == EXPECTED_QUADRUPLE_TARGETS
