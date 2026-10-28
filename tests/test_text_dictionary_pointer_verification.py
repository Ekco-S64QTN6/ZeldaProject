"""Tests for read-only text dictionary pointer word verification."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.rom_image import EXPECTED_US_ROM_SIZE, lorom_cpu_address
from zelda_suite.extract.text_dictionary_pointer_verification import (
    verify_text_dictionary_pointers,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
POINTER_EXPORT_PATH = ROOT / "data" / "extracted" / "text-dictionary-pointers.json"
FRAGMENT_EXPORT_PATH = ROOT / "data" / "extracted" / "text-dictionary-fragments.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _write_synthetic_rom(tmp_path: Path) -> Path:
    pointers = json.loads(POINTER_EXPORT_PATH.read_text(encoding="utf-8"))
    fragments = json.loads(FRAGMENT_EXPORT_PATH.read_text(encoding="utf-8"))
    fragments_by_expression = {
        fragment["pointer_expression"]: fragment for fragment in fragments["fragments"]
    }
    rom = bytearray(EXPECTED_US_ROM_SIZE)
    for pointer in pointers["entries"]:
        fragment = fragments_by_expression[pointer["expression"]]
        offset = fragment["fragment_file_offset"]
        candidate_word = lorom_cpu_address(offset) & 0xFFFF
        entry_offset = pointer["entry_file_offset"]
        rom[entry_offset:entry_offset + 2] = candidate_word.to_bytes(2, "little")

    path = tmp_path / "synthetic-text-dictionary-rom.smc"
    path.write_bytes(rom)
    return path


def test_verifier_checks_98_words_and_preserves_known_source_diagnostics(
    tmp_path: Path,
) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    original = rom_path.read_bytes()

    report = verify_text_dictionary_pointers(rom_path, REGISTRY_PATH)

    assert report["format"] == "zelda-suite-text-dictionary-pointer-verification"
    assert report["format_version"] == 1
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["rom"]["provenance_verified"] is False
    assert report["pointer_table"] == {
        "label": "DictionaryPointers",
        "file_offset": 0x074703,
        "entry_width_bytes": 2,
        "entry_count": 98,
        "unique_target_label_count": 98,
        "checked_comparisons": 98,
        "mismatch_count": 0,
        "source_extent_mismatch_count": 1,
    }
    assert len(report["entries"]) == 98
    assert report["entries"][0]["pointer_entry_file_offset"] == 0x074703
    assert report["entries"][0]["candidate_pointer_word"] == "$C7C7"
    assert report["entries"][96]["target_fragment_label"] == ".You"
    assert report["entries"][96]["target_fragment_file_offset"] == 0x0748D6
    assert report["entries"][96]["candidate_pointer_word"] == "$C8D6"
    assert report["entries"][-1]["target_fragment_label"] == ".endOfTable"
    assert report["entries"][-1]["candidate_pointer_word"] == "$C8D8"
    assert report["mismatches"] == []
    assert report["source_findings"] == [{
        "code": "source_extent_mismatch",
        "severity": "warning",
        "pointer_index": 96,
        "pointer_expression": "DictionaryEntries_You",
        "fragment_label": ".You",
        "message": (
            "Source extent is 2 byte(s), while the declared directive values describe "
            "6 byte(s); neither value was changed by this audit."
        ),
    }]
    assert report["source_symbol_name_mapping_verified"] is False
    assert report["source_offsets_verified"] is False
    assert report["fragment_payload_bytes_verified"] is False
    assert report["semantic_text_decoded"] is False
    assert report["rom_modified"] is False
    assert rom_path.read_bytes() == original


def test_verifier_reports_pointer_byte_mismatch(tmp_path: Path) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    rom = bytearray(rom_path.read_bytes())
    rom[0x074703 + (7 * 2)] ^= 0x01
    rom_path.write_bytes(rom)

    report = verify_text_dictionary_pointers(rom_path, REGISTRY_PATH)

    assert report["pointer_table"]["mismatch_count"] == 1
    assert len(report["mismatches"]) == 1
    assert report["mismatches"][0]["table_index"] == 7
    assert report["mismatches"][0]["pointer_expression"] == "DictionaryEntries_ain"
    assert report["entries"][7]["status"] == "fail"


def test_cli_writes_report_refuses_overwrite_and_exits_nonzero_on_mismatch(
    tmp_path: Path,
) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    output = tmp_path / "dictionary-pointer-verification.json"
    runner = CliRunner()
    arguments = [
        "verify-text-dictionary-pointers",
        str(rom_path),
        "--registry",
        str(REGISTRY_PATH),
    ]

    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    assert '"mismatch_count": 0' in result.output

    written = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert '"mismatch_count": 0' in output.read_text(encoding="utf-8")
    assert "checked=98, mismatches=0" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output

    rom = bytearray(rom_path.read_bytes())
    rom[0x074703] ^= 0x01
    rom_path.write_bytes(rom)
    failed = runner.invoke(cli, arguments)
    assert failed.exit_code == 1
    assert '"mismatch_count": 1' in failed.output


def test_verifier_rejects_wrong_rom_size(tmp_path: Path) -> None:
    rom_path = tmp_path / "too-short.smc"
    rom_path.write_bytes(bytes(1024))

    try:
        verify_text_dictionary_pointers(rom_path, REGISTRY_PATH)
    except ValueError as exc:
        assert "expected headerless 1 MiB image" in str(exc)
    else:
        raise AssertionError("verifier accepted a short ROM image")
