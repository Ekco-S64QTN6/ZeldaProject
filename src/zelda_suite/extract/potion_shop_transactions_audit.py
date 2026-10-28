"""Join potion-shop transaction selectors to raw receive-item slots by index."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    ITEM_RECEIPT_LAYOUT_FORMAT,
    POTION_SHOP_TRANSACTIONS_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.extract.item_receipt_annotation_audit import (
    ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
    ItemReceiptAnnotationAuditError,
    audit_item_receipt_annotations,
)

POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT = "zelda-suite-potion-shop-transactions-audit"
POTION_SHOP_TRANSACTIONS_ASSET_NAME = "potion-shop-transactions"
ITEM_RECEIPT_LAYOUT_ASSET_NAME = "item-receipt-layout"


class PotionShopTransactionsAuditError(ValueError):
    """Raised when registered potion transactions cannot be audited."""


def audit_potion_shop_transactions(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = POTION_SHOP_TRANSACTIONS_ASSET_NAME,
    receipt_asset_name: str = ITEM_RECEIPT_LAYOUT_ASSET_NAME,
) -> dict[str, Any]:
    """Cross-reference source potion prices and receipt indexes without resolving item names."""
    try:
        records = list_extracted_assets(registry_path)
        by_name = {record["name"]: record for record in records}
        transaction_record = by_name.get(asset_name)
        receipt_record = by_name.get(receipt_asset_name)
        if transaction_record is None:
            raise PotionShopTransactionsAuditError(
                f"potion-shop transaction asset is not registered: {asset_name!r}"
            )
        if receipt_record is None:
            raise PotionShopTransactionsAuditError(
                f"item-receipt layout asset is not registered: {receipt_asset_name!r}"
            )
        if transaction_record["format"] != POTION_SHOP_TRANSACTIONS_FORMAT:
            raise PotionShopTransactionsAuditError(
                f"asset {asset_name!r} must use {POTION_SHOP_TRANSACTIONS_FORMAT!r}"
            )
        if receipt_record["format"] != ITEM_RECEIPT_LAYOUT_FORMAT:
            raise PotionShopTransactionsAuditError(
                f"asset {receipt_asset_name!r} must use {ITEM_RECEIPT_LAYOUT_FORMAT!r}"
            )
        transactions = load_extracted_asset(asset_name, registry_path)
        receipt_layout = load_extracted_asset(receipt_asset_name, registry_path)
        annotation_report = audit_item_receipt_annotations(
            registry_path, asset_name=ITEM_RECEIPT_GRAPHICS_ASSET_NAME
        )
    except (AssetLoadError, ItemReceiptAnnotationAuditError, OSError) as exc:
        raise PotionShopTransactionsAuditError(str(exc)) from exc

    revision = transactions["source_revision"]
    if revision != receipt_layout["source_revision"]:
        raise PotionShopTransactionsAuditError(
            "potion-shop transaction and item-receipt exports do not share a source revision"
        )
    if revision != annotation_report["source_revision"]:
        raise PotionShopTransactionsAuditError(
            "potion-shop transactions and graphics comment annotations do not share a source revision"
        )

    receipt_entries = receipt_layout["entries"]
    annotation_by_index = {
        entry["table_index"]: entry for entry in annotation_report["entries"]
    }
    rows: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for transaction in transactions["entries"]:
        receipt_index = transaction["receipt_item_index"]
        if not 0 <= receipt_index < len(receipt_entries):
            raise PotionShopTransactionsAuditError(
                f"receipt item index {receipt_index} from "
                f"{transaction['handler_label']!r} is outside the "
                f"{len(receipt_entries)}-entry receive-item layout"
            )
        receipt_slot = receipt_entries[receipt_index]
        if receipt_slot["table_index"] != receipt_index:
            raise PotionShopTransactionsAuditError(
                f"receipt layout slot {receipt_index} has table_index "
                f"{receipt_slot['table_index']!r}"
            )
        annotation = annotation_by_index.get(receipt_index)
        if annotation is None:
            raise PotionShopTransactionsAuditError(
                f"graphics comment annotation missing for receipt table index {receipt_index}"
            )
        seen_indexes.add(receipt_index)
        rows.append({
            "transaction_index": transaction["table_index"],
            "handler_label": transaction["handler_label"],
            "source_handler_range_annotation": transaction[
                "source_handler_range_annotation"
            ],
            "source_handler_label_line": transaction["source_handler_label_line"],
            "price_value": transaction["price_value"],
            "price_compare_expression": transaction["price_compare_expression"],
            "price_compare_source_line": transaction["price_compare_source_line"],
            "price_deduction_expression": transaction["price_deduction_expression"],
            "price_deduction_source_line": transaction["price_deduction_source_line"],
            "rupee_balance_address_expression": transaction[
                "rupee_balance_address_expression"
            ],
            "receipt_item_index": receipt_index,
            "receipt_index_expression": transaction["receipt_index_expression"],
            "receipt_selector_source_line": transaction["receipt_selector_source_line"],
            "receipt_call_source_line": transaction["receipt_call_source_line"],
            "empty_bottle_check_source_line": transaction[
                "empty_bottle_check_source_line"
            ],
            "receipt_slot": {
                "table_index": receipt_slot["table_index"],
                "item_value": receipt_slot["item_value"],
                "target_address": receipt_slot["target_address"],
                "wide_item_flag": receipt_slot["wide_item_flag"],
                "properties": receipt_slot["properties"],
                "x_offset": receipt_slot["x_offset"],
                "y_offset": receipt_slot["y_offset"],
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

    rows.sort(key=lambda row: row["transaction_index"])
    prices = [row["price_value"] for row in rows]
    return {
        "format": POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "receipt_asset_name": receipt_asset_name,
        "graphics_annotation_asset_name": ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
        "source_file": transactions["source_file"],
        "source_revision": revision,
        "transaction_count": len(rows),
        "rows": rows,
        "summary": {
            "transaction_count": len(rows),
            "distinct_receipt_item_index_count": len(seen_indexes),
            "minimum_price_value": min(prices),
            "maximum_price_value": max(prices),
            "receipt_layout_entry_count": len(receipt_entries),
            "receipt_indexes_within_layout": len(seen_indexes),
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
            "price_behavior_runtime_verified": False,
            "source_range_annotations_verified": False,
            "receipt_item_names_resolved": False,
            "room_specific_shop_stock_resolved": False,
            "canonical_item_ids_resolved": False,
            "source_comment_ids_are_canonical": False,
            "source_comment_labels_are_raw_annotations": True,
        },
    }
