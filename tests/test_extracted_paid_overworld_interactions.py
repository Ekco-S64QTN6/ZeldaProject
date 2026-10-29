"""Regression baseline for all registered paid overworld interactions."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export
from zelda_suite.extract.paid_overworld_interactions import PAID_OVERWORLD_SOURCE_FILES

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "paid-overworld-interactions.json"
SOURCE_DIR = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_committed_export_pins_every_fee_model_and_source_limit() -> None:
    payload = load_source_export(EXPORT_PATH)
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["source_files"] == list(PAID_OVERWORLD_SOURCE_FILES)
    assert payload["interaction_count"] == 7
    assert {entry["interaction_id"]: entry["fee_values"] for entry in payload["interactions"]} == {
        "fortune-teller-reading": [10, 15, 20, 30],
        "digging-game-entry": [80],
        "zora-king-flippers": [500],
        "kiki-follow-fee": [10],
        "kiki-palace-access-fee": [100],
        "archery-game-entry": [20],
        "lake-hylia-fairy-donation": [5, 20, 25, 50],
    }
    assert payload["reward_tables"][0]["entry_count"] == 8
    assert payload["reward_tables"][1]["entry_count"] == 4
    assert payload["reward_gates"][0]["minimum_hole_count"] == 25
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "source_range_annotations_verified": False,
        "fee_behavior_runtime_verified": False,
        "reward_probability_runtime_verified": False,
        "item_value_names_resolved": False,
        "payment_semantics_runtime_verified": False,
    }


@pytest.mark.skipif(
    not all((SOURCE_DIR / name).is_file() for name in PAID_OVERWORLD_SOURCE_FILES),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_export_matches_pinned_source_parser() -> None:
    from zelda_suite.extract.paid_overworld_interactions import parse_paid_overworld_interactions

    sources = {
        name: (SOURCE_DIR / name).read_text(encoding="utf-8")
        for name in PAID_OVERWORLD_SOURCE_FILES
    }
    assert load_source_export(EXPORT_PATH) == parse_paid_overworld_interactions(sources)
