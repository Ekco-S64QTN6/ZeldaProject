"""Tests for registered source-only overworld payload inventories."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import load_extracted_asset, load_source_export
from zelda_suite.extract.incbin_inventory import parse_incbin_inventory

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "AsarUSALTTPDisassembly"
BANK0B_PATH = REFERENCE / "Bank0B.asm"
BANK0C_PATH = REFERENCE / "Bank0C.asm"
BANK0B_EXPORT = ROOT / "data" / "extracted" / "overworld-payloads-bank0b.json"
BANK0C_EXPORT = ROOT / "data" / "extracted" / "overworld-payloads-bank0c.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not BANK0B_PATH.is_file() or not BANK0C_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_overworld_payload_inventories_match_pinned_source() -> None:
    cases = [
        (BANK0B_PATH, BANK0B_EXPORT, "Bank0B.asm", 164),
        (BANK0C_PATH, BANK0C_EXPORT, "Bank0C.asm", 84),
    ]

    for source_path, export_path, source_file, expected_count in cases:
        payload = load_source_export(export_path)
        declarations = parse_incbin_inventory(
            source_path.read_text(encoding="utf-8"),
            source_file=source_file,
            source_revision=PINNED_REVISION,
        )

        assert payload["format"] == "zelda-suite-incbin-inventory"
        assert payload["source_file"] == source_file
        assert payload["source_revision"] == PINNED_REVISION
        assert payload["declaration_count"] == expected_count
        assert payload["declarations"] == [item.to_dict() for item in declarations]
        assert all(
            item["incbin_path"].startswith("bin/ow/")
            for item in payload["declarations"]
        )

    bank0b = load_source_export(BANK0B_EXPORT)
    assert sum(
        item["source_range_size_matches"] is True
        for item in bank0b["declarations"]
    ) == 161
    assert [
        item["label"]
        for item in bank0b["declarations"]
        if item["source_range_size_matches"] is False
    ] == [
        "OverworldMap32_Screen42_Low",
        "OverworldMap32_Screen61_Low",
    ]
    assert [
        item["label"]
        for item in bank0b["declarations"]
        if item["source_file_offset_start"] is None
        or item["source_file_offset_end"] is None
    ] == ["OverworldMap32_Screen4F_High"]

    bank0c = load_source_export(BANK0C_EXPORT)
    assert sum(
        item["source_range_size_matches"] is True
        for item in bank0c["declarations"]
    ) == 83
    assert [
        item["label"]
        for item in bank0c["declarations"]
        if item["source_range_size_matches"] is False
    ] == ["OverworldMap32_Screen88_Low"]


@pytest.mark.skipif(
    not BANK0B_PATH.is_file() or not BANK0C_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_inspect_incbin_cli_reproduces_both_committed_inventories(
    tmp_path: Path,
) -> None:
    cases = [
        (BANK0B_PATH, BANK0B_EXPORT, "overworld-bank0b.json"),
        (BANK0C_PATH, BANK0C_EXPORT, "overworld-bank0c.json"),
    ]

    for source_path, export_path, output_name in cases:
        generated_path = tmp_path / output_name
        result = CliRunner().invoke(
            cli,
            [
                "inspect-incbin",
                str(source_path),
                "--source-revision",
                PINNED_REVISION,
                "--output",
                str(generated_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert load_source_export(generated_path) == load_source_export(export_path)


def test_overworld_payload_inventories_are_registered_by_name() -> None:
    bank0b = load_extracted_asset("overworld-payloads-bank0b", REGISTRY_PATH)
    bank0c = load_extracted_asset("overworld-payloads-bank0c", REGISTRY_PATH)

    assert bank0b["source_file"] == "Bank0B.asm"
    assert bank0b["declaration_count"] == 164
    assert bank0c["source_file"] == "Bank0C.asm"
    assert bank0c["declaration_count"] == 84
