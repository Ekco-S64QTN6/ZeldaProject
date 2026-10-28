"""Audit packed Dungeon_ChestData room/item fields from registered source metadata."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DUNGEON_CHEST_DATA_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

DUNGEON_CHEST_DATA_AUDIT_FORMAT = "zelda-suite-dungeon-chest-data-audit"
DUNGEON_CHEST_DATA_ASSET_NAME = "dungeon-chest-data"


class DungeonChestDataAuditError(ValueError):
    """Raised when the registered chest inventory cannot be audited."""


def audit_dungeon_chest_data(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = DUNGEON_CHEST_DATA_ASSET_NAME,
) -> dict[str, Any]:
    """Summarize raw room/item values and repeated-room entries without resolving IDs."""
    try:
        records = list_extracted_assets(registry_path)
        record_by_name = {record["name"]: record for record in records}
        record = record_by_name.get(asset_name)
        if record is None:
            raise DungeonChestDataAuditError(
                f"dungeon chest data asset is not registered: {asset_name!r}"
            )
        if record["format"] != DUNGEON_CHEST_DATA_FORMAT:
            raise DungeonChestDataAuditError(
                f"asset {asset_name!r} must use {DUNGEON_CHEST_DATA_FORMAT!r}"
            )
        payload = load_extracted_asset(asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise DungeonChestDataAuditError(str(exc)) from exc

    entries = payload["entries"]
    grouped_by_room: dict[int, list[dict[str, Any]]] = defaultdict(list)
    grouped_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped_by_room[entry["room_value"]].append(entry)
        grouped_by_item[entry["item_value"]].append(entry)

    def room_view(room_value: int, group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "room_value": room_value,
            "entry_count": len(group),
            "entry_indexes": [entry["table_index"] for entry in group],
            "item_values": [entry["item_value"] for entry in group],
            "big_chest_entry_indexes": [
                entry["table_index"] for entry in group if entry["is_big_chest"]
            ],
        }

    room_groups = [
        room_view(room_value, grouped_by_room[room_value])
        for room_value in sorted(grouped_by_room)
    ]
    duplicate_room_groups = [
        group for group in room_groups if group["entry_count"] > 1
    ]
    item_value_distribution = [
        {
            "item_value": item_value,
            "entry_count": len(group),
            "entry_indexes": [entry["table_index"] for entry in group],
        }
        for item_value, group in sorted(grouped_by_item.items())
    ]
    big_chest_count = sum(entry["is_big_chest"] for entry in entries)

    return {
        "format": DUNGEON_CHEST_DATA_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "source_file": payload["source_file"],
        "source_revision": payload["source_revision"],
        "table_label": payload["table_label"],
        "source_range_annotation": payload["source_range_annotation"],
        "source_annotated_start_offset": payload["source_annotated_start_offset"],
        "source_annotated_end_offset": payload["source_annotated_end_offset"],
        "room_groups": room_groups,
        "duplicate_room_groups": duplicate_room_groups,
        "item_value_distribution": item_value_distribution,
        "summary": {
            "entry_count": len(entries),
            "unique_room_value_count": len(grouped_by_room),
            "room_values_with_multiple_entries": len(duplicate_room_groups),
            "big_chest_count": big_chest_count,
            "small_chest_count": len(entries) - big_chest_count,
            "distinct_item_value_count": len(grouped_by_item),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "source_range_offsets_verified": False,
            "item_value_names_resolved": False,
            "room_values_verified_against_rom": False,
        },
    }
