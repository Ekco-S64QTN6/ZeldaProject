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
    get_overworld_hidden_item_model,
    import_overworld_hidden_item_model,
    initialize_project,
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

    update_overworld_hidden_item(database, 0, value_byte=0x84)
    current = get_overworld_hidden_item_model(database)
    assert current is not None
    assert current["summary"]["modified_record_count"] == 1

    replaced = import_overworld_hidden_item_model(
        database, SOURCE_PATH, replace_existing=True
    )
    assert replaced["summary"]["modified_record_count"] == 0
    assert replaced["records"][0]["value_byte"] == replaced["records"][0]["source_value_byte"]
    assert validate_project(database) == []
