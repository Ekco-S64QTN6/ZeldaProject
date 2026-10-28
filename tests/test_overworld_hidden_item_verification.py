"""Tests for read-only overworld hidden-item pointer and record verification."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    lorom_cpu_address,
    parse_overworld_hidden_item_source,
    verify_overworld_hidden_items,
)
from zelda_suite.extract.rom_image import EXPECTED_US_ROM_SIZE

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

pytestmark = pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)


def _source_text() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _write_rom_from_source(tmp_path: Path) -> tuple[Path, dict]:
    source = _source_text()
    layout = parse_overworld_hidden_item_source(source)
    rom = bytearray(EXPECTED_US_ROM_SIZE)

    for pointer in layout["pointer_entries"]:
        target_offset = layout["label_offsets"][pointer["target_label"]]
        if pointer["target_addend"] is not None:
            target_offset += pointer["target_addend"]
        target_word = lorom_cpu_address(target_offset) & 0xFFFF
        offset = pointer["pointer_entry_file_offset"]
        rom[offset:offset + 2] = target_word.to_bytes(2, "little")

    for record in layout["records"]:
        offset = record["file_offset"]
        expected = (
            record["coordinate_word"].to_bytes(2, "little")
            + bytes([record["value_byte"]])
        )
        rom[offset:offset + 3] = expected

    for sentinel in layout["sentinels"]:
        offset = sentinel["file_offset"]
        rom[offset:offset + 2] = b"\xFF\xFF"

    for word in layout["replacement_words"]:
        offset = word["file_offset"]
        rom[offset:offset + 2] = word["value"].to_bytes(2, "little")

    path = tmp_path / "synthetic-from-pinned-source.smc"
    path.write_bytes(rom)
    return path, layout


def test_source_layout_parses_expected_mixed_width_region_and_pointer_targets() -> None:
    layout = parse_overworld_hidden_item_source(
        _source_text(),
    )

    assert len(layout["pointer_entries"]) == 128
    assert len(layout["label_offsets"]) == 80
    assert len(layout["records"]) == 351
    assert len(layout["sentinels"]) == 67
    assert len(layout["replacement_words"]) == 4
    assert layout["data_start_offset"] == 0x0DC3F9
    assert layout["data_end_exclusive"] == 0x0DC89C
    assert layout["data_end_exclusive"] - layout["data_start_offset"] == 1187
    assert (
        len(layout["records"]) * 3 + len(layout["sentinels"]) * 2
        == 1187
    )
    assert layout["label_offsets"]["OverworldData_HiddenItems_Screen_00"] == 0x0DC3F9
    assert layout["pointer_entries"][0]["target_label"] == "OverworldData_HiddenItems_Screen_00"
    assert layout["replacement_words"][0]["value"] == 0x0DCC
    assert len(layout["area_lists"]) == 128
    assert layout["area_lists"][0]["record_count"] == 4
    assert layout["area_lists"][7]["record_count"] == 0


def test_verifier_matches_synthetic_rom_encoded_from_pinned_source_and_is_read_only(
    tmp_path: Path,
) -> None:
    rom_path, _layout = _write_rom_from_source(tmp_path)
    original = rom_path.read_bytes()

    report = verify_overworld_hidden_items(
        rom_path,
        _source_text(),
    )

    assert report["format"] == "zelda-suite-overworld-hidden-item-verification"
    assert report["format_version"] == 1
    assert report["rom"]["provenance_verified"] is False
    assert report["source_revision"] == PINNED_REVISION
    assert report["source_layout"] == {
        "pointer_count": 128,
        "distinct_target_label_count": 80,
        "three_byte_record_count": 351,
        "two_byte_sentinel_count": 67,
        "replacement_word_count": 4,
        "data_start_offset": 0x0DC3F9,
        "data_end_exclusive": 0x0DC89C,
        "data_region_size_bytes": 1187,
    }
    assert len(report["area_lists"]) == 128
    assert report["area_lists"][0]["record_count"] == 4
    assert report["area_lists"][7]["record_count"] == 0
    assert report["checked_comparisons"] == 550
    assert report["mismatch_count"] == 0
    assert report["mismatches"] == []
    assert report["semantic_values_decoded"] is False
    assert report["rom_modified"] is False
    assert rom_path.read_bytes() == original


def test_verifier_reports_pointer_record_sentinel_and_replacement_mismatches(
    tmp_path: Path,
) -> None:
    rom_path, layout = _write_rom_from_source(tmp_path)
    rom = bytearray(rom_path.read_bytes())

    pointer_offset = layout["pointer_entries"][0]["pointer_entry_file_offset"]
    record_offset = layout["records"][0]["file_offset"]
    sentinel_offset = layout["sentinels"][0]["file_offset"]
    replacement_offset = layout["replacement_words"][0]["file_offset"]
    for offset in (pointer_offset, record_offset, sentinel_offset, replacement_offset):
        rom[offset] ^= 0x01
    rom_path.write_bytes(rom)

    report = verify_overworld_hidden_items(
        rom_path,
        _source_text(),
    )

    assert report["mismatch_count"] == 4
    assert {item["kind"] for item in report["mismatches"]} == {
        "pointer",
        "record",
        "sentinel",
        "replacement-map16",
    }
    assert all(item["reason"] == "ROM bytes do not match the source declaration"
               for item in report["mismatches"])


def test_hidden_item_cli_emits_report_and_refuses_overwrite(tmp_path: Path) -> None:
    rom_path, _layout = _write_rom_from_source(tmp_path)
    output = tmp_path / "hidden-items.json"
    arguments = ["verify-overworld-hidden-items", str(rom_path)]
    runner = CliRunner()

    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    assert '"mismatch_count": 0' in result.output

    written = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert '"mismatch_count": 0' in output.read_text(encoding="utf-8")
    assert "checked=550, mismatches=0" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


def test_parser_rejects_a_missing_or_shortened_source_region() -> None:
    source = _source_text()
    start = source.index("; $0DC3F9-$0DC89B Overworld secrets data")
    end = source.index("; $0DC89C-$0DC8A3 DATA", start)
    altered_region = source[start:end].replace("dw $FFFF", "dw $FFFE", 1)
    altered = source[:start] + altered_region + source[end:]

    with pytest.raises(
        ValueError,
        match="unsupported declaration|expected 67 two-byte sentinels",
    ):
        parse_overworld_hidden_item_source(altered, source_revision=PINNED_REVISION)
