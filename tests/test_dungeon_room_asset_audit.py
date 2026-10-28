"""Tests for source-only dungeon room pointer/payload cross-reference auditing."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.dungeon_room_asset_audit import audit_dungeon_room_assets

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _write_registry(
    tmp_path: Path,
    *,
    include_missing_target: bool = False,
    duplicate_target: bool = False,
    orphan_missing_size: bool = False,
) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    targets = ["RoomDataTiles_A", "RoomDataTiles_Empty"]
    if include_missing_target:
        targets.append("RoomDataTiles_Missing")
    pointer_entries = [
        {
            "table_index": index,
            "pointer_entry_file_offset": 0x0F8000 + index * 3,
            "source_line": index + 1,
            "pointer_expression": label,
            "target_label": label,
            "target_addend": None,
            "is_empty_target": label == "RoomDataTiles_Empty",
            "source_revision": "synthetic-revision",
        }
        for index, label in enumerate(targets)
    ]
    pointer_payload = {
        "format": "zelda-suite-pointer-table",
        "format_version": 1,
        "source_file": "Bank1F.asm",
        "source_revision": "synthetic-revision",
        "table_label": "RoomData_ObjectDataPointers",
        "table_file_offset": 0x0F8000,
        "entry_width": 3,
        "entry_count": len(pointer_entries),
        "entries": pointer_entries,
    }

    def declaration(
        label: str,
        source_file: str,
        path: str,
        line: int,
        start: int,
        size: int | None,
    ) -> dict[str, object]:
        return {
            "source_file": source_file,
            "source_revision": "synthetic-revision",
            "label": label,
            "source_line": line,
            "incbin_path": path,
            "declared_size_bytes": size,
            "source_file_offset_start": start,
            "source_file_offset_end": None,
            "computed_file_offset_end": start + size - 1 if size is not None else None,
            "source_range_size_matches": None,
        }

    by_asset: dict[str, list[dict[str, object]]] = {
        "dungeon-room-payloads-bank03": [
            declaration("RoomDataTiles_A", "Bank03.asm", "bin/rooms/a.bin", 10, 0x3000, 4)
        ],
        "dungeon-room-payload-inventory": [
            declaration(
                "RoomDataTiles_Orphan",
                "Bank0A.asm",
                "bin/rooms/orphan.bin",
                20,
                0x4000,
                None if orphan_missing_size else 2,
            )
        ],
        "dungeon-room-payloads-bank1f": [
            declaration("RoomDataTiles_Empty", "Bank1F.asm", "bin/rooms/empty.bin", 30, 0x5000, 1)
        ],
    }
    if duplicate_target:
        by_asset["dungeon-room-payload-inventory"].append(
            declaration("RoomDataTiles_A", "Bank0A.asm", "bin/rooms/a-duplicate.bin", 21, 0x4002, 4)
        )

    exports = [
        (
            "dungeon-room-object-pointers",
            "dungeon-room-object-pointers.json",
            "zelda-suite-pointer-table",
            pointer_payload,
            len(pointer_entries),
            "Bank1F.asm",
        )
    ]
    for asset_name, declarations in by_asset.items():
        source_file = {
            "dungeon-room-payloads-bank03": "Bank03.asm",
            "dungeon-room-payload-inventory": "Bank0A.asm",
            "dungeon-room-payloads-bank1f": "Bank1F.asm",
        }[asset_name]
        payload = {
            "format": "zelda-suite-incbin-inventory",
            "format_version": 1,
            "source_file": source_file,
            "source_revision": "synthetic-revision",
            "declaration_count": len(declarations),
            "declarations": declarations,
        }
        exports.append((
            asset_name,
            asset_name + ".json",
            "zelda-suite-incbin-inventory",
            payload,
            len(declarations),
            source_file,
        ))

    registry_assets = []
    for asset_name, filename, format_name, payload, count, source_file in exports:
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        registry_assets.append({
            "name": asset_name,
            "file": filename,
            "format": format_name,
            "source_revision": "synthetic-revision",
            "record_count": count,
            "subsystem": "dungeons",
            "description": f"Synthetic audit fixture for {source_file}.",
        })

    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps({
            "format": "zelda-suite-asset-registry",
            "format_version": 1,
            "assets": registry_assets,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_synthetic_room_pointer_targets_join_to_unique_payload_labels(
    tmp_path: Path,
) -> None:
    report = audit_dungeon_room_assets(_write_registry(tmp_path))

    assert report["summary"] == {
        "pointer_entry_count": 2,
        "empty_pointer_count": 1,
        "unique_pointer_target_label_count": 2,
        "payload_declaration_count": 3,
        "unique_payload_label_count": 3,
        "matched_target_label_count": 2,
        "missing_payload_target_count": 0,
        "missing_payload_reference_count": 0,
        "unreferenced_payload_count": 1,
        "duplicate_payload_label_count": 0,
        "payload_start_offset_missing_count": 0,
        "payload_without_size_count": 0,
        "payload_source_range_mismatch_count": 0,
        "error_count": 0,
        "warning_count": 1,
        "finding_count": 1,
    }
    assert report["unreferenced_payload_labels"] == ["RoomDataTiles_Orphan"]
    assert [row["payload_declaration_found"] for row in report["cross_references"]] == [
        True, True
    ]
    assert report["evidence"]["rom_bytes_read"] is False


def test_audit_reports_missing_target_and_unknown_payload_size_through_cli(
    tmp_path: Path,
) -> None:
    registry = _write_registry(
        tmp_path,
        include_missing_target=True,
        orphan_missing_size=True,
    )
    report = audit_dungeon_room_assets(registry)
    assert report["missing_payload_targets"] == ["RoomDataTiles_Missing"]
    assert report["summary"]["missing_payload_reference_count"] == 1
    assert report["summary"]["unreferenced_payload_count"] == 1
    assert report["summary"]["payload_without_size_count"] == 1
    assert report["summary"]["error_count"] == 1
    assert report["summary"]["warning_count"] == 2

    output = tmp_path / "dungeon-room-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-dungeon-room-assets", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["missing_payload_targets"] == ["RoomDataTiles_Missing"]
    assert "missing_targets=1" in written.output
    assert "unreferenced_payloads=1" in written.output

    failed = runner.invoke(cli, [
        "audit-dungeon-room-assets", "--registry", str(registry), "--fail-on-findings"
    ])
    assert failed.exit_code == 1
    assert json.loads(failed.output)["summary"]["finding_count"] == 3

    output.write_text("keep existing", encoding="utf-8")
    refused = runner.invoke(cli, [
        "audit-dungeon-room-assets", "--registry", str(registry), "--output", str(output)
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert output.read_text(encoding="utf-8") == "keep existing"


def test_audit_flags_duplicate_payload_labels_as_ambiguous(tmp_path: Path) -> None:
    report = audit_dungeon_room_assets(
        _write_registry(tmp_path, duplicate_target=True)
    )

    assert report["summary"]["duplicate_payload_label_count"] == 1
    assert report["missing_payload_targets"] == ["RoomDataTiles_A"]
    assert report["summary"]["matched_target_label_count"] == 1
    assert report["summary"]["error_count"] == 2
    assert {finding["code"] for finding in report["findings"]} == {
        "duplicate_payload_label",
        "missing_payload_declaration",
        "unreferenced_payload_declaration",
    }


def test_audit_pins_committed_dungeon_room_cross_reference_baseline() -> None:
    report = audit_dungeon_room_assets(REGISTERED_MANIFEST)

    assert report["pointer_source_file"] == "Bank1F.asm"
    assert report["pointer_table_label"] == "RoomData_ObjectDataPointers"
    assert report["pointer_table_file_offset"] == 0x0F8000
    assert report["pointer_entry_width_bytes"] == 3
    assert report["payload_source_files"] == ["Bank03.asm", "Bank0A.asm", "Bank1F.asm"]
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["summary"] == {
        "pointer_entry_count": 320,
        "empty_pointer_count": 39,
        "unique_pointer_target_label_count": 263,
        "payload_declaration_count": 266,
        "unique_payload_label_count": 266,
        "matched_target_label_count": 263,
        "missing_payload_target_count": 0,
        "missing_payload_reference_count": 0,
        "unreferenced_payload_count": 3,
        "duplicate_payload_label_count": 0,
        "payload_start_offset_missing_count": 0,
        "payload_without_size_count": 0,
        "payload_source_range_mismatch_count": 0,
        "error_count": 0,
        "warning_count": 3,
        "finding_count": 3,
    }
    assert report["missing_payload_targets"] == []
    assert report["unreferenced_payload_labels"] == [
        "RoomDataTiles_Orphan",
        "RoomDataTiles_Zarby89",
        "RoomDataTiles_Zarby90",
    ]
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "room_payload_bytes_read": False,
        "pointer_values_resolved": False,
        "offsets_verified": False,
        "payload_bytes_verified": False,
    }
    assert report == audit_dungeon_room_assets(REGISTERED_MANIFEST)
