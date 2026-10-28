"""Tests for source-only cross-reference of music pointers and payload declarations."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.music_asset_audit import audit_music_assets
from zelda_suite.extract.music_track_index import parse_music_track_index

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

SYNTHETIC_SOURCE = """SongBank_Underworld_Main:
{
    dw $0000, SONG_POINTERS
    base SONG_POINTERS
    dw $0000 ; 0x01
    dw Song_Cave ; 0x02
    dw Song_Cave ; 0x03
    dw Song_Absent ; 0x04
}
"""


def _write_registry(tmp_path: Path) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    index_payload = parse_music_track_index(
        SYNTHETIC_SOURCE,
        table_file_offset=0x200,
        source_revision="synthetic-revision",
        expected_entry_count=4,
    ).to_dict()
    declarations = [
        {
            "source_file": "Bank1B.asm",
            "source_revision": "synthetic-revision",
            "label": "Song_Cave",
            "source_line": 10,
            "incbin_path": "bin/music/cave.bin",
            "declared_size_bytes": 3,
            "source_file_offset_start": 0x3000,
            "source_file_offset_end": 0x3002,
            "computed_file_offset_end": 0x3002,
            "source_range_size_matches": True,
        },
        {
            "source_file": "Bank1B.asm",
            "source_revision": "synthetic-revision",
            "label": "Song_MissingSize",
            "source_line": 20,
            "incbin_path": "bin/music/missing-size.bin",
            "declared_size_bytes": None,
            "source_file_offset_start": 0x3003,
            "source_file_offset_end": 0x3004,
            "computed_file_offset_end": None,
            "source_range_size_matches": None,
        },
    ]
    inventory_payload = {
        "format": "zelda-suite-incbin-inventory",
        "format_version": 1,
        "source_file": "Bank1B.asm",
        "source_revision": "synthetic-revision",
        "declaration_count": len(declarations),
        "declarations": declarations,
    }
    assets = [
        {
            "name": "music-track-index",
            "file": "music-track-index.json",
            "format": "zelda-suite-music-track-index",
            "source_revision": "synthetic-revision",
            "record_count": 4,
            "subsystem": "audio",
            "description": "Synthetic music pointer index.",
        },
        {
            "name": "music-payload-inventory",
            "file": "music-payload-inventory.json",
            "format": "zelda-suite-incbin-inventory",
            "source_revision": "synthetic-revision",
            "record_count": len(declarations),
            "subsystem": "audio",
            "description": "Synthetic music payload declaration inventory.",
        },
    ]
    for filename, payload in [
        ("music-track-index.json", index_payload),
        ("music-payload-inventory.json", inventory_payload),
    ]:
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps({
            "format": "zelda-suite-asset-registry",
            "format_version": 1,
            "assets": assets,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_synthetic_music_cross_reference_reports_missing_target_and_size(
    tmp_path: Path,
) -> None:
    report = audit_music_assets(_write_registry(tmp_path))

    assert report["summary"] == {
        "track_entry_count": 4,
        "empty_pointer_count": 1,
        "nonempty_pointer_count": 3,
        "alias_entry_count": 1,
        "unique_target_label_count": 2,
        "payload_declaration_count": 2,
        "matched_payload_label_count": 1,
        "missing_payload_target_count": 1,
        "missing_payload_reference_count": 1,
        "unreferenced_payload_count": 1,
        "payload_without_size_count": 1,
        "payload_source_range_mismatch_count": 0,
        "duplicate_payload_label_count": 0,
        "error_count": 0,
        "warning_count": 3,
        "finding_count": 3,
    }
    assert report["missing_payload_targets"] == ["Song_Absent"]
    assert report["unreferenced_payload_labels"] == ["Song_MissingSize"]
    assert [finding["code"] for finding in report["findings"]] == [
        "missing_payload_declaration",
        "unreferenced_payload_declaration",
        "payload_size_missing",
    ]
    assert report["cross_references"][0]["payload_declaration_found"] is None
    assert report["cross_references"][1]["payload_declaration_found"] is True
    assert report["cross_references"][2]["alias_of_track_index"] == 2
    assert report["cross_references"][3]["payload_declaration_found"] is False
    assert report["evidence"]["audio_payload_bytes_read"] is False


def test_cli_writes_report_fails_on_findings_and_preserves_existing_output(
    tmp_path: Path,
) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "music-audit.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "audit-music-assets", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["missing_payload_target_count"] == 1
    assert "missing_targets=1" in written.output
    assert "payloads_missing_size=1" in written.output

    failed = runner.invoke(cli, [
        "audit-music-assets", "--registry", str(registry), "--fail-on-findings"
    ])
    assert failed.exit_code == 1
    assert json.loads(failed.output)["summary"]["finding_count"] == 3

    output.write_text("keep existing", encoding="utf-8")
    refused = runner.invoke(cli, [
        "audit-music-assets", "--registry", str(registry), "--output", str(output)
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert output.read_text(encoding="utf-8") == "keep existing"


def test_audit_pins_committed_music_cross_reference_baseline() -> None:
    report = audit_music_assets(REGISTERED_MANIFEST)

    assert report["source_file"] == "Bank1B.asm"
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["summary"] == {
        "track_entry_count": 35,
        "empty_pointer_count": 15,
        "nonempty_pointer_count": 20,
        "alias_entry_count": 4,
        "unique_target_label_count": 16,
        "payload_declaration_count": 15,
        "matched_payload_label_count": 15,
        "missing_payload_target_count": 1,
        "missing_payload_reference_count": 1,
        "unreferenced_payload_count": 0,
        "payload_without_size_count": 3,
        "payload_source_range_mismatch_count": 0,
        "duplicate_payload_label_count": 0,
        "error_count": 0,
        "warning_count": 4,
        "finding_count": 4,
    }
    assert report["missing_payload_targets"] == ["Song0B_FairyTheme"]
    assert report["unreferenced_payload_labels"] == []
    assert {item["label"] for item in report["payloads_missing_size"]} == {
        "Song1D_AgahnimEscapes",
        "Song1E_MeetingGanon",
        "Song1F_KingOfThieves",
    }
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "audio_payload_bytes_read": False,
        "pointer_values_resolved": False,
        "offsets_verified": False,
    }
    assert report == audit_music_assets(REGISTERED_MANIFEST)
