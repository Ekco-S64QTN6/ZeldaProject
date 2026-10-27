"""SQLite project initialization and canonical JSON export.

Schema version 1 deliberately stores only project metadata. Game-system tables
will be added alongside the Phase 1 extractors that define their semantics.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_FORMAT = "zelda-suite-project"
PROJECT_FORMAT_VERSION = 1
CURRENT_SCHEMA_VERSION = 1
BASE_ROM_FILENAME = "Legend of Zelda, The - A Link to the Past (U) [!].smc"
_PROJECT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

_SCHEMA_SQL = """
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


def _utc_timestamp() -> str:
    """Return a sortable UTC timestamp with an explicit Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _validate_project_name(name: str) -> None:
    if not _PROJECT_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "project name must be 1-64 characters, start with a letter or digit, "
            "and contain only letters, digits, hyphens, or underscores"
        )


def _export_payload(connection: sqlite3.Connection) -> dict[str, Any]:
    project_row = connection.execute(
        """SELECT name, format_version, created_at,
                  expected_base_rom_filename, base_rom_sha256
           FROM project WHERE singleton = 1"""
    ).fetchone()
    if project_row is None:
        raise ValueError("database does not contain project metadata")

    version_row = connection.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()
    if version_row is None or version_row[0] is None:
        raise ValueError("database does not contain a schema version")

    return {
        "format": PROJECT_FORMAT,
        "format_version": int(project_row[1]),
        "project": {
            "name": str(project_row[0]),
            "created_at": str(project_row[2]),
            "base_rom": {
                "expected_filename": str(project_row[3]),
                "sha256": project_row[4],
            },
        },
        "schema_version": int(version_row[0]),
    }


def _render_json(payload: dict[str, Any]) -> str:
    """Serialize an export payload using the canonical byte representation."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def export_project(
    database_path: str | Path, json_path: str | Path | None = None
) -> Path:
    """Export project metadata as stable, sorted, UTF-8 JSON.

    The SQLite database remains authoritative. The output is atomically replaced
    so a failed write does not leave a partially-written export behind.
    """
    db_path = Path(database_path)
    output_path = Path(json_path) if json_path is not None else db_path.with_suffix(".json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(read_only_uri, uri=True)
    try:
        payload = _export_payload(connection)
    finally:
        connection.close()

    rendered = _render_json(payload)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(rendered)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return output_path


def initialize_project(
    name: str, project_directory: str | Path
) -> tuple[Path, Path]:
    """Create a versioned SQLite project and its first JSON export.

    Existing database or export files are never overwritten. The base ROM is
    not read or copied; the project records only the canonical expected name.
    """
    _validate_project_name(name)
    target_directory = Path(project_directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    database_path = target_directory / f"{name}.db"
    json_path = target_directory / f"{name}.json"

    created_artifacts: list[Path] = []
    try:
        # Reserve both final names with exclusive creation so this command
        # cannot accidentally overwrite files that already exist.
        for artifact_path in (database_path, json_path):
            file_descriptor = os.open(
                artifact_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o666,
            )
            os.close(file_descriptor)
            created_artifacts.append(artifact_path)
    except FileExistsError as exc:
        for artifact_path in created_artifacts:
            artifact_path.unlink(missing_ok=True)
        existing_path = exc.filename or str(database_path)
        raise FileExistsError(
            f"refusing to overwrite existing project artifact: {existing_path}"
        ) from exc

    try:
        created_at = _utc_timestamp()
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(_SCHEMA_SQL)
            with connection:
                connection.execute(
                    """INSERT INTO project (
                           singleton, name, format_version, created_at,
                           expected_base_rom_filename, base_rom_sha256
                       ) VALUES (1, ?, ?, ?, ?, NULL)""",
                    (
                        name,
                        PROJECT_FORMAT_VERSION,
                        created_at,
                        BASE_ROM_FILENAME,
                    ),
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, created_at),
                )
        finally:
            connection.close()

        export_project(database_path, json_path)
    except BaseException:
        for artifact_path in created_artifacts:
            artifact_path.unlink(missing_ok=True)
        raise

    return database_path, json_path



def validate_project(
    database_path: str | Path, json_path: str | Path | None = None
) -> list[str]:
    """Validate a project without mutating its SQLite database or JSON export.

    Returns a list of human-readable problems. An empty list means the current
    schema is structurally sound and the adjacent JSON export matches SQLite.
    """
    db_path = Path(database_path)
    output_path = Path(json_path) if json_path is not None else db_path.with_suffix(".json")
    if not db_path.is_file():
        return [f"database file not found: {db_path}"]

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(read_only_uri, uri=True)
    except sqlite3.Error as exc:
        return [f"could not open database read-only: {exc}"]

    problems: list[str] = []
    try:
        try:
            integrity_rows = connection.execute("PRAGMA quick_check").fetchall()
        except sqlite3.Error as exc:
            return [f"SQLite integrity check failed to run: {exc}"]

        if integrity_rows != [("ok",)]:
            detail = "; ".join(str(row[0]) for row in integrity_rows)
            problems.append(f"SQLite integrity check failed: {detail}")

        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        required_tables = {"project", "schema_version"}
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            problems.append(
                "missing required table(s): " + ", ".join(missing_tables)
            )
            return problems

        try:
            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
        except sqlite3.Error as exc:
            problems.append(f"foreign-key check failed to run: {exc}")
        else:
            if foreign_key_errors:
                problems.append(
                    f"foreign-key check found {len(foreign_key_errors)} violation(s)"
                )

        try:
            payload = _export_payload(connection)
        except (sqlite3.Error, ValueError, TypeError) as exc:
            problems.append(f"project metadata is invalid: {exc}")
            return problems

        format_version = payload["format_version"]
        if format_version != PROJECT_FORMAT_VERSION:
            problems.append(
                f"unsupported project format version {format_version}; "
                f"this tool supports {PROJECT_FORMAT_VERSION}"
            )

        schema_version = payload["schema_version"]
        if schema_version != CURRENT_SCHEMA_VERSION:
            problems.append(
                f"unsupported database schema version {schema_version}; "
                f"this tool supports {CURRENT_SCHEMA_VERSION}"
            )

        try:
            _validate_project_name(payload["project"]["name"])
        except (ValueError, TypeError) as exc:
            problems.append(f"invalid project name in metadata: {exc}")

        if payload["project"]["base_rom"]["expected_filename"] != BASE_ROM_FILENAME:
            problems.append(
                "project metadata does not name the canonical US base ROM"
            )

        try:
            expected_json = _render_json(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            problems.append(f"project metadata cannot be exported as JSON: {exc}")
        else:
            if not output_path.is_file():
                problems.append(f"JSON export file not found: {output_path}")
            else:
                try:
                    actual_json = output_path.read_bytes()
                except OSError as exc:
                    problems.append(f"could not read JSON export: {exc}")
                else:
                    if actual_json != expected_json:
                        problems.append(
                            f"JSON export is stale or non-canonical: {output_path}"
                        )
    finally:
        connection.close()

    return problems
