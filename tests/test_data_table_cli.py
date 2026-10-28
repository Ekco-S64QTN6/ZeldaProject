"""CLI tests for raw Asar data-table inspection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.asset_loader import AssetLoadError, validate_source_export

SAMPLE_SOURCE = """ExampleScope:
{
    .values
    .medallions
    db $10, $0F ; medal table
    .end_values
    db $FF
}
"""


def test_cli_exports_raw_data_table_json_and_matches_schema(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source),
            ".values",
            "--table-offset",
            "$048B90",
            "--directive",
            "db",
            "--parent-label",
            "ExampleScope",
            "--end-label",
            ".end_values",
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
        / "data-table-export.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert set(payload) == set(schema["required"])
    assert set(payload["entries"][0]) == set(schema["$defs"]["entry"]["required"])
    assert payload["entry_count"] == 2
    assert payload["entries"][0]["entry_file_offset"] == 0x048B90
    assert payload["entries"][1]["entry_file_offset"] == 0x048B91
    assert [entry["literal_value"] for entry in payload["entries"]] == [0x10, 0x0F]
    assert [entry["source_label"] for entry in payload["entries"]] == [
        ".medallions",
        ".medallions",
    ]
    assert result.output.endswith("\n")


def test_cli_writes_data_table_export_to_a_new_file(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    output = tmp_path / "data-table.json"
    runner = CliRunner()
    args = [
        "inspect-data-table",
        str(source),
        ".values",
        "--table-offset",
        "0x200",
        "--parent-label",
        "ExampleScope",
        "--end-label",
        ".end_values",
        "--output",
        str(output),
    ]

    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert output.is_file()
    saved_payload = json.loads(output.read_text(encoding="utf-8"))
    assert saved_payload["directive"] == "db"
    assert saved_payload["entry_count"] == 2

    refused = runner.invoke(cli, args)
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


def test_cli_rejects_missing_data_table_label(tmp_path: Path) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source),
            ".missing",
            "--table-offset",
            "$0200",
            "--parent-label",
            "ExampleScope",
        ],
    )
    assert result.exit_code != 0
    assert "not found inside parent block" in result.output

def test_cli_opt_in_comment_export_uses_v2_schema_and_validates(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "inspect-data-table",
            str(source),
            ".values",
            "--table-offset",
            "$048B90",
            "--directive",
            "db",
            "--parent-label",
            "ExampleScope",
            "--end-label",
            ".end_values",
            "--source-revision",
            "synthetic-revision",
            "--include-comments",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format_version"] == 2
    assert payload["entry_count"] == 2
    assert [entry["inline_comment"] for entry in payload["entries"]] == [
        "medal table",
        "medal table",
    ]
    assert validate_source_export(payload) == payload

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "schemas"
        / "data-table-export-v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert payload["format_version"] == schema["properties"]["format_version"]["const"]
    assert set(payload["entries"][0]) == set(schema["$defs"]["entry"]["required"])

    malformed = json.loads(json.dumps(payload))
    malformed["entries"][0]["inline_comment"] = 7
    with pytest.raises(AssetLoadError, match="inline_comment must be a string or null"):
        validate_source_export(malformed)

