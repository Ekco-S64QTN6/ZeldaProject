"""Read and validate source-inspection JSON exports.

These exports describe assembly-source declarations, not decoded ROM content.
Loading them never opens ROMs or referenced incbin payload files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

POINTER_TABLE_FORMAT = "zelda-suite-pointer-table"
INCBIN_INVENTORY_FORMAT = "zelda-suite-incbin-inventory"
DATA_TABLE_FORMAT = "zelda-suite-data-table"
SOURCE_EXPORT_FORMAT_VERSION = 1

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_POINTER_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "table_label",
    "table_file_offset",
    "entry_width",
    "entry_count",
    "entries",
}
_POINTER_ENTRY_KEYS = {
    "table_index",
    "pointer_entry_file_offset",
    "source_line",
    "pointer_expression",
    "target_label",
    "target_addend",
    "is_empty_target",
    "source_revision",
}
_INCBIN_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "declaration_count",
    "declarations",
}
_INCBIN_DECLARATION_KEYS = {
    "source_file",
    "source_revision",
    "label",
    "source_line",
    "incbin_path",
    "declared_size_bytes",
    "source_file_offset_start",
    "source_file_offset_end",
    "computed_file_offset_end",
    "source_range_size_matches",
}


class AssetLoadError(ValueError):
    """Raised when a source-inspection export is malformed or inconsistent."""


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssetLoadError(f"{context} must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise AssetLoadError(f"{context} must use string keys")
    return value


def _exact_keys(
    value: dict[str, Any], expected: set[str], context: str
) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing:
        raise AssetLoadError(f"{context} is missing required field(s): {', '.join(missing)}")
    if extra:
        raise AssetLoadError(f"{context} has unexpected field(s): {', '.join(extra)}")


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise AssetLoadError(f"{context} must be a non-empty string")
    return value


def _integer(value: Any, context: str, *, minimum: int | None = None) -> int:
    # bool is an int subclass in Python, but JSON booleans are not valid integer fields.
    if type(value) is not int:
        raise AssetLoadError(f"{context} must be an integer")
    if minimum is not None and value < minimum:
        raise AssetLoadError(f"{context} must be at least {minimum}")
    return value


def _identifier(value: Any, context: str) -> str:
    label = _string(value, context)
    if _IDENTIFIER_RE.fullmatch(label) is None:
        raise AssetLoadError(f"{context} must be an assembly identifier")
    return label


def _boolean(value: Any, context: str) -> bool:
    if type(value) is not bool:
        raise AssetLoadError(f"{context} must be a boolean")
    return value


def _nullable_integer(
    value: Any, context: str, *, minimum: int | None = None
) -> int | None:
    if value is None:
        return None
    return _integer(value, context, minimum=minimum)


def _validate_pointer_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _POINTER_TOP_KEYS, "pointer-table export")
    if payload["format"] != POINTER_TABLE_FORMAT:
        raise AssetLoadError("pointer-table export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported pointer-table format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    _identifier(payload["table_label"], "table_label")
    table_offset = _integer(payload["table_file_offset"], "table_file_offset", minimum=0)
    entry_width = _integer(payload["entry_width"], "entry_width", minimum=1)
    entry_count = _integer(payload["entry_count"], "entry_count", minimum=1)
    entries = payload["entries"]
    if not isinstance(entries, list) or not entries:
        raise AssetLoadError("entries must be a non-empty array")
    if entry_count != len(entries):
        raise AssetLoadError(
            f"entry_count is {entry_count}, but entries contains {len(entries)} records"
        )

    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _POINTER_ENTRY_KEYS, context)

        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {index}"
            )

        actual_offset = _integer(
            entry["pointer_entry_file_offset"],
            f"{context}.pointer_entry_file_offset",
            minimum=0,
        )
        expected_offset = table_offset + expected_index * entry_width
        if actual_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.pointer_entry_file_offset must be "
                f"{expected_offset}, got {actual_offset}"
            )

        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        _string(entry["pointer_expression"], f"{context}.pointer_expression")
        target = _identifier(entry["target_label"], f"{context}.target_label")
        addend = entry["target_addend"]
        if addend is not None:
            _integer(addend, f"{context}.target_addend")
        is_empty = _boolean(entry["is_empty_target"], f"{context}.is_empty_target")
        if is_empty != (target == "RoomDataTiles_Empty"):
            raise AssetLoadError(
                f"{context}.is_empty_target disagrees with target_label"
            )
        entry_revision = _string(entry["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )


def _validate_incbin_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _INCBIN_TOP_KEYS, "incbin inventory export")
    if payload["format"] != INCBIN_INVENTORY_FORMAT:
        raise AssetLoadError("incbin inventory export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported incbin inventory format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    source_file = _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    count = _integer(payload["declaration_count"], "declaration_count", minimum=0)
    declarations = payload["declarations"]
    if not isinstance(declarations, list):
        raise AssetLoadError("declarations must be an array")
    if count != len(declarations):
        raise AssetLoadError(
            f"declaration_count is {count}, but declarations contains {len(declarations)} records"
        )

    for index, raw_declaration in enumerate(declarations):
        context = f"declarations[{index}]"
        declaration = _object(raw_declaration, context)
        _exact_keys(declaration, _INCBIN_DECLARATION_KEYS, context)
        declared_source_file = _string(
            declaration["source_file"], f"{context}.source_file"
        )
        declared_revision = _string(
            declaration["source_revision"], f"{context}.source_revision"
        )
        if declared_source_file != source_file:
            raise AssetLoadError(
                f"{context}.source_file does not match top-level source_file"
            )
        if declared_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )

        _identifier(declaration["label"], f"{context}.label")
        _integer(declaration["source_line"], f"{context}.source_line", minimum=1)
        _string(declaration["incbin_path"], f"{context}.incbin_path")
        size = _nullable_integer(
            declaration["declared_size_bytes"],
            f"{context}.declared_size_bytes",
            minimum=0,
        )
        start = _nullable_integer(
            declaration["source_file_offset_start"],
            f"{context}.source_file_offset_start",
            minimum=0,
        )
        end = _nullable_integer(
            declaration["source_file_offset_end"],
            f"{context}.source_file_offset_end",
            minimum=0,
        )
        computed_end = _nullable_integer(
            declaration["computed_file_offset_end"],
            f"{context}.computed_file_offset_end",
            minimum=0,
        )
        range_matches = declaration["source_range_size_matches"]
        if range_matches is not None:
            _boolean(range_matches, f"{context}.source_range_size_matches")

        if start is not None and end is not None and end < start:
            raise AssetLoadError(f"{context} source offset range ends before it starts")

        expected_computed_end = (
            start + size - 1
            if start is not None and size is not None and size > 0
            else None
        )
        if computed_end != expected_computed_end:
            raise AssetLoadError(
                f"{context}.computed_file_offset_end is inconsistent with "
                "source_file_offset_start and declared_size_bytes"
            )

        expected_range_matches: bool | None = None
        if start is not None and end is not None and size is not None:
            expected_range_matches = (end - start + 1) == size
        if range_matches is not expected_range_matches:
            raise AssetLoadError(
                f"{context}.source_range_size_matches is inconsistent with "
                "the recorded range and size"
            )


_DATA_TABLE_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "table_label",
    "table_file_offset",
    "directive",
    "entry_width",
    "entry_count",
    "entries",
}
_DATA_TABLE_ENTRY_KEYS = {
    "table_index",
    "entry_file_offset",
    "source_line",
    "directive",
    "source_label",
    "expression",
    "numeric_value",
    "inline_comment",
    "source_revision",
}
_DATA_TABLE_LABEL_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?\Z"
)
_SOURCE_LABEL_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|\.[A-Za-z_][A-Za-z0-9_]*)\Z")
_DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}


def _validate_data_table_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _DATA_TABLE_TOP_KEYS, "data-table export")
    if payload["format"] != DATA_TABLE_FORMAT:
        raise AssetLoadError("data-table export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported data-table format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    source_file = _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    table_label = _string(payload["table_label"], "table_label")
    if _DATA_TABLE_LABEL_RE.fullmatch(table_label) is None:
        raise AssetLoadError("table_label must be a global or qualified local assembly label")
    table_offset = _integer(payload["table_file_offset"], "table_file_offset", minimum=0)
    directive = _string(payload["directive"], "directive").lower()
    if directive not in _DATA_DIRECTIVE_WIDTHS:
        raise AssetLoadError("directive must be db, dw, or dl")
    entry_width = _integer(payload["entry_width"], "entry_width", minimum=1)
    if entry_width != _DATA_DIRECTIVE_WIDTHS[directive]:
        raise AssetLoadError("entry_width does not match the selected directive")
    entry_count = _integer(payload["entry_count"], "entry_count", minimum=1)
    entries = payload["entries"]
    if not isinstance(entries, list) or not entries:
        raise AssetLoadError("entries must be a non-empty array")
    if entry_count != len(entries):
        raise AssetLoadError(
            f"entry_count is {entry_count}, but entries contains {len(entries)} records"
        )

    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _DATA_TABLE_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {index}"
            )
        actual_offset = _integer(
            entry["entry_file_offset"], f"{context}.entry_file_offset", minimum=0
        )
        expected_offset = table_offset + expected_index * entry_width
        if actual_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.entry_file_offset must be {expected_offset}, got {actual_offset}"
            )
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        entry_directive = _string(entry["directive"], f"{context}.directive").lower()
        if entry_directive != directive:
            raise AssetLoadError(f"{context}.directive does not match top-level directive")
        source_label = _string(entry["source_label"], f"{context}.source_label")
        if _SOURCE_LABEL_RE.fullmatch(source_label) is None:
            raise AssetLoadError(f"{context}.source_label must be an assembly label")
        _string(entry["expression"], f"{context}.expression")
        numeric_value = entry["numeric_value"]
        if numeric_value is not None:
            _integer(numeric_value, f"{context}.numeric_value")
        inline_comment = entry["inline_comment"]
        if inline_comment is not None and not isinstance(inline_comment, str):
            raise AssetLoadError(f"{context}.inline_comment must be a string or null")
        entry_source_file = _string(entry.get("source_file", source_file), f"{context}.source_file") if "source_file" in entry else source_file
        if entry_source_file != source_file:
            raise AssetLoadError(f"{context}.source_file does not match top-level source_file")
        entry_revision = _string(entry["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )


def validate_source_export(payload: Any) -> dict[str, Any]:
    """Validate an already-parsed source export and return it unchanged."""
    export = _object(payload, "source export")
    format_name = export.get("format")
    if format_name == POINTER_TABLE_FORMAT:
        _validate_pointer_export(export)
    elif format_name == INCBIN_INVENTORY_FORMAT:
        _validate_incbin_export(export)
    elif format_name == DATA_TABLE_FORMAT:
        _validate_data_table_export(export)
    else:
        raise AssetLoadError(f"unsupported source export format: {format_name!r}")
    return export


def _reject_nonstandard_constant(value: str) -> None:
    raise AssetLoadError(f"non-standard JSON constant is not allowed: {value}")


def load_source_export(path: str | Path) -> dict[str, Any]:
    """Load and validate one supported JSON source export from disk.

    The file is read as UTF-8. No referenced source, payload, or ROM file is
    opened. The returned dictionary is the parsed export, unchanged.
    """
    source_path = Path(path)
    try:
        content = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssetLoadError(f"could not read source export {source_path}: {exc}") from exc

    try:
        payload = json.loads(content, parse_constant=_reject_nonstandard_constant)
    except (json.JSONDecodeError, AssetLoadError) as exc:
        raise AssetLoadError(f"invalid JSON in {source_path}: {exc}") from exc

    return validate_source_export(payload)
