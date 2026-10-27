"""Tests for source-only dictionary fragment inventory."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract.dictionary_inventory import (
    DictionaryInventoryError,
    parse_dictionary_fragment_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0E.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_inventory_tracks_dictionary_fragments_without_storing_bytes() -> None:
    if not SOURCE_PATH.is_file():
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_dictionary_fragment_inventory(
        source,
        pointer_table_file_offset=0x074703,
        data_file_offset=0x0747C7,
        source_revision=PINNED_REVISION,
    )

    assert len(entries) == 98
    first = entries[0]
    assert first.pointer_index == 0
    assert first.pointer_entry_file_offset == 0x074703
    assert first.pointer_expression == "DictionaryEntries_fourSpaces"
    assert first.fragment_label == ".fourSpaces"
    assert first.fragment_file_offset == 0x0747C7
    assert first.source_extent_bytes == 4
    assert first.declared_payload_bytes == 4
    assert first.source_extent_matches_directive is True

    last_content = entries[96]
    assert last_content.pointer_expression == "DictionaryEntries_You"
    assert last_content.fragment_label == ".You"
    assert last_content.fragment_file_offset == 0x0748D6
    assert last_content.next_fragment_file_offset == 0x0748D8
    assert last_content.source_extent_bytes == 2
    assert last_content.data_directive == "dw"
    assert last_content.directive_value_count == 3
    assert last_content.declared_payload_bytes == 6
    assert last_content.source_extent_matches_directive is False

    sentinel = entries[-1]
    assert sentinel.pointer_index == 97
    assert sentinel.pointer_expression == "DictionaryEntries_endOfTable"
    assert sentinel.fragment_label == ".endOfTable"
    assert sentinel.fragment_file_offset == 0x0748D8
    assert sentinel.data_directive is None
    assert sentinel.is_end_of_table is True
    assert sentinel.source_revision == PINNED_REVISION


def test_fragment_inventory_requires_source_offsets_and_resolvable_labels() -> None:
    source = """DictionaryPointers:
{
    dw DictionaryEntries_missing
}
DictionaryEntries:
{
    ; $1000
    .present
    db $01
    ; $1001
    .endOfTable
}
"""
    with pytest.raises(DictionaryInventoryError, match="no corresponding fragment label"):
        parse_dictionary_fragment_inventory(
            source,
            pointer_table_file_offset=0x200,
            data_file_offset=0x1000,
            source_revision="synthetic",
        )


def test_fragment_inventory_rejects_missing_offset_comments() -> None:
    source = """DictionaryPointers:
{
    dw DictionaryEntries_one
}
DictionaryEntries:
{
    .one
    db $01
    ; $1001
    .endOfTable
}
"""
    with pytest.raises(DictionaryInventoryError, match="missing source offset comment"):
        parse_dictionary_fragment_inventory(
            source,
            pointer_table_file_offset=0x200,
            data_file_offset=0x1000,
            source_revision="synthetic",
        )
