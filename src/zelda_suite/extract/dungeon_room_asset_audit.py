"""Cross-reference the committed dungeon room pointer and payload inventories."""
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

DUNGEON_ROOM_ASSET_AUDIT_FORMAT = "zelda-suite-dungeon-room-asset-audit"
DUNGEON_POINTER_ASSET_NAME = "dungeon-room-object-pointers"
DUNGEON_POINTER_TABLE_LABEL = "RoomData_ObjectDataPointers"
DUNGEON_ROOM_PAYLOAD_ASSETS = (
    "dungeon-room-payloads-bank03",
    "dungeon-room-payload-inventory",
    "dungeon-room-payloads-bank1f",
)
DUNGEON_ROOM_PAYLOAD_SOURCE_FILES = {
    "dungeon-room-payloads-bank03": "Bank03.asm",
    "dungeon-room-payload-inventory": "Bank0A.asm",
    "dungeon-room-payloads-bank1f": "Bank1F.asm",
}


class DungeonRoomAssetAuditError(ValueError):
    """Raised when the registered dungeon-room assets cannot be audited."""


def audit_dungeon_room_assets(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Join registered room pointer labels to payload declarations without a ROM.

    Source-commented payload offsets are preserved as candidate metadata only.
    This command does not turn those offsets into verified ROM addresses or
    claim that the referenced room payload bytes exist in the local ROM.
    """
    try:
        registered = list_extracted_assets(registry_path)
        by_name = {asset["name"]: asset for asset in registered}
        required_names = (DUNGEON_POINTER_ASSET_NAME, *DUNGEON_ROOM_PAYLOAD_ASSETS)
        for name in required_names:
            if name not in by_name:
                raise DungeonRoomAssetAuditError(
                    f"dungeon room audit asset is not registered: {name!r}"
                )

        if by_name[DUNGEON_POINTER_ASSET_NAME]["format"] != POINTER_TABLE_FORMAT:
            raise DungeonRoomAssetAuditError(
                f"{DUNGEON_POINTER_ASSET_NAME!r} must use {POINTER_TABLE_FORMAT!r}"
            )
        for name in DUNGEON_ROOM_PAYLOAD_ASSETS:
            if by_name[name]["format"] != INCBIN_INVENTORY_FORMAT:
                raise DungeonRoomAssetAuditError(
                    f"{name!r} must use {INCBIN_INVENTORY_FORMAT!r}"
                )

        pointers = load_extracted_asset(DUNGEON_POINTER_ASSET_NAME, registry_path)
        inventories = {
            name: load_extracted_asset(name, registry_path)
            for name in DUNGEON_ROOM_PAYLOAD_ASSETS
        }
    except (AssetLoadError, OSError) as exc:
        raise DungeonRoomAssetAuditError(str(exc)) from exc

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

    if pointers["table_label"] != DUNGEON_POINTER_TABLE_LABEL or pointers["entry_width"] != 3:
        add_finding(
            "pointer_table_metadata_mismatch",
            "error",
            "The registered dungeon pointer asset must be the three-byte "
            f"{DUNGEON_POINTER_TABLE_LABEL!r} table.",
        )

    pointer_revision = pointers["source_revision"]
    if pointers["source_file"] != "Bank1F.asm":
        add_finding(
            "source_provenance_mismatch",
            "error",
            "The dungeon pointer table source_file should be 'Bank1F.asm'.",
        )

    declarations: list[dict[str, Any]] = []
    for asset_name in DUNGEON_ROOM_PAYLOAD_ASSETS:
        inventory = inventories[asset_name]
        expected_file = DUNGEON_ROOM_PAYLOAD_SOURCE_FILES[asset_name]
        if inventory["source_revision"] != pointer_revision:
            add_finding(
                "source_provenance_mismatch",
                "error",
                f"Payload inventory {asset_name!r} has a different source revision "
                "from the pointer table.",
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
            declarations.append({
                **declaration,
                "payload_asset_name": asset_name,
            })

    declaration_counts = Counter(item["label"] for item in declarations)
    first_declaration_by_label: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        first_declaration_by_label.setdefault(declaration["label"], declaration)

    duplicate_labels = sorted(
        label for label, count in declaration_counts.items() if count > 1
    )
    for label in duplicate_labels:
        add_finding(
            "duplicate_payload_label",
            "error",
            f"Room payload label {label!r} is declared more than once across the registered inventories.",
            payload_label=label,
        )

    unique_declaration_by_label = {
        label: first_declaration_by_label[label]
        for label, count in declaration_counts.items()
        if count == 1
    }
    pointer_entries = pointers["entries"]
    unique_targets = {entry["target_label"] for entry in pointer_entries}
    missing_targets = sorted(unique_targets - set(unique_declaration_by_label))
    unreferenced_labels = sorted(set(declaration_counts) - unique_targets)
    missing_reference_count = 0
    cross_references: list[dict[str, Any]] = []

    for pointer in pointer_entries:
        label = pointer["target_label"]
        declaration = unique_declaration_by_label.get(label)
        declaration_count = declaration_counts.get(label, 0)
        found = declaration is not None
        if not found:
            missing_reference_count += 1

        cross_references.append({
            "table_index": pointer["table_index"],
            "pointer_entry_file_offset": pointer["pointer_entry_file_offset"],
            "pointer_expression": pointer["pointer_expression"],
            "target_label": label,
            "is_empty_target": pointer["is_empty_target"],
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
            "source_file_offset_start": (
                declaration["source_file_offset_start"] if declaration is not None else None
            ),
            "declared_size_bytes": (
                declaration["declared_size_bytes"] if declaration is not None else None
            ),
        })

    for label in missing_targets:
        matching_entries = [entry for entry in pointer_entries if entry["target_label"] == label]
        add_finding(
            "missing_payload_declaration",
            "error",
            f"Target label {label!r} is declared {declaration_counts.get(label, 0)} "
            "time(s); exactly one payload declaration is required.",
            pointer_index=matching_entries[0]["table_index"] if matching_entries else None,
            target_label=label,
            payload_label=label,
        )

    for label in unreferenced_labels:
        declaration = first_declaration_by_label[label]
        add_finding(
            "unreferenced_payload_declaration",
            "warning",
            f"Payload declaration {label!r} is not referenced by any pointer-table entry.",
            payload_label=label,
            payload_asset_name=declaration["payload_asset_name"],
            incbin_path=declaration["incbin_path"],
        )

    payloads_missing_start: list[dict[str, Any]] = []
    payloads_missing_size: list[dict[str, Any]] = []
    source_range_mismatch_count = 0
    for declaration in declarations:
        if declaration["source_file_offset_start"] is None:
            payloads_missing_start.append({
                "label": declaration["label"],
                "payload_asset_name": declaration["payload_asset_name"],
                "source_file": declaration["source_file"],
                "incbin_path": declaration["incbin_path"],
            })
            add_finding(
                "payload_start_offset_missing",
                "warning",
                "Payload declaration has no numeric source-commented start offset.",
                payload_label=declaration["label"],
                payload_asset_name=declaration["payload_asset_name"],
                incbin_path=declaration["incbin_path"],
            )
        if declaration["declared_size_bytes"] is None:
            payloads_missing_size.append({
                "label": declaration["label"],
                "payload_asset_name": declaration["payload_asset_name"],
                "source_file": declaration["source_file"],
                "incbin_path": declaration["incbin_path"],
            })
            add_finding(
                "payload_size_missing",
                "warning",
                "Payload declaration has no declared byte size.",
                payload_label=declaration["label"],
                payload_asset_name=declaration["payload_asset_name"],
                incbin_path=declaration["incbin_path"],
            )
        if declaration["source_range_size_matches"] is False:
            source_range_mismatch_count += 1
            add_finding(
                "payload_source_range_mismatch",
                "warning",
                "Payload source range does not match its declared size.",
                payload_label=declaration["label"],
                payload_asset_name=declaration["payload_asset_name"],
                incbin_path=declaration["incbin_path"],
            )

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    unique_payload_labels = set(declaration_counts)
    empty_entries = [entry for entry in pointer_entries if entry["is_empty_target"]]
    return {
        "format": DUNGEON_ROOM_ASSET_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "pointer_asset_name": DUNGEON_POINTER_ASSET_NAME,
        "payload_asset_names": list(DUNGEON_ROOM_PAYLOAD_ASSETS),
        "pointer_source_file": pointers["source_file"],
        "pointer_table_label": pointers["table_label"],
        "pointer_table_file_offset": pointers["table_file_offset"],
        "pointer_entry_width_bytes": pointers["entry_width"],
        "payload_source_files": sorted({
            inventories[name]["source_file"] for name in DUNGEON_ROOM_PAYLOAD_ASSETS
        }),
        "source_revision": pointer_revision,
        "cross_references": cross_references,
        "missing_payload_targets": missing_targets,
        "unreferenced_payload_labels": unreferenced_labels,
        "payloads_missing_start_offset": payloads_missing_start,
        "payloads_missing_size": payloads_missing_size,
        "findings": findings,
        "summary": {
            "pointer_entry_count": len(pointer_entries),
            "empty_pointer_count": len(empty_entries),
            "unique_pointer_target_label_count": len(unique_targets),
            "payload_declaration_count": len(declarations),
            "unique_payload_label_count": len(unique_payload_labels),
            "matched_target_label_count": len(unique_targets & set(unique_declaration_by_label)),
            "missing_payload_target_count": len(missing_targets),
            "missing_payload_reference_count": missing_reference_count,
            "unreferenced_payload_count": len(unreferenced_labels),
            "duplicate_payload_label_count": len(duplicate_labels),
            "payload_start_offset_missing_count": len(payloads_missing_start),
            "payload_without_size_count": len(payloads_missing_size),
            "payload_source_range_mismatch_count": source_range_mismatch_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "room_payload_bytes_read": False,
            "pointer_values_resolved": False,
            "offsets_verified": False,
            "payload_bytes_verified": False,
        },
    }
