"""SQLite project metadata, validated source assets, migrations, and JSON export.

Schema v2 stores project metadata and validated source-export snapshots.
Semantic game-system tables and ROM writing remain future work.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    AssetLoadError,
    load_extracted_asset,
    load_source_export,
    validate_source_export,
)

PROJECT_FORMAT = "zelda-suite-project"
PROJECT_FORMAT_VERSION = 2
CURRENT_SCHEMA_VERSION = 2
BASE_ROM_FILENAME = "Legend of Zelda, The - A Link to the Past (U) [!].smc"
_PROJECT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ASSET_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")

_SOURCE_ASSET_TABLE_SQL = """
CREATE TABLE source_asset (
    asset_key TEXT PRIMARY KEY CHECK (length(asset_key) BETWEEN 1 AND 96),
    asset_format TEXT NOT NULL CHECK (length(asset_format) > 0),
    asset_format_version INTEGER NOT NULL CHECK (asset_format_version > 0),
    source_file TEXT NOT NULL CHECK (length(source_file) > 0),
    source_revision TEXT NOT NULL CHECK (length(source_revision) > 0),
    payload_sha256 TEXT NOT NULL CHECK (
        length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    imported_at TEXT NOT NULL CHECK (length(imported_at) > 0),
    payload_json TEXT NOT NULL
);
"""

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
""" + _SOURCE_ASSET_TABLE_SQL


def _utc_timestamp() -> str:
    """Return a sortable UTC timestamp with an explicit Z suffix."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _validate_project_name(name: str) -> None:
    if not _PROJECT_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "project name must be 1-64 characters, start with a letter or digit, "
            "and contain only letters, digits, hyphens, or underscores"
        )


def _validate_asset_key(asset_key: str) -> None:
    if not isinstance(asset_key, str) or not _ASSET_KEY_PATTERN.fullmatch(asset_key):
        raise ValueError(
            "asset key must be 1-96 characters, start with a letter or digit, "
            "and contain only letters, digits, dots, hyphens, or underscores"
        )


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _source_file_metadata(payload: dict[str, Any]) -> str:
    """Return deterministic provenance for single- and multi-source exports."""
    source_file = payload.get("source_file")
    if isinstance(source_file, str) and source_file:
        return source_file

    source_blocks = payload.get("source_blocks")
    if isinstance(source_blocks, list):
        source_files = sorted(
            {
                block["source_file"]
                for block in source_blocks
                if isinstance(block, dict)
                and isinstance(block.get("source_file"), str)
                and block["source_file"]
            }
        )
        if source_files:
            return ";".join(source_files)

    raise ValueError(
        "source export must include source_file or source_blocks with source_file values"
    )


def _read_source_asset_row(row: sqlite3.Row) -> dict[str, Any]:
    """Decode and verify a persisted source-asset record."""
    asset_key = str(row["asset_key"])
    _validate_asset_key(asset_key)
    try:
        payload = json.loads(
            str(row["payload_json"]),
            parse_constant=_reject_nonstandard_constant,
        )
        payload = validate_source_export(payload)
    except (json.JSONDecodeError, AssetLoadError, TypeError, ValueError) as exc:
        raise ValueError(
            f"stored source asset {asset_key!r} has invalid payload: {exc}"
        ) from exc

    canonical = _render_json(payload)
    if str(row["payload_json"]) != canonical:
        raise ValueError(f"stored source asset {asset_key!r} is not canonical JSON")
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    stored_hash = str(row["payload_sha256"])
    if stored_hash != expected_hash:
        raise ValueError(f"stored source asset {asset_key!r} has a SHA-256 mismatch")

    metadata_checks = (
        ("asset_format", payload.get("format")),
        ("asset_format_version", payload.get("format_version")),
        ("source_file", _source_file_metadata(payload)),
        ("source_revision", payload.get("source_revision")),
    )
    for column, value in metadata_checks:
        if row[column] != value:
            raise ValueError(
                f"stored source asset {asset_key!r} has inconsistent {column}"
            )
    return {
        "key": asset_key,
        "format": str(row["asset_format"]),
        "format_version": int(row["asset_format_version"]),
        "source_file": str(row["source_file"]),
        "source_revision": str(row["source_revision"]),
        "sha256": stored_hash,
        "imported_at": str(row["imported_at"]),
        "payload": payload,
    }


def _select_source_asset(
    connection: sqlite3.Connection, asset_key: str
) -> dict[str, Any]:
    row = connection.execute(
        """SELECT asset_key, asset_format, asset_format_version, source_file,
                  source_revision, payload_sha256, imported_at, payload_json
           FROM source_asset WHERE asset_key = ?""",
        (asset_key,),
    ).fetchone()
    if row is None:
        raise KeyError(f"source asset not found: {asset_key}")
    return _read_source_asset_row(row)


def _require_current_schema(connection: sqlite3.Connection) -> None:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "schema_version" not in tables or "source_asset" not in tables:
        raise ValueError(
            "project schema v2 is required; run 'zelda-suite migrate-project' first"
        )
    current_row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = None if current_row is None else current_row[0]
    if current != CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"project schema version is {current}; expected {CURRENT_SCHEMA_VERSION}. "
            "Run 'zelda-suite migrate-project' first."
        )
    project_row = connection.execute(
        "SELECT format_version FROM project WHERE singleton = 1"
    ).fetchone()
    if project_row is None or project_row[0] != PROJECT_FORMAT_VERSION:
        raise ValueError(
            f"project format version must be {PROJECT_FORMAT_VERSION}; "
            "run 'zelda-suite migrate-project' first if this is an older project"
        )


def _export_payload(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
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

    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "source_asset" not in tables:
        raise ValueError(
            "project schema v2 is required; run 'zelda-suite migrate-project' first"
        )
    assets = [
        _read_source_asset_row(row)
        for row in connection.execute(
            """SELECT asset_key, asset_format, asset_format_version, source_file,
                      source_revision, payload_sha256, imported_at, payload_json
               FROM source_asset ORDER BY asset_key"""
        ).fetchall()
    ]

    format_version = int(project_row["format_version"])
    schema_version = int(version_row[0])
    return {
        "format": PROJECT_FORMAT,
        "format_version": format_version,
        "project": {
            "name": str(project_row["name"]),
            "created_at": str(project_row["created_at"]),
            "base_rom": {
                "expected_filename": str(project_row["expected_base_rom_filename"]),
                "sha256": project_row["base_rom_sha256"],
            },
        },
        "schema_version": schema_version,
        "source_assets": assets,
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
                connection.executemany(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    [(1, created_at), (CURRENT_SCHEMA_VERSION, created_at)],
                )
        finally:
            connection.close()

        export_project(database_path, json_path)
    except BaseException:
        for artifact_path in created_artifacts:
            artifact_path.unlink(missing_ok=True)
        raise

    return database_path, json_path



def migrate_project(
    database_path: str | Path, json_path: str | Path | None = None
) -> bool:
    """Migrate a schema-v1 project to v2 and refresh its JSON export.

    Returns True when migration was applied, or False when already current.
    Validation and import never trigger an automatic migration.
    """
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    connection = sqlite3.connect(db_path)
    migrated = False
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not {"project", "schema_version"}.issubset(tables):
            raise ValueError("not a recognized ZeldaProject SQLite database")

        version_row = connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        current = None if version_row is None else version_row[0]
        if current is None:
            raise ValueError("project database has no schema version")
        if current > CURRENT_SCHEMA_VERSION:
            raise ValueError(
                f"project schema version {current} is newer than supported version "
                f"{CURRENT_SCHEMA_VERSION}"
            )
        if current < 1:
            raise ValueError(f"unsupported project schema version: {current}")

        if current == 1:
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != 1:
                raise ValueError("schema-v1 project metadata is inconsistent")
            if "source_asset" in tables:
                raise ValueError(
                    "schema-v1 project unexpectedly contains source_asset; "
                    "refusing an ambiguous partial migration"
                )
            with connection:
                connection.execute(_SOURCE_ASSET_TABLE_SQL)
                connection.execute(
                    "UPDATE project SET format_version = ? WHERE singleton = 1",
                    (PROJECT_FORMAT_VERSION,),
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, _utc_timestamp()),
                )
            migrated = True
        elif current == CURRENT_SCHEMA_VERSION:
            if "source_asset" not in tables:
                raise ValueError("schema-v2 project is missing the source_asset table")
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != PROJECT_FORMAT_VERSION:
                raise ValueError("schema-v2 project metadata is inconsistent")

    except sqlite3.Error as exc:
        raise ValueError(f"could not migrate project database: {exc}") from exc
    finally:
        connection.close()

    # Refreshing the JSON sidecar is explicit, even when the database is current.
    export_project(db_path, json_path)
    return migrated


def _persist_source_asset_payload(
    database_path: str | Path,
    asset_key: str,
    payload: dict[str, Any],
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Validate and persist a loaded source-export payload."""
    _validate_asset_key(asset_key)
    try:
        payload = validate_source_export(payload)
    except AssetLoadError as exc:
        raise ValueError(f"source export is invalid: {exc}") from exc

    canonical = _render_json(payload)
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    imported_at = _utc_timestamp()
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        existing = connection.execute(
            "SELECT 1 FROM source_asset WHERE asset_key = ?", (asset_key,)
        ).fetchone()
        if existing is not None and not replace_existing:
            raise ValueError(
                f"source asset key already exists: {asset_key}; use replace_existing=True "
                "or the CLI --replace option to replace it"
            )

        with connection:
            if existing is None:
                connection.execute(
                    """INSERT INTO source_asset (
                           asset_key, asset_format, asset_format_version, source_file,
                           source_revision, payload_sha256, imported_at, payload_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        asset_key,
                        payload["format"],
                        payload["format_version"],
                        _source_file_metadata(payload),
                        payload["source_revision"],
                        payload_hash,
                        imported_at,
                        canonical,
                    ),
                )
            else:
                connection.execute(
                    """UPDATE source_asset SET
                           asset_format = ?, asset_format_version = ?, source_file = ?,
                           source_revision = ?, payload_sha256 = ?, imported_at = ?,
                           payload_json = ?
                       WHERE asset_key = ?""",
                    (
                        payload["format"],
                        payload["format_version"],
                        _source_file_metadata(payload),
                        payload["source_revision"],
                        payload_hash,
                        imported_at,
                        canonical,
                        asset_key,
                    ),
                )
        export_project(db_path)
        return _select_source_asset(connection, asset_key)
    except sqlite3.Error as exc:
        raise ValueError(f"could not store source asset {asset_key!r}: {exc}") from exc
    finally:
        connection.close()


def import_source_asset(
    database_path: str | Path,
    asset_key: str,
    source_export_path: str | Path,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Import a validated source-export JSON file into a project database."""
    try:
        payload = load_source_export(source_export_path)
    except AssetLoadError as exc:
        raise ValueError(f"could not load source export: {exc}") from exc
    return _persist_source_asset_payload(
        database_path,
        asset_key,
        payload,
        replace_existing=replace_existing,
    )


def import_extracted_asset(
    database_path: str | Path,
    asset_name: str,
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_key: str | None = None,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Import a committed manifest asset after registry/provenance checks.

    By default, the project's asset key matches the registry name. A separate
    asset_key may be supplied when multiple project-local snapshots are needed.
    """
    try:
        payload = load_extracted_asset(asset_name, registry_path)
    except AssetLoadError as exc:
        raise ValueError(f"could not load registered asset: {exc}") from exc
    return _persist_source_asset_payload(
        database_path,
        asset_name if asset_key is None else asset_key,
        payload,
        replace_existing=replace_existing,
    )

def list_source_assets(database_path: str | Path) -> list[dict[str, Any]]:
    """List validated source-asset metadata stored in a schema-v2 project."""
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(read_only_uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        rows = connection.execute(
            """SELECT asset_key, asset_format, asset_format_version, source_file,
                      source_revision, payload_sha256, imported_at, payload_json
               FROM source_asset ORDER BY asset_key"""
        ).fetchall()
        assets = []
        for row in rows:
            record = _read_source_asset_row(row)
            assets.append({key: value for key, value in record.items() if key != "payload"})
        return assets
    finally:
        connection.close()


def get_source_asset(database_path: str | Path, asset_key: str) -> dict[str, Any]:
    """Load one stored source asset, verifying its format and SHA-256 digest."""
    _validate_asset_key(asset_key)
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(read_only_uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        return _select_source_asset(connection, asset_key)
    finally:
        connection.close()


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
        required_tables = {"project", "schema_version", "source_asset"}
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
