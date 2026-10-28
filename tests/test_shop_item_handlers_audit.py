"""Regression tests for source-only shop purchase / receipt-slot cross-reference."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.shop_item_handlers_audit import (
    SHOP_ITEM_HANDLERS_AUDIT_FORMAT,
    audit_shop_item_handlers,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
EXPECTED = [
    (7, "ShopItem_RedPotion150", 150, 46),
    (8, "ShopItem_FighterShield", 50, 4),
    (9, "ShopItem_FireShield", 500, 5),
    (10, "ShopItem_Heart", 10, 66),
    (11, "ShopItem_Arrows", 30, 68),
    (12, "ShopItem_Bombs", 50, 49),
    (13, "ShopItem_Bee", 10, 14),
]


def test_registered_audit_joins_raw_receipt_slots_by_index() -> None:
    report = audit_shop_item_handlers(MANIFEST)
    assert report["format"] == SHOP_ITEM_HANDLERS_AUDIT_FORMAT
    assert report["format_version"] == 1
    assert report["summary"] == {
        "handler_count": 7,
        "distinct_receipt_item_index_count": 7,
        "minimum_price_value": 10,
        "maximum_price_value": 500,
        "receipt_layout_entry_count": 76,
        "receipt_indexes_within_layout": 7,
    }
    assert [
        (
            row["shopkeeper_variant_id"],
            row["handler_label"],
            row["price_value"],
            row["receipt_item_index"],
        )
        for row in report["rows"]
    ] == EXPECTED
    assert [
        row["receipt_slot"]["table_index"] for row in report["rows"]
    ] == [46, 4, 5, 66, 68, 49, 14]
    assert report["rows"][0]["receipt_slot"]["item_value"]["expression"] == "$FF"
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "dispatch_table_offset_established": False,
        "handler_address_annotations_verified": False,
        "price_behavior_runtime_verified": False,
        "receipt_item_names_resolved": False,
        "room_specific_shop_stock_resolved": False,
        "receipt_slot_semantics_verified": False,
    }
    assert report == audit_shop_item_handlers(MANIFEST)


def test_audit_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "shop-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-shop-item-handlers",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["handler_count"] == 7
    assert "receipt_slots=7" in written.output

    refused = runner.invoke(cli, [
        "audit-shop-item-handlers",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
