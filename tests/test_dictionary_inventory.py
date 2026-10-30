"""Tests for source-only dictionary fragment inventory."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import load_source_export
from zelda_suite.extract.asset_loader import AssetLoadError, validate_source_export
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



def test_cli_exports_inventory_and_loader_rejects_inconsistent_extent_flag(
    tmp_path: Path,
) -> None:
    synthetic = """DictionaryPointers:
{
    dw DictionaryEntries_alpha
    dw DictionaryEntries_endOfTable
}
DictionaryEntries:
{
    ; $001000
    .alpha
    db $01, $02
    ; $001002
    .endOfTable
}
"""
    source_path = tmp_path / "synthetic.asm"
    output_path = tmp_path / "dictionary-inventory.json"
    source_path.write_text(synthetic, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "inspect-text-dictionary",
            str(source_path),
            "--pointer-table-offset",
            "$0200",
            "--data-offset",
            "$1000",
            "--source-revision",
            "synthetic-revision",
            "--output",
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output

    payload = load_source_export(output_path)
    assert payload["format"] == "zelda-suite-dictionary-inventory"
    assert payload["fragment_count"] == 2
    assert payload["fragments"][0]["source_extent_matches_directive"] is True
    assert payload["fragments"][-1]["is_end_of_table"] is True

    malformed = json.loads(output_path.read_text(encoding="utf-8"))
    malformed["fragments"][0]["source_extent_matches_directive"] = False
    with pytest.raises(AssetLoadError, match="source_extent_matches_directive"):
        validate_source_export(malformed)


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_dictionary_inventory_export_matches_pinned_source() -> None:
    payload = load_source_export(
        ROOT / "data" / "extracted" / "text-dictionary-fragments.json"
    )
    source = SOURCE_PATH.read_text(encoding="utf-8")
    fragments = parse_dictionary_fragment_inventory(
        source,
        pointer_table_file_offset=0x074703,
        data_file_offset=0x0747C7,
        source_revision=PINNED_REVISION,
    )
    assert payload["fragments"] == [fragment.to_dict() for fragment in fragments]
    assert payload["fragment_count"] == len(fragments)


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_dictionary_source_preserves_symbol_and_you_extent_discrepancies() -> None:
    """Pin the two unresolved Bank0E source inconsistencies without repairing them."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()

    consumer_references = [
        (line_number, line.strip())
        for line_number, line in enumerate(lines, start=1)
        if "Text_DictionaryPointers" in line
    ]
    assert consumer_references == [
        (
            6018,
            "LDA.w Text_DictionaryPointers+2, Y : STA.b $00",
        ),
        (
            6019,
            "LDA.w Text_DictionaryPointers+0, Y : TAY",
        ),
    ]
    # There is one visible table declaration, but no source-level declaration
    # or alias with the consumer's Text_ prefix in the pinned Bank0E.asm.
    assert [line.strip() for line in lines if line.strip() == "DictionaryPointers:"] == [
        "DictionaryPointers:"
    ]
    assert not any(
        line.strip() == "Text_DictionaryPointers:" for line in lines
    )

    entries = parse_dictionary_fragment_inventory(
        source,
        pointer_table_file_offset=0x074703,
        data_file_offset=0x0747C7,
        source_revision=PINNED_REVISION,
    )
    you = entries[96]
    end = entries[97]
    assert you.pointer_expression == "DictionaryEntries_You"
    assert you.fragment_file_offset == 0x0748D6
    assert you.data_directive == "dw"
    assert you.directive_value_count == 3
    assert you.declared_payload_bytes == 6
    assert you.next_fragment_file_offset == 0x0748D8
    assert you.source_extent_bytes == 2
    assert you.source_extent_matches_directive is False
    assert end.pointer_expression == "DictionaryEntries_endOfTable"
    assert end.fragment_file_offset == 0x0748D8

    # The runtime reads the current pointer as the start and the following
    # pointer as the exclusive end. Do not "fix" the source annotations here.
    assert (
        "LDA.w Text_DictionaryPointers+2, Y : STA.b $00"
        in source
    )
    assert (
        "LDA.w Text_DictionaryPointers+0, Y : TAY"
        in source
    )
    assert "INY : CPY.b $00 : BCC .nextCharacter" in source
