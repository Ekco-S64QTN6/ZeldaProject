"""Build a source-only structured view of the OAM allocator lookup table."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

OAM_ALLOCATION_AUDIT_FORMAT = "zelda-suite-oam-allocation-audit"
OAM_TABLE_ASSET_NAME = "oam-buffer-position-table"
OAM_SOURCE_FILE = "sprite_oam_allocation.asm"
OAM_TABLE_LABEL = "Pool_OAM_GetBufferPosition"
OAM_TABLE_FILE_OFFSET = 0x06BA9E
OAM_TABLE_ENTRY_COUNT = 54
OAM_LIMIT_ENTRY_COUNT = 6
OAM_FALLBACKS_PER_REGION = 8
OAM_REGION_NAMES = ("A", "B", "C", "D", "E", "F")
OAM_ALLOCATOR_Y_VALUES = (0x00, 0x02, 0x04, 0x06, 0x08, 0x0A)


class OAMAllocationAuditError(ValueError):
    """Raised when the registered OAM source table is missing or inconsistent."""


def _entry_view(entry: dict[str, Any]) -> dict[str, Any]:
    """Return only the stable version-1 entry fields used by the audit report."""
    return {
        "table_index": entry["table_index"],
        "entry_file_offset": entry["entry_file_offset"],
        "source_line": entry["source_line"],
        "source_label": entry["source_label"],
        "expression": entry["expression"],
        "literal_value": entry["literal_value"],
        "source_revision": entry["source_revision"],
    }


def audit_oam_allocation(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    table_asset_name: str = OAM_TABLE_ASSET_NAME,
) -> dict[str, Any]:
    """Join the six OAM limits to their eight fallback words per allocator region.

    This report interprets source labels and the lookup shape only. It does not
    execute the allocator, read a ROM, or establish that source-commented
    offsets are accurate for any specific ROM image.
    """
    try:
        records = list_extracted_assets(registry_path)
        record_by_name = {record["name"]: record for record in records}
        record = record_by_name.get(table_asset_name)
        if record is None:
            raise OAMAllocationAuditError(
                f"OAM allocation table asset is not registered: {table_asset_name!r}"
            )
        if record["format"] != DATA_TABLE_FORMAT:
            raise OAMAllocationAuditError(
                f"asset {table_asset_name!r} must use {DATA_TABLE_FORMAT!r}"
            )
        payload = load_extracted_asset(table_asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise OAMAllocationAuditError(str(exc)) from exc

    problems: list[str] = []
    expected_header = {
        "source_file": OAM_SOURCE_FILE,
        "table_label": OAM_TABLE_LABEL,
        "table_file_offset": OAM_TABLE_FILE_OFFSET,
        "directive": "dw",
        "entry_width": 2,
        "entry_count": OAM_TABLE_ENTRY_COUNT,
    }
    for field, expected in expected_header.items():
        if payload.get(field) != expected:
            problems.append(f"{field} must be {expected!r}")
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != OAM_TABLE_ENTRY_COUNT:
        actual_count = len(entries) if isinstance(entries, list) else "not a list"
        problems.append(
            f"entries must contain {OAM_TABLE_ENTRY_COUNT} records, got {actual_count}"
        )
        entries = entries if isinstance(entries, list) else []

    if payload.get("source_revision") != record["source_revision"]:
        problems.append("source_revision does not match the registered asset")

    for index, entry in enumerate(entries):
        expected_label = ".limits" if index < OAM_LIMIT_ENTRY_COUNT else ".fallback_points"
        if not isinstance(entry, dict):
            problems.append(f"entries[{index}] must be an object")
            continue
        if entry.get("table_index") != index:
            problems.append(f"entries[{index}].table_index must be {index}")
        expected_offset = OAM_TABLE_FILE_OFFSET + index * 2
        if entry.get("entry_file_offset") != expected_offset:
            problems.append(
                f"entries[{index}].entry_file_offset must be {expected_offset:#x}"
            )
        if entry.get("source_label") != expected_label:
            problems.append(
                f"entries[{index}].source_label must be {expected_label!r}"
            )
        value = entry.get("literal_value")
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFF:
            problems.append(f"entries[{index}].literal_value must be a 16-bit integer")
        if entry.get("source_revision") != payload.get("source_revision"):
            problems.append(f"entries[{index}].source_revision does not match the table")

    if problems:
        raise OAMAllocationAuditError(
            "invalid registered OAM allocation table: " + "; ".join(problems)
        )

    # The checks above establish every entry is a dict with the required shape.
    valid_entries = [entry for entry in entries if isinstance(entry, dict)]
    regions: list[dict[str, Any]] = []
    for region_index, region_name in enumerate(OAM_REGION_NAMES):
        limit_entry = valid_entries[region_index]
        fallback_start = OAM_LIMIT_ENTRY_COUNT + region_index * OAM_FALLBACKS_PER_REGION
        fallback_points = [
            {
                "overflow_counter_slot": counter_slot,
                "entry": _entry_view(valid_entries[fallback_start + counter_slot]),
            }
            for counter_slot in range(OAM_FALLBACKS_PER_REGION)
        ]
        regions.append({
            "region_name": region_name,
            "allocator_y": OAM_ALLOCATOR_Y_VALUES[region_index],
            "limit_entry": _entry_view(limit_entry),
            "fallback_points": fallback_points,
        })

    return {
        "format": OAM_ALLOCATION_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "table_asset_name": table_asset_name,
        "source_file": payload["source_file"],
        "source_revision": payload["source_revision"],
        "table_label": payload["table_label"],
        "table_file_offset": payload["table_file_offset"],
        "regions": regions,
        "summary": {
            "table_entry_count": len(valid_entries),
            "region_count": len(regions),
            "limit_entry_count": OAM_LIMIT_ENTRY_COUNT,
            "fallback_point_count": OAM_FALLBACKS_PER_REGION * len(regions),
            "fallback_points_per_region": OAM_FALLBACKS_PER_REGION,
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "oam_runtime_executed": False,
            "source_comment_offsets_verified": False,
            "oam_buffer_positions_verified": False,
        },
    }
