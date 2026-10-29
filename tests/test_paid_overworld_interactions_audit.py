"""Tests for the paid-overworld interaction audit."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.paid_overworld_interactions_audit import (
    PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT,
    audit_paid_overworld_interactions,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
EXPECTED = {
    "fortune-teller-reading": [10, 15, 20, 30],
    "digging-game-entry": [80],
    "zora-king-flippers": [500],
    "kiki-follow-fee": [10],
    "kiki-palace-access-fee": [100],
    "archery-game-entry": [20],
    "lake-hylia-fairy-donation": [5, 20, 25, 50],
}


def test_registered_paid_interaction_audit_summarizes_source_fees_and_rewards() -> None:
    report = audit_paid_overworld_interactions(MANIFEST)
    assert report["format"] == PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT
    assert report["summary"] == {
        "interaction_count": 7,
        "fixed_fee_interaction_count": 5,
        "selected_price_table_interaction_count": 2,
        "unique_fee_value_count": 10,
        "minimum_fee_value": 5,
        "maximum_fee_value": 500,
        "digging_game_dispatch_entry_count": 8,
        "digging_game_basic_reward_count": 4,
        "digging_game_minimum_hole_count_for_heart_piece_gate": 25,
    }
    assert {t["interaction_id"]: t["fee_values"] for t in report["transactions"]} == EXPECTED
    rewards = report["digging_game_rewards"]
    assert [e["handler_label"] for e in rewards["dispatch_entries"]] == [
        "DiggingGameGuy_GiveItem_basic",
        "DiggingGameGuy_GiveItem_basic",
        "DiggingGameGuy_GiveItem_basic",
        "DiggingGameGuy_GiveItem_basic",
        "DiggingGameGuy_GiveItem_heart_piece",
        "DiggingGameGuy_GiveItem_nothing",
        "DiggingGameGuy_GiveItem_nothing",
        "DiggingGameGuy_GiveItem_nothing",
    ]
    assert [e["expression"] for e in rewards["basic_reward_pool"]] == [
        "$DB", "$DA", "$D9", "$DF"
    ]
    assert report["evidence"]["rom_bytes_read"] is False
    assert report == audit_paid_overworld_interactions(MANIFEST)


def test_audit_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "paid-overworld-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-paid-overworld-interactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["interaction_count"] == 7
    assert "fee_range=5-500" in written.output

    refused = runner.invoke(cli, [
        "audit-paid-overworld-interactions",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
