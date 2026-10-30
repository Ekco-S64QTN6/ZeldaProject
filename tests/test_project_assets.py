"""Tests for source-asset persistence and project schema migration."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import zelda_suite.project.store as project_store
from zelda_suite.cli.main import cli
from zelda_suite.extract.asset_loader import (
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.project.store import (
    CURRENT_SCHEMA_VERSION,
    PROJECT_FORMAT,
    PROJECT_FORMAT_VERSION,
    get_source_asset,
    import_extracted_asset,
    import_source_asset,
    initialize_project,
    list_source_assets,
    migrate_project,
    validate_project,
)

ROOT = Path(__file__).resolve().parents[1]
ITEM_VALUES_EXPORT = ROOT / "data" / "extracted" / "falling-prize-item-values.json"
FALL_HEIGHTS_EXPORT = ROOT / "data" / "extracted" / "falling-prize-fall-heights.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"


def _create_schema_v1_project(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "legacy.db"
    json_path = directory / "legacy.json"
    created_at = "2026-01-02T03:04:05Z"

    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE project (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 64),
                format_version INTEGER NOT NULL CHECK (format_version > 0),
                created_at TEXT NOT NULL,
                expected_base_rom_filename TEXT NOT NULL,
                base_rom_sha256 TEXT
            );
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY CHECK (version > 0),
                applied_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """INSERT INTO project (
                   singleton, name, format_version, created_at,
                   expected_base_rom_filename, base_rom_sha256
               ) VALUES (1, ?, 1, ?, ?, NULL)""",
            (
                "legacy",
                created_at,
                "Legend of Zelda, The - A Link to the Past (U) [!].smc",
            ),
        )
        connection.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
            (created_at,),
        )

    legacy_payload: dict[str, Any] = {
        "format": "zelda-suite-project",
        "format_version": 1,
        "project": {
            "name": "legacy",
            "created_at": created_at,
            "base_rom": {
                "expected_filename": (
                    "Legend of Zelda, The - A Link to the Past (U) [!].smc"
                ),
                "sha256": None,
            },
        },
        "schema_version": 1,
    }
    json_path.write_text(
        json.dumps(
            legacy_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return database, json_path


def test_import_source_asset_round_trips_and_updates_canonical_export(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("assets", tmp_path)
    imported = import_source_asset(database, "falling-prize-values", ITEM_VALUES_EXPORT)

    assert imported["key"] == "falling-prize-values"
    assert imported["format"] == "zelda-suite-data-table"
    assert imported["source_file"] == "ancilla_init.asm"
    canonical_payload = json.dumps(
        imported["payload"], ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    assert imported["sha256"] == hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    listed = list_source_assets(database)
    assert len(listed) == 1
    assert "payload" not in listed[0]
    assert listed[0]["key"] == "falling-prize-values"
    assert get_source_asset(database, "falling-prize-values") == imported

    project_export = json.loads(json_path.read_text(encoding="utf-8"))
    assert project_export["format"] == PROJECT_FORMAT
    assert project_export["format_version"] == PROJECT_FORMAT_VERSION
    assert project_export["schema_version"] == CURRENT_SCHEMA_VERSION
    assert project_export["source_assets"] == [imported]
    assert validate_project(database) == []


def test_import_extracted_asset_uses_registered_provenance(tmp_path: Path) -> None:
    database, _ = initialize_project("registry_import", tmp_path)
    expected = load_extracted_asset("falling-prize-item-values", REGISTRY_PATH)

    imported = import_extracted_asset(
        database,
        "falling-prize-item-values",
        REGISTRY_PATH,
    )

    assert imported["key"] == "falling-prize-item-values"
    assert imported["payload"] == expected
    assert imported["source_revision"] == expected["source_revision"]
    assert list_source_assets(database)[0]["key"] == "falling-prize-item-values"
    assert validate_project(database) == []


def test_cli_import_extracted_asset_by_name(tmp_path: Path) -> None:
    database, _ = initialize_project("cli_registry", tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "import-extracted-asset",
            str(database),
            "falling-prize-item-values",
            "--registry",
            str(REGISTRY_PATH),
            "--asset-key",
            "prize-values",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["key"] == "prize-values"
    imported = get_source_asset(database, "prize-values")
    assert imported["payload"]["source_file"] == "ancilla_init.asm"


def test_import_extracted_asset_rejects_unregistered_names(tmp_path: Path) -> None:
    database, _ = initialize_project("unknown_registry", tmp_path)
    with pytest.raises(ValueError, match="unknown extracted asset"):
        import_extracted_asset(database, "not-in-registry", REGISTRY_PATH)


def test_every_registered_asset_round_trips_through_project_storage(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("all_registry_assets", tmp_path)
    registry_assets = list_extracted_assets(REGISTRY_PATH)

    assert registry_assets
    for asset in registry_assets:
        stored = import_extracted_asset(
            database,
            asset["name"],
            REGISTRY_PATH,
        )
        assert stored["key"] == asset["name"]
        assert stored["format"] == asset["format"]
        assert stored["source_revision"] == asset["source_revision"]

    expected_names = sorted(asset["name"] for asset in registry_assets)
    listed = list_source_assets(database)
    assert [asset["key"] for asset in listed] == expected_names

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    exported_assets = exported["source_assets"]
    assert [asset["key"] for asset in exported_assets] == expected_names
    assert exported["schema_version"] == CURRENT_SCHEMA_VERSION

    for metadata in listed:
        stored = get_source_asset(database, metadata["key"])
        committed = load_extracted_asset(metadata["key"], REGISTRY_PATH)
        assert stored["payload"] == committed
        assert stored["sha256"] == metadata["sha256"]
        assert stored["source_revision"] == metadata["source_revision"]
        assert stored["source_file"] == metadata["source_file"]
        if metadata["key"] == "text-message-index":
            assert metadata["source_file"] == "Bank0E.asm;Bank1C.asm"
        elif metadata["key"] == "paid-overworld-interactions":
            assert metadata["source_file"] == ";".join(
                sorted(committed["source_files"])
            )

    assert validate_project(database) == []


def test_duplicate_source_asset_requires_explicit_replacement(tmp_path: Path) -> None:
    database, json_path = initialize_project("replace_asset", tmp_path)
    first = import_source_asset(database, "item-layout", ITEM_VALUES_EXPORT)
    original_export = json_path.read_bytes()

    with pytest.raises(ValueError, match="source asset key already exists"):
        import_source_asset(database, "item-layout", FALL_HEIGHTS_EXPORT)

    assert json_path.read_bytes() == original_export
    assert get_source_asset(database, "item-layout") == first

    replaced = import_source_asset(
        database,
        "item-layout",
        FALL_HEIGHTS_EXPORT,
        replace_existing=True,
    )
    assert replaced["key"] == "item-layout"
    assert replaced["payload"]["table_label"] == ".fall_height"
    assert get_source_asset(database, "item-layout") == replaced
    assert validate_project(database) == []


@pytest.mark.parametrize(
    "asset_key",
    ["", "../escape", "has space", "-leading", "x" * 97, "key/slash"],
)
def test_source_asset_keys_are_safe(tmp_path: Path, asset_key: str) -> None:
    database, _ = initialize_project("safe_keys", tmp_path)

    with pytest.raises(ValueError, match="asset key"):
        import_source_asset(database, asset_key, ITEM_VALUES_EXPORT)


def test_stored_source_asset_digest_and_json_are_checked(tmp_path: Path) -> None:
    database, _ = initialize_project("tamper_check", tmp_path)
    import_source_asset(database, "verified-payload", ITEM_VALUES_EXPORT)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE source_asset SET payload_json = ? WHERE asset_key = ?",
            ("{}", "verified-payload"),
        )

    with pytest.raises(ValueError, match="invalid payload"):
        get_source_asset(database, "verified-payload")
    problems = validate_project(database)
    assert any("project metadata is invalid" in problem for problem in problems)


def test_migrate_schema_v1_project_preserves_metadata_and_exports_v5(
    tmp_path: Path,
) -> None:
    database, json_path = _create_schema_v1_project(tmp_path / "legacy")
    assert migrate_project(database) is True

    with sqlite3.connect(database) as connection:
        project_version = connection.execute(
            "SELECT format_version FROM project WHERE singleton = 1"
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'source_asset'"
        ).fetchone()

    assert project_version == (PROJECT_FORMAT_VERSION,)
    assert versions == [
        (version,) for version in range(1, CURRENT_SCHEMA_VERSION + 1)
    ]
    assert table == ("source_asset",)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    assert payload["project"]["name"] == "legacy"
    assert payload["project"]["created_at"] == "2026-01-02T03:04:05Z"
    assert payload["source_assets"] == []
    assert payload["overworld_hidden_items"] is None
    assert payload["dungeon_chests"] is None
    assert validate_project(database) == []


def test_migration_is_idempotent_and_refreshes_export(tmp_path: Path) -> None:
    database, json_path = initialize_project("already_current", tmp_path)
    assert migrate_project(database) is False
    first_export = json_path.read_bytes()

    json_path.write_text("stale", encoding="utf-8")
    assert migrate_project(database) is False
    assert json_path.read_bytes() == first_export
    assert validate_project(database) == []


def test_migrate_schema_v3_project_adds_dungeon_chest_and_custom_tables(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("legacy_v3", tmp_path)
    with sqlite3.connect(database) as connection, connection:
        connection.execute("DROP TABLE overworld_hidden_item_custom_area_record")
        connection.execute("DROP TABLE overworld_hidden_item_custom_record")
        connection.execute("DROP TABLE dungeon_chest_record")
        connection.execute("DROP TABLE dungeon_chest_model")
        connection.execute("DELETE FROM schema_version WHERE version IN (4, 5)")
        connection.execute("UPDATE project SET format_version = 3 WHERE singleton = 1")

    assert migrate_project(database) is True

    with sqlite3.connect(database) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        format_version = connection.execute(
            "SELECT format_version FROM project WHERE singleton = 1"
        ).fetchone()

    assert versions == [(1,), (2,), (3,), (4,), (CURRENT_SCHEMA_VERSION,)]
    assert format_version == (PROJECT_FORMAT_VERSION,)
    assert {
        "dungeon_chest_model", "dungeon_chest_record",
        "overworld_hidden_item_custom_record", "overworld_hidden_item_custom_area_record",
    }.issubset(tables)
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["format_version"] == PROJECT_FORMAT_VERSION
    assert exported["dungeon_chests"] is None
    assert validate_project(database) == []


def test_migrate_schema_v4_project_adds_project_authored_hidden_item_tables(
    tmp_path: Path,
) -> None:
    database, _ = initialize_project("legacy_v4", tmp_path)
    with sqlite3.connect(database) as connection, connection:
        connection.execute("DROP TABLE overworld_hidden_item_custom_area_record")
        connection.execute("DROP TABLE overworld_hidden_item_custom_record")
        connection.execute("DELETE FROM schema_version WHERE version = 5")
        connection.execute("UPDATE project SET format_version = 4 WHERE singleton = 1")

    assert migrate_project(database) is True

    with sqlite3.connect(database) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
    assert {
        "overworld_hidden_item_custom_record",
        "overworld_hidden_item_custom_area_record",
    }.issubset(tables)
    assert versions == [(1,), (2,), (3,), (4,), (5,)]
    assert validate_project(database) == []


def test_migration_rolls_back_partial_ddl_when_schema_creation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, json_path = initialize_project("migration_rollback", tmp_path)
    with sqlite3.connect(database) as connection, connection:
        connection.execute("DROP TABLE overworld_hidden_item_custom_area_record")
        connection.execute("DROP TABLE overworld_hidden_item_custom_record")
        connection.execute("DELETE FROM schema_version WHERE version = 5")
        connection.execute("UPDATE project SET format_version = 4 WHERE singleton = 1")

    original_export = json_path.read_bytes()
    monkeypatch.setattr(
        project_store,
        "_OVERWORLD_CUSTOM_SCHEMA_SQL",
        "CREATE TABLE migration_partial_marker (id INTEGER PRIMARY KEY);"
        "\nINVALID MIGRATION STATEMENT;",
    )

    with pytest.raises(ValueError, match="could not migrate project database"):
        migrate_project(database)

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        format_version = connection.execute(
            "SELECT format_version FROM project WHERE singleton = 1"
        ).fetchone()

    assert "migration_partial_marker" not in tables
    assert "overworld_hidden_item_custom_record" not in tables
    assert "overworld_hidden_item_custom_area_record" not in tables
    assert versions == [(1,), (2,), (3,), (4,)]
    assert format_version == (4,)
    assert json_path.read_bytes() == original_export


def test_import_does_not_implicitly_migrate_v1_project(tmp_path: Path) -> None:
    database, json_path = _create_schema_v1_project(tmp_path / "legacy_no_auto")
    with pytest.raises(ValueError, match="migrate-project"):
        import_source_asset(database, "item-values", ITEM_VALUES_EXPORT)

    with sqlite3.connect(database) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert versions == [(1,)]
    assert "source_asset" not in tables
    assert json.loads(json_path.read_text(encoding="utf-8"))["format_version"] == 1


def test_cli_migration_and_source_asset_commands(tmp_path: Path) -> None:
    database, _ = initialize_project("cli_assets", tmp_path)
    runner = CliRunner()

    imported = runner.invoke(
        cli,
        [
            "import-source-asset",
            str(database),
            "receipt-values",
            str(ITEM_VALUES_EXPORT),
        ],
    )
    assert imported.exit_code == 0, imported.output
    assert json.loads(imported.output)["key"] == "receipt-values"

    listed = runner.invoke(cli, ["list-source-assets", str(database)])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)[0]["key"] == "receipt-values"

    fetched = runner.invoke(
        cli, ["get-source-asset", str(database), "receipt-values"]
    )
    assert fetched.exit_code == 0, fetched.output
    assert json.loads(fetched.output)["payload"]["entry_count"] == 7

    migrated_db, _ = _create_schema_v1_project(tmp_path / "cli_legacy")
    migrated = runner.invoke(cli, ["migrate-project", str(migrated_db)])
    assert migrated.exit_code == 0, migrated.output
    assert "Migrated project to schema v5" in migrated.output
    assert validate_project(migrated_db) == []
