"""Audit regression for special-shop receipt selector cross-references."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.special_shop_transactions_audit import (
    SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT,
    audit_special_shop_transactions,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "extracted" / "manifest.json"


def test_registered_audit_joins_receipts_and_preserves_non_receipt_reward() -> None:
    report = audit_special_shop_transactions(MANIFEST)
    assert report["format"] == SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT
    assert report["summary"] == {
        "transaction_count": 3,
        "receipt_transaction_count": 2,
        "distinct_receipt_item_index_count": 2,
        "non_receipt_reward_count": 1,
        "minimum_price_value": 100,
        "maximum_price_value": 100,
        "receipt_layout_entry_count": 76,
        "receipt_indexes_within_layout": 2,
    }
    assert [
        (row["transaction_label"], row["receipt_item_index"])
        for row in report["rows"]
    ] == [
        ("Bomb Shop Bomb", 0x28),
        ("Bomb Shop Super Bomb", None),
        ("Bottle Vendor Bottle Sale", 0x16),
    ]
    assert report["rows"][0]["receipt_slot"]["table_index"] == 0x28
    assert report["rows"][1]["receipt_slot"] is None
    assert report["rows"][2]["receipt_slot"]["table_index"] == 0x16
    assert report["rows"][0]["receipt_slot"]["graphics_index_annotation"]["table_index"] == 0x28
    assert report["rows"][2]["receipt_slot"]["graphics_index_annotation"]["table_index"] == 0x16
    assert report["evidence"]["canonical_item_ids_resolved"] is False
    assert report == audit_special_shop_transactions(MANIFEST)


def test_audit_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "special-shop-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-special-shop-transactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["non_receipt_reward_count"] == 1
    assert "receipt_slots=2" in written.output

    refused = runner.invoke(cli, [
        "audit-special-shop-transactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
