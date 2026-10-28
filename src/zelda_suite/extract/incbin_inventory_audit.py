"""Source-only diagnostics across registered Asar incbin inventories.

The audit compares metadata already recorded in exports. It does not read
included payloads or ROM bytes, and it treats every offset-derived span as a
candidate rather than verified ROM truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    INCBIN_INVENTORY_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

INCBIN_INVENTORY_AUDIT_FORMAT = "zelda-suite-incbin-inventory-audit"


class IncbinInventoryAuditError(ValueError):
    """Raised when registered incbin metadata cannot be audited safely."""


def audit_incbin_inventories(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Audit registered incbin metadata while preserving unresolved source facts.

    Range mismatches, metadata gaps, and candidate overlaps are diagnostics.
    They do not establish which source annotation is wrong or whether any
    candidate offset maps to the intended bytes in a ROM.
    """
    try:
        registered_assets = list_extracted_assets(registry_path)
    except (AssetLoadError, OSError) as exc:
        raise IncbinInventoryAuditError(str(exc)) from exc

    assets = sorted(
        (
            asset for asset in registered_assets
            if asset["format"] == INCBIN_INVENTORY_FORMAT
        ),
        key=lambda asset: asset["name"],
    )
    if not assets:
        raise IncbinInventoryAuditError(
            f"registry contains no {INCBIN_INVENTORY_FORMAT!r} assets: {registry_path}"
        )

    inventory_reports: list[dict[str, Any]] = []
    metadata_gaps: list[dict[str, Any]] = []
    range_mismatches: list[dict[str, Any]] = []
    candidate_spans: list[dict[str, Any]] = []
    declaration_total = 0
    located_total = 0
    missing_start_total = 0
    missing_size_total = 0

    for asset in assets:
        try:
            payload = load_extracted_asset(asset["name"], registry_path)
        except (AssetLoadError, OSError) as exc:
            raise IncbinInventoryAuditError(str(exc)) from exc

        declarations = payload["declarations"]
        asset_missing_start = 0
        asset_missing_size = 0
        asset_range_mismatches = 0
        for declaration in declarations:
            start = declaration["source_file_offset_start"]
            size = declaration["declared_size_bytes"]
            end_annotation = declaration["source_file_offset_end"]
            if start is not None and size is not None:
                located_total += 1

            missing_fields: list[str] = []
            if start is None:
                missing_fields.append("source_file_offset_start")
                asset_missing_start += 1
                missing_start_total += 1
            if size is None:
                missing_fields.append("declared_size_bytes")
                asset_missing_size += 1
                missing_size_total += 1

            context = {
                "asset_name": asset["name"],
                "source_file": declaration["source_file"],
                "source_revision": declaration["source_revision"],
                "label": declaration["label"],
                "source_line": declaration["source_line"],
            }
            if missing_fields:
                metadata_gaps.append({**context, "missing_fields": missing_fields})

            if declaration["source_range_size_matches"] is False:
                asset_range_mismatches += 1
                range_mismatches.append({
                    **context,
                    "source_file_offset_start": start,
                    "source_file_offset_end": end_annotation,
                    "declared_size_bytes": size,
                    "computed_file_offset_end": declaration["computed_file_offset_end"],
                })

            # A zero-byte declaration has no inclusive last byte, so it does
            # not create a candidate span. Its source facts remain in inventory.
            if start is not None and size is not None and size > 0:
                candidate_spans.append({
                    **context,
                    "file_offset_start": start,
                    "file_offset_end": start + size - 1,
                    "declared_size_bytes": size,
                    "source_file_offset_end_annotation": end_annotation,
                })

        inventory_reports.append({
            "asset_name": asset["name"],
            "source_file": payload["source_file"],
            "source_revision": payload["source_revision"],
            "declaration_count": len(declarations),
            "missing_start_count": asset_missing_start,
            "missing_size_count": asset_missing_size,
            "range_mismatch_count": asset_range_mismatches,
        })
        declaration_total += len(declarations)

    candidate_spans.sort(key=lambda span: (
        span["file_offset_start"],
        span["file_offset_end"],
        span["asset_name"],
        span["label"],
        span["source_file"],
    ))

    candidate_overlaps: list[dict[str, Any]] = []
    for left_index, left in enumerate(candidate_spans):
        for right in candidate_spans[left_index + 1:]:
            if right["file_offset_start"] > left["file_offset_end"]:
                break
            overlap_start = max(left["file_offset_start"], right["file_offset_start"])
            overlap_end = min(left["file_offset_end"], right["file_offset_end"])
            if overlap_start <= overlap_end:
                candidate_overlaps.append({
                    "left": left,
                    "right": right,
                    "overlap_start": overlap_start,
                    "overlap_end": overlap_end,
                    "overlap_size_bytes": overlap_end - overlap_start + 1,
                })

    summary = {
        "inventory_count": len(inventory_reports),
        "declaration_count": declaration_total,
        "located_declaration_count": located_total,
        "missing_start_count": missing_start_total,
        "missing_size_count": missing_size_total,
        "metadata_gap_count": len(metadata_gaps),
        "range_mismatch_count": len(range_mismatches),
        "candidate_span_count": len(candidate_spans),
        "candidate_overlap_count": len(candidate_overlaps),
        "finding_count": (
            len(metadata_gaps) + len(range_mismatches) + len(candidate_overlaps)
        ),
    }
    return {
        "format": INCBIN_INVENTORY_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "inventories": inventory_reports,
        "metadata_gaps": metadata_gaps,
        "range_mismatches": range_mismatches,
        "candidate_spans": candidate_spans,
        "candidate_overlaps": candidate_overlaps,
        "summary": summary,
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "payload_bytes_read": False,
            "offsets_verified": False,
        },
    }
