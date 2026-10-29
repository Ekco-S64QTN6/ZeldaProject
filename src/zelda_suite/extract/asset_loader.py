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
SHOP_ITEM_HANDLERS_FORMAT = "zelda-suite-shop-item-handlers"
POTION_SHOP_TRANSACTIONS_FORMAT = "zelda-suite-potion-shop-transactions"
SPECIAL_SHOP_TRANSACTIONS_FORMAT = "zelda-suite-special-shop-transactions"
PAID_OVERWORLD_INTERACTIONS_FORMAT = "zelda-suite-paid-overworld-interactions"
DUNGEON_CHEST_DATA_FORMAT = "zelda-suite-dungeon-chest-data"
MIXED_DATA_TABLE_FORMAT = "zelda-suite-mixed-data-table"
DICTIONARY_INVENTORY_FORMAT = "zelda-suite-dictionary-inventory"
TEXT_MESSAGE_INDEX_FORMAT = "zelda-suite-text-message-index"
SPRITE_DISPATCH_FORMAT = "zelda-suite-sprite-dispatch"
SPRITE_PREP_DISPATCH_FORMAT = "zelda-suite-sprite-prep-dispatch"
MUSIC_TRACK_INDEX_FORMAT = "zelda-suite-music-track-index"
ITEM_RECEIPT_LAYOUT_FORMAT = "zelda-suite-item-receipt-layout"
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
_DATA_TABLE_ENTRY_V2_KEYS = _DATA_TABLE_ENTRY_KEYS | {"inline_comment"}

_DUNGEON_CHEST_DATA_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "table_label",
    "source_range_annotation",
    "source_annotated_start_offset",
    "source_annotated_end_offset",
    "table_size_bytes",
    "entry_width_bytes",
    "entry_count",
    "entries",
    "evidence",
}
_DUNGEON_CHEST_DATA_ENTRY_KEYS = {
    "table_index",
    "candidate_entry_offset",
    "source_line",
    "expression",
    "literal_value",
    "item_value",
    "room_value",
    "is_big_chest",
    "source_revision",
}
_DUNGEON_CHEST_DATA_EVIDENCE_KEYS = {
    "source_only",
    "rom_bytes_read",
    "source_range_offsets_verified",
    "item_value_names_resolved",
    "room_values_verified_against_rom",
}
_DUNGEON_CHEST_RANGE_RE = re.compile(
    r"\$(?P<start>[0-9A-Fa-f]+)-\$(?P<end>[0-9A-Fa-f]+)\Z"
)
_DUNGEON_CHEST_LITERAL_RE = re.compile(r"\$[0-9A-Fa-f]{6}\Z")


_SHOP_ITEM_HANDLERS_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "dispatch_routine_label",
    "dispatch_routine_source_range_annotation",
    "dispatch_table_file_offset",
    "dispatch_table_offset_established",
    "dispatch_entry_count",
    "entry_count",
    "entries",
    "evidence",
}
_SHOP_ITEM_HANDLERS_ENTRY_KEYS = {
    "table_index",
    "shopkeeper_variant_id",
    "handler_label",
    "source_handler_address_annotation",
    "source_dispatch_comment",
    "source_dispatch_line",
    "source_handler_range_annotation",
    "source_handler_label_line",
    "price_low_expression",
    "price_low_source_line",
    "price_high_expression",
    "price_high_source_line",
    "price_value",
    "payment_call_source_line",
    "receipt_item_index",
    "receipt_index_expression",
    "receipt_selector_source_line",
    "receipt_call_source_line",
    "source_revision",
}
_SHOP_ITEM_HANDLERS_EVIDENCE_KEYS = {
    "source_only",
    "rom_bytes_read",
    "dispatch_table_offset_established",
    "handler_address_annotations_verified",
    "price_behavior_runtime_verified",
    "receipt_item_names_resolved",
    "room_specific_shop_stock_resolved",
}
_SHOP_ITEM_RANGE_RE = re.compile(
    r"\$(?P<start>[0-9A-Fa-f]+)-\$(?P<end>[0-9A-Fa-f]+) JUMP LOCATION\Z",
    re.IGNORECASE,
)
_SHOP_ITEM_ADDRESS_RE = re.compile(r"\$[0-9A-Fa-f]{4}\Z")
_SHOP_ITEM_BYTE_RE = re.compile(r"\$[0-9A-Fa-f]{2}\Z")
_SHOP_ITEM_DISPATCH_COMMENT_RE = re.compile(
    r"0x(?P<selector>[0-9A-Fa-f]{2})\s*-\s*"
    r"(?P<address>\$[0-9A-Fa-f]{4})(?:\s+(?P<description>.*))?\Z"
)


_POTION_SHOP_TRANSACTIONS_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "entry_count",
    "entries",
    "evidence",
}
_POTION_SHOP_TRANSACTION_ENTRY_KEYS = {
    "table_index",
    "handler_label",
    "source_handler_range_annotation",
    "source_handler_label_line",
    "rupee_balance_address_expression",
    "price_compare_expression",
    "price_compare_source_line",
    "price_deduction_expression",
    "price_deduction_source_line",
    "price_value",
    "receipt_index_expression",
    "receipt_item_index",
    "receipt_selector_source_line",
    "receipt_call_source_line",
    "empty_bottle_check_source_line",
    "source_revision",
}
_POTION_SHOP_TRANSACTIONS_EVIDENCE_KEYS = {
    "source_only",
    "rom_bytes_read",
    "price_behavior_runtime_verified",
    "source_range_annotations_verified",
    "receipt_item_names_resolved",
    "room_specific_shop_stock_resolved",
    "canonical_item_ids_resolved",
}
_POTION_SHOP_RANGE_RE = re.compile(
    r"\$(?P<start>[0-9A-Fa-f]+)-\$(?P<end>[0-9A-Fa-f]+)"
    r"(?:\s+LOCAL)?\s+JUMP LOCATION\Z",
    re.IGNORECASE,
)
_POTION_SHOP_WORD_RE = re.compile(r"\$[0-9A-Fa-f]{4}\Z")
_POTION_SHOP_BYTE_RE = re.compile(r"\$[0-9A-Fa-f]{2}\Z")
_POTION_SHOP_ADDRESS_RE = re.compile(r"\$[0-9A-Fa-f]{6}\Z")


_SPECIAL_SHOP_TRANSACTIONS_TOP_KEYS = {
    "format", "format_version", "source_revision", "source_file", "entry_count", "entries", "evidence",
}
_SPECIAL_SHOP_TRANSACTION_ENTRY_KEYS = {
    "table_index", "transaction_label", "shop_type", "source_file",
    "source_handler_label", "source_handler_range_annotation", "source_handler_label_line",
    "reward_handler_label", "reward_handler_range_annotation", "reward_handler_label_line",
    "price_mode", "price_value", "price_low_expression", "price_low_source_line",
    "price_high_expression", "price_high_source_line", "price_compare_expression",
    "price_compare_source_line", "price_deduction_expression", "price_deduction_source_line",
    "rupee_balance_address_expression", "payment_call_source_line", "receipt_method",
    "receipt_item_index", "receipt_index_expression", "receipt_selector_source_line",
    "receipt_call_source_line", "source_item_annotation", "source_item_annotation_line",
    "reward_flag_address_expression", "reward_flag_value_expression", "reward_flag_source_line",
    "source_reward_comment", "tagalong_spawn_source_line", "source_revision",
}
_SPECIAL_SHOP_TRANSACTIONS_EVIDENCE_KEYS = {
    "source_only", "rom_bytes_read", "source_range_annotations_verified",
    "price_behavior_runtime_verified", "receipt_item_names_resolved",
    "room_specific_shop_stock_resolved", "canonical_item_ids_resolved",
    "special_bomb_reward_runtime_verified",
}
_SPECIAL_SHOP_RANGE_RE = re.compile(
    r"\$(?P<start>[0-9A-Fa-f]+)-\$(?P<end>[0-9A-Fa-f]+)(?: LOCAL)? JUMP LOCATION\Z",
    re.IGNORECASE,
)
_SPECIAL_SHOP_BYTE_RE = re.compile(r"\$[0-9A-Fa-f]{2}\Z")
_SPECIAL_SHOP_WORD_RE = re.compile(r"\$[0-9A-Fa-f]{4}\Z")
_SPECIAL_SHOP_ADDRESS_RE = re.compile(r"\$[0-9A-Fa-f]{6}\Z")


_PAID_OVERWORLD_TOP_KEYS = {
    "format",
    "format_version",
    "source_revision",
    "source_files",
    "interaction_count",
    "interactions",
    "reward_tables",
    "reward_gates",
    "evidence",
}
_PAID_OVERWORLD_INTERACTION_KEYS = {
    "interaction_id",
    "actor_label",
    "interaction_kind",
    "source_file",
    "source_label",
    "source_range_annotation",
    "source_annotation_line",
    "fee_model",
    "fee_values",
    "fee_expressions",
    "fee_table_label",
    "fee_source_lines",
    "payment_source_lines",
    "outcome_label",
    "outcome_source_lines",
    "source_revision",
}
_PAID_OVERWORLD_DISPATCH_TABLE_KEYS = {
    "table_id",
    "table_kind",
    "source_file",
    "source_label",
    "source_range_annotation",
    "source_annotation_line",
    "entry_count",
    "entries",
    "source_revision",
}
_PAID_OVERWORLD_DISPATCH_ENTRY_KEYS = {
    "table_index",
    "handler_label",
    "source_address_annotation",
    "source_comment",
    "source_line",
}
_PAID_OVERWORLD_POOL_ENTRY_KEYS = {
    "table_index",
    "expression",
    "source_comment",
    "source_line",
}
_PAID_OVERWORLD_GATE_KEYS = {
    "gate_id",
    "source_file",
    "source_label",
    "source_range_annotation",
    "source_annotation_line",
    "condition_source_lines",
    "condition_expressions",
    "minimum_hole_count",
    "required_state_expression",
    "random_mask_expression",
    "successful_random_value",
    "reward_flag_write_expression",
    "source_revision",
}
_PAID_OVERWORLD_EVIDENCE_KEYS = {
    "source_only",
    "rom_bytes_read",
    "source_range_annotations_verified",
    "fee_behavior_runtime_verified",
    "reward_probability_runtime_verified",
    "item_value_names_resolved",
    "payment_semantics_runtime_verified",
}
_PAID_OVERWORLD_RANGE_RE = re.compile(
    r"\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+ "
    r"(?:DATA|JUMP LOCATION|LOCAL JUMP LOCATION|BRANCH LOCATION)\Z",
    re.IGNORECASE,
)
_PAID_OVERWORLD_FEE_EXPRESSION_RE = re.compile(r"(?:\d+|\$[0-9A-Fa-f]{2,4})\Z")
_PAID_OVERWORLD_BYTE_RE = re.compile(r"\$[0-9A-Fa-f]{2}\Z")
_PAID_OVERWORLD_ADDRESS_RE = re.compile(r"\$[0-9A-Fa-f]{4}\Z")


