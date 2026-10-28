"""Tests for mixed-width Asar data-table parsing."""
from __future__ import annotations

import pytest

from zelda_suite.extract import MixedDataTableParseError, parse_mixed_data_table

SAMPLE_SOURCE = """ExampleOAM:
{
    dw 0, 4 : db $70, $00, $00, $00
    dw 8, 4 : db $70, $40, $00, $00
}
"""


def test_parses_mixed_width_rows_with_byte_accurate_offsets() -> None:
    table = parse_mixed_data_table(
        SAMPLE_SOURCE,
        "ExampleOAM",
        0x1000,
        expected_record_count=2,
    )

    assert table.record_count == 2
    assert table.byte_count == 16
    assert [record.record_file_offset for record in table.records] == [0x1000, 0x1008]
    assert [record.byte_length for record in table.records] == [8, 8]
    assert [record.source_line for record in table.records] == [3, 4]

    first_word_field, first_byte_field = table.records[0].fields
    assert first_word_field.directive == "dw"
    assert first_word_field.field_file_offset == 0x1000
    assert [entry.expression for entry in first_word_field.entries] == ["0", "4"]
    assert [entry.entry_file_offset for entry in first_word_field.entries] == [
        0x1000,
        0x1002,
    ]
    assert first_byte_field.directive == "db"
    assert first_byte_field.field_file_offset == 0x1004
    assert [entry.literal_value for entry in first_byte_field.entries] == [
        0x70,
        0,
        0,
        0,
    ]
    assert [entry.entry_file_offset for entry in first_byte_field.entries] == [
        0x1004,
        0x1005,
        0x1006,
        0x1007,
    ]


def test_rejects_unsupported_segments_and_width_overflow() -> None:
    source = """ExampleOAM:
{
    dw 0, 4 : nop
}
"""
    with pytest.raises(MixedDataTableParseError, match="unsupported syntax"):
        parse_mixed_data_table(source, "ExampleOAM", 0x1000)

    source = """ExampleOAM:
{
    dw $10000
}
"""
    with pytest.raises(MixedDataTableParseError, match="exceeds 2-byte directive width"):
        parse_mixed_data_table(source, "ExampleOAM", 0x1000)


def test_rejects_duplicate_labels_and_unexpected_record_count() -> None:
    duplicate = """ExampleOAM:
{
    db $01
}
ExampleOAM:
{
    db $02
}
"""
    with pytest.raises(MixedDataTableParseError, match="occurs multiple times"):
        parse_mixed_data_table(duplicate, "ExampleOAM", 0x1000)

    with pytest.raises(
        MixedDataTableParseError,
        match="expected 3 records.*found 2",
    ):
        parse_mixed_data_table(SAMPLE_SOURCE, "ExampleOAM", 0x1000, expected_record_count=3)
