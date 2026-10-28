"""CLI tests for mixed-width source table export."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli

SAMPLE_SOURCE = """ExampleOAM:
{
    dw 0, 4 : db $70, $00, $00, $00
    dw 8, 4 : db $70, $40, $00, $00
}
"""


def test_cli_exports_mixed_width_table_and_matches_schema(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "inspect-mixed-data-table",
            str(source),
            "ExampleOAM",
            "--table-offset",
            "$1000",
            "--record-count",
            "2",
            "--source-revision",
            "synthetic-revision",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "schemas"
        / "mixed-data-table-export.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert payload["format"] == "zelda-suite-mixed-data-table"
    assert payload["format_version"] == 1
    assert set(payload) == set(schema["required"])
    assert set(payload["records"][0]) == set(schema["$defs"]["record"]["required"])
    assert payload["record_count"] == 2
    assert payload["byte_count"] == 16
    assert payload["records"][0]["fields"][1]["field_file_offset"] == 0x1004
    assert result.output.endswith("\n")


def test_cli_refuses_to_overwrite_existing_export(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    output = tmp_path / "table.json"
    output.write_text("keep this", encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "inspect-mixed-data-table",
            str(source),
            "ExampleOAM",
            "--table-offset",
            "$1000",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "refusing to overwrite existing output" in result.output
    assert output.read_text(encoding="utf-8") == "keep this"