_MIXED_DATA_TABLE_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "table_label",
    "table_file_offset",
    "record_count",
    "byte_count",
    "records",
}
_MIXED_DATA_RECORD_KEYS = {
    "record_index",
    "record_file_offset",
    "source_line",
    "source_label",
    "byte_length",
    "fields",
}
_MIXED_DATA_FIELD_KEYS = {
    "field_index",
    "field_file_offset",
    "source_line",
    "directive",
    "entry_width",
    "entry_count",
    "entries",
}
_MIXED_DATA_ENTRY_KEYS = {
    "entry_index",
    "entry_file_offset",
    "expression",
    "literal_value",
}

_ITEM_RECEIPT_LAYOUT_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "parent_label",
    "entry_count",
    "entries",
    "dungeon_mask_count",
    "dungeon_masks",
    "semantic_item_ids_resolved",
}
_ITEM_RECEIPT_LAYOUT_ROW_KEYS = {
    "table_index",
    "y_offset",
    "x_offset",
    "wide_item_flag",
    "properties",
    "target_address",
    "item_value",
}
_ITEM_RECEIPT_LAYOUT_CELL_KEYS = {
    "source_label",
    "entry_file_offset",
    "expression",
    "literal_value",
}
_ITEM_RECEIPT_LAYOUT_MASK_KEYS = {
    "table_index",
    *_ITEM_RECEIPT_LAYOUT_CELL_KEYS,
}
_ITEM_RECEIPT_LAYOUT_ARRAYS = {
    "y_offset": (".y_offsets", 0x04836C, 1),
    "x_offset": (".x_offsets", 0x0483B8, 1),
    "wide_item_flag": (".wide_item_flag", 0x048450, 1),
    "properties": (".properties", 0x04849C, 1),
    "target_address": (".item_target_addr", 0x0484E8, 2),
    "item_value": (".item_values", 0x048580, 1),
}
_ITEM_RECEIPT_LAYOUT_ENTRY_COUNT = 76
_ITEM_RECEIPT_LAYOUT_MASK_LABEL = ".item_masks"
_ITEM_RECEIPT_LAYOUT_MASK_OFFSET = 0x0485CC
_ITEM_RECEIPT_LAYOUT_MASK_WIDTH = 2
_ITEM_RECEIPT_LAYOUT_MASK_COUNT = 14


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
    if version not in (1, 2):
        raise AssetLoadError(
            f"unsupported data-table format version {version}; "
            "this loader supports versions 1 and 2"
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
        expected_entry_keys = (
            _DATA_TABLE_ENTRY_V2_KEYS if version == 2 else _DATA_TABLE_ENTRY_KEYS
        )
        _exact_keys(entry, expected_entry_keys, context)

        if version == 2:
            inline_comment = entry["inline_comment"]
            if inline_comment is not None and not isinstance(inline_comment, str):
                raise AssetLoadError(
                    f"{context}.inline_comment must be a string or null"
                )

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




def _validate_dungeon_chest_data_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _DUNGEON_CHEST_DATA_TOP_KEYS, "dungeon chest data export")
    if payload["format"] != DUNGEON_CHEST_DATA_FORMAT:
        raise AssetLoadError("dungeon chest data has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported dungeon chest data format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    if _string(payload["source_file"], "source_file") != "Bank01.asm":
        raise AssetLoadError("dungeon chest data source_file must be 'Bank01.asm'")
    revision = _string(payload["source_revision"], "source_revision")
    if _string(payload["table_label"], "table_label") != "Dungeon_ChestData":
        raise AssetLoadError("dungeon chest data table_label must be 'Dungeon_ChestData'")

    annotation = _string(
        payload["source_range_annotation"], "source_range_annotation"
    )
    match = _DUNGEON_CHEST_RANGE_RE.fullmatch(annotation)
    if match is None:
        raise AssetLoadError("source_range_annotation must be '$start-$end'")
    annotation_start = int(match.group("start"), 16)
    annotation_end = int(match.group("end"), 16)
    start = _integer(
        payload["source_annotated_start_offset"],
        "source_annotated_start_offset",
        minimum=0,
    )
    end = _integer(
        payload["source_annotated_end_offset"],
        "source_annotated_end_offset",
        minimum=0,
    )
    if (start, end) != (annotation_start, annotation_end):
        raise AssetLoadError(
            "source_annotated_start/end_offset do not match source_range_annotation"
        )
    if end < start:
        raise AssetLoadError("source_annotated_end_offset precedes start offset")

    table_size = _integer(payload["table_size_bytes"], "table_size_bytes", minimum=1)
    if table_size != end - start + 1:
        raise AssetLoadError("table_size_bytes is inconsistent with source range")
    entry_width = _integer(
        payload["entry_width_bytes"], "entry_width_bytes", minimum=1
    )
    if entry_width != 3:
        raise AssetLoadError("dungeon chest data entry_width_bytes must be 3")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if table_size != count * entry_width:
        raise AssetLoadError("table_size_bytes is inconsistent with entry count")

    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != count:
        raise AssetLoadError("entry_count does not match the chest data entries")
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _DUNGEON_CHEST_DATA_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(f"{context}.table_index must be {expected_index}")
        candidate_offset = _integer(
            entry["candidate_entry_offset"],
            f"{context}.candidate_entry_offset",
            minimum=0,
        )
        expected_offset = start + expected_index * entry_width
        if candidate_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.candidate_entry_offset must be {expected_offset:#x}"
            )
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        expression = _string(entry["expression"], f"{context}.expression")
        if _DUNGEON_CHEST_LITERAL_RE.fullmatch(expression) is None:
            raise AssetLoadError(f"{context}.expression must be a six-digit hex literal")
        literal = _integer(entry["literal_value"], f"{context}.literal_value", minimum=0)
        if literal > 0xFFFFFF:
            raise AssetLoadError(f"{context}.literal_value must fit in 24 bits")
        if int(expression[1:], 16) != literal:
            raise AssetLoadError(f"{context}.literal_value does not match expression")
        item_value = _integer(entry["item_value"], f"{context}.item_value", minimum=0)
        if item_value > 0xFF or item_value != ((literal >> 16) & 0xFF):
            raise AssetLoadError(f"{context}.item_value does not match the top byte")
        room_value = _integer(entry["room_value"], f"{context}.room_value", minimum=0)
        if room_value > 0x7FFF or room_value != (literal & 0x7FFF):
            raise AssetLoadError(f"{context}.room_value does not match the low 15 bits")
        is_big_chest = _boolean(entry["is_big_chest"], f"{context}.is_big_chest")
        if is_big_chest is not (bool(literal & 0x8000)):
            raise AssetLoadError(f"{context}.is_big_chest does not match bit 15")
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(evidence, _DUNGEON_CHEST_DATA_EVIDENCE_KEYS, "evidence")
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read",
        "source_range_offsets_verified",
        "item_value_names_resolved",
        "room_values_verified_against_rom",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")



def _validate_shop_item_handlers_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _SHOP_ITEM_HANDLERS_TOP_KEYS, "shop item handlers export")
    if payload["format"] != SHOP_ITEM_HANDLERS_FORMAT:
        raise AssetLoadError("shop item handlers has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported shop item handlers format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    if _string(payload["source_file"], "source_file") != "sprite_shopkeeper.asm":
        raise AssetLoadError("shop item handlers source_file must be 'sprite_shopkeeper.asm'")
    revision = _string(payload["source_revision"], "source_revision")
    if _string(payload["dispatch_routine_label"], "dispatch_routine_label") != "Sprite_ShopKeeper":
        raise AssetLoadError("dispatch_routine_label must be 'Sprite_ShopKeeper'")
    dispatch_range = _string(
        payload["dispatch_routine_source_range_annotation"],
        "dispatch_routine_source_range_annotation",
    )
    if _SHOP_ITEM_RANGE_RE.fullmatch(dispatch_range) is None:
        raise AssetLoadError("dispatch routine range annotation is malformed")
    if payload["dispatch_table_file_offset"] is not None:
        raise AssetLoadError("dispatch_table_file_offset must be null because its exact offset is not established")
    if _boolean(payload["dispatch_table_offset_established"], "dispatch_table_offset_established") is not False:
        raise AssetLoadError("dispatch_table_offset_established must be false")
    dispatch_count = _integer(payload["dispatch_entry_count"], "dispatch_entry_count", minimum=1)
    if dispatch_count != 14:
        raise AssetLoadError("dispatch_entry_count must be 14")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if count != 7:
        raise AssetLoadError("entry_count must be 7 for the standard shopkeeper purchase handlers")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != count:
        raise AssetLoadError("entry_count does not match purchase handler entries")

    expected_variant_ids = tuple(range(7, 14))
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _SHOP_ITEM_HANDLERS_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(f"{context}.table_index must be {expected_index}")
        variant_id = _integer(entry["shopkeeper_variant_id"], f"{context}.shopkeeper_variant_id", minimum=0)
        if variant_id != expected_variant_ids[expected_index]:
            raise AssetLoadError(
                f"{context}.shopkeeper_variant_id must be {expected_variant_ids[expected_index]}"
            )
        _identifier(entry["handler_label"], f"{context}.handler_label")
        address = _string(
            entry["source_handler_address_annotation"],
            f"{context}.source_handler_address_annotation",
        )
        if _SHOP_ITEM_ADDRESS_RE.fullmatch(address) is None:
            raise AssetLoadError(f"{context}.source_handler_address_annotation must be a four-digit address comment")
        dispatch_comment = _string(entry["source_dispatch_comment"], f"{context}.source_dispatch_comment")
        comment_match = _SHOP_ITEM_DISPATCH_COMMENT_RE.fullmatch(dispatch_comment)
        if comment_match is None:
            raise AssetLoadError(f"{context}.source_dispatch_comment is malformed")
        if int(comment_match.group("selector"), 16) != variant_id:
            raise AssetLoadError(f"{context}.source_dispatch_comment selector does not match shopkeeper_variant_id")
        if comment_match.group("address").upper() != address:
            raise AssetLoadError(f"{context}.source_dispatch_comment address does not match annotation")
        _string(entry["source_handler_range_annotation"], f"{context}.source_handler_range_annotation")
        if _SHOP_ITEM_RANGE_RE.fullmatch(entry["source_handler_range_annotation"]) is None:
            raise AssetLoadError(f"{context}.source_handler_range_annotation is malformed")
        for field in (
            "source_dispatch_line",
            "source_handler_label_line",
            "price_low_source_line",
            "price_high_source_line",
            "payment_call_source_line",
            "receipt_selector_source_line",
            "receipt_call_source_line",
        ):
            _integer(entry[field], f"{context}.{field}", minimum=1)

        low_expr = _string(entry["price_low_expression"], f"{context}.price_low_expression")
        high_expr = _string(entry["price_high_expression"], f"{context}.price_high_expression")
        if _SHOP_ITEM_BYTE_RE.fullmatch(low_expr) is None or _SHOP_ITEM_BYTE_RE.fullmatch(high_expr) is None:
            raise AssetLoadError(f"{context} price expressions must be two-digit hex bytes")
        low = int(low_expr[1:], 16)
        high = int(high_expr[1:], 16)
        price = _integer(entry["price_value"], f"{context}.price_value", minimum=0)
        if price != ((high << 8) | low):
            raise AssetLoadError(f"{context}.price_value does not match A/Y byte expressions")
        if not 1 <= price <= 0xFFFF:
            raise AssetLoadError(f"{context}.price_value must fit in a nonzero 16-bit price")

        receipt_expr = _string(entry["receipt_index_expression"], f"{context}.receipt_index_expression")
        if _SHOP_ITEM_BYTE_RE.fullmatch(receipt_expr) is None:
            raise AssetLoadError(f"{context}.receipt_index_expression must be a two-digit hex byte")
        receipt_index = _integer(entry["receipt_item_index"], f"{context}.receipt_item_index", minimum=0)
        if int(receipt_expr[1:], 16) != receipt_index:
            raise AssetLoadError(f"{context}.receipt_item_index does not match receipt_index_expression")
        if receipt_index > 0xFF:
            raise AssetLoadError(f"{context}.receipt_item_index must fit in one byte")
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(evidence, _SHOP_ITEM_HANDLERS_EVIDENCE_KEYS, "evidence")
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read",
        "dispatch_table_offset_established",
        "handler_address_annotations_verified",
        "price_behavior_runtime_verified",
        "receipt_item_names_resolved",
        "room_specific_shop_stock_resolved",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")



def _validate_potion_shop_transactions_export(payload: dict[str, Any]) -> None:
    _exact_keys(
        payload,
        _POTION_SHOP_TRANSACTIONS_TOP_KEYS,
        "potion-shop transactions export",
    )
    if payload["format"] != POTION_SHOP_TRANSACTIONS_FORMAT:
        raise AssetLoadError("potion-shop transactions has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported potion-shop transactions format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    if _string(payload["source_file"], "source_file") != "sprite_potion_shop.asm":
        raise AssetLoadError(
            "potion-shop transactions source_file must be 'sprite_potion_shop.asm'"
        )
    revision = _string(payload["source_revision"], "source_revision")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if count != 3:
        raise AssetLoadError("potion-shop transactions entry_count must be 3")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != count:
        raise AssetLoadError("entry_count does not match potion-shop transactions entries")

    expected_handlers = (
        "Sprite_GreenPotionItem",
        "Sprite_BluePotionItem",
        "Sprite_RedPotionItem",
    )
    expected_receipt_indexes = (0x2F, 0x30, 0x2E)
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _POTION_SHOP_TRANSACTION_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(f"{context}.table_index must be {expected_index}")
        handler = _identifier(entry["handler_label"], f"{context}.handler_label")
        if handler != expected_handlers[expected_index]:
            raise AssetLoadError(
                f"{context}.handler_label must be {expected_handlers[expected_index]!r}"
            )

        range_annotation = _string(
            entry["source_handler_range_annotation"],
            f"{context}.source_handler_range_annotation",
        )
        if _POTION_SHOP_RANGE_RE.fullmatch(range_annotation) is None:
            raise AssetLoadError(
                f"{context}.source_handler_range_annotation is malformed"
            )
        for field in (
            "source_handler_label_line",
            "price_compare_source_line",
            "price_deduction_source_line",
            "receipt_selector_source_line",
            "receipt_call_source_line",
            "empty_bottle_check_source_line",
        ):
            _integer(entry[field], f"{context}.{field}", minimum=1)

        balance_address = _string(
            entry["rupee_balance_address_expression"],
            f"{context}.rupee_balance_address_expression",
        )
        if _POTION_SHOP_ADDRESS_RE.fullmatch(balance_address) is None:
            raise AssetLoadError(
                f"{context}.rupee_balance_address_expression must be a six-digit address"
            )
        if balance_address.upper() != "$7EF360":
            raise AssetLoadError(
                f"{context}.rupee_balance_address_expression must preserve $7EF360"
            )

        compare_expression = _string(
            entry["price_compare_expression"], f"{context}.price_compare_expression"
        )
        deduction_expression = _string(
            entry["price_deduction_expression"], f"{context}.price_deduction_expression"
        )
        if (
            _POTION_SHOP_WORD_RE.fullmatch(compare_expression) is None
            or _POTION_SHOP_WORD_RE.fullmatch(deduction_expression) is None
        ):
            raise AssetLoadError(
                f"{context} price compare/deduction expressions must be four-digit hex words"
            )
        if compare_expression.upper() != deduction_expression.upper():
            raise AssetLoadError(
                f"{context} price compare literal does not match deduction literal"
            )
        price = _integer(entry["price_value"], f"{context}.price_value", minimum=1)
        if price != int(compare_expression[1:], 16):
            raise AssetLoadError(f"{context}.price_value does not match price expression")
        if price > 0xFFFF:
            raise AssetLoadError(f"{context}.price_value must fit in 16 bits")

        receipt_expression = _string(
            entry["receipt_index_expression"], f"{context}.receipt_index_expression"
        )
        if _POTION_SHOP_BYTE_RE.fullmatch(receipt_expression) is None:
            raise AssetLoadError(
                f"{context}.receipt_index_expression must be a two-digit hex byte"
            )
        receipt_index = _integer(
            entry["receipt_item_index"], f"{context}.receipt_item_index", minimum=0
        )
        if receipt_index != int(receipt_expression[1:], 16):
            raise AssetLoadError(
                f"{context}.receipt_item_index does not match receipt_index_expression"
            )
        if receipt_index != expected_receipt_indexes[expected_index]:
            raise AssetLoadError(
                f"{context}.receipt_item_index must be {expected_receipt_indexes[expected_index]:#04x}"
            )
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(
        evidence,
        _POTION_SHOP_TRANSACTIONS_EVIDENCE_KEYS,
        "potion-shop transactions evidence",
    )
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read",
        "price_behavior_runtime_verified",
        "source_range_annotations_verified",
        "receipt_item_names_resolved",
        "room_specific_shop_stock_resolved",
        "canonical_item_ids_resolved",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")



def _validate_special_shop_transactions_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _SPECIAL_SHOP_TRANSACTIONS_TOP_KEYS, "special-shop transactions export")
    if payload["format"] != SPECIAL_SHOP_TRANSACTIONS_FORMAT:
        raise AssetLoadError("special-shop transactions has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported special-shop transactions format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    revision = _string(payload["source_revision"], "source_revision")
    source_file = _string(payload["source_file"], "source_file")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if count != 3:
        raise AssetLoadError("special-shop transactions entry_count must be 3")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != count:
        raise AssetLoadError("entry_count does not match special-shop transaction entries")

    expected = (
        ("Bomb Shop Bomb", "bomb-shop", "sprite_bomb_shop_entity.asm",
         "Sprite_BombShopBomb", "Sprite_BombShopBomb", "shopkeeper-a-y-registers",
         "ShopItem_HandleReceipt", 0x28, "$0F6190-$0F61DE JUMP LOCATION"),
        ("Bomb Shop Super Bomb", "bomb-shop", "sprite_bomb_shop_entity.asm",
         "Sprite_BombShopSuperBomb", "Sprite_BombShopSuperBomb", "shopkeeper-a-y-registers",
         "special-bomb-flag-and-tagalong", None, "$0F61DF-$0F6215 JUMP LOCATION"),
        ("Bottle Vendor Bottle Sale", "bottle-vendor", "sprite_bottle_vendor.asm",
         "BottleVendor_SellingBottle", "BottleVendor_GiveBottle",
         "wallet-balance-compare-and-deduction", "Link_ReceiveItem", 0x16,
         "$02EAED-$02EB16 JUMP LOCATION"),
    )
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _SPECIAL_SHOP_TRANSACTION_ENTRY_KEYS, context)
        (expected_label, expected_shop, expected_file, expected_handler, expected_reward,
         expected_mode, expected_receipt_method, expected_receipt_index, _expected_range) = expected[expected_index]
        if _integer(entry["table_index"], f"{context}.table_index", minimum=0) != expected_index:
            raise AssetLoadError(f"{context}.table_index must be {expected_index}")
        fixed_strings = {
            "transaction_label": expected_label,
            "shop_type": expected_shop,
            "source_file": expected_file,
            "source_handler_label": expected_handler,
            "reward_handler_label": expected_reward,
            "price_mode": expected_mode,
            "receipt_method": expected_receipt_method,
        }
        for field, expected_value in fixed_strings.items():
            if _string(entry[field], f"{context}.{field}") != expected_value:
                raise AssetLoadError(f"{context}.{field} must be {expected_value!r}")
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")
        for field in ("source_handler_range_annotation", "reward_handler_range_annotation"):
            value = _string(entry[field], f"{context}.{field}")
            if _SPECIAL_SHOP_RANGE_RE.fullmatch(value) is None:
                raise AssetLoadError(f"{context}.{field} is malformed")
        for field in ("source_handler_label_line", "reward_handler_label_line"):
            _integer(entry[field], f"{context}.{field}", minimum=1)

        price = _integer(entry["price_value"], f"{context}.price_value", minimum=1)
        if price != 100:
            raise AssetLoadError(f"{context}.price_value must be 100")

        nullable_int_fields = (
            "price_low_source_line", "price_high_source_line", "price_compare_source_line",
            "price_deduction_source_line", "payment_call_source_line",
            "receipt_selector_source_line", "receipt_call_source_line",
            "source_item_annotation_line", "reward_flag_source_line", "tagalong_spawn_source_line",
        )
        for field in nullable_int_fields:
            if entry[field] is not None:
                _integer(entry[field], f"{context}.{field}", minimum=1)
        nullable_string_fields = (
            "price_low_expression", "price_high_expression", "price_compare_expression",
            "price_deduction_expression", "rupee_balance_address_expression",
            "receipt_index_expression", "source_item_annotation",
            "reward_flag_address_expression", "reward_flag_value_expression", "source_reward_comment",
        )
        for field in nullable_string_fields:
            if entry[field] is not None:
                _string(entry[field], f"{context}.{field}")

        if expected_index < 2:
            low = _string(entry["price_low_expression"], f"{context}.price_low_expression")
            high = _string(entry["price_high_expression"], f"{context}.price_high_expression")
            if _SPECIAL_SHOP_BYTE_RE.fullmatch(low) is None or _SPECIAL_SHOP_BYTE_RE.fullmatch(high) is None:
                raise AssetLoadError(f"{context} A/Y price expressions must be two-digit hex bytes")
            if ((int(high[1:], 16) << 8) | int(low[1:], 16)) != price:
                raise AssetLoadError(f"{context}.price_value does not match A/Y price expressions")
            if (low.upper(), high.upper()) != ("$64", "$00"):
                raise AssetLoadError(f"{context} Bomb Shop price registers must preserve $64/$00")
            if entry["price_compare_expression"] is not None or entry["price_deduction_expression"] is not None:
                raise AssetLoadError(f"{context} must not use Bottle Vendor price fields")
            if entry["payment_call_source_line"] is None:
                raise AssetLoadError(f"{context}.payment_call_source_line is required")
        else:
            compare = _string(entry["price_compare_expression"], f"{context}.price_compare_expression")
            deduction = _string(entry["price_deduction_expression"], f"{context}.price_deduction_expression")
            if _SPECIAL_SHOP_WORD_RE.fullmatch(compare) is None or _SPECIAL_SHOP_WORD_RE.fullmatch(deduction) is None:
                raise AssetLoadError(f"{context} compare/deduction expressions must be four-digit hex words")
            if compare.upper() != deduction.upper() or int(compare[1:], 16) != price:
                raise AssetLoadError(f"{context} Bottle Vendor compare/deduction literals do not match price")
            balance = _string(entry["rupee_balance_address_expression"], f"{context}.rupee_balance_address_expression")
            if _SPECIAL_SHOP_ADDRESS_RE.fullmatch(balance) is None or balance.upper() != "$7EF360":
                raise AssetLoadError(f"{context}.rupee_balance_address_expression must preserve $7EF360")
            if entry["price_low_expression"] is not None or entry["price_high_expression"] is not None:
                raise AssetLoadError(f"{context} must not use Bomb Shop price fields")
            if entry["source_item_annotation"] != "Bottle":
                raise AssetLoadError(f"{context}.source_item_annotation must preserve source comment Bottle")

        receipt_index = entry["receipt_item_index"]
        if expected_receipt_index is None:
            if receipt_index is not None or entry["receipt_index_expression"] is not None:
                raise AssetLoadError(f"{context} Super Bomb reward must not claim a receipt selector")
            if entry["receipt_selector_source_line"] is not None or entry["receipt_call_source_line"] is not None:
                raise AssetLoadError(f"{context} Super Bomb reward must not claim a receipt call")
            if entry["reward_flag_address_expression"] != "$7EF3CC":
                raise AssetLoadError(f"{context} Super Bomb flag address must be $7EF3CC")
            if entry["reward_flag_value_expression"] != "$0D":
                raise AssetLoadError(f"{context} Super Bomb flag value must be $0D")
            if entry["source_reward_comment"] != "Super Bomb sprite":
                raise AssetLoadError(f"{context} must preserve the Super Bomb source comment")
            if entry["reward_flag_source_line"] is None or entry["tagalong_spawn_source_line"] is None:
                raise AssetLoadError(f"{context} Super Bomb flag/tagalong source lines are required")
        else:
            if receipt_index != expected_receipt_index:
                raise AssetLoadError(f"{context}.receipt_item_index must be {expected_receipt_index:#04x}")
            expr = _string(entry["receipt_index_expression"], f"{context}.receipt_index_expression")
            if _SPECIAL_SHOP_BYTE_RE.fullmatch(expr) is None or int(expr[1:], 16) != receipt_index:
                raise AssetLoadError(f"{context}.receipt_index_expression does not match receipt_item_index")
            if entry["receipt_selector_source_line"] is None or entry["receipt_call_source_line"] is None:
                raise AssetLoadError(f"{context} receipt selector/call source lines are required")

    expected_source_file = ";".join(sorted({entry["source_file"] for entry in entries}))
    if source_file != expected_source_file:
        raise AssetLoadError("source_file must be the sorted semicolon-joined set of entry source files")

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(evidence, _SPECIAL_SHOP_TRANSACTIONS_EVIDENCE_KEYS, "evidence")
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read", "source_range_annotations_verified", "price_behavior_runtime_verified",
        "receipt_item_names_resolved", "room_specific_shop_stock_resolved",
        "canonical_item_ids_resolved", "special_bomb_reward_runtime_verified",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")



def _validate_paid_overworld_interactions_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _PAID_OVERWORLD_TOP_KEYS, "paid-overworld interactions export")
    if payload["format"] != PAID_OVERWORLD_INTERACTIONS_FORMAT:
        raise AssetLoadError("paid-overworld interactions export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported paid-overworld interactions format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    revision = _string(payload["source_revision"], "source_revision")
    expected_sources = [
        "sprite_archery_game_guy.asm",
        "sprite_digging_game_guy.asm",
        "sprite_fortune_teller.asm",
        "sprite_kiki.asm",
        "sprite_ponds.asm",
        "sprite_zora_king.asm",
    ]
    source_files = payload["source_files"]
    if source_files != expected_sources:
        raise AssetLoadError("source_files must list the six pinned paid-interaction source files")
    count = _integer(payload["interaction_count"], "interaction_count", minimum=1)
    if count != 7:
        raise AssetLoadError("interaction_count must be 7")
    interactions = payload["interactions"]
    if not isinstance(interactions, list) or len(interactions) != count:
        raise AssetLoadError("interaction_count does not match interactions")

    expected_ids = (
        "fortune-teller-reading",
        "digging-game-entry",
        "zora-king-flippers",
        "kiki-follow-fee",
        "kiki-palace-access-fee",
        "archery-game-entry",
        "lake-hylia-fairy-donation",
    )
    seen_ids: set[str] = set()
    for index, raw_entry in enumerate(interactions):
        context = f"interactions[{index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _PAID_OVERWORLD_INTERACTION_KEYS, context)
        interaction_id = _string(entry["interaction_id"], f"{context}.interaction_id")
        if interaction_id != expected_ids[index] or interaction_id in seen_ids:
            raise AssetLoadError(f"{context}.interaction_id must be {expected_ids[index]!r}")
        seen_ids.add(interaction_id)
        _string(entry["actor_label"], f"{context}.actor_label")
        _string(entry["interaction_kind"], f"{context}.interaction_kind")
        source_file = _string(entry["source_file"], f"{context}.source_file")
        if source_file not in expected_sources:
            raise AssetLoadError(f"{context}.source_file is not a registered paid-interaction source")
        _source_label(entry["source_label"], f"{context}.source_label")
        annotation = _string(entry["source_range_annotation"], f"{context}.source_range_annotation")
        if _PAID_OVERWORLD_RANGE_RE.fullmatch(annotation) is None:
            raise AssetLoadError(f"{context}.source_range_annotation is malformed")
        _integer(entry["source_annotation_line"], f"{context}.source_annotation_line", minimum=1)
        fee_model = _string(entry["fee_model"], f"{context}.fee_model")
        if fee_model not in {"fixed", "selected-price-table"}:
            raise AssetLoadError(f"{context}.fee_model is unsupported")
        values = entry["fee_values"]
        expressions = entry["fee_expressions"]
        if not isinstance(values, list) or not values or not isinstance(expressions, list):
            raise AssetLoadError(f"{context} fee values and expressions must be non-empty arrays")
        if len(values) != len(expressions):
            raise AssetLoadError(f"{context} fee expression count does not match fee value count")
        parsed_values: list[int] = []
        for fee_index, (raw_value, raw_expression) in enumerate(zip(values, expressions, strict=True)):
            fee_context = f"{context}.fee_values[{fee_index}]"
            fee_value = _integer(raw_value, fee_context, minimum=1)
            expression = _string(raw_expression, f"{context}.fee_expressions[{fee_index}]")
            if _PAID_OVERWORLD_FEE_EXPRESSION_RE.fullmatch(expression) is None:
                raise AssetLoadError(f"{context}.fee_expressions[{fee_index}] is malformed")
            parsed_expression = int(expression[1:], 16) if expression.startswith("$") else int(expression)
            if parsed_expression != fee_value:
                raise AssetLoadError(f"{fee_context} does not match its source expression")
            parsed_values.append(fee_value)
        fee_table = entry["fee_table_label"]
        if fee_model == "fixed":
            if len(values) != 1 or fee_table is not None:
                raise AssetLoadError(f"{context} fixed fee must have one value and no fee table")
        else:
            if len(values) < 2 or not isinstance(fee_table, str) or not fee_table:
                raise AssetLoadError(f"{context} selected-price-table fee requires multiple values and a table label")
        for field in ("fee_source_lines", "payment_source_lines", "outcome_source_lines"):
            raw_lines = entry[field]
            if not isinstance(raw_lines, list) or not raw_lines:
                raise AssetLoadError(f"{context}.{field} must be a non-empty array")
            for line_index, line in enumerate(raw_lines):
                _integer(line, f"{context}.{field}[{line_index}]", minimum=1)
        _string(entry["outcome_label"], f"{context}.outcome_label")
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")

    reward_tables = payload["reward_tables"]
    if not isinstance(reward_tables, list) or len(reward_tables) != 2:
        raise AssetLoadError("reward_tables must contain the digging dispatch and basic-item pool")
    expected_table_ids = (
        ("digging-game-random-reward-dispatch", "jump-table", 8),
        ("digging-game-basic-reward-pool", "item-pool", 4),
    )
    for table_index, raw_table in enumerate(reward_tables):
        context = f"reward_tables[{table_index}]"
        table = _object(raw_table, context)
        _exact_keys(table, _PAID_OVERWORLD_DISPATCH_TABLE_KEYS, context)
        expected_id, expected_kind, expected_count = expected_table_ids[table_index]
        if table["table_id"] != expected_id or table["table_kind"] != expected_kind:
            raise AssetLoadError(f"{context} must describe {expected_id!r}")
        if _string(table["source_file"], f"{context}.source_file") != "sprite_digging_game_guy.asm":
            raise AssetLoadError(f"{context}.source_file must be the Digging Game source")
        _source_label(table["source_label"], f"{context}.source_label")
        annotation = _string(table["source_range_annotation"], f"{context}.source_range_annotation")
        if _PAID_OVERWORLD_RANGE_RE.fullmatch(annotation) is None:
            raise AssetLoadError(f"{context}.source_range_annotation is malformed")
        _integer(table["source_annotation_line"], f"{context}.source_annotation_line", minimum=1)
        entry_count = _integer(table["entry_count"], f"{context}.entry_count", minimum=1)
        entries = table["entries"]
        if entry_count != expected_count or not isinstance(entries, list) or len(entries) != entry_count:
            raise AssetLoadError(f"{context}.entry_count must be {expected_count}")
        for entry_index, raw_entry in enumerate(entries):
            entry_context = f"{context}.entries[{entry_index}]"
            item = _object(raw_entry, entry_context)
            if table_index == 0:
                _exact_keys(item, _PAID_OVERWORLD_DISPATCH_ENTRY_KEYS, entry_context)
                address = _string(item["source_address_annotation"], f"{entry_context}.source_address_annotation")
                if _PAID_OVERWORLD_ADDRESS_RE.fullmatch(address) is None:
                    raise AssetLoadError(f"{entry_context}.source_address_annotation is malformed")
                _string(item["handler_label"], f"{entry_context}.handler_label")
                _string(item["source_comment"], f"{entry_context}.source_comment")
            else:
                _exact_keys(item, _PAID_OVERWORLD_POOL_ENTRY_KEYS, entry_context)
                expression = _string(item["expression"], f"{entry_context}.expression")
                if _PAID_OVERWORLD_BYTE_RE.fullmatch(expression) is None:
                    raise AssetLoadError(f"{entry_context}.expression must be a two-digit hex byte")
                _string(item["source_comment"], f"{entry_context}.source_comment")
            slot = _integer(item["table_index"], f"{entry_context}.table_index", minimum=0)
            if slot != entry_index:
                raise AssetLoadError(f"{entry_context}.table_index must be {entry_index}")
            _integer(item["source_line"], f"{entry_context}.source_line", minimum=1)
        if _string(table["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")

    reward_gates = payload["reward_gates"]
    if not isinstance(reward_gates, list) or len(reward_gates) != 1:
        raise AssetLoadError("reward_gates must contain the Digging Game heart-piece gate")
    gate = _object(reward_gates[0], "reward_gates[0]")
    _exact_keys(gate, _PAID_OVERWORLD_GATE_KEYS, "reward_gates[0]")
    if gate["gate_id"] != "digging-game-heart-piece":
        raise AssetLoadError("reward_gates[0].gate_id must be 'digging-game-heart-piece'")
    if _string(gate["source_file"], "reward_gates[0].source_file") != "sprite_digging_game_guy.asm":
        raise AssetLoadError("heart-piece gate source_file must be the Digging Game source")
    _source_label(gate["source_label"], "reward_gates[0].source_label")
    annotation = _string(gate["source_range_annotation"], "reward_gates[0].source_range_annotation")
    if _PAID_OVERWORLD_RANGE_RE.fullmatch(annotation) is None:
        raise AssetLoadError("heart-piece gate source_range_annotation is malformed")
    _integer(gate["source_annotation_line"], "reward_gates[0].source_annotation_line", minimum=1)
    gate_lines = gate["condition_source_lines"]
    gate_expressions = gate["condition_expressions"]
    if not isinstance(gate_lines, list) or len(gate_lines) != 4 or not isinstance(gate_expressions, list) or len(gate_expressions) != 4:
        raise AssetLoadError("heart-piece gate must preserve four source condition/effect lines")
    for index, line in enumerate(gate_lines):
        _integer(line, f"reward_gates[0].condition_source_lines[{index}]", minimum=1)
        _string(gate_expressions[index], f"reward_gates[0].condition_expressions[{index}]")
    if _integer(gate["minimum_hole_count"], "reward_gates[0].minimum_hole_count", minimum=1) != 25:
        raise AssetLoadError("Digging Game heart-piece threshold must remain 25 holes")
    if gate["required_state_expression"] != "$7FFE00 == 0":
        raise AssetLoadError("heart-piece gate required_state_expression is unexpected")
    if gate["random_mask_expression"] != "#$03":
        raise AssetLoadError("heart-piece gate random_mask_expression is unexpected")
    if _integer(gate["successful_random_value"], "reward_gates[0].successful_random_value", minimum=0) != 0:
        raise AssetLoadError("heart-piece gate successful_random_value must be zero")
    _string(gate["reward_flag_write_expression"], "reward_gates[0].reward_flag_write_expression")
    if _string(gate["source_revision"], "reward_gates[0].source_revision") != revision:
        raise AssetLoadError("heart-piece gate source_revision does not match top-level source_revision")

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(evidence, _PAID_OVERWORLD_EVIDENCE_KEYS, "evidence")
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read",
        "source_range_annotations_verified",
        "fee_behavior_runtime_verified",
        "reward_probability_runtime_verified",
        "item_value_names_resolved",
        "payment_semantics_runtime_verified",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")


def _validate_mixed_data_table_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _MIXED_DATA_TABLE_TOP_KEYS, "mixed data-table export")
    if payload["format"] != MIXED_DATA_TABLE_FORMAT:
        raise AssetLoadError("mixed data-table export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != 1:
        raise AssetLoadError(
            f"unsupported mixed data-table format version {version}; this loader supports 1"
        )

    _string(payload["source_file"], "source_file")
    _string(payload["source_revision"], "source_revision")
    _source_label(payload["table_label"], "table_label")
    table_start = _integer(payload["table_file_offset"], "table_file_offset", minimum=0)
    record_count = _integer(payload["record_count"], "record_count", minimum=1)
    byte_count = _integer(payload["byte_count"], "byte_count", minimum=1)
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise AssetLoadError("records must be a non-empty array")
    if record_count != len(records):
        raise AssetLoadError(
            f"record_count is {record_count}, but records contains {len(records)} items"
        )

    width_by_directive = _DATA_DIRECTIVE_WIDTHS
    cursor = table_start
    counted_bytes = 0
    for expected_record_index, raw_record in enumerate(records):
        context = f"records[{expected_record_index}]"
        record = _object(raw_record, context)
        _exact_keys(record, _MIXED_DATA_RECORD_KEYS, context)
        record_index = _integer(record["record_index"], f"{context}.record_index", minimum=0)
        if record_index != expected_record_index:
            raise AssetLoadError(
                f"{context}.record_index must be {expected_record_index}, got {record_index}"
            )
        record_offset = _integer(
            record["record_file_offset"], f"{context}.record_file_offset", minimum=0
        )
        if record_offset != cursor:
            raise AssetLoadError(
                f"{context}.record_file_offset must be {cursor}, got {record_offset}"
            )
        record_line = _integer(record["source_line"], f"{context}.source_line", minimum=1)
        source_label = record["source_label"]
        if source_label is not None:
            _source_label(source_label, f"{context}.source_label")
        record_byte_length = _integer(
            record["byte_length"], f"{context}.byte_length", minimum=1
        )
        fields = record["fields"]
        if not isinstance(fields, list) or not fields:
            raise AssetLoadError(f"{context}.fields must be a non-empty array")
        record_start = cursor

        for expected_field_index, raw_field in enumerate(fields):
            field_context = f"{context}.fields[{expected_field_index}]"
            field = _object(raw_field, field_context)
            _exact_keys(field, _MIXED_DATA_FIELD_KEYS, field_context)
            field_index = _integer(
                field["field_index"], f"{field_context}.field_index", minimum=0
            )
            if field_index != expected_field_index:
                raise AssetLoadError(
                    f"{field_context}.field_index must be {expected_field_index}, got {field_index}"
                )
            field_offset = _integer(
                field["field_file_offset"], f"{field_context}.field_file_offset", minimum=0
            )
            if field_offset != cursor:
                raise AssetLoadError(
                    f"{field_context}.field_file_offset must be {cursor}, got {field_offset}"
                )
            field_line = _integer(
                field["source_line"], f"{field_context}.source_line", minimum=1
            )
            if field_line != record_line:
                raise AssetLoadError(
                    f"{field_context}.source_line must match its parent record"
                )
            directive = _string(field["directive"], f"{field_context}.directive")
            if directive not in width_by_directive:
                raise AssetLoadError(f"{field_context}.directive must be db, dw, or dl")
            width = _integer(field["entry_width"], f"{field_context}.entry_width", minimum=1)
            if width != width_by_directive[directive]:
                raise AssetLoadError(
                    f"{field_context}.entry_width does not match directive {directive!r}"
                )
            entry_count = _integer(
                field["entry_count"], f"{field_context}.entry_count", minimum=1
            )
            entries = field["entries"]
            if not isinstance(entries, list) or not entries:
                raise AssetLoadError(f"{field_context}.entries must be a non-empty array")
            if entry_count != len(entries):
                raise AssetLoadError(
                    f"{field_context}.entry_count is {entry_count}, "
                    f"but entries contains {len(entries)} items"
                )
            literal_limit = 1 << (8 * width)

            for expected_entry_index, raw_entry in enumerate(entries):
                entry_context = f"{field_context}.entries[{expected_entry_index}]"
                entry = _object(raw_entry, entry_context)
                _exact_keys(entry, _MIXED_DATA_ENTRY_KEYS, entry_context)
                entry_index = _integer(
                    entry["entry_index"], f"{entry_context}.entry_index", minimum=0
                )
                if entry_index != expected_entry_index:
                    raise AssetLoadError(
                        f"{entry_context}.entry_index must be {expected_entry_index}, "
                        f"got {entry_index}"
                    )
                entry_offset = _integer(
                    entry["entry_file_offset"], f"{entry_context}.entry_file_offset", minimum=0
                )
                if entry_offset != cursor:
                    raise AssetLoadError(
                        f"{entry_context}.entry_file_offset must be {cursor}, got {entry_offset}"
                    )
                _string(entry["expression"], f"{entry_context}.expression")
                literal_value = _nullable_integer(
                    entry["literal_value"], f"{entry_context}.literal_value", minimum=0
                )
                if literal_value is not None and literal_value >= literal_limit:
                    raise AssetLoadError(
                        f"{entry_context}.literal_value does not fit {width}-byte directive"
                    )
                cursor += width

        if cursor - record_start != record_byte_length:
            raise AssetLoadError(
                f"{context}.byte_length is inconsistent with its field widths"
            )
        counted_bytes += record_byte_length

    if counted_bytes != byte_count:
        raise AssetLoadError(
            f"byte_count is {byte_count}, but records contain {counted_bytes} bytes"
        )



def _validate_item_receipt_layout_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _ITEM_RECEIPT_LAYOUT_TOP_KEYS, "item-receipt layout")
    if payload["format"] != ITEM_RECEIPT_LAYOUT_FORMAT:
        raise AssetLoadError("item-receipt layout has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != 1:
        raise AssetLoadError(
            f"unsupported item-receipt layout version {version}; this loader supports 1"
        )
    if _string(payload["source_file"], "source_file") != "ancilla_init.asm":
        raise AssetLoadError("item-receipt layout source_file must be 'ancilla_init.asm'")
    _string(payload["source_revision"], "source_revision")
    if _string(payload["parent_label"], "parent_label") != "Pool_AddReceiveItem":
        raise AssetLoadError("item-receipt layout parent_label must be 'Pool_AddReceiveItem'")

    entry_count = _integer(payload["entry_count"], "entry_count", minimum=1)
    entries = payload["entries"]
    if not isinstance(entries, list) or entry_count != len(entries):
        raise AssetLoadError("item-receipt layout entry_count does not match entries")
    if entry_count != _ITEM_RECEIPT_LAYOUT_ENTRY_COUNT:
        raise AssetLoadError(
            f"item-receipt layout must contain {_ITEM_RECEIPT_LAYOUT_ENTRY_COUNT} entries"
        )

    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _ITEM_RECEIPT_LAYOUT_ROW_KEYS, context)
        table_index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if table_index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {table_index}"
            )

        for field, (expected_label, start_offset, width) in _ITEM_RECEIPT_LAYOUT_ARRAYS.items():
            cell_context = f"{context}.{field}"
            cell = _object(entry[field], cell_context)
            _exact_keys(cell, _ITEM_RECEIPT_LAYOUT_CELL_KEYS, cell_context)
            source_label = _source_label(cell["source_label"], f"{cell_context}.source_label")
            if source_label != expected_label:
                raise AssetLoadError(
                    f"{cell_context}.source_label must be {expected_label!r}"
                )
            offset = _integer(
                cell["entry_file_offset"],
                f"{cell_context}.entry_file_offset",
                minimum=0,
            )
            expected_offset = start_offset + expected_index * width
            if offset != expected_offset:
                raise AssetLoadError(
                    f"{cell_context}.entry_file_offset must be {expected_offset}, got {offset}"
                )
            _string(cell["expression"], f"{cell_context}.expression")
            value = _nullable_integer(
                cell["literal_value"], f"{cell_context}.literal_value", minimum=0
            )
            if value is not None and value >= 1 << (8 * width):
                raise AssetLoadError(
                    f"{cell_context}.literal_value does not fit its {width}-byte table"
                )

    mask_count = _integer(
        payload["dungeon_mask_count"], "dungeon_mask_count", minimum=1
    )
    masks = payload["dungeon_masks"]
    if not isinstance(masks, list) or mask_count != len(masks):
        raise AssetLoadError("dungeon_mask_count does not match dungeon_masks")
    if mask_count != _ITEM_RECEIPT_LAYOUT_MASK_COUNT:
        raise AssetLoadError(
            f"item-receipt layout must contain {_ITEM_RECEIPT_LAYOUT_MASK_COUNT} dungeon masks"
        )
    for expected_index, raw_mask in enumerate(masks):
        context = f"dungeon_masks[{expected_index}]"
        mask = _object(raw_mask, context)
        _exact_keys(mask, _ITEM_RECEIPT_LAYOUT_MASK_KEYS, context)
        table_index = _integer(mask["table_index"], f"{context}.table_index", minimum=0)
        if table_index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {table_index}"
            )
        if _source_label(mask["source_label"], f"{context}.source_label") != (
            _ITEM_RECEIPT_LAYOUT_MASK_LABEL
        ):
            raise AssetLoadError(
                f"{context}.source_label must be {_ITEM_RECEIPT_LAYOUT_MASK_LABEL!r}"
            )
        offset = _integer(mask["entry_file_offset"], f"{context}.entry_file_offset", minimum=0)
        expected_offset = (
            _ITEM_RECEIPT_LAYOUT_MASK_OFFSET
            + expected_index * _ITEM_RECEIPT_LAYOUT_MASK_WIDTH
        )
        if offset != expected_offset:
            raise AssetLoadError(
                f"{context}.entry_file_offset must be {expected_offset}, got {offset}"
            )
        _string(mask["expression"], f"{context}.expression")
        value = _nullable_integer(mask["literal_value"], f"{context}.literal_value", minimum=0)
        if value is not None and value >= 1 << (8 * _ITEM_RECEIPT_LAYOUT_MASK_WIDTH):
            raise AssetLoadError(f"{context}.literal_value does not fit a two-byte mask")

    semantic_ids_resolved = _boolean(
        payload["semantic_item_ids_resolved"], "semantic_item_ids_resolved"
    )
    if semantic_ids_resolved:
        raise AssetLoadError(
            "item-receipt layout must not claim canonical semantic item IDs are resolved"
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
_SPRITE_HANDLER_RE = re.compile(r"Sprite_[A-Za-z0-9_]+\Z")
_SPRITE_COMMENT_RE = re.compile(
    r"0x(?P<sprite_id>[0-9A-Fa-f]+)\s*-\s*\$(?P<address>[0-9A-Fa-f]+)\s*(?P<description>.*)\Z"
)
_SPRITE_PREP_HANDLER_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|\$[0-9A-Fa-f]{1,4})\Z")
_SPRITE_PREP_COMMENT_RE = re.compile(
    r"0x(?P<sprite_id>[0-9A-Fa-f]{2})\s*-\s*"
    r"(?P<address>\$[0-9A-Fa-f]{4})\s*(?P<description>.*)\Z"
)
_SPRITE_PREP_RANGE_RE = re.compile(
    r"\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+\s+JUMP LOCATION\Z", re.IGNORECASE
)


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


