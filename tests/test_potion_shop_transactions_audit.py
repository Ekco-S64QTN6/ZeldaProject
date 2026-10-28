"""Regression tests for potion-shop purchase / receipt-slot cross-references."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.potion_shop_transactions_audit import (
    POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT,
    audit_potion_shop_transactions,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
EXPECTED = [
    (0, "Sprite_GreenPotionItem", 60, 47, "POTION REFILL (GREEN)"),
    (1, "Sprite_BluePotionItem", 160, 48, "POTION REFILL (BLUE)"),
    (2, "Sprite_RedPotionItem", 120, 46, "POTION REFILL (RED)"),
]


def test_registered_audit_joins_receipt_indexes_to_raw_layout_and_comments() -> None:
    report = audit_potion_shop_transactions(MANIFEST)
    assert report["format"] == POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT
    assert report["format_version"] == 1
    assert report["transaction_count"] == 3
    assert report["summary"] == {
        "transaction_count": 3,
        "distinct_receipt_item_index_count": 3,
        "minimum_price_value": 60,
        "maximum_price_value": 160,
        "receipt_layout_entry_count": 76,
        "receipt_indexes_within_layout": 3,
        "receipt_indexes_with_comment_id_mismatch": 0,
    }
    assert [
        (
            row["transaction_index"],
            row["handler_label"],
            row["price_value"],
            row["receipt_item_index"],
            row["receipt_slot"]["graphics_index_annotation"]["source_comment_label"],
        )
        for row in report["rows"]
    ] == EXPECTED
    assert all(
        row["receipt_slot"]["graphics_index_annotation"][
            "source_comment_id_matches_table_index"
        ] is True
        for row in report["rows"]
    )
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "price_behavior_runtime_verified": False,
        "source_range_annotations_verified": False,
        "receipt_item_names_resolved": False,
        "room_specific_shop_stock_resolved": False,
        "canonical_item_ids_resolved": False,
        "source_comment_ids_are_canonical": False,
        "source_comment_labels_are_raw_annotations": True,
    }
    assert report == audit_potion_shop_transactions(MANIFEST)


def test_audit_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "potion-shop-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-potion-shop-transactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["transaction_count"] == 3
    assert "price_range=60-160" in written.output

    refused = runner.invoke(cli, [
        "audit-potion-shop-transactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
