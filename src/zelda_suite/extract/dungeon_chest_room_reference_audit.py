"""Cross-reference packed dungeon chest room values with source room-pointer slots."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DUNGEON_CHEST_DATA_FORMAT,
    POINTER_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

DUNGEON_CHEST_ROOM_REFERENCE_AUDIT_FORMAT = "zelda-suite-dungeon-chest-room-reference-audit"
CHEST_ASSET_NAME = "dungeon-chest-data"
OBJECT_POINTER_ASSET_NAME = "dungeon-room-object-pointers"
DOOR_POINTER_ASSET_NAME = "dungeon-room-door-pointers"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
CHEST_SOURCE_FILE = "Bank01.asm"
CHEST_TABLE_LABEL = "Dungeon_ChestData"
CHEST_TABLE_START_OFFSET = 0x00E96E
CHEST_TABLE_END_OFFSET = 0x00EB65
CHEST_ENTRY_WIDTH = 3
CHEST_ENTRY_COUNT = 168
OBJECT_POINTER_SOURCE_FILE = "Bank1F.asm"
OBJECT_POINTER_TABLE_LABEL = "RoomData_ObjectDataPointers"
OBJECT_POINTER_TABLE_OFFSET = 0x0F8000
DOOR_POINTER_SOURCE_FILE = "Bank1F.asm"
DOOR_POINTER_TABLE_LABEL = "RoomData_DoorDataPointers"
DOOR_POINTER_TABLE_OFFSET = 0x0F83C0
POINTER_ENTRY_WIDTH = 3
POINTER_ENTRY_COUNT = 320


class DungeonChestRoomReferenceAuditError(ValueError):
    """Raised when the pinned chest/room pointer exports cannot be audited safely."""


def audit_dungeon_chest_room_references(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Join packed chest room values to the corresponding object/door pointer slots.

    The pinned Bank01.asm consumer compares the chest record's low 15 bits with
    the current room value, then indexes the room pointer tables with room_index*3.
    This audit verifies only those source-metadata relationships; it does not read
    payload/ROM bytes or determine which pointer slots represent playable rooms.
    """
    try:
        registered = list_extracted_assets(registry_path)
        by_name = {asset["name"]: asset for asset in registered}
        required = {
            CHEST_ASSET_NAME: DUNGEON_CHEST_DATA_FORMAT,
            OBJECT_POINTER_ASSET_NAME: POINTER_TABLE_FORMAT,
            DOOR_POINTER_ASSET_NAME: POINTER_TABLE_FORMAT,
        }
        for name, expected_format in required.items():
            asset = by_name.get(name)
            if asset is None:
                raise DungeonChestRoomReferenceAuditError(
                    f"dungeon chest room-reference asset is not registered: {name!r}"
                )
            if asset["format"] != expected_format:
                raise DungeonChestRoomReferenceAuditError(
                    f"asset {name!r} must use {expected_format!r}"
                )

        chest = load_extracted_asset(CHEST_ASSET_NAME, registry_path)
        objects = load_extracted_asset(OBJECT_POINTER_ASSET_NAME, registry_path)
        doors = load_extracted_asset(DOOR_POINTER_ASSET_NAME, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise DungeonChestRoomReferenceAuditError(str(exc)) from exc

    revisions = {
        chest["source_revision"],
        objects["source_revision"],
        doors["source_revision"],
    }
    if revisions != {PINNED_SOURCE_REVISION}:
        rendered = ", ".join(sorted(revisions))
        raise DungeonChestRoomReferenceAuditError(
            "dungeon chest room-reference audit is pinned to source revision "
            f"{PINNED_SOURCE_REVISION!r}; registered revisions were: {rendered}"
        )

    findings: list[dict[str, Any]] = []

    def add_finding(
        code: str,
        severity: str,
        message: str,
        *,
        chest_table_index: int | None = None,
        room_value: int | None = None,
        object_pointer_target_label: str | None = None,
        door_pointer_target_label: str | None = None,
    ) -> None:
        findings.append({
            "code": code,
            "severity": severity,
            "message": message,
            "chest_table_index": chest_table_index,
            "room_value": room_value,
            "object_pointer_target_label": object_pointer_target_label,
            "door_pointer_target_label": door_pointer_target_label,
        })

    if (
        chest["source_file"] != CHEST_SOURCE_FILE
        or chest["table_label"] != CHEST_TABLE_LABEL
        or chest["source_annotated_start_offset"] != CHEST_TABLE_START_OFFSET
        or chest["source_annotated_end_offset"] != CHEST_TABLE_END_OFFSET
        or chest["entry_width_bytes"] != CHEST_ENTRY_WIDTH
        or chest["entry_count"] != CHEST_ENTRY_COUNT
    ):
        add_finding(
            "chest_table_metadata_mismatch",
            "error",
            "The chest export does not match the pinned 168-entry "
            "Dungeon_ChestData declaration at source-annotated $00E96E-$00EB65.",
        )

    if (
        objects["source_file"] != OBJECT_POINTER_SOURCE_FILE
        or objects["table_label"] != OBJECT_POINTER_TABLE_LABEL
        or objects["table_file_offset"] != OBJECT_POINTER_TABLE_OFFSET
        or objects["entry_width"] != POINTER_ENTRY_WIDTH
        or objects["entry_count"] != POINTER_ENTRY_COUNT
    ):
        add_finding(
            "object_pointer_table_metadata_mismatch",
            "error",
            "The object-pointer export does not match the pinned 320-entry "
            "RoomData_ObjectDataPointers declaration at source-commented $0F8000.",
        )

    if (
        doors["source_file"] != DOOR_POINTER_SOURCE_FILE
        or doors["table_label"] != DOOR_POINTER_TABLE_LABEL
        or doors["table_file_offset"] != DOOR_POINTER_TABLE_OFFSET
        or doors["entry_width"] != POINTER_ENTRY_WIDTH
        or doors["entry_count"] != POINTER_ENTRY_COUNT
    ):
        add_finding(
            "door_pointer_table_metadata_mismatch",
            "error",
            "The door-pointer export does not match the pinned 320-entry "
            "RoomData_DoorDataPointers declaration at source-commented $0F83C0.",
        )

    object_entries = {entry["table_index"]: entry for entry in objects["entries"]}
    door_entries = {entry["table_index"]: entry for entry in doors["entries"]}
    chest_entries = chest["entries"]
    grouped_by_room: dict[int, list[dict[str, Any]]] = defaultdict(list)
    cross_references: list[dict[str, Any]] = []
    out_of_range_entry_count = 0
    in_range_entry_count = 0
    empty_object_target_chest_count = 0

    for entry in chest_entries:
        room_value = entry["room_value"]
        grouped_by_room[room_value].append(entry)
        object_entry = object_entries.get(room_value)
        door_entry = door_entries.get(room_value)
        in_range = object_entry is not None and door_entry is not None
        if in_range:
            in_range_entry_count += 1
        else:
            out_of_range_entry_count += 1
            add_finding(
                "room_value_out_of_pointer_range",
                "error",
                f"Chest room value {room_value} does not resolve to a slot in both "
                f"320-entry source pointer tables (chest entry {entry['table_index']}).",
                chest_table_index=entry["table_index"],
                room_value=room_value,
            )

        object_label = object_entry["target_label"] if object_entry is not None else None
        door_label = door_entry["target_label"] if door_entry is not None else None
        targets_match = (
            object_label == door_label
            if object_entry is not None and door_entry is not None
            else None
        )
        if object_entry is not None and object_entry["is_empty_target"]:
            empty_object_target_chest_count += 1
        cross_references.append({
            "chest_table_index": entry["table_index"],
            "chest_source_line": entry["source_line"],
            "chest_expression": entry["expression"],
            "room_value": room_value,
            "item_value": entry["item_value"],
            "is_big_chest": entry["is_big_chest"],
            "room_pointer_table_index": room_value if in_range else None,
            "room_value_in_pointer_tables": in_range,
            "object_pointer_target_label": object_label,
            "object_pointer_is_empty_target": (
                object_entry["is_empty_target"] if object_entry is not None else None
            ),
            "door_pointer_target_label": door_label,
            "door_pointer_target_addend": (
                door_entry["target_addend"] if door_entry is not None else None
            ),
            "pointer_target_labels_match": targets_match,
        })

    object_door_mismatch_room_values = sorted({
        room_value
        for room_value in grouped_by_room
        if (
            room_value in object_entries
            and room_value in door_entries
            and object_entries[room_value]["target_label"]
            != door_entries[room_value]["target_label"]
        )
    })
    for room_value in object_door_mismatch_room_values:
        add_finding(
            "object_door_pointer_target_mismatch",
            "error",
            f"Room index {room_value} has different target labels in the object- and "
            "door-pointer tables.",
            room_value=room_value,
            object_pointer_target_label=object_entries[room_value]["target_label"],
            door_pointer_target_label=door_entries[room_value]["target_label"],
        )

    room_groups: list[dict[str, Any]] = []
    for room_value, group in sorted(grouped_by_room.items()):
        object_entry = object_entries.get(room_value)
        door_entry = door_entries.get(room_value)
        in_range = object_entry is not None and door_entry is not None
        room_groups.append({
            "room_value": room_value,
            "chest_entry_count": len(group),
            "chest_table_indexes": [entry["table_index"] for entry in group],
            "item_values": [entry["item_value"] for entry in group],
            "big_chest_entry_indexes": [
                entry["table_index"] for entry in group if entry["is_big_chest"]
            ],
            "room_pointer_table_index": room_value if in_range else None,
            "room_value_in_pointer_tables": in_range,
            "object_pointer_target_label": (
                object_entry["target_label"] if object_entry is not None else None
            ),
            "object_pointer_is_empty_target": (
                object_entry["is_empty_target"] if object_entry is not None else None
            ),
            "door_pointer_target_label": (
                door_entry["target_label"] if door_entry is not None else None
            ),
            "door_pointer_target_addend": (
                door_entry["target_addend"] if door_entry is not None else None
            ),
            "pointer_target_labels_match": (
                object_entry["target_label"] == door_entry["target_label"]
                if object_entry is not None and door_entry is not None
                else None
            ),
        })

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    return {
        "format": DUNGEON_CHEST_ROOM_REFERENCE_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "source_revision": PINNED_SOURCE_REVISION,
        "chest_asset_name": CHEST_ASSET_NAME,
        "object_pointer_asset_name": OBJECT_POINTER_ASSET_NAME,
        "door_pointer_asset_name": DOOR_POINTER_ASSET_NAME,
        "room_groups": room_groups,
        "cross_references": cross_references,
        "object_door_pointer_mismatch_room_values": object_door_mismatch_room_values,
        "findings": findings,
        "summary": {
            "chest_entry_count": len(chest_entries),
            "unique_room_value_count": len(grouped_by_room),
            "room_values_with_multiple_chests": sum(
                len(group) > 1 for group in grouped_by_room.values()
            ),
            "chest_entries_with_pointer_slots": in_range_entry_count,
            "chest_entries_without_pointer_slots": out_of_range_entry_count,
            "unique_room_values_without_pointer_slots": sum(
                room_value not in object_entries or room_value not in door_entries
                for room_value in grouped_by_room
            ),
            "empty_object_pointer_target_chest_count": empty_object_target_chest_count,
            "unique_room_values_targeting_empty_object_pointer": sum(
                room_value in object_entries and object_entries[room_value]["is_empty_target"]
                for room_value in grouped_by_room
            ),
            "object_door_pointer_target_mismatch_room_count": len(
                object_door_mismatch_room_values
            ),
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
            "minimum_room_value": min(grouped_by_room) if grouped_by_room else None,
            "maximum_room_value": max(grouped_by_room) if grouped_by_room else None,
        },
        "source_semantics": {
            "source_file": "Bank01.asm",
            "source_revision": PINNED_SOURCE_REVISION,
            "chest_field_comment_lines": [15108, 15109],
            "chest_room_compare_line": 15231,
            "chest_item_value_load_line": 15236,
            "chest_big_chest_flag_test_line": 15239,
            "room_index_times_three_comment_line": 7908,
            "room_index_times_three_calculation_line": 7909,
            "door_pointer_read_lines": [7910, 7911],
            "object_pointer_room_index_comment_line": 826,
            "object_pointer_read_lines": [828, 829],
            "relationship_description": (
                "The source comments describe the low 15 bits as the room value. "
                "The chest consumer masks with $7FFF and compares that value to $A0; "
                "the pointer consumer computes $A0*3 and uses it to read the door-"
                "data pointer, while the object-data consumer uses the same room "
                "index times three to read the object pointer."
            ),
            "room_value_is_used_to_select_pointer_slot_in_source": True,
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "room_payload_bytes_read": False,
            "room_value_compared_to_source_pointer_slots": True,
            "source_consumer_relationship_traced": True,
            "pointer_offsets_verified": False,
            "payload_bytes_verified": False,
            "item_value_names_resolved": False,
            "playable_room_set_resolved": False,
        },
    }
