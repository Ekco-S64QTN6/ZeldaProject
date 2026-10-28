"""Tests for joining SpritePrep and SpriteActive3 source dispatch inventories."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.sprite_prep_dispatch_audit import (
    SPRITE_PREP_DISPATCH_AUDIT_FORMAT,
    audit_sprite_prep_dispatch,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_registered_cross_reference_covers_all_active3_sprite_ids() -> None:
    report = audit_sprite_prep_dispatch(REGISTERED_MANIFEST)

    assert report["format"] == SPRITE_PREP_DISPATCH_AUDIT_FORMAT
    assert report["format_version"] == 1
    assert report["source_revision"] == PINNED_REVISION
    assert report["prep_routine_label"] == "SpritePrep_Main"
    assert report["prep_table_file_offset"] is None
    assert report["summary"] == {
        "prep_entry_count": 243,
        "active3_entry_count": 68,
        "shared_sprite_id_count": 68,
        "prep_only_sprite_id_count": 175,
        "active3_only_sprite_id_count": 0,
    }
    assert [row["sprite_type_id"] for row in report["rows"]] == list(range(0x79, 0xBD))
    assert report["prep_only_sprite_ids"] == [
        *range(0x79),
        *range(0xBD, 0xF3),
    ]
    assert report["active3_only_sprite_ids"] == []
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "table_offsets_verified": False,
        "handler_address_annotations_verified": False,
        "same_runtime_handler_semantics_asserted": False,
    }
    assert report == audit_sprite_prep_dispatch(REGISTERED_MANIFEST)


def test_cross_reference_cli_writes_report_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "sprite-prep-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-sprite-prep-dispatch",
        "--registry", str(REGISTERED_MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["shared_sprite_id_count"] == 68
    assert "shared_ids=68" in written.output

    refused = runner.invoke(cli, [
        "audit-sprite-prep-dispatch",
        "--registry", str(REGISTERED_MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
