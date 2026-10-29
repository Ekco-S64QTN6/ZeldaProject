"""Read-only join of editable chest room values to source room-pointer metadata."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import AssetLoadError, load_extracted_asset
from zelda_suite.extract.dungeon_chest_room_reference_audit import (
    CHEST_ENTRY_COUNT,
    DOOR_POINTER_ASSET_NAME,
    DOOR_POINTER_SOURCE_FILE,
    DOOR_POINTER_TABLE_LABEL,
    DOOR_POINTER_TABLE_OFFSET,
    OBJECT_POINTER_ASSET_NAME,
    OBJECT_POINTER_SOURCE_FILE,
    OBJECT_POINTER_TABLE_LABEL,
    OBJECT_POINTER_TABLE_OFFSET,
    PINNED_SOURCE_REVISION,
    POINTER_ENTRY_COUNT,
    POINTER_ENTRY_WIDTH,
)
from zelda_suite.project.store import get_dungeon_chest_model

PROJECT_DUNGEON_CHEST_ROOM_REFERENCE_AUDIT_FORMAT = (
    "zelda-suite-project-dungeon-chest-room-reference-audit"
)


class ProjectDungeonChestRoomReferenceAuditError(ValueError):
    """Raised when project chest records cannot be joined safely to pointer metadata."""


def _index_pointer_entries(
    payload: dict[str, Any], *, asset_name: str
) -> dict[int, dict[str, Any]]:
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != POINTER_ENTRY_COUNT:
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"{asset_name!r} must contain {POINTER_ENTRY_COUNT} pointer entries"
        )

    indexed: dict[int, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProjectDungeonChestRoomReferenceAuditError(
                f"{asset_name!r} contains a malformed pointer entry"
            )
        index = entry.get("table_index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ProjectDungeonChestRoomReferenceAuditError(
                f"{asset_name!r} contains a non-integer table index"
            )
        if index in indexed:
            raise ProjectDungeonChestRoomReferenceAuditError(
                f"{asset_name!r} contains duplicate table index {index}"
            )
        if entry.get("source_revision") != PINNED_SOURCE_REVISION:
            raise ProjectDungeonChestRoomReferenceAuditError(
                f"{asset_name!r} contains an entry from an unexpected source revision"
            )
        indexed[index] = entry

    if sorted(indexed) != list(range(POINTER_ENTRY_COUNT)):
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"{asset_name!r} indexes must cover 0..{POINTER_ENTRY_COUNT - 1}"
        )
    return indexed


def _load_pointer_table(
    registry_path: str | Path,
    *,
    asset_name: str,
    source_file: str,
    table_label: str,
    table_offset: int,
) -> dict[int, dict[str, Any]]:
    try:
        payload = load_extracted_asset(asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"could not load pointer asset {asset_name!r}: {exc}"
        ) from exc

    if (
        payload.get("source_file") != source_file
        or payload.get("source_revision") != PINNED_SOURCE_REVISION
        or payload.get("table_label") != table_label
        or payload.get("table_file_offset") != table_offset
        or payload.get("entry_width") != POINTER_ENTRY_WIDTH
        or payload.get("entry_count") != POINTER_ENTRY_COUNT
    ):
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"pointer asset {asset_name!r} does not match the pinned "
            f"{table_label} source table metadata"
        )
    return _index_pointer_entries(payload, asset_name=asset_name)


def audit_project_dungeon_chest_room_references(
    database_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Join current project chest room values to source pointer slots.

    The editable room value is used for the join; immutable source room values
    are included in every entry so that changed references remain auditable.
    This report reads project metadata and registered source exports only. It
    neither reads nor writes ROM bytes and does not verify candidate offsets.
    """
    try:
        model = get_dungeon_chest_model(database_path)
    except (OSError, ValueError) as exc:
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"could not read project dungeon chest model: {exc}"
        ) from exc
    if model is None:
        raise ProjectDungeonChestRoomReferenceAuditError(
            "no dungeon chest model has been imported; run "
            "'zelda-suite import-dungeon-chest-data' first"
        )

    if (
        model.get("format") != "zelda-suite-dungeon-chest-model"
        or model.get("format_version") != 1
        or model.get("source_revision") != PINNED_SOURCE_REVISION
        or model.get("entry_count") != CHEST_ENTRY_COUNT
    ):
        raise ProjectDungeonChestRoomReferenceAuditError(
            "project chest model does not match the pinned 168-entry Dungeon_ChestData model"
        )

    chest_entries = model.get("entries")
    if not isinstance(chest_entries, list) or len(chest_entries) != CHEST_ENTRY_COUNT:
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"project chest model must contain {CHEST_ENTRY_COUNT} entries"
        )
    chest_indexes = [
        entry.get("table_index") if isinstance(entry, dict) else None
        for entry in chest_entries
    ]
    if chest_indexes != list(range(CHEST_ENTRY_COUNT)):
        raise ProjectDungeonChestRoomReferenceAuditError(
            f"project chest indexes must cover 0..{CHEST_ENTRY_COUNT - 1} in source order"
        )

    source_sha256 = model.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_sha256)
    ):
        raise ProjectDungeonChestRoomReferenceAuditError(
            "project chest model has an invalid source SHA-256 digest"
        )

    object_entries = _load_pointer_table(
        registry_path,
        asset_name=OBJECT_POINTER_ASSET_NAME,
        source_file=OBJECT_POINTER_SOURCE_FILE,
        table_label=OBJECT_POINTER_TABLE_LABEL,
        table_offset=OBJECT_POINTER_TABLE_OFFSET,
    )
    door_entries = _load_pointer_table(
        registry_path,
        asset_name=DOOR_POINTER_ASSET_NAME,
        source_file=DOOR_POINTER_SOURCE_FILE,
        table_label=DOOR_POINTER_TABLE_LABEL,
        table_offset=DOOR_POINTER_TABLE_OFFSET,
    )

    findings: list[dict[str, Any]] = []

    def add_finding(
        code: str,
        message: str,
        *,
        chest_table_index: int,
        room_value: int,
        object_label: str | None,
        door_label: str | None,
    ) -> None:
        findings.append(
            {
                "code": code,
                "severity": "error",
                "message": message,
                "chest_table_index": chest_table_index,
                "room_value": room_value,
                "object_pointer_target_label": object_label,
                "door_pointer_target_label": door_label,
            }
        )

    grouped_by_room: dict[int, list[dict[str, Any]]] = {}
    report_entries: list[dict[str, Any]] = []
    entries_with_slots = 0
    entries_without_slots = 0
    empty_target_chests = 0

    for chest in chest_entries:
        index = int(chest["table_index"])
        room_value = int(chest["room_value"])
        source_room_value = int(chest["source_room_value"])
        object_entry = object_entries.get(room_value)
        door_entry = door_entries.get(room_value)
        in_range = object_entry is not None and door_entry is not None
        object_label = (
            str(object_entry["target_label"])
            if object_entry is not None and object_entry.get("target_label") is not None
            else None
        )
        door_label = (
            str(door_entry["target_label"])
            if door_entry is not None and door_entry.get("target_label") is not None
            else None
        )
        target_labels_match = (
            object_label == door_label
            if object_entry is not None and door_entry is not None
            else None
        )

        if in_range:
            entries_with_slots += 1
        else:
            entries_without_slots += 1
            add_finding(
                "room_value_out_of_pointer_range",
                f"Edited room value {room_value} does not resolve to a slot in both "
                f"{POINTER_ENTRY_COUNT}-entry source pointer tables (chest entry {index}).",
                chest_table_index=index,
                room_value=room_value,
                object_label=object_label,
                door_label=door_label,
            )
        if target_labels_match is False:
            add_finding(
                "object_door_pointer_target_mismatch",
                f"Edited room value {room_value} has different object- and door-pointer "
                f"target labels (chest entry {index}).",
                chest_table_index=index,
                room_value=room_value,
                object_label=object_label,
                door_label=door_label,
            )
        if object_entry is not None and object_entry.get("is_empty_target") is True:
            empty_target_chests += 1

        report_entry = {
            "table_index": index,
            "candidate_entry_offset": int(chest["candidate_entry_offset"]),
            "source_line": int(chest["source_line"]),
            "source_expression": str(chest["source_expression"]),
            "source_room_value": source_room_value,
            "room_value": room_value,
            "item_value": int(chest["item_value"]),
            "is_big_chest": bool(chest["is_big_chest"]),
            "is_modified": bool(chest["is_modified"]),
            "room_pointer_table_index": room_value if in_range else None,
            "room_value_in_pointer_tables": in_range,
            "object_pointer_entry_file_offset": (
                int(object_entry["pointer_entry_file_offset"])
                if object_entry is not None
                else None
            ),
            "object_pointer_target_label": object_label,
            "object_pointer_is_empty_target": (
                bool(object_entry["is_empty_target"]) if object_entry is not None else None
            ),
            "door_pointer_entry_file_offset": (
                int(door_entry["pointer_entry_file_offset"])
                if door_entry is not None
                else None
            ),
            "door_pointer_target_label": door_label,
            "door_pointer_target_addend": (
                int(door_entry["target_addend"])
                if door_entry is not None and door_entry.get("target_addend") is not None
                else None
            ),
            "pointer_target_labels_match": target_labels_match,
        }
        report_entries.append(report_entry)
        grouped_by_room.setdefault(room_value, []).append(report_entry)

    mismatch_rooms = sorted(
        {
            entry["room_value"]
            for entry in report_entries
            if entry["pointer_target_labels_match"] is False
        }
    )
    room_groups: list[dict[str, Any]] = []
    for room_value, group in sorted(grouped_by_room.items()):
        first = group[0]
        room_groups.append(
            {
                "room_value": room_value,
                "chest_entry_count": len(group),
                "chest_table_indexes": [entry["table_index"] for entry in group],
                "source_room_values": sorted({entry["source_room_value"] for entry in group}),
                "item_values": [entry["item_value"] for entry in group],
                "big_chest_entry_indexes": [
                    entry["table_index"] for entry in group if entry["is_big_chest"]
                ],
                "room_pointer_table_index": first["room_pointer_table_index"],
                "room_value_in_pointer_tables": first["room_value_in_pointer_tables"],
                "object_pointer_target_label": first["object_pointer_target_label"],
                "object_pointer_is_empty_target": first["object_pointer_is_empty_target"],
                "door_pointer_target_label": first["door_pointer_target_label"],
                "door_pointer_target_addend": first["door_pointer_target_addend"],
                "pointer_target_labels_match": first["pointer_target_labels_match"],
            }
        )

    error_count = len(findings)
    return {
        "format": PROJECT_DUNGEON_CHEST_ROOM_REFERENCE_AUDIT_FORMAT,
        "format_version": 1,
        "source_revision": PINNED_SOURCE_REVISION,
        "source_sha256": source_sha256,
        "entry_count": len(report_entries),
        "entries": report_entries,
        "room_groups": room_groups,
        "object_door_pointer_mismatch_room_values": mismatch_rooms,
        "findings": findings,
        "summary": {
            "chest_entry_count": len(report_entries),
            "modified_record_count": int(model["summary"]["modified_record_count"]),
            "unique_room_value_count": len(grouped_by_room),
            "room_values_with_multiple_chests": sum(
                len(group) > 1 for group in grouped_by_room.values()
            ),
            "chest_entries_with_pointer_slots": entries_with_slots,
            "chest_entries_without_pointer_slots": entries_without_slots,
            "unique_room_values_without_pointer_slots": sum(
                room_value not in object_entries or room_value not in door_entries
                for room_value in grouped_by_room
            ),
            "empty_object_pointer_target_chest_count": empty_target_chests,
            "object_door_pointer_target_mismatch_room_count": len(mismatch_rooms),
            "error_count": error_count,
            "warning_count": 0,
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
                "The report joins the current project room value, preserving the source "
                "baseline separately. The pinned source comments describe the low 15 bits "
                "as a room value; the chest consumer compares it with $A0, and room-pointer "
                "consumers index their tables with $A0*3."
            ),
        },
        "evidence": {
            "project_edits_included": True,
            "source_baselines_preserved": True,
            "source_consumer_relationship_traced": True,
            "candidate_entry_offsets_verified": False,
            "candidate_pointer_offsets_verified": False,
            "room_payload_bytes_verified": False,
            "item_value_names_resolved": False,
            "playable_room_set_resolved": False,
            "rom_bytes_read": False,
            "rom_modified": False,
        },
    }
