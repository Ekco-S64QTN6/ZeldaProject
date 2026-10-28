"""Join aligned raw receive-item tables without inferring canonical item IDs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    ITEM_RECEIPT_LAYOUT_FORMAT,
    AssetLoadError,
    load_extracted_asset,
    validate_source_export,
)

PINNED_ITEM_SOURCE_FILE = "ancilla_init.asm"
ITEM_RECEIPT_PARENT_LABEL = "Pool_AddReceiveItem"
ITEM_RECEIPT_TABLE_COUNT = 76
ITEM_RECEIPT_MASK_COUNT = 14

# field key, registered source asset, source label, source file offset, directive,
# and element width. These offsets identify source annotations from the pinned
# disassembly; a local ROM verification is a separate check.
ITEM_RECEIPT_ARRAYS = (
    ("y_offset", "item-receipt-y-offsets", ".y_offsets", 0x04836C, "db", 1),
    ("x_offset", "item-receipt-x-offsets", ".x_offsets", 0x0483B8, "db", 1),
    ("wide_item_flag", "item-receipt-wide-flags", ".wide_item_flag", 0x048450, "db", 1),
    ("properties", "item-receipt-properties", ".properties", 0x04849C, "db", 1),
    ("target_address", "item-receipt-target-addresses", ".item_target_addr", 0x0484E8, "dw", 2),
    ("item_value", "item-receipt-values", ".item_values", 0x048580, "db", 1),
)
MASK_ARRAY = ("item-receipt-dungeon-masks", ".item_masks", 0x0485CC, "dw", 2)


class ItemReceiptLayoutError(ValueError):
    """Raised when aligned receive-item source tables cannot be safely joined."""


def _cell(entry: dict[str, Any]) -> dict[str, Any]:
    """Keep raw expression and source location; never infer value semantics."""
    return {
        "source_label": entry["source_label"],
        "entry_file_offset": entry["entry_file_offset"],
        "expression": entry["expression"],
        "literal_value": entry["literal_value"],
    }


def build_item_receipt_layout(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Join six 76-entry source arrays and preserve the separate 14-word mask table.

    The joined rows use zero-based source table positions, not canonical item
    IDs. Negative expressions stay verbatim with null literal values, and the
    array called target_address contains WRAM destinations rather than ROM
    pointers. The source's .item_graphics_indices array is intentionally not
    included because its comment-index discrepancy remains unresolved.
    """
    tables: dict[str, dict[str, Any]] = {}
    revision: str | None = None

    specs = ITEM_RECEIPT_ARRAYS + (
        ("dungeon_masks", MASK_ARRAY[0], MASK_ARRAY[1], MASK_ARRAY[2], MASK_ARRAY[3], MASK_ARRAY[4]),
    )
    for key, asset_name, expected_label, expected_offset, expected_directive, expected_width in specs:
        try:
            payload = load_extracted_asset(asset_name, registry_path)
        except AssetLoadError as exc:
            raise ItemReceiptLayoutError(
                f"could not load registered source table {asset_name!r}: {exc}"
            ) from exc

        if payload["source_file"] != PINNED_ITEM_SOURCE_FILE:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} source_file must be {PINNED_ITEM_SOURCE_FILE!r}"
            )
        if payload["parent_label"] != ITEM_RECEIPT_PARENT_LABEL:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} parent_label must be {ITEM_RECEIPT_PARENT_LABEL!r}"
            )
        if payload["table_label"] != expected_label:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} table_label is {payload['table_label']!r}; "
                f"expected {expected_label!r}"
            )
        if payload["table_file_offset"] != expected_offset:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} table offset is 0x{payload['table_file_offset']:06X}; "
                f"expected 0x{expected_offset:06X}"
            )
        if payload["directive"] != expected_directive or payload["entry_width"] != expected_width:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} must use {expected_directive} with "
                f"{expected_width}-byte entries"
            )

        expected_count = ITEM_RECEIPT_MASK_COUNT if key == "dungeon_masks" else ITEM_RECEIPT_TABLE_COUNT
        if payload["entry_count"] != expected_count:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} must contain {expected_count} entries"
            )
        payload_revision = payload["source_revision"]
        if revision is None:
            revision = payload_revision
        elif payload_revision != revision:
            raise ItemReceiptLayoutError(
                f"{asset_name!r} source revision does not match the other joined tables"
            )
        tables[key] = payload

    assert revision is not None
    rows = []
    for index in range(ITEM_RECEIPT_TABLE_COUNT):
        row: dict[str, Any] = {"table_index": index}
        for field, *_ in ITEM_RECEIPT_ARRAYS:
            entry = tables[field]["entries"][index]
            if entry["table_index"] != index:
                raise ItemReceiptLayoutError(
                    f"{field} table index mismatch at expected position {index}"
                )
            row[field] = _cell(entry)
        rows.append(row)

    masks = []
    for index, entry in enumerate(tables["dungeon_masks"]["entries"]):
        if entry["table_index"] != index:
            raise ItemReceiptLayoutError(
                f"dungeon mask table index mismatch at expected position {index}"
            )
        masks.append({
            "table_index": index,
            **_cell(entry),
        })

    report: dict[str, Any] = {
        "format": ITEM_RECEIPT_LAYOUT_FORMAT,
        "format_version": 1,
        "source_file": PINNED_ITEM_SOURCE_FILE,
        "source_revision": revision,
        "parent_label": ITEM_RECEIPT_PARENT_LABEL,
        "entry_count": ITEM_RECEIPT_TABLE_COUNT,
        "entries": rows,
        "dungeon_mask_count": ITEM_RECEIPT_MASK_COUNT,
        "dungeon_masks": masks,
        "semantic_item_ids_resolved": False,
    }
    try:
        validate_source_export(report)
    except AssetLoadError as exc:
        raise ItemReceiptLayoutError(f"joined receive-item layout is invalid: {exc}") from exc
    return report
