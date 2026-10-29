"""Tests for source-only dungeon door-pointer addend bounds auditing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import audit_dungeon_room_door_pointer_bounds

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _write_registry(
    tmp_path: Path,
    *,
    out_of_bounds: bool = False,
    slot_target_mismatch: bool = False,
    missing_target: bool = False,
    missing_size: bool = False,
) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    revision = "synthetic-revision"
    targets = ["RoomDataTiles_A", "RoomDataTiles_Empty", "RoomDataTiles_B"]
    if missing_target:
        targets[2] = "RoomDataTiles_Missing"
    addends = [1, 0, 4 if out_of_bounds else 2]

    door_entries: list[dict[str, Any]] = []
    object_entries: list[dict[str, Any]] = []
    for index, label in enumerate(targets):
        door_entries.append({
            "table_index": index,
            "pointer_entry_file_offset": 0x0F83C0 + index * 3,
            "source_line": index + 340,
            "pointer_expression": f"{label}+$" + f"{addends[index]:04X}",
            "target_label": label,
            "target_addend": addends[index],
            "is_empty_target": label == "RoomDataTiles_Empty",
            "source_revision": revision,
        })
        object_label = (
            "RoomDataTiles_A"
            if slot_target_mismatch and index == 1
            else label
        )
        object_entries.append({
            "table_index": index,
            "pointer_entry_file_offset": 0x0F8000 + index * 3,
            "source_line": index + 10,
            "pointer_expression": object_label,
            "target_label": object_label,
            "target_addend": None,
            "is_empty_target": object_label == "RoomDataTiles_Empty",
            "source_revision": revision,
        })

    pointer_assets = [
        (
            "dungeon-room-door-pointers",
            "door-pointers.json",
            {
                "format": "zelda-suite-pointer-table",
                "format_version": 1,
                "source_file": "Bank1F.asm",
                "source_revision": revision,
                "table_label": "RoomData_DoorDataPointers",
                "table_file_offset": 0x0F83C0,
                "entry_width": 3,
                "entry_count": len(door_entries),
                "entries": door_entries,
            },
        ),
        (
            "dungeon-room-object-pointers",
            "object-pointers.json",
            {
                "format": "zelda-suite-pointer-table",
                "format_version": 1,
                "source_file": "Bank1F.asm",
                "source_revision": revision,
                "table_label": "RoomData_ObjectDataPointers",
                "table_file_offset": 0x0F8000,
                "entry_width": 3,
                "entry_count": len(object_entries),
                "entries": object_entries,
            },
        ),
    ]

    def declaration(
        label: str, source_file: str, source_line: int, size: int | None, offset: int
    ) -> dict[str, Any]:
        return {
            "source_file": source_file,
            "source_revision": revision,
            "label": label,
            "source_line": source_line,
            "incbin_path": f"bin/rooms/{label}.bin",
            "declared_size_bytes": size,
            "source_file_offset_start": offset,
            "source_file_offset_end": None,
            "computed_file_offset_end": offset + size - 1 if size is not None else None,
            "source_range_size_matches": None,
        }

    payload_specs = [
        (
            "dungeon-room-payloads-bank03",
            "Bank03.asm",
            [declaration("RoomDataTiles_A", "Bank03.asm", 10, 4, 0x3000)],
        ),
        (
            "dungeon-room-payload-inventory",
            "Bank0A.asm",
            [declaration(
                "RoomDataTiles_Empty", "Bank0A.asm", 20,
                None if missing_size else 1, 0x4000,
            )],
        ),
        ("dungeon-room-payloads-bank1f", "Bank1F.asm", [declaration("RoomDataTiles_B", "Bank1F.asm", 30, 3, 0x5000)]),
    ]
    exports: list[tuple[str, str, dict[str, Any], str, int]] = [
        (name, filename, payload, "zelda-suite-pointer-table", payload["entry_count"])
        for name, filename, payload in pointer_assets
    ]
    for name, source_file, declarations in payload_specs:
        payload = {
            "format": "zelda-suite-incbin-inventory",
            "format_version": 1,
            "source_file": source_file,
            "source_revision": revision,
            "declaration_count": len(declarations),
            "declarations": declarations,
        }
        exports.append((
            name, name + ".json", payload, "zelda-suite-incbin-inventory", len(declarations)
        ))

    registry_assets = []
    for name, filename, payload, format_name, count in exports:
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        registry_assets.append({
            "name": name,
            "file": filename,
            "format": format_name,
            "source_revision": revision,
            "record_count": count,
            "subsystem": "dungeons",
            "description": "Synthetic audit fixture.",
        })

    manifest = extracted / "manifest.json"
    manifest.write_text(
        json.dumps({
            "format": "zelda-suite-asset-registry",
            "format_version": 1,
            "assets": registry_assets,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def test_synthetic_door_pointer_addends_fit_source_sizes(tmp_path: Path) -> None:
    report = audit_dungeon_room_door_pointer_bounds(_write_registry(tmp_path))
    assert report["summary"] == {
        "pointer_entry_count": 3,
        "empty_pointer_count": 1,
        "unique_pointer_target_label_count": 3,
        "payload_declaration_count": 3,
        "unique_payload_label_count": 3,
        "matched_target_label_count": 3,
        "missing_payload_target_count": 0,
        "missing_payload_reference_count": 0,
        "unreferenced_payload_count": 0,
        "duplicate_payload_label_count": 0,
        "payload_without_size_count": 0,
        "addend_in_bounds_count": 3,
        "addend_out_of_bounds_count": 0,
        "addend_bounds_unknown_count": 0,
        "slot_target_mismatch_count": 0,
        "pointer_entry_offset_mismatch_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "finding_count": 0,
    }
    assert all(row["addend_within_declared_size"] is True for row in report["cross_references"])
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "room_payload_bytes_read": False,
        "addends_checked_against_source_declared_sizes": True,
        "door_data_semantics_decoded": False,
        "offsets_verified": False,
        "payload_bytes_verified": False,
        "playable_room_set_resolved": False,
    }


def test_audit_reports_out_of_bounds_addend_and_slot_mismatch(tmp_path: Path) -> None:
    report = audit_dungeon_room_door_pointer_bounds(
        _write_registry(tmp_path, out_of_bounds=True, slot_target_mismatch=True)
    )
    assert report["summary"]["addend_out_of_bounds_count"] == 1
    assert report["summary"]["slot_target_mismatch_count"] == 1
    assert report["summary"]["error_count"] == 2
    assert {finding["code"] for finding in report["findings"]} == {
        "target_addend_out_of_bounds",
        "target_label_slot_mismatch",
    }


def test_audit_reports_missing_target_and_unknown_size(tmp_path: Path) -> None:
    report = audit_dungeon_room_door_pointer_bounds(
        _write_registry(tmp_path, missing_target=True, missing_size=True)
    )
    assert report["missing_payload_targets"] == ["RoomDataTiles_Missing"]
    assert report["summary"]["missing_payload_reference_count"] == 1
    assert report["summary"]["payload_without_size_count"] == 1
    assert report["summary"]["addend_bounds_unknown_count"] == 2
    assert report["summary"]["error_count"] == 1
    assert report["summary"]["warning_count"] == 2
    assert {finding["code"] for finding in report["findings"]} == {
        "missing_payload_declaration",
        "payload_size_missing",
        "unreferenced_payload_declaration",
    }


def test_audit_pins_committed_door_pointer_bounds_baseline() -> None:
    report = audit_dungeon_room_door_pointer_bounds(REGISTERED_MANIFEST)
    assert report["source_revision"] == PINNED_REVISION
    assert report["door_pointer_table_label"] == "RoomData_DoorDataPointers"
    assert report["door_pointer_table_file_offset"] == 0x0F83C0
    assert report["object_pointer_table_label"] == "RoomData_ObjectDataPointers"
    assert report["object_pointer_table_file_offset"] == 0x0F8000
    assert report["summary"] == {
        "pointer_entry_count": 320,
        "empty_pointer_count": 39,
        "unique_pointer_target_label_count": 263,
        "payload_declaration_count": 266,
        "unique_payload_label_count": 266,
        "matched_target_label_count": 263,
        "missing_payload_target_count": 0,
        "missing_payload_reference_count": 0,
        "unreferenced_payload_count": 3,
        "duplicate_payload_label_count": 0,
        "payload_without_size_count": 0,
        "addend_in_bounds_count": 320,
        "addend_out_of_bounds_count": 0,
        "addend_bounds_unknown_count": 0,
        "slot_target_mismatch_count": 0,
        "pointer_entry_offset_mismatch_count": 0,
        "error_count": 0,
        "warning_count": 3,
        "finding_count": 3,
    }
    assert report["unreferenced_payload_labels"] == [
        "RoomDataTiles_Orphan",
        "RoomDataTiles_Zarby89",
        "RoomDataTiles_Zarby90",
    ]
    assert report == audit_dungeon_room_door_pointer_bounds(REGISTERED_MANIFEST)


def test_cli_writes_json_and_refuses_overwrite(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "door-pointer-audit.json"
    runner = CliRunner()
    args = [
        "audit-dungeon-room-door-pointers",
        "--registry", str(registry),
        "--output", str(output),
    ]
    written = runner.invoke(cli, args)
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["pointer_entry_count"] == 3
    assert saved["summary"]["addend_in_bounds_count"] == 3
    assert "in_bounds=3" in written.output

    refused = runner.invoke(cli, args)
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved

    failed = runner.invoke(cli, [
        "audit-dungeon-room-door-pointers",
        "--registry", str(registry),
        "--fail-on-findings",
    ])
    assert failed.exit_code == 0


def test_cli_fail_on_findings_returns_nonzero_for_a_bad_addend(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path, out_of_bounds=True)
    result = CliRunner().invoke(cli, [
        "audit-dungeon-room-door-pointers",
        "--registry", str(registry),
        "--fail-on-findings",
    ])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["summary"]["addend_out_of_bounds_count"] == 1
