"""Read-only verification of source-derived text dictionary pointer words."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import AssetLoadError, load_extracted_asset
from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    lorom_cpu_address,
    read_rom_bytes,
    sha256_rom_bytes,
)
from zelda_suite.extract.text_dictionary_audit import (
    TextDictionaryAuditError,
    audit_text_dictionary_assets,
)

TEXT_DICTIONARY_POINTER_VERIFICATION_FORMAT = "zelda-suite-text-dictionary-pointer-verification"
TEXT_DICTIONARY_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TEXT_DICTIONARY_POINTER_ASSET = "text-dictionary-pointers"
TEXT_DICTIONARY_FRAGMENT_ASSET = "text-dictionary-fragments"
TEXT_DICTIONARY_POINTER_TABLE_LABEL = "DictionaryPointers"
TEXT_DICTIONARY_POINTER_TABLE_OFFSET = 0x074703
TEXT_DICTIONARY_POINTER_ENTRY_WIDTH = 2
TEXT_DICTIONARY_POINTER_ENTRY_COUNT = 98
TEXT_DICTIONARY_DATA_LABEL = "DictionaryEntries"
TEXT_DICTIONARY_DATA_OFFSET = 0x0747C7
# Bank0E.asm's inclusive DATA range ends at $0748D8; the following code
# section starts at $0748D9. The terminal dictionary pointer is that exclusive
# end boundary, not a pointer to the final byte of the inclusive range.
TEXT_DICTIONARY_DATA_END_INCLUSIVE_OFFSET = 0x0748D8
TEXT_DICTIONARY_END_EXCLUSIVE_OFFSET = TEXT_DICTIONARY_DATA_END_INCLUSIVE_OFFSET + 1
TEXT_DICTIONARY_NEXT_SECTION_START_OFFSET = 0x0748D9


class TextDictionaryPointerVerificationError(ValueError):
    """Raised when dictionary pointer metadata cannot safely support a byte check."""


def verify_text_dictionary_pointers(
    rom_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Compare dictionary pointers using fragment starts and an exclusive end sentinel.

    Ordinary targets use source-commented fragment starts. The final end-of-table
    pointer uses the first byte after the pinned inclusive DATA range because the
    runtime copies token bytes up to the next pointer (exclusive end). The raw
    terminal comment is preserved separately. The .You directive extent warning
    remains visible; this check does not validate fragment bytes, decode semantic
    text, or establish ROM provenance.
    """
    image_path = Path(rom_path)
    if not image_path.is_file():
        raise TextDictionaryPointerVerificationError(
            f"ROM path is not a file: {image_path}"
        )
    try:
        rom = read_rom_bytes(image_path)
    except ROMImageInspectionError as exc:
        raise TextDictionaryPointerVerificationError(str(exc)) from exc
    if len(rom) != EXPECTED_US_ROM_SIZE:
        raise TextDictionaryPointerVerificationError(
            "ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(rom):,}. "
            "Use inspect-rom to diagnose the file; do not adjust it automatically."
        )

    try:
        pointers = load_extracted_asset(TEXT_DICTIONARY_POINTER_ASSET, registry_path)
        fragments = load_extracted_asset(TEXT_DICTIONARY_FRAGMENT_ASSET, registry_path)
        source_audit = audit_text_dictionary_assets(registry_path)
    except (AssetLoadError, TextDictionaryAuditError, OSError, ValueError) as exc:
        raise TextDictionaryPointerVerificationError(str(exc)) from exc

    if pointers["source_file"] != "Bank0E.asm" or fragments["source_file"] != "Bank0E.asm":
        raise TextDictionaryPointerVerificationError(
            "text dictionary pointer and fragment assets must both record Bank0E.asm"
        )
    if pointers["source_revision"] != TEXT_DICTIONARY_SOURCE_REVISION:
        raise TextDictionaryPointerVerificationError(
            f"text dictionary source revision must be {TEXT_DICTIONARY_SOURCE_REVISION}"
        )
    if fragments["source_revision"] != pointers["source_revision"]:
        raise TextDictionaryPointerVerificationError(
            "text dictionary fragment source revision does not match its pointer table"
        )
    if (
        pointers["table_label"] != TEXT_DICTIONARY_POINTER_TABLE_LABEL
        or pointers["table_file_offset"] != TEXT_DICTIONARY_POINTER_TABLE_OFFSET
        or pointers["directive"] != "dw"
        or pointers["entry_width"] != TEXT_DICTIONARY_POINTER_ENTRY_WIDTH
        or pointers["entry_count"] != TEXT_DICTIONARY_POINTER_ENTRY_COUNT
    ):
        raise TextDictionaryPointerVerificationError(
            "registered text dictionary pointer asset does not match the pinned "
            "98-entry, two-byte DictionaryPointers table"
        )
    if (
        fragments["pointer_table_label"] != TEXT_DICTIONARY_POINTER_TABLE_LABEL
        or fragments["pointer_table_file_offset"] != TEXT_DICTIONARY_POINTER_TABLE_OFFSET
        or fragments["data_label"] != TEXT_DICTIONARY_DATA_LABEL
        or fragments["data_file_offset"] != TEXT_DICTIONARY_DATA_OFFSET
        or fragments["fragment_count"] != TEXT_DICTIONARY_POINTER_ENTRY_COUNT
    ):
        raise TextDictionaryPointerVerificationError(
            "registered text dictionary fragment inventory does not match the pinned table metadata"
        )
    if source_audit["summary"]["error_count"] != 0:
        raise TextDictionaryPointerVerificationError(
            "registered text dictionary exports contain cross-reference errors; "
            "run audit-text-dictionary before pointer verification"
        )

    pointer_entries = pointers["entries"]
    fragment_entries = fragments["fragments"]
    fragments_by_expression = {
        fragment["pointer_expression"]: fragment for fragment in fragment_entries
    }
    if len(fragments_by_expression) != len(fragment_entries):
        raise TextDictionaryPointerVerificationError(
            "registered text dictionary fragment expressions are not unique"
        )

    if (
        TEXT_DICTIONARY_END_EXCLUSIVE_OFFSET
        != TEXT_DICTIONARY_NEXT_SECTION_START_OFFSET
    ):
        raise TextDictionaryPointerVerificationError(
            "pinned terminal dictionary boundary does not meet the next source section"
        )

    pointer_bank = TEXT_DICTIONARY_POINTER_TABLE_OFFSET // 0x8000
    entries_report: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for pointer in pointer_entries:
        expression = pointer["expression"]
        fragment = fragments_by_expression.get(expression)
        if fragment is None:
            raise TextDictionaryPointerVerificationError(
                f"pointer expression {expression!r} has no unique fragment metadata"
            )
        source_comment_offset = fragment["fragment_file_offset"]
        target_offset = source_comment_offset
        target_offset_basis = "source_comment_start"
        if fragment["is_end_of_table"]:
            if (
                pointer["table_index"] != TEXT_DICTIONARY_POINTER_ENTRY_COUNT - 1
                or expression != "DictionaryEntries_endOfTable"
                or source_comment_offset != TEXT_DICTIONARY_DATA_END_INCLUSIVE_OFFSET
            ):
                raise TextDictionaryPointerVerificationError(
                    "terminal dictionary sentinel does not match the pinned inclusive "
                    "data-range endpoint"
                )
            target_offset = TEXT_DICTIONARY_END_EXCLUSIVE_OFFSET
            target_offset_basis = "exclusive_end_after_inclusive_data_range"
        if target_offset // 0x8000 != pointer_bank:
            raise TextDictionaryPointerVerificationError(
                f"target {fragment['fragment_label']!r} at file offset "
                f"0x{target_offset:06X} is outside the pointer table's LoROM bank"
            )
        try:
            candidate_address = lorom_cpu_address(target_offset) & 0xFFFF
        except (TypeError, ValueError) as exc:
            raise TextDictionaryPointerVerificationError(
                f"target {fragment['fragment_label']!r} has invalid candidate "
                f"offset 0x{target_offset:X}: {exc}"
            ) from exc

        expected = candidate_address.to_bytes(TEXT_DICTIONARY_POINTER_ENTRY_WIDTH, "little")
        offset = pointer["entry_file_offset"]
        actual = rom[offset:offset + TEXT_DICTIONARY_POINTER_ENTRY_WIDTH]
        if len(actual) != TEXT_DICTIONARY_POINTER_ENTRY_WIDTH:
            raise TextDictionaryPointerVerificationError(
                f"pointer entry {pointer['table_index']} is outside the ROM image"
            )

        record = {
            "table_index": pointer["table_index"],
            "pointer_entry_file_offset": offset,
            "pointer_expression": expression,
            "target_fragment_label": fragment["fragment_label"],
            "target_fragment_file_offset": target_offset,
            "target_fragment_source_comment_offset": source_comment_offset,
            "target_offset_basis": target_offset_basis,
            "candidate_pointer_word": "$" + format(candidate_address, "04X"),
            "expected_hex": expected.hex().upper(),
            "actual_hex": actual.hex().upper(),
            "status": "pass" if actual == expected else "fail",
        }
        entries_report.append(record)
        if actual != expected:
            mismatches.append({
                "table_index": pointer["table_index"],
                "pointer_entry_file_offset": offset,
                "pointer_expression": expression,
                "target_fragment_label": fragment["fragment_label"],
                "target_fragment_file_offset": target_offset,
                "target_fragment_source_comment_offset": source_comment_offset,
                "target_offset_basis": target_offset_basis,
                "candidate_pointer_word": "$" + format(candidate_address, "04X"),
                "expected_hex": expected.hex().upper(),
                "actual_hex": actual.hex().upper(),
                "reason": "ROM pointer bytes do not match the source-offset candidate",
            })

    source_extent_findings = [
        {
            "code": finding["code"],
            "severity": finding["severity"],
            "pointer_index": finding["pointer_index"],
            "pointer_expression": finding["pointer_expression"],
            "fragment_label": finding["fragment_label"],
            "message": finding["message"],
        }
        for finding in source_audit["findings"]
        if finding["code"] == "source_extent_mismatch"
    ]

    return {
        "format": TEXT_DICTIONARY_POINTER_VERIFICATION_FORMAT,
        "format_version": 2,
        "rom": {
            "filename": image_path.name,
            "size_bytes": len(rom),
            "sha256": sha256_rom_bytes(rom),
            "header_assessment": "headerless-by-expected-size",
            "provenance_verified": False,
        },
        "source_revision": pointers["source_revision"],
        "pointer_table": {
            "label": TEXT_DICTIONARY_POINTER_TABLE_LABEL,
            "file_offset": TEXT_DICTIONARY_POINTER_TABLE_OFFSET,
            "entry_width_bytes": TEXT_DICTIONARY_POINTER_ENTRY_WIDTH,
            "entry_count": TEXT_DICTIONARY_POINTER_ENTRY_COUNT,
            "unique_target_label_count": len(fragments_by_expression),
            "checked_comparisons": len(entries_report),
            "mismatch_count": len(mismatches),
            "source_extent_mismatch_count": source_audit["summary"]["source_extent_mismatch_count"],
        },
        "entries": entries_report,
        "mismatches": mismatches,
        "source_findings": source_extent_findings,
        "terminal_pointer_rule": (
            "exclusive end of the inclusive source-commented dictionary data range"
        ),
        "source_symbol_name_mapping_verified": False,
        "source_offsets_verified": False,
        "fragment_payload_bytes_verified": False,
        "semantic_text_decoded": False,
        "rom_modified": False,
    }