_SPRITE_DISPATCH_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "table_label",
    "table_file_offset",
    "table_end_offset",
    "table_size_bytes",
    "entry_width_bytes",
    "sprite_type_id_start",
    "sprite_type_id_end",
    "entry_count",
    "entries",
}
_SPRITE_DISPATCH_ENTRY_KEYS = {
    "table_index",
    "sprite_type_id",
    "pointer_entry_file_offset",
    "source_line",
    "handler_expression",
    "handler_label",
    "source_comment_sprite_type_id",
    "source_handler_address_annotation",
    "source_description",
    "source_comment",
    "source_revision",
}


def _validate_sprite_dispatch_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _SPRITE_DISPATCH_TOP_KEYS, "sprite dispatch export")
    if payload["format"] != SPRITE_DISPATCH_FORMAT:
        raise AssetLoadError("sprite dispatch export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported sprite dispatch format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    table_label = _string(payload["table_label"], "table_label")
    _identifier(table_label, "table_label")
    table_start = _integer(payload["table_file_offset"], "table_file_offset", minimum=0)
    table_end = _integer(payload["table_end_offset"], "table_end_offset", minimum=0)
    if table_end < table_start:
        raise AssetLoadError("table_end_offset precedes table_file_offset")
    table_size = _integer(payload["table_size_bytes"], "table_size_bytes", minimum=1)
    if table_size != table_end - table_start + 1:
        raise AssetLoadError("table_size_bytes is inconsistent with table offsets")
    entry_width = _integer(payload["entry_width_bytes"], "entry_width_bytes", minimum=1)
    if entry_width != 2:
        raise AssetLoadError("sprite dispatch entry_width_bytes must be 2")
    if table_size % entry_width:
        raise AssetLoadError("table_size_bytes must be divisible by entry_width_bytes")

    sprite_start = _integer(payload["sprite_type_id_start"], "sprite_type_id_start", minimum=0)
    sprite_end = _integer(payload["sprite_type_id_end"], "sprite_type_id_end", minimum=0)
    if sprite_start > 0xFFFF or sprite_end > 0xFFFF:
        raise AssetLoadError("sprite type ID range must fit in 16 bits")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if count != table_size // entry_width:
        raise AssetLoadError("entry_count is inconsistent with table size and entry width")
    if sprite_end != sprite_start + count - 1:
        raise AssetLoadError("sprite_type_id_end is inconsistent with start ID and entry count")

    entries = payload["entries"]
    if not isinstance(entries, list) or not entries:
        raise AssetLoadError("entries must be a non-empty array")
    if len(entries) != count:
        raise AssetLoadError(
            f"entry_count is {count}, but entries contains {len(entries)} records"
        )

    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _SPRITE_DISPATCH_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {index}"
            )
        sprite_id = _integer(entry["sprite_type_id"], f"{context}.sprite_type_id", minimum=0)
        expected_sprite_id = sprite_start + expected_index
        if sprite_id != expected_sprite_id:
            raise AssetLoadError(
                f"{context}.sprite_type_id must be {expected_sprite_id:#x}, got {sprite_id:#x}"
            )
        comment_sprite_id = _integer(
            entry["source_comment_sprite_type_id"],
            f"{context}.source_comment_sprite_type_id",
            minimum=0,
        )
        if comment_sprite_id != sprite_id:
            raise AssetLoadError(
                f"{context}.source_comment_sprite_type_id does not match sprite_type_id"
            )
        pointer_offset = _integer(
            entry["pointer_entry_file_offset"],
            f"{context}.pointer_entry_file_offset",
            minimum=0,
        )
        expected_offset = table_start + expected_index * entry_width
        if pointer_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.pointer_entry_file_offset must be {expected_offset}, "
                f"got {pointer_offset}"
            )
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        expression = _string(entry["handler_expression"], f"{context}.handler_expression")
        handler_label = _string(entry["handler_label"], f"{context}.handler_label")
        if _SPRITE_HANDLER_RE.fullmatch(expression) is None:
            raise AssetLoadError(
                f"{context}.handler_expression must be a Sprite_ handler label"
            )
        if handler_label != expression:
            raise AssetLoadError(f"{context}.handler_label must match handler_expression")

        source_comment = _string(entry["source_comment"], f"{context}.source_comment")
        comment_match = _SPRITE_COMMENT_RE.fullmatch(source_comment)
        if comment_match is None:
            raise AssetLoadError(f"{context}.source_comment is malformed")
        comment_address = "$" + comment_match.group("address")
        handler_address = _string(
            entry["source_handler_address_annotation"],
            f"{context}.source_handler_address_annotation",
        )
        if comment_address != handler_address:
            raise AssetLoadError(
                f"{context}.source_handler_address_annotation does not match source_comment"
            )
        if int(comment_match.group("sprite_id"), 16) != sprite_id:
            raise AssetLoadError(
                f"{context}.source_comment sprite ID does not match sprite_type_id"
            )
        description = entry["source_description"]
        if not isinstance(description, str) or description != comment_match.group("description"):
            raise AssetLoadError(
                f"{context}.source_description does not match source_comment"
            )
        entry_revision = _string(entry["source_revision"], f"{context}.source_revision")
        if entry_revision != revision:
            raise AssetLoadError(
                f"{context}.source_revision does not match top-level source_revision"
            )


