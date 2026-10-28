"""Pinned-source regression for potion-shop transaction handlers."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_potion_shop_transactions

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "potion-shop-transactions.json"
SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites" / "sprite_potion_shop.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
EXPECTED = [
    ("Sprite_GreenPotionItem", "$003C", 60, "$2F", 47, "$02F68E-$02F6FF LOCAL JUMP LOCATION"),
    ("Sprite_BluePotionItem", "$00A0", 160, "$30", 48, "$02F72B-$02F79C JUMP LOCATION"),
    ("Sprite_RedPotionItem", "$0078", 120, "$2E", 46, "$02F7D0-$02F83D JUMP LOCATION"),
]


def test_registered_potion_transactions_pin_price_and_receipt_literals() -> None:
    payload = load_source_export(EXPORT_PATH)
    assert payload["source_file"] == "sprite_potion_shop.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["entry_count"] == 3
    assert [
        (
            entry["handler_label"],
            entry["price_compare_expression"],
            entry["price_value"],
            entry["receipt_index_expression"],
            entry["receipt_item_index"],
            entry["source_handler_range_annotation"],
        )
        for entry in payload["entries"]
    ] == EXPECTED
    assert payload["evidence"]["rom_bytes_read"] is False
    assert payload["evidence"]["price_behavior_runtime_verified"] is False
    assert payload["evidence"]["canonical_item_ids_resolved"] is False


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_registered_potion_export_matches_pinned_source_parser() -> None:
    table = parse_potion_shop_transactions(
        SOURCE_PATH.read_text(encoding="utf-8"),
        source_revision=PINNED_REVISION,
        source_file="sprite_potion_shop.asm",
    )
    assert load_source_export(EXPORT_PATH) == table.to_dict()
