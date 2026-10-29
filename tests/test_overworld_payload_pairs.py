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
    audit_overworld_payload_layout,
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
    assert by_source["Bank0C.asm"]["screen_tokens"][-1] == "9F"


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


def test_layout_audit_reports_source_range_discrepancies_without_decoding() -> None:
    report = audit_overworld_payload_layout(_load_inventories())

    assert report["format"] == "zelda-suite-overworld-payload-layout-audit"
    assert report["format_version"] == 1
    assert report["source_revision"] == "347c23f9fc019c72d32da537c9cb235f468d021d"
    assert report["summary"] == {
        "source_count": 2,
        "declaration_count": 248,
        "screen_pair_count": 124,
        "high_layer_count": 124,
        "low_layer_count": 124,
        "range_size_match_count": 244,
        "range_size_mismatch_count": 3,
        "range_size_unknown_count": 1,
        "candidate_source_ranges_adjacent_count": 123,
        "candidate_source_ranges_nonadjacent_count": 0,
        "candidate_source_ranges_adjacency_unknown_count": 1,
    }
    assert [
        (item["source_file"], item["screen_token"], item["layer"], item["kind"])
        for item in report["range_size_mismatches"]
    ] == [
        ("Bank0B.asm", "42", "Low", "range_size_mismatch"),
        ("Bank0B.asm", "61", "Low", "range_size_mismatch"),
        ("Bank0C.asm", "88", "Low", "range_size_mismatch"),
    ]
    assert [
        (item["source_file"], item["screen_token"], item["layer"], item["kind"])
        for item in report["range_size_unknowns"]
    ] == [("Bank0B.asm", "4F", "High", "range_size_unknown")]

    screen00 = next(
        pair for pair in report["screen_pairs"]
        if pair["source_file"] == "Bank0B.asm" and pair["screen_token"] == "00"
    )
    assert screen00["high"]["declared_size_bytes"] == 4
    assert screen00["low"]["declared_size_bytes"] == 210
    assert screen00["candidate_source_ranges_adjacent"] is True

    screen4f = next(
        pair for pair in report["screen_pairs"]
        if pair["source_file"] == "Bank0B.asm" and pair["screen_token"] == "4F"
    )
    assert screen4f["high"]["source_range_size_matches"] is None
    assert screen4f["candidate_source_ranges_adjacent"] is None

    assert report["source_semantics"]["source_log_lines"] == [969, 970]
    assert report["source_semantics"]["consumer_label"] == "Overworld_LoadAndBuildScreen_long"
    assert report["source_semantics"]["semantic_decode_completed"] is False
    assert report["evidence"] == {
        "source_only": True,
        "incbin_target_files_opened": False,
        "rom_bytes_read": False,
        "source_range_offsets_verified": False,
        "compressed_payloads_decoded": False,
        "editable_map_layers_emitted": False,
        "runtime_map_semantics_verified": False,
    }



def test_pair_validator_is_generic_but_layout_audit_requires_pinned_revision() -> None:
    inventories = _load_inventories()
    for inventory in inventories:
        inventory["source_revision"] = "another-revision"
        for declaration in inventory["declarations"]:
            declaration["source_revision"] = "another-revision"

    assert validate_overworld_payload_pairs(inventories)["valid"] is True
    with pytest.raises(OverworldPayloadPairError, match="requires source revision"):
        audit_overworld_payload_layout(inventories)


def test_layout_audit_rejects_incomplete_pinned_inventory_baseline() -> None:
    inventories = _load_inventories()
    bank0b = copy.deepcopy(inventories[0])
    bank0b["declarations"] = [
        declaration
        for declaration in bank0b["declarations"]
        if declaration["label"] not in {
            "OverworldMap32_Screen00_High",
            "OverworldMap32_Screen00_Low",
        }
    ]
    bank0b["declaration_count"] = len(bank0b["declarations"])
    inventories[0] = bank0b

    assert validate_overworld_payload_pairs(inventories)["screen_pair_count"] == 123
    with pytest.raises(OverworldPayloadPairError, match="requires the pinned Bank0B.asm"):
        audit_overworld_payload_layout(inventories)

def test_layout_audit_cli_writes_json_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "overworld-layout-audit.json"
    runner = CliRunner()
    written = runner.invoke(
        cli,
        [
            "audit-overworld-payload-layout",
            str(BANK0B_EXPORT),
            str(BANK0C_EXPORT),
            "--output",
            str(output),
        ],
    )
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["screen_pair_count"] == 124
    assert "range_mismatches=3" in written.output
    assert "range_unknown=1" in written.output

    refused = runner.invoke(
        cli,
        [
            "audit-overworld-payload-layout",
            str(BANK0B_EXPORT),
            str(BANK0C_EXPORT),
            "--output",
            str(output),
        ],
    )
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
