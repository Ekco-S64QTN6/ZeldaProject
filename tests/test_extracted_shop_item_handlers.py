"""Pinned-source regression for the standard shopkeeper purchase handlers."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_shop_item_handlers

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "shop-item-handlers.json"
SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites" / "sprite_shopkeeper.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
EXPECTED = [
    ("ShopItem_RedPotion150", 0x96, 0x00, 0x2E, 150, "$F16E"),
    ("ShopItem_FighterShield", 0x32, 0x00, 0x04, 50, "$F1F2"),
    ("ShopItem_FireShield", 0xF4, 0x01, 0x05, 500, "$F230"),
    ("ShopItem_Heart", 0x0A, 0x00, 0x42, 10, "$F27D"),
    ("ShopItem_Arrows", 0x1E, 0x00, 0x44, 30, "$F2AF"),
    ("ShopItem_Bombs", 0x32, 0x00, 0x31, 50, "$F2F0"),
    ("ShopItem_Bee", 0x0A, 0x00, 0x0E, 10, "$F322"),
]


def test_registered_purchase_handlers_pin_raw_price_and_receipt_selectors() -> None:
    payload = load_source_export(EXPORT_PATH)
    assert payload["source_file"] == "sprite_shopkeeper.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["dispatch_routine_source_range_annotation"] == "$0F6EEF-$0F6F11 JUMP LOCATION"
    assert payload["dispatch_table_file_offset"] is None
    assert payload["entry_count"] == 7
    assert [
        (
            entry["handler_label"],
            int(entry["price_low_expression"][1:], 16),
            int(entry["price_high_expression"][1:], 16),
            entry["receipt_item_index"],
            entry["price_value"],
            entry["source_handler_address_annotation"],
        )
        for entry in payload["entries"]
    ] == EXPECTED
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "dispatch_table_offset_established": False,
        "handler_address_annotations_verified": False,
        "price_behavior_runtime_verified": False,
        "receipt_item_names_resolved": False,
        "room_specific_shop_stock_resolved": False,
    }


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_registered_purchase_export_matches_pinned_source_parser() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    table = parse_shop_item_handlers(
        source,
        source_revision=PINNED_REVISION,
        source_file="sprite_shopkeeper.asm",
    )
    assert load_source_export(EXPORT_PATH) == table.to_dict()
