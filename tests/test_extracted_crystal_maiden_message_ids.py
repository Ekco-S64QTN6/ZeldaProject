"""Tests for the source-only Crystal Maiden message-ID table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "crystal-maiden-message-ids.json"
TEXT_INDEX_PATH = ROOT / "data" / "extracted" / "text-message-index.json"
SOURCE_PATH = (
    ROOT
    / "reference"
    / "AsarUSALTTPDisassembly"
    / "Sprites"
    / "sprite_crystal_maiden.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
TABLE_LABEL = "CrystalMaiden_ShowMessage_message_ids"
TABLE_FILE_OFFSET = 0x0F4EBC
EXPECTED_EXPRESSIONS = [
    "$0133", "$0132", "$0137", "$0134", "$0136", "$0132", "$0135", "$0138", "$013c"
]
EXPECTED_VALUES = [0x0133, 0x0132, 0x0137, 0x0134, 0x0136, 0x0132, 0x0135, 0x0138, 0x013C]
EXPECTED_MESSAGE_LABELS = {
    0x0132: "Message_0132",
    0x0133: "Message_0133",
    0x0134: "Message_0134",
    0x0135: "Message_0135",
    0x0136: "Message_0136",
    0x0137: "Message_0137",
    0x0138: "Message_0138",
    0x013C: "Message_013C",
}


def test_committed_crystal_maiden_message_ids_have_traceable_baseline() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["format"] == "zelda-suite-data-table"
    assert payload["format_version"] == 1
    assert payload["source_file"] == "sprite_crystal_maiden.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["parent_label"] is None
    assert payload["table_label"] == TABLE_LABEL
    assert payload["end_label"] is None
    assert payload["table_file_offset"] == TABLE_FILE_OFFSET
    assert payload["directive"] == "dw"
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 9
    assert [entry["table_index"] for entry in payload["entries"]] == list(range(9))
    assert [entry["entry_file_offset"] for entry in payload["entries"]] == [
        TABLE_FILE_OFFSET + 2 * index for index in range(9)
    ]
    assert [entry["expression"] for entry in payload["entries"]] == EXPECTED_EXPRESSIONS
    assert [entry["literal_value"] for entry in payload["entries"]] == EXPECTED_VALUES
    assert [entry["source_line"] for entry in payload["entries"]] == [310] * 8 + [311]
    assert all(
        entry["source_label"] == TABLE_LABEL
        and entry["source_revision"] == PINNED_REVISION
        for entry in payload["entries"]
    )


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_crystal_maiden_message_ids_match_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    source = SOURCE_PATH.read_text(encoding="utf-8")
    entries = parse_data_table(
        source,
        TABLE_LABEL,
        TABLE_FILE_OFFSET,
        directive="dw",
        source_revision=PINNED_REVISION,
        expected_entry_count=9,
    )

    assert payload["entries"] == [entry.to_dict() for entry in entries]
    assert "; $0F4EBC-$0F4ECD DATA" in source
    assert "LDA.w .message_ids+0, Y" in source
    assert "LDA.w .message_ids+1, Y" in source


def test_crystal_maiden_message_ids_cross_reference_registered_text_index() -> None:
    payload = load_source_export(EXPORT_PATH)
    text_index = load_source_export(TEXT_INDEX_PATH)
    labels_by_id = {
        message["message_id"]: message["message_label"]
        for message in text_index["messages"]
    }
    distinct_ids = {entry["literal_value"] for entry in payload["entries"]}

    assert len(distinct_ids) == 8
    assert {message_id: labels_by_id.get(message_id) for message_id in distinct_ids} == (
        EXPECTED_MESSAGE_LABELS
    )
