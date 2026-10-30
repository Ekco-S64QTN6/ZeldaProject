"""Tests for the project-aware dungeon chest room-reference audit."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project import (
    audit_project_dungeon_chest_room_references,
    import_dungeon_chest_data,
    initialize_project,
    update_dungeon_chest_record,
    validate_project,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"


def _populated_project(tmp_path: Path) -> Path:
    database, _json_path = initialize_project("project_chest_audit", tmp_path)
    import_dungeon_chest_data(database, REGISTRY_PATH)
    return database


def _registry_with_door_target_mismatch(tmp_path: Path, table_index: int) -> Path:
    """Copy the registered pointer tables and corrupt one semantic target label."""
    extracted = tmp_path / "mismatched_registry"
    extracted.mkdir()
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    names = {
        "dungeon-room-object-pointers",
        "dungeon-room-door-pointers",
    }
    assets = [asset for asset in registry["assets"] if asset["name"] in names]
    assert {asset["name"] for asset in assets} == names

    for asset in assets:
        source_file = ROOT / "data" / "extracted" / asset["file"]
        shutil.copyfile(source_file, extracted / asset["file"])

    door_asset = next(
        asset for asset in assets if asset["name"] == "dungeon-room-door-pointers"
    )
    door_path = extracted / door_asset["file"]
    payload = json.loads(door_path.read_text(encoding="utf-8"))
    entry = payload["entries"][table_index]
    target_label = f"RoomDataTilesAuditMismatch{table_index}"
    entry["target_label"] = target_label
    addend = entry["target_addend"]
    entry["pointer_expression"] = (
        target_label
        if addend is None
        else f"{target_label}+" + "$" + f"{int(addend):04X}"
    )
    door_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    registry["assets"] = assets
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_project_audit_joins_current_values_and_preserves_source_baselines(
    tmp_path: Path,
) -> None:
    database = _populated_project(tmp_path)

    before = audit_project_dungeon_chest_room_references(database, REGISTRY_PATH)
    assert before["format"] == "zelda-suite-project-dungeon-chest-room-reference-audit"
    assert before["format_version"] == 1
    assert before["summary"]["chest_entry_count"] == 168
    assert before["summary"]["modified_record_count"] == 0
    assert before["summary"]["chest_entries_with_pointer_slots"] == 168
    assert before["summary"]["chest_entries_without_pointer_slots"] == 0
    assert before["summary"]["error_count"] == 0
    assert before["evidence"]["project_edits_included"] is True
    assert before["evidence"]["rom_bytes_read"] is False

    update_dungeon_chest_record(database, 0, room_value=0x1234, dry_run=False)
    after = audit_project_dungeon_chest_room_references(database, REGISTRY_PATH)
    first = after["entries"][0]
    assert first["source_room_value"] == 0x32
    assert first["room_value"] == 0x1234
    assert first["is_modified"] is True
    assert first["room_pointer_table_index"] is None
    assert first["room_value_in_pointer_tables"] is False
    assert first["object_pointer_entry_file_offset"] is None
    assert first["door_pointer_entry_file_offset"] is None
    assert after["summary"]["modified_record_count"] == 1
    assert after["summary"]["chest_entries_without_pointer_slots"] == 1
    assert after["summary"]["unique_room_values_without_pointer_slots"] == 1
    assert after["summary"]["error_count"] == 1
    assert after["findings"][0]["code"] == "room_value_out_of_pointer_range"
    assert validate_project(database) == []


def test_project_audit_joins_edited_in_range_room_value(tmp_path: Path) -> None:
    database = _populated_project(tmp_path)
    update_dungeon_chest_record(database, 0, room_value=0x33, dry_run=False)

    report = audit_project_dungeon_chest_room_references(database, REGISTRY_PATH)
    first = report["entries"][0]

    assert first["source_room_value"] == 0x32
    assert first["room_value"] == 0x33
    assert first["is_modified"] is True
    assert first["room_pointer_table_index"] == 0x33
    assert first["room_value_in_pointer_tables"] is True
    assert first["object_pointer_target_label"] == "RoomDataTiles_0033"
    assert first["door_pointer_target_label"] == "RoomDataTiles_0033"
    assert first["pointer_target_labels_match"] is True
    assert report["summary"]["modified_record_count"] == 1
    assert report["summary"]["chest_entries_with_pointer_slots"] == 168
    assert report["summary"]["chest_entries_without_pointer_slots"] == 0
    assert report["summary"]["error_count"] == 0
    assert report["findings"] == []


def test_project_audit_reports_object_door_target_mismatch(
    tmp_path: Path,
) -> None:
    database = _populated_project(tmp_path)
    # Move another chest to the same edited room to exercise room-group behavior.
    update_dungeon_chest_record(database, 2, room_value=0x32, dry_run=False)
    registry = _registry_with_door_target_mismatch(tmp_path, table_index=0x32)

    report = audit_project_dungeon_chest_room_references(database, registry)
    affected = [
        entry for entry in report["entries"] if entry["room_value"] == 0x32
    ]

    assert {entry["table_index"] for entry in affected} == {0, 2}
    assert all(entry["room_value_in_pointer_tables"] is True for entry in affected)
    assert all(entry["pointer_target_labels_match"] is False for entry in affected)
    assert all(
        entry["door_pointer_target_label"] == "RoomDataTilesAuditMismatch50"
        for entry in affected
    )
    assert report["object_door_pointer_mismatch_room_values"] == [0x32]
    group = next(
        group for group in report["room_groups"] if group["room_value"] == 0x32
    )
    assert group["chest_table_indexes"] == [0, 2]
    assert group["source_room_values"] == [0x32, 0x71]
    assert report["summary"]["modified_record_count"] == 1
    assert report["summary"]["object_door_pointer_target_mismatch_room_count"] == 1
    assert report["summary"]["error_count"] == len(affected)
    assert {finding["code"] for finding in report["findings"]} == {
        "object_door_pointer_target_mismatch"
    }


def test_project_audit_requires_imported_chest_model(tmp_path: Path) -> None:
    database, _json_path = initialize_project("empty_chest_audit", tmp_path)
    with pytest.raises(ValueError, match="no dungeon chest model"):
        audit_project_dungeon_chest_room_references(database, REGISTRY_PATH)


def test_cli_emits_project_audit_and_fails_on_findings(tmp_path: Path) -> None:
    database = _populated_project(tmp_path)
    runner = CliRunner()

    clean = runner.invoke(
        cli,
        [
            "audit-project-dungeon-chest-room-references",
            str(database),
            "--registry",
            str(REGISTRY_PATH),
        ],
    )
    assert clean.exit_code == 0, clean.output
    payload = json.loads(clean.output)
    assert payload["summary"]["error_count"] == 0
    assert payload["summary"]["chest_entry_count"] == 168

    report_path = tmp_path / "project-chest-audit.json"
    written = runner.invoke(
        cli,
        [
            "audit-project-dungeon-chest-room-references",
            str(database),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            str(report_path),
        ],
    )
    assert written.exit_code == 0, written.output
    written_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert written_payload["summary"]["error_count"] == 0

    overwrite = runner.invoke(
        cli,
        [
            "audit-project-dungeon-chest-room-references",
            str(database),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            str(report_path),
        ],
    )
    assert overwrite.exit_code != 0
    assert json.loads(report_path.read_text(encoding="utf-8")) == written_payload

    update_dungeon_chest_record(database, 0, room_value=0x1234, dry_run=False)
    failing = runner.invoke(
        cli,
        [
            "audit-project-dungeon-chest-room-references",
            str(database),
            "--registry",
            str(REGISTRY_PATH),
            "--fail-on-findings",
        ],
    )
    assert failing.exit_code == 1, failing.output
    payload = json.loads(failing.output)
    assert payload["entries"][0]["room_value"] == 0x1234
    assert payload["findings"][0]["severity"] == "error"
