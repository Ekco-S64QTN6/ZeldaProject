"""Tests for the joined, source-traceable receive-item layout view."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    AssetLoadError,
    build_item_receipt_layout,
    load_extracted_asset,
    load_source_export,
    validate_source_export,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
LAYOUT_PATH = ROOT / "data" / "extracted" / "item-receipt-layout.json"

ARRAY_ASSETS = {
    "y_offset": "item-receipt-y-offsets",
    "x_offset": "item-receipt-x-offsets",
    "wide_item_flag": "item-receipt-wide-flags",
    "properties": "item-receipt-properties",
    "target_address": "item-receipt-target-addresses",
    "item_value": "item-receipt-values",
}


def test_joined_layout_matches_registered_raw_arrays_and_keeps_masks_separate() -> None:
    layout = load_extracted_asset("item-receipt-layout", REGISTRY_PATH)

    assert layout["format"] == "zelda-suite-item-receipt-layout"
    assert layout["format_version"] == 1
    assert layout["source_file"] == "ancilla_init.asm"
    assert layout["source_revision"] == "347c23f9fc019c72d32da537c9cb235f468d021d"
    assert layout["parent_label"] == "Pool_AddReceiveItem"
    assert layout["entry_count"] == 76
    assert layout["dungeon_mask_count"] == 14
    assert layout["semantic_item_ids_resolved"] is False

    raw_arrays = {
        field: load_extracted_asset(asset_name, REGISTRY_PATH)["entries"]
        for field, asset_name in ARRAY_ASSETS.items()
    }
    for index, row in enumerate(layout["entries"]):
        assert row["table_index"] == index
        for field, raw_entries in raw_arrays.items():
            raw_entry = raw_entries[index]
            assert row[field] == {
                "source_label": raw_entry["source_label"],
                "entry_file_offset": raw_entry["entry_file_offset"],
                "expression": raw_entry["expression"],
                "literal_value": raw_entry["literal_value"],
            }

    raw_masks = load_extracted_asset("item-receipt-dungeon-masks", REGISTRY_PATH)["entries"]
    for index, mask in enumerate(layout["dungeon_masks"]):
        assert mask == {
            "table_index": index,
            "source_label": raw_masks[index]["source_label"],
            "entry_file_offset": raw_masks[index]["entry_file_offset"],
            "expression": raw_masks[index]["expression"],
            "literal_value": raw_masks[index]["literal_value"],
        }


def test_layout_builder_reproduces_committed_export() -> None:
    committed = load_source_export(LAYOUT_PATH)
    rebuilt = build_item_receipt_layout(REGISTRY_PATH)

    assert rebuilt == committed
    raw = LAYOUT_PATH.read_bytes()
    assert raw.endswith(b"\n")
    assert json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n" == raw.decode(
        "utf-8"
    )


def test_join_item_receipt_cli_emits_and_saves_the_same_view(tmp_path: Path) -> None:
    runner = CliRunner()
    arguments = [
        "join-item-receipt-tables",
        "--registry",
        str(REGISTRY_PATH),
    ]

    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == load_source_export(LAYOUT_PATH)

    output = tmp_path / "item-receipt-layout.json"
    written = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert load_source_export(output) == load_source_export(LAYOUT_PATH)
    assert "76 joined receive-item records" in written.output
    assert "14 separate dungeon masks" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


def test_layout_validation_rejects_misaligned_source_offset() -> None:
    payload = load_source_export(LAYOUT_PATH)
    payload["entries"][1]["x_offset"]["entry_file_offset"] += 1

    with pytest.raises(AssetLoadError, match="entry_file_offset must be"):
        validate_source_export(payload)


def test_layout_validation_does_not_allow_claiming_semantic_ids_are_resolved() -> None:
    payload = load_source_export(LAYOUT_PATH)
    payload["semantic_item_ids_resolved"] = True

    with pytest.raises(AssetLoadError, match="must not claim canonical semantic item IDs"):
        validate_source_export(payload)
