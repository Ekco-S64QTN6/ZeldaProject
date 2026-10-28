"""Audit the source-comment IDs attached to the dense receive-item graphics table."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT = "zelda-suite-item-receipt-annotation-audit"
ITEM_RECEIPT_GRAPHICS_ASSET_NAME = "item-receipt-graphics-indices"
EXPECTED_ITEM_RECEIPT_GRAPHICS_ENTRY_COUNT = 76

_COMMENT_ANNOTATION_RE = re.compile(
    r"\s*0x(?P<item_id>[0-9A-Fa-f]{2})\s*-\s*(?P<label>.+?)\s*"
)


class ItemReceiptAnnotationAuditError(ValueError):
    """Raised when the registered receive-item graphics annotation data is invalid."""


def audit_item_receipt_annotations(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
) -> dict[str, Any]:
    """Report inline-comment IDs separately from dense table indexes.

    The source table is indexed densely by its consumer. Inline-comment IDs are
    evidence only: the comments omit 0x40, which means entries at table indexes
    0x40 through 0x4B carry comments labeled 0x41 through 0x4C. No labels are
    normalized into canonical item IDs by this audit.
    """
    try:
        records = list_extracted_assets(registry_path)
        record_by_name = {record["name"]: record for record in records}
        record = record_by_name.get(asset_name)
        if record is None:
            raise ItemReceiptAnnotationAuditError(
                f"item-receipt graphics asset is not registered: {asset_name!r}"
            )
        if record["format"] != DATA_TABLE_FORMAT:
            raise ItemReceiptAnnotationAuditError(
                f"asset {asset_name!r} must use {DATA_TABLE_FORMAT!r}"
            )
        payload = load_extracted_asset(asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise ItemReceiptAnnotationAuditError(str(exc)) from exc

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ItemReceiptAnnotationAuditError("graphics-index entries must be an array")
    if len(entries) != EXPECTED_ITEM_RECEIPT_GRAPHICS_ENTRY_COUNT:
        raise ItemReceiptAnnotationAuditError(
            f"graphics-index table has {len(entries)} entries; expected "
            f"{EXPECTED_ITEM_RECEIPT_GRAPHICS_ENTRY_COUNT}"
        )

    report_entries: list[dict[str, Any]] = []
    seen_ids: Counter[int] = Counter()
    for expected_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ItemReceiptAnnotationAuditError(
                f"graphics-index entry {expected_index} must be an object"
            )
        table_index = entry.get("table_index")
        if isinstance(table_index, bool) or table_index != expected_index:
            raise ItemReceiptAnnotationAuditError(
                f"graphics-index table_index at position {expected_index} is invalid"
            )
        inline_comment = entry.get("inline_comment")
        source_comment_item_id: int | None = None
        source_comment_label: str | None = None
        matches_index: bool | None = None
        annotation_id_delta: int | None = None
        parsed = False
        if isinstance(inline_comment, str):
            match = _COMMENT_ANNOTATION_RE.fullmatch(inline_comment)
            if match is not None:
                source_comment_item_id = int(match.group("item_id"), 16)
                source_comment_label = match.group("label").strip()
                if source_comment_label:
                    parsed = True
                    seen_ids[source_comment_item_id] += 1
                    matches_index = source_comment_item_id == table_index
                    annotation_id_delta = source_comment_item_id - table_index

        report_entries.append({
            "table_index": table_index,
            "entry_file_offset": entry.get("entry_file_offset"),
            "expression": entry.get("expression"),
            "literal_value": entry.get("literal_value"),
            "source_line": entry.get("source_line"),
            "source_comment": inline_comment,
            "source_comment_item_id": source_comment_item_id,
            "source_comment_label": source_comment_label,
            "source_comment_annotation_parsed": parsed,
            "source_comment_id_matches_table_index": matches_index,
            "annotation_id_delta": annotation_id_delta,
        })

    parsed_entries = [
        entry for entry in report_entries if entry["source_comment_annotation_parsed"]
    ]
    matched_entries = [
        entry
        for entry in parsed_entries
        if entry["source_comment_id_matches_table_index"] is True
    ]
    mismatched_entries = [
        entry
        for entry in parsed_entries
        if entry["source_comment_id_matches_table_index"] is False
    ]
    maximum_comment_id = max(seen_ids, default=-1)
    missing_ids = [
        item_id for item_id in range(maximum_comment_id + 1) if item_id not in seen_ids
    ]
    duplicate_ids = sorted(item_id for item_id, count in seen_ids.items() if count > 1)

    return {
        "format": ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "source_file": payload["source_file"],
        "source_revision": payload["source_revision"],
        "table_label": payload["table_label"],
        "entry_count": len(report_entries),
        "entries": report_entries,
        "mismatched_entries": [entry["table_index"] for entry in mismatched_entries],
        "missing_source_comment_ids": missing_ids,
        "duplicate_source_comment_ids": duplicate_ids,
        "summary": {
            "table_entry_count": len(report_entries),
            "parsed_source_comment_count": len(parsed_entries),
            "source_comment_parse_failure_count": len(report_entries) - len(parsed_entries),
            "source_comment_ids_matching_table_index_count": len(matched_entries),
            "source_comment_ids_mismatched_count": len(mismatched_entries),
            "missing_source_comment_id_count": len(missing_ids),
            "duplicate_source_comment_id_count": len(duplicate_ids),
            "first_mismatched_table_index": (
                mismatched_entries[0]["table_index"] if mismatched_entries else None
            ),
            "last_mismatched_table_index": (
                mismatched_entries[-1]["table_index"] if mismatched_entries else None
            ),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "canonical_item_ids_resolved": False,
            "semantic_item_names_resolved": False,
            "source_comments_corrected": False,
        },
    }
