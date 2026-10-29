"""SQLite project metadata, semantic overworld records, migrations, and JSON export.

Schema v3 stores validated source-export snapshots and the first editable
semantic domain. ROM writing and general game-system models remain future work.
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
from typing import Any, cast

from zelda_suite.extract.asset_loader import (
    AssetLoadError,
    load_extracted_asset,
    load_source_export,
    validate_source_export,
)
from zelda_suite.extract.overworld_hidden_item_value_semantics import (
    OverworldHiddenItemValueSemanticsError,
    audit_overworld_hidden_item_value_semantics,
    classify_overworld_hidden_item_value_byte,
)
from zelda_suite.extract.overworld_hidden_item_verification import (
    OverworldHiddenItemVerificationError,
    parse_overworld_hidden_item_source,
)

PROJECT_FORMAT = "zelda-suite-project"
PROJECT_FORMAT_VERSION = 3
CURRENT_SCHEMA_VERSION = 3
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


_OVERWORLD_SCHEMA_SQL = """
CREATE TABLE overworld_hidden_item_model (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    source_file TEXT NOT NULL CHECK (length(source_file) > 0),
    source_revision TEXT NOT NULL CHECK (length(source_revision) = 40),
    source_sha256 TEXT NOT NULL CHECK (
        length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    imported_at TEXT NOT NULL CHECK (length(imported_at) > 0),
    consumer_label TEXT NOT NULL CHECK (consumer_label = 'Overworld_RevealSecret'),
    replacement_table_label TEXT NOT NULL CHECK (
        replacement_table_label = 'Overworld_SecretTileType'
    )
);

CREATE TABLE overworld_hidden_item_area (
    area_index INTEGER PRIMARY KEY CHECK (area_index BETWEEN 0 AND 127),
    pointer_entry_file_offset INTEGER NOT NULL CHECK (pointer_entry_file_offset >= 0),
    target_label TEXT NOT NULL CHECK (length(target_label) > 0),
    target_file_offset INTEGER NOT NULL CHECK (target_file_offset >= 0),
    sentinel_file_offset INTEGER NOT NULL CHECK (sentinel_file_offset >= 0),
    record_count INTEGER NOT NULL CHECK (record_count BETWEEN 0 AND 351)
);

CREATE TABLE overworld_hidden_item_record (
    record_index INTEGER PRIMARY KEY CHECK (record_index BETWEEN 0 AND 350),
    source_label TEXT NOT NULL CHECK (length(source_label) > 0),
    source_line INTEGER NOT NULL CHECK (source_line > 0),
    source_file_offset INTEGER NOT NULL CHECK (source_file_offset >= 0),
    source_expression TEXT NOT NULL CHECK (length(source_expression) > 0),
    source_coordinate_word INTEGER NOT NULL CHECK (
        source_coordinate_word BETWEEN 0 AND 65534
    ),
    coordinate_word INTEGER NOT NULL CHECK (coordinate_word BETWEEN 0 AND 65534),
    source_value_byte INTEGER NOT NULL CHECK (source_value_byte BETWEEN 0 AND 255),
    value_byte INTEGER NOT NULL CHECK (value_byte BETWEEN 0 AND 255),
    consumer_class TEXT NOT NULL CHECK (
        consumer_class IN ('zero_value', 'ordinary_secret_mask', 'extended_secret_selector')
    ),
    consumer_operation TEXT NOT NULL CHECK (length(consumer_operation) > 0),
    selector_byte_offset INTEGER CHECK (
        selector_byte_offset IS NULL OR selector_byte_offset BETWEEN 0 AND 15
    ),
    replacement_table_index INTEGER CHECK (
        replacement_table_index IS NULL OR replacement_table_index BETWEEN 0 AND 3
    ),
    replacement_word_value INTEGER CHECK (
        replacement_word_value IS NULL OR replacement_word_value BETWEEN 0 AND 65535
    ),
    replacement_word_comment TEXT,
    special_case TEXT
);

CREATE TABLE overworld_hidden_item_area_record (
    area_index INTEGER NOT NULL REFERENCES overworld_hidden_item_area(area_index)
        ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    record_index INTEGER NOT NULL REFERENCES overworld_hidden_item_record(record_index)
        ON DELETE CASCADE,
    PRIMARY KEY (area_index, ordinal),
    UNIQUE (area_index, record_index)
);

CREATE TABLE overworld_hidden_item_replacement_word (
    table_index INTEGER PRIMARY KEY CHECK (table_index BETWEEN 0 AND 3),
    source_line INTEGER NOT NULL CHECK (source_line > 0),
    file_offset INTEGER NOT NULL CHECK (file_offset >= 0),
    selector_byte_offset INTEGER NOT NULL CHECK (
        selector_byte_offset IN (0, 2, 4, 6)
    ),
    expression TEXT NOT NULL CHECK (length(expression) > 0),
    value INTEGER NOT NULL CHECK (value BETWEEN 0 AND 65535),
    comment TEXT NOT NULL CHECK (length(comment) > 0)
);
"""
_OVERWORLD_TABLE_NAMES = {
    "overworld_hidden_item_model",
    "overworld_hidden_item_area",
    "overworld_hidden_item_record",
    "overworld_hidden_item_area_record",
    "overworld_hidden_item_replacement_word",
}

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
""" + _SOURCE_ASSET_TABLE_SQL + _OVERWORLD_SCHEMA_SQL


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

    source_files = payload.get("source_files")
    if isinstance(source_files, list):
        normalized_source_files = sorted(
            {source for source in source_files if isinstance(source, str) and source}
        )
        if normalized_source_files:
            return ";".join(normalized_source_files)

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
        "source export must include source_file, source_files, or source_blocks with source_file values"
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
    required_tables = {"schema_version", "source_asset"} | _OVERWORLD_TABLE_NAMES
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise ValueError(
            "project schema v3 is required; run 'zelda-suite migrate-project' first "
            "(missing: " + ", ".join(missing_tables) + ")"
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



def _export_overworld_hidden_items(
    connection: sqlite3.Connection,
) -> dict[str, Any] | None:
    """Validate and serialize the first editable semantic domain in a project."""
    model = connection.execute(
        """SELECT source_file, source_revision, source_sha256, imported_at,
                  consumer_label, replacement_table_label
           FROM overworld_hidden_item_model WHERE singleton = 1"""
    ).fetchone()
    table_counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in (
            "overworld_hidden_item_area",
            "overworld_hidden_item_record",
            "overworld_hidden_item_area_record",
            "overworld_hidden_item_replacement_word",
        )
    }
    if model is None:
        if any(table_counts.values()):
            raise ValueError(
                "overworld hidden-item rows exist without model provenance metadata"
            )
        return None

    if table_counts["overworld_hidden_item_area"] != 128:
        raise ValueError("overworld hidden-item model must contain 128 area entries")
    if table_counts["overworld_hidden_item_record"] != 351:
        raise ValueError("overworld hidden-item model must contain 351 records")
    if table_counts["overworld_hidden_item_replacement_word"] != 4:
        raise ValueError("overworld hidden-item model must contain four replacement words")

    replacement_rows = connection.execute(
        """SELECT table_index, source_line, file_offset, selector_byte_offset,
                  expression, value, comment
           FROM overworld_hidden_item_replacement_word ORDER BY table_index"""
    ).fetchall()
    replacement_words = [
        {
            "table_index": int(row["table_index"]),
            "source_line": int(row["source_line"]),
            "file_offset": int(row["file_offset"]),
            "selector_byte_offset": int(row["selector_byte_offset"]),
            "expression": str(row["expression"]),
            "value": int(row["value"]),
            "comment": str(row["comment"]),
        }
        for row in replacement_rows
    ]
    if [word["table_index"] for word in replacement_words] != list(range(4)):
        raise ValueError("overworld hidden-item replacement words must use indexes 0..3")

    areas_rows = connection.execute(
        """SELECT area_index, pointer_entry_file_offset, target_label,
                  target_file_offset, sentinel_file_offset, record_count
           FROM overworld_hidden_item_area ORDER BY area_index"""
    ).fetchall()
    if [int(row["area_index"]) for row in areas_rows] != list(range(128)):
        raise ValueError("overworld hidden-item area indexes must cover 0..127")
    relations = connection.execute(
        """SELECT area_index, ordinal, record_index
           FROM overworld_hidden_item_area_record
           ORDER BY area_index, ordinal"""
    ).fetchall()
    area_records: dict[int, list[int]] = {}
    record_areas: dict[int, list[int]] = {}
    for relation in relations:
        area_index = int(relation["area_index"])
        record_index = int(relation["record_index"])
        ordinal = int(relation["ordinal"])
        indices = area_records.setdefault(area_index, [])
        if ordinal != len(indices):
            raise ValueError(
                f"area {area_index} has a non-contiguous relationship ordinal {ordinal}"
            )
        indices.append(record_index)
        record_areas.setdefault(record_index, []).append(area_index)

    areas: list[dict[str, Any]] = []
    for row in areas_rows:
        area_index = int(row["area_index"])
        indices = area_records.get(area_index, [])
        record_count = int(row["record_count"])
        if len(indices) != record_count:
            raise ValueError(
                f"area {area_index} declares {record_count} records but links {len(indices)}"
            )
        areas.append({
            "area_index": area_index,
            "pointer_entry_file_offset": int(row["pointer_entry_file_offset"]),
            "target_label": str(row["target_label"]),
            "target_file_offset": int(row["target_file_offset"]),
            "record_indices": indices,
            "record_count": record_count,
            "sentinel_file_offset": int(row["sentinel_file_offset"]),
        })

    class_counts = {
        "zero_value": 0,
        "ordinary_secret_mask": 0,
        "extended_secret_selector": 0,
    }
    modified_count = 0
    unmapped_extended_count = 0
    records: list[dict[str, Any]] = []
    record_rows = connection.execute(
        """SELECT record_index, source_label, source_line, source_file_offset,
                  source_expression, source_coordinate_word, coordinate_word,
                  source_value_byte, value_byte, consumer_class, consumer_operation,
                  selector_byte_offset, replacement_table_index,
                  replacement_word_value, replacement_word_comment, special_case
           FROM overworld_hidden_item_record ORDER BY record_index"""
    ).fetchall()
    if [int(row["record_index"]) for row in record_rows] != list(range(351)):
        raise ValueError("overworld hidden-item record indexes must cover 0..350")

    for row in record_rows:
        record_index = int(row["record_index"])
        source_value = int(row["source_value_byte"])
        value = int(row["value_byte"])
        coordinate = int(row["coordinate_word"])
        source_coordinate = int(row["source_coordinate_word"])
        current_semantics = classify_overworld_hidden_item_value_byte(
            value, replacement_words
        )
        stored_semantics = {
            "consumer_class": row["consumer_class"],
            "consumer_operation": row["consumer_operation"],
            "selector_byte_offset": row["selector_byte_offset"],
            "replacement_table_index": row["replacement_table_index"],
            "replacement_word_value": row["replacement_word_value"],
            "replacement_word_comment": row["replacement_word_comment"],
            "special_case": row["special_case"],
        }
        for key, value_expected in stored_semantics.items():
            if current_semantics[key] != value_expected:
                raise ValueError(
                    f"overworld hidden-item record {record_index} has inconsistent "
                    f"{key} for value byte " + "$" + format(value, "02X")
                )
        source_semantics = classify_overworld_hidden_item_value_byte(
            source_value, replacement_words
        )
        is_modified = coordinate != source_coordinate or value != source_value
        if is_modified:
            modified_count += 1
        class_counts[str(current_semantics["consumer_class"])] += 1
        if (
            current_semantics["consumer_class"] == "extended_secret_selector"
            and current_semantics["replacement_table_index"] is None
        ):
            unmapped_extended_count += 1

        records.append({
            "record_index": record_index,
            "area_indices": record_areas.get(record_index, []),
            "source_label": str(row["source_label"]),
            "source_line": int(row["source_line"]),
            "source_file_offset": int(row["source_file_offset"]),
            "source_expression": str(row["source_expression"]),
            "source_coordinate_word": source_coordinate,
            "source_coordinate_word_hex": "$" + format(source_coordinate, "04X"),
            "coordinate_word": coordinate,
            "coordinate_word_hex": "$" + format(coordinate, "04X"),
            "source_value_byte": source_value,
            "source_value_hex": "$" + format(source_value, "02X"),
            "source_consumer_class": str(source_semantics["consumer_class"]),
            "value_byte": value,
            "value_hex": "$" + format(value, "02X"),
            "consumer_class": current_semantics["consumer_class"],
            "consumer_operation": current_semantics["consumer_operation"],
            "selector_byte_offset": current_semantics["selector_byte_offset"],
            "replacement_table_index": current_semantics["replacement_table_index"],
            "replacement_word_value": current_semantics["replacement_word_value"],
            "replacement_word_comment": current_semantics["replacement_word_comment"],
            "special_case": current_semantics["special_case"],
            "canonical_item_id": None,
            "canonical_item_id_resolved": False,
            "is_modified": is_modified,
        })

    return {
        "format": "zelda-suite-overworld-hidden-item-model",
        "format_version": 1,
        "source_file": str(model["source_file"]),
        "source_revision": str(model["source_revision"]),
        "source_sha256": str(model["source_sha256"]),
        "imported_at": str(model["imported_at"]),
        "consumer_label": str(model["consumer_label"]),
        "replacement_table_label": str(model["replacement_table_label"]),
        "areas": areas,
        "records": records,
        "replacement_words": replacement_words,
        "summary": {
            "area_count": len(areas),
            "record_count": len(records),
            "area_record_reference_count": len(relations),
            "empty_area_count": sum(1 for area in areas if area["record_count"] == 0),
            "modified_record_count": modified_count,
            "zero_value_count": class_counts["zero_value"],
            "ordinary_secret_mask_count": class_counts["ordinary_secret_mask"],
            "extended_secret_selector_count": class_counts["extended_secret_selector"],
            "extended_selector_unmapped_count": unmapped_extended_count,
        },
        "evidence": {
            "source_layout_parsed": True,
            "source_consumer_patterns_checked": True,
            "rom_bytes_read": False,
            "rom_modified": False,
            "canonical_item_ids_resolved": False,
        },
    }


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
    required_tables = {"source_asset"} | _OVERWORLD_TABLE_NAMES
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise ValueError(
            "project schema v3 is required; run 'zelda-suite migrate-project' first "
            "(missing: " + ", ".join(missing_tables) + ")"
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
        "overworld_hidden_items": _export_overworld_hidden_items(connection),
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
                    [(1, created_at), (2, created_at), (CURRENT_SCHEMA_VERSION, created_at)],
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
    """Migrate a schema-v1 or schema-v2 project to the current schema and refresh JSON.

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
            if tables & _OVERWORLD_TABLE_NAMES:
                raise ValueError(
                    "schema-v1 project unexpectedly contains overworld model tables; "
                    "refusing an ambiguous partial migration"
                )
            with connection:
                connection.execute(_SOURCE_ASSET_TABLE_SQL)
                connection.execute(
                    "UPDATE project SET format_version = 2 WHERE singleton = 1"
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (2, _utc_timestamp()),
                )
            tables.add("source_asset")
            current = 2
            migrated = True

        if current == 2:
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != 2:
                raise ValueError("schema-v2 project metadata is inconsistent")
            if "source_asset" not in tables:
                raise ValueError("schema-v2 project is missing the source_asset table")
            existing_overworld_tables = tables & _OVERWORLD_TABLE_NAMES
            if existing_overworld_tables:
                raise ValueError(
                    "schema-v2 project unexpectedly contains overworld model tables; "
                    "refusing an ambiguous partial migration"
                )
            with connection:
                for statement in _OVERWORLD_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "UPDATE project SET format_version = ? WHERE singleton = 1",
                    (PROJECT_FORMAT_VERSION,),
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, _utc_timestamp()),
                )
            current = CURRENT_SCHEMA_VERSION
            migrated = True

        if current == CURRENT_SCHEMA_VERSION:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            required_tables = {"source_asset"} | _OVERWORLD_TABLE_NAMES
            missing_tables = sorted(required_tables - tables)
            if missing_tables:
                raise ValueError(
                    "schema-v3 project is missing required table(s): "
                    + ", ".join(missing_tables)
                )
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != PROJECT_FORMAT_VERSION:
                raise ValueError("schema-v3 project metadata is inconsistent")


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
    """List validated source-asset metadata stored in a current project."""
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




def import_overworld_hidden_item_model(
    database_path: str | Path,
    source_path: str | Path,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Import the pinned hidden-item source model into the editable project tables.

    The import stores source values as an immutable baseline and initializes the
    editable coordinate/value fields from those values. It never reads or writes
    a ROM. Re-import with replace_existing=True explicitly resets project edits.
    """
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    source_file_path = Path(source_path)
    try:
        source_bytes = source_file_path.read_bytes()
        source = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not read UTF-8 disassembly source {source_file_path}: {exc}") from exc

    try:
        layout = parse_overworld_hidden_item_source(source)
        semantics = audit_overworld_hidden_item_value_semantics(source)
    except (OverworldHiddenItemVerificationError, OverworldHiddenItemValueSemanticsError, TypeError) as exc:
        raise ValueError(f"could not import overworld hidden-item source: {exc}") from exc

    if layout["source_revision"] != semantics["source_revision"]:
        raise ValueError("hidden-item layout and consumer semantics use different source revisions")
    if len(layout["area_lists"]) != 128 or len(layout["records"]) != 351:
        raise ValueError("hidden-item source layout has unexpected area or record counts")
    semantic_records = {int(record["record_index"]): record for record in semantics["records"]}
    if set(semantic_records) != {int(record["record_index"]) for record in layout["records"]}:
        raise ValueError("hidden-item source layout and semantic rows do not align by record index")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _require_current_schema(connection)
        existing = connection.execute(
            "SELECT 1 FROM overworld_hidden_item_model WHERE singleton = 1"
        ).fetchone()
        if existing is not None and not replace_existing:
            raise ValueError(
                "overworld hidden-item model already exists; pass replace_existing=True "
                "to intentionally discard its project-local edits"
            )
        if existing is None:
            counts = [
                int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in sorted(_OVERWORLD_TABLE_NAMES - {"overworld_hidden_item_model"})
            ]
            if any(counts):
                raise ValueError("overworld hidden-item tables contain partial data without model metadata")

        imported_at = _utc_timestamp()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        with connection:
            if existing is not None:
                connection.execute("DELETE FROM overworld_hidden_item_area_record")
                connection.execute("DELETE FROM overworld_hidden_item_area")
                connection.execute("DELETE FROM overworld_hidden_item_record")
                connection.execute("DELETE FROM overworld_hidden_item_replacement_word")
                connection.execute("DELETE FROM overworld_hidden_item_model")

            connection.execute(
                """INSERT INTO overworld_hidden_item_model (
                       singleton, source_file, source_revision, source_sha256,
                       imported_at, consumer_label, replacement_table_label
                   ) VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    str(semantics["source_file"]),
                    str(semantics["source_revision"]),
                    source_sha256,
                    imported_at,
                    str(semantics["consumer_label"]),
                    str(semantics["replacement_table_label"]),
                ),
            )

            connection.executemany(
                """INSERT INTO overworld_hidden_item_area (
                       area_index, pointer_entry_file_offset, target_label,
                       target_file_offset, sentinel_file_offset, record_count
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        int(area["area_index"]),
                        int(area["pointer_entry_file_offset"]),
                        str(area["target_label"]),
                        int(area["target_file_offset"]),
                        int(area["sentinel_file_offset"]),
                        int(area["record_count"]),
                    )
                    for area in layout["area_lists"]
                ],
            )

            record_inserts = []
            for source_record in layout["records"]:
                record_index = int(source_record["record_index"])
                semantic = semantic_records[record_index]
                coordinate_word = int(source_record["coordinate_word"])
                value_byte = int(source_record["value_byte"])
                record_inserts.append((
                    record_index,
                    str(source_record["source_label"]),
                    int(source_record["source_line"]),
                    int(source_record["file_offset"]),
                    str(source_record["expression"]),
                    coordinate_word,
                    coordinate_word,
                    value_byte,
                    value_byte,
                    str(semantic["consumer_class"]),
                    str(semantic["consumer_operation"]),
                    semantic["selector_byte_offset"],
                    semantic["replacement_table_index"],
                    semantic["replacement_word_value"],
                    semantic["replacement_word_comment"],
                    semantic["special_case"],
                ))
            connection.executemany(
                """INSERT INTO overworld_hidden_item_record (
                       record_index, source_label, source_line, source_file_offset,
                       source_expression, source_coordinate_word, coordinate_word,
                       source_value_byte, value_byte, consumer_class, consumer_operation,
                       selector_byte_offset, replacement_table_index,
                       replacement_word_value, replacement_word_comment, special_case
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                record_inserts,
            )

            area_record_inserts = [
                (int(area["area_index"]), ordinal, int(record_index))
                for area in layout["area_lists"]
                for ordinal, record_index in enumerate(area["record_indices"])
            ]
            connection.executemany(
                """INSERT INTO overworld_hidden_item_area_record (
                       area_index, ordinal, record_index
                   ) VALUES (?, ?, ?)""",
                area_record_inserts,
            )

            connection.executemany(
                """INSERT INTO overworld_hidden_item_replacement_word (
                       table_index, source_line, file_offset, selector_byte_offset,
                       expression, value, comment
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        int(word["table_index"]),
                        int(word["source_line"]),
                        int(word["file_offset"]),
                        int(word["selector_byte_offset"]),
                        str(word["expression"]),
                        int(word["value"]),
                        str(word["comment"]),
                    )
                    for word in semantics["replacement_words"]
                ],
            )
        export_project(db_path)
    except sqlite3.Error as exc:
        raise ValueError(f"could not store overworld hidden-item model: {exc}") from exc
    finally:
        connection.close()

    model = get_overworld_hidden_item_model(db_path)
    if model is None:
        raise ValueError("overworld hidden-item model import did not persist")
    return model


