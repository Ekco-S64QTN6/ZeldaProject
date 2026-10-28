"""Tests for read-only registered scalar-table verification against ROM bytes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.rom_image import EXPECTED_US_ROM_SIZE
from zelda_suite.extract.rom_table_verification import (
    ROMTableVerificationError,
    verify_registered_scalar_tables,
)


def _write_fixture_registry(
    tmp_path: Path,
    table_specs: list[dict[str, Any]],
) -> Path:
    extracted_dir = tmp_path / "data" / "extracted"
    extracted_dir.mkdir(parents=True)
    records = []
    for spec in table_specs:
        name = spec["name"]
        width = spec.get("entry_stride", {"db": 1, "dw": 2, "dl": 3}[spec["directive"]])
        offset = spec["offset"]
        values = spec["values"]
        entries = []
        for index, value in enumerate(values):
            entries.append({
                "table_index": index,
                "entry_file_offset": offset + index * width,
                "source_line": index + 1,
                "source_label": ".values",
                "expression": f"${value:02X}" if value is not None else "UnresolvedExpression",
                "literal_value": value,
                "source_revision": "fixture-revision",
            })
        payload = {
            "format": "zelda-suite-data-table",
            "format_version": 1,
            "source_file": "fixture.asm",
            "source_revision": "fixture-revision",
            "parent_label": "Fixture",
            "table_label": ".values",
            "end_label": ".end",
            "table_file_offset": offset,
            "directive": spec["directive"],
            "entry_width": width,
            "entry_count": len(entries),
            "entries": entries,
        }
        (extracted_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        records.append({
            "name": name,
            "file": f"{name}.json",
            "format": "zelda-suite-data-table",
            "source_revision": "fixture-revision",
            "record_count": len(entries),
            "subsystem": "test",
            "description": "Synthetic table fixture.",
        })

    registry_path = extracted_dir / "manifest.json"
    registry_path.write_text(
        json.dumps({
            "format": "zelda-suite-asset-registry",
            "format_version": 1,
            "assets": records,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def _write_fixture_rom(tmp_path: Path, *, wrong_size: bool = False) -> Path:
    size = 128 if wrong_size else EXPECTED_US_ROM_SIZE
    rom = bytearray(size)
    if not wrong_size:
        rom[0x100] = 0x42
        rom[0x300:0x302] = bytes([0x34, 0x12])
        rom[0x304:0x306] = bytes([0x78, 0x56])
    path = tmp_path / "fixture.smc"
    path.write_bytes(rom)
    return path


def _table_specs() -> list[dict[str, Any]]:
    return [
        {"name": "sample-values", "directive": "db", "offset": 0x100, "values": [0x42, None]},
        {"name": "all-symbolic", "directive": "db", "offset": 0x200, "values": [None, None]},
        {
            "name": "strided-words",
            "directive": "dw",
            "offset": 0x300,
            "entry_stride": 4,
            "values": [0x1234, 0x5678],
        },
        {"name": "wrong-values", "directive": "db", "offset": 0x102, "values": [0x55]},
    ]


def test_verifies_registered_tables_and_distinguishes_skips_from_passes(
    tmp_path: Path,
) -> None:
    rom_path = _write_fixture_rom(tmp_path)
    original = rom_path.read_bytes()
    registry = _write_fixture_registry(tmp_path, _table_specs())

    report = verify_registered_scalar_tables(rom_path, registry)

    assert report["format"] == "zelda-suite-rom-table-verification"
    assert report["rom"]["provenance_verified"] is False
    assert report["rom"]["sha256"]
    assert report["summary"] == {
        "table_asset_count": 4,
        "pass_asset_count": 1,
        "partial_asset_count": 1,
        "skipped_asset_count": 1,
        "failed_asset_count": 1,
        "checked_entries": 4,
        "skipped_entries": 3,
        "mismatches": 1,
    }
    by_name = {asset["name"]: asset for asset in report["assets"]}
    assert by_name["sample-values"]["status"] == "partial"
    assert by_name["sample-values"]["checked_entries"] == 1
    assert by_name["sample-values"]["skipped_entries"] == 1
    assert by_name["all-symbolic"]["status"] == "skip"
    assert by_name["all-symbolic"]["checked_entries"] == 0
    assert by_name["strided-words"]["status"] == "pass"
    assert by_name["strided-words"]["literal_width_bytes"] == 2
    assert by_name["strided-words"]["entry_stride_bytes"] == 4
    assert by_name["wrong-values"]["status"] == "fail"
    assert by_name["wrong-values"]["mismatches"][0]["offset"] == 0x102
    assert rom_path.read_bytes() == original


def test_rejects_wrong_rom_size(tmp_path: Path) -> None:
    rom_path = _write_fixture_rom(tmp_path, wrong_size=True)
    registry = _write_fixture_registry(tmp_path, _table_specs())

    try:
        verify_registered_scalar_tables(rom_path, registry)
    except ROMTableVerificationError as exc:
        assert "expected headerless 1 MiB image" in str(exc)
    else:
        raise AssertionError("wrong-size ROM should be rejected")


def test_verify_rom_tables_cli_returns_nonzero_and_emits_report_on_mismatch(
    tmp_path: Path,
) -> None:
    rom_path = _write_fixture_rom(tmp_path)
    registry = _write_fixture_registry(tmp_path, _table_specs())

    result = CliRunner().invoke(
        cli,
        ["verify-rom-tables", str(rom_path), "--registry", str(registry)],
    )

    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["summary"]["mismatches"] == 1
    assert report["format"] == "zelda-suite-rom-table-verification"


def test_verify_rom_tables_cli_writes_new_report_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    rom_path = _write_fixture_rom(tmp_path)
    registry = _write_fixture_registry(tmp_path, _table_specs())
    output = tmp_path / "verification.json"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["verify-rom-tables", str(rom_path), "--registry", str(registry), "--output", str(output)],
    )

    assert result.exit_code == 1
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["mismatches"] == 1
    assert "mismatches=1" in result.output

    refused = runner.invoke(
        cli,
        ["verify-rom-tables", str(rom_path), "--registry", str(registry), "--output", str(output)],
    )
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
