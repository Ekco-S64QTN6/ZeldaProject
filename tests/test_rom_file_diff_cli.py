"""Tests for file-backed read-only ROM diffs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.rom_image import EXPECTED_US_ROM_SIZE, COPIER_HEADER_SIZE


def _write_base_and_candidate(tmp_path: Path) -> tuple[Path, Path]:
    base_path = tmp_path / "base-us.smc"
    modified_path = tmp_path / "candidate.smc"
    base = b"\x11" * EXPECTED_US_ROM_SIZE
    modified = bytearray(base)
    modified[0x100] = 0x22
    modified[0x101] = 0x23
    modified[0x200] = 0x33
    base_path.write_bytes(base)
    modified_path.write_bytes(modified)
    return base_path, modified_path


def test_diff_rom_cli_reports_metadata_and_deterministic_regions(tmp_path: Path) -> None:
    base_path, modified_path = _write_base_and_candidate(tmp_path)
    base_before = base_path.read_bytes()
    modified_before = modified_path.read_bytes()

    result = CliRunner().invoke(cli, ["diff-rom", str(base_path), str(modified_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format"] == "zelda-suite-rom-file-diff"
    assert payload["format_version"] == 1
    assert payload["base_rom"]["filename"] == "base-us.smc"
    assert payload["base_rom"]["sha256"] == hashlib.sha256(base_before).hexdigest()
    assert payload["modified_rom"]["sha256"] == hashlib.sha256(modified_before).hexdigest()

    diff = payload["diff"]
    assert diff["format"] == "zelda-suite-byte-diff"
    assert diff["original_size"] == EXPECTED_US_ROM_SIZE
    assert diff["modified_size"] == EXPECTED_US_ROM_SIZE
    assert diff["changed_byte_count"] == 3
    assert diff["region_count"] == 2
    assert diff["regions"][0]["start_offset"] == 0x100
    assert diff["regions"][0]["end_offset_exclusive"] == 0x102
    assert diff["regions"][1]["start_offset"] == 0x200
    assert result.output.endswith("\n")
    assert base_path.read_bytes() == base_before
    assert modified_path.read_bytes() == modified_before


def test_diff_rom_cli_writes_new_file_and_refuses_overwrite(tmp_path: Path) -> None:
    base_path, modified_path = _write_base_and_candidate(tmp_path)
    output_path = tmp_path / "diff.json"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["diff-rom", str(base_path), str(modified_path), "--output", str(output_path)],
    )
    assert result.exit_code == 0, result.output
    saved = output_path.read_text(encoding="utf-8")
    assert saved.endswith("\n")
    assert json.loads(saved)["format"] == "zelda-suite-rom-file-diff"

    refused = runner.invoke(
        cli,
        ["diff-rom", str(base_path), str(modified_path), "--output", str(output_path)],
    )
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


def test_diff_rom_cli_rejects_noncanonical_base_size(tmp_path: Path) -> None:
    base_path = tmp_path / "wrong-base.smc"
    modified_path = tmp_path / "candidate.smc"
    base_path.write_bytes(b"short")
    modified_path.write_bytes(b"candidate")

    result = CliRunner().invoke(cli, ["diff-rom", str(base_path), str(modified_path)])

    assert result.exit_code != 0
    assert "base ROM must be the expected headerless 1 MiB image" in result.output


def test_diff_rom_cli_rejects_candidate_with_suspected_copier_header(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "base-us.smc"
    modified_path = tmp_path / "headered-candidate.smc"
    base_path.write_bytes(b"\xAA" * EXPECTED_US_ROM_SIZE)
    modified_path.write_bytes(b"\xBB" * (EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE))

    result = CliRunner().invoke(cli, ["diff-rom", str(base_path), str(modified_path)])

    assert result.exit_code != 0
    assert "suggests a 512-byte copier header" in result.output
