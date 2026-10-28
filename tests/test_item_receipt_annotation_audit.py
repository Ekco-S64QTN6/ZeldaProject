"""Tests for source-comment IDs on the dense receive-item graphics table."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.item_receipt_annotation_audit import (
    ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT,
    audit_item_receipt_annotations,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "extracted" / "manifest.json"


def test_registered_audit_preserves_comment_ids_separately_from_table_indexes() -> None:
    report = audit_item_receipt_annotations(MANIFEST)
    assert report["format"] == ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT
    assert report["format_version"] == 1
    assert report["entry_count"] == 76
    assert report["summary"] == {
        "table_entry_count": 76,
        "parsed_source_comment_count": 76,
        "source_comment_parse_failure_count": 0,
        "source_comment_ids_matching_table_index_count": 64,
        "source_comment_ids_mismatched_count": 12,
        "missing_source_comment_id_count": 1,
        "duplicate_source_comment_id_count": 0,
        "first_mismatched_table_index": 64,
        "last_mismatched_table_index": 75,
    }
    assert report["missing_source_comment_ids"] == [0x40]
    assert report["duplicate_source_comment_ids"] == []
    assert report["mismatched_entries"] == list(range(0x40, 0x4C))

    before_gap = report["entries"][0x3F]
    assert before_gap["source_comment_item_id"] == 0x3F
    assert before_gap["source_comment_label"] == "SANC HC"
    assert before_gap["source_comment_id_matches_table_index"] is True
    assert before_gap["annotation_id_delta"] == 0

    after_gap = report["entries"][0x40]
    assert after_gap["table_index"] == 0x40
    assert after_gap["source_comment_item_id"] == 0x41
    assert after_gap["source_comment_label"] == "100 RUPEES"
    assert after_gap["source_comment_id_matches_table_index"] is False
    assert after_gap["annotation_id_delta"] == 1

    last = report["entries"][0x4B]
    assert last["table_index"] == 0x4B
    assert last["source_comment_item_id"] == 0x4C
    assert last["source_comment_label"] == "BOOTS"
    assert last["annotation_id_delta"] == 1
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "canonical_item_ids_resolved": False,
        "semantic_item_names_resolved": False,
        "source_comments_corrected": False,
    }
    assert report == audit_item_receipt_annotations(MANIFEST)


def test_audit_cli_writes_report_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "item-receipt-annotation-audit.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-item-receipt-annotations",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["source_comment_ids_mismatched_count"] == 12
    assert "comment_id_mismatches=12" in written.output

    refused = runner.invoke(cli, [
        "audit-item-receipt-annotations",
        "--registry", str(MANIFEST),
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
