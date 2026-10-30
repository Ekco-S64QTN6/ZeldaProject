"""Tests for explicit and preview-only SQLite project migrations."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    CURRENT_SCHEMA_VERSION,
    initialize_project,
    migrate_project,
    validate_project,
)


def _make_schema_v1_project(tmp_path: Path, name: str) -> tuple[Path, Path]:
    """Downgrade a fresh fixture to the table/version shape of schema v1."""
    database, json_path = initialize_project(name, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        table_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        for table_name in table_names:
            if table_name not in {"project", "schema_version", "sqlite_sequence"}:
                escaped = table_name.replace('"', '""')
                connection.execute(f'DROP TABLE "{escaped}"')
        connection.execute("DELETE FROM schema_version WHERE version > 1")
        connection.execute(
            "UPDATE project SET format_version = 1 WHERE singleton = 1"
        )
    return database, json_path


def _assert_schema_v1(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        version_rows = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        project_version = connection.execute(
            "SELECT format_version FROM project WHERE singleton = 1"
        ).fetchone()
    assert tables == {"project", "schema_version", "sqlite_sequence"}
    assert version_rows == [(1,)]
    assert project_version == (1,)


def test_dry_run_simulates_all_migration_steps_without_touching_project_files(
    tmp_path: Path,
) -> None:
    database, json_path = _make_schema_v1_project(tmp_path, "preview-all-migrations")
    json_path.write_text('{"keep":"the original sidecar"}\n', encoding="utf-8")
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()

    assert migrate_project(database, json_path, dry_run=True) is True

    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before
    _assert_schema_v1(database)


def test_explicit_migration_after_preview_upgrades_and_exports_schema_v5(
    tmp_path: Path,
) -> None:
    database, json_path = _make_schema_v1_project(tmp_path, "apply-after-preview")

    assert migrate_project(database, json_path, dry_run=True) is True
    _assert_schema_v1(database)

    assert migrate_project(database, json_path) is True
    assert validate_project(database) == []
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    assert payload["format_version"] == CURRENT_SCHEMA_VERSION

    with sqlite3.connect(database) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        project_version = connection.execute(
            "SELECT format_version FROM project WHERE singleton = 1"
        ).fetchone()
    assert versions == [(1,), (2,), (3,), (4,), (5,)]
    assert project_version == (CURRENT_SCHEMA_VERSION,)


def test_cli_migrate_dry_run_is_non_destructive_and_default_invocation_applies(
    tmp_path: Path,
) -> None:
    database, json_path = _make_schema_v1_project(tmp_path, "cli-migration-preview")
    json_path.write_text("preserve until apply\n", encoding="utf-8")
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()
    runner = CliRunner()

    preview = runner.invoke(cli, ["migrate-project", str(database), "--dry-run"])

    assert preview.exit_code == 0, preview.output
    assert "Would migrate project to schema v5" in preview.output
    assert "no files changed" in preview.output
    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before
    _assert_schema_v1(database)

    applied = runner.invoke(cli, ["migrate-project", str(database)])
    assert applied.exit_code == 0, applied.output
    assert "Migrated project to schema v5" in applied.output
    assert validate_project(database) == []


def test_current_schema_dry_run_does_not_refresh_a_stale_json_sidecar(
    tmp_path: Path,
) -> None:
    database, json_path = initialize_project("current-migration-preview", tmp_path)
    json_path.write_text("leave stale export alone during preview\n", encoding="utf-8")
    database_before = database.read_bytes()
    json_before = json_path.read_bytes()

    assert migrate_project(database, json_path, dry_run=True) is False

    assert database.read_bytes() == database_before
    assert json_path.read_bytes() == json_before

    assert migrate_project(database, json_path) is False
    assert validate_project(database) == []
