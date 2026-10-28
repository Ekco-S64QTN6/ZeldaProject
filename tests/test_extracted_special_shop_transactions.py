"""Pinned-source regression for special-shop purchase transactions."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_special_shop_transactions

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "special-shop-transactions.json"
SOURCE_ROOT = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites"
BOMB_SOURCE = SOURCE_ROOT / "sprite_bomb_shop_entity.asm"
BOTTLE_SOURCE = SOURCE_ROOT / "sprite_bottle_vendor.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_registered_special_shop_export_pins_source_transactions() -> None:
    payload = load_source_export(EXPORT_PATH)
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["source_file"] == "sprite_bomb_shop_entity.asm;sprite_bottle_vendor.asm"
    assert payload["entry_count"] == 3
    assert [
        (entry["transaction_label"], entry["price_value"], entry["receipt_item_index"])
        for entry in payload["entries"]
    ] == [
        ("Bomb Shop Bomb", 100, 0x28),
        ("Bomb Shop Super Bomb", 100, None),
        ("Bottle Vendor Bottle Sale", 100, 0x16),
    ]
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "source_range_annotations_verified": False,
        "price_behavior_runtime_verified": False,
        "receipt_item_names_resolved": False,
        "room_specific_shop_stock_resolved": False,
        "canonical_item_ids_resolved": False,
        "special_bomb_reward_runtime_verified": False,
    }


@pytest.mark.skipif(
    not BOMB_SOURCE.is_file() or not BOTTLE_SOURCE.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_special_shop_export_matches_pinned_source_parser() -> None:
    table = parse_special_shop_transactions(
        BOMB_SOURCE.read_text(encoding="utf-8"),
        BOTTLE_SOURCE.read_text(encoding="utf-8"),
        source_revision=PINNED_REVISION,
        bomb_shop_source_file=BOMB_SOURCE.name,
        bottle_vendor_source_file=BOTTLE_SOURCE.name,
    )
    assert load_source_export(EXPORT_PATH) == table.to_dict()
