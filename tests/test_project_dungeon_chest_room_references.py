"""Tests for the project-aware dungeon chest room-reference audit."""
from __future__ import annotations

import json
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

    update_dungeon_chest_record(database, 0, room_value=0x1234)
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

    update_dungeon_chest_record(database, 0, room_value=0x1234)
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
