"""Read-only verification of overworld hidden-item pointers and records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from zelda_suite.extract.disassembly import parse_dw_pointer_table
from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    lorom_cpu_address,
    read_rom_bytes,
    sha256_rom_bytes,
)

PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
POINTER_TABLE_OFFSET = 0x0DC2F9
DATA_START_OFFSET = 0x0DC3F9
DATA_END_EXCLUSIVE = 0x0DC89C
REPLACEMENT_TABLE_OFFSET = 0x0DC89C
POINTER_COUNT = 128
RECORD_COUNT = 351
SENTINEL_COUNT = 67
REPLACEMENT_WORD_COUNT = 4

_REGION_START_MARKER = "; $0DC3F9-$0DC89B Overworld secrets data"
_REGION_END_MARKER = "; $0DC89C-$0DC8A3 DATA"
_LABEL_RE = re.compile(r"^OverworldData_HiddenItems_Screen_([0-9A-Fa-f]{2})$")
_RECORD_RE = re.compile(
    r"^dw\s+\$([0-9A-Fa-f]{4})\s*:\s*db\s+\$([0-9A-Fa-f]{2})$",
    re.IGNORECASE,
)
_SENTINEL_RE = re.compile(r"^dw\s+\$FFFF$", re.IGNORECASE)
_ASSEMBLY_LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):$")
_WORD_RE = re.compile(r"^dw\s+\$([0-9A-Fa-f]{4})$", re.IGNORECASE)


class OverworldHiddenItemVerificationError(ValueError):
    """Raised when source layout or a ROM cannot be verified safely."""


def parse_overworld_hidden_item_source(
    source: str,
    *,
    source_revision: str = PINNED_SOURCE_REVISION,
) -> dict[str, Any]:
    """Parse the pointer table, mixed-width secret records, sentinels, and replacement words.

    Label offsets are computed from the declaration stream. Labels do not end
    lists: runtime list termination is represented only by the two-byte FFFF
    sentinel, while records are three bytes wide.
    """
    if not isinstance(source, str):
        raise TypeError("source must be text")

    try:
        region_start = source.index(_REGION_START_MARKER)
        region_end = source.index(_REGION_END_MARKER, region_start + len(_REGION_START_MARKER))
    except ValueError as exc:
        raise OverworldHiddenItemVerificationError(
            "could not locate the pinned hidden-item source region markers"
        ) from exc

    pointer_entries = parse_dw_pointer_table(
        source,
        "OverworldData_HiddenItems",
        POINTER_TABLE_OFFSET,
        source_revision=source_revision,
    )
    if len(pointer_entries) != POINTER_COUNT:
        raise OverworldHiddenItemVerificationError(
            f"expected {POINTER_COUNT} area pointers, got {len(pointer_entries)}"
        )

    lines = source.splitlines()
    start_line = source.count("\n", 0, region_start)
    end_line = source.count("\n", 0, region_end)
    region_lines = lines[start_line:end_line]
    current_offset = DATA_START_OFFSET
    current_label: str | None = None
    label_offsets: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    sentinels: list[dict[str, Any]] = []

    for relative_line, raw_line in enumerate(region_lines, start=start_line + 1):
        code = raw_line.split(";", 1)[0].strip()
        if not code:
            continue
        if code in ("{", "}"):
            continue

        label_match = _LABEL_RE.fullmatch(code)
        if label_match:
            label = code[:-1]
            if label in label_offsets:
                raise OverworldHiddenItemVerificationError(
                    f"duplicate hidden-item target label {label!r} on line {relative_line}"
                )
            label_offsets[label] = current_offset
            current_label = label
            continue

        record_match = _RECORD_RE.fullmatch(code)
        if record_match:
            if current_label is None:
                raise OverworldHiddenItemVerificationError(
                    f"record before a screen label on line {relative_line}"
                )
            coordinate = int(record_match.group(1), 16)
            value = int(record_match.group(2), 16)
            records.append({
                "record_index": len(records),
                "source_label": current_label,
                "source_line": relative_line,
                "file_offset": current_offset,
                "coordinate_word": coordinate,
                "value_byte": value,
                "expression": code,
            })
            current_offset += 3
            continue

        if _SENTINEL_RE.fullmatch(code):
            if current_label is None:
                raise OverworldHiddenItemVerificationError(
                    f"sentinel before a screen label on line {relative_line}"
                )
            sentinels.append({
                "sentinel_index": len(sentinels),
                "source_label": current_label,
                "source_line": relative_line,
                "file_offset": current_offset,
                "expression": code,
            })
            current_offset += 2
            continue

        raise OverworldHiddenItemVerificationError(
            f"unsupported declaration in hidden-item region on line "
            f"{relative_line}: {code!r}"
        )

    if current_offset != DATA_END_EXCLUSIVE:
        raise OverworldHiddenItemVerificationError(
            f"hidden-item declarations end at 0x{current_offset:06X}; "
            f"expected 0x{DATA_END_EXCLUSIVE:06X}"
        )
    if len(records) != RECORD_COUNT:
        raise OverworldHiddenItemVerificationError(
            f"expected {RECORD_COUNT} three-byte records, got {len(records)}"
        )
    if len(sentinels) != SENTINEL_COUNT:
        raise OverworldHiddenItemVerificationError(
            f"expected {SENTINEL_COUNT} two-byte sentinels, got {len(sentinels)}"
        )
    if len(label_offsets) != 80:
        raise OverworldHiddenItemVerificationError(
            f"expected 80 target labels, got {len(label_offsets)}"
        )

    missing_targets = sorted({
        entry.target_label
        for entry in pointer_entries
        if entry.target_label not in label_offsets
    })
    if missing_targets:
        raise OverworldHiddenItemVerificationError(
            "pointer target labels missing from the data region: "
            + ", ".join(missing_targets)
        )

    replacement_start = source.find("Overworld_SecretTileType:", region_end)
    if replacement_start < 0:
        raise OverworldHiddenItemVerificationError(
            "could not locate Overworld_SecretTileType replacement table"
        )
    replacement_open = source.find("{", replacement_start)
    replacement_close = source.find("}", replacement_open + 1)
    if replacement_open < 0 or replacement_close < 0:
        raise OverworldHiddenItemVerificationError(
            "replacement table braces are missing"
        )

    replacement_words: list[dict[str, Any]] = []
    replacement_source = source[replacement_open + 1:replacement_close]
    for relative_line, raw_line in enumerate(
        replacement_source.splitlines(),
        start=source.count("\n", 0, replacement_open) + 2,
    ):
        code = raw_line.split(";", 1)[0].strip()
        if not code:
            continue
        word_match = _WORD_RE.fullmatch(code)
        if word_match is None:
            raise OverworldHiddenItemVerificationError(
                f"unsupported replacement-table declaration on line "
                f"{relative_line}: {code!r}"
            )
        replacement_words.append({
            "table_index": len(replacement_words),
            "source_line": relative_line,
            "file_offset": REPLACEMENT_TABLE_OFFSET + 2 * len(replacement_words),
            "value": int(word_match.group(1), 16),
            "expression": code,
        })
    if len(replacement_words) != REPLACEMENT_WORD_COUNT:
        raise OverworldHiddenItemVerificationError(
            f"expected {REPLACEMENT_WORD_COUNT} replacement words, "
            f"got {len(replacement_words)}"
        )

    return {
        "source_revision": source_revision,
        "pointer_table_offset": POINTER_TABLE_OFFSET,
        "pointer_entries": [entry.to_dict() for entry in pointer_entries],
        "data_start_offset": DATA_START_OFFSET,
        "data_end_exclusive": DATA_END_EXCLUSIVE,
        "label_offsets": label_offsets,
        "records": records,
        "sentinels": sentinels,
        "replacement_words": replacement_words,
    }


def verify_overworld_hidden_items(
    rom_path: str | Path,
    source: str,
    *,
    source_revision: str = PINNED_SOURCE_REVISION,
) -> dict[str, Any]:
    """Compare source-computed hidden-item pointer and data bytes to a local ROM."""
    image_path = Path(rom_path)
    if not image_path.is_file():
        raise OverworldHiddenItemVerificationError(
            f"ROM path is not a file: {image_path}"
        )
    try:
        rom = read_rom_bytes(image_path)
    except ROMImageInspectionError as exc:
        raise OverworldHiddenItemVerificationError(str(exc)) from exc
    if len(rom) != EXPECTED_US_ROM_SIZE:
        raise OverworldHiddenItemVerificationError(
            "ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(rom):,}. "
            "Use inspect-rom to diagnose the file; do not adjust it automatically."
        )

    layout = parse_overworld_hidden_item_source(
        source,
        source_revision=source_revision,
    )
    mismatches: list[dict[str, Any]] = []
    checks = 0

    def compare(
        kind: str,
        index: int,
        offset: int,
        expected: bytes,
        *,
        label: str | None = None,
        expression: str | None = None,
    ) -> None:
        nonlocal checks
        end_offset = offset + len(expected)
        if offset < 0 or end_offset > len(rom):
            mismatches.append({
                "kind": kind,
                "index": index,
                "label": label,
                "expression": expression,
                "offset": offset,
                "reason": "comparison range is outside the ROM image",
                "expected_hex": expected.hex().upper(),
                "actual_hex": None,
            })
            return
        actual = rom[offset:end_offset]
        checks += 1
        if actual != expected:
            mismatches.append({
                "kind": kind,
                "index": index,
                "label": label,
                "expression": expression,
                "offset": offset,
                "reason": "ROM bytes do not match the source declaration",
                "expected_hex": expected.hex().upper(),
                "actual_hex": actual.hex().upper(),
            })

    for pointer in layout["pointer_entries"]:
        label = pointer["target_label"]
        target_offset = layout["label_offsets"][label]
        if pointer["target_addend"] is not None:
            target_offset += pointer["target_addend"]
        try:
            target_address = lorom_cpu_address(target_offset) & 0xFFFF
        except (TypeError, ValueError) as exc:
            raise OverworldHiddenItemVerificationError(
                f"pointer target {label!r} resolves outside the headerless ROM: {exc}"
            ) from exc
        compare(
            "pointer",
            pointer["table_index"],
            pointer["pointer_entry_file_offset"],
            target_address.to_bytes(2, "little"),
            label=label,
            expression=pointer["pointer_expression"],
        )

    for record in layout["records"]:
        expected = (
            record["coordinate_word"].to_bytes(2, "little")
            + bytes([record["value_byte"]])
        )
        compare(
            "record",
            record["record_index"],
            record["file_offset"],
            expected,
            label=record["source_label"],
            expression=record["expression"],
        )

    for sentinel in layout["sentinels"]:
        compare(
            "sentinel",
            sentinel["sentinel_index"],
            sentinel["file_offset"],
            b"\xFF\xFF",
            label=sentinel["source_label"],
            expression=sentinel["expression"],
        )

    for word in layout["replacement_words"]:
        compare(
            "replacement-map16",
            word["table_index"],
            word["file_offset"],
            word["value"].to_bytes(2, "little"),
            expression=word["expression"],
        )

    return {
        "format": "zelda-suite-overworld-hidden-item-verification",
        "format_version": 1,
        "rom": {
            "filename": image_path.name,
            "size_bytes": len(rom),
            "sha256": sha256_rom_bytes(rom),
            "header_assessment": "headerless-by-expected-size",
            "provenance_verified": False,
        },
        "source_revision": layout["source_revision"],
        "source_layout": {
            "pointer_count": len(layout["pointer_entries"]),
            "distinct_target_label_count": len(layout["label_offsets"]),
            "three_byte_record_count": len(layout["records"]),
            "two_byte_sentinel_count": len(layout["sentinels"]),
            "replacement_word_count": len(layout["replacement_words"]),
            "data_start_offset": layout["data_start_offset"],
            "data_end_exclusive": layout["data_end_exclusive"],
            "data_region_size_bytes": (
                layout["data_end_exclusive"] - layout["data_start_offset"]
            ),
        },
        "checked_comparisons": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "semantic_values_decoded": False,
        "rom_modified": False,
    }
