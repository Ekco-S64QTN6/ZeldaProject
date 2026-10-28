"""Tests for source-only dungeon chest data audits."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.dungeon_chest_data import parse_dungeon_chest_data
from zelda_suite.extract.dungeon_chest_data_audit import (
    DUNGEON_CHEST_DATA_AUDIT_FORMAT,
    audit_dungeon_chest_data,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
SYNTHETIC_SOURCE = """; $001000-$00100B
Dungeon_ChestData:
{
    dl $240032, $0B80A9, $258032, $440041
}
"""


def _write_registry(tmp_path: Path) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    payload = parse_dungeon_chest_data(
        SYNTHETIC_SOURCE,
        source_revision="synthetic-revision",
        expected_entry_count=4,
    ).to_dict()
    filename = "dungeon-chest-data.json"
    (extracted / filename).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry = {
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": [{
            "name": "dungeon-chest-data",
            "file": filename,
            "format": "zelda-suite-dungeon-chest-data",
            "source_revision": "synthetic-revision",
            "record_count": 4,
            "subsystem": "dungeons",
            "description": "Synthetic packed chest records for audit tests.",
        }],
    }
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_audit_summarizes_duplicate_rooms_items_and_big_chests(tmp_path: Path) -> None:
    report = audit_dungeon_chest_data(_write_registry(tmp_path))

    assert report["format"] == DUNGEON_CHEST_DATA_AUDIT_FORMAT
    assert report["summary"] == {
        "entry_count": 4,
        "unique_room_value_count": 3,
        "room_values_with_multiple_entries": 1,
        "big_chest_count": 2,
        "small_chest_count": 2,
        "distinct_item_value_count": 4,
    }
    duplicate = report["duplicate_room_groups"]
    assert len(duplicate) == 1
    assert duplicate[0]["room_value"] == 0x32
    assert duplicate[0]["entry_indexes"] == [0, 2]
    assert duplicate[0]["item_values"] == [0x24, 0x25]
    assert report["item_value_distribution"][0] == {
        "item_value": 0x0B,
        "entry_count": 1,
        "entry_indexes": [1],
    }


def test_registered_audit_pins_the_current_source_inventory() -> None:
    report = audit_dungeon_chest_data(REGISTERED_MANIFEST)

    assert report["summary"] == {
        "entry_count": 168,
        "unique_room_value_count": 106,
        "room_values_with_multiple_entries": 32,
        "big_chest_count": 11,
        "small_chest_count": 157,
        "distinct_item_value_count": 33,
    }
    assert report["duplicate_room_groups"] == [
        group for group in report["room_groups"] if group["entry_count"] > 1
    ]
    assert report == audit_dungeon_chest_data(REGISTERED_MANIFEST)


def test_audit_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "chest-audit.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "audit-dungeon-chest-data",
        "--registry", str(registry),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["room_values_with_multiple_entries"] == 1
    assert "unique_rooms=3" in written.output

    refused = runner.invoke(cli, [
        "audit-dungeon-chest-data",
        "--registry", str(registry),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
