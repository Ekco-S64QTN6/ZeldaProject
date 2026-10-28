"""Tests for the metadata-only source music track index."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    load_extracted_asset,
    load_source_export,
    parse_music_track_index,
)
from zelda_suite.extract.asset_loader import AssetLoadError, validate_source_export

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "music-track-index.json"
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

SYNTHETIC_SOURCE = """SongBank_Underworld_Main:
{
    dw $0000, SONG_POINTERS
    base SONG_POINTERS
    dw $0000 ; 0x01
    dw Song_Cave ; 0x02
    dw Song_Cave ; 0x03
    Song_Cave:
    {
        incbin "song.bin"
    }
}
"""


def test_parses_empty_symbolic_and_aliased_track_pointers() -> None:
    index = parse_music_track_index(
        SYNTHETIC_SOURCE,
        table_file_offset=0x1000,
        source_revision="synthetic-revision",
        expected_entry_count=3,
    )
    payload = index.to_dict()

    assert payload["table_file_offset"] == 0x1000
    assert payload["table_end_offset"] == 0x1005
    assert payload["table_size_bytes"] == 6
    assert payload["entry_count"] == 3
    assert [entry["track_index"] for entry in payload["entries"]] == [1, 2, 3]
    assert [entry["pointer_entry_file_offset"] for entry in payload["entries"]] == [
        0x1000, 0x1002, 0x1004
    ]
    assert payload["entries"][0]["is_empty"] is True
    assert payload["entries"][0]["target_label"] is None
    assert payload["entries"][1]["target_label"] == "Song_Cave"
    assert payload["entries"][1]["alias_of_track_index"] is None
    assert payload["entries"][2]["target_label"] == "Song_Cave"
    assert payload["entries"][2]["alias_of_track_index"] == 2


def test_rejects_missing_or_out_of_order_source_index_annotations() -> None:
    malformed = SYNTHETIC_SOURCE.replace("dw Song_Cave ; 0x02", "dw Song_Cave ; 0x04")
    with pytest.raises(ValueError, match="source index"):
        parse_music_track_index(
            malformed,
            table_file_offset=0x1000,
            source_revision="synthetic-revision",
            expected_entry_count=3,
        )


def test_music_index_loader_rejects_bad_alias_and_offset_invariants() -> None:
    payload = parse_music_track_index(
        SYNTHETIC_SOURCE,
        table_file_offset=0x1000,
        source_revision="synthetic-revision",
        expected_entry_count=3,
    ).to_dict()
    malformed_alias = json.loads(json.dumps(payload))
    malformed_alias["entries"][2]["alias_of_track_index"] = None
    with pytest.raises(AssetLoadError, match="alias_of_track_index"):
        validate_source_export(malformed_alias)

    malformed_offset = json.loads(json.dumps(payload))
    malformed_offset["entries"][1]["pointer_entry_file_offset"] += 1
    with pytest.raises(AssetLoadError, match="pointer_entry_file_offset"):
        validate_source_export(malformed_offset)


def test_cli_exports_music_index_and_preserves_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "music.asm"
    output = tmp_path / "music-index.json"
    source.write_text(SYNTHETIC_SOURCE, encoding="utf-8")

    command = [
        "inspect-music-track-index",
        str(source),
        "--table-offset",
        "$1000",
        "--entry-count",
        "3",
        "--source-revision",
        "synthetic-revision",
        "--output",
        str(output),
    ]
    result = CliRunner().invoke(cli, command)

    assert result.exit_code == 0, result.output
    payload = load_source_export(output)
    assert payload["format"] == "zelda-suite-music-track-index"
    assert payload["entry_count"] == 3
    assert "1 empty and 1 aliased entries" in result.output

    refused = CliRunner().invoke(cli, command)
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_music_index_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    parsed = parse_music_track_index(
        source,
        table_file_offset=0x0D8004,
        source_revision=PINNED_REVISION,
    ).to_dict()

    assert payload == parsed
    assert payload["table_end_offset"] == 0x0D8049
    assert payload["entry_count"] == 35
    assert sum(entry["is_empty"] for entry in payload["entries"]) == 15
    assert sum(entry["alias_of_track_index"] is not None for entry in payload["entries"]) == 4
    cave_alias = next(entry for entry in payload["entries"] if entry["track_index"] == 0x18)
    assert cave_alias["pointer_expression"] == "Song12_Cave"
    assert cave_alias["alias_of_track_index"] == 0x12


def test_music_index_is_registered_and_loadable_by_name() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    record = next(asset for asset in registry["assets"] if asset["name"] == "music-track-index")
    assert record["record_count"] == 35
    payload = load_extracted_asset("music-track-index", REGISTRY_PATH)
    assert payload["format"] == "zelda-suite-music-track-index"
    assert payload["entry_count"] == 35
