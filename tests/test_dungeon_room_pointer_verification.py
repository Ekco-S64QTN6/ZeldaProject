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
    """Build synthetic payload positions from source order and declared sizes."""
    offsets: dict[str, dict[str, object]] = {}
    for path in PAYLOAD_ASSET_PATHS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        declarations = payload["declarations"]
        layout_offset = declarations[0]["source_file_offset_start"]
        for declaration in declarations:
            offsets[declaration["label"]] = {
                "offset": layout_offset,
                "size": declaration["declared_size_bytes"],
            }
            layout_offset += declaration["declared_size_bytes"]
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


def test_verifier_matches_sequential_layout_and_reports_conflicting_comments(
    tmp_path: Path,
) -> None:
    rom_path = _write_synthetic_rom(tmp_path)
    original = rom_path.read_bytes()

    report = verify_dungeon_room_pointers(rom_path, REGISTRY_PATH)

    assert report["format"] == "zelda-suite-dungeon-room-pointer-verification"
    assert report["format_version"] == 2
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
        "source_comment_offset_mismatch_count": 6,
    }
    assert len(report["entries"]) == 320
    assert len(report["targets"]) == 266
    assert report["mismatches"] == []
    assert report["source_layout_method"] == (
        "first source-commented offset per inventory plus sequential declared payload sizes"
    )
    assert report["source_comment_offsets_rewritten"] is False
    assert len(report["source_offset_findings"]) == 6
    findings_by_label = {
        finding["label"]: finding for finding in report["source_offset_findings"]
    }
    assert {
        label: (
            findings_by_label[label]["source_comment_file_offset"],
            findings_by_label[label]["computed_layout_file_offset_start"],
            findings_by_label[label]["offset_delta_bytes"],
        )
        for label in findings_by_label
    } == {
        "RoomDataTiles_00E1": (330153, 328046, 2107),
        "RoomDataTiles_0011": (331545, 330655, 890),
        "RoomDataTiles_0050": (333473, 331823, 1650),
        "RoomDataTiles_00F9": (344053, 339957, 4096),
        "RoomDataTiles_011C": (130899, 128086, 2813),
        "RoomDataTiles_0015": (1040753, 1041524, -771),
    }
    assert all(
        finding["code"] == "source_comment_offset_disagrees_with_sequential_layout"
        for finding in findings_by_label.values()
    )
    room_0011 = next(
        target for target in report["targets"] if target["label"] == "RoomDataTiles_0011"
    )
    assert room_0011["source_comment_file_offset"] == 331545
    assert room_0011["computed_layout_file_offset_start"] == 330655
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
        "ROM pointer bytes do not match the sequential payload-layout candidate"
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
    assert "checked=320, mismatches=0, source_offset_findings=6" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
