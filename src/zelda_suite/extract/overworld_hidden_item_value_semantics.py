"""Source-consumer classification for overworld hidden-item value bytes."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from zelda_suite.extract.overworld_hidden_item_verification import (
    PINNED_SOURCE_REVISION,
    OverworldHiddenItemVerificationError,
    parse_overworld_hidden_item_source,
)

OVERWORLD_HIDDEN_ITEM_VALUE_SEMANTICS_FORMAT = (
    "zelda-suite-overworld-hidden-item-value-semantics"
)
REPLACEMENT_TABLE_LABEL = "Overworld_SecretTileType"
EXPECTED_REPLACEMENT_VALUES = (0x0DCC, 0x0212, 0xFFFF, 0x0DB4)
EXPECTED_CONSUMER_LINES = {
    "sentinel_compare_line": 2847,
    "room_word_mask_compare_line": 2848,
    "value_byte_load_line": 2851,
    "extended_value_threshold_line": 2852,
    "secret_mask_update_line": 2853,
    "extended_special_case_line": 2863,
    "selector_byte_offset_line": 2878,
    "replacement_table_load_line": 2879,
}
_EXPECTED_CONSUMER_FRAGMENTS = (
    ("LDY.w #$FFFD", None),
    ("INY #3", None),
    ("LDA.b [$00], Y : CMP.w #$FFFF : BEQ .failure", "sentinel_compare_line"),
    ("AND.w #$7FFF : CMP.b $04 : BNE .nextSecret", "room_word_mask_compare_line"),
    ("INY : INY", None),
    ("LDA.b [$00], Y : AND.w #$00FF : BEQ .emptySecret", "value_byte_load_line"),
    ("CMP.w #$0080 : BCS .extendedSecret", "extended_value_threshold_line"),
    ("TSB.w $0B9C", "secret_mask_update_line"),
    ("CMP.w #$0084 : BEQ .notBurrow", "extended_special_case_line"),
    ("LDA.b [$00], Y : AND.w #$000F : TAX", "selector_byte_offset_line"),
    ("LDA.l Overworld_SecretTileType, X : STA.b $0E", "replacement_table_load_line"),
)
_WORD_WITH_COMMENT_RE = re.compile(
    r"^dw\s+\$([0-9A-Fa-f]{4})\s*;\s*(.*?)\s*$",
    re.IGNORECASE,
)


class OverworldHiddenItemValueSemanticsError(ValueError):
    """Raised when pinned source consumer evidence is incomplete or inconsistent."""


def classify_overworld_hidden_item_value_byte(
    value_byte: int,
    replacement_words: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify a raw value byte by consumer branches, never as a canonical item ID.

    Values below $80 feed the secret-state mask at $0B9C (zero follows the empty
    branch). Values $80 and above use the low nibble as a byte offset into the
    two-byte Overworld_SecretTileType replacement table.
    """
    if isinstance(value_byte, bool) or not isinstance(value_byte, int):
        raise OverworldHiddenItemValueSemanticsError("value_byte must be an integer byte")
    if not 0 <= value_byte <= 0xFF:
        raise OverworldHiddenItemValueSemanticsError(
            f"value_byte must be in 0..255, got {value_byte}"
        )

    base: dict[str, Any] = {
        "value_byte": value_byte,
        "value_hex": "$" + format(value_byte, "02X"),
        "canonical_item_id_resolved": False,
    }
    if value_byte == 0:
        return {
            **base,
            "consumer_class": "zero_value",
            "consumer_operation": "branches to .emptySecret and skips TSB $0B9C",
            "selector_byte_offset": None,
            "replacement_table_index": None,
            "replacement_word_value": None,
            "replacement_word_comment": None,
            "special_case": None,
        }
    if value_byte < 0x80:
        return {
            **base,
            "consumer_class": "ordinary_secret_mask",
            "consumer_operation": "TSB $0B9C combines this value with secret-state flags",
            "selector_byte_offset": None,
            "replacement_table_index": None,
            "replacement_word_value": None,
            "replacement_word_comment": None,
            "special_case": None,
        }

    selector_byte_offset = value_byte & 0x0F
    matching_words = [
        word for word in replacement_words
        if word["selector_byte_offset"] == selector_byte_offset
    ]
    replacement = matching_words[0] if len(matching_words) == 1 else None
    mapped = selector_byte_offset % 2 == 0 and replacement is not None

    return {
        **base,
        "consumer_class": "extended_secret_selector",
        "consumer_operation": (
            "uses the low nibble as a byte offset into Overworld_SecretTileType"
        ),
        "selector_byte_offset": selector_byte_offset,
        "replacement_table_index": replacement["table_index"] if mapped else None,
        "replacement_word_value": replacement["value"] if mapped else None,
        "replacement_word_comment": replacement["comment"] if mapped else None,
        "special_case": (
            "$84 branches to .notBurrow and skips the generic overlay-activation block"
            if value_byte == 0x84 else None
        ),
    }


