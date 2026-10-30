"""Tests for SQLite project initialization and canonical JSON exports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    BASE_ROM_FILENAME,
    CURRENT_SCHEMA_VERSION,
    PROJECT_FORMAT,
    PROJECT_FORMAT_VERSION,
    export_project,
    initialize_project,
)


def test_initialize_project_creates_database_and_json_export(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"

    database_path, json_path = initialize_project("demo_project", project_dir)

    assert database_path == project_dir / "demo_project.db"
    assert json_path == project_dir / "demo_project.json"
    assert database_path.is_file()
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["format"] == PROJECT_FORMAT
    assert payload["format_version"] == PROJECT_FORMAT_VERSION
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    assert payload["project"]["name"] == "demo_project"
    assert payload["project"]["base_rom"] == {
        "expected_filename": BASE_ROM_FILENAME,
        "sha256": None,
    }

    with sqlite3.connect(database_path) as connection:
        project_row = connection.execute(
            "SELECT name, format_version, base_rom_sha256 FROM project"
        ).fetchone()
        version_rows = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()

    assert project_row == ("demo_project", PROJECT_FORMAT_VERSION, None)
    assert version_rows == [
        (version,) for version in range(1, CURRENT_SCHEMA_VERSION + 1)
    ]


def test_export_is_stable_for_unchanged_database(tmp_path: Path) -> None:
    database_path, json_path = initialize_project("stable", tmp_path)
    first_export = json_path.read_text(encoding="utf-8")

    returned_path = export_project(database_path)

    assert returned_path == json_path
    assert json_path.read_text(encoding="utf-8") == first_export
    assert first_export.endswith("\n")
    assert "\r\n" not in first_export


def test_initialize_project_does_not_overwrite_existing_database(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    existing_db = project_dir / "demo.db"
    existing_db.write_text("keep this file", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        initialize_project("demo", project_dir)

    assert existing_db.read_text(encoding="utf-8") == "keep this file"
    assert not (project_dir / "demo.json").exists()


def test_initialize_project_cleans_up_reservation_if_export_exists(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    existing_json = project_dir / "demo.json"
    existing_json.write_text("preserve this export", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        initialize_project("demo", project_dir)

    assert existing_json.read_text(encoding="utf-8") == "preserve this export"
    assert not (project_dir / "demo.db").exists()


@pytest.mark.parametrize("name", ["../escape", "bad/name", "two words", "", ".", "-bad"])
def test_initialize_project_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="project name"):
        initialize_project(name, tmp_path / "project")

    assert not (tmp_path / "escape.db").exists()
    assert not (tmp_path / "project").exists()


def test_cli_init_creates_project_without_requiring_a_rom(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli, ["init", "new-game", "--workspace", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "project" / "new-game.db").is_file()
    assert (tmp_path / "project" / "new-game.json").is_file()
    assert "No ROM was read or copied" in result.output


def test_cli_init_reports_existing_project_without_overwriting(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    existing_json = project_dir / "existing.json"
    existing_json.write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        cli, ["init", "existing", "--workspace", str(tmp_path)]
    )

    assert result.exit_code != 0
    assert "refusing to overwrite" in result.output
    assert existing_json.read_text(encoding="utf-8") == "keep"
    assert not (project_dir / "existing.db").exists()
