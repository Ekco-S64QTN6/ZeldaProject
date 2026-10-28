"""Cross-reference special-shop transactions to raw receive-item slots."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    ITEM_RECEIPT_LAYOUT_FORMAT,
    SPECIAL_SHOP_TRANSACTIONS_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.extract.item_receipt_annotation_audit import (
    ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
    ItemReceiptAnnotationAuditError,
    audit_item_receipt_annotations,
)

SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT = "zelda-suite-special-shop-transactions-audit"
SPECIAL_SHOP_TRANSACTIONS_ASSET_NAME = "special-shop-transactions"
ITEM_RECEIPT_LAYOUT_ASSET_NAME = "item-receipt-layout"


class SpecialShopTransactionsAuditError(ValueError):
    """Raised when special-shop transaction references cannot be audited."""


def audit_special_shop_transactions(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = SPECIAL_SHOP_TRANSACTIONS_ASSET_NAME,
    receipt_asset_name: str = ITEM_RECEIPT_LAYOUT_ASSET_NAME,
) -> dict[str, Any]:
    """Join receipt indexes to raw fields and source-comment annotations by table index.

    The Super Bomb reward writes a game-state flag and spawns a tagalong instead
    of invoking Link_ReceiveItem; its receipt-slot fields therefore remain null.
    """
    try:
        records = list_extracted_assets(registry_path)
        by_name = {record["name"]: record for record in records}
        transaction_record = by_name.get(asset_name)
        receipt_record = by_name.get(receipt_asset_name)
        if transaction_record is None:
            raise SpecialShopTransactionsAuditError(
                f"special-shop transaction asset is not registered: {asset_name!r}"
            )
        if receipt_record is None:
            raise SpecialShopTransactionsAuditError(
                f"item-receipt layout asset is not registered: {receipt_asset_name!r}"
            )
        if transaction_record["format"] != SPECIAL_SHOP_TRANSACTIONS_FORMAT:
            raise SpecialShopTransactionsAuditError(
                f"asset {asset_name!r} must use {SPECIAL_SHOP_TRANSACTIONS_FORMAT!r}"
            )
        if receipt_record["format"] != ITEM_RECEIPT_LAYOUT_FORMAT:
            raise SpecialShopTransactionsAuditError(
                f"asset {receipt_asset_name!r} must use {ITEM_RECEIPT_LAYOUT_FORMAT!r}"
            )
        transactions = load_extracted_asset(asset_name, registry_path)
        receipt_layout = load_extracted_asset(receipt_asset_name, registry_path)
        annotation_report = audit_item_receipt_annotations(
            registry_path, asset_name=ITEM_RECEIPT_GRAPHICS_ASSET_NAME
        )
    except (AssetLoadError, ItemReceiptAnnotationAuditError, OSError) as exc:
        raise SpecialShopTransactionsAuditError(str(exc)) from exc

    revision = transactions["source_revision"]
    if revision != receipt_layout["source_revision"]:
        raise SpecialShopTransactionsAuditError(
            "special-shop transactions and item-receipt exports do not share a source revision"
        )
    if revision != annotation_report["source_revision"]:
        raise SpecialShopTransactionsAuditError(
            "special-shop transactions and graphics comment annotations do not share a source revision"
        )

    receipt_entries = receipt_layout["entries"]
    annotation_by_index = {
        entry["table_index"]: entry for entry in annotation_report["entries"]
    }
    rows: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for transaction in transactions["entries"]:
        receipt_index = transaction["receipt_item_index"]
        receipt_slot: dict[str, Any] | None = None
        if receipt_index is not None:
            if not isinstance(receipt_index, int) or not 0 <= receipt_index < len(receipt_entries):
                raise SpecialShopTransactionsAuditError(
                    f"receipt item index {receipt_index!r} from "
                    f"{transaction['source_handler_label']!r} is outside the "
                    f"{len(receipt_entries)}-entry receive-item layout"
                )
            slot = receipt_entries[receipt_index]
            if slot["table_index"] != receipt_index:
                raise SpecialShopTransactionsAuditError(
                    f"receipt layout slot {receipt_index} has table_index "
                    f"{slot['table_index']!r}"
                )
            annotation = annotation_by_index.get(receipt_index)
            if annotation is None:
                raise SpecialShopTransactionsAuditError(
                    f"graphics comment annotation missing for receipt index {receipt_index}"
                )
            seen_indexes.add(receipt_index)
            receipt_slot = {
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
            }

        rows.append({
            "transaction_index": transaction["table_index"],
            "transaction_label": transaction["transaction_label"],
            "shop_type": transaction["shop_type"],
            "source_file": transaction["source_file"],
            "source_handler_label": transaction["source_handler_label"],
            "source_handler_range_annotation": transaction[
                "source_handler_range_annotation"
            ],
            "source_handler_label_line": transaction["source_handler_label_line"],
            "reward_handler_label": transaction["reward_handler_label"],
            "reward_handler_range_annotation": transaction[
                "reward_handler_range_annotation"
            ],
            "reward_handler_label_line": transaction["reward_handler_label_line"],
            "price_mode": transaction["price_mode"],
            "price_value": transaction["price_value"],
            "price_low_expression": transaction["price_low_expression"],
            "price_low_source_line": transaction["price_low_source_line"],
            "price_high_expression": transaction["price_high_expression"],
            "price_high_source_line": transaction["price_high_source_line"],
            "price_compare_expression": transaction["price_compare_expression"],
            "price_compare_source_line": transaction["price_compare_source_line"],
            "price_deduction_expression": transaction["price_deduction_expression"],
            "price_deduction_source_line": transaction["price_deduction_source_line"],
            "rupee_balance_address_expression": transaction[
                "rupee_balance_address_expression"
            ],
            "payment_call_source_line": transaction["payment_call_source_line"],
            "receipt_method": transaction["receipt_method"],
            "receipt_item_index": receipt_index,
            "receipt_index_expression": transaction["receipt_index_expression"],
            "receipt_selector_source_line": transaction["receipt_selector_source_line"],
            "receipt_call_source_line": transaction["receipt_call_source_line"],
            "source_item_annotation": transaction["source_item_annotation"],
            "source_item_annotation_line": transaction["source_item_annotation_line"],
            "reward_flag_address_expression": transaction[
                "reward_flag_address_expression"
            ],
            "reward_flag_value_expression": transaction[
                "reward_flag_value_expression"
            ],
            "reward_flag_source_line": transaction["reward_flag_source_line"],
            "source_reward_comment": transaction["source_reward_comment"],
            "tagalong_spawn_source_line": transaction["tagalong_spawn_source_line"],
            "receipt_slot": receipt_slot,
        })

    rows.sort(key=lambda row: row["transaction_index"])
    prices = [row["price_value"] for row in rows]
    return {
        "format": SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "receipt_asset_name": receipt_asset_name,
        "graphics_annotation_asset_name": ITEM_RECEIPT_GRAPHICS_ASSET_NAME,
        "source_revision": revision,
        "transaction_count": len(rows),
        "rows": rows,
        "summary": {
            "transaction_count": len(rows),
            "receipt_transaction_count": sum(row["receipt_item_index"] is not None for row in rows),
            "distinct_receipt_item_index_count": len(seen_indexes),
            "non_receipt_reward_count": sum(row["receipt_item_index"] is None for row in rows),
            "minimum_price_value": min(prices),
            "maximum_price_value": max(prices),
            "receipt_layout_entry_count": len(receipt_entries),
            "receipt_indexes_within_layout": len(seen_indexes),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "source_range_annotations_verified": False,
            "price_behavior_runtime_verified": False,
            "receipt_item_names_resolved": False,
            "room_specific_shop_stock_resolved": False,
            "canonical_item_ids_resolved": False,
            "special_bomb_reward_runtime_verified": False,
            "receipt_slot_semantics_verified": False,
        },
    }
