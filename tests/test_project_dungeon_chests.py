"""Tests for project-local packed dungeon chest editing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    get_dungeon_chest_model,
    import_dungeon_chest_data,
    initialize_project,
    update_dungeon_chest_record,
    validate_project,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"


def _populated_project(tmp_path: Path) -> tuple[Path, Path]:
    database, json_path = initialize_project("dungeon_chests", tmp_path)
    import_dungeon_chest_data(database, REGISTRY_PATH)
    return database, json_path


def test_import_preserves_source_fields_and_publishes_canonical_model(
    tmp_path: Path,
) -> None:
    database, json_path = _populated_project(tmp_path)
    model = get_dungeon_chest_model(database)

    assert model is not None
    assert model["format"] == "zelda-suite-dungeon-chest-model"
    assert model["format_version"] == 1
    assert model["source_revision"] == "347c23f9fc019c72d32da537c9cb235f468d021d"
    assert model["summary"] == {
        "entry_count": 168,
        "distinct_room_value_count": 106,
        "distinct_item_value_count": 33,
        "big_chest_count": 11,
        "modified_record_count": 0,
    }
    first = model["entries"][0]
    assert first["table_index"] == 0
    assert first["source_expression"] == "$240032"
    assert first["source_literal_value"] == 0x240032
    assert first["literal_value"] == 0x240032
    assert first["source_item_value"] == first["item_value"] == 0x24
    assert first["source_room_value"] == first["room_value"] == 0x32
    assert first["source_is_big_chest"] is first["is_big_chest"] is False
    assert first["room_pointer_index"] == 0x32
    assert first["room_pointer_table_byte_displacement"] == 0x32 * 3
    assert model["entries"][5]["is_big_chest"] is True
    assert model["evidence"]["source_range_offsets_verified"] is False
    assert model["evidence"]["rom_modified"] is False

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["dungeon_chests"] == model
    assert exported["overworld_hidden_items"] is None
    assert validate_project(database) == []


def test_edit_recomposes_packed_literal_and_retains_source_baseline(
    tmp_path: Path,
) -> None:
    database, json_path = _populated_project(tmp_path)

    updated = update_dungeon_chest_record(
        database,
        0,
        item_value=0xAA,
        room_value=0x1234,
        is_big_chest=True,
    )

    assert updated["source_literal_value"] == 0x240032
    assert updated["source_expression"] == "$240032"
    assert updated["source_item_value"] == 0x24
    assert updated["source_room_value"] == 0x32
    assert updated["source_is_big_chest"] is False
    assert updated["item_value"] == 0xAA
    assert updated["room_value"] == 0x1234
    assert updated["is_big_chest"] is True
    assert updated["literal_value"] == 0xAA9234
    assert updated["literal_hex"] == "$AA9234"
    assert updated["expression"] == "$AA9234"
    assert updated["room_pointer_table_byte_displacement"] == 0x1234 * 3
    assert updated["is_modified"] is True

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["dungeon_chests"]["entries"][0]["literal_value"] == 0xAA9234
    assert exported["dungeon_chests"]["summary"]["modified_record_count"] == 1
    assert exported["dungeon_chests"]["summary"]["big_chest_count"] == 12
    assert validate_project(database) == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"item_value": -1}, "item_value"),
        ({"item_value": 256}, "item_value"),
        ({"item_value": True}, "item_value"),
        ({"room_value": -1}, "room_value"),
        ({"room_value": 0x8000}, "room_value"),
        ({"room_value": True}, "room_value"),
        ({"is_big_chest": 1}, "is_big_chest"),
        ({}, "supply item_value"),
    ],
)
def test_update_rejects_out_of_range_or_empty_edits(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    database, _json_path = initialize_project("invalid_chest_edit", tmp_path)
    with pytest.raises((ValueError, KeyError), match=message):
        update_dungeon_chest_record(database, 0, **kwargs)  # type: ignore[arg-type]


def test_reimport_requires_explicit_replace_and_resets_local_edits(
    tmp_path: Path,
) -> None:
    database, _json_path = _populated_project(tmp_path)
    update_dungeon_chest_record(database, 5, item_value=0xEE)

    with pytest.raises(ValueError, match="already exists"):
        import_dungeon_chest_data(database, REGISTRY_PATH)

    restored = import_dungeon_chest_data(
        database, REGISTRY_PATH, replace_existing=True
    )
    assert restored["summary"]["modified_record_count"] == 0
    assert restored["entries"][5]["item_value"] == restored["entries"][5]["source_item_value"]
    assert validate_project(database) == []


def test_cli_lists_and_updates_chest_records(tmp_path: Path) -> None:
    database, _json_path = _populated_project(tmp_path)
    runner = CliRunner()

    listed = runner.invoke(
        cli, ["list-dungeon-chest-records", str(database), "--table-index", "5"]
    )
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["table_index"] == 5
    assert payload["entries"][0]["is_big_chest"] is True

    updated = runner.invoke(
        cli,
        [
            "update-dungeon-chest-record",
            str(database),
            "0",
            "--item-value",
            "$AA",
            "--room-value",
            "$1234",
            "--big-chest",
        ],
    )
    assert updated.exit_code == 0, updated.output
    record = json.loads(updated.output)
    assert record["literal_hex"] == "$AA9234"
    assert record["item_value"] == 0xAA
    assert record["room_value"] == 0x1234
    assert record["is_big_chest"] is True

    bad_room = runner.invoke(
        cli,
        [
            "update-dungeon-chest-record",
            str(database),
            "0",
            "--room-value",
            "$8000",
        ],
    )
    assert bad_room.exit_code != 0
    assert "room_value" in bad_room.output or "room-value" in bad_room.output