_SPRITE_PREP_DISPATCH_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "routine_label",
    "routine_source_range_annotation",
    "table_file_offset",
    "table_offset_established",
    "sprite_type_id_start",
    "sprite_type_id_end",
    "entry_count",
    "entries",
    "evidence",
}
_SPRITE_PREP_DISPATCH_ENTRY_KEYS = {
    "table_index",
    "sprite_type_id",
    "source_line",
    "handler_expression",
    "handler_label",
    "source_comment_sprite_type_id",
    "source_handler_address_annotation",
    "source_description",
    "source_comment",
    "source_comment_continuations",
    "source_revision",
}
_SPRITE_PREP_DISPATCH_EVIDENCE_KEYS = {
    "source_only",
    "rom_bytes_read",
    "table_offset_established",
    "handler_address_annotations_verified",
    "runtime_behavior_verified",
}



def _validate_sprite_prep_dispatch_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _SPRITE_PREP_DISPATCH_TOP_KEYS, "sprite prep dispatch export")
    if payload["format"] != SPRITE_PREP_DISPATCH_FORMAT:
        raise AssetLoadError("sprite prep dispatch export has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported sprite prep dispatch format version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )
    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    if _identifier(payload["routine_label"], "routine_label") != "SpritePrep_Main":
        raise AssetLoadError("routine_label must be SpritePrep_Main")
    range_annotation = _string(
        payload["routine_source_range_annotation"], "routine_source_range_annotation"
    )
    if _SPRITE_PREP_RANGE_RE.fullmatch(range_annotation) is None:
        raise AssetLoadError("routine_source_range_annotation must preserve the JUMP LOCATION comment")
    if payload["table_file_offset"] is not None:
        raise AssetLoadError("table_file_offset must be null until the inline table offset is established")
    if _boolean(payload["table_offset_established"], "table_offset_established") is not False:
        raise AssetLoadError("table_offset_established must be false for this source export")

    sprite_start = _integer(payload["sprite_type_id_start"], "sprite_type_id_start", minimum=0)
    sprite_end = _integer(payload["sprite_type_id_end"], "sprite_type_id_end", minimum=0)
    if sprite_start > 0xFFFF or sprite_end > 0xFFFF:
        raise AssetLoadError("sprite type ID range must fit in 16 bits")
    count = _integer(payload["entry_count"], "entry_count", minimum=1)
    if sprite_end != sprite_start + count - 1:
        raise AssetLoadError("sprite_type_id_end is inconsistent with start ID and entry count")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != count:
        raise AssetLoadError("entry_count does not match the sprite prep entries")

    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _SPRITE_PREP_DISPATCH_ENTRY_KEYS, context)
        index = _integer(entry["table_index"], f"{context}.table_index", minimum=0)
        if index != expected_index:
            raise AssetLoadError(f"{context}.table_index must be {expected_index}")
        sprite_id = _integer(entry["sprite_type_id"], f"{context}.sprite_type_id", minimum=0)
        expected_id = sprite_start + expected_index
        if sprite_id != expected_id:
            raise AssetLoadError(f"{context}.sprite_type_id must be {expected_id:#x}")
        comment_id = _integer(
            entry["source_comment_sprite_type_id"],
            f"{context}.source_comment_sprite_type_id",
            minimum=0,
        )
        if comment_id != sprite_id:
            raise AssetLoadError(f"{context}.source_comment_sprite_type_id does not match sprite_type_id")
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        expression = _string(entry["handler_expression"], f"{context}.handler_expression")
        if _SPRITE_PREP_HANDLER_RE.fullmatch(expression) is None:
            raise AssetLoadError(f"{context}.handler_expression is unsupported")
        handler_label = entry["handler_label"]
        if _IDENTIFIER_RE.fullmatch(expression) is not None:
            if handler_label != expression:
                raise AssetLoadError(f"{context}.handler_label must match the symbol expression")
        elif handler_label is not None:
            raise AssetLoadError(f"{context}.handler_label must be null for literal expressions")
        address = _string(
            entry["source_handler_address_annotation"],
            f"{context}.source_handler_address_annotation",
        )
        source_comment = _string(entry["source_comment"], f"{context}.source_comment")
        comment_match = _SPRITE_PREP_COMMENT_RE.fullmatch(source_comment)
        if comment_match is None:
            raise AssetLoadError(f"{context}.source_comment is malformed")
        if int(comment_match.group("sprite_id"), 16) != sprite_id:
            raise AssetLoadError(f"{context}.source_comment sprite ID does not match sprite_type_id")
        if comment_match.group("address") != address:
            raise AssetLoadError(
                f"{context}.source_handler_address_annotation does not match source_comment"
            )
        if entry["source_description"] != comment_match.group("description"):
            raise AssetLoadError(f"{context}.source_description does not match source_comment")
        continuations = entry["source_comment_continuations"]
        if not isinstance(continuations, list) or any(
            not isinstance(item, str) for item in continuations
        ):
            raise AssetLoadError(f"{context}.source_comment_continuations must be an array of strings")
        if _string(entry["source_revision"], f"{context}.source_revision") != revision:
            raise AssetLoadError(f"{context}.source_revision does not match top-level source_revision")

    evidence = _object(payload["evidence"], "evidence")
    _exact_keys(evidence, _SPRITE_PREP_DISPATCH_EVIDENCE_KEYS, "evidence")
    if _boolean(evidence["source_only"], "evidence.source_only") is not True:
        raise AssetLoadError("evidence.source_only must be true")
    for field in (
        "rom_bytes_read",
        "table_offset_established",
        "handler_address_annotations_verified",
        "runtime_behavior_verified",
    ):
        if _boolean(evidence[field], f"evidence.{field}") is not False:
            raise AssetLoadError(f"evidence.{field} must be false")