def audit_overworld_hidden_item_value_semantics(source: str) -> dict[str, Any]:
    """Report source-consumer behavior for each third byte in the pinned secret table.

    Source annotations are retained as data; classifications describe the visible
    consumer branches and do not resolve canonical item IDs or verify ROM bytes.
    """
    try:
        layout = parse_overworld_hidden_item_source(source)
    except (OverworldHiddenItemVerificationError, TypeError) as exc:
        raise OverworldHiddenItemValueSemanticsError(str(exc)) from exc

    if layout["source_revision"] != PINNED_SOURCE_REVISION:
        raise OverworldHiddenItemValueSemanticsError(
            "hidden-item value semantics audit requires the pinned source revision"
        )

    consumer_start = source.find("Overworld_RevealSecret:\n{")
    if consumer_start < 0:
        raise OverworldHiddenItemValueSemanticsError(
            "could not locate the Overworld_RevealSecret consumer"
        )
    consumer_end = source.find("\n}\n", consumer_start)
    if consumer_end < 0:
        raise OverworldHiddenItemValueSemanticsError(
            "could not locate the end of Overworld_RevealSecret"
        )
    consumer = source[consumer_start:consumer_end]
    source_lines: dict[str, int] = {}
    missing_fragments: list[str] = []
    for fragment, line_key in _EXPECTED_CONSUMER_FRAGMENTS:
        relative_offset = consumer.find(fragment)
        if relative_offset < 0:
            missing_fragments.append(fragment)
            continue
        if line_key is not None:
            actual_line = source.count("\n", 0, consumer_start + relative_offset) + 1
            source_lines[line_key] = actual_line
            if actual_line != EXPECTED_CONSUMER_LINES[line_key]:
                missing_fragments.append(
                    f"{fragment} (expected pinned line {EXPECTED_CONSUMER_LINES[line_key]}, got {actual_line})"
                )
    if missing_fragments:
        raise OverworldHiddenItemValueSemanticsError(
            "pinned Overworld_RevealSecret consumer did not match its expected "
            "value-byte logic: " + "; ".join(missing_fragments)
        )

    table_start = source.find(REPLACEMENT_TABLE_LABEL + ":", consumer_end)
    if table_start < 0:
        raise OverworldHiddenItemValueSemanticsError(
            "could not locate Overworld_SecretTileType source table"
        )
    table_open = source.find("{", table_start)
    table_close = source.find("}", table_open + 1)
    if table_open < 0 or table_close < 0:
        raise OverworldHiddenItemValueSemanticsError(
            "Overworld_SecretTileType table braces are missing"
        )

    table_lines: list[dict[str, Any]] = []
    table_source = source[table_open + 1:table_close]
    start_line = source.count("\n", 0, table_open) + 2
    for line_number, raw_line in enumerate(table_source.splitlines(), start=start_line):
        code = raw_line.split(";", 1)[0].strip()
        if not code:
            continue
        match = _WORD_WITH_COMMENT_RE.fullmatch(raw_line.strip())
        if match is None:
            raise OverworldHiddenItemValueSemanticsError(
                f"replacement-table word lacks an inline comment on line {line_number}"
            )
        if len(table_lines) >= len(layout["replacement_words"]):
            raise OverworldHiddenItemValueSemanticsError(
                "replacement table has more commented words than the parsed baseline"
            )
        parsed_word = layout["replacement_words"][len(table_lines)]
        table_lines.append({
            "table_index": len(table_lines),
            "source_line": line_number,
            "file_offset": parsed_word["file_offset"],
            "selector_byte_offset": 2 * len(table_lines),
            "expression": code,
            "value": int(match.group(1), 16),
            "comment": match.group(2).strip(),
        })

    raw_words = [word["value"] for word in table_lines]
    if tuple(raw_words) != EXPECTED_REPLACEMENT_VALUES:
        raise OverworldHiddenItemValueSemanticsError(
            "Overworld_SecretTileType values changed from the pinned four-word baseline: "
            + ", ".join("$" + format(value, "04X") for value in raw_words)
        )
    if len(table_lines) != len(layout["replacement_words"]):
        raise OverworldHiddenItemValueSemanticsError(
            "commented replacement-table rows do not align with parsed replacement words"
        )

    records: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    extended_value_counts: Counter[int] = Counter()
    unmapped_extended_value_counts: Counter[int] = Counter()
    for record in layout["records"]:
        classification = classify_overworld_hidden_item_value_byte(
            record["value_byte"],
            table_lines,
        )
        if (
            classification["consumer_class"] == "extended_secret_selector"
            and classification["replacement_table_index"] is None
        ):
            unmapped_extended_value_counts[record["value_byte"]] += 1
        if classification["consumer_class"] == "extended_secret_selector":
            extended_value_counts[record["value_byte"]] += 1
        class_counts[classification["consumer_class"]] += 1
        records.append({
            "record_index": record["record_index"],
            "source_label": record["source_label"],
            "source_line": record["source_line"],
            "file_offset": record["file_offset"],
            "coordinate_word": record["coordinate_word"],
            "coordinate_word_hex": "$" + format(record["coordinate_word"], "04X"),
            "expression": record["expression"],
            **classification,
        })

    extended_distribution = [
        {
            "value_byte": value,
            "value_hex": "$" + format(value, "02X"),
            "record_count": count,
            "selector_byte_offset": value & 0x0F,
            "replacement_table_index": (
                (value & 0x0F) // 2
                if (value & 0x0F) % 2 == 0 and (value & 0x0F) <= 6
                else None
            ),
            "replacement_word_comment": (
                table_lines[(value & 0x0F) // 2]["comment"]
                if (value & 0x0F) % 2 == 0 and (value & 0x0F) <= 6
                else None
            ),
        }
        for value, count in sorted(extended_value_counts.items())
    ]

    return {
        "format": OVERWORLD_HIDDEN_ITEM_VALUE_SEMANTICS_FORMAT,
        "format_version": 1,
        "source_file": "Bank1B.asm",
        "source_revision": PINNED_SOURCE_REVISION,
        "consumer_label": "Overworld_RevealSecret",
        "replacement_table_label": REPLACEMENT_TABLE_LABEL,
        "replacement_words": table_lines,
        "records": records,
        "summary": {
            "record_count": len(records),
            "zero_value_count": class_counts["zero_value"],
            "ordinary_secret_mask_count": class_counts["ordinary_secret_mask"],
            "extended_secret_selector_count": class_counts["extended_secret_selector"],
            "extended_selector_unmapped_count": sum(unmapped_extended_value_counts.values()),
            "extended_value_distribution": extended_distribution,
        },
        "source_semantics": {
            "source_file": "Bank1B.asm",
            "source_revision": PINNED_SOURCE_REVISION,
            "reader_label": "Overworld_RevealSecret",
            "sentinel_compare_line": source_lines["sentinel_compare_line"],
            "room_word_mask_compare_line": source_lines["room_word_mask_compare_line"],
            "value_byte_load_line": source_lines["value_byte_load_line"],
            "extended_value_threshold_line": source_lines["extended_value_threshold_line"],
            "secret_mask_update_line": source_lines["secret_mask_update_line"],
            "extended_special_case_line": source_lines["extended_special_case_line"],
            "selector_byte_offset_line": source_lines["selector_byte_offset_line"],
            "replacement_table_load_line": source_lines["replacement_table_load_line"],
            "replacement_table_comment_lines": [word["source_line"] for word in table_lines],
            "description": (
                "The third byte is not used as a canonical item ID by the traced consumer. "
                "Values below $80 feed the secret-state mask at $0B9C (with zero taking "
                "an empty-value branch); values at or above $80 use the low nibble as a "
                "byte offset into Overworld_SecretTileType. Value $84 branches to "
                ".notBurrow before the generic overlay-activation block."
            ),
        },
        "evidence": {
            "source_only": True,
            "source_consumer_patterns_checked": True,
            "rom_bytes_read": False,
            "room_payload_bytes_read": False,
            "canonical_item_ids_resolved": False,
            "value_byte_semantics_verified_in_rom": False,
        },
    }
