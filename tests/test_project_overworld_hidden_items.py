"""Tests for the first SQLite-backed semantic overworld domain."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    create_custom_overworld_hidden_item,
    delete_custom_overworld_hidden_item,
    get_overworld_hidden_item_model,
    import_overworld_hidden_item_model,
    initialize_project,
    update_custom_overworld_hidden_item,
    update_overworld_hidden_item,
    validate_project,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
REPLACEMENTS = [
    (0, 2813, 0x0DC89C, 0, "dw $0DCC", 0x0DCC, "Hole"),
    (1, 2814, 0x0DC89E, 2, "dw $0212", 0x0212, "Portal"),
    (2, 2815, 0x0DC8A0, 4, "dw $FFFF", 0xFFFF, "Garbage"),
    (3, 2816, 0x0DC8A2, 6, "dw $0DB4", 0x0DB4, "Bomb hole"),
]


def _seed_semantic_model(database: Path) -> None:
    """Seed a structurally complete fixture so CRUD tests don't need the submodule."""
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute(
                """INSERT INTO overworld_hidden_item_model (
                       singleton, source_file, source_revision, source_sha256,
                       imported_at, consumer_label, replacement_table_label
                   ) VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    "Bank1B.asm",
                    PINNED_REVISION,
                    "0" * 64,
                    "2026-10-29T00:00:00Z",
                    "Overworld_RevealSecret",
                    "Overworld_SecretTileType",
                ),
            )
            connection.executemany(
                """INSERT INTO overworld_hidden_item_replacement_word (
                       table_index, source_line, file_offset, selector_byte_offset,
                       expression, value, comment
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                REPLACEMENTS,
            )

            for record_index in range(351):
                coordinate = record_index + 1
                label = "OverworldData_HiddenItems_Screen_" + format(record_index % 80, "02X")
                source_expression = (
                    "dw $" + format(coordinate, "04X") + " : db $05"
                )
                connection.execute(
                    """INSERT INTO overworld_hidden_item_record (
                           record_index, source_label, source_line, source_file_offset,
                           source_expression, source_coordinate_word, coordinate_word,
                           source_value_byte, value_byte, consumer_class, consumer_operation,
                           selector_byte_offset, replacement_table_index,
                           replacement_word_value, replacement_word_comment, special_case
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)""",
                    (
                        record_index,
                        label,
                        500 + record_index,
                        0x0DC3F9 + (record_index * 3),
                        source_expression,
                        coordinate,
                        coordinate,
                        0x05,
                        0x05,
                        "ordinary_secret_mask",
                        "TSB $0B9C combines this value with secret-state flags",
                    ),
                )

            for area_index in range(128):
                record_index = 0 if area_index < 2 else area_index - 1
                target_label = (
                    "OverworldData_HiddenItems_Screen_00"
                    if area_index < 2
                    else "OverworldData_HiddenItems_Screen_"
                    + format(record_index % 80, "02X")
                )
                target_offset = (
                    0x0DC3F9
                    if area_index < 2
                    else 0x0DC3F9 + record_index * 3
                )
                sentinel_offset = 0x0DC450 + area_index
                connection.execute(
                    """INSERT INTO overworld_hidden_item_area (
                           area_index, pointer_entry_file_offset, target_label,
                           target_file_offset, sentinel_file_offset, record_count
                       ) VALUES (?, ?, ?, ?, ?, 1)""",
                    (
                        area_index,
                        0x0DC2F9 + area_index * 2,
                        target_label,
                        target_offset,
                        sentinel_offset,
                    ),
                )
                connection.execute(
                    """INSERT INTO overworld_hidden_item_area_record (
                           area_index, ordinal, record_index
                       ) VALUES (?, 0, ?)""",
                    (area_index, record_index),
                )


def test_update_changes_project_value_and_recomputes_consumer_semantics(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("overworld_model", tmp_path)
    _seed_semantic_model(database)

    original = get_overworld_hidden_item_model(database)
    assert original is not None
    assert original["summary"]["area_count"] == 128
    assert original["summary"]["record_count"] == 351
    assert original["records"][0]["area_indices"] == [0, 1]
    assert original["summary"]["modified_record_count"] == 0

    updated = update_overworld_hidden_item(
        database, 0, coordinate_word=0x1234, value_byte=0x84
    )

    assert updated["source_coordinate_word"] == 1
    assert updated["source_value_byte"] == 0x05
    assert updated["coordinate_word"] == 0x1234
    assert updated["value_byte"] == 0x84
    assert updated["consumer_class"] == "extended_secret_selector"
    assert updated["selector_byte_offset"] == 4
    assert updated["replacement_table_index"] == 2
    assert updated["replacement_word_value"] == 0xFFFF
    assert updated["replacement_word_comment"] == "Garbage"
    assert updated["canonical_item_id_resolved"] is False
    assert updated["is_modified"] is True

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["overworld_hidden_items"]["summary"]["modified_record_count"] == 1
    exported_record = exported["overworld_hidden_items"]["records"][0]
    assert exported_record["coordinate_word"] == 0x1234
    assert exported_record["source_coordinate_word"] == 1
    assert validate_project(database) == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"coordinate_word": 0xFFFF}, "reserved as the list sentinel"),
        ({"coordinate_word": -1}, "coordinate_word"),
        ({"value_byte": 256}, "value_byte"),
        ({"value_byte": True}, "value_byte"),
        ({}, "supply coordinate_word"),
    ],
)
def test_update_rejects_invalid_or_empty_edit(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    database, _ = initialize_project("invalid_overworld_edit", tmp_path)
    with pytest.raises(ValueError, match=message):
        update_overworld_hidden_item(database, 0, **kwargs)  # type: ignore[arg-type]


def test_cli_lists_area_and_updates_model(tmp_path: Path) -> None:
    database, _ = initialize_project("overworld_cli", tmp_path)
    _seed_semantic_model(database)
    runner = CliRunner()

    listed = runner.invoke(
        cli, ["list-overworld-hidden-items", str(database), "--area-index", "1"]
    )
    assert listed.exit_code == 0, listed.output
    area_payload = json.loads(listed.output)
    assert area_payload["area"]["area_index"] == 1
    assert area_payload["records"][0]["record_index"] == 0

    updated = runner.invoke(
        cli,
        ["update-overworld-hidden-item", str(database), "0", "--value-byte", "$82"],
    )
    assert updated.exit_code == 0, updated.output
    record = json.loads(updated.output)
    assert record["value_byte"] == 0x82
    assert record["consumer_class"] == "extended_secret_selector"





def test_custom_hidden_item_create_defaults_to_dry_run_and_preserves_source_rows(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("custom_item_preview", tmp_path)
    _seed_semantic_model(database)
    source_export = json_path.read_bytes()
    with sqlite3.connect(database) as connection:
        source_records_before = connection.execute(
            """SELECT record_index, source_coordinate_word, source_value_byte,
                      coordinate_word, value_byte
               FROM overworld_hidden_item_record ORDER BY record_index"""
        ).fetchall()
        source_links_before = connection.execute(
            """SELECT area_index, ordinal, record_index
               FROM overworld_hidden_item_area_record ORDER BY area_index, ordinal"""
        ).fetchall()

    preview = create_custom_overworld_hidden_item(
        database, area_indices=[3, 2], coordinate_word=0x3456, value_byte=0x84
    )

    assert preview["dry_run"] is True
    assert preview["custom_record_id"] is None
    assert preview["area_indices"] == [2, 3]
    assert preview["consumer_class"] == "extended_secret_selector"
    assert preview["replacement_table_index"] == 2
    assert preview["source_record_index"] is None
    assert preview["rom_modified"] is False
    assert json_path.read_bytes() == source_export
    preview_model = get_overworld_hidden_item_model(database)
    assert preview_model is not None
    assert preview_model["custom_records"] == []

    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[3, 2],
        coordinate_word=0x3456,
        value_byte=0x84,
        dry_run=False,
    )
    record = created["record"]
    custom_id = record["custom_record_id"]
    assert created["dry_run"] is False
    assert record["record_kind"] == "project_authored"
    assert record["source_record_index"] is None
    assert record["area_indices"] == [2, 3]
    assert record["coordinate_word"] == 0x3456
    assert record["value_byte"] == 0x84
    assert record["consumer_class"] == "extended_secret_selector"

    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["summary"]["record_count"] == 351
    assert model["summary"]["custom_record_count"] == 1
    assert model["summary"]["custom_area_record_reference_count"] == 2
    assert model["records"][0]["area_indices"] == [0, 1]
    assert model["areas"][2]["record_indices"] == [1]
    assert model["areas"][2]["custom_record_ids"] == [custom_id]
    assert model["areas"][3]["custom_record_ids"] == [custom_id]

    with sqlite3.connect(database) as connection:
        source_records_after = connection.execute(
            """SELECT record_index, source_coordinate_word, source_value_byte,
                      coordinate_word, value_byte
               FROM overworld_hidden_item_record ORDER BY record_index"""
        ).fetchall()
        source_links_after = connection.execute(
            """SELECT area_index, ordinal, record_index
               FROM overworld_hidden_item_area_record ORDER BY area_index, ordinal"""
        ).fetchall()
    assert source_records_after == source_records_before
    assert source_links_after == source_links_before
    assert validate_project(database) == []


def test_custom_hidden_item_delete_defaults_to_dry_run_and_cascades_alias_links(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("custom_item_delete", tmp_path)
    _seed_semantic_model(database)
    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[4, 5],
        coordinate_word=0x1234,
        value_byte=0x05,
        dry_run=False,
    )
    custom_id = created["record"]["custom_record_id"]
    before_delete = json_path.read_bytes()

    preview = delete_custom_overworld_hidden_item(database, custom_id)
    assert preview["dry_run"] is True
    assert preview["record"]["area_indices"] == [4, 5]
    assert json_path.read_bytes() == before_delete

    deleted = delete_custom_overworld_hidden_item(
        database, custom_id, dry_run=False
    )
    assert deleted["dry_run"] is False
    assert deleted["deleted"]["custom_record_id"] == custom_id
    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["custom_records"] == []
    assert model["areas"][4]["custom_record_ids"] == []
    assert model["areas"][5]["custom_record_ids"] == []
    assert model["records"][0]["area_indices"] == [0, 1]
    assert model["summary"]["record_count"] == 351
    assert model["summary"]["custom_record_count"] == 0
    assert validate_project(database) == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"area_indices": [], "coordinate_word": 1, "value_byte": 1}, "at least one area"),
        ({"area_indices": [128], "coordinate_word": 1, "value_byte": 1}, "0..127"),
        ({"area_indices": [1, 1], "coordinate_word": 1, "value_byte": 1}, "duplicate area"),
        ({"area_indices": [1], "coordinate_word": 0xFFFF, "value_byte": 1}, "reserved as the list sentinel"),
        ({"area_indices": [1], "coordinate_word": 1, "value_byte": 256}, "value_byte"),
        ({"area_indices": [1], "coordinate_word": True, "value_byte": 1}, "coordinate_word"),
    ],
)
def test_custom_hidden_item_create_rejects_invalid_fields(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    database, _ = initialize_project("invalid_custom_item", tmp_path)
    _seed_semantic_model(database)
    with pytest.raises(ValueError, match=message):
        create_custom_overworld_hidden_item(database, **kwargs)  # type: ignore[arg-type]


def test_custom_hidden_item_cannot_delete_a_source_record(tmp_path: Path) -> None:
    database, _ = initialize_project("source_delete_guard", tmp_path)
    _seed_semantic_model(database)
    with pytest.raises(KeyError, match="custom overworld hidden item not found"):
        delete_custom_overworld_hidden_item(database, 1, dry_run=False)
    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert len(model["records"]) == 351
    assert model["custom_records"] == []


def test_cli_custom_hidden_item_create_and_delete_require_apply(tmp_path: Path) -> None:
    database, json_path = initialize_project("custom_item_cli", tmp_path)
    _seed_semantic_model(database)
    runner = CliRunner()
    original_export = json_path.read_bytes()

    preview = runner.invoke(
        cli,
        [
            "create-custom-overworld-hidden-item", str(database),
            "--area-index", "2", "--area-index", "3",
            "--coordinate-word", "$1234", "--value-byte", "$05",
        ],
    )
    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.output)
    assert preview_payload["dry_run"] is True
    assert json_path.read_bytes() == original_export

    applied = runner.invoke(
        cli,
        [
            "create-custom-overworld-hidden-item", str(database),
            "--area-index", "2", "--area-index", "3",
            "--coordinate-word", "$1234", "--value-byte", "$05", "--apply",
        ],
    )
    assert applied.exit_code == 0, applied.output
    custom_id = json.loads(applied.output)["record"]["custom_record_id"]

    deletion_preview = runner.invoke(
        cli,
        ["delete-custom-overworld-hidden-item", str(database), str(custom_id)],
    )
    assert deletion_preview.exit_code == 0, deletion_preview.output
    assert json.loads(deletion_preview.output)["dry_run"] is True

    deletion = runner.invoke(
        cli,
        ["delete-custom-overworld-hidden-item", str(database), str(custom_id), "--apply"],
    )
    assert deletion.exit_code == 0, deletion.output
    assert json.loads(deletion.output)["deleted"]["custom_record_id"] == custom_id
    assert validate_project(database) == []


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_import_pinned_source_preserves_shared_area_aliases_and_source_hash(
    tmp_path: Path,
) -> None:
    source_bytes = SOURCE_PATH.read_bytes()
    database, _ = initialize_project("overworld_import", tmp_path)

    model = import_overworld_hidden_item_model(database, SOURCE_PATH)

    assert model["source_revision"] == PINNED_REVISION
    assert model["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert model["summary"]["area_count"] == 128
    assert model["summary"]["record_count"] == 351
    assert model["records"][0]["area_indices"] == [0, 1, 8, 9]
    assert model["areas"][0]["record_indices"] == model["areas"][1]["record_indices"]
    assert validate_project(database) == []

    with pytest.raises(ValueError, match="already exists"):
        import_overworld_hidden_item_model(database, SOURCE_PATH)

    created_custom = create_custom_overworld_hidden_item(
        database, area_indices=[0, 1], coordinate_word=0x4567, value_byte=0x05,
        dry_run=False,
    )
    custom_id = created_custom["record"]["custom_record_id"]

    update_overworld_hidden_item(database, 0, value_byte=0x84)
    current = get_overworld_hidden_item_model(database)
    assert current is not None
    assert current["summary"]["modified_record_count"] == 1

    replaced = import_overworld_hidden_item_model(
        database, SOURCE_PATH, replace_existing=True
    )
    assert replaced["summary"]["modified_record_count"] == 0
    assert replaced["records"][0]["value_byte"] == replaced["records"][0]["source_value_byte"]
    assert replaced["custom_records"][0]["custom_record_id"] == custom_id
    assert replaced["custom_records"][0]["area_indices"] == [0, 1]
    assert validate_project(database) == []


def test_custom_hidden_item_update_defaults_to_preview_and_preserves_source_rows(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("custom_item_update", tmp_path)
    _seed_semantic_model(database)
    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[4, 5],
        coordinate_word=0x1234,
        value_byte=0x05,
        dry_run=False,
    )
    custom_id = created["record"]["custom_record_id"]
    original_database = database.read_bytes()
    original_export = json_path.read_bytes()
    with sqlite3.connect(database) as connection:
        source_records_before = connection.execute(
            """SELECT record_index, source_coordinate_word, source_value_byte,
                      coordinate_word, value_byte
               FROM overworld_hidden_item_record ORDER BY record_index"""
        ).fetchall()
        source_links_before = connection.execute(
            """SELECT area_index, ordinal, record_index
               FROM overworld_hidden_item_area_record ORDER BY area_index, ordinal"""
        ).fetchall()

    preview = update_custom_overworld_hidden_item(
        database,
        custom_id,
        area_indices=[7, 6],
        coordinate_word=0x4567,
        value_byte=0x84,
    )
    assert preview["dry_run"] is True
    assert preview["before"]["area_indices"] == [4, 5]
    assert preview["before"]["coordinate_word"] == 0x1234
    assert preview["proposed"]["area_indices"] == [6, 7]
    assert preview["proposed"]["coordinate_word"] == 0x4567
    assert preview["proposed"]["value_byte"] == 0x84
    assert preview["proposed"]["consumer_class"] == "extended_secret_selector"
    assert preview["proposed"]["replacement_table_index"] == 2
    assert preview["changed_fields"] == [
        "coordinate_word", "value_byte", "area_indices"
    ]
    assert preview["rom_modified"] is False
    assert database.read_bytes() == original_database
    assert json_path.read_bytes() == original_export

    unchanged_model = get_overworld_hidden_item_model(database)
    assert unchanged_model is not None
    unchanged_record = unchanged_model["custom_records"][0]
    assert unchanged_record["area_indices"] == [4, 5]
    assert unchanged_record["coordinate_word"] == 0x1234
    assert unchanged_record["value_byte"] == 0x05

    updated = update_custom_overworld_hidden_item(
        database,
        custom_id,
        area_indices=[7, 6],
        coordinate_word=0x4567,
        value_byte=0x84,
        dry_run=False,
    )
    record = updated["record"]
    assert updated["dry_run"] is False
    assert updated["changed_fields"] == [
        "coordinate_word", "value_byte", "area_indices"
    ]
    assert record["custom_record_id"] == custom_id
    assert record["record_kind"] == "project_authored"
    assert record["source_record_index"] is None
    assert record["area_indices"] == [6, 7]
    assert record["coordinate_word"] == 0x4567
    assert record["value_byte"] == 0x84
    assert record["consumer_class"] == "extended_secret_selector"
    assert record["replacement_table_index"] == 2

    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["areas"][4]["custom_record_ids"] == []
    assert model["areas"][5]["custom_record_ids"] == []
    assert model["areas"][6]["custom_record_ids"] == [custom_id]
    assert model["areas"][7]["custom_record_ids"] == [custom_id]
    assert model["summary"]["record_count"] == 351
    assert model["summary"]["custom_record_count"] == 1
    assert model["summary"]["custom_area_record_reference_count"] == 2

    with sqlite3.connect(database) as connection:
        source_records_after = connection.execute(
            """SELECT record_index, source_coordinate_word, source_value_byte,
                      coordinate_word, value_byte
               FROM overworld_hidden_item_record ORDER BY record_index"""
        ).fetchall()
        source_links_after = connection.execute(
            """SELECT area_index, ordinal, record_index
               FROM overworld_hidden_item_area_record ORDER BY area_index, ordinal"""
        ).fetchall()
    assert source_records_after == source_records_before
    assert source_links_after == source_links_before
    assert validate_project(database) == []


@pytest.mark.parametrize(
    ("invalid_id", "kwargs", "message"),
    [
        (True, {"value_byte": 1}, "custom_record_id"),
        (False, {}, "supply area_indices"),
        (False, {"area_indices": []}, "at least one area"),
        (False, {"area_indices": [2, 2]}, "duplicate area"),
        (False, {"area_indices": [128]}, "0..127"),
        (False, {"coordinate_word": 0xFFFF}, "reserved as the list sentinel"),
        (False, {"coordinate_word": True}, "coordinate_word"),
        (False, {"value_byte": 256}, "value_byte"),
        (False, {"value_byte": False}, "value_byte"),
    ],
)
def test_custom_hidden_item_update_rejects_invalid_fields(
    tmp_path: Path,
    invalid_id: bool,
    kwargs: dict[str, object],
    message: str,
) -> None:
    database, _ = initialize_project("invalid_custom_item_update", tmp_path)
    _seed_semantic_model(database)
    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[0],
        coordinate_word=1,
        value_byte=1,
        dry_run=False,
    )
    custom_id = True if invalid_id else created["record"]["custom_record_id"]
    with pytest.raises(ValueError, match=message):
        update_custom_overworld_hidden_item(
            database, custom_id, **kwargs  # type: ignore[arg-type]
        )


