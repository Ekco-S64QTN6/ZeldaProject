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
DICTIONARY_INVENTORY_FORMAT = "zelda-suite-dictionary-inventory"
TEXT_MESSAGE_INDEX_FORMAT = "zelda-suite-text-message-index"
_DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}
SOURCE_EXPORT_FORMAT_VERSION = 1

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SOURCE_LABEL_RE = re.compile(r"\.?[A-Za-z_][A-Za-z0-9_]*\Z")
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
_DATA_TABLE_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "parent_label",
    "table_label",
    "end_label",
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
    "source_label",
    "expression",
    "literal_value",
    "source_revision",
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


def _source_label(value: Any, context: str) -> str:
    label = _string(value, context)
    if _SOURCE_LABEL_RE.fullmatch(label) is None:
        raise AssetLoadError(f"{context} must be a source assembly label")
    return label


def _nullable_source_label(value: Any, context: str) -> str | None:
    if value is None:
        return None
    return _source_label(value, context)


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

    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    _nullable_label = payload["parent_label"]
    if _nullable_label is not None:
        _identifier(_nullable_label, "parent_label")
    _source_label(payload["table_label"], "table_label")
    _nullable_source_label(payload["end_label"], "end_label")

    table_offset = _integer(payload["table_file_offset"], "table_file_offset", minimum=0)
    directive = payload["directive"]
    directive_widths = {"db": 1, "dw": 2, "dl": 3}
    if directive not in directive_widths:
        raise AssetLoadError("directive must be 'db', 'dw', or 'dl'")
    entry_width = _integer(payload["entry_width"], "entry_width", minimum=1)
    entry_count = _integer(payload["entry_count"], "entry_count", minimum=1)
    entries = payload["entries"]
    if not isinstance(entries, list) or not entries:
        raise AssetLoadError("entries must be a non-empty array")
    if entry_count != len(entries):
        raise AssetLoadError(
            f"entry_count is {entry_count}, but entries contains {len(entries)} records"
        )

    literal_limit = 1 << (8 * directive_widths[directive])
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _DATA_TABLE_ENTRY_KEYS, context)

        table_index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if table_index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {table_index}"
            )
        entry_offset = _integer(
            entry["entry_file_offset"], f"{context}.entry_file_offset", minimum=0
        )
        expected_offset = table_offset + expected_index * entry_width
        if entry_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.entry_file_offset must be {expected_offset}, got {entry_offset}"
            )
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        source_label = entry["source_label"]
        if source_label is not None:
            _source_label(source_label, f"{context}.source_label")
        _string(entry["expression"], f"{context}.expression")
        literal_value = _nullable_integer(
            entry["literal_value"], f"{context}.literal_value", minimum=0
        )
        if literal_value is not None and literal_value >= literal_limit:
            raise AssetLoadError(
                f"{context}.literal_value does not fit the {directive} directive"
            )
        entry_revision = _string(entry["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )

_DICTIONARY_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "pointer_table_label",
    "pointer_table_file_offset",
    "data_label",
    "data_file_offset",
    "fragment_count",
    "fragments",
}
_DICTIONARY_FRAGMENT_KEYS = {
    "pointer_index",
    "pointer_entry_file_offset",
    "pointer_expression",
    "fragment_label",
    "fragment_source_line",
    "fragment_file_offset",
    "next_fragment_file_offset",
    "source_extent_bytes",
    "data_directive",
    "directive_value_count",
    "directive_width_bytes",
    "declared_payload_bytes",
    "source_extent_matches_directive",
    "is_end_of_table",
    "source_revision",
}
_DICTIONARY_TARGET_RE = re.compile(r"DictionaryEntries_([A-Za-z_][A-Za-z0-9_]*)\Z")


def _validate_dictionary_inventory_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _DICTIONARY_TOP_KEYS, "dictionary inventory export")
    if payload["format"] != DICTIONARY_INVENTORY_FORMAT:
        raise AssetLoadError("dictionary inventory export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported dictionary inventory format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    pointer_label = _string(payload["pointer_table_label"], "pointer_table_label")
    _identifier(pointer_label, "pointer_table_label")
    pointer_offset = _integer(
        payload["pointer_table_file_offset"], "pointer_table_file_offset", minimum=0
    )
    data_label = _string(payload["data_label"], "data_label")
    _identifier(data_label, "data_label")
    data_offset = _integer(payload["data_file_offset"], "data_file_offset", minimum=0)
    fragment_count = _integer(payload["fragment_count"], "fragment_count", minimum=1)
    fragments = payload["fragments"]
    if not isinstance(fragments, list) or not fragments:
        raise AssetLoadError("fragments must be a non-empty array")
    if fragment_count != len(fragments):
        raise AssetLoadError(
            f"fragment_count is {fragment_count}, but fragments contains {len(fragments)} records"
        )

    seen_labels: set[str] = set()
    last_file_offset = -1
    end_marker_count = 0
    width_by_directive = {"db": 1, "dw": 2, "dl": 3}

    for expected_index, raw_fragment in enumerate(fragments):
        context = f"fragments[{expected_index}]"
        fragment = _object(raw_fragment, context)
        _exact_keys(fragment, _DICTIONARY_FRAGMENT_KEYS, context)

        index = _integer(fragment["pointer_index"], f"{context}.pointer_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(
                f"{context}.pointer_index must be {expected_index}, got {index}"
            )
        pointer_offset_actual = _integer(
            fragment["pointer_entry_file_offset"],
            f"{context}.pointer_entry_file_offset",
            minimum=0,
        )
        expected_pointer_offset = pointer_offset + expected_index * 2
        if pointer_offset_actual != expected_pointer_offset:
            raise AssetLoadError(
                f"{context}.pointer_entry_file_offset must be "
                f"{expected_pointer_offset}, got {pointer_offset_actual}"
            )

        pointer_expression = _string(
            fragment["pointer_expression"], f"{context}.pointer_expression"
        )
        target_match = _DICTIONARY_TARGET_RE.fullmatch(pointer_expression)
        if target_match is None:
            raise AssetLoadError(
                f"{context}.pointer_expression must reference a DictionaryEntries label"
            )
        expected_label = f".{target_match.group(1)}"
        fragment_label = _source_label(fragment["fragment_label"], f"{context}.fragment_label")
        if fragment_label != expected_label:
            raise AssetLoadError(
                f"{context}.fragment_label must match pointer target {expected_label}"
            )
        if fragment_label in seen_labels:
            raise AssetLoadError(f"duplicate fragment label: {fragment_label}")
        seen_labels.add(fragment_label)

        _integer(fragment["fragment_source_line"], f"{context}.fragment_source_line", minimum=1)
        fragment_offset = _integer(
            fragment["fragment_file_offset"], f"{context}.fragment_file_offset", minimum=0
        )
        if expected_index == 0 and fragment_offset != data_offset:
            raise AssetLoadError(
                f"{context}.fragment_file_offset must match data_file_offset {data_offset}"
            )
        if fragment_offset <= last_file_offset:
            raise AssetLoadError("fragment file offsets must be strictly increasing")
        last_file_offset = fragment_offset

        next_offset = _nullable_integer(
            fragment["next_fragment_file_offset"],
            f"{context}.next_fragment_file_offset",
            minimum=0,
        )
        extent = _nullable_integer(
            fragment["source_extent_bytes"],
            f"{context}.source_extent_bytes",
            minimum=0,
        )
        if next_offset is None:
            expected_extent = None
        else:
            if next_offset <= fragment_offset:
                raise AssetLoadError(
                    f"{context}.next_fragment_file_offset must be greater than fragment_file_offset"
                )
            expected_extent = next_offset - fragment_offset
        if extent != expected_extent:
            raise AssetLoadError(
                f"{context}.source_extent_bytes is inconsistent with fragment offsets"
            )
        if expected_index < fragment_count - 1:
            next_fragment = fragments[expected_index + 1]
            if next_offset != next_fragment.get("fragment_file_offset"):
                raise AssetLoadError(
                    f"{context}.next_fragment_file_offset does not match the next fragment"
                )
        elif next_offset is not None:
            raise AssetLoadError("last fragment must not declare a next fragment offset")

        directive = fragment["data_directive"]
        value_count = _integer(
            fragment["directive_value_count"], f"{context}.directive_value_count", minimum=0
        )
        width = _nullable_integer(
            fragment["directive_width_bytes"], f"{context}.directive_width_bytes", minimum=1
        )
        declared_bytes = _nullable_integer(
            fragment["declared_payload_bytes"], f"{context}.declared_payload_bytes", minimum=0
        )
        if directive is None:
            if value_count != 0 or width is not None or declared_bytes is not None:
                raise AssetLoadError(
                    f"{context} has inconsistent fields for a fragment without a data directive"
                )
        else:
            if directive not in width_by_directive:
                raise AssetLoadError(f"{context}.data_directive must be db, dw, dl, or null")
            if value_count <= 0:
                raise AssetLoadError(f"{context}.directive_value_count must be positive")
            if width != width_by_directive[directive]:
                raise AssetLoadError(
                    f"{context}.directive_width_bytes does not match data_directive"
                )
            if declared_bytes != value_count * width:
                raise AssetLoadError(
                    f"{context}.declared_payload_bytes does not match directive count and width"
                )

        extent_match = fragment["source_extent_matches_directive"]
        if extent_match is not None:
            _boolean(extent_match, f"{context}.source_extent_matches_directive")
        expected_extent_match = (
            extent == declared_bytes
            if extent is not None and declared_bytes is not None
            else None
        )
        if extent_match is not expected_extent_match:
            raise AssetLoadError(
                f"{context}.source_extent_matches_directive is inconsistent with the source extent"
            )

        end_marker = _boolean(fragment["is_end_of_table"], f"{context}.is_end_of_table")
        if end_marker:
            end_marker_count += 1
            if fragment_label != ".endOfTable" or expected_index != fragment_count - 1:
                raise AssetLoadError("end-of-table marker must be the final .endOfTable fragment")
        entry_revision = _string(fragment["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )

    if end_marker_count != 1:
        raise AssetLoadError("dictionary inventory must contain exactly one end-of-table marker")


_TEXT_MESSAGE_INDEX_TOP_KEYS = {
    "format",
    "format_version",
    "source_revision",
    "source_block_count",
    "source_blocks",
    "message_count",
    "messages",
}
_TEXT_MESSAGE_BLOCK_KEYS = {
    "source_file",
    "data_block_label",
    "block_start_offset",
    "block_end_offset",
    "block_size_bytes",
    "message_count",
    "declared_byte_count_total",
    "declared_bytes_match_block_size",
}
_TEXT_MESSAGE_KEYS = {
    "message_index",
    "message_id",
    "message_label",
    "source_file",
    "data_block_label",
    "source_line",
    "source_offset_annotation",
    "annotated_file_offset",
    "source_offset_annotation_valid",
    "source_offset_matches_sequential",
    "sequential_file_offset",
    "declared_byte_count",
    "source_revision",
}
_MESSAGE_LABEL_RE = re.compile(r"Message_([0-9A-Fa-f]{4})\Z")
_MESSAGE_OFFSET_ANNOTATION_RE = re.compile(r"\$([0-9A-Fa-f]+)\Z")


def _validate_text_message_index_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _TEXT_MESSAGE_INDEX_TOP_KEYS, "text message index")
    if payload["format"] != TEXT_MESSAGE_INDEX_FORMAT:
        raise AssetLoadError("text message index has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported text message index version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    revision = _string(payload["source_revision"], "source_revision")

    raw_blocks = payload["source_blocks"]
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise AssetLoadError("source_blocks must be a non-empty array")
    block_count = _integer(payload["source_block_count"], "source_block_count", minimum=1)
    if block_count != len(raw_blocks):
        raise AssetLoadError(
            f"source_block_count is {block_count}, but source_blocks contains {len(raw_blocks)} records"
        )

    blocks: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw_block in enumerate(raw_blocks):
        context = f"source_blocks[{index}]"
        block = _object(raw_block, context)
        _exact_keys(block, _TEXT_MESSAGE_BLOCK_KEYS, context)
        source_file = _string(block["source_file"], f"{context}.source_file")
        label = _string(block["data_block_label"], f"{context}.data_block_label")
        _identifier(label, f"{context}.data_block_label")
        start = _integer(block["block_start_offset"], f"{context}.block_start_offset", minimum=0)
        end = _integer(block["block_end_offset"], f"{context}.block_end_offset", minimum=0)
        if end < start:
            raise AssetLoadError(f"{context}.block_end_offset precedes block_start_offset")
        size = _integer(block["block_size_bytes"], f"{context}.block_size_bytes", minimum=1)
        if size != end - start + 1:
            raise AssetLoadError(f"{context}.block_size_bytes is inconsistent with its range")
        _integer(block["message_count"], f"{context}.message_count", minimum=1)
        declared_total = _integer(
            block["declared_byte_count_total"],
            f"{context}.declared_byte_count_total",
            minimum=1,
        )
        matches = _boolean(
            block["declared_bytes_match_block_size"],
            f"{context}.declared_bytes_match_block_size",
        )
        if matches is not (declared_total == size):
            raise AssetLoadError(
                f"{context}.declared_bytes_match_block_size is inconsistent with its counts"
            )
        identity = (source_file, label)
        if identity in blocks:
            raise AssetLoadError(f"duplicate source block: {source_file}:{label}")
        blocks[identity] = block

    messages = payload["messages"]
    message_count = _integer(payload["message_count"], "message_count", minimum=1)
    if not isinstance(messages, list) or not messages:
        raise AssetLoadError("messages must be a non-empty array")
    if message_count != len(messages):
        raise AssetLoadError(
            f"message_count is {message_count}, but messages contains {len(messages)} records"
        )

    block_records: dict[tuple[str, str], list[dict[str, Any]]] = {
        key: [] for key in blocks
    }
    seen_ids: set[int] = set()
    running_offsets: dict[tuple[str, str], int] = {
        key: block["block_start_offset"] for key, block in blocks.items()
    }
    totals: dict[tuple[str, str], int] = {key: 0 for key in blocks}
    for expected_index, raw_message in enumerate(messages):
        context = f"messages[{expected_index}]"
        message = _object(raw_message, context)
        _exact_keys(message, _TEXT_MESSAGE_KEYS, context)
        index = _integer(message["message_index"], f"{context}.message_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(
                f"{context}.message_index must be {expected_index}, got {index}"
            )
        message_id = _integer(message["message_id"], f"{context}.message_id", minimum=0)
        if message_id > 0xFFFF:
            raise AssetLoadError(f"{context}.message_id exceeds 16 bits")
        if message_id in seen_ids:
            raise AssetLoadError(f"duplicate text message ID: {message_id:04X}")
        seen_ids.add(message_id)
        message_label = _string(message["message_label"], f"{context}.message_label")
        label_match = _MESSAGE_LABEL_RE.fullmatch(message_label)
        if label_match is None or int(label_match.group(1), 16) != message_id:
            raise AssetLoadError(f"{context}.message_label does not match message_id")

        source_file = _string(message["source_file"], f"{context}.source_file")
        data_label = _string(message["data_block_label"], f"{context}.data_block_label")
        identity = (source_file, data_label)
        if identity not in blocks:
            raise AssetLoadError(f"{context} refers to an unknown source block")
        block = blocks[identity]
        _integer(message["source_line"], f"{context}.source_line", minimum=1)
        annotation = message["source_offset_annotation"]
        annotated_offset = _nullable_integer(
            message["annotated_file_offset"], f"{context}.annotated_file_offset", minimum=0
        )
        annotation_valid = message["source_offset_annotation_valid"]
        annotation_matches = message["source_offset_matches_sequential"]
        sequential_offset = _integer(
            message["sequential_file_offset"], f"{context}.sequential_file_offset", minimum=0
        )
        expected_sequential = running_offsets[identity]
        if sequential_offset != expected_sequential:
            raise AssetLoadError(
                f"{context}.sequential_file_offset is inconsistent with previous message lengths"
            )
        byte_count = _integer(message["declared_byte_count"], f"{context}.declared_byte_count", minimum=1)
        running_offsets[identity] += byte_count
        totals[identity] += byte_count

        if annotation is None:
            if annotated_offset is not None or annotation_valid is not None or annotation_matches is not None:
                raise AssetLoadError(
                    f"{context} must use null offset fields when no source annotation exists"
                )
        else:
            annotation_text = _string(annotation, f"{context}.source_offset_annotation")
            annotation_match = _MESSAGE_OFFSET_ANNOTATION_RE.fullmatch(annotation_text)
            if annotation_match is None:
                raise AssetLoadError(
                    f"{context}.source_offset_annotation must be a dollar-prefixed hexadecimal value"
                )
            raw_digits = annotation_match.group(1)
            raw_value = int(raw_digits, 16)
            expected_valid = (
                len(raw_digits) == 6
                and block["block_start_offset"] <= raw_value <= block["block_end_offset"]
            )
            if type(annotation_valid) is not bool or annotation_valid is not expected_valid:
                raise AssetLoadError(
                    f"{context}.source_offset_annotation_valid is inconsistent with its block range"
                )
            expected_annotated_offset = raw_value if expected_valid else None
            if annotated_offset != expected_annotated_offset:
                raise AssetLoadError(
                    f"{context}.annotated_file_offset is inconsistent with its annotation"
                )
            expected_matches = annotated_offset == sequential_offset
            if type(annotation_matches) is not bool or annotation_matches is not expected_matches:
                raise AssetLoadError(
                    f"{context}.source_offset_matches_sequential is inconsistent with its offsets"
                )

        entry_revision = _string(message["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )
        block_records[identity].append(message)

    for identity, block in blocks.items():
        entries = block_records[identity]
        if len(entries) != block["message_count"]:
            raise AssetLoadError(
                f"{identity[0]}:{identity[1]} message_count does not match its messages"
            )
        if totals[identity] != block["declared_byte_count_total"]:
            raise AssetLoadError(
                f"{identity[0]}:{identity[1]} declared_byte_count_total does not match its messages"
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
    elif format_name == DICTIONARY_INVENTORY_FORMAT:
        _validate_dictionary_inventory_export(export)
    elif format_name == TEXT_MESSAGE_INDEX_FORMAT:
        _validate_text_message_index_export(export)
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
