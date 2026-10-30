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
    import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    return database, json_path



def test_import_defaults_to_read_only_preview(tmp_path: Path) -> None:
    database, json_path = initialize_project("dungeon_chest_import_preview", tmp_path)
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()

    preview = import_dungeon_chest_data(database, REGISTRY_PATH)

    assert preview["action"] == "import_dungeon_chest_data"
    assert preview["dry_run"] is True
    assert preview["before"] is None
    assert preview["proposed"]["source_revision"] == "347c23f9fc019c72d32da537c9cb235f468d021d"
    assert preview["proposed"]["summary"]["entry_count"] == 168
    assert preview["proposed"]["summary"]["distinct_room_value_count"] == 106
    assert preview["rom_modified"] is False
    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before
    assert get_dungeon_chest_model(database) is None

    imported = import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    assert imported["summary"]["entry_count"] == 168
    assert validate_project(database) == []


def test_cli_import_dungeon_chest_data_previews_then_applies(tmp_path: Path) -> None:
    database, json_path = initialize_project("dungeon_chest_import_cli", tmp_path)
    runner = CliRunner()
    args = [
        "import-dungeon-chest-data",
        str(database),
        "--registry",
        str(REGISTRY_PATH),
    ]
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()

    preview = runner.invoke(cli, args)
    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.output)
    assert preview_payload["dry_run"] is True
    assert preview_payload["proposed"]["summary"]["entry_count"] == 168
    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before
    assert get_dungeon_chest_model(database) is None

    applied = runner.invoke(cli, [*args, "--apply"])
    assert applied.exit_code == 0, applied.output
    imported = get_dungeon_chest_model(database)
    assert imported is not None
    assert imported["summary"]["entry_count"] == 168


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


def test_update_defaults_to_read_only_preview(tmp_path: Path) -> None:
    database, json_path = _populated_project(tmp_path)
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()

    preview = update_dungeon_chest_record(
        database, 0, item_value=0xAA, room_value=0x1234, is_big_chest=True
    )

    assert preview["action"] == "update_dungeon_chest_record"
    assert preview["dry_run"] is True
    assert preview["table_index"] == 0
    assert preview["before"]["literal_value"] == 0x240032
    assert preview["proposed"]["item_value"] == 0xAA
    assert preview["proposed"]["room_value"] == 0x1234
    assert preview["proposed"]["is_big_chest"] is True
    assert preview["proposed"]["literal_value"] == 0xAA9234
    assert preview["proposed"]["room_pointer_table_byte_displacement"] == 0x1234 * 3
    assert preview["changed_fields"] == ["item_value", "room_value", "is_big_chest"]
    assert preview["rom_modified"] is False
    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before
    unchanged = get_dungeon_chest_model(database)
    assert unchanged is not None
    assert unchanged["entries"][0]["literal_value"] == 0x240032


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
        dry_run=False,
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
    update_dungeon_chest_record(database, 5, item_value=0xEE, dry_run=False)

    with pytest.raises(ValueError, match="already exists"):
        import_dungeon_chest_data(database, REGISTRY_PATH)

    database_before = database.read_bytes()
    json_before = _json_path.read_bytes()
    preview = import_dungeon_chest_data(
        database, REGISTRY_PATH, replace_existing=True
    )
    assert preview["dry_run"] is True
    assert preview["before"]["summary"]["modified_record_count"] == 1
    assert preview["proposed"]["summary"]["entry_count"] == 168
    assert database.read_bytes() == database_before
    assert _json_path.read_bytes() == json_before

    restored = import_dungeon_chest_data(
        database, REGISTRY_PATH, replace_existing=True, dry_run=False
    )
    assert restored["summary"]["modified_record_count"] == 0
    assert restored["entries"][5]["item_value"] == restored["entries"][5]["source_item_value"]
    assert validate_project(database) == []


def test_cli_lists_and_updates_chest_records(tmp_path: Path) -> None:
    database, json_path = _populated_project(tmp_path)
    runner = CliRunner()

    listed = runner.invoke(
        cli, ["list-dungeon-chest-records", str(database), "--table-index", "5"]
    )
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["table_index"] == 5
    assert payload["entries"][0]["is_big_chest"] is True

    database_before = database.read_bytes()
    json_before = json_path.read_bytes()
    update_args = [
        "update-dungeon-chest-record", str(database), "0",
        "--item-value", "$AA", "--room-value", "$1234", "--big-chest",
    ]
    preview = runner.invoke(cli, update_args)
    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.output)
    assert preview_payload["dry_run"] is True
    assert preview_payload["before"]["literal_value"] == 0x240032
    assert preview_payload["proposed"]["literal_value"] == 0xAA9234
    assert preview_payload["changed_fields"] == ["item_value", "room_value", "is_big_chest"]
    assert preview_payload["rom_modified"] is False
    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before

    updated = runner.invoke(cli, [*update_args, "--apply"])
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
