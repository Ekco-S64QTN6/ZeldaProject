"""Tests for source-only audit of the committed message-index diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.text_message_index import MessageSourceBlock, parse_text_message_index
from zelda_suite.extract.text_message_index_audit import audit_text_message_index

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

SYNTHETIC_SOURCE = """Message_Data:
{
    ; $001000
    Message_0000:
    db $7F
    ; $001005
    Message_0001:
    db $01, $7F
    ; $00100
    Message_0002:
    db $01, $02, $7F
}
"""


def _write_registry(tmp_path: Path, *, block_end_offset: int = 0x1005) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    payload = parse_text_message_index(
        [
            MessageSourceBlock(
                source_file="BankFixture.asm",
                block_label="Message_Data",
                block_start_offset=0x1000,
                block_end_offset=block_end_offset,
                source_text=SYNTHETIC_SOURCE,
            )
        ],
        source_revision="synthetic-revision",
    ).to_dict()
    filename = "text-message-index.json"
    (extracted / filename).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry = {
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": [
            {
                "name": "text-message-index",
                "file": filename,
                "format": "zelda-suite-text-message-index",
                "source_revision": "synthetic-revision",
                "record_count": 3,
                "subsystem": "text",
                "description": "Synthetic message index for audit tests.",
            }
        ],
    }
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_audit_distinguishes_bad_offset_annotations_from_valid_mismatches(
    tmp_path: Path,
) -> None:
    report = audit_text_message_index(_write_registry(tmp_path))

    assert report["summary"] == {
        "source_block_count": 1,
        "message_count": 3,
        "offset_annotation_count": 3,
        "missing_offset_annotation_count": 0,
        "offset_mismatch_count": 2,
        "invalid_offset_annotation_count": 1,
        "block_size_mismatch_count": 0,
        "warning_count": 2,
        "finding_count": 2,
    }
    assert [finding["code"] for finding in report["findings"]] == [
        "offset_annotation_mismatch",
        "invalid_offset_annotation",
    ]
    assert report["findings"][0]["message_id"] == 1
    assert report["findings"][1]["message_id"] == 2
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "encoded_message_bytes_read": False,
        "decoded_text_produced": False,
        "offsets_verified": False,
    }


def test_audit_reports_block_size_mismatch_without_changing_source_facts(
    tmp_path: Path,
) -> None:
    report = audit_text_message_index(_write_registry(tmp_path, block_end_offset=0x1006))

    assert report["summary"]["block_size_mismatch_count"] == 1
    assert report["summary"]["finding_count"] == 3
    block_finding = report["findings"][-1]
    assert block_finding["code"] == "block_size_mismatch"
    assert block_finding["block_size_bytes"] == 7
    assert block_finding["declared_byte_count_total"] == 6
    assert block_finding["difference_bytes"] == -1


def test_cli_writes_report_supports_fail_on_findings_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    registry = _write_registry(tmp_path, block_end_offset=0x1006)
    output = tmp_path / "message-audit.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "audit-text-message-index", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["finding_count"] == 3
    assert "invalid_annotations=1" in written.output
    assert "block_size_mismatches=1" in written.output

    failed = runner.invoke(cli, [
        "audit-text-message-index", "--registry", str(registry), "--fail-on-findings"
    ])
    assert failed.exit_code == 1
    assert json.loads(failed.output)["summary"]["finding_count"] == 3

    output.write_text("keep existing", encoding="utf-8")
    refused = runner.invoke(cli, [
        "audit-text-message-index", "--registry", str(registry), "--output", str(output)
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert output.read_text(encoding="utf-8") == "keep existing"


def test_audit_pins_committed_text_message_index_baseline() -> None:
    report = audit_text_message_index(REGISTERED_MANIFEST)

    assert report["source_files"] == ["Bank1C.asm", "Bank0E.asm"]
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["summary"] == {
        "source_block_count": 2,
        "message_count": 397,
        "offset_annotation_count": 359,
        "missing_offset_annotation_count": 38,
        "offset_mismatch_count": 6,
        "invalid_offset_annotation_count": 3,
        "block_size_mismatch_count": 1,
        "warning_count": 7,
        "finding_count": 7,
    }
    assert [
        finding["message_id"]
        for finding in report["findings"]
        if finding["code"] in {"offset_annotation_mismatch", "invalid_offset_annotation"}
    ] == [21, 122, 202, 305, 307, 310]
    assert [
        finding["message_id"]
        for finding in report["findings"]
        if finding["code"] == "invalid_offset_annotation"
    ] == [21, 305, 310]
    extra = next(block for block in report["source_blocks"] if block["block_label"] == "Message_DataExtra")
    assert extra["declared_bytes_match_block_size"] is False
    assert extra["difference_bytes"] == -1
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "encoded_message_bytes_read": False,
        "decoded_text_produced": False,
        "offsets_verified": False,
    }
    assert report == audit_text_message_index(REGISTERED_MANIFEST)