_MUSIC_TRACK_INDEX_TOP_KEYS = {
    "format",
    "format_version",
    "source_file",
    "source_revision",
    "block_label",
    "base_expression",
    "table_file_offset",
    "table_end_offset",
    "table_size_bytes",
    "entry_width_bytes",
    "track_index_start",
    "track_index_end",
    "entry_count",
    "entries",
}
_MUSIC_TRACK_ENTRY_KEYS = {
    "table_index",
    "track_index",
    "pointer_entry_file_offset",
    "source_line",
    "pointer_expression",
    "target_label",
    "is_empty",
    "alias_of_track_index",
    "source_comment_index",
    "source_revision",
}
_MUSIC_POINTER_EXPRESSION_RE = re.compile(
    r"(?:\$[0-9A-Fa-f]{4}|[A-Za-z_][A-Za-z0-9_]*)\Z"
)


def _validate_music_track_index_export(payload: dict[str, Any]) -> None:
    _exact_keys(payload, _MUSIC_TRACK_INDEX_TOP_KEYS, "music track index")
    if payload["format"] != MUSIC_TRACK_INDEX_FORMAT:
        raise AssetLoadError("music track index has an invalid format identifier")
    version = _integer(payload["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported music track index version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    _string(payload["source_file"], "source_file")
    revision = _string(payload["source_revision"], "source_revision")
    _identifier(payload["block_label"], "block_label")
    _identifier(payload["base_expression"], "base_expression")
    table_offset = _integer(
        payload["table_file_offset"], "table_file_offset", minimum=0
    )
    table_end = _integer(payload["table_end_offset"], "table_end_offset", minimum=0)
    table_size = _integer(payload["table_size_bytes"], "table_size_bytes", minimum=1)
    width = _integer(payload["entry_width_bytes"], "entry_width_bytes", minimum=1)
    if width != 2:
        raise AssetLoadError("music track pointer entries must be two bytes")
    if table_end != table_offset + table_size - 1:
        raise AssetLoadError("table_end_offset is inconsistent with table range")
    if table_size % width:
        raise AssetLoadError("table_size_bytes must be divisible by entry_width_bytes")

    start_index = _integer(
        payload["track_index_start"], "track_index_start", minimum=0
    )
    end_index = _integer(payload["track_index_end"], "track_index_end", minimum=0)
    if start_index > 0xFFFF or end_index > 0xFFFF:
        raise AssetLoadError("track index range must fit in 16 bits")
    entry_count = _integer(payload["entry_count"], "entry_count", minimum=1)
    entries = payload["entries"]
    if not isinstance(entries, list) or not entries:
        raise AssetLoadError("entries must be a non-empty array")
    if entry_count != len(entries):
        raise AssetLoadError(
            f"entry_count is {entry_count}, but entries contains {len(entries)} records"
        )
    if table_size != entry_count * width:
        raise AssetLoadError("table_size_bytes is inconsistent with entry_count")
    if end_index != start_index + entry_count - 1:
        raise AssetLoadError("track_index_end is inconsistent with the index range")

    first_track_for_label: dict[str, int] = {}
    for expected_index, raw_entry in enumerate(entries):
        context = f"entries[{expected_index}]"
        entry = _object(raw_entry, context)
        _exact_keys(entry, _MUSIC_TRACK_ENTRY_KEYS, context)

        table_index = _integer(
            entry["table_index"], f"{context}.table_index", minimum=0
        )
        if table_index != expected_index:
            raise AssetLoadError(
                f"{context}.table_index must be {expected_index}, got {table_index}"
            )
        expected_track_index = start_index + expected_index
        track_index = _integer(
            entry["track_index"], f"{context}.track_index", minimum=0
        )
        if track_index != expected_track_index:
            raise AssetLoadError(
                f"{context}.track_index must be {expected_track_index}, got {track_index}"
            )
        source_comment_index = _integer(
            entry["source_comment_index"],
            f"{context}.source_comment_index",
            minimum=0,
        )
        if source_comment_index != track_index:
            raise AssetLoadError(
                f"{context}.source_comment_index does not match track_index"
            )

        pointer_offset = _integer(
            entry["pointer_entry_file_offset"],
            f"{context}.pointer_entry_file_offset",
            minimum=0,
        )
        expected_offset = table_offset + expected_index * width
        if pointer_offset != expected_offset:
            raise AssetLoadError(
                f"{context}.pointer_entry_file_offset must be {expected_offset}, got {pointer_offset}"
            )
        _integer(entry["source_line"], f"{context}.source_line", minimum=1)
        expression = _string(
            entry["pointer_expression"], f"{context}.pointer_expression"
        )
        if _MUSIC_POINTER_EXPRESSION_RE.fullmatch(expression) is None:
            raise AssetLoadError(
                f"{context}.pointer_expression must be a four-digit literal or assembly identifier"
            )
        is_empty = _boolean(entry["is_empty"], f"{context}.is_empty")
        target = entry["target_label"]
        if expression.upper() == "$0000":
            if is_empty is not True or target is not None:
                raise AssetLoadError(
                    f"{context} zero pointer must have is_empty=true and target_label=null"
                )
        else:
            _identifier(expression, f"{context}.pointer_expression")
            if is_empty is not False or target != expression:
                raise AssetLoadError(
                    f"{context} symbolic pointer target does not match its expression"
                )
            first_index = first_track_for_label.get(expression)
            alias = _nullable_integer(
                entry["alias_of_track_index"],
                f"{context}.alias_of_track_index",
                minimum=0,
            )
            if alias != first_index:
                raise AssetLoadError(
                    f"{context}.alias_of_track_index does not match prior target aliases"
                )
            first_track_for_label.setdefault(expression, track_index)
            target_revision = _string(entry["source_revision"], f"{context}.source_revision")
            if target_revision != revision:
                raise AssetLoadError(
                    f"{context}.source_revision does not match top-level source_revision"
                )
            continue

        alias = entry["alias_of_track_index"]
        if alias is not None:
            raise AssetLoadError(f"{context} empty pointer cannot be an alias")
        target_revision = _string(entry["source_revision"], f"{context}.source_revision")
        if target_revision != revision:
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
    elif format_name == DUNGEON_CHEST_DATA_FORMAT:
        _validate_dungeon_chest_data_export(export)
    elif format_name == SHOP_ITEM_HANDLERS_FORMAT:
        _validate_shop_item_handlers_export(export)
    elif format_name == POTION_SHOP_TRANSACTIONS_FORMAT:
        _validate_potion_shop_transactions_export(export)
    elif format_name == SPECIAL_SHOP_TRANSACTIONS_FORMAT:
        _validate_special_shop_transactions_export(export)
    elif format_name == PAID_OVERWORLD_INTERACTIONS_FORMAT:
        _validate_paid_overworld_interactions_export(export)
    elif format_name == MIXED_DATA_TABLE_FORMAT:
        _validate_mixed_data_table_export(export)
    elif format_name == ITEM_RECEIPT_LAYOUT_FORMAT:
        _validate_item_receipt_layout_export(export)
    elif format_name == DICTIONARY_INVENTORY_FORMAT:
        _validate_dictionary_inventory_export(export)
    elif format_name == TEXT_MESSAGE_INDEX_FORMAT:
        _validate_text_message_index_export(export)
    elif format_name == SPRITE_DISPATCH_FORMAT:
        _validate_sprite_dispatch_export(export)
    elif format_name == SPRITE_PREP_DISPATCH_FORMAT:
        _validate_sprite_prep_dispatch_export(export)
    elif format_name == MUSIC_TRACK_INDEX_FORMAT:
        _validate_music_track_index_export(export)
    else:
        raise AssetLoadError(f"unsupported source export format: {format_name!r}")
    return export



ASSET_REGISTRY_FORMAT = "zelda-suite-asset-registry"
_ASSET_REGISTRY_TOP_KEYS = {"format", "format_version", "assets"}
_ASSET_REGISTRY_ENTRY_KEYS = {
    "name",
    "file",
    "format",
    "source_revision",
    "record_count",
    "subsystem",
    "description",
}
_ASSET_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ASSET_FILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json\Z")
_SUPPORTED_SOURCE_FORMATS = {
    POINTER_TABLE_FORMAT,
    INCBIN_INVENTORY_FORMAT,
    DATA_TABLE_FORMAT,
    DUNGEON_CHEST_DATA_FORMAT,
    SHOP_ITEM_HANDLERS_FORMAT,
    POTION_SHOP_TRANSACTIONS_FORMAT,
    SPECIAL_SHOP_TRANSACTIONS_FORMAT,
    PAID_OVERWORLD_INTERACTIONS_FORMAT,
    MIXED_DATA_TABLE_FORMAT,
    ITEM_RECEIPT_LAYOUT_FORMAT,
    DICTIONARY_INVENTORY_FORMAT,
    TEXT_MESSAGE_INDEX_FORMAT,
    SPRITE_DISPATCH_FORMAT,
    SPRITE_PREP_DISPATCH_FORMAT,
    MUSIC_TRACK_INDEX_FORMAT,
}


def _validate_asset_registry(payload: Any) -> dict[str, Any]:
    registry = _object(payload, "asset registry")
    _exact_keys(registry, _ASSET_REGISTRY_TOP_KEYS, "asset registry")
    if registry["format"] != ASSET_REGISTRY_FORMAT:
        raise AssetLoadError("asset registry has an invalid format identifier")
    version = _integer(registry["format_version"], "format_version", minimum=1)
    if version != SOURCE_EXPORT_FORMAT_VERSION:
        raise AssetLoadError(
            f"unsupported asset registry version {version}; "
            f"this loader supports {SOURCE_EXPORT_FORMAT_VERSION}"
        )

    assets = registry["assets"]
    if not isinstance(assets, list) or not assets:
        raise AssetLoadError("asset registry assets must be a non-empty array")
    seen_names: set[str] = set()
    seen_files: set[str] = set()
    for index, raw_asset in enumerate(assets):
        context = f"assets[{index}]"
        asset = _object(raw_asset, context)
        _exact_keys(asset, _ASSET_REGISTRY_ENTRY_KEYS, context)
        name = _string(asset["name"], f"{context}.name")
        if _ASSET_NAME_RE.fullmatch(name) is None:
            raise AssetLoadError(f"{context}.name must be a lowercase kebab-case asset name")
        if name in seen_names:
            raise AssetLoadError(f"duplicate asset name: {name}")
        seen_names.add(name)

        filename = _string(asset["file"], f"{context}.file")
        if _ASSET_FILE_RE.fullmatch(filename) is None or Path(filename).name != filename:
            raise AssetLoadError(
                f"{context}.file must be a JSON filename inside the registry directory"
            )
        if filename in seen_files:
            raise AssetLoadError(f"duplicate asset file: {filename}")
        seen_files.add(filename)

        format_name = _string(asset["format"], f"{context}.format")
        if format_name not in _SUPPORTED_SOURCE_FORMATS:
            raise AssetLoadError(
                f"{context}.format is not a supported source export format"
            )
        _string(asset["source_revision"], f"{context}.source_revision")
        _integer(asset["record_count"], f"{context}.record_count", minimum=1)
        _string(asset["subsystem"], f"{context}.subsystem")
        _string(asset["description"], f"{context}.description")

    return registry


def _load_asset_registry(registry_path: str | Path) -> tuple[dict[str, Any], Path]:
    path = Path(registry_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssetLoadError(f"could not read asset registry {path}: {exc}") from exc

    try:
        payload = json.loads(content, parse_constant=_reject_nonstandard_constant)
    except (json.JSONDecodeError, AssetLoadError) as exc:
        raise AssetLoadError(f"invalid JSON in asset registry {path}: {exc}") from exc
    return _validate_asset_registry(payload), path


def list_extracted_assets(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> list[dict[str, Any]]:
    """List registered extracted assets without opening their data files.

    The registry path defaults to data/extracted/manifest.json. Callers using a
    different workspace can pass that workspace's registry explicitly.
    """
    registry, _ = _load_asset_registry(registry_path)
    return [dict(asset) for asset in registry["assets"]]


def load_extracted_asset(
    name: str,
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Load one named asset from the registry and validate its provenance.

    Only a simple registered name is accepted; the filename is selected by the
    registry and cannot be provided by the caller. The selected file must stay
    directly inside the registry directory. Its export format, source revision,
    and record count must match the registry metadata.
    """
    if not isinstance(name, str) or _ASSET_NAME_RE.fullmatch(name) is None:
        raise AssetLoadError("asset name must be lowercase kebab-case")

    registry, registry_file = _load_asset_registry(registry_path)
    record = next((asset for asset in registry["assets"] if asset["name"] == name), None)
    if record is None:
        raise AssetLoadError(f"unknown extracted asset: {name}")

    base_directory = registry_file.resolve().parent
    asset_path = (base_directory / record["file"]).resolve()
    if asset_path.parent != base_directory:
        raise AssetLoadError(
            f"registered asset {name!r} resolves outside the registry directory"
        )

    payload = load_source_export(asset_path)
    if payload.get("format") != record["format"]:
        raise AssetLoadError(
            f"registered asset {name!r} declares format {record['format']!r}, "
            f"but file contains {payload.get('format')!r}"
        )
    if payload.get("source_revision") != record["source_revision"]:
        raise AssetLoadError(
            f"registered asset {name!r} source_revision does not match the registry"
        )

    count_field = {
        POINTER_TABLE_FORMAT: "entry_count",
        INCBIN_INVENTORY_FORMAT: "declaration_count",
        DATA_TABLE_FORMAT: "entry_count",
        DUNGEON_CHEST_DATA_FORMAT: "entry_count",
        SHOP_ITEM_HANDLERS_FORMAT: "entry_count",
        POTION_SHOP_TRANSACTIONS_FORMAT: "entry_count",
        SPECIAL_SHOP_TRANSACTIONS_FORMAT: "entry_count",
        PAID_OVERWORLD_INTERACTIONS_FORMAT: "interaction_count",
        MIXED_DATA_TABLE_FORMAT: "record_count",
        ITEM_RECEIPT_LAYOUT_FORMAT: "entry_count",
        DICTIONARY_INVENTORY_FORMAT: "fragment_count",
        TEXT_MESSAGE_INDEX_FORMAT: "message_count",
        SPRITE_DISPATCH_FORMAT: "entry_count",
        SPRITE_PREP_DISPATCH_FORMAT: "entry_count",
        MUSIC_TRACK_INDEX_FORMAT: "entry_count",
    }[record["format"]]
    actual_count = payload.get(count_field)
    if actual_count != record["record_count"]:
        raise AssetLoadError(
            f"registered asset {name!r} record_count is {record['record_count']}, "
            f"but file contains {actual_count}"
        )
    return payload


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
