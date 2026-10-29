"""Tests for source-only dungeon chest room-to-pointer cross-references."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.dungeon_chest_room_reference_audit import (
    DungeonChestRoomReferenceAuditError,
    audit_dungeon_chest_room_references,
)
from zelda_suite.extract.dungeon_chest_data import parse_dungeon_chest_data

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _write_registry(
    tmp_path: Path,
    *,
    out_of_range: bool = False,
    slot_target_mismatch: bool = False,
    revision_mismatch: bool = False,
) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    values = [0x240032, 0x0B80A9, 0x258032, 0x440041]
    values.extend([0x100002] * 164)
    if out_of_range:
        values[-1] = 0x440140  # room value $0140 is outside the 320-slot table

    source = (
        "; $00E96E-$00EB65\n"
        "Dungeon_ChestData:\n"
        "{\n"
        + "    dl " + ", ".join("$" + format(value, "06X") for value in values) + "\n"
        + "}\n"
    )
    chest = parse_dungeon_chest_data(
        source,
        source_revision=PINNED_REVISION,
        expected_entry_count=168,
    ).to_dict()

    object_entries: list[dict[str, Any]] = []
    door_entries: list[dict[str, Any]] = []
    door_revision = "alternate-revision" if revision_mismatch else PINNED_REVISION
    for index in range(320):
        label = "RoomDataTiles_Empty" if index == 169 else f"RoomDataTiles_{index:04X}"
        object_entries.append({
            "table_index": index,
            "pointer_entry_file_offset": 0x0F8000 + index * 3,
            "source_line": index + 14,
            "pointer_expression": label,
            "target_label": label,
            "target_addend": None,
            "is_empty_target": label == "RoomDataTiles_Empty",
            "source_revision": PINNED_REVISION,
        })
        door_label = (
            f"RoomDataTiles_{index + 1:04X}"
            if slot_target_mismatch and index == 50
            else label
        )
        door_entries.append({
            "table_index": index,
            "pointer_entry_file_offset": 0x0F83C0 + index * 3,
            "source_line": index + 341,
            "pointer_expression": f"{door_label}+$" + "0001",
            "target_label": door_label,
            "target_addend": 1,
            "is_empty_target": door_label == "RoomDataTiles_Empty",
            "source_revision": door_revision,
        })

    object_export = {
        "format": "zelda-suite-pointer-table",
        "format_version": 1,
        "source_file": "Bank1F.asm",
        "source_revision": PINNED_REVISION,
        "table_label": "RoomData_ObjectDataPointers",
        "table_file_offset": 0x0F8000,
        "entry_width": 3,
        "entry_count": len(object_entries),
        "entries": object_entries,
    }
    door_export = {
        "format": "zelda-suite-pointer-table",
        "format_version": 1,
        "source_file": "Bank1F.asm",
        "source_revision": door_revision,
        "table_label": "RoomData_DoorDataPointers",
        "table_file_offset": 0x0F83C0,
        "entry_width": 3,
        "entry_count": len(door_entries),
        "entries": door_entries,
    }

    exports = [
        ("dungeon-chest-data", "dungeon-chest-data.json", chest,
         "zelda-suite-dungeon-chest-data", 168),
        ("dungeon-room-object-pointers", "dungeon-room-object-pointers.json", object_export,
         "zelda-suite-pointer-table", 320),
        ("dungeon-room-door-pointers", "dungeon-room-door-pointers.json", door_export,
         "zelda-suite-pointer-table", 320),
    ]
    registry_assets = []
    for name, filename, payload, format_name, count in exports:
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        registry_assets.append({
            "name": name,
            "file": filename,
            "format": format_name,
            "source_revision": payload["source_revision"],
            "record_count": count,
            "subsystem": "dungeons",
            "description": "Synthetic source-only room reference fixture.",
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


def test_synthetic_chest_room_values_join_to_pointer_slots(tmp_path: Path) -> None:
    report = audit_dungeon_chest_room_references(_write_registry(tmp_path))

    assert report["summary"] == {
        "chest_entry_count": 168,
        "unique_room_value_count": 4,
        "room_values_with_multiple_chests": 2,
        "chest_entries_with_pointer_slots": 168,
        "chest_entries_without_pointer_slots": 0,
        "unique_room_values_without_pointer_slots": 0,
        "empty_object_pointer_target_chest_count": 1,
        "unique_room_values_targeting_empty_object_pointer": 1,
        "object_door_pointer_target_mismatch_room_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "finding_count": 0,
        "minimum_room_value": 2,
        "maximum_room_value": 169,
    }
    room_32 = next(group for group in report["room_groups"] if group["room_value"] == 0x32)
    assert room_32["chest_table_indexes"] == [0, 2]
    assert room_32["object_pointer_target_label"] == "RoomDataTiles_0032"
    assert room_32["door_pointer_target_label"] == "RoomDataTiles_0032"
    assert room_32["pointer_target_labels_match"] is True
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "room_payload_bytes_read": False,
        "room_value_compared_to_source_pointer_slots": True,
        "source_consumer_relationship_traced": True,
        "pointer_offsets_verified": False,
        "payload_bytes_verified": False,
        "item_value_names_resolved": False,
        "playable_room_set_resolved": False,
    }


def test_audit_reports_out_of_range_room_value(tmp_path: Path) -> None:
    report = audit_dungeon_chest_room_references(
        _write_registry(tmp_path, out_of_range=True)
    )
    assert report["summary"]["chest_entries_without_pointer_slots"] == 1
    assert report["summary"]["unique_room_values_without_pointer_slots"] == 1
    assert report["summary"]["error_count"] == 1
    assert report["findings"][0]["code"] == "room_value_out_of_pointer_range"
    assert report["findings"][0]["room_value"] == 0x140


def test_audit_reports_object_and_door_pointer_target_mismatch(tmp_path: Path) -> None:
    report = audit_dungeon_chest_room_references(
        _write_registry(tmp_path, slot_target_mismatch=True)
    )
    assert report["summary"]["object_door_pointer_target_mismatch_room_count"] == 1
    assert report["summary"]["error_count"] == 1
    assert report["object_door_pointer_mismatch_room_values"] == [0x32]
    assert report["findings"][0]["code"] == "object_door_pointer_target_mismatch"
    assert report["findings"][0]["room_value"] == 0x32


def test_audit_rejects_non_pinned_source_revision(tmp_path: Path) -> None:
    with pytest.raises(DungeonChestRoomReferenceAuditError, match="pinned to source revision"):
        audit_dungeon_chest_room_references(
            _write_registry(tmp_path, revision_mismatch=True)
        )


def test_audit_pins_committed_chest_to_room_pointer_baseline() -> None:
    report = audit_dungeon_chest_room_references(REGISTERED_MANIFEST)

    assert report["source_revision"] == PINNED_REVISION
    assert report["source_semantics"]["chest_room_compare_line"] == 15231
    assert report["source_semantics"]["door_pointer_read_lines"] == [7910, 7911]
    assert report["source_semantics"]["object_pointer_read_lines"] == [828, 829]
    assert report["summary"] == {
        "chest_entry_count": 168,
        "unique_room_value_count": 106,
        "room_values_with_multiple_chests": 32,
        "chest_entries_with_pointer_slots": 168,
        "chest_entries_without_pointer_slots": 0,
        "unique_room_values_without_pointer_slots": 0,
        "empty_object_pointer_target_chest_count": 3,
        "unique_room_values_targeting_empty_object_pointer": 3,
        "object_door_pointer_target_mismatch_room_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "finding_count": 0,
        "minimum_room_value": 4,
        "maximum_room_value": 317,
    }
    assert report == audit_dungeon_chest_room_references(REGISTERED_MANIFEST)


def test_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "chest-room-reference-audit.json"
    runner = CliRunner()
    args = [
        "audit-dungeon-chest-room-references",
        "--registry", str(registry),
        "--output", str(output),
    ]

    written = runner.invoke(cli, args)
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["unique_room_value_count"] == 4
    assert "out_of_range=0" in written.output

    refused = runner.invoke(cli, args)
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved


def test_cli_fail_on_findings_returns_nonzero_for_bad_room_reference(
    tmp_path: Path,
) -> None:
    registry = _write_registry(tmp_path, out_of_range=True)
    result = CliRunner().invoke(cli, [
        "audit-dungeon-chest-room-references",
        "--registry", str(registry),
        "--fail-on-findings",
    ])
    assert result.exit_code == 1
    assert json.loads(result.output)["summary"]["chest_entries_without_pointer_slots"] == 1
