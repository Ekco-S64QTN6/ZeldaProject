"""Tests for source-level Asar pointer table parsing."""
from __future__ import annotations

import pytest

from zelda_suite.extract.disassembly import (
    DisassemblyParseError,
    parse_dl_pointer_table,
    parse_dw_pointer_table,
)

SAMPLE_SOURCE = """
; synthetic excerpt — not ROM data
RoomData_ObjectDataPointers:
{
    dl RoomDataTiles_0000
    dl RoomDataTiles_Empty+$0008 ; empty target with door-data offset
    dl RoomDataTiles_0002, RoomDataTiles_0002+$0010
}

RoomData_DoorDataPointers:
{
    dl RoomDataTiles_0000+$004D
}
"""


def test_parses_entries_and_preserves_source_expressions() -> None:
    entries = parse_dl_pointer_table(
        SAMPLE_SOURCE,
        "RoomData_ObjectDataPointers",
        0x0F8000,
    )

    assert len(entries) == 4
    assert [entry.table_index for entry in entries] == [0, 1, 2, 3]
    assert [entry.pointer_entry_file_offset for entry in entries] == [
        0x0F8000,
        0x0F8003,
        0x0F8006,
        0x0F8009,
    ]
    assert entries[0].pointer_expression == "RoomDataTiles_0000"
    assert entries[0].target_label == "RoomDataTiles_0000"
    assert entries[0].target_addend is None
    assert entries[1].pointer_expression == "RoomDataTiles_Empty+$0008"
    assert entries[1].target_label == "RoomDataTiles_Empty"
    assert entries[1].target_addend == 8
    assert entries[1].is_empty_target
    assert entries[2].source_line == 7
    assert entries[3].target_addend == 0x10


def test_only_parses_the_requested_brace_delimited_table() -> None:
    entries = parse_dl_pointer_table(
        SAMPLE_SOURCE,
        "RoomData_DoorDataPointers",
        0x0F83C0,
    )

    assert len(entries) == 1
    assert entries[0].table_index == 0
    assert entries[0].pointer_entry_file_offset == 0x0F83C0
    assert entries[0].pointer_expression == "RoomDataTiles_0000+$004D"
    assert entries[0].target_addend == 0x4D



def test_rejects_duplicate_requested_table_labels() -> None:
    source = """ExamplePointers:
{
    dl FirstTarget
}
ExamplePointers:
{
    dl SecondTarget
}
"""

    with pytest.raises(
        DisassemblyParseError,
        match=r"occurs multiple times on lines 1, 5",
    ):
        parse_dl_pointer_table(source, "ExamplePointers", 0x100)


def test_supports_decimal_addends_and_negative_offsets() -> None:
    source = """ExamplePointers:
{
    dl SomeTarget+12, SomeOtherTarget-$0003
}
"""
    entries = parse_dl_pointer_table(source, "ExamplePointers", 0x100)

    assert entries[0].target_addend == 12
    assert entries[1].target_addend == -3


@pytest.mark.parametrize(
    ("source", "label", "message"),
    [
        ("SomeOtherLabel:\n{\n    dl Target\n}\n", "Missing", "label not found"),
        ("Broken:\n    dl Target\n", "Broken", "expected '{'"),
        ("Broken:\n{\n    dl Target\n", "Broken", "closing brace not found"),
        ("Empty:\n{\n}\n", "Empty", "is empty"),
        ("Bad:\n{\n    dl Target+$QQ\n}\n", "Bad", "unsupported pointer expression"),
        ("Bad:\n{\n    dl Target,\n}\n", "Bad", "malformed dl directive"),
    ],
)
def test_rejects_missing_or_malformed_table(
    source: str, label: str, message: str
) -> None:
    with pytest.raises(DisassemblyParseError, match=message):
        parse_dl_pointer_table(source, label, 0x100)


def test_rejects_invalid_offsets_and_entry_width() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        parse_dl_pointer_table(SAMPLE_SOURCE, "RoomData_ObjectDataPointers", -1)
    with pytest.raises(ValueError, match="positive"):
        parse_dl_pointer_table(
            SAMPLE_SOURCE, "RoomData_ObjectDataPointers", 0, entry_width=0
        )


def test_records_are_json_friendly() -> None:
    entry = parse_dl_pointer_table(
        SAMPLE_SOURCE, "RoomData_ObjectDataPointers", 0x0F8000
    )[1]

    record = entry.to_dict()
    assert record["pointer_expression"] == "RoomDataTiles_Empty+$0008"
    assert record["target_addend"] == 8
    assert record["is_empty_target"] is True



SAMPLE_WORD_SOURCE = """; synthetic excerpt — not ROM data
OverworldData_HiddenItems:
{
    dw OverworldData_HiddenItems_Screen_00
    dw OverworldData_HiddenItems_Screen_02+$0002 ; addend example
    dw Screen03, Screen04+$0004
}
"""


def test_parses_dw_pointer_table_with_two_byte_stride() -> None:
    entries = parse_dw_pointer_table(
        SAMPLE_WORD_SOURCE,
        "OverworldData_HiddenItems",
        0x0DC2F9,
        source_revision="pinned-sha",
    )

    assert len(entries) == 4
    assert [entry.table_index for entry in entries] == [0, 1, 2, 3]
    assert [entry.pointer_entry_file_offset for entry in entries] == [
        0x0DC2F9,
        0x0DC2FB,
        0x0DC2FD,
        0x0DC2FF,
    ]
    assert entries[0].pointer_expression == "OverworldData_HiddenItems_Screen_00"
    assert entries[1].target_label == "OverworldData_HiddenItems_Screen_02"
    assert entries[1].target_addend == 2
    assert entries[2].target_addend is None
    assert entries[3].target_addend == 4
    assert entries[3].source_revision == "pinned-sha"


def test_dw_parser_rejects_dl_entries_inside_word_table() -> None:
    source = """WordPointers:
{
    dw FirstTarget
    dl SecondTarget
}
"""
    with pytest.raises(DisassemblyParseError, match="expected dw directive but found dl"):
        parse_dw_pointer_table(source, "WordPointers", 0x100)
