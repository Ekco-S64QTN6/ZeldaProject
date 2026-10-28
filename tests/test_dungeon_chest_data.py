"""Unit tests for the packed dungeon chest-data parser and CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.dungeon_chest_data import (
    DungeonChestDataParseError,
    parse_dungeon_chest_data,
)

SYNTHETIC_SOURCE = """; $001000-$00100B
Dungeon_ChestData:
{
    dl $240032, $0B80A9, $258032, $440041
}
"""


def test_parser_unpacks_only_source_documented_fields() -> None:
    table = parse_dungeon_chest_data(
        SYNTHETIC_SOURCE,
        source_revision="synthetic-revision",
        expected_entry_count=4,
    )
    payload = table.to_dict()

    assert validate_source_export(payload) == payload
    assert payload["source_range_annotation"] == "$001000-$00100B"
    assert payload["source_annotated_start_offset"] == 0x1000
    assert payload["source_annotated_end_offset"] == 0x100B
    assert payload["table_size_bytes"] == 12
    assert payload["entry_width_bytes"] == 3
    assert payload["entry_count"] == 4
    assert [entry["candidate_entry_offset"] for entry in payload["entries"]] == [
        0x1000, 0x1003, 0x1006, 0x1009
    ]
    assert [
        (entry["item_value"], entry["room_value"], entry["is_big_chest"])
        for entry in payload["entries"]
    ] == [
        (0x24, 0x32, False),
        (0x0B, 0xA9, True),
        (0x25, 0x32, True),
        (0x44, 0x41, False),
    ]
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "source_range_offsets_verified": False,
        "item_value_names_resolved": False,
        "room_values_verified_against_rom": False,
    }


def test_loader_rejects_inconsistent_packed_chest_fields() -> None:
    payload = parse_dungeon_chest_data(
        SYNTHETIC_SOURCE,
        source_revision="synthetic-revision",
        expected_entry_count=4,
    ).to_dict()
    payload["entries"][0]["room_value"] = 0x33

    with pytest.raises(AssetLoadError, match="room_value does not match"):
        validate_source_export(payload)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SYNTHETIC_SOURCE.replace("$001000-$00100B", "$001000-$00100A"), "source range covers 11 bytes"),
        (SYNTHETIC_SOURCE.replace("$240032", "UnresolvedItem"), "six-digit 24-bit literal"),
        (SYNTHETIC_SOURCE.replace("Dungeon_ChestData:", "OtherTable:"), "expected exactly one"),
    ],
)
def test_parser_fails_closed_on_bad_source(source: str, expected: str) -> None:
    with pytest.raises(DungeonChestDataParseError, match=expected):
        parse_dungeon_chest_data(
            source,
            source_revision="synthetic-revision",
            expected_entry_count=4,
        )


def test_inspect_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "Bank01.asm"
    source_path.write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    output = tmp_path / "dungeon-chest-data.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "inspect-dungeon-chest-data",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--entry-count", "4",
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["entry_count"] == 4
    assert saved["entries"][1]["is_big_chest"] is True
    assert "source-range offsets remain unverified" in written.output

    refused = runner.invoke(cli, [
        "inspect-dungeon-chest-data",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--entry-count", "4",
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