def test_custom_hidden_item_update_cannot_target_an_imported_source_record(
    tmp_path: Path,
) -> None:
    database, _ = initialize_project("source_update_guard", tmp_path)
    _seed_semantic_model(database)
    with pytest.raises(KeyError, match="custom overworld hidden item not found"):
        update_custom_overworld_hidden_item(database, 1, value_byte=0x84)
    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["records"][0]["value_byte"] == model["records"][0]["source_value_byte"]
    assert model["custom_records"] == []


def test_cli_custom_hidden_item_update_defaults_to_dry_run_and_requires_apply(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("custom_item_update_cli", tmp_path)
    _seed_semantic_model(database)
    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[4, 5],
        coordinate_word=0x1234,
        value_byte=0x05,
        dry_run=False,
    )
    custom_id = created["record"]["custom_record_id"]
    before_export = json_path.read_bytes()
    runner = CliRunner()
    arguments = [
        "update-custom-overworld-hidden-item",
        str(database),
        str(custom_id),
        "--area-index", "6",
        "--area-index", "7",
        "--coordinate-word", "$2345",
        "--value-byte", "$84",
    ]

    preview = runner.invoke(cli, arguments)
    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.output)
    assert preview_payload["dry_run"] is True
    assert preview_payload["proposed"]["area_indices"] == [6, 7]
    assert preview_payload["proposed"]["coordinate_word"] == 0x2345
    assert preview_payload["proposed"]["value_byte"] == 0x84
    assert json_path.read_bytes() == before_export

    applied = runner.invoke(cli, [*arguments, "--apply"])
    assert applied.exit_code == 0, applied.output
    applied_payload = json.loads(applied.output)
    assert applied_payload["dry_run"] is False
    assert applied_payload["record"]["area_indices"] == [6, 7]
    assert applied_payload["record"]["coordinate_word"] == 0x2345
    assert applied_payload["record"]["value_byte"] == 0x84
    model = get_overworld_hidden_item_model(database)
    assert model is not None
    assert model["areas"][4]["custom_record_ids"] == []
    assert model["areas"][6]["custom_record_ids"] == [custom_id]
    assert validate_project(database) == []


