"""Tests for raw Asar db/dw/dl data-table parsing."""
from __future__ import annotations

import pytest

from zelda_suite.extract.data_table import (
    DataTableParseError,
    parse_data_table,
)

SAMPLE_SOURCE = """ParentTable:
{
    .values
    .first
    db $10, $37
    .second
    db $20, SymbolicItem
    .next
    dw $1234
}
"""


def test_parses_raw_literals_and_keeps_unresolved_expressions() -> None:
    entries = parse_data_table(
        SAMPLE_SOURCE,
        ".values",
        0x0200,
        directive="db",
        parent_label="ParentTable",
        end_label=".next",
        source_revision="example-sha",
    )

    assert len(entries) == 4
    assert [entry.table_index for entry in entries] == [0, 1, 2, 3]
    assert [entry.entry_file_offset for entry in entries] == [0x0200, 0x0201, 0x0202, 0x0203]
    assert [entry.literal_value for entry in entries] == [0x10, 0x37, 0x20, None]
    assert [entry.source_label for entry in entries] == [
        ".first",
        ".first",
        ".second",
        ".second",
    ]
    assert entries[-1].expression == "SymbolicItem"
    assert entries[-1].source_revision == "example-sha"


def test_supports_unscoped_brace_delimited_global_table() -> None:
    source = """ExampleValues:
{
    db $01, 0x02, 3
}
NextTable:
{
    db $FF
}
"""
    entries = parse_data_table(source, "ExampleValues", 0x0400, directive="db")

    assert [entry.literal_value for entry in entries] == [1, 2, 3]
    assert [entry.entry_file_offset for entry in entries] == [0x0400, 0x0401, 0x0402]


def test_rejects_mixed_directives_inside_table() -> None:
    source = """ParentTable:
{
    .values
    db $01
    dw $0002
    .next
}
"""
    with pytest.raises(DataTableParseError, match="expected db directive but found dw"):
        parse_data_table(
            source,
            ".values",
            0x100,
            directive="db",
            parent_label="ParentTable",
            end_label=".next",
        )


def test_rejects_numeric_literal_that_exceeds_directive_width() -> None:
    source = """ParentTable:
{
    .values
    db $100
    .next
}
"""
    with pytest.raises(DataTableParseError, match="exceeds 1-byte directive width"):
        parse_data_table(
            source,
            ".values",
            0x100,
            directive="db",
            parent_label="ParentTable",
            end_label=".next",
        )


def test_rejects_ambiguous_local_label_without_parent_scope() -> None:
    source = """First:
{
    .values
    db $01
}
Second:
{
    .values
    db $02
}
"""
    with pytest.raises(DataTableParseError, match="ambiguous"):
        parse_data_table(source, ".values", 0x100)


def test_requires_valid_offset_and_directive() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        parse_data_table(SAMPLE_SOURCE, ".values", -1, parent_label="ParentTable")
    with pytest.raises(ValueError, match="db.*dw.*dl"):
        parse_data_table(SAMPLE_SOURCE, ".values", 0, directive="dd", parent_label="ParentTable")



def test_entry_width_override_does_not_widen_directive_literal_range() -> None:
    source = """Values:
{
    db $100
}
"""
    with pytest.raises(DataTableParseError, match="exceeds 1-byte directive width"):
        parse_data_table(
            source,
            "Values",
            0x100,
            directive="db",
            entry_width=2,
        )
