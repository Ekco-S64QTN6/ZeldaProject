"""Tests for source-only audit of registered incbin inventories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.incbin_inventory_audit import audit_incbin_inventories

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _declaration(
    label: str,
    *,
    source_line: int,
    start: int | None,
    size: int | None,
    end: int | None = None,
) -> dict[str, Any]:
    computed_end = start + size - 1 if start is not None and size is not None and size > 0 else None
    range_matches = (
        (end - start + 1) == size
        if start is not None and end is not None and size is not None
        else None
    )
    return {
        "source_file": "Bank0A.asm",
        "source_revision": "synthetic-revision",
        "label": label,
        "source_line": source_line,
        "incbin_path": f"bin/{label}.bin",
        "declared_size_bytes": size,
        "source_file_offset_start": start,
        "source_file_offset_end": end,
        "computed_file_offset_end": computed_end,
        "source_range_size_matches": range_matches,
    }


def _write_registry(tmp_path: Path) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    first_declarations = [
        _declaration("First", source_line=2, start=0x100, size=6, end=0x105),
        _declaration("Overlap", source_line=5, start=0x104, size=5, end=0x108),
        _declaration("MissingStart", source_line=8, start=None, size=16),
        _declaration("RangeMismatch", source_line=11, start=0x200, size=4, end=0x201),
    ]
    second_declarations = [
        _declaration("MissingSize", source_line=3, start=0x300, size=None),
    ]
    assets = []
    for name, source_file, declarations in [
        ("fixture-bank0a", "Bank0A.asm", first_declarations),
        ("fixture-bank0b", "Bank0B.asm", second_declarations),
    ]:
        for declaration in declarations:
            declaration["source_file"] = source_file
        payload = {
            "format": "zelda-suite-incbin-inventory",
            "format_version": 1,
            "source_file": source_file,
            "source_revision": "synthetic-revision",
            "declaration_count": len(declarations),
            "declarations": declarations,
        }
        filename = f"{name}.json"
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assets.append({
            "name": name,
            "file": filename,
            "format": "zelda-suite-incbin-inventory",
            "source_revision": "synthetic-revision",
            "record_count": len(declarations),
            "subsystem": "test",
            "description": "Synthetic source-only inventory for audit tests.",
        })
    registry = {
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": assets,
    }
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_audit_reports_metadata_gaps_mismatches_and_candidate_overlaps(
    tmp_path: Path,
) -> None:
    registry = _write_registry(tmp_path)

    report = audit_incbin_inventories(registry)

    assert report["format"] == "zelda-suite-incbin-inventory-audit"
    assert report["format_version"] == 1
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "payload_bytes_read": False,
        "offsets_verified": False,
    }
    assert report["summary"] == {
        "inventory_count": 2,
        "declaration_count": 5,
        "located_declaration_count": 3,
        "missing_start_count": 1,
        "missing_size_count": 1,
        "metadata_gap_count": 2,
        "range_mismatch_count": 1,
        "candidate_span_count": 3,
        "candidate_overlap_count": 1,
        "finding_count": 4,
    }
    assert report["metadata_gaps"][0]["label"] == "MissingStart"
    assert report["metadata_gaps"][0]["missing_fields"] == ["source_file_offset_start"]
    assert report["metadata_gaps"][1]["label"] == "MissingSize"
    assert report["metadata_gaps"][1]["missing_fields"] == ["declared_size_bytes"]
    assert report["range_mismatches"][0]["label"] == "RangeMismatch"
    overlap = report["candidate_overlaps"][0]
    assert overlap["left"]["label"] == "First"
    assert overlap["right"]["label"] == "Overlap"
    assert overlap["overlap_start"] == 0x104
    assert overlap["overlap_end"] == 0x105
    assert overlap["overlap_size_bytes"] == 2
    assert report == audit_incbin_inventories(registry)


def test_audit_cli_writes_report_and_optional_findings_exit(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "audit.json"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["audit-incbin-inventory", "--registry", str(registry), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["candidate_overlap_count"] == 1
    assert "metadata_gaps=2" in result.output
    assert "candidate_overlaps=1" in result.output

    fail_result = runner.invoke(
        cli,
        [
            "audit-incbin-inventory",
            "--registry",
            str(registry),
            "--fail-on-findings",
        ],
    )
    assert fail_result.exit_code == 1
    assert json.loads(fail_result.output)["summary"]["finding_count"] == 4


def test_audit_cli_refuses_to_overwrite_output(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "audit.json"
    output.write_text("keep me", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["audit-incbin-inventory", "--registry", str(registry), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "refusing to overwrite existing output" in result.output
    assert output.read_text(encoding="utf-8") == "keep me"



def test_audit_pins_current_registered_inventory_baseline() -> None:
    """Keep the checked-in inventory scope and findings visible in CI."""
    report = audit_incbin_inventories(REGISTERED_MANIFEST)

    assert [inventory["asset_name"] for inventory in report["inventories"]] == [
        "dungeon-room-payload-inventory",
        "dungeon-room-payloads-bank03",
        "dungeon-room-payloads-bank1f",
        "music-payload-inventory",
        "overworld-payloads-bank0b",
        "overworld-payloads-bank0c",
    ]
    assert all(
        inventory["source_revision"] == PINNED_SOURCE_REVISION
        for inventory in report["inventories"]
    )
    assert report["summary"] == {
        "inventory_count": 6,
        "declaration_count": 529,
        "located_declaration_count": 525,
        "missing_start_count": 1,
        "missing_size_count": 3,
        "metadata_gap_count": 4,
        "range_mismatch_count": 3,
        "candidate_span_count": 525,
        "candidate_overlap_count": 10,
        "finding_count": 17,
    }
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "payload_bytes_read": False,
        "offsets_verified": False,
    }
    assert report == audit_incbin_inventories(REGISTERED_MANIFEST)
