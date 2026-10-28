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
    {
        "name": "item-receipt-y-offsets",
        "file": ROOT / "data" / "extracted" / "item-receipt-y-offsets.json",
        "label": ".y_offsets",
        "offset": 0x04836C,
        "directive": "db",
        "end_label": ".x_offsets",
        "count": 76,
    },
    {
        "name": "item-receipt-x-offsets",
        "file": ROOT / "data" / "extracted" / "item-receipt-x-offsets.json",
        "label": ".x_offsets",
        "offset": 0x0483B8,
        "directive": "db",
        "end_label": ".item_graphics_indices",
        "count": 76,
    },
    {
        "name": "item-receipt-wide-flags",
        "file": ROOT / "data" / "extracted" / "item-receipt-wide-flags.json",
        "label": ".wide_item_flag",
        "offset": 0x048450,
        "directive": "db",
        "end_label": ".properties",
        "count": 76,
    },
    {
        "name": "item-receipt-properties",
        "file": ROOT / "data" / "extracted" / "item-receipt-properties.json",
        "label": ".properties",
        "offset": 0x04849C,
        "directive": "db",
        "end_label": ".item_target_addr",
        "count": 76,
    },
    {
        "name": "item-receipt-graphics-indices",
        "file": ROOT / "data" / "extracted" / "item-receipt-graphics-indices.json",
        "label": ".item_graphics_indices",
        "offset": 0x048404,
        "directive": "db",
        "end_label": ".wide_item_flag",
        "count": 76,
        "include_comments": True,
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
        assert payload["format_version"] == (2 if spec.get("include_comments") else 1)
        assert payload["source_file"] == "ancilla_init.asm"
        assert payload["source_revision"] == PINNED_REVISION
        assert payload["parent_label"] == "Pool_AddReceiveItem"
        assert payload["table_label"] == spec["label"]
        assert payload["table_file_offset"] == spec["offset"]
        assert payload["directive"] == spec["directive"]
        assert payload["entry_width"] == (1 if spec["directive"] == "db" else 2)
        assert payload["entry_count"] == spec["count"]
        assert payload["entries"] == [
            entry.to_dict(include_inline_comment=spec.get("include_comments", False))
            for entry in entries
        ]


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
        if spec.get("include_comments"):
            args.append("--include-comments")

        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0, result.output
        assert load_source_export(output) == load_source_export(spec["file"])


def test_receive_item_tables_are_registered_by_name() -> None:
    expected_counts = {
        "item-receipt-target-addresses": 76,
        "item-receipt-values": 76,
        "item-receipt-dungeon-masks": 14,
        "item-receipt-y-offsets": 76,
        "item-receipt-x-offsets": 76,
        "item-receipt-wide-flags": 76,
        "item-receipt-properties": 76,
        "item-receipt-graphics-indices": 76,
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



def test_signed_decimal_parallel_values_remain_raw_expressions() -> None:
    y_offsets = load_source_export(
        ROOT / "data" / "extracted" / "item-receipt-y-offsets.json"
    )
    properties = load_source_export(
        ROOT / "data" / "extracted" / "item-receipt-properties.json"
    )

    assert y_offsets["entries"][0]["expression"] == "-5"
    assert y_offsets["entries"][0]["literal_value"] is None
    negative_property = next(
        entry for entry in properties["entries"] if entry["expression"] == "-1"
    )
    assert negative_property["literal_value"] is None



def test_graphics_index_comments_preserve_the_missing_0x40_comment_id() -> None:
    payload = load_extracted_asset("item-receipt-graphics-indices", REGISTRY_PATH)

    assert payload["format_version"] == 2
    entries = payload["entries"]
    assert len(entries) == 76
    assert [entry["table_index"] for entry in entries] == list(range(76))
    comment_indices = [
        int(entry["inline_comment"].split("-", 1)[0].strip(), 16)
        for entry in entries
    ]
    assert comment_indices == [*range(0x40), *range(0x41, 0x4D)]
    assert entries[63]["inline_comment"].startswith("0x3F")
    assert entries[64]["inline_comment"].startswith("0x41")
    assert entries[64]["entry_file_offset"] == 0x048444
    assert entries[-1]["entry_file_offset"] == 0x04844F
