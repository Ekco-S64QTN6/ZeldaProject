"""Tests for the committed music payload source inventory."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import load_extracted_asset, load_source_export
from zelda_suite.extract.incbin_inventory import parse_incbin_inventory

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "music-payload-inventory.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_music_payload_inventory_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    declarations = parse_incbin_inventory(
        source,
        source_file="Bank1B.asm",
        source_revision=PINNED_REVISION,
    )

    assert payload["format"] == "zelda-suite-incbin-inventory"
    assert payload["source_file"] == "Bank1B.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["declaration_count"] == 15
    assert payload["declarations"] == [item.to_dict() for item in declarations]
    assert all(item["incbin_path"].startswith("bin/music/") for item in payload["declarations"])

    explicit_sizes = [
        item for item in payload["declarations"] if item["declared_size_bytes"] is not None
    ]
    assert len(explicit_sizes) == 12
    assert all(item["source_range_size_matches"] is True for item in explicit_sizes)

    auxiliary = {
        item["label"]: item
        for item in payload["declarations"]
        if item["declared_size_bytes"] is None
    }
    assert set(auxiliary) == {
        "Song1D_AgahnimEscapes",
        "Song1F_KingOfThieves",
        "Song1E_MeetingGanon",
    }
    assert auxiliary["Song1D_AgahnimEscapes"]["source_file_offset_start"] == 0x0DACC7
    assert auxiliary["Song1D_AgahnimEscapes"]["source_file_offset_end"] == 0x0DAD79
    assert auxiliary["Song1D_AgahnimEscapes"]["source_range_size_matches"] is None


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_cli_reproduces_registered_music_payload_inventory(tmp_path: Path) -> None:
    output = tmp_path / "music-payload-inventory.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-incbin",
            str(SOURCE_PATH),
            "--source-revision",
            PINNED_REVISION,
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    generated = load_source_export(output)
    committed = load_source_export(EXPORT_PATH)
    assert generated == committed


def test_music_payload_inventory_is_registered_and_loadable() -> None:
    payload = load_extracted_asset("music-payload-inventory", REGISTRY_PATH)
    assert payload["declaration_count"] == 15
    assert all(
        declaration["incbin_path"].startswith("bin/music/")
        for declaration in payload["declarations"]
    )
