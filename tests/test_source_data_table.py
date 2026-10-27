"""Tests for bounded Asar scalar-table parsing and JSON export."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.asset_loader import AssetLoadError, load_source_export
from zelda_suite.extract.source_data_table import (
    DataTableParseError,
    parse_source_data_table,
)

SAMPLE_SOURCE = """Parent:
{
    .item_values
    ; first semantic group
    .ether
    db $10 ; inline note
    .pendants
    db $37, $39, $38
    .heart
    db $26
    .bombos
    db $0F
    .crystal
    db $20
    .fall_height
    db $60, $80
}
"""


def test_parses_bounded_local_db_table_and_keeps_source_annotations() -> None:
    entries = parse_source_data_table(
        SAMPLE_SOURCE,
        "Parent.item_values",
        0x1000,
        directive="db",
        entry_count=7,
        stop_before_label=".fall_height",
        source_file="synthetic.asm",
        source_revision="pinned-sha",
    )

    assert len(entries) == 7
    assert [entry.table_index for entry in entries] == list(range(7))
    assert [entry.entry_file_offset for entry in entries] == list(range(0x1000, 0x1007))
    assert [entry.numeric_value for entry in entries] == [
        0x10, 0x37, 0x39, 0x38, 0x26, 0x0F, 0x20
    ]
    assert entries[0].source_label == ".ether"
    assert entries[1].source_label == ".pendants"
    assert entries[2].source_label == ".pendants"
    assert entries[4].source_label == ".heart"
    assert entries[6].source_label == ".crystal"
    assert entries[0].inline_comment == "inline note"
    assert entries[-1].source_revision == "pinned-sha"


def test_preserves_non_literal_expression_without_evaluating_it() -> None:
    source = """Values:
{
    db $01, SomeConstant, $03+$01
}
"""
    entries = parse_source_data_table(
        source,
        "Values",
        0x200,
        entry_count=3,
    )

    assert entries[0].numeric_value == 1
    assert entries[1].expression == "SomeConstant"
    assert entries[1].numeric_value is None
    assert entries[2].expression == "$03+$01"
    assert entries[2].numeric_value is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"entry_count": 0}, "positive"),
        ({"entry_count": True}, "integer"),
        ({"directive": "foo", "entry_count": 1}, "directive"),
        ({"source": SAMPLE_SOURCE.replace("    .fall_height\\n    db $60, $80\\n", ""), "entry_count": 7, "stop_before_label": ".missing"}, "stop label"),
    ],
)
def test_rejects_invalid_counts_directives_and_boundaries(
    kwargs: dict[str, object], message: str
) -> None:
    base = {
        "source": SAMPLE_SOURCE,
        "label": "Parent.item_values",
        "table_file_offset": 0x1000,
        "directive": "db",
        "entry_count": 7,
        "stop_before_label": ".fall_height",
    }
    base.update(kwargs)
    with pytest.raises((ValueError, DataTableParseError), match=message):
        parse_source_data_table(**base)  # type: ignore[arg-type]


def test_rejects_table_with_more_values_than_declared_count() -> None:
    source = """Parent:
{
    .values
    db $01, $02, $03
    .next
    db $04
}
"""
    with pytest.raises(DataTableParseError, match="more than the expected"):
        parse_source_data_table(
            source,
            "Parent.values",
            0x300,
            entry_count=2,
            stop_before_label=".next",
        )


def test_cli_exports_validated_data_table_json(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    output = tmp_path / "values.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source),
            "Parent.item_values",
            "--table-offset",
            "$1000",
            "--directive",
            "db",
            "--entry-count",
            "7",
            "--stop-before-label",
            ".fall_height",
            "--source-revision",
            "test-revision",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["format"] == "zelda-suite-data-table"
    assert payload["entry_count"] == 7
    assert payload["entries"][-1]["numeric_value"] == 0x20
    assert payload["entries"][1]["entry_file_offset"] == 0x1001
    assert load_source_export(output) == payload

    second = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source),
            "Parent.item_values",
            "--table-offset",
            "$1000",
            "--entry-count",
            "7",
            "--stop-before-label",
            ".fall_height",
            "--output",
            str(output),
        ],
    )
    assert second.exit_code != 0
    assert "refusing to overwrite existing output" in second.output


def test_real_pinned_falling_prize_table_exports_seven_item_values(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source_path = root / "reference" / "AsarUSALTTPDisassembly" / "Ancilla" / "ancilla_init.asm"
    if not source_path.is_file():
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")

    output = tmp_path / "falling-prize-items.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source_path),
            "Pool_AddPendantOrCrystal.item_values",
            "--table-offset",
            "$048B90",
            "--directive",
            "db",
            "--entry-count",
            "7",
            "--stop-before-label",
            ".fall_height",
            "--source-revision",
            "347c23f9fc019c72d32da537c9cb235f468d021d",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_source_export(output)
    entries = payload["entries"]
    assert [entry["numeric_value"] for entry in entries] == [
        0x10, 0x37, 0x39, 0x38, 0x26, 0x0F, 0x20
    ]
    assert [entry["entry_file_offset"] for entry in entries] == list(
        range(0x048B90, 0x048B97)
    )
    assert [entry["source_label"] for entry in entries] == [
        ".ether_medallion",
        ".pendants",
        ".pendants",
        ".pendants",
        ".heart_container",
        ".bombos_medallion",
        ".crystal",
    ]
