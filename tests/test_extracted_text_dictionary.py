"""Regression checks for the committed text dictionary pointer export."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "extracted" / "text-dictionary-pointers.json"
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0E.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_dictionary_pointer_export_is_valid_and_retains_symbol_expressions() -> None:
    payload = load_source_export(DATA_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "Bank0E.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == "DictionaryPointers"
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == 0x074703
    assert payload["directive"] == "dw"
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 98
    assert payload["entries"][0]["expression"] == "DictionaryEntries_fourSpaces"
    assert payload["entries"][0]["literal_value"] is None
    assert payload["entries"][-1]["expression"] == "DictionaryEntries_endOfTable"
    assert payload["entries"][-1]["table_index"] == 97
    assert payload["entries"][-1]["entry_file_offset"] == 0x0747C5


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_dictionary_pointer_export_matches_pinned_source_parser() -> None:
    payload = load_source_export(DATA_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    parsed = parse_data_table(
        source,
        "DictionaryPointers",
        0x074703,
        directive="dw",
        source_revision=PINNED_REVISION,
    )

    assert len(parsed) == 98
    assert payload["entries"] == [entry.to_dict() for entry in parsed]
    assert payload["entry_count"] == len(parsed)
