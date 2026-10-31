"""SQLite project metadata, semantic game records, migrations, and JSON export.

Schema v5 stores source-preserving overworld hidden-item and dungeon-chest
models plus project-authored hidden-item additions. ROM writing and broad
game-system coverage remain future work.
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
PROJECT_FORMAT_VERSION = 5
CURRENT_SCHEMA_VERSION = 5
DUNGEON_CHEST_SCHEMA_VERSION = 4
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


_DUNGEON_CHEST_SCHEMA_SQL = """
CREATE TABLE dungeon_chest_model (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    source_file TEXT NOT NULL CHECK (length(source_file) > 0),
    source_revision TEXT NOT NULL CHECK (length(source_revision) = 40),
    source_sha256 TEXT NOT NULL CHECK (
        length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    imported_at TEXT NOT NULL CHECK (length(imported_at) > 0),
    table_label TEXT NOT NULL CHECK (table_label = 'Dungeon_ChestData'),
    source_range_annotation TEXT NOT NULL CHECK (length(source_range_annotation) > 0),
    source_annotated_start_offset INTEGER NOT NULL CHECK (source_annotated_start_offset >= 0),
    source_annotated_end_offset INTEGER NOT NULL CHECK (
        source_annotated_end_offset >= source_annotated_start_offset
    ),
    table_size_bytes INTEGER NOT NULL CHECK (table_size_bytes = 504),
    entry_width_bytes INTEGER NOT NULL CHECK (entry_width_bytes = 3),
    entry_count INTEGER NOT NULL CHECK (entry_count = 168)
);

CREATE TABLE dungeon_chest_record (
    table_index INTEGER PRIMARY KEY CHECK (table_index BETWEEN 0 AND 167),
    candidate_entry_offset INTEGER NOT NULL CHECK (candidate_entry_offset >= 0),
    source_line INTEGER NOT NULL CHECK (source_line > 0),
    source_expression TEXT NOT NULL CHECK (length(source_expression) = 7),
    source_literal_value INTEGER NOT NULL CHECK (source_literal_value BETWEEN 0 AND 16777215),
    literal_value INTEGER NOT NULL CHECK (literal_value BETWEEN 0 AND 16777215),
    source_item_value INTEGER NOT NULL CHECK (source_item_value BETWEEN 0 AND 255),
    item_value INTEGER NOT NULL CHECK (item_value BETWEEN 0 AND 255),
    source_room_value INTEGER NOT NULL CHECK (source_room_value BETWEEN 0 AND 32767),
    room_value INTEGER NOT NULL CHECK (room_value BETWEEN 0 AND 32767),
    source_is_big_chest INTEGER NOT NULL CHECK (source_is_big_chest IN (0, 1)),
    is_big_chest INTEGER NOT NULL CHECK (is_big_chest IN (0, 1)),
    source_revision TEXT NOT NULL CHECK (length(source_revision) = 40),
    CHECK (source_literal_value =
        (source_item_value << 16) |
        (source_room_value) |
        (source_is_big_chest << 15)
    ),
    CHECK (literal_value =
        (item_value << 16) |
        (room_value) |
        (is_big_chest << 15)
    )
);
"""
_DUNGEON_CHEST_TABLE_NAMES = {
    "dungeon_chest_model",
    "dungeon_chest_record",
}

_OVERWORLD_CUSTOM_SCHEMA_SQL = """
CREATE TABLE overworld_hidden_item_custom_record (
    custom_record_id INTEGER PRIMARY KEY AUTOINCREMENT CHECK (custom_record_id > 0),
    coordinate_word INTEGER NOT NULL CHECK (coordinate_word BETWEEN 0 AND 65534),
    value_byte INTEGER NOT NULL CHECK (value_byte BETWEEN 0 AND 255),
    created_at TEXT NOT NULL CHECK (length(created_at) > 0)
);

CREATE TABLE overworld_hidden_item_custom_area_record (
    area_index INTEGER NOT NULL REFERENCES overworld_hidden_item_area(area_index)
        ON DELETE CASCADE,
    custom_record_id INTEGER NOT NULL
        REFERENCES overworld_hidden_item_custom_record(custom_record_id)
        ON DELETE CASCADE,
    PRIMARY KEY (area_index, custom_record_id)
);
"""
_OVERWORLD_CUSTOM_TABLE_NAMES = {
    "overworld_hidden_item_custom_record",
    "overworld_hidden_item_custom_area_record",
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
""" + _SOURCE_ASSET_TABLE_SQL + _OVERWORLD_SCHEMA_SQL + _DUNGEON_CHEST_SCHEMA_SQL + _OVERWORLD_CUSTOM_SCHEMA_SQL


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
    required_tables = (
        {"schema_version", "source_asset"}
        | _OVERWORLD_TABLE_NAMES
        | _DUNGEON_CHEST_TABLE_NAMES
        | _OVERWORLD_CUSTOM_TABLE_NAMES
    )
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise ValueError(
            "project schema v5 is required; run 'zelda-suite migrate-project' first "
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
            "overworld_hidden_item_custom_record",
            "overworld_hidden_item_custom_area_record",
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

    custom_relations = connection.execute(
        """SELECT area_index, custom_record_id
           FROM overworld_hidden_item_custom_area_record
           ORDER BY area_index, custom_record_id"""
    ).fetchall()
    custom_area_records: dict[int, list[int]] = {}
    custom_record_areas: dict[int, list[int]] = {}
    for relation in custom_relations:
        area_index = int(relation["area_index"])
        custom_record_id = int(relation["custom_record_id"])
        custom_area_records.setdefault(area_index, []).append(custom_record_id)
        custom_record_areas.setdefault(custom_record_id, []).append(area_index)

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
            "custom_record_ids": custom_area_records.get(area_index, []),
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

    custom_records: list[dict[str, Any]] = []
    custom_rows = connection.execute(
        """SELECT custom_record_id, coordinate_word, value_byte, created_at
           FROM overworld_hidden_item_custom_record ORDER BY custom_record_id"""
    ).fetchall()
    custom_class_counts = {
        "zero_value": 0,
        "ordinary_secret_mask": 0,
        "extended_secret_selector": 0,
    }
    for row in custom_rows:
        custom_record_id = int(row["custom_record_id"])
        coordinate = int(row["coordinate_word"])
        value = int(row["value_byte"])
        semantics = classify_overworld_hidden_item_value_byte(value, replacement_words)
        custom_class_counts[str(semantics["consumer_class"])] += 1
        custom_records.append({
            "custom_record_id": custom_record_id,
            "record_kind": "project_authored",
            "source_record_index": None,
            "area_indices": custom_record_areas.get(custom_record_id, []),
            "coordinate_word": coordinate,
            "coordinate_word_hex": "$" + format(coordinate, "04X"),
            "value_byte": value,
            "value_hex": "$" + format(value, "02X"),
            "consumer_class": semantics["consumer_class"],
            "consumer_operation": semantics["consumer_operation"],
            "selector_byte_offset": semantics["selector_byte_offset"],
            "replacement_table_index": semantics["replacement_table_index"],
            "replacement_word_value": semantics["replacement_word_value"],
            "replacement_word_comment": semantics["replacement_word_comment"],
            "special_case": semantics["special_case"],
            "canonical_item_id": None,
            "canonical_item_id_resolved": False,
            "created_at": str(row["created_at"]),
        })

    return {
        "format": "zelda-suite-overworld-hidden-item-model",
        "format_version": 2,
        "source_file": str(model["source_file"]),
        "source_revision": str(model["source_revision"]),
        "source_sha256": str(model["source_sha256"]),
        "imported_at": str(model["imported_at"]),
        "consumer_label": str(model["consumer_label"]),
        "replacement_table_label": str(model["replacement_table_label"]),
        "areas": areas,
        "records": records,
        "custom_records": custom_records,
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
            "custom_record_count": len(custom_records),
            "custom_area_record_reference_count": len(custom_relations),
            "custom_zero_value_count": custom_class_counts["zero_value"],
            "custom_ordinary_secret_mask_count": custom_class_counts["ordinary_secret_mask"],
            "custom_extended_secret_selector_count": custom_class_counts["extended_secret_selector"],
        },
        "evidence": {
            "source_layout_parsed": True,
            "source_consumer_patterns_checked": True,
            "rom_bytes_read": False,
            "rom_modified": False,
            "canonical_item_ids_resolved": False,
        },
    }



def _export_dungeon_chests(
    connection: sqlite3.Connection,
) -> dict[str, Any] | None:
    """Validate and serialize the editable raw-field model for Dungeon_ChestData."""
    model = connection.execute(
        """SELECT source_file, source_revision, source_sha256, imported_at,
                  table_label, source_range_annotation, source_annotated_start_offset,
                  source_annotated_end_offset, table_size_bytes, entry_width_bytes,
                  entry_count
           FROM dungeon_chest_model WHERE singleton = 1"""
    ).fetchone()
    row_count = int(
        connection.execute("SELECT COUNT(*) FROM dungeon_chest_record").fetchone()[0]
    )
    if model is None:
        if row_count:
            raise ValueError("dungeon chest records exist without model provenance metadata")
        return None

    if row_count != 168 or int(model["entry_count"]) != 168:
        raise ValueError("dungeon chest model must contain 168 records")
    if int(model["entry_width_bytes"]) != 3 or int(model["table_size_bytes"]) != 504:
        raise ValueError("dungeon chest model has inconsistent packed-entry dimensions")

    rows = connection.execute(
        """SELECT table_index, candidate_entry_offset, source_line, source_expression,
                  source_literal_value, literal_value, source_item_value, item_value,
                  source_room_value, room_value, source_is_big_chest, is_big_chest,
                  source_revision
           FROM dungeon_chest_record ORDER BY table_index"""
    ).fetchall()
    if [int(row["table_index"]) for row in rows] != list(range(168)):
        raise ValueError("dungeon chest record indexes must cover 0..167")

    entries: list[dict[str, Any]] = []
    source_entries: list[dict[str, Any]] = []
    room_values: set[int] = set()
    item_values: set[int] = set()
    big_chest_count = 0
    modified_count = 0
    for row in rows:
        table_index = int(row["table_index"])
        source_item = int(row["source_item_value"])
        source_room = int(row["source_room_value"])
        source_big = bool(row["source_is_big_chest"])
        item = int(row["item_value"])
        room = int(row["room_value"])
        big = bool(row["is_big_chest"])
        source_packed = (source_item << 16) | source_room | (int(source_big) << 15)
        packed = (item << 16) | room | (int(big) << 15)
        if int(row["source_literal_value"]) != source_packed:
            raise ValueError(
                f"dungeon chest {table_index} has inconsistent source packed fields"
            )
        source_entries.append({
            "table_index": table_index,
            "candidate_entry_offset": int(row["candidate_entry_offset"]),
            "source_line": int(row["source_line"]),
            "expression": str(row["source_expression"]),
            "literal_value": int(row["source_literal_value"]),
            "item_value": source_item,
            "room_value": source_room,
            "is_big_chest": source_big,
            "source_revision": str(row["source_revision"]),
        })
        if int(row["literal_value"]) != packed:
            raise ValueError(
                f"dungeon chest {table_index} has inconsistent edited packed fields"
            )
        is_modified = (
            item != source_item or room != source_room or big != source_big
        )
        if is_modified:
            modified_count += 1
        room_values.add(room)
        item_values.add(item)
        big_chest_count += int(big)
        entries.append({
            "table_index": table_index,
            "candidate_entry_offset": int(row["candidate_entry_offset"]),
            "source_line": int(row["source_line"]),
            "source_revision": str(row["source_revision"]),
            "source_expression": str(row["source_expression"]),
            "source_literal_value": int(row["source_literal_value"]),
            "source_literal_hex": "$" + format(int(row["source_literal_value"]), "06X"),
            "literal_value": packed,
            "literal_hex": "$" + format(packed, "06X"),
            "expression": "$" + format(packed, "06X"),
            "source_item_value": source_item,
            "item_value": item,
            "source_room_value": source_room,
            "room_value": room,
            "room_pointer_index": room,
            "room_pointer_table_byte_displacement": room * 3,
            "source_is_big_chest": source_big,
            "is_big_chest": big,
            "is_modified": is_modified,
        })

    source_payload = {
        "format": "zelda-suite-dungeon-chest-data",
        "format_version": 1,
        "source_file": str(model["source_file"]),
        "source_revision": str(model["source_revision"]),
        "table_label": str(model["table_label"]),
        "source_range_annotation": str(model["source_range_annotation"]),
        "source_annotated_start_offset": int(model["source_annotated_start_offset"]),
        "source_annotated_end_offset": int(model["source_annotated_end_offset"]),
        "table_size_bytes": int(model["table_size_bytes"]),
        "entry_width_bytes": int(model["entry_width_bytes"]),
        "entry_count": int(model["entry_count"]),
        "entries": source_entries,
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "source_range_offsets_verified": False,
            "item_value_names_resolved": False,
            "room_values_verified_against_rom": False,
        },
    }
    source_payload_hash = hashlib.sha256(_render_json(source_payload).encode("utf-8")).hexdigest()
    if source_payload_hash != str(model["source_sha256"]):
        raise ValueError("dungeon chest source fields no longer match their import SHA-256 digest")

    return {
        "format": "zelda-suite-dungeon-chest-model",
        "format_version": 1,
        "source_file": str(model["source_file"]),
        "source_revision": str(model["source_revision"]),
        "source_sha256": str(model["source_sha256"]),
        "imported_at": str(model["imported_at"]),
        "table_label": str(model["table_label"]),
        "source_range_annotation": str(model["source_range_annotation"]),
        "source_annotated_start_offset": int(model["source_annotated_start_offset"]),
        "source_annotated_end_offset": int(model["source_annotated_end_offset"]),
        "table_size_bytes": int(model["table_size_bytes"]),
        "entry_width_bytes": int(model["entry_width_bytes"]),
        "entry_count": int(model["entry_count"]),
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "distinct_room_value_count": len(room_values),
            "distinct_item_value_count": len(item_values),
            "big_chest_count": big_chest_count,
            "modified_record_count": modified_count,
        },
        "evidence": {
            "source_revision_pinned": True,
            "packed_fields_recomposed": True,
            "source_range_offsets_verified": False,
            "item_value_names_resolved": False,
            "room_values_verified_against_rom": False,
            "rom_bytes_read": False,
            "rom_modified": False,
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
    required_tables = (
        {"source_asset"}
        | _OVERWORLD_TABLE_NAMES
        | _DUNGEON_CHEST_TABLE_NAMES
        | _OVERWORLD_CUSTOM_TABLE_NAMES
    )
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise ValueError(
            "project schema v5 is required; run 'zelda-suite migrate-project' first "
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
        "dungeon_chests": _export_dungeon_chests(connection),
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


def _validate_expected_project_revision(expected_project_revision: str | None) -> None:
    """Validate an optional SHA-256 fingerprint supplied by an approved preview."""
    if expected_project_revision is None:
        return
    if (
        not isinstance(expected_project_revision, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_project_revision) is None
    ):
        raise ValueError("expected_project_revision must be a lowercase SHA-256 hex digest")


def _calculate_project_revision(connection: sqlite3.Connection) -> str:
    """Fingerprint the complete canonical project state from the current SQLite snapshot."""
    canonical_payload = _render_json(_export_payload(connection)).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


def _require_matching_project_revision(
    expected_project_revision: str | None,
    current_project_revision: str,
) -> None:
    """Reject an apply when any canonical project content changed after its preview."""
    if (
        expected_project_revision is not None
        and expected_project_revision != current_project_revision
    ):
        raise ValueError(
            "project revision changed since preview; create a fresh preview before applying"
        )


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
                    [(version, created_at) for version in range(1, CURRENT_SCHEMA_VERSION + 1)],
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
    database_path: str | Path,
    json_path: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> bool:
    """Migrate a project, or validate the complete upgrade on a temporary copy.

    Returns True when an upgrade is needed and was applied (or would be applied
    in dry-run mode), or False when the database is already current. A dry run
    executes the same migration steps against a disposable SQLite backup and
    never changes the original database or JSON sidecar.
    """
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    temporary_directory: Any = None
    connection: sqlite3.Connection | None = None
    migrated = False
    try:
        if dry_run:
            temporary_directory = tempfile.TemporaryDirectory(
                prefix="zelda-suite-migration-preview-"
            )
            preview_path = Path(temporary_directory.name) / "project-preview.sqlite3"
            source_connection = sqlite3.connect(
                db_path.resolve().as_uri() + "?mode=ro", uri=True
            )
            try:
                connection = sqlite3.connect(preview_path)
                source_connection.backup(connection)
            finally:
                source_connection.close()
        else:
            connection = sqlite3.connect(db_path)
        assert connection is not None
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
            if tables & (
                _OVERWORLD_TABLE_NAMES
                | _DUNGEON_CHEST_TABLE_NAMES
                | _OVERWORLD_CUSTOM_TABLE_NAMES
            ):
                raise ValueError(
                    "schema-v1 project unexpectedly contains newer semantic-model tables; "
                    "refusing an ambiguous partial migration"
                )
            connection.execute("BEGIN IMMEDIATE")
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
            if (
                existing_overworld_tables
                or tables & _DUNGEON_CHEST_TABLE_NAMES
                or tables & _OVERWORLD_CUSTOM_TABLE_NAMES
            ):
                raise ValueError(
                    "schema-v2 project unexpectedly contains newer semantic-model tables; "
                    "refusing an ambiguous partial migration"
                )
            connection.execute("BEGIN IMMEDIATE")
            with connection:
                for statement in _OVERWORLD_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "UPDATE project SET format_version = 3 WHERE singleton = 1"
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (3, _utc_timestamp()),
                )
            tables.update(_OVERWORLD_TABLE_NAMES)
            current = 3
            migrated = True

        if current == 3:
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != 3:
                raise ValueError("schema-v3 project metadata is inconsistent")
            if "source_asset" not in tables or not _OVERWORLD_TABLE_NAMES.issubset(tables):
                raise ValueError("schema-v3 project is missing its source-asset or overworld tables")
            existing_v4_or_custom_tables = tables & (
                _DUNGEON_CHEST_TABLE_NAMES | _OVERWORLD_CUSTOM_TABLE_NAMES
            )
            if existing_v4_or_custom_tables:
                raise ValueError(
                    "schema-v3 project unexpectedly contains newer semantic-model tables; "
                    "refusing an ambiguous partial migration"
                )
            connection.execute("BEGIN IMMEDIATE")
            with connection:
                for statement in _DUNGEON_CHEST_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "UPDATE project SET format_version = ? WHERE singleton = 1",
                    (DUNGEON_CHEST_SCHEMA_VERSION,),
                )
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (DUNGEON_CHEST_SCHEMA_VERSION, _utc_timestamp()),
                )
            tables.update(_DUNGEON_CHEST_TABLE_NAMES)
            current = DUNGEON_CHEST_SCHEMA_VERSION
            migrated = True

        if current == DUNGEON_CHEST_SCHEMA_VERSION:
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != DUNGEON_CHEST_SCHEMA_VERSION:
                raise ValueError("schema-v4 project metadata is inconsistent")
            required_v4_tables = (
                {"source_asset"} | _OVERWORLD_TABLE_NAMES | _DUNGEON_CHEST_TABLE_NAMES
            )
            if not required_v4_tables.issubset(tables):
                raise ValueError("schema-v4 project is missing required source-asset or semantic-model tables")
            existing_custom_tables = tables & _OVERWORLD_CUSTOM_TABLE_NAMES
            if existing_custom_tables:
                raise ValueError(
                    "schema-v4 project unexpectedly contains custom hidden-item tables; "
                    "refusing an ambiguous partial migration"
                )
            connection.execute("BEGIN IMMEDIATE")
            with connection:
                for statement in _OVERWORLD_CUSTOM_SCHEMA_SQL.split(";"):
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
            tables.update(_OVERWORLD_CUSTOM_TABLE_NAMES)
            current = CURRENT_SCHEMA_VERSION
            migrated = True

        if current == CURRENT_SCHEMA_VERSION:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            required_tables = (
        {"source_asset"}
        | _OVERWORLD_TABLE_NAMES
        | _DUNGEON_CHEST_TABLE_NAMES
        | _OVERWORLD_CUSTOM_TABLE_NAMES
    )
            missing_tables = sorted(required_tables - tables)
            if missing_tables:
                raise ValueError(
                    "schema-v5 project is missing required table(s): "
                    + ", ".join(missing_tables)
                )
            project_row = connection.execute(
                "SELECT format_version FROM project WHERE singleton = 1"
            ).fetchone()
            if project_row is None or project_row[0] != PROJECT_FORMAT_VERSION:
                raise ValueError("schema-v5 project metadata is inconsistent")


    except sqlite3.Error as exc:
        raise ValueError(f"could not migrate project database: {exc}") from exc
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            if temporary_directory is not None:
                temporary_directory.cleanup()

    # A dry run validates every transition on the disposable copy and never
    # refreshes or otherwise touches the caller's JSON sidecar.
    if not dry_run:
        # Refreshing the JSON sidecar is explicit, even when the DB is current.
        export_project(db_path, json_path)
    return migrated


