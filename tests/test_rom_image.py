"""Tests for read-only ROM image inspection and LoROM offset mapping."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.rom_image import (
    COPIER_HEADER_SIZE,
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    format_lorom_cpu_address,
    inspect_rom_image,
    lorom_cpu_address,
)


@pytest.mark.parametrize(
    ("file_offset", "address"),
    [
        (0x000000, "$008000"),
        (0x007FFF, "$00FFFF"),
        (0x008000, "$018000"),
        (0x058000, "$0B8000"),
        (0x0FFFFF, "$1FFFFF"),
    ],
)
def test_maps_headerless_file_offsets_to_canonical_lorom_addresses(
    file_offset: int, address: str
) -> None:
    assert format_lorom_cpu_address(file_offset) == address
    assert f"${lorom_cpu_address(file_offset):06X}" == address


@pytest.mark.parametrize("offset", [-1, EXPECTED_US_ROM_SIZE])
def test_rejects_offsets_outside_headerless_image(offset: int) -> None:
    with pytest.raises(ValueError, match="within a 1 MiB"):
        lorom_cpu_address(offset)


def test_rejects_bool_offset() -> None:
    with pytest.raises(TypeError, match="integer"):
        lorom_cpu_address(True)


def test_inspects_headerless_size_and_hash_without_modifying_file(tmp_path: Path) -> None:
    image = tmp_path / "synthetic-us.smc"
    content = b"Z" * EXPECTED_US_ROM_SIZE
    image.write_bytes(content)

    before = image.read_bytes()
    result = inspect_rom_image(image)
    after = image.read_bytes()

    payload = result.to_dict()
    assert payload["format"] == "zelda-suite-rom-image"
    assert payload["format_version"] == 1
    assert result.filename == "synthetic-us.smc"
    assert result.size_bytes == EXPECTED_US_ROM_SIZE
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert result.is_expected_headerless_size is True
    assert result.header_assessment == "headerless-by-expected-size"
    assert result.offset_map_applicable is True
    assert result.first_cpu_address == "$008000"
    assert result.last_cpu_address == "$1FFFFF"
    assert payload["offset_map"]["example_cpu_address"] == "$0B8000"
    assert before == after


def test_flags_a_512_byte_header_sized_image(tmp_path: Path) -> None:
    image = tmp_path / "headered.smc"
    image.write_bytes(b"H" * (EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE))

    result = inspect_rom_image(image)

    assert result.is_expected_headerless_size is False
    assert result.header_assessment == "copier-header-suspected-by-size"
    assert result.offset_map_applicable is False
    assert result.first_cpu_address is None
    assert result.last_cpu_address is None


def test_reports_unrecognized_size_without_claiming_header_state(tmp_path: Path) -> None:
    image = tmp_path / "partial.bin"
    image.write_bytes(b"test bytes")

    result = inspect_rom_image(image)

    assert result.header_assessment == "unrecognized-size"
    assert result.offset_map_applicable is False
    assert result.sha256 == hashlib.sha256(b"test bytes").hexdigest()


def test_missing_image_has_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ROMImageInspectionError, match="could not read ROM image"):
        inspect_rom_image(tmp_path / "missing.smc")



def test_inspect_rom_cli_emits_metadata_json_and_creates_new_output(
    tmp_path: Path,
) -> None:
    image = tmp_path / "synthetic-us.smc"
    image.write_bytes(b"R" * EXPECTED_US_ROM_SIZE)
    output = tmp_path / "rom-inspection.json"
    runner = CliRunner()

    result = runner.invoke(cli, ["inspect-rom", str(image)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format"] == "zelda-suite-rom-image"
    assert payload["is_expected_headerless_size"] is True
    assert payload["offset_map"]["example_cpu_address"] == "$0B8000"

    written = runner.invoke(cli, ["inspect-rom", str(image), "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert output.is_file()
    assert output.read_text(encoding="utf-8").endswith("\n")

    refused = runner.invoke(cli, ["inspect-rom", str(image), "--output", str(output)])
    assert refused.exit_code != 0
    assert "already exists" in refused.output or "exists" in refused.output
