"""Tests for read-only dungeon-room long-pointer verification."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.dungeon_room_pointer_verification import (
    DUNGEON_POINTER_ENTRY_WIDTH,
    DUNGEON_POINTER_TABLE_OFFSET,
    verify_dungeon_room_pointers,
)
from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    lorom_cpu_address,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
POINTER_ASSET_PATH = ROOT / "data" / "extracted" / "dungeon-room-object-pointers.json"
PAYLOAD_ASSET_PATHS = (
    ROOT / "data" / "extracted" / "dungeon-room-payloads-bank03.json",
    ROOT / "data" / "extracted" / "dungeon-room-payload-inventory.json",
    ROOT / "data" / "extracted" / "dungeon-room-payloads-bank1f.json",
)


def _target_offsets() -> dict[str, dict[str, object]]:
    offsets: dict[str, dict[str, object]] = {}
    for path in PAYLOAD_ASSET_PATHS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for declaration in payload["declarations"]:
            offsets[declaration["label"]] = {
                "offset": declaration["source_file_offset_start"],
                "size": declaration["declared_size_bytes"],
            }
    return offsets


def _write_synthetic_rom(tmp_path: Path) -> Path:
    pointers = json.loads(POINTER_ASSET_PATH.read_text(encoding="utf-8"))
    targets = _target_offsets()
    rom = bytearray(EXPECTED_US_ROM_SIZE)
    for pointer in pointers["entries"]:
        target = targets[pointer["target_label"]]
        target_offset = int(target["offset"])
        if pointer["target_addend"] is not None:
            target_offset += int(pointer["target_addend"])
        pointer_value = lorom_cpu_address(target_offset)
        offset = pointer["pointer_entry_file_offset"]
        rom[offset:offset + DUNGEON_POINTER_ENTRY_WIDTH] = pointer_value.to_bytes(
            DUNGEON_POINTER_ENTRY_WIDTH,
            "little",
        )

    path = tmp_path / "synthetic-dungeon-pointer-rom.smc"
    path.write_bytes(rom)
    return path


def test_verifier_matches_all_source_annotated_long_pointers_and_preserves_caveats(
    tmp_path: Path,
) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    original = rom_path.read_bytes()

    report = verify_dungeon_room_pointers(rom_path, REGISTRY_PATH)

    assert report["format"] == "zelda-suite-dungeon-room-pointer-verification"
    assert report["format_version"] == 1
    assert report["rom"]["provenance_verified"] is False
    assert report["source_revision"] == "347c23f9fc019c72d32da537c9cb235f468d021d"
    assert report["pointer_table"] == {
        "label": "RoomData_ObjectDataPointers",
        "file_offset": DUNGEON_POINTER_TABLE_OFFSET,
        "entry_width_bytes": DUNGEON_POINTER_ENTRY_WIDTH,
        "entry_count": 320,
        "unique_target_label_count": 263,
        "empty_target_entry_count": 39,
        "source_payload_label_count": 266,
        "checked_comparisons": 320,
        "mismatch_count": 0,
    }
    assert len(report["entries"]) == 320
    assert len(report["targets"]) == 266
    assert report["mismatches"] == []
    assert report["rom_modified"] is False
    assert report["payload_bytes_verified"] is False
    assert report["playable_room_set_resolved"] is False
    orphan = next(
        target for target in report["targets"]
        if target["label"] == "RoomDataTiles_Orphan"
    )
    assert orphan["pointer_indices"] == []
    assert rom_path.read_bytes() == original


def test_verifier_reports_pointer_byte_mismatches(tmp_path: Path) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    rom = bytearray(rom_path.read_bytes())
    rom[DUNGEON_POINTER_TABLE_OFFSET + 3] ^= 0x01
    rom_path.write_bytes(rom)

    report = verify_dungeon_room_pointers(rom_path, REGISTRY_PATH)

    assert report["pointer_table"]["mismatch_count"] == 1
    assert report["mismatches"][0]["table_index"] == 1
    assert report["mismatches"][0]["target_label"] == "RoomDataTiles_0001"
    assert report["mismatches"][0]["reason"] == (
        "ROM pointer bytes do not match the source-commented target offset"
    )
    assert report["entries"][1]["status"] == "fail"


def test_dungeon_room_pointer_cli_emits_json_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    output = tmp_path / "dungeon-room-pointer-verification.json"
    runner = CliRunner()
    arguments = [
        "verify-dungeon-room-pointers",
        str(rom_path),
        "--registry",
        str(REGISTRY_PATH),
    ]

    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    assert '"mismatch_count": 0' in result.output
    assert '"playable_room_set_resolved": false' in result.output

    written = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert '"mismatch_count": 0' in output.read_text(encoding="utf-8")
    assert "checked=320, mismatches=0" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
