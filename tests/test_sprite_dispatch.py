"""Tests for source-only SpriteActive3 handler dispatch metadata."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    SpriteDispatchParseError,
    load_extracted_asset,
    load_source_export,
    parse_sprite_dispatch_table,
    validate_source_export,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1E.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "sprite-active3-dispatch.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

SYNTHETIC_SOURCE = """SpriteActive3_Table:
{
    dw Sprite_First ; 0x79 - $C000 First variant
    dw Sprite_First ; 0x7A - $C100 Second variant
}
"""


def _parse_pinned_source():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    return parse_sprite_dispatch_table(
        source,
        table_file_offset=0x0F0B33,
        table_end_offset=0x0F0BBA,
        source_revision=PINNED_REVISION,
        source_file="Bank1E.asm",
    )


def test_pinned_dispatch_has_68_entries_and_keeps_aliases_separate() -> None:
    if not SOURCE_PATH.is_file():
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")

    table = _parse_pinned_source()
    payload = table.to_dict()
    entries = payload["entries"]

    assert payload["format"] == "zelda-suite-sprite-dispatch"
    assert payload["table_size_bytes"] == 0x88
    assert payload["entry_count"] == 68
    assert payload["sprite_type_id_start"] == 0x79
    assert payload["sprite_type_id_end"] == 0xBC
    assert entries[0]["table_index"] == 0
    assert entries[0]["sprite_type_id"] == 0x79
    assert entries[0]["pointer_entry_file_offset"] == 0x0F0B33
    assert entries[-1]["table_index"] == 67
    assert entries[-1]["sprite_type_id"] == 0xBC
    assert entries[-1]["pointer_entry_file_offset"] == 0x0F0B33 + 67 * 2

    aliases = [
        entry
        for entry in entries
        if entry["handler_label"] == "Sprite_GuruguruBar"
    ]
    assert [entry["sprite_type_id"] for entry in aliases] == [0x7E, 0x7F]
    assert aliases[0]["table_index"] != aliases[1]["table_index"]

    laser_eyes = [
        entry
        for entry in entries
        if entry["handler_label"] == "Sprite_LaserEye"
    ]
    assert [entry["sprite_type_id"] for entry in laser_eyes] == [0x95, 0x96, 0x97, 0x98]
    assert all(entry["source_revision"] == PINNED_REVISION for entry in entries)


def test_parser_rejects_comment_id_sequence_and_table_range_mismatches() -> None:
    bad_id = SYNTHETIC_SOURCE.replace("0x7A", "0x7B")
    with pytest.raises(SpriteDispatchParseError, match="annotated with sprite ID"):
        parse_sprite_dispatch_table(
            bad_id,
            table_file_offset=0x1000,
            table_end_offset=0x1003,
            source_revision="synthetic",
            expected_entry_count=2,
        )

    with pytest.raises(ValueError, match="require 4"):
        parse_sprite_dispatch_table(
            SYNTHETIC_SOURCE,
            table_file_offset=0x1000,
            table_end_offset=0x1004,
            source_revision="synthetic",
            expected_entry_count=2,
        )


def test_cli_emits_valid_sprite_dispatch_json(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.asm"
    output = tmp_path / "sprite-dispatch.json"
    source.write_text(SYNTHETIC_SOURCE, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "inspect-sprite-dispatch",
            str(source),
            "--table-offset",
            "$1000",
            "--table-end-offset",
            "$1003",
            "--entry-count",
            "2",
            "--sprite-id-start",
            "$79",
            "--source-revision",
            "synthetic-revision",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output

    payload = load_source_export(output)
    assert payload["entry_count"] == 2
    assert payload["entries"][0]["handler_label"] == "Sprite_First"
    assert payload["entries"][0]["source_description"] == "First variant"
    assert "2 sprite IDs share aliased handlers" in result.output

    malformed = json.loads(output.read_text(encoding="utf-8"))
    malformed["entries"][1]["pointer_entry_file_offset"] += 1
    with pytest.raises(ValueError, match="pointer_entry_file_offset"):
        validate_source_export(malformed)

    registered = load_extracted_asset(
        "sprite-active3-dispatch",
        ROOT / "data" / "extracted" / "manifest.json",
    )
    assert registered["entry_count"] == 68


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_dispatch_export_matches_pinned_parser() -> None:
    payload = load_source_export(EXPORT_PATH)
    parsed = _parse_pinned_source().to_dict()
    assert payload == parsed