def get_overworld_hidden_item_model(
    database_path: str | Path,
) -> dict[str, Any] | None:
    """Return the project-local hidden-item model, including edit/source comparison."""
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(read_only_uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        return _export_overworld_hidden_items(connection)
    finally:
        connection.close()


def update_overworld_hidden_item(
    database_path: str | Path,
    record_index: int,
    *,
    coordinate_word: int | None = None,
    value_byte: int | None = None,
) -> dict[str, Any]:
    """Update one semantic hidden-item record without touching source baselines or ROM bytes."""
    if isinstance(record_index, bool) or not isinstance(record_index, int) or not 0 <= record_index <= 350:
        raise ValueError("record_index must be an integer in 0..350")
    if coordinate_word is None and value_byte is None:
        raise ValueError("supply coordinate_word, value_byte, or both")
    if coordinate_word is not None and (
        isinstance(coordinate_word, bool)
        or not isinstance(coordinate_word, int)
        or not 0 <= coordinate_word <= 0xFFFE
    ):
        raise ValueError("coordinate_word must be an integer in 0..65534; $FFFF is reserved as the list sentinel")
    if value_byte is not None and (
        isinstance(value_byte, bool)
        or not isinstance(value_byte, int)
        or not 0 <= value_byte <= 0xFF
    ):
        raise ValueError("value_byte must be an integer in 0..255")

    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _require_current_schema(connection)
        existing = connection.execute(
            """SELECT coordinate_word, value_byte
               FROM overworld_hidden_item_record WHERE record_index = ?""",
            (record_index,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"overworld hidden-item record not found: {record_index}")

        new_coordinate = int(existing["coordinate_word"]) if coordinate_word is None else coordinate_word
        new_value = int(existing["value_byte"]) if value_byte is None else value_byte
        replacements = [
            {
                "table_index": int(row["table_index"]),
                "selector_byte_offset": int(row["selector_byte_offset"]),
                "value": int(row["value"]),
                "comment": str(row["comment"]),
            }
            for row in connection.execute(
                """SELECT table_index, selector_byte_offset, value, comment
                   FROM overworld_hidden_item_replacement_word ORDER BY table_index"""
            ).fetchall()
        ]
        semantics = classify_overworld_hidden_item_value_byte(new_value, replacements)
        with connection:
            connection.execute(
                """UPDATE overworld_hidden_item_record
                   SET coordinate_word = ?, value_byte = ?, consumer_class = ?,
                       consumer_operation = ?, selector_byte_offset = ?,
                       replacement_table_index = ?, replacement_word_value = ?,
                       replacement_word_comment = ?, special_case = ?
                   WHERE record_index = ?""",
                (
                    new_coordinate,
                    new_value,
                    semantics["consumer_class"],
                    semantics["consumer_operation"],
                    semantics["selector_byte_offset"],
                    semantics["replacement_table_index"],
                    semantics["replacement_word_value"],
                    semantics["replacement_word_comment"],
                    semantics["special_case"],
                    record_index,
                ),
            )
        export_project(db_path)
    except sqlite3.Error as exc:
        raise ValueError(f"could not update overworld hidden-item record: {exc}") from exc
    finally:
        connection.close()

    model = get_overworld_hidden_item_model(db_path)
    if model is None:
        raise ValueError("no overworld hidden-item model has been imported")
    for record in model["records"]:
        if record["record_index"] == record_index:
            return cast(dict[str, Any], record)
    raise KeyError(f"overworld hidden-item record not found: {record_index}")


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
        required_tables = {
            "project",
            "schema_version",
            "source_asset",
            *_OVERWORLD_TABLE_NAMES,
        }
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
