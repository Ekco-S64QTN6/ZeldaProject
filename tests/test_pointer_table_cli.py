"""CLI tests for source-level disassembly pointer table inspection."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import _parse_offset_text, cli

SAMPLE_SOURCE = """; test-only synthetic source — not ROM data
ExamplePointers:
{
    dl FirstTarget
    dl RoomDataTiles_Empty+$0008
    dl ThirdTarget, FourthTarget+$0010
}
"""


def test_cli_inspects_pointer_table_to_json_stdout(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "ExamplePointers",
            "--table-offset",
            "$0F8000",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["entry_count"] == 4
    assert payload["source_revision"] == "unspecified"
    assert payload["entries"][1]["pointer_entry_file_offset"] == 0x0F8003
    assert payload["entries"][1]["is_empty_target"] is True
    assert payload["entries"][1]["source_revision"] == "unspecified"
    assert result.output.endswith("\n")


def test_cli_writes_output_file_without_overwriting(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    output = tmp_path / "table.json"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "ExamplePointers",
            "--table-offset",
            "0x0F8000",
            "--source-revision",
            "test-revision",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_revision"] == "test-revision"
    assert payload["entry_count"] == 4
    assert "Wrote 4 pointer-table entries" in result.output

    second_result = runner.invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "ExamplePointers",
            "--table-offset",
            "$0F8000",
            "--output",
            str(output),
        ],
    )
    assert second_result.exit_code != 0
    assert "refusing to overwrite existing output" in second_result.output
    assert json.loads(output.read_text(encoding="utf-8")) == payload


def test_cli_reports_invalid_source_table_and_offset(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")

    missing_label = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "MissingPointers",
            "--table-offset",
            "$0F8000",
        ],
    )
    assert missing_label.exit_code != 0
    assert "label not found" in missing_label.output

    invalid_offset = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "ExamplePointers",
            "--table-offset",
            "$not-hex",
        ],
    )
    assert invalid_offset.exit_code != 0
    assert "use a decimal" in invalid_offset.output



def test_offset_parser_accepts_decimal_and_prefixed_values() -> None:
    assert _parse_offset_text("0") == 0
    assert _parse_offset_text("000") == 0
    assert _parse_offset_text("123") == 123
    assert _parse_offset_text("0x7B") == 123
    assert _parse_offset_text("$7B") == 123



def test_pointer_table_json_schema_matches_cli_payload(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "schemas"
        / "pointer-table-export.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "ExamplePointers",
            "--table-offset",
            "0",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == set(schema["required"])
    assert set(payload["entries"][0]) == set(schema["$defs"]["entry"]["required"])



def test_cli_inspects_dw_pointer_table_with_two_byte_offsets(tmp_path: Path) -> None:
    source = tmp_path / "word-pointers.asm"
    source.write_text(
        """WordPointers:
{
    dw FirstTarget
    dw SecondTarget+$0002
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(source),
            "WordPointers",
            "--table-offset",
            "$0DC2F9",
            "--directive",
            "dw",
            "--source-revision",
            "pinned-sha",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 2
    assert payload["entries"][0]["pointer_entry_file_offset"] == 0x0DC2F9
    assert payload["entries"][1]["pointer_entry_file_offset"] == 0x0DC2FB
    assert payload["entries"][1]["target_addend"] == 2
