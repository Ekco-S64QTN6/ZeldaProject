"""Tests for the committed receive-item source table exports."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import load_extracted_asset, load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Ancilla" / "ancilla_init.asm"
)
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

TABLES = [
    {
        "name": "item-receipt-target-addresses",
        "file": ROOT / "data" / "extracted" / "item-receipt-target-addresses.json",
        "label": ".item_target_addr",
        "offset": 0x0484E8,
        "directive": "dw",
        "end_label": ".item_values",
        "count": 76,
    },
    {
        "name": "item-receipt-values",
        "file": ROOT / "data" / "extracted" / "item-receipt-values.json",
        "label": ".item_values",
        "offset": 0x048580,
        "directive": "db",
        "end_label": ".item_masks",
        "count": 76,
    },
    {
        "name": "item-receipt-dungeon-masks",
        "file": ROOT / "data" / "extracted" / "item-receipt-dungeon-masks.json",
        "label": ".item_masks",
        "offset": 0x0485CC,
        "directive": "dw",
        "end_label": None,
        "count": 14,
    },
]


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_item_receipt_tables_match_pinned_source() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for spec in TABLES:
        payload = load_source_export(spec["file"])
        entries = parse_data_table(
            source,
            spec["label"],
            spec["offset"],
            directive=spec["directive"],
            parent_label="Pool_AddReceiveItem",
            end_label=spec["end_label"],
            source_revision=PINNED_REVISION,
        )

        assert payload["format"] == "zelda-suite-data-table"
        assert payload["source_file"] == "ancilla_init.asm"
        assert payload["source_revision"] == PINNED_REVISION
        assert payload["parent_label"] == "Pool_AddReceiveItem"
        assert payload["table_label"] == spec["label"]
        assert payload["table_file_offset"] == spec["offset"]
        assert payload["directive"] == spec["directive"]
        assert payload["entry_width"] == (1 if spec["directive"] == "db" else 2)
        assert payload["entry_count"] == spec["count"]
        assert payload["entries"] == [entry.to_dict() for entry in entries]


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_inspect_data_table_cli_reproduces_receive_item_exports(tmp_path: Path) -> None:
    for spec in TABLES:
        output = tmp_path / (spec["name"] + ".json")
        args = [
            "inspect-data-table",
            str(SOURCE_PATH),
            spec["label"],
            "--table-offset",
            "$" + format(spec["offset"], "06X"),
            "--directive",
            spec["directive"],
            "--parent-label",
            "Pool_AddReceiveItem",
            "--source-revision",
            PINNED_REVISION,
            "--output",
            str(output),
        ]
        if spec["end_label"] is not None:
            args.extend(["--end-label", spec["end_label"]])

        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0, result.output
        assert load_source_export(output) == load_source_export(spec["file"])


def test_receive_item_tables_are_registered_by_name() -> None:
    expected_counts = {
        "item-receipt-target-addresses": 76,
        "item-receipt-values": 76,
        "item-receipt-dungeon-masks": 14,
    }
    for name, count in expected_counts.items():
        payload = load_extracted_asset(name, REGISTRY_PATH)
        assert payload["entry_count"] == count
        assert payload["source_revision"] == PINNED_REVISION


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_receive_item_values_preserve_raw_negative_sentinels() -> None:
    payload = load_source_export(TABLES[1]["file"])
    values = [entry["literal_value"] for entry in payload["entries"]]

    assert len(values) == 76
    assert 0xFF in values
    assert 0xFB in values
    assert 0xEC in values
    # The table stores byte patterns. Signed-byte write suppression remains
    # consumer behavior; this export does not replace the values with meanings.
    assert payload["entries"][0]["expression"] == "$01"
