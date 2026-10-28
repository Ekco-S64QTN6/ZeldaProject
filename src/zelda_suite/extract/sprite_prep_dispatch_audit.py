"""Cross-reference sprite preparation IDs with SpriteActive3 IDs by slot only."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    SPRITE_DISPATCH_FORMAT,
    SPRITE_PREP_DISPATCH_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

SPRITE_PREP_DISPATCH_AUDIT_FORMAT = "zelda-suite-sprite-prep-dispatch-audit"
SPRITE_PREP_DISPATCH_ASSET_NAME = "sprite-prep-dispatch"
SPRITE_ACTIVE3_ASSET_NAME = "sprite-active3-dispatch"


class SpritePrepDispatchAuditError(ValueError):
    """Raised when registered sprite dispatch sources cannot be cross-referenced."""


def audit_sprite_prep_dispatch(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    prep_asset_name: str = SPRITE_PREP_DISPATCH_ASSET_NAME,
    active3_asset_name: str = SPRITE_ACTIVE3_ASSET_NAME,
) -> dict[str, Any]:
    """Join the two sprite dispatch inventories by their source-commented IDs.

    A matching ID establishes only shared index-domain coverage. The two
    handler tables describe different stages; the report does not assert that
    handler labels or source-address comments have equivalent semantics.
    """
    try:
        registry = list_extracted_assets(registry_path)
        by_name = {record["name"]: record for record in registry}
        prep_record = by_name.get(prep_asset_name)
        active_record = by_name.get(active3_asset_name)
        if prep_record is None:
            raise SpritePrepDispatchAuditError(
                f"sprite prep dispatch asset is not registered: {prep_asset_name!r}"
            )
        if active_record is None:
            raise SpritePrepDispatchAuditError(
                f"active3 sprite dispatch asset is not registered: {active3_asset_name!r}"
            )
        if prep_record["format"] != SPRITE_PREP_DISPATCH_FORMAT:
            raise SpritePrepDispatchAuditError(
                f"asset {prep_asset_name!r} must use {SPRITE_PREP_DISPATCH_FORMAT!r}"
            )
        if active_record["format"] != SPRITE_DISPATCH_FORMAT:
            raise SpritePrepDispatchAuditError(
                f"asset {active3_asset_name!r} must use {SPRITE_DISPATCH_FORMAT!r}"
            )
        prep = load_extracted_asset(prep_asset_name, registry_path)
        active = load_extracted_asset(active3_asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise SpritePrepDispatchAuditError(str(exc)) from exc

    if prep["source_revision"] != active["source_revision"]:
        raise SpritePrepDispatchAuditError(
            "sprite prep and SpriteActive3 exports do not share a source revision"
        )

    prep_by_id = {entry["sprite_type_id"]: entry for entry in prep["entries"]}
    active_by_id = {entry["sprite_type_id"]: entry for entry in active["entries"]}
    if len(prep_by_id) != len(prep["entries"]):
        raise SpritePrepDispatchAuditError("sprite prep export contains duplicate sprite IDs")
    if len(active_by_id) != len(active["entries"]):
        raise SpritePrepDispatchAuditError("SpriteActive3 export contains duplicate sprite IDs")

    shared_ids = sorted(prep_by_id.keys() & active_by_id.keys())
    prep_only_ids = sorted(prep_by_id.keys() - active_by_id.keys())
    active3_only_ids = sorted(active_by_id.keys() - prep_by_id.keys())

    rows: list[dict[str, Any]] = []
    for sprite_id in shared_ids:
        prep_entry = prep_by_id[sprite_id]
        active_entry = active_by_id[sprite_id]
        rows.append({
            "sprite_type_id": sprite_id,
            "sprite_id_hex": "0x" + format(sprite_id, "02X"),
            "prep": {
                "handler_expression": prep_entry["handler_expression"],
                "handler_label": prep_entry["handler_label"],
                "source_handler_address_annotation": prep_entry["source_handler_address_annotation"],
                "source_description": prep_entry["source_description"],
                "source_comment_continuations": prep_entry["source_comment_continuations"],
                "source_line": prep_entry["source_line"],
            },
            "active3": {
                "handler_expression": active_entry["handler_expression"],
                "handler_label": active_entry["handler_label"],
                "source_handler_address_annotation": active_entry["source_handler_address_annotation"],
                "source_description": active_entry["source_description"],
                "source_line": active_entry["source_line"],
            },
        })

    return {
        "format": SPRITE_PREP_DISPATCH_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "prep_asset_name": prep_asset_name,
        "active3_asset_name": active3_asset_name,
        "source_revision": prep["source_revision"],
        "prep_routine_label": prep["routine_label"],
        "prep_routine_source_range_annotation": prep["routine_source_range_annotation"],
        "prep_table_file_offset": None,
        "active3_table_file_offset": active["table_file_offset"],
        "rows": rows,
        "prep_only_sprite_ids": prep_only_ids,
        "active3_only_sprite_ids": active3_only_ids,
        "summary": {
            "prep_entry_count": len(prep["entries"]),
            "active3_entry_count": len(active["entries"]),
            "shared_sprite_id_count": len(shared_ids),
            "prep_only_sprite_id_count": len(prep_only_ids),
            "active3_only_sprite_id_count": len(active3_only_ids),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "table_offsets_verified": False,
            "handler_address_annotations_verified": False,
            "same_runtime_handler_semantics_asserted": False,
        },
    }
