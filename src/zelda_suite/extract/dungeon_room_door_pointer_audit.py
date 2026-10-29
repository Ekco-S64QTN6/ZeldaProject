"""Audit dungeon door-pointer addends against source-annotated room payload sizes."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    INCBIN_INVENTORY_FORMAT,
    POINTER_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

DUNGEON_ROOM_DOOR_POINTER_AUDIT_FORMAT = "zelda-suite-dungeon-room-door-pointer-audit"
DOOR_POINTER_ASSET_NAME = "dungeon-room-door-pointers"
OBJECT_POINTER_ASSET_NAME = "dungeon-room-object-pointers"
ROOM_PAYLOAD_ASSETS = (
    "dungeon-room-payloads-bank03",
    "dungeon-room-payload-inventory",
    "dungeon-room-payloads-bank1f",
)
ROOM_PAYLOAD_SOURCE_FILES = {
    "dungeon-room-payloads-bank03": "Bank03.asm",
    "dungeon-room-payload-inventory": "Bank0A.asm",
    "dungeon-room-payloads-bank1f": "Bank1F.asm",
}
EXPECTED_DOOR_TABLE_OFFSET = 0x0F83C0
EXPECTED_OBJECT_TABLE_OFFSET = 0x0F8000
EXPECTED_ENTRY_WIDTH = 3
EXPECTED_ENTRY_COUNT = 320


class DungeonRoomDoorPointerAuditError(ValueError):
    """Raised when the registered dungeon door-pointer assets cannot be audited."""


def audit_dungeon_room_door_pointer_bounds(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Audit door-pointer addends against source-declared sizes without reading bytes.

    This verifies arithmetic against registered source metadata only. It does not
    establish that source-commented sizes/offsets are correct in a ROM, decode
    door records, or infer the set of playable rooms.
    """
    try:
        registered = list_extracted_assets(registry_path)
        by_name = {asset["name"]: asset for asset in registered}
        required_names = (
            DOOR_POINTER_ASSET_NAME,
            OBJECT_POINTER_ASSET_NAME,
            *ROOM_PAYLOAD_ASSETS,
        )
        for name in required_names:
            if name not in by_name:
                raise DungeonRoomDoorPointerAuditError(
                    f"dungeon door-pointer audit asset is not registered: {name!r}"
                )

        for name in (DOOR_POINTER_ASSET_NAME, OBJECT_POINTER_ASSET_NAME):
            if by_name[name]["format"] != POINTER_TABLE_FORMAT:
                raise DungeonRoomDoorPointerAuditError(
                    f"{name!r} must use {POINTER_TABLE_FORMAT!r}"
                )
        for name in ROOM_PAYLOAD_ASSETS:
            if by_name[name]["format"] != INCBIN_INVENTORY_FORMAT:
                raise DungeonRoomDoorPointerAuditError(
                    f"{name!r} must use {INCBIN_INVENTORY_FORMAT!r}"
                )

        door = load_extracted_asset(DOOR_POINTER_ASSET_NAME, registry_path)
        objects = load_extracted_asset(OBJECT_POINTER_ASSET_NAME, registry_path)
        inventories = {
            name: load_extracted_asset(name, registry_path)
            for name in ROOM_PAYLOAD_ASSETS
        }
    except (AssetLoadError, OSError) as exc:
        raise DungeonRoomDoorPointerAuditError(str(exc)) from exc

    findings: list[dict[str, Any]] = []

    def add_finding(
        code: str,
        severity: str,
        message: str,
        *,
        pointer_index: int | None = None,
        target_label: str | None = None,
        payload_label: str | None = None,
        payload_asset_name: str | None = None,
        incbin_path: str | None = None,
    ) -> None:
        findings.append({
            "code": code,
            "severity": severity,
            "message": message,
            "pointer_index": pointer_index,
            "target_label": target_label,
            "payload_label": payload_label,
            "payload_asset_name": payload_asset_name,
            "incbin_path": incbin_path,
        })

    if (
        door["source_file"] != "Bank1F.asm"
        or door["table_label"] != "RoomData_DoorDataPointers"
        or door["table_file_offset"] != EXPECTED_DOOR_TABLE_OFFSET
        or door["entry_width"] != EXPECTED_ENTRY_WIDTH
        or door["entry_count"] != EXPECTED_ENTRY_COUNT
    ):
        add_finding(
            "pointer_table_metadata_mismatch",
            "error",
            "The door-pointer asset must describe the 320-entry, three-byte "
            "RoomData_DoorDataPointers table at source-commented offset $0F83C0.",
        )

    if (
        objects["source_file"] != "Bank1F.asm"
        or objects["table_label"] != "RoomData_ObjectDataPointers"
        or objects["table_file_offset"] != EXPECTED_OBJECT_TABLE_OFFSET
        or objects["entry_width"] != EXPECTED_ENTRY_WIDTH
        or objects["entry_count"] != EXPECTED_ENTRY_COUNT
    ):
        add_finding(
            "object_pointer_table_metadata_mismatch",
            "error",
            "The object-pointer asset must describe the 320-entry, three-byte "
            "RoomData_ObjectDataPointers table at source-commented offset $0F8000.",
        )

    source_revision = door["source_revision"]
    if objects["source_revision"] != source_revision:
        add_finding(
            "source_provenance_mismatch",
            "error",
            "The door-pointer and object-pointer tables use different source revisions.",
        )

    declarations: list[dict[str, Any]] = []
    for asset_name in ROOM_PAYLOAD_ASSETS:
        inventory = inventories[asset_name]
        expected_file = ROOM_PAYLOAD_SOURCE_FILES[asset_name]
        if inventory["source_revision"] != source_revision:
            add_finding(
                "source_provenance_mismatch",
                "error",
                f"Payload inventory {asset_name!r} has a different source revision "
                "from the door-pointer table.",
                payload_asset_name=asset_name,
            )
        if inventory["source_file"] != expected_file:
            add_finding(
                "source_provenance_mismatch",
                "error",
                f"Payload inventory {asset_name!r} source_file should be {expected_file!r}.",
                payload_asset_name=asset_name,
            )
        for declaration in inventory["declarations"]:
            declarations.append({**declaration, "payload_asset_name": asset_name})

    declaration_counts = Counter(item["label"] for item in declarations)
    first_declaration_by_label: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        first_declaration_by_label.setdefault(declaration["label"], declaration)

    duplicate_labels = sorted(
        label for label, count in declaration_counts.items() if count > 1
    )
    for label in duplicate_labels:
        declaration = first_declaration_by_label[label]
        add_finding(
            "duplicate_payload_label",
            "error",
            f"Room payload label {label!r} is declared more than once across inventories.",
            payload_label=label,
            payload_asset_name=declaration["payload_asset_name"],
            incbin_path=declaration["incbin_path"],
        )

    unique_declaration_by_label = {
        label: first_declaration_by_label[label]
        for label, count in declaration_counts.items()
        if count == 1
    }
    door_entries = door["entries"]
    object_entries_by_index = {
        entry["table_index"]: entry for entry in objects["entries"]
    }
    unique_targets = {entry["target_label"] for entry in door_entries}
    missing_targets = sorted(unique_targets - set(unique_declaration_by_label))
    unreferenced_labels = sorted(set(declaration_counts) - unique_targets)

    for label in missing_targets:
        matching = [entry for entry in door_entries if entry["target_label"] == label]
        add_finding(
            "missing_payload_declaration",
            "error",
            f"Door-pointer target {label!r} does not have exactly one payload declaration.",
            pointer_index=matching[0]["table_index"] if matching else None,
            target_label=label,
            payload_label=label,
        )

    for label in unreferenced_labels:
        declaration = first_declaration_by_label[label]
        add_finding(
            "unreferenced_payload_declaration",
            "warning",
            f"Payload declaration {label!r} is not targeted by the door-pointer table.",
            payload_label=label,
            payload_asset_name=declaration["payload_asset_name"],
            incbin_path=declaration["incbin_path"],
        )

    payloads_missing_size: list[dict[str, Any]] = []
    for declaration in declarations:
        size = declaration["declared_size_bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            payloads_missing_size.append({
                "label": declaration["label"],
                "payload_asset_name": declaration["payload_asset_name"],
                "source_file": declaration["source_file"],
                "incbin_path": declaration["incbin_path"],
                "declared_size_bytes": size,
            })
            add_finding(
                "payload_size_missing",
                "warning",
                "Payload declaration has no positive integer source-declared byte size.",
                payload_label=declaration["label"],
                payload_asset_name=declaration["payload_asset_name"],
                incbin_path=declaration["incbin_path"],
            )

    cross_references: list[dict[str, Any]] = []
    out_of_bounds_addend_count = 0
    unknown_addend_bounds_count = 0
    in_bounds_addend_count = 0
    slot_target_mismatch_count = 0
    pointer_entry_offset_mismatch_count = 0
    missing_payload_reference_count = 0

    for entry in door_entries:
        index = entry["table_index"]
        expected_entry_offset = EXPECTED_DOOR_TABLE_OFFSET + index * EXPECTED_ENTRY_WIDTH
        if entry["pointer_entry_file_offset"] != expected_entry_offset:
            pointer_entry_offset_mismatch_count += 1
            add_finding(
                "pointer_entry_offset_mismatch",
                "error",
                "Door-pointer slot offset does not follow the three-byte source-table stride.",
                pointer_index=index,
                target_label=entry["target_label"],
            )

        object_entry = object_entries_by_index.get(index)
        object_target = object_entry["target_label"] if object_entry is not None else None
        slot_matches = object_target == entry["target_label"]
        if not slot_matches:
            slot_target_mismatch_count += 1
            add_finding(
                "target_label_slot_mismatch",
                "error",
                "Door-pointer target label differs from the object-pointer target at the same slot.",
                pointer_index=index,
                target_label=entry["target_label"],
            )

        label = entry["target_label"]
        declaration = unique_declaration_by_label.get(label)
        declaration_count = declaration_counts.get(label, 0)
        found = declaration is not None
        if not found:
            missing_payload_reference_count += 1

        addend = entry["target_addend"]
        size = declaration["declared_size_bytes"] if declaration is not None else None
        if (
            declaration is not None
            and isinstance(size, int)
            and not isinstance(size, bool)
            and size > 0
            and isinstance(addend, int)
            and not isinstance(addend, bool)
        ):
            within_bounds: bool | None = 0 <= addend < size
            if within_bounds:
                in_bounds_addend_count += 1
            else:
                out_of_bounds_addend_count += 1
                add_finding(
                    "target_addend_out_of_bounds",
                    "error",
                    f"Door-pointer addend {addend} is outside the source-declared "
                    f"payload size {size} for {label!r}.",
                    pointer_index=index,
                    target_label=label,
                    payload_label=label,
                    payload_asset_name=declaration["payload_asset_name"],
                    incbin_path=declaration["incbin_path"],
                )
        else:
            within_bounds = None
            unknown_addend_bounds_count += 1
            if not isinstance(addend, int) or isinstance(addend, bool):
                add_finding(
                    "invalid_target_addend",
                    "error",
                    "Door-pointer entry does not have a numeric integer addend.",
                    pointer_index=index,
                    target_label=label,
                )

        cross_references.append({
            "table_index": index,
            "pointer_entry_file_offset": entry["pointer_entry_file_offset"],
            "pointer_expression": entry["pointer_expression"],
            "target_label": label,
            "target_addend": addend,
            "is_empty_target": entry["is_empty_target"],
            "object_pointer_target_label": object_target,
            "target_matches_object_pointer_slot": slot_matches,
            "payload_declaration_count": declaration_count,
            "payload_declaration_found": found,
            "payload_asset_name": (
                declaration["payload_asset_name"] if declaration is not None else None
            ),
            "payload_source_file": (
                declaration["source_file"] if declaration is not None else None
            ),
            "incbin_path": (
                declaration["incbin_path"] if declaration is not None else None
            ),
            "declared_size_bytes": size,
            "addend_within_declared_size": within_bounds,
        })

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    return {
        "format": DUNGEON_ROOM_DOOR_POINTER_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "door_pointer_asset_name": DOOR_POINTER_ASSET_NAME,
        "object_pointer_asset_name": OBJECT_POINTER_ASSET_NAME,
        "payload_asset_names": list(ROOM_PAYLOAD_ASSETS),
        "source_revision": source_revision,
        "door_pointer_table_label": door["table_label"],
        "door_pointer_table_file_offset": door["table_file_offset"],
        "pointer_entry_width_bytes": door["entry_width"],
        "object_pointer_table_label": objects["table_label"],
        "object_pointer_table_file_offset": objects["table_file_offset"],
        "cross_references": cross_references,
        "missing_payload_targets": missing_targets,
        "unreferenced_payload_labels": unreferenced_labels,
        "payloads_missing_size": payloads_missing_size,
        "findings": findings,
        "summary": {
            "pointer_entry_count": len(door_entries),
            "empty_pointer_count": sum(entry["is_empty_target"] for entry in door_entries),
            "unique_pointer_target_label_count": len(unique_targets),
            "payload_declaration_count": len(declarations),
            "unique_payload_label_count": len(declaration_counts),
            "matched_target_label_count": len(unique_targets & set(unique_declaration_by_label)),
            "missing_payload_target_count": len(missing_targets),
            "missing_payload_reference_count": missing_payload_reference_count,
            "unreferenced_payload_count": len(unreferenced_labels),
            "duplicate_payload_label_count": len(duplicate_labels),
            "payload_without_size_count": len(payloads_missing_size),
            "addend_in_bounds_count": in_bounds_addend_count,
            "addend_out_of_bounds_count": out_of_bounds_addend_count,
            "addend_bounds_unknown_count": unknown_addend_bounds_count,
            "slot_target_mismatch_count": slot_target_mismatch_count,
            "pointer_entry_offset_mismatch_count": pointer_entry_offset_mismatch_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "room_payload_bytes_read": False,
            "addends_checked_against_source_declared_sizes": True,
            "door_data_semantics_decoded": False,
            "offsets_verified": False,
            "payload_bytes_verified": False,
            "playable_room_set_resolved": False,
        },
    }
