"""Tests for source-labelled overworld High/Low pair validation."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    OverworldPayloadPairError,
    load_source_export,
    validate_overworld_payload_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
BANK0B_EXPORT = ROOT / "data" / "extracted" / "overworld-payloads-bank0b.json"
BANK0C_EXPORT = ROOT / "data" / "extracted" / "overworld-payloads-bank0c.json"


def _load_inventories() -> list[dict[str, Any]]:
    return [
        load_source_export(BANK0B_EXPORT),
        load_source_export(BANK0C_EXPORT),
    ]


def test_committed_overworld_inventories_have_complete_source_local_pairs() -> None:
    report = validate_overworld_payload_pairs(_load_inventories())

    assert report["valid"] is True
    assert report["source_count"] == 2
    assert report["screen_pair_count"] == 124
    by_source = {source["source_file"]: source for source in report["sources"]}
    assert by_source["Bank0B.asm"]["screen_count"] == 82
    assert by_source["Bank0C.asm"]["screen_count"] == 42
    assert by_source["Bank0B.asm"]["screen_tokens"][0] == "00"
    assert by_source["Bank0C.asm"]["screen_tokens"][-1] == "88"


def test_validator_rejects_a_missing_low_declaration() -> None:
    inventories = _load_inventories()
    bank0b = copy.deepcopy(inventories[0])
    bank0b["declarations"] = [
        declaration
        for declaration in bank0b["declarations"]
        if declaration["label"] != "OverworldMap32_Screen00_Low"
    ]
    bank0b["declaration_count"] = len(bank0b["declarations"])
    inventories[0] = bank0b

    with pytest.raises(OverworldPayloadPairError, match="Screen00.*Low"):
        validate_overworld_payload_pairs(inventories)


def test_validator_rejects_duplicate_high_declaration() -> None:
    inventories = _load_inventories()
    bank0b = copy.deepcopy(inventories[0])
    high = next(
        declaration
        for declaration in bank0b["declarations"]
        if declaration["label"] == "OverworldMap32_Screen00_High"
    )
    bank0b["declarations"].append(copy.deepcopy(high))
    bank0b["declaration_count"] = len(bank0b["declarations"])
    inventories[0] = bank0b

    with pytest.raises(OverworldPayloadPairError, match="Screen00.*High"):
        validate_overworld_payload_pairs(inventories)


def test_validator_rejects_duplicate_source_file_and_mixed_revisions() -> None:
    inventories = _load_inventories()
    with pytest.raises(OverworldPayloadPairError, match="duplicate source_file"):
        validate_overworld_payload_pairs([inventories[0], inventories[0]])

    mixed_revision = copy.deepcopy(inventories[1])
    mixed_revision["source_revision"] = "another-revision"
    for declaration in mixed_revision["declarations"]:
        declaration["source_revision"] = "another-revision"
    with pytest.raises(OverworldPayloadPairError, match="same source_revision"):
        validate_overworld_payload_pairs([inventories[0], mixed_revision])


def test_cli_validates_committed_overworld_inventory_pairs() -> None:
    result = CliRunner().invoke(
        cli,
        [
            "validate-overworld-payload-pairs",
            str(BANK0B_EXPORT),
            str(BANK0C_EXPORT),
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["valid"] is True
    assert report["screen_pair_count"] == 124


def test_cli_returns_a_clear_error_for_an_incomplete_pair(tmp_path: Path) -> None:
    inventories = _load_inventories()
    broken = copy.deepcopy(inventories[0])
    broken["declarations"] = [
        declaration
        for declaration in broken["declarations"]
        if declaration["label"] != "OverworldMap32_Screen00_Low"
    ]
    broken["declaration_count"] = len(broken["declarations"])
    broken_path = tmp_path / "broken-overworld-inventory.json"
    broken_path.write_text(
        json.dumps(broken, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        [
            "validate-overworld-payload-pairs",
            str(broken_path),
            str(BANK0C_EXPORT),
        ],
    )

    assert result.exit_code != 0
    assert "Screen00" in result.output
    assert "Low" in result.output