def _persist_source_asset_payload(
    database_path: str | Path,
    asset_key: str,
    payload: dict[str, Any],
    *,
    replace_existing: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate and optionally preview or persist a source-export payload."""
    _validate_asset_key(asset_key)
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a bool")
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

    if dry_run:
        read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(read_only_uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            _require_current_schema(connection)
            existing = connection.execute(
                "SELECT 1 FROM source_asset WHERE asset_key = ?", (asset_key,)
            ).fetchone()
            if existing is not None and not replace_existing:
                raise ValueError(
                    f"source asset key already exists: {asset_key}; use "
                    "replace_existing=True or the CLI --replace option to replace it"
                )
            before = (
                _select_source_asset(connection, asset_key)
                if existing is not None
                else None
            )
        except sqlite3.Error as exc:
            raise ValueError(
                f"could not inspect source asset {asset_key!r}: {exc}"
            ) from exc
        finally:
            connection.close()

        before_summary = (
            None
            if before is None
            else {key: value for key, value in before.items() if key != "payload"}
        )
        proposed = {
            "key": asset_key,
            "format": payload["format"],
            "format_version": payload["format_version"],
            "source_file": _source_file_metadata(payload),
            "source_revision": payload["source_revision"],
            "sha256": payload_hash,
        }
        return {
            "action": "import_source_asset",
            "dry_run": True,
            "key": asset_key,
            "replacing": before is not None,
            "before": before_summary,
            "proposed": proposed,
            "database_modified": False,
            "json_modified": False,
            "rom_modified": False,
        }

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
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import or preview a validated source-export JSON file."""
    try:
        payload = load_source_export(source_export_path)
    except AssetLoadError as exc:
        raise ValueError(f"could not load source export: {exc}") from exc
    return _persist_source_asset_payload(
        database_path,
        asset_key,
        payload,
        replace_existing=replace_existing,
        dry_run=dry_run,
    )


def import_extracted_asset(
    database_path: str | Path,
    asset_name: str,
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_key: str | None = None,
    replace_existing: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import or preview a committed manifest asset after registry/provenance checks.

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
        dry_run=dry_run,
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
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or import the pinned hidden-item source model.

    The default is a read-only preview. Applying an import stores source values
    as immutable baselines and initializes editable fields from those values.
    Re-import with replace_existing=True resets imported edits but preserves
    project-authored custom records and their area links. No ROM is accessed.
    """
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
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

    connection_target = (
        db_path.resolve().as_uri() + "?mode=ro" if dry_run else str(db_path)
    )
    connection = sqlite3.connect(connection_target, uri=dry_run)
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
                for table in sorted(
                    (_OVERWORLD_TABLE_NAMES | _OVERWORLD_CUSTOM_TABLE_NAMES)
                    - {"overworld_hidden_item_model"}
                )
            ]
            if any(counts):
                raise ValueError("overworld hidden-item tables contain partial data without model metadata")

        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        custom_memberships = (
            connection.execute(
                """SELECT area_index, custom_record_id
                   FROM overworld_hidden_item_custom_area_record
                   ORDER BY area_index, custom_record_id"""
            ).fetchall()
            if existing is not None
            else []
        )
        if dry_run:
            before_model = (
                _export_overworld_hidden_items(connection)
                if existing is not None
                else None
            )
            custom_record_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM overworld_hidden_item_custom_record"
                ).fetchone()[0]
            )
            return {
                "action": "import_overworld_hidden_item_model",
                "dry_run": True,
                "replace_existing": replace_existing,
                "before": None if before_model is None else {
                    "source_file": before_model["source_file"],
                    "source_revision": before_model["source_revision"],
                    "source_sha256": before_model["source_sha256"],
                    "summary": before_model["summary"],
                },
                "proposed": {
                    "source_file": str(semantics["source_file"]),
                    "source_revision": str(semantics["source_revision"]),
                    "source_sha256": source_sha256,
                    "summary": {
                        "area_count": len(layout["area_lists"]),
                        "record_count": len(layout["records"]),
                        "replacement_word_count": len(semantics["replacement_words"]),
                        "modified_record_count": 0,
                        "custom_record_count": custom_record_count,
                        "custom_area_link_count": len(custom_memberships),
                    },
                },
                "rom_modified": False,
            }
        imported_at = _utc_timestamp()
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
            if custom_memberships:
                connection.executemany(
                    """INSERT INTO overworld_hidden_item_custom_area_record (
                           area_index, custom_record_id
                       ) VALUES (?, ?)""",
                    [
                        (int(row["area_index"]), int(row["custom_record_id"]))
                        for row in custom_memberships
                    ],
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
    expected_project_revision: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or update one imported hidden-item row without touching its source baseline.

    The default is read-only. Applying an edit updates the current project values
    and derived consumer classification, while source fields and area aliases
    remain unchanged. When supplied, expected_project_revision is checked against
    the canonical project snapshot held by the write transaction. No ROM bytes
    are read or written.
    """
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
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    _validate_expected_project_revision(expected_project_revision)

    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = (
        sqlite3.connect(read_only_uri, uri=True)
        if dry_run
        else sqlite3.connect(db_path)
    )
    connection.row_factory = sqlite3.Row
    changed_fields: list[str] = []
    before: dict[str, Any]
    try:
        if dry_run:
            connection.execute("BEGIN")
        else:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
        _require_current_schema(connection)
        project_revision = _calculate_project_revision(connection)
        _require_matching_project_revision(
            expected_project_revision, project_revision
        )
        model = _export_overworld_hidden_items(connection)
        if model is None:
            raise ValueError("no overworld hidden-item model has been imported")
        before_record = next(
            (
                record for record in model["records"]
                if record["record_index"] == record_index
            ),
            None,
        )
        if before_record is None:
            raise KeyError(f"overworld hidden-item record not found: {record_index}")
        before = dict(before_record)
        source_references = _imported_overworld_record_source_references(
            connection, model, before_record
        )

        new_coordinate = (
            int(before_record["coordinate_word"])
            if coordinate_word is None
            else coordinate_word
        )
        new_value = (
            int(before_record["value_byte"])
            if value_byte is None
            else value_byte
        )
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
        proposed = dict(before)
        proposed.update({
            "coordinate_word": new_coordinate,
            "value_byte": new_value,
            "consumer_class": semantics["consumer_class"],
            "consumer_operation": semantics["consumer_operation"],
            "selector_byte_offset": semantics["selector_byte_offset"],
            "replacement_table_index": semantics["replacement_table_index"],
            "replacement_word_value": semantics["replacement_word_value"],
            "replacement_word_comment": semantics["replacement_word_comment"],
            "special_case": semantics["special_case"],
            "is_modified": (
                new_coordinate != before["source_coordinate_word"]
                or new_value != before["source_value_byte"]
            ),
        })
        if new_coordinate != before["coordinate_word"]:
            changed_fields.append("coordinate_word")
        if new_value != before["value_byte"]:
            changed_fields.append("value_byte")

        if dry_run:
            return {
                "action": "update_overworld_hidden_item",
                "dry_run": True,
                "project_revision": project_revision,
                "record_index": record_index,
                "before": before,
                "proposed": proposed,
                "source_references": source_references,
                "changed_fields": changed_fields,
                "rom_modified": False,
            }

        if changed_fields:
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
    except sqlite3.Error as exc:
        raise ValueError(f"could not update overworld hidden-item record: {exc}") from exc
    finally:
        connection.close()

    if changed_fields:
        export_project(db_path)
    updated_model = get_overworld_hidden_item_model(db_path)
    if updated_model is None:
        raise ValueError("no overworld hidden-item model has been imported")
    for record in updated_model["records"]:
        if record["record_index"] == record_index:
            return cast(
                dict[str, Any],
                {**record, "source_references": source_references},
            )
    raise KeyError(f"overworld hidden-item record not found: {record_index}")


def _validated_custom_hidden_item_fields(
    coordinate_word: int,
    value_byte: int,
    area_indices: list[int] | tuple[int, ...],
) -> list[int]:
    if (
        isinstance(coordinate_word, bool)
        or not isinstance(coordinate_word, int)
        or not 0 <= coordinate_word <= 0xFFFE
    ):
        raise ValueError(
            "coordinate_word must be an integer in 0..65534; $FFFF is reserved as the list sentinel"
        )
    if (
        isinstance(value_byte, bool)
        or not isinstance(value_byte, int)
        or not 0 <= value_byte <= 0xFF
    ):
        raise ValueError("value_byte must be an integer in 0..255")
    if not isinstance(area_indices, (list, tuple)) or not area_indices:
        raise ValueError("area_indices must contain at least one area index")
    validated: list[int] = []
    for area_index in area_indices:
        if (
            isinstance(area_index, bool)
            or not isinstance(area_index, int)
            or not 0 <= area_index <= 127
        ):
            raise ValueError("area indexes must be integers in 0..127")
        if area_index in validated:
            raise ValueError(f"duplicate area index: {area_index}")
        validated.append(area_index)
    return sorted(validated)


def _custom_hidden_item_replacement_words(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    return [
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


def _overworld_area_source_references(
    connection: sqlite3.Connection,
    area_indices: list[int],
) -> list[dict[str, Any]]:
    """Cite source-annotated pointer metadata for imported or custom area links."""
    if not area_indices:
        return []
    placeholders = ",".join("?" for _ in area_indices)
    model = connection.execute(
        """SELECT source_file, source_revision, source_sha256
           FROM overworld_hidden_item_model WHERE singleton = 1"""
    ).fetchone()
    if model is None:
        raise ValueError("overworld hidden-item model has no source provenance")
    rows = connection.execute(
        f"""SELECT area_index, pointer_entry_file_offset, target_label,
                   target_file_offset, sentinel_file_offset, record_count
            FROM overworld_hidden_item_area
            WHERE area_index IN ({placeholders})
            ORDER BY area_index""",
        area_indices,
    ).fetchall()
    if len(rows) != len(area_indices):
        raise ValueError("overworld area source references are incomplete")
    return [
        {
            "area_index": int(row["area_index"]),
            "source_file": str(model["source_file"]),
            "source_revision": str(model["source_revision"]),
            "source_sha256": str(model["source_sha256"]),
            "target_label": str(row["target_label"]),
            "pointer_entry_file_offset_annotation": int(
                row["pointer_entry_file_offset"]
            ),
            "target_file_offset_annotation": int(row["target_file_offset"]),
            "sentinel_file_offset_annotation": int(row["sentinel_file_offset"]),
            "source_record_count": int(row["record_count"]),
            "rom_offsets_verified": False,
            "rom_bytes_read": False,
        }
        for row in rows
    ]


def _imported_overworld_record_source_references(
    connection: sqlite3.Connection,
    model: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    """Cite the imported row and each source area pointer that references it."""
    area_references = _overworld_area_source_references(
        connection, [int(area) for area in record["area_indices"]]
    )
    return {
        "record": {
            "record_kind": "imported_overworld_hidden_item",
            "record_index": int(record["record_index"]),
            "source_file": str(model["source_file"]),
            "source_revision": str(model["source_revision"]),
            "source_sha256": str(model["source_sha256"]),
            "source_label": str(record["source_label"]),
            "source_line": int(record["source_line"]),
            "source_file_offset_annotation": int(record["source_file_offset"]),
            "source_expression": str(record["source_expression"]),
            "rom_offsets_verified": False,
            "rom_bytes_read": False,
        },
        "areas": area_references,
        "rom_offsets_verified": False,
        "rom_bytes_read": False,
    }


def _dungeon_chest_record_source_references(
    model: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    """Cite a packed chest row against its source table declaration and range."""
    return {
        "record": {
            "record_kind": "dungeon_chest_source_entry",
            "table_index": int(record["table_index"]),
            "source_file": str(model["source_file"]),
            "source_revision": str(model["source_revision"]),
            "source_sha256": str(model["source_sha256"]),
            "table_label": str(model["table_label"]),
            "source_range_annotation": model["source_range_annotation"],
            "source_annotated_start_offset": model["source_annotated_start_offset"],
            "source_annotated_end_offset": model["source_annotated_end_offset"],
            "source_line": int(record["source_line"]),
            "source_expression": str(record["expression"]),
            "candidate_entry_offset_annotation": int(record["candidate_entry_offset"]),
            "rom_offsets_verified": False,
            "rom_bytes_read": False,
        },
        "rom_offsets_verified": False,
        "rom_bytes_read": False,
    }


def create_custom_overworld_hidden_item(
    database_path: str | Path,
    *,
    area_indices: list[int] | tuple[int, ...],
    coordinate_word: int,
    value_byte: int,
    expected_project_revision: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or create a project-authored hidden item linked to one or more areas.

    The 351 imported source records and their source-area relationships are never
    changed. When supplied, expected_project_revision is checked before creation
    under the write transaction. A committed custom record is project-local and
    never writes a ROM.
    """
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    _validate_expected_project_revision(expected_project_revision)
    validated_areas = _validated_custom_hidden_item_fields(
        coordinate_word, value_byte, area_indices
    )
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = (
        sqlite3.connect(read_only_uri, uri=True)
        if dry_run
        else sqlite3.connect(db_path)
    )
    connection.row_factory = sqlite3.Row
    try:
        if dry_run:
            connection.execute("BEGIN")
        else:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
        _require_current_schema(connection)
        project_revision = _calculate_project_revision(connection)
        _require_matching_project_revision(
            expected_project_revision, project_revision
        )
        model_row = connection.execute(
            "SELECT 1 FROM overworld_hidden_item_model WHERE singleton = 1"
        ).fetchone()
        if model_row is None:
            raise ValueError("no overworld hidden-item model has been imported")
        placeholders = ",".join("?" for _ in validated_areas)
        existing_areas = {
            int(row["area_index"])
            for row in connection.execute(
                f"SELECT area_index FROM overworld_hidden_item_area "
                f"WHERE area_index IN ({placeholders})",
                validated_areas,
            ).fetchall()
        }
        missing = [area for area in validated_areas if area not in existing_areas]
        if missing:
            raise KeyError(f"overworld area not found: {missing[0]}")
        semantics = classify_overworld_hidden_item_value_byte(
            value_byte, _custom_hidden_item_replacement_words(connection)
        )
        area_source_references = _overworld_area_source_references(
            connection, validated_areas
        )
        if dry_run:
            return {
                "action": "create_custom_overworld_hidden_item",
                "dry_run": True,
                "project_revision": project_revision,
                "custom_record_id": None,
                "area_indices": validated_areas,
                "area_source_references": area_source_references,
                "coordinate_word": coordinate_word,
                "value_byte": value_byte,
                "consumer_class": semantics["consumer_class"],
                "consumer_operation": semantics["consumer_operation"],
                "selector_byte_offset": semantics["selector_byte_offset"],
                "replacement_table_index": semantics["replacement_table_index"],
                "replacement_word_value": semantics["replacement_word_value"],
                "replacement_word_comment": semantics["replacement_word_comment"],
                "source_record_index": None,
                "rom_modified": False,
            }
        with connection:
            cursor = connection.execute(
                """INSERT INTO overworld_hidden_item_custom_record (
                       coordinate_word, value_byte, created_at
                   ) VALUES (?, ?, ?)""",
                (coordinate_word, value_byte, _utc_timestamp()),
            )
            if cursor.lastrowid is None:
                raise ValueError("SQLite did not return a custom hidden-item ID")
            custom_record_id = cursor.lastrowid
            connection.executemany(
                """INSERT INTO overworld_hidden_item_custom_area_record (
                       area_index, custom_record_id
                   ) VALUES (?, ?)""",
                [(area, custom_record_id) for area in validated_areas],
            )
    except sqlite3.Error as exc:
        raise ValueError(f"could not create custom overworld hidden item: {exc}") from exc
    finally:
        connection.close()

    export_project(db_path)
    model = get_overworld_hidden_item_model(db_path)
    if model is None:
        raise ValueError("custom overworld hidden item was not persisted")
    result = next(
        (
            record for record in model["custom_records"]
            if record["custom_record_id"] == custom_record_id
        ),
        None,
    )
    if result is None:
        raise ValueError("custom overworld hidden item was not present in the project export")
    return {
        "action": "create_custom_overworld_hidden_item",
        "dry_run": False,
        "record": result,
        "area_source_references": area_source_references,
        "rom_modified": False,
    }


def update_custom_overworld_hidden_item(
    database_path: str | Path,
    custom_record_id: int,
    *,
    area_indices: list[int] | tuple[int, ...] | None = None,
    coordinate_word: int | None = None,
    value_byte: int | None = None,
    expected_project_revision: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or update only a project-authored hidden item.

    Omitted fields retain their current values. Supplying area_indices
    replaces the complete area-link set; at least one valid area must remain.
    Imported source records, their baselines, and their area links are never
    updated. A committed change affects only SQLite and canonical JSON. When
    supplied, expected_project_revision rejects persistence after any intervening
    canonical project edit.
    """
    if (
        isinstance(custom_record_id, bool)
        or not isinstance(custom_record_id, int)
        or custom_record_id < 1
    ):
        raise ValueError("custom_record_id must be a positive integer")
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    _validate_expected_project_revision(expected_project_revision)
    if area_indices is None and coordinate_word is None and value_byte is None:
        raise ValueError("supply area_indices, coordinate_word, or value_byte")

    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = (
        sqlite3.connect(read_only_uri, uri=True)
        if dry_run
        else sqlite3.connect(db_path)
    )
    connection.row_factory = sqlite3.Row
    changed_fields: list[str] = []
    before: dict[str, Any]
    try:
        if dry_run:
            connection.execute("BEGIN")
        else:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
        _require_current_schema(connection)
        project_revision = _calculate_project_revision(connection)
        _require_matching_project_revision(
            expected_project_revision, project_revision
        )
        row = connection.execute(
            """SELECT custom_record_id, coordinate_word, value_byte, created_at
               FROM overworld_hidden_item_custom_record
               WHERE custom_record_id = ?""",
            (custom_record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"custom overworld hidden item not found: {custom_record_id}")

        old_coordinate = int(row["coordinate_word"])
        old_value = int(row["value_byte"])
        created_at = str(row["created_at"])
        old_areas = [
            int(item["area_index"])
            for item in connection.execute(
                """SELECT area_index FROM overworld_hidden_item_custom_area_record
                   WHERE custom_record_id = ? ORDER BY area_index""",
                (custom_record_id,),
            ).fetchall()
        ]
        before_area_source_references = _overworld_area_source_references(
            connection, old_areas
        )
        new_coordinate = old_coordinate if coordinate_word is None else coordinate_word
        new_value = old_value if value_byte is None else value_byte
        requested_areas = old_areas if area_indices is None else area_indices
        new_areas = _validated_custom_hidden_item_fields(
            new_coordinate, new_value, requested_areas
        )

        placeholders = ",".join("?" for _ in new_areas)
        existing_areas = {
            int(item["area_index"])
            for item in connection.execute(
                f"SELECT area_index FROM overworld_hidden_item_area "
                f"WHERE area_index IN ({placeholders})",
                new_areas,
            ).fetchall()
        }
        missing_areas = [area for area in new_areas if area not in existing_areas]
        if missing_areas:
            raise KeyError(f"overworld area not found: {missing_areas[0]}")
        proposed_area_source_references = _overworld_area_source_references(
            connection, new_areas
        )

        replacement_words = _custom_hidden_item_replacement_words(connection)
        before_semantics = classify_overworld_hidden_item_value_byte(
            old_value, replacement_words
        )
        proposed_semantics = classify_overworld_hidden_item_value_byte(
            new_value, replacement_words
        )

        def snapshot(
            coordinate: int,
            value: int,
            areas: list[int],
            semantics: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "custom_record_id": custom_record_id,
                "record_kind": "project_authored",
                "source_record_index": None,
                "area_indices": areas,
                "coordinate_word": coordinate,
                "value_byte": value,
                "consumer_class": semantics["consumer_class"],
                "consumer_operation": semantics["consumer_operation"],
                "selector_byte_offset": semantics["selector_byte_offset"],
                "replacement_table_index": semantics["replacement_table_index"],
                "replacement_word_value": semantics["replacement_word_value"],
                "replacement_word_comment": semantics["replacement_word_comment"],
                "special_case": semantics["special_case"],
                "canonical_item_id": None,
                "canonical_item_id_resolved": False,
                "created_at": created_at,
            }

        before = snapshot(old_coordinate, old_value, old_areas, before_semantics)
        proposed = snapshot(new_coordinate, new_value, new_areas, proposed_semantics)
        if new_coordinate != old_coordinate:
            changed_fields.append("coordinate_word")
        if new_value != old_value:
            changed_fields.append("value_byte")
        if new_areas != old_areas:
            changed_fields.append("area_indices")

        if dry_run:
            return {
                "action": "update_custom_overworld_hidden_item",
                "dry_run": True,
                "project_revision": project_revision,
                "custom_record_id": custom_record_id,
                "before": before,
                "proposed": proposed,
                "before_area_source_references": before_area_source_references,
                "proposed_area_source_references": proposed_area_source_references,
                "changed_fields": changed_fields,
                "rom_modified": False,
            }

        if changed_fields:
            with connection:
                if new_coordinate != old_coordinate or new_value != old_value:
                    connection.execute(
                        """UPDATE overworld_hidden_item_custom_record
                           SET coordinate_word = ?, value_byte = ?
                           WHERE custom_record_id = ?""",
                        (new_coordinate, new_value, custom_record_id),
                    )
                if new_areas != old_areas:
                    connection.execute(
                        """DELETE FROM overworld_hidden_item_custom_area_record
                           WHERE custom_record_id = ?""",
                        (custom_record_id,),
                    )
                    connection.executemany(
                        """INSERT INTO overworld_hidden_item_custom_area_record (
                               area_index, custom_record_id
                           ) VALUES (?, ?)""",
                        [(area, custom_record_id) for area in new_areas],
                    )
    except sqlite3.Error as exc:
        raise ValueError(f"could not update custom overworld hidden item: {exc}") from exc
    finally:
        connection.close()

    if changed_fields:
        export_project(db_path)
    model = get_overworld_hidden_item_model(db_path)
    if model is None:
        raise ValueError("custom overworld hidden item model was not persisted")
    record = next(
        (
            item for item in model["custom_records"]
            if item["custom_record_id"] == custom_record_id
        ),
        None,
    )
    if record is None:
        raise ValueError("custom overworld hidden item was not present in the project export")
    return {
        "action": "update_custom_overworld_hidden_item",
        "dry_run": False,
        "record": record,
        "before": before,
        "before_area_source_references": before_area_source_references,
        "area_source_references": proposed_area_source_references,
        "changed_fields": changed_fields,
        "rom_modified": False,
    }


def delete_custom_overworld_hidden_item(
    database_path: str | Path,
    custom_record_id: int,
    *,
    expected_project_revision: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or delete only a project-authored record, never a source record.

    When supplied, expected_project_revision is checked inside the write
    transaction so a stale preview cannot delete a record after another project
    edit has occurred.
    """
    if (
        isinstance(custom_record_id, bool)
        or not isinstance(custom_record_id, int)
        or custom_record_id < 1
    ):
        raise ValueError("custom_record_id must be a positive integer")
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    _validate_expected_project_revision(expected_project_revision)
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = (
        sqlite3.connect(read_only_uri, uri=True)
        if dry_run
        else sqlite3.connect(db_path)
    )
    connection.row_factory = sqlite3.Row
    try:
        if dry_run:
            connection.execute("BEGIN")
        else:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
        _require_current_schema(connection)
        project_revision = _calculate_project_revision(connection)
        _require_matching_project_revision(
            expected_project_revision, project_revision
        )
        row = connection.execute(
            """SELECT custom_record_id, coordinate_word, value_byte, created_at
               FROM overworld_hidden_item_custom_record
               WHERE custom_record_id = ?""",
            (custom_record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"custom overworld hidden item not found: {custom_record_id}")
        area_indices = [
            int(item["area_index"])
            for item in connection.execute(
                """SELECT area_index FROM overworld_hidden_item_custom_area_record
                   WHERE custom_record_id = ? ORDER BY area_index""",
                (custom_record_id,),
            ).fetchall()
        ]
        area_source_references = _overworld_area_source_references(
            connection, area_indices
        )
        result = {
            "custom_record_id": int(row["custom_record_id"]),
            "area_indices": area_indices,
            "coordinate_word": int(row["coordinate_word"]),
            "value_byte": int(row["value_byte"]),
            "created_at": str(row["created_at"]),
            "source_record_index": None,
        }
        if dry_run:
            return {
                "action": "delete_custom_overworld_hidden_item",
                "dry_run": True,
                "project_revision": project_revision,
                "record": result,
                "area_source_references": area_source_references,
                "rom_modified": False,
            }
        with connection:
            connection.execute(
                "DELETE FROM overworld_hidden_item_custom_record WHERE custom_record_id = ?",
                (custom_record_id,),
            )
    except sqlite3.Error as exc:
        raise ValueError(f"could not delete custom overworld hidden item: {exc}") from exc
    finally:
        connection.close()

    export_project(db_path)
    return {
        "action": "delete_custom_overworld_hidden_item",
        "dry_run": False,
        "deleted": result,
        "area_source_references": area_source_references,
        "rom_modified": False,
    }

def import_dungeon_chest_data(
    database_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    replace_existing: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or import the registered packed chest inventory.

    The default is a read-only preview. Re-import requires explicit replacement,
    and applying that replacement resets project-local chest edits. Original
    source fields remain available as baselines; no ROM is accessed.
    """
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    try:
        payload = load_extracted_asset("dungeon-chest-data", registry_path)
    except (AssetLoadError, OSError) as exc:
        raise ValueError(f"could not load registered dungeon chest data: {exc}") from exc

    if payload.get("format") != "zelda-suite-dungeon-chest-data":
        raise ValueError("registered dungeon chest asset has an unsupported format")
    if payload.get("entry_count") != 168 or len(payload.get("entries", [])) != 168:
        raise ValueError("registered dungeon chest asset must contain 168 entries")
    if payload.get("entry_width_bytes") != 3 or payload.get("table_size_bytes") != 504:
        raise ValueError("registered dungeon chest asset has inconsistent entry dimensions")

    canonical_payload = _render_json(payload)
    payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    records = []
    for entry in payload["entries"]:
        literal_value = int(entry["literal_value"])
        item_value = int(entry["item_value"])
        room_value = int(entry["room_value"])
        big_chest = bool(entry["is_big_chest"])
        packed = (item_value << 16) | room_value | (int(big_chest) << 15)
        if packed != literal_value:
            raise ValueError(
                f"registered dungeon chest entry {entry['table_index']} has inconsistent fields"
            )
        records.append((
            int(entry["table_index"]),
            int(entry["candidate_entry_offset"]),
            int(entry["source_line"]),
            str(entry["expression"]),
            literal_value,
            literal_value,
            item_value,
            item_value,
            room_value,
            room_value,
            int(big_chest),
            int(big_chest),
            str(entry["source_revision"]),
        ))

    connection_target = (
        db_path.resolve().as_uri() + "?mode=ro" if dry_run else str(db_path)
    )
    connection = sqlite3.connect(connection_target, uri=dry_run)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        existing = connection.execute(
            "SELECT 1 FROM dungeon_chest_model WHERE singleton = 1"
        ).fetchone()
        if existing is not None and not replace_existing:
            raise ValueError(
                "dungeon chest model already exists; pass replace_existing=True "
                "to intentionally discard project-local edits"
            )
        if existing is None:
            record_count = int(
                connection.execute("SELECT COUNT(*) FROM dungeon_chest_record").fetchone()[0]
            )
            if record_count:
                raise ValueError(
                    "dungeon chest records exist without model metadata; refusing partial import"
                )

        if dry_run:
            before_model = (
                _export_dungeon_chests(connection) if existing is not None else None
            )
            room_values = {int(entry["room_value"]) for entry in payload["entries"]}
            item_values = {int(entry["item_value"]) for entry in payload["entries"]}
            big_chest_count = sum(bool(entry["is_big_chest"]) for entry in payload["entries"])
            return {
                "action": "import_dungeon_chest_data",
                "dry_run": True,
                "replace_existing": replace_existing,
                "before": None if before_model is None else {
                    "source_file": before_model["source_file"],
                    "source_revision": before_model["source_revision"],
                    "source_sha256": before_model["source_sha256"],
                    "summary": before_model["summary"],
                },
                "proposed": {
                    "source_file": str(payload["source_file"]),
                    "source_revision": str(payload["source_revision"]),
                    "source_sha256": payload_hash,
                    "table_label": str(payload["table_label"]),
                    "summary": {
                        "entry_count": len(payload["entries"]),
                        "distinct_room_value_count": len(room_values),
                        "distinct_item_value_count": len(item_values),
                        "big_chest_count": big_chest_count,
                        "modified_record_count": 0,
                    },
                },
                "rom_modified": False,
            }
        imported_at = _utc_timestamp()
        with connection:
            if existing is not None:
                connection.execute("DELETE FROM dungeon_chest_record")
                connection.execute("DELETE FROM dungeon_chest_model")

            connection.execute(
                """INSERT INTO dungeon_chest_model (
                       singleton, source_file, source_revision, source_sha256,
                       imported_at, table_label, source_range_annotation,
                       source_annotated_start_offset, source_annotated_end_offset,
                       table_size_bytes, entry_width_bytes, entry_count
                   ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(payload["source_file"]),
                    str(payload["source_revision"]),
                    payload_hash,
                    imported_at,
                    str(payload["table_label"]),
                    str(payload["source_range_annotation"]),
                    int(payload["source_annotated_start_offset"]),
                    int(payload["source_annotated_end_offset"]),
                    int(payload["table_size_bytes"]),
                    int(payload["entry_width_bytes"]),
                    int(payload["entry_count"]),
                ),
            )

            connection.executemany(
                """INSERT INTO dungeon_chest_record (
                       table_index, candidate_entry_offset, source_line, source_expression,
                       source_literal_value, literal_value, source_item_value, item_value,
                       source_room_value, room_value, source_is_big_chest, is_big_chest,
                       source_revision
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                records,
            )
    except sqlite3.Error as exc:
        raise ValueError(f"could not store dungeon chest model: {exc}") from exc
    finally:
        connection.close()

    export_project(db_path)
    model = get_dungeon_chest_model(db_path)
    if model is None:
        raise ValueError("dungeon chest model import did not persist")
    return model


def get_dungeon_chest_model(
    database_path: str | Path,
) -> dict[str, Any] | None:
    """Return the project-local dungeon chest inventory and its source comparison."""
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(read_only_uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _require_current_schema(connection)
        return _export_dungeon_chests(connection)
    finally:
        connection.close()


def update_dungeon_chest_record(
    database_path: str | Path,
    table_index: int,
    *,
    item_value: int | None = None,
    room_value: int | None = None,
    is_big_chest: bool | None = None,
    expected_project_revision: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview or edit packed chest fields while preserving immutable source values.

    The default is read-only. An applied edit recomposes the packed 24-bit
    literal and updates only current project fields; source expression, source
    literal, and source field values remain unchanged. When supplied,
    expected_project_revision is checked inside the write transaction. No ROM
    bytes are read or written.
    """
    if isinstance(table_index, bool) or not isinstance(table_index, int) or not 0 <= table_index <= 167:
        raise ValueError("table_index must be an integer in 0..167")
    if item_value is None and room_value is None and is_big_chest is None:
        raise ValueError("supply item_value, room_value, or is_big_chest")
    if item_value is not None and (
        isinstance(item_value, bool) or not isinstance(item_value, int) or not 0 <= item_value <= 0xFF
    ):
        raise ValueError("item_value must be an integer in 0..255")
    if room_value is not None and (
        isinstance(room_value, bool) or not isinstance(room_value, int) or not 0 <= room_value <= 0x7FFF
    ):
        raise ValueError("room_value must be an integer in 0..32767")
    if is_big_chest is not None and not isinstance(is_big_chest, bool):
        raise ValueError("is_big_chest must be a boolean")
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be a boolean")
    _validate_expected_project_revision(expected_project_revision)

    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"project database not found: {db_path}")
    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = (
        sqlite3.connect(read_only_uri, uri=True)
        if dry_run
        else sqlite3.connect(db_path)
    )
    connection.row_factory = sqlite3.Row
    changed_fields: list[str] = []
    before: dict[str, Any]
    try:
        if dry_run:
            connection.execute("BEGIN")
        else:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
        _require_current_schema(connection)
        project_revision = _calculate_project_revision(connection)
        _require_matching_project_revision(
            expected_project_revision, project_revision
        )
        model = _export_dungeon_chests(connection)
        if model is None:
            raise ValueError("no dungeon chest model has been imported")
        before_record = next(
            (
                record for record in model["entries"]
                if record["table_index"] == table_index
            ),
            None,
        )
        if before_record is None:
            raise KeyError(f"dungeon chest record not found: {table_index}")
        before = dict(before_record)
        source_references = _dungeon_chest_record_source_references(
            model, before_record
        )

        new_item = int(before["item_value"]) if item_value is None else item_value
        new_room = int(before["room_value"]) if room_value is None else room_value
        new_big = bool(before["is_big_chest"]) if is_big_chest is None else is_big_chest
        packed = (new_item << 16) | new_room | (int(new_big) << 15)
        proposed = dict(before)
        proposed.update({
            "item_value": new_item,
            "room_value": new_room,
            "is_big_chest": new_big,
            "literal_value": packed,
            "literal_hex": "$" + format(packed, "06X"),
            "expression": "$" + format(packed, "06X"),
            "room_pointer_index": new_room,
            "room_pointer_table_byte_displacement": new_room * 3,
            "is_modified": (
                new_item != before["source_item_value"]
                or new_room != before["source_room_value"]
                or new_big != before["source_is_big_chest"]
            ),
        })
        if new_item != before["item_value"]:
            changed_fields.append("item_value")
        if new_room != before["room_value"]:
            changed_fields.append("room_value")
        if new_big != before["is_big_chest"]:
            changed_fields.append("is_big_chest")

        if dry_run:
            return {
                "action": "update_dungeon_chest_record",
                "dry_run": True,
                "project_revision": project_revision,
                "table_index": table_index,
                "before": before,
                "proposed": proposed,
                "source_references": source_references,
                "changed_fields": changed_fields,
                "rom_modified": False,
            }

        if changed_fields:
            with connection:
                connection.execute(
                    """UPDATE dungeon_chest_record
                       SET item_value = ?, room_value = ?, is_big_chest = ?, literal_value = ?
                       WHERE table_index = ?""",
                    (new_item, new_room, int(new_big), packed, table_index),
                )
    except sqlite3.Error as exc:
        raise ValueError(f"could not update dungeon chest record: {exc}") from exc
    finally:
        connection.close()

    if changed_fields:
        export_project(db_path)
    updated_model = get_dungeon_chest_model(db_path)
    if updated_model is None:
        raise ValueError("no dungeon chest model has been imported")
    for record in updated_model["entries"]:
        if record["table_index"] == table_index:
            return cast(
                dict[str, Any],
                {**record, "source_references": source_references},
            )
    raise KeyError(f"dungeon chest record not found: {table_index}")


def _project_validation_snapshot(
    connection: sqlite3.Connection,
    output_path: Path,
) -> tuple[list[str], dict[str, Any] | None]:
    """Validate one read-only SQLite snapshot and return its canonical payload."""
    problems: list[str] = []
    try:
        integrity_rows = connection.execute("PRAGMA quick_check").fetchall()
    except sqlite3.Error as exc:
        return [f"SQLite integrity check failed to run: {exc}"], None

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
        *_DUNGEON_CHEST_TABLE_NAMES,
        *_OVERWORLD_CUSTOM_TABLE_NAMES,
    }
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        problems.append("missing required table(s): " + ", ".join(missing_tables))
        return problems, None

    try:
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
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
        return problems, None

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
        problems.append("project metadata does not name the canonical US base ROM")

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
    return problems, payload


def _compact_semantic_model_context(
    model: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Keep semantic-model provenance and counters, never individual records."""
    if model is None:
        return None
    return {
        "format": model["format"],
        "format_version": model["format_version"],
        "source_file": model["source_file"],
        "source_revision": model["source_revision"],
        "source_sha256": model["source_sha256"],
        "summary": model["summary"],
        "evidence": model["evidence"],
    }


def _redact_project_context_problems(
    problems: list[str],
    database_path: Path,
    json_path: Path,
) -> list[str]:
    """Remove machine-specific local paths from context summary diagnostics."""
    redacted = list(problems)
    for path, label in (
        (database_path, "project database"),
        (json_path, "canonical JSON sidecar"),
    ):
        candidates = {str(path), str(path.resolve())}
        for candidate in candidates:
            if candidate:
                redacted = [message.replace(candidate, label) for message in redacted]
    return redacted


def get_project_context(
    database_path: str | Path,
    json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return validated project metadata, provenance, model counts, and revision.

    All SQLite-backed values are derived from one read-only transaction so the
    project summary and fingerprint describe the same canonical snapshot.
    Individual source-asset payloads and semantic record arrays are omitted.
    No ROM bytes are read or written.
    """
    db_path = Path(database_path)
    output_path = Path(json_path) if json_path is not None else db_path.with_suffix(".json")
    if not db_path.is_file():
        return {
            "valid": False,
            "problems": ["project database file not found"],
            "project_revision": None,
            "format": None,
            "format_version": None,
            "schema_version": None,
            "project": None,
            "source_asset_count": 0,
            "source_assets": [],
            "semantic_models": {
                "overworld_hidden_items": None,
                "dungeon_chests": None,
            },
            "evidence": {
                "sqlite_snapshot_read_only": False,
                "full_payloads_omitted": True,
                "rom_bytes_read": False,
                "rom_modified": False,
            },
        }

    read_only_uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(read_only_uri, uri=True)
    except sqlite3.Error:
        return {
            "valid": False,
            "problems": ["could not open project database read-only"],
            "project_revision": None,
            "format": None,
            "format_version": None,
            "schema_version": None,
            "project": None,
            "source_asset_count": 0,
            "source_assets": [],
            "semantic_models": {
                "overworld_hidden_items": None,
                "dungeon_chests": None,
            },
            "evidence": {
                "sqlite_snapshot_read_only": False,
                "full_payloads_omitted": True,
                "rom_bytes_read": False,
                "rom_modified": False,
            },
        }

    try:
        connection.execute("BEGIN")
        problems, payload = _project_validation_snapshot(connection, output_path)
        context_problems = _redact_project_context_problems(
            problems, db_path, output_path
        )
        if payload is None:
            return {
                "valid": False,
                "problems": context_problems,
                "project_revision": None,
                "format": None,
                "format_version": None,
                "schema_version": None,
                "project": None,
                "source_asset_count": 0,
                "source_assets": [],
                "semantic_models": {
                    "overworld_hidden_items": None,
                    "dungeon_chests": None,
                },
                "evidence": {
                    "sqlite_snapshot_read_only": True,
                    "full_payloads_omitted": True,
                    "rom_bytes_read": False,
                    "rom_modified": False,
                },
            }

        project_revision = hashlib.sha256(
            _render_json(payload).encode("utf-8")
        ).hexdigest()
        source_asset_fields = (
            "key",
            "format",
            "format_version",
            "source_file",
            "source_revision",
            "sha256",
            "imported_at",
        )
        source_assets = [
            {field: asset[field] for field in source_asset_fields}
            for asset in payload["source_assets"]
        ]
        return {
            "valid": not problems,
            "problems": context_problems,
            "project_revision": project_revision,
            "format": payload["format"],
            "format_version": payload["format_version"],
            "schema_version": payload["schema_version"],
            "project": payload["project"],
            "source_asset_count": len(source_assets),
            "source_assets": source_assets,
            "semantic_models": {
                "overworld_hidden_items": _compact_semantic_model_context(
                    payload["overworld_hidden_items"]
                ),
                "dungeon_chests": _compact_semantic_model_context(
                    payload["dungeon_chests"]
                ),
            },
            "evidence": {
                "sqlite_snapshot_read_only": True,
                "full_payloads_omitted": True,
                "rom_bytes_read": False,
                "rom_modified": False,
            },
        }
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

    try:
        problems, _payload = _project_validation_snapshot(connection, output_path)
        return problems
    finally:
        connection.close()
