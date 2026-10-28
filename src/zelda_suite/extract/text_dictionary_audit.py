"""Cross-check committed text dictionary pointer and fragment inventories."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    DICTIONARY_INVENTORY_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

TEXT_DICTIONARY_AUDIT_FORMAT = "zelda-suite-text-dictionary-audit"
_POINTER_TARGET_RE = re.compile(r"DictionaryEntries_([A-Za-z_][A-Za-z0-9_]*)\Z")


class TextDictionaryAuditError(ValueError):
    """Raised when the registered dictionary assets cannot be audited."""


def audit_text_dictionary_assets(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    pointer_asset_name: str = "text-dictionary-pointers",
    fragment_asset_name: str = "text-dictionary-fragments",
) -> dict[str, Any]:
    """Cross-reference committed dictionary exports without reading ROM or bytes.

    Source extent mismatches are reported as warnings and preserved. Pointer
    expressions remain symbols; this function does not resolve them to ROM
    addresses or prove that source-annotated offsets match an actual image.
    """
    try:
        registered = list_extracted_assets(registry_path)
        by_name = {asset["name"]: asset for asset in registered}
        pointer_record = by_name.get(pointer_asset_name)
        fragment_record = by_name.get(fragment_asset_name)
        if pointer_record is None:
            raise TextDictionaryAuditError(
                f"pointer asset is not registered: {pointer_asset_name!r}"
            )
        if fragment_record is None:
            raise TextDictionaryAuditError(
                f"fragment asset is not registered: {fragment_asset_name!r}"
            )
        if pointer_record["format"] != DATA_TABLE_FORMAT:
            raise TextDictionaryAuditError(
                f"pointer asset {pointer_asset_name!r} must use {DATA_TABLE_FORMAT!r}"
            )
        if fragment_record["format"] != DICTIONARY_INVENTORY_FORMAT:
            raise TextDictionaryAuditError(
                f"fragment asset {fragment_asset_name!r} must use "
                f"{DICTIONARY_INVENTORY_FORMAT!r}"
            )
        pointers = load_extracted_asset(pointer_asset_name, registry_path)
        fragments = load_extracted_asset(fragment_asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise TextDictionaryAuditError(str(exc)) from exc

    findings: list[dict[str, Any]] = []

    def add_finding(
        code: str,
        severity: str,
        message: str,
        *,
        pointer_index: int | None = None,
        pointer_expression: str | None = None,
        fragment_label: str | None = None,
    ) -> None:
        findings.append({
            "code": code,
            "severity": severity,
            "message": message,
            "pointer_index": pointer_index,
            "pointer_expression": pointer_expression,
            "fragment_label": fragment_label,
        })

    if pointers["source_revision"] != fragments["source_revision"]:
        add_finding(
            "source_provenance_mismatch",
            "error",
            "Pointer and fragment exports record different source revisions.",
        )
    if pointers["source_file"] != fragments["source_file"]:
        add_finding(
            "source_provenance_mismatch",
            "error",
            "Pointer and fragment exports record different source files.",
        )
    if (
        pointers["table_label"] != fragments["pointer_table_label"]
        or pointers["table_file_offset"] != fragments["pointer_table_file_offset"]
        or pointers["directive"] != "dw"
        or pointers["entry_width"] != 2
        or fragments["pointer_table_label"] != "DictionaryPointers"
        or fragments["data_label"] != "DictionaryEntries"
    ):
        add_finding(
            "pointer_table_metadata_mismatch",
            "error",
            "Pointer table labels, source offset, or two-byte directive metadata disagree.",
        )
    if fragments["fragment_count"] != pointers["entry_count"]:
        add_finding(
            "entry_count_mismatch",
            "error",
            f"Pointer export has {pointers['entry_count']} entries but fragment inventory has "
            f"{fragments['fragment_count']} records.",
        )
    if not fragments["fragments"] or (
        fragments["data_file_offset"] != fragments["fragments"][0]["fragment_file_offset"]
    ):
        add_finding(
            "data_start_offset_mismatch",
            "error",
            "Fragment inventory data_file_offset does not match its first fragment_file_offset.",
        )

    pointer_entries = pointers["entries"]
    fragment_entries = fragments["fragments"]
    cross_references: list[dict[str, Any]] = []
    mismatch_rows = 0
    extent_mismatch_count = 0
    terminal_sentinel_count = sum(
        fragment["is_end_of_table"] for fragment in fragment_entries
    )

    for index in range(min(len(pointer_entries), len(fragment_entries))):
        pointer = pointer_entries[index]
        fragment = fragment_entries[index]
        expression = pointer["expression"]
        target_match = _POINTER_TARGET_RE.fullmatch(expression)
        expected_label = (
            f".{target_match.group(1)}" if target_match is not None else None
        )
        label_matches = expected_label is not None and (
            expected_label == fragment["fragment_label"]
        )
        expression_matches = expression == fragment["pointer_expression"]
        offset_matches = (
            pointer["entry_file_offset"] == fragment["pointer_entry_file_offset"]
        )
        index_matches = pointer["table_index"] == fragment["pointer_index"]
        cross_reference_matches = (
            label_matches and expression_matches and offset_matches and index_matches
        )
        if not cross_reference_matches:
            mismatch_rows += 1

        if target_match is None:
            add_finding(
                "unsupported_pointer_expression",
                "error",
                "Pointer expression does not match DictionaryEntries_suffix syntax.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )
        if target_match is not None and not label_matches:
            add_finding(
                "fragment_label_mismatch",
                "error",
                f"Pointer suffix implies {expected_label!r}, but inventory records "
                f"{fragment['fragment_label']!r}.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )
        if not expression_matches:
            add_finding(
                "fragment_pointer_expression_mismatch",
                "error",
                "Pointer expression differs between the two registered exports.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )
        if not offset_matches:
            add_finding(
                "pointer_entry_offset_mismatch",
                "error",
                "Pointer entry offset differs between the two registered exports.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )
        if not index_matches:
            add_finding(
                "pointer_index_mismatch",
                "error",
                "Pointer index differs between the two registered exports.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )

        if fragment["source_extent_matches_directive"] is False:
            extent_mismatch_count += 1
            add_finding(
                "source_extent_mismatch",
                "warning",
                f"Source extent is {fragment['source_extent_bytes']} byte(s), while the "
                f"declared directive values describe {fragment['declared_payload_bytes']} "
                "byte(s); neither value was changed by this audit.",
                pointer_index=index,
                pointer_expression=expression,
                fragment_label=fragment["fragment_label"],
            )

        cross_references.append({
            "pointer_index": index,
            "pointer_entry_file_offset": pointer["entry_file_offset"],
            "pointer_expression": expression,
            "fragment_index": fragment["pointer_index"],
            "fragment_pointer_expression": fragment["pointer_expression"],
            "expected_fragment_label": expected_label,
            "fragment_label": fragment["fragment_label"],
            "fragment_file_offset": fragment["fragment_file_offset"],
            "next_fragment_file_offset": fragment["next_fragment_file_offset"],
            "source_extent_bytes": fragment["source_extent_bytes"],
            "data_directive": fragment["data_directive"],
            "declared_payload_bytes": fragment["declared_payload_bytes"],
            "source_extent_matches_directive": fragment["source_extent_matches_directive"],
            "is_end_of_table": fragment["is_end_of_table"],
            "cross_reference_matches": cross_reference_matches,
        })

    for index in range(min(len(pointer_entries), len(fragment_entries)), len(pointer_entries)):
        pointer = pointer_entries[index]
        add_finding(
            "entry_count_mismatch",
            "error",
            "Pointer entry has no fragment record at the same index.",
            pointer_index=index,
            pointer_expression=pointer["expression"],
        )
    for index in range(min(len(pointer_entries), len(fragment_entries)), len(fragment_entries)):
        fragment = fragment_entries[index]
        add_finding(
            "entry_count_mismatch",
            "error",
            "Fragment record has no pointer entry at the same index.",
            pointer_index=index,
            pointer_expression=fragment["pointer_expression"],
            fragment_label=fragment["fragment_label"],
        )

    if pointer_entries:
        final_expression = pointer_entries[-1]["expression"]
        final_fragment = fragment_entries[-1] if fragment_entries else None
        final_target = _POINTER_TARGET_RE.fullmatch(final_expression)
        final_is_sentinel = final_target is not None and final_target.group(1) == "endOfTable"
        if (
            not final_is_sentinel
            or final_fragment is None
            or not final_fragment["is_end_of_table"]
            or final_fragment["data_directive"] is not None
            or final_fragment["next_fragment_file_offset"] is not None
        ):
            add_finding(
                "terminal_sentinel_mismatch",
                "error",
                "The final pointer and final fragment do not agree on the endOfTable sentinel.",
                pointer_index=len(pointer_entries) - 1,
                pointer_expression=final_expression,
                fragment_label=final_fragment["fragment_label"] if final_fragment else None,
            )

    for fragment in fragment_entries[:-1]:
        if fragment["is_end_of_table"]:
            add_finding(
                "unexpected_end_sentinel",
                "error",
                "An endOfTable marker appears before the final fragment record.",
                pointer_index=fragment["pointer_index"],
                pointer_expression=fragment["pointer_expression"],
                fragment_label=fragment["fragment_label"],
            )

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    return {
        "format": TEXT_DICTIONARY_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "pointer_asset_name": pointer_asset_name,
        "fragment_asset_name": fragment_asset_name,
        "source_file": pointers["source_file"],
        "source_revision": pointers["source_revision"],
        "cross_references": cross_references,
        "findings": findings,
        "summary": {
            "pointer_entry_count": len(pointer_entries),
            "fragment_count": len(fragment_entries),
            "cross_reference_count": len(cross_references),
            "cross_reference_mismatch_count": mismatch_rows + abs(
                len(pointer_entries) - len(fragment_entries)
            ),
            "source_extent_mismatch_count": extent_mismatch_count,
            "terminal_sentinel_count": terminal_sentinel_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "fragment_bytes_read": False,
            "pointer_values_resolved": False,
            "offsets_verified": False,
        },
    }
