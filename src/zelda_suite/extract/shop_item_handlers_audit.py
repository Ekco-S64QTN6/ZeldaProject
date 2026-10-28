"""Join purchase-handler receipt selectors to raw item-receipt layout slots."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    ITEM_RECEIPT_LAYOUT_FORMAT,
    SHOP_ITEM_HANDLERS_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.extract.item_receipt_annotation_audit import (
    ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
    ItemReceiptAnnotationAuditError,
    audit_item_receipt_annotations,
)

SHOP_ITEM_HANDLERS_AUDIT_FORMAT = "zelda-suite-shop-item-handlers-audit"
SHOP_ITEM_HANDLERS_ASSET_NAME = "shop-item-handlers"
ITEM_RECEIPT_LAYOUT_ASSET_NAME = "item-receipt-layout"


class ShopItemHandlersAuditError(ValueError):
    """Raised when registered shop purchase handlers cannot be audited."""


def audit_shop_item_handlers(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = SHOP_ITEM_HANDLERS_ASSET_NAME,
    receipt_asset_name: str = ITEM_RECEIPT_LAYOUT_ASSET_NAME,
) -> dict[str, Any]:
    """Join source receipt selectors to raw receive-item records by table index.

    The receipt layout is an index-based raw-data view. This audit deliberately
    does not map receipt slots to canonical item names or infer which purchases
    appear in particular rooms/shops.
    """
    try:
        records = list_extracted_assets(registry_path)
        by_name = {record["name"]: record for record in records}
        purchase_record = by_name.get(asset_name)
        receipt_record = by_name.get(receipt_asset_name)
        if purchase_record is None:
            raise ShopItemHandlersAuditError(
                f"shop-item handler asset is not registered: {asset_name!r}"
            )
        if receipt_record is None:
            raise ShopItemHandlersAuditError(
                f"item-receipt layout asset is not registered: {receipt_asset_name!r}"
            )
        if purchase_record["format"] != SHOP_ITEM_HANDLERS_FORMAT:
            raise ShopItemHandlersAuditError(
                f"asset {asset_name!r} must use {SHOP_ITEM_HANDLERS_FORMAT!r}"
            )
        if receipt_record["format"] != ITEM_RECEIPT_LAYOUT_FORMAT:
            raise ShopItemHandlersAuditError(
                f"asset {receipt_asset_name!r} must use {ITEM_RECEIPT_LAYOUT_FORMAT!r}"
            )
        purchases = load_extracted_asset(asset_name, registry_path)
        receipts = load_extracted_asset(receipt_asset_name, registry_path)
        annotation_report = audit_item_receipt_annotations(
            registry_path, asset_name=ITEM_RECEIPT_GRAPHICS_ASSET_NAME
        )
    except (AssetLoadError, ItemReceiptAnnotationAuditError, OSError) as exc:
        raise ShopItemHandlersAuditError(str(exc)) from exc

    if purchases["source_revision"] != receipts["source_revision"]:
        raise ShopItemHandlersAuditError(
            "shop-item handler and item-receipt exports do not share a source revision"
        )
    if purchases["source_revision"] != annotation_report["source_revision"]:
        raise ShopItemHandlersAuditError(
            "shop-item handlers and graphics comment annotations do not share a source revision"
        )
    annotation_by_index = {
        row["table_index"]: row for row in annotation_report["entries"]
    }
    receipt_entries = receipts["entries"]
    receipt_count = len(receipt_entries)
    rows: list[dict[str, Any]] = []
    seen_receipt_indexes: set[int] = set()
    for entry in purchases["entries"]:
        receipt_index = entry["receipt_item_index"]
        if not 0 <= receipt_index < receipt_count:
            raise ShopItemHandlersAuditError(
                f"receipt item index {receipt_index} from "
                f"{entry['handler_label']!r} is outside the {receipt_count}-entry layout"
            )
        slot = receipt_entries[receipt_index]
        if slot["table_index"] != receipt_index:
            raise ShopItemHandlersAuditError(
                f"receipt layout slot {receipt_index} has table_index "
                f"{slot['table_index']!r}"
            )
        annotation = annotation_by_index.get(receipt_index)
        if annotation is None:
            raise ShopItemHandlersAuditError(
                f"no graphics comment annotation exists for receipt table index {receipt_index}"
            )
        seen_receipt_indexes.add(receipt_index)
        rows.append({
            "shopkeeper_variant_id": entry["shopkeeper_variant_id"],
            "handler_label": entry["handler_label"],
            "source_handler_address_annotation": entry["source_handler_address_annotation"],
            "source_handler_range_annotation": entry["source_handler_range_annotation"],
            "source_dispatch_line": entry["source_dispatch_line"],
            "price_value": entry["price_value"],
            "price_low_expression": entry["price_low_expression"],
            "price_high_expression": entry["price_high_expression"],
            "payment_call_source_line": entry["payment_call_source_line"],
            "receipt_item_index": receipt_index,
            "receipt_index_expression": entry["receipt_index_expression"],
            "receipt_selector_source_line": entry["receipt_selector_source_line"],
            "receipt_call_source_line": entry["receipt_call_source_line"],
            "receipt_slot": {
                "table_index": slot["table_index"],
                "item_value": slot["item_value"],
                "target_address": slot["target_address"],
                "wide_item_flag": slot["wide_item_flag"],
                "properties": slot["properties"],
                "x_offset": slot["x_offset"],
                "y_offset": slot["y_offset"],
                "graphics_index_annotation": {
                    "table_index": annotation["table_index"],
                    "expression": annotation["expression"],
                    "literal_value": annotation["literal_value"],
                    "source_comment": annotation["source_comment"],
                    "source_comment_item_id": annotation["source_comment_item_id"],
                    "source_comment_label": annotation["source_comment_label"],
                    "source_comment_annotation_parsed": annotation[
                        "source_comment_annotation_parsed"
                    ],
                    "source_comment_id_matches_table_index": annotation[
                        "source_comment_id_matches_table_index"
                    ],
                    "annotation_id_delta": annotation["annotation_id_delta"],
                },
            },
        })

    rows.sort(key=lambda row: row["shopkeeper_variant_id"])
    prices = [row["price_value"] for row in rows]
    return {
        "format": SHOP_ITEM_HANDLERS_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "receipt_asset_name": receipt_asset_name,
        "graphics_annotation_asset_name": ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
        "source_file": purchases["source_file"],
        "source_revision": purchases["source_revision"],
        "dispatch_routine_label": purchases["dispatch_routine_label"],
        "dispatch_routine_source_range_annotation": purchases[
            "dispatch_routine_source_range_annotation"
        ],
        "dispatch_table_file_offset": None,
        "rows": rows,
        "summary": {
            "handler_count": len(rows),
            "distinct_receipt_item_index_count": len(seen_receipt_indexes),
            "minimum_price_value": min(prices),
            "maximum_price_value": max(prices),
            "receipt_layout_entry_count": receipt_count,
            "receipt_indexes_within_layout": len(seen_receipt_indexes),
            "receipt_indexes_with_comment_id_mismatch": sum(
                row["receipt_slot"]["graphics_index_annotation"][
                    "source_comment_id_matches_table_index"
                ] is False
                for row in rows
            ),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "dispatch_table_offset_established": False,
            "handler_address_annotations_verified": False,
            "price_behavior_runtime_verified": False,
            "receipt_item_names_resolved": False,
            "room_specific_shop_stock_resolved": False,
            "receipt_slot_semantics_verified": False,
            "source_comment_ids_are_canonical": False,
            "source_comment_labels_are_raw_annotations": True,
        },
    }
