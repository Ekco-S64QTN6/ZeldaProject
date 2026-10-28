"""Tests for the source-only OAM allocator audit report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.oam_allocation_audit import (
    OAM_ALLOCATION_AUDIT_FORMAT,
    OAMAllocationAuditError,
    audit_oam_allocation,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_FILE_OFFSET = 0x06BA9E
ASSET_NAME = "oam-buffer-position-table"
LIMIT_VALUES = [0x0171, 0x0201, 0x0031, 0x00C1, 0x0141, 0x01D1]
FALLBACK_ROWS = [
    [0x0030, 0x0050, 0x0080, 0x00B0, 0x00E0, 0x0110, 0x0140, 0x0170],
    [0x01D0, 0x01D4, 0x01DC, 0x01E0, 0x01E4, 0x01EC, 0x01F0, 0x01F8],
    [0x0000, 0x0004, 0x0008, 0x000C, 0x0010, 0x0014, 0x0018, 0x001C],
    [0x0030, 0x0038, 0x0050, 0x0068, 0x0080, 0x0098, 0x00B0, 0x00C8],
    [0x0120, 0x0124, 0x0128, 0x012C, 0x0130, 0x0134, 0x0138, 0x013C],
    [0x0140, 0x0150, 0x0160, 0x0170, 0x0180, 0x0190, 0x01A0, 0x01B8],
]


def _export(revision: str = "synthetic-revision") -> dict[str, Any]:
    values = [*LIMIT_VALUES, *(value for row in FALLBACK_ROWS for value in row)]
    entries: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        entries.append({
            "table_index": index,
            "entry_file_offset": TABLE_FILE_OFFSET + index * 2,
            "source_line": 70 + index,
            "source_label": ".limits" if index < 6 else ".fallback_points",
            "expression": "$" + f"{value:04X}",
            "literal_value": value,
            "source_revision": revision,
        })
    return {
        "format": "zelda-suite-data-table",
        "format_version": 1,
        "source_file": "sprite_oam_allocation.asm",
        "source_revision": revision,
        "parent_label": None,
        "table_label": "Pool_OAM_GetBufferPosition",
        "end_label": None,
        "table_file_offset": TABLE_FILE_OFFSET,
        "directive": "dw",
        "entry_width": 2,
        "entry_count": len(entries),
        "entries": entries,
    }


def _write_registry(tmp_path: Path, *, mutate_entry: tuple[int, str, Any] | None = None) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    payload = _export()
    if mutate_entry is not None:
        index, key, value = mutate_entry
        payload["entries"][index][key] = value
    filename = f"{ASSET_NAME}.json"
    (extracted / filename).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry = {
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": [{
            "name": ASSET_NAME,
            "file": filename,
            "format": "zelda-suite-data-table",
            "source_revision": payload["source_revision"],
            "record_count": 54,
            "subsystem": "sprites",
            "description": "Synthetic OAM allocator table used by audit tests.",
        }],
    }
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_audit_groups_six_limits_with_eight_fallback_points_each(tmp_path: Path) -> None:
    report = audit_oam_allocation(_write_registry(tmp_path))

    assert report["format"] == OAM_ALLOCATION_AUDIT_FORMAT
    assert report["format_version"] == 1
    assert report["summary"] == {
        "table_entry_count": 54,
        "region_count": 6,
        "limit_entry_count": 6,
        "fallback_point_count": 48,
        "fallback_points_per_region": 8,
    }
    assert [region["region_name"] for region in report["regions"]] == list("ABCDEF")
    assert [region["allocator_y"] for region in report["regions"]] == [
        0x00, 0x02, 0x04, 0x06, 0x08, 0x0A
    ]
    assert [
        region["limit_entry"]["literal_value"] for region in report["regions"]
    ] == LIMIT_VALUES
    assert [
        [point["entry"]["literal_value"] for point in region["fallback_points"]]
        for region in report["regions"]
    ] == FALLBACK_ROWS
    assert [
        [point["overflow_counter_slot"] for point in region["fallback_points"]]
        for region in report["regions"]
    ] == [list(range(8))] * 6
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "oam_runtime_executed": False,
        "source_comment_offsets_verified": False,
        "oam_buffer_positions_verified": False,
    }


def test_audit_rejects_a_broken_limit_fallback_boundary(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path, mutate_entry=(6, "source_label", ".limits"))

    with pytest.raises(OAMAllocationAuditError, match=r"entries\[6\]\.source_label"):
        audit_oam_allocation(registry)


def test_audit_pins_registered_oam_allocator_source_inventory() -> None:
    report = audit_oam_allocation(REGISTERED_MANIFEST)

    assert report["source_file"] == "sprite_oam_allocation.asm"
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["table_label"] == "Pool_OAM_GetBufferPosition"
    assert report["table_file_offset"] == TABLE_FILE_OFFSET
    assert report["summary"] == {
        "table_entry_count": 54,
        "region_count": 6,
        "limit_entry_count": 6,
        "fallback_point_count": 48,
        "fallback_points_per_region": 8,
    }
    assert [
        region["limit_entry"]["literal_value"] for region in report["regions"]
    ] == LIMIT_VALUES
    assert [
        [point["entry"]["literal_value"] for point in region["fallback_points"]]
        for region in report["regions"]
    ] == FALLBACK_ROWS
    assert report == audit_oam_allocation(REGISTERED_MANIFEST)


def test_cli_writes_report_and_refuses_to_overwrite_output(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "oam-audit.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "audit-oam-allocation", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["fallback_point_count"] == 48
    assert "regions=6" in written.output
    assert "fallback_points=48" in written.output

    output.write_text("keep existing", encoding="utf-8")
    refused = runner.invoke(cli, [
        "audit-oam-allocation", "--registry", str(registry), "--output", str(output)
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert output.read_text(encoding="utf-8") == "keep existing"
