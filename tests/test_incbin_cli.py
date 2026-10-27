"""CLI tests for source-level incbin inventory."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli

SAMPLE_SOURCE = """; $058000-$058003 DATA
Screen00_High:
{
    incbin "bin/ow/screen00-h.bin" ; Size: 0x0004
}
; $050000
RoomDataTiles_0104:
incbin "bin/rooms/room0104.bin" ; Size: 0x0047
"""


def test_cli_emits_stable_incbin_inventory_json(tmp_path: Path) -> None:
    source = tmp_path / "Bank0B.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")

    result = CliRunner().invoke(cli, ["inspect-incbin", str(source)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format"] == "zelda-suite-incbin-inventory"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "Bank0B.asm"
    assert payload["source_revision"] == "unspecified"
    assert payload["declaration_count"] == 2
    first, second = payload["declarations"]
    assert first["label"] == "Screen00_High"
    assert first["source_file_offset_start"] == 0x058000
    assert first["source_range_size_matches"] is True
    assert second["label"] == "RoomDataTiles_0104"
    assert second["computed_file_offset_end"] == 0x050046
    assert result.output.endswith("\n")


def test_cli_records_revision_and_refuses_to_overwrite_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Bank0B.asm"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    output = tmp_path / "inventory.json"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "inspect-incbin",
            str(source),
            "--source-revision",
            "pinned-test-revision",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    first_payload = json.loads(output.read_text(encoding="utf-8"))
    assert first_payload["source_revision"] == "pinned-test-revision"
    assert "Wrote 2 incbin declarations" in result.output

    second = runner.invoke(
        cli,
        ["inspect-incbin", str(source), "--output", str(output)],
    )
    assert second.exit_code != 0
    assert "refusing to overwrite existing output" in second.output
    assert json.loads(output.read_text(encoding="utf-8")) == first_payload


def test_cli_reports_malformed_incbin_source(tmp_path: Path) -> None:
    source = tmp_path / "broken.asm"
    source.write_text('incbin "orphan.bin" ; Size: 4\n', encoding="utf-8")

    result = CliRunner().invoke(cli, ["inspect-incbin", str(source)])

    assert result.exit_code != 0
    assert "no preceding label" in result.output
