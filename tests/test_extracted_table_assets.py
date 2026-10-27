"""Tests for committed, source-traceable extracted table assets."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "falling-prize-item-values.json"
ANCILLA_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Ancilla" / "ancilla_init.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_committed_falling_prize_export_is_valid_and_source_traceable() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "ancilla_init.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] == "Pool_AddPendantOrCrystal"
    assert payload["table_label"] == ".item_values"
    assert payload["end_label"] == ".fall_height"
    assert payload["table_file_offset"] == 0x048B90
    assert payload["directive"] == "db"
    assert payload["entry_width"] == 1
    assert payload["entry_count"] == 7
    assert [entry["literal_value"] for entry in payload["entries"]] == [
        0x10, 0x37, 0x39, 0x38, 0x26, 0x0F, 0x20
    ]


@pytest.mark.skipif(
    not ANCILLA_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_export_matches_parser_output_for_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = ANCILLA_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        ".item_values",
        0x048B90,
        directive="db",
        parent_label="Pool_AddPendantOrCrystal",
        end_label=".fall_height",
        source_revision=PINNED_REVISION,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert payload["entry_count"] == len(entries)


def test_export_file_is_deterministic_json() -> None:
    raw = EXPORT_PATH.read_bytes()
    payload = json.loads(raw)
    assert raw.endswith(b"\n")
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert rendered == raw.decode("utf-8")
