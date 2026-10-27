"""Tests for read-only project validation."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    CURRENT_SCHEMA_VERSION,
    export_project,
    initialize_project,
    validate_project,
)


def test_validate_accepts_new_project_without_mutating_artifacts(
    tmp_path: Path,
) -> None:
    database_path, json_path = initialize_project("validated", tmp_path)
    original_database = database_path.read_bytes()
    original_export = json_path.read_bytes()

    assert validate_project(database_path) == []

    assert database_path.read_bytes() == original_database
    assert json_path.read_bytes() == original_export


def test_validate_reports_missing_database(tmp_path: Path) -> None:
    problems = validate_project(tmp_path / "missing.db")

    assert len(problems) == 1
    assert "database file not found" in problems[0]


def test_validate_reports_missing_json_export(tmp_path: Path) -> None:
    database_path, json_path = initialize_project("missing-export", tmp_path)
    json_path.unlink()

    problems = validate_project(database_path)

    assert any("JSON export file not found" in problem for problem in problems)


def test_validate_reports_stale_json_export(tmp_path: Path) -> None:
    database_path, json_path = initialize_project("stale", tmp_path)
    json_path.write_text('{"format":"wrong"}\n', encoding="utf-8")

    problems = validate_project(database_path)

    assert any("JSON export is stale or non-canonical" in problem for problem in problems)


def test_validate_reports_invalid_sqlite_file(tmp_path: Path) -> None:
    database_path = tmp_path / "broken.db"
    database_path.write_bytes(b"not a sqlite database")

    problems = validate_project(database_path)

    assert any("SQLite integrity check failed to run" in problem for problem in problems)


def test_validate_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    database_path, _ = initialize_project("future-schema", tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION + 1, "2099-01-01T00:00:00Z"),
        )
    export_project(database_path)

    problems = validate_project(database_path)

    assert any("unsupported database schema version" in problem for problem in problems)


def test_cli_validate_succeeds_for_new_project(tmp_path: Path) -> None:
    database_path, _ = initialize_project("cli-valid", tmp_path)

    result = CliRunner().invoke(cli, ["validate", str(database_path)])

    assert result.exit_code == 0, result.output
    assert "[OK] SQLite project and JSON export are consistent" in result.output


def test_cli_validate_fails_for_stale_export(tmp_path: Path) -> None:
    database_path, json_path = initialize_project("cli-stale", tmp_path)
    json_path.write_text("{}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["validate", str(database_path)])

    assert result.exit_code == 1
    assert "[FAIL]" in result.output
    assert "stale or non-canonical" in result.output