def test_custom_hidden_item_update_rolls_back_all_fields_when_area_link_insert_fails(
    tmp_path: Path,
) -> None:
    """A failed replacement of many-to-many links must not partially apply fields."""
    database, json_path = initialize_project("custom_item_update_rollback", tmp_path)
    _seed_semantic_model(database)
    created = create_custom_overworld_hidden_item(
        database,
        area_indices=[4, 5],
        coordinate_word=0x1234,
        value_byte=0x05,
        dry_run=False,
    )
    custom_id = created["record"]["custom_record_id"]
    export_before = json_path.read_bytes()

    # Force the second new relationship to fail after the first was inserted.
    # The API's transaction must restore both the old links and packed fields.
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TRIGGER fail_custom_hidden_item_area_link
               BEFORE INSERT ON overworld_hidden_item_custom_area_record
               WHEN NEW.area_index = 7
               BEGIN
                   SELECT RAISE(ABORT, 'injected area-link failure');
               END"""
        )

    with pytest.raises(ValueError, match="could not update custom overworld hidden item"):
        update_custom_overworld_hidden_item(
            database,
            custom_id,
            area_indices=[6, 7],
            coordinate_word=0x4567,
            value_byte=0x84,
            dry_run=False,
        )

    model = get_overworld_hidden_item_model(database)
    assert model is not None
    record = next(
        item for item in model["custom_records"]
        if item["custom_record_id"] == custom_id
    )
    assert record["area_indices"] == [4, 5]
    assert record["coordinate_word"] == 0x1234
    assert record["value_byte"] == 0x05
    assert model["areas"][4]["custom_record_ids"] == [custom_id]
    assert model["areas"][5]["custom_record_ids"] == [custom_id]
    assert model["areas"][6]["custom_record_ids"] == []
    assert model["areas"][7]["custom_record_ids"] == []
    assert json_path.read_bytes() == export_before
    assert model["summary"]["record_count"] == 351
    assert model["summary"]["custom_record_count"] == 1
    assert validate_project(database) == []
