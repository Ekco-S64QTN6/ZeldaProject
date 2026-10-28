"""Tests for cross-checking committed text dictionary source exports."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.text_dictionary_audit import (
    TextDictionaryAuditError,
    audit_text_dictionary_assets,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _fixture_registry(
    tmp_path: Path,
    *,
    pointer_suffix: str = "alpha",
    fragment_suffix: str = "alpha",
    extent_mismatch: bool = False,
) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    pointers = [
        {
            "table_index": 0,
            "entry_file_offset": 0x200,
            "source_line": 1,
            "source_label": "DictionaryPointers",
            "expression": f"DictionaryEntries_{pointer_suffix}",
            "literal_value": None,
            "source_revision": "synthetic-revision",
        },
        {
            "table_index": 1,
            "entry_file_offset": 0x202,
            "source_line": 2,
            "source_label": "DictionaryPointers",
            "expression": "DictionaryEntries_endOfTable",
            "literal_value": None,
            "source_revision": "synthetic-revision",
        },
    ]
    pointer_payload = {
        "format": "zelda-suite-data-table",
        "format_version": 1,
        "source_file": "Bank0E.asm",
        "source_revision": "synthetic-revision",
        "parent_label": None,
        "table_label": "DictionaryPointers",
        "end_label": None,
        "table_file_offset": 0x200,
        "directive": "dw",
        "entry_width": 2,
        "entry_count": len(pointers),
        "entries": pointers,
    }
    payload_bytes = 4 if extent_mismatch else 2
    fragment_payload = {
        "format": "zelda-suite-dictionary-inventory",
        "format_version": 1,
        "source_file": "Bank0E.asm",
        "source_revision": "synthetic-revision",
        "pointer_table_label": "DictionaryPointers",
        "pointer_table_file_offset": 0x200,
        "data_label": "DictionaryEntries",
        "data_file_offset": 0x1000,
        "fragment_count": 2,
        "fragments": [
            {
                "pointer_index": 0,
                "pointer_entry_file_offset": 0x200,
                "pointer_expression": f"DictionaryEntries_{fragment_suffix}",
                "fragment_label": f".{fragment_suffix}",
                "fragment_source_line": 10,
                "fragment_file_offset": 0x1000,
                "next_fragment_file_offset": 0x1002,
                "source_extent_bytes": 2,
                "data_directive": "db",
                "directive_value_count": payload_bytes,
                "directive_width_bytes": 1,
                "declared_payload_bytes": payload_bytes,
                "source_extent_matches_directive": True,
                "is_end_of_table": False,
                "source_revision": "synthetic-revision",
            },
            {
                "pointer_index": 1,
                "pointer_entry_file_offset": 0x202,
                "pointer_expression": "DictionaryEntries_endOfTable",
                "fragment_label": ".endOfTable",
                "fragment_source_line": 11,
                "fragment_file_offset": 0x1002,
                "next_fragment_file_offset": None,
                "source_extent_bytes": None,
                "data_directive": None,
                "directive_value_count": 0,
                "directive_width_bytes": None,
                "declared_payload_bytes": None,
                "source_extent_matches_directive": None,
                "is_end_of_table": True,
                "source_revision": "synthetic-revision",
            },
        ],
    }
    if extent_mismatch:
        fragment_payload["fragments"][0]["declared_payload_bytes"] = 4
        fragment_payload["fragments"][0]["source_extent_matches_directive"] = False

    for filename, payload in [
        ("text-dictionary-pointers.json", pointer_payload),
        ("text-dictionary-fragments.json", fragment_payload),
    ]:
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    registry = {
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": [
            {
                "name": "text-dictionary-pointers",
                "file": "text-dictionary-pointers.json",
                "format": "zelda-suite-data-table",
                "source_revision": "synthetic-revision",
                "record_count": 2,
                "subsystem": "text",
                "description": "Synthetic dictionary pointer fixture.",
            },
            {
                "name": "text-dictionary-fragments",
                "file": "text-dictionary-fragments.json",
                "format": "zelda-suite-dictionary-inventory",
                "source_revision": "synthetic-revision",
                "record_count": 2,
                "subsystem": "text",
                "description": "Synthetic dictionary fragment fixture.",
            },
        ],
    }
    registry_path = extracted / "manifest.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry_path


def test_synthetic_dictionary_exports_cross_reference_cleanly(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    report = audit_text_dictionary_assets(registry)

    assert report["summary"] == {
        "pointer_entry_count": 2,
        "fragment_count": 2,
        "cross_reference_count": 2,
        "cross_reference_mismatch_count": 0,
        "source_extent_mismatch_count": 0,
        "terminal_sentinel_count": 1,
        "error_count": 0,
        "warning_count": 0,
        "finding_count": 0,
    }
    assert all(row["cross_reference_matches"] for row in report["cross_references"])
    assert report["evidence"]["rom_bytes_read"] is False


def test_audit_reports_symbol_to_fragment_mismatch(tmp_path: Path) -> None:
    registry = _fixture_registry(
        tmp_path,
        pointer_suffix="beta",
        fragment_suffix="alpha",
    )
    report = audit_text_dictionary_assets(registry)

    assert report["summary"]["cross_reference_mismatch_count"] == 1
    assert report["summary"]["error_count"] == 2
    assert {finding["code"] for finding in report["findings"]} == {
        "fragment_label_mismatch",
        "fragment_pointer_expression_mismatch",
    }


def test_audit_preserves_source_extent_mismatch_as_warning(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path, extent_mismatch=True)
    report = audit_text_dictionary_assets(registry)

    assert report["summary"]["source_extent_mismatch_count"] == 1
    assert report["summary"]["warning_count"] == 1
    assert report["summary"]["error_count"] == 0
    assert report["findings"][0]["code"] == "source_extent_mismatch"


def test_cli_writes_report_and_fails_on_findings_without_overwriting(
    tmp_path: Path,
) -> None:
    registry = _fixture_registry(tmp_path, extent_mismatch=True)
    output = tmp_path / "dictionary-audit.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "audit-text-dictionary", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["source_extent_mismatch_count"] == 1
    assert "warnings=1" in written.output

    failed = runner.invoke(cli, [
        "audit-text-dictionary", "--registry", str(registry), "--fail-on-findings"
    ])
    assert failed.exit_code == 1
    assert json.loads(failed.output)["summary"]["finding_count"] == 1

    output.write_text("do not replace", encoding="utf-8")
    overwrite = runner.invoke(cli, [
        "audit-text-dictionary", "--registry", str(registry), "--output", str(output)
    ])
    assert overwrite.exit_code != 0
    assert "refusing to overwrite existing output" in overwrite.output
    assert output.read_text(encoding="utf-8") == "do not replace"


def _rewrite_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_audit_rejects_fragment_next_offset_mismatch(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    fragment_path = registry.parent / "text-dictionary-fragments.json"
    payload = json.loads(fragment_path.read_text(encoding="utf-8"))
    payload["fragments"][0]["next_fragment_file_offset"] = 0x1003
    payload["fragments"][0]["source_extent_bytes"] = 3
    _rewrite_json(fragment_path, payload)

    with pytest.raises(
        TextDictionaryAuditError,
        match=r"fragments\[0\]\.next_fragment_file_offset does not match the next fragment",
    ):
        audit_text_dictionary_assets(registry)


def test_audit_rejects_fragment_extent_mismatch(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    fragment_path = registry.parent / "text-dictionary-fragments.json"
    payload = json.loads(fragment_path.read_text(encoding="utf-8"))
    payload["fragments"][0]["source_extent_bytes"] = 3
    _rewrite_json(fragment_path, payload)

    with pytest.raises(
        TextDictionaryAuditError,
        match=r"fragments\[0\]\.source_extent_bytes is inconsistent with fragment offsets",
    ):
        audit_text_dictionary_assets(registry)


def test_audit_pins_committed_dictionary_cross_reference_baseline() -> None:
    report = audit_text_dictionary_assets(REGISTERED_MANIFEST)

    assert report["source_file"] == "Bank0E.asm"
    assert report["source_revision"] == PINNED_SOURCE_REVISION
    assert report["summary"] == {
        "pointer_entry_count": 98,
        "fragment_count": 98,
        "cross_reference_count": 98,
        "cross_reference_mismatch_count": 0,
        "source_extent_mismatch_count": 1,
        "terminal_sentinel_count": 1,
        "error_count": 0,
        "warning_count": 1,
        "finding_count": 1,
    }
    assert report["findings"] == [{
        "code": "source_extent_mismatch",
        "severity": "warning",
        "message": (
            "Source extent is 2 byte(s), while the declared directive values describe "
            "6 byte(s); neither value was changed by this audit."
        ),
        "pointer_index": 96,
        "pointer_expression": "DictionaryEntries_You",
        "fragment_label": ".You",
    }]
    assert report["cross_references"][96]["cross_reference_matches"] is True
    assert report["cross_references"][96]["source_extent_bytes"] == 2
    assert report["cross_references"][96]["declared_payload_bytes"] == 6
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "fragment_bytes_read": False,
        "pointer_values_resolved": False,
        "offsets_verified": False,
    }
    assert report == audit_text_dictionary_assets(REGISTERED_MANIFEST)
