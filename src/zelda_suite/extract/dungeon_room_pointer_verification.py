"""Read-only verification of dungeon-room long pointers against local ROM bytes.

Source-comment offsets are kept as annotations; candidate offsets follow each
registered inventory from its first commented start plus declared payload sizes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    AssetLoadError,
    load_extracted_asset,
)
from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    lorom_cpu_address,
    read_rom_bytes,
    sha256_rom_bytes,
)

PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
DUNGEON_POINTER_ASSET = "dungeon-room-object-pointers"
DUNGEON_POINTER_TABLE_LABEL = "RoomData_ObjectDataPointers"
DUNGEON_POINTER_TABLE_OFFSET = 0x0F8000
DUNGEON_POINTER_ENTRY_WIDTH = 3
DUNGEON_POINTER_ENTRY_COUNT = 320
DUNGEON_ROOM_PAYLOAD_ASSETS = (
    "dungeon-room-payloads-bank03",
    "dungeon-room-payload-inventory",
    "dungeon-room-payloads-bank1f",
)
DUNGEON_ROOM_PAYLOAD_FILES = {
    "dungeon-room-payloads-bank03": "Bank03.asm",
    "dungeon-room-payload-inventory": "Bank0A.asm",
    "dungeon-room-payloads-bank1f": "Bank1F.asm",
}


class DungeonRoomPointerVerificationError(ValueError):
    """Raised when registered dungeon source metadata cannot support a safe comparison."""


def verify_dungeon_room_pointers(
    rom_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Compare 320 registered pointers with source-order payload-layout candidates.

    Each inventory starts at its first source-commented offset; later candidate
    offsets advance by declared payload sizes in source order. Conflicting or
    missing comments are reported separately, never rewritten. A successful
    byte check is evidence for this local file only and does not establish ROM
    provenance or prove the source declarations describe canonical payloads.
    """
    image_path = Path(rom_path)
    if not image_path.is_file():
        raise DungeonRoomPointerVerificationError(
            f"ROM path is not a file: {image_path}"
        )
    try:
        rom = read_rom_bytes(image_path)
    except ROMImageInspectionError as exc:
        raise DungeonRoomPointerVerificationError(str(exc)) from exc
    if len(rom) != EXPECTED_US_ROM_SIZE:
        raise DungeonRoomPointerVerificationError(
            "ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(rom):,}. "
            "Use inspect-rom to diagnose the file; do not adjust it automatically."
        )

    try:
        pointers = load_extracted_asset(DUNGEON_POINTER_ASSET, registry_path)
        inventories = {
            name: load_extracted_asset(name, registry_path)
            for name in DUNGEON_ROOM_PAYLOAD_ASSETS
        }
    except AssetLoadError as exc:
        raise DungeonRoomPointerVerificationError(str(exc)) from exc

    if pointers["table_label"] != DUNGEON_POINTER_TABLE_LABEL:
        raise DungeonRoomPointerVerificationError(
            f"{DUNGEON_POINTER_ASSET!r} must contain "
            f"{DUNGEON_POINTER_TABLE_LABEL!r}"
        )
    if pointers["table_file_offset"] != DUNGEON_POINTER_TABLE_OFFSET:
        raise DungeonRoomPointerVerificationError(
            f"room pointer-table offset must be 0x{DUNGEON_POINTER_TABLE_OFFSET:06X}"
        )
    if pointers["entry_width"] != DUNGEON_POINTER_ENTRY_WIDTH:
        raise DungeonRoomPointerVerificationError(
            f"room pointer-table entries must be {DUNGEON_POINTER_ENTRY_WIDTH} bytes"
        )
    if pointers["entry_count"] != DUNGEON_POINTER_ENTRY_COUNT:
        raise DungeonRoomPointerVerificationError(
            f"expected {DUNGEON_POINTER_ENTRY_COUNT} room pointer entries, "
            f"got {pointers['entry_count']}"
        )

    source_revision = pointers["source_revision"]
    if source_revision != PINNED_SOURCE_REVISION:
        raise DungeonRoomPointerVerificationError(
            f"room pointer asset source revision must be {PINNED_SOURCE_REVISION}"
        )

    targets: dict[str, dict[str, Any]] = {}
    source_offset_findings: list[dict[str, Any]] = []
    for asset_name, payload in inventories.items():
        expected_source_file = DUNGEON_ROOM_PAYLOAD_FILES[asset_name]
        if payload["source_file"] != expected_source_file:
            raise DungeonRoomPointerVerificationError(
                f"{asset_name!r} source_file must be {expected_source_file!r}"
            )
        if payload["source_revision"] != source_revision:
            raise DungeonRoomPointerVerificationError(
                f"{asset_name!r} source revision does not match the pointer table"
            )

        declarations = payload["declarations"]
        if not declarations:
            raise DungeonRoomPointerVerificationError(
                f"{asset_name!r} has no room payload declarations"
            )
        layout_offset = declarations[0]["source_file_offset_start"]
        if type(layout_offset) is not int or layout_offset < 0:
            raise DungeonRoomPointerVerificationError(
                f"{asset_name!r} first declaration has no numeric source-commented "
                "start offset to anchor its sequential layout"
            )

        for declaration in declarations:
            label = declaration["label"]
            if label in targets:
                raise DungeonRoomPointerVerificationError(
                    f"duplicate room target label in registered payloads: {label}"
                )
            comment_offset = declaration["source_file_offset_start"]
            size = declaration["declared_size_bytes"]
            if type(size) is not int or size < 1:
                raise DungeonRoomPointerVerificationError(
                    f"{label!r} has no positive declared payload size"
                )
            if type(comment_offset) is not int or comment_offset < 0:
                source_offset_findings.append({
                    "code": "source_comment_offset_missing",
                    "severity": "warning",
                    "source_file": payload["source_file"],
                    "source_asset": asset_name,
                    "source_line": declaration["source_line"],
                    "label": label,
                    "incbin_path": declaration["incbin_path"],
                    "source_comment_file_offset": None,
                    "computed_layout_file_offset_start": layout_offset,
                    "declared_size_bytes": size,
                    "offset_delta_bytes": None,
                })
            elif comment_offset != layout_offset:
                source_offset_findings.append({
                    "code": "source_comment_offset_disagrees_with_sequential_layout",
                    "severity": "warning",
                    "source_file": payload["source_file"],
                    "source_asset": asset_name,
                    "source_line": declaration["source_line"],
                    "label": label,
                    "incbin_path": declaration["incbin_path"],
                    "source_comment_file_offset": comment_offset,
                    "computed_layout_file_offset_start": layout_offset,
                    "declared_size_bytes": size,
                    "offset_delta_bytes": comment_offset - layout_offset,
                })

            targets[label] = {
                "label": label,
                "source_file": payload["source_file"],
                "source_asset": asset_name,
                "source_comment_file_offset": (
                    comment_offset if type(comment_offset) is int else None
                ),
                "computed_layout_file_offset_start": layout_offset,
                "declared_size_bytes": size,
            }
            layout_offset += size

    if len(targets) != 266:
        raise DungeonRoomPointerVerificationError(
            f"expected 266 distinct source room payload labels, got {len(targets)}"
        )

    target_labels = {entry["target_label"] for entry in pointers["entries"]}
    missing_labels = sorted(target_labels - targets.keys())
    if missing_labels:
        raise DungeonRoomPointerVerificationError(
            "room pointer targets lack registered payload metadata: "
            + ", ".join(missing_labels)
        )

    for target in targets.values():
        target["pointer_indices"] = []

    entries_report: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for pointer in pointers["entries"]:
        label = pointer["target_label"]
        target = targets[label]
        target_offset = target["computed_layout_file_offset_start"]
        if pointer["target_addend"] is not None:
            target_offset += pointer["target_addend"]
        try:
            cpu_address = lorom_cpu_address(target_offset)
        except (TypeError, ValueError) as exc:
            raise DungeonRoomPointerVerificationError(
                f"target {label!r} offset 0x{target_offset:X} is outside the ROM image: {exc}"
            ) from exc

        if target_offset + target["declared_size_bytes"] > len(rom):
            raise DungeonRoomPointerVerificationError(
                f"declared payload for {label!r} extends beyond the ROM image"
            )

        offset = pointer["pointer_entry_file_offset"]
        expected = cpu_address.to_bytes(DUNGEON_POINTER_ENTRY_WIDTH, "little")
        actual = rom[offset:offset + DUNGEON_POINTER_ENTRY_WIDTH]
        if len(actual) != DUNGEON_POINTER_ENTRY_WIDTH:
            raise DungeonRoomPointerVerificationError(
                f"pointer entry {pointer['table_index']} is outside the ROM image"
            )

        target["pointer_indices"].append(pointer["table_index"])
        record = {
            "table_index": pointer["table_index"],
            "pointer_entry_file_offset": offset,
            "pointer_expression": pointer["pointer_expression"],
            "target_label": label,
            "is_empty_target": pointer["is_empty_target"],
            "target_source_file": target["source_file"],
            "target_source_asset": target["source_asset"],
            "target_source_file_offset": target_offset,
            "target_source_comment_offset": target["source_comment_file_offset"],
            "target_declared_size_bytes": target["declared_size_bytes"],
            "expected_cpu_address": "$" + format(cpu_address, "06X"),
            "expected_hex": expected.hex().upper(),
            "actual_hex": actual.hex().upper(),
            "status": "pass" if actual == expected else "fail",
        }
        entries_report.append(record)
        if actual != expected:
            mismatches.append({
                "table_index": pointer["table_index"],
                "pointer_entry_file_offset": offset,
                "pointer_expression": pointer["pointer_expression"],
                "target_label": label,
                "target_source_file_offset": target_offset,
                "target_source_comment_offset": target["source_comment_file_offset"],
                "expected_cpu_address": "$" + format(cpu_address, "06X"),
                "expected_hex": expected.hex().upper(),
                "actual_hex": actual.hex().upper(),
                "reason": "ROM pointer bytes do not match the sequential payload-layout candidate",
            })

    target_reports = [
        targets[label]
        for label in sorted(targets)
    ]
    return {
        "format": "zelda-suite-dungeon-room-pointer-verification",
        "format_version": 2,
        "rom": {
            "filename": image_path.name,
            "size_bytes": len(rom),
            "sha256": sha256_rom_bytes(rom),
            "header_assessment": "headerless-by-expected-size",
            "provenance_verified": False,
        },
        "source_revision": source_revision,
        "pointer_table": {
            "label": DUNGEON_POINTER_TABLE_LABEL,
            "file_offset": DUNGEON_POINTER_TABLE_OFFSET,
            "entry_width_bytes": DUNGEON_POINTER_ENTRY_WIDTH,
            "entry_count": DUNGEON_POINTER_ENTRY_COUNT,
            "unique_target_label_count": len(target_labels),
            "empty_target_entry_count": sum(
                entry["is_empty_target"] for entry in pointers["entries"]
            ),
            "source_payload_label_count": len(targets),
            "checked_comparisons": len(entries_report),
            "mismatch_count": len(mismatches),
            "source_comment_offset_mismatch_count": len(source_offset_findings),
        },
        "entries": entries_report,
        "targets": target_reports,
        "mismatches": mismatches,
        "source_offset_findings": source_offset_findings,
        "source_layout_method": "first source-commented offset per inventory plus sequential declared payload sizes",
        "rom_modified": False,
        "source_comment_offsets_rewritten": False,
        "payload_bytes_verified": False,
        "playable_room_set_resolved": False,
    }
