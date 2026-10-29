"""Tests for source-consumer classification of overworld hidden-item value bytes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.overworld_hidden_item_value_semantics import (
    OverworldHiddenItemValueSemanticsError,
    audit_overworld_hidden_item_value_semantics,
    classify_overworld_hidden_item_value_byte,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
SCHEMA_PATH = ROOT / "docs" / "schemas" / "overworld-hidden-item-value-semantics.schema.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

REPLACEMENT_WORDS = [
    {
        "table_index": 0,
        "selector_byte_offset": 0,
        "value": 0x0DCC,
        "comment": "Hole",
    },
    {
        "table_index": 1,
        "selector_byte_offset": 2,
        "value": 0x0212,
        "comment": "Portal",
    },
    {
        "table_index": 2,
        "selector_byte_offset": 4,
        "value": 0xFFFF,
        "comment": "Garbage",
    },
    {
        "table_index": 3,
        "selector_byte_offset": 6,
        "value": 0x0DB4,
        "comment": "Bomb hole",
    },
]


def test_zero_value_uses_empty_branch_and_is_not_an_item_id() -> None:
    result = classify_overworld_hidden_item_value_byte(0, REPLACEMENT_WORDS)
    assert result["consumer_class"] == "zero_value"
    assert result["consumer_operation"] == "branches to .emptySecret and skips TSB $0B9C"
    assert result["canonical_item_id_resolved"] is False
    assert result["selector_byte_offset"] is None


def test_low_values_are_secret_state_masks_not_canonical_item_ids() -> None:
    result = classify_overworld_hidden_item_value_byte(0x05, REPLACEMENT_WORDS)
    assert result["consumer_class"] == "ordinary_secret_mask"
    assert result["consumer_operation"] == "TSB $0B9C combines this value with secret-state flags"
    assert result["canonical_item_id_resolved"] is False
    assert result["replacement_table_index"] is None


@pytest.mark.parametrize(
    ("value", "selector_offset", "table_index", "word", "comment", "special_case"),
    [
        (0x80, 0, 0, 0x0DCC, "Hole", None),
        (0x82, 2, 1, 0x0212, "Portal", None),
        (0x84, 4, 2, 0xFFFF, "Garbage",
         "$84 branches to .notBurrow and skips the generic overlay-activation block"),
        (0x86, 6, 3, 0x0DB4, "Bomb hole", None),
    ],
)
def test_extended_values_use_low_nibble_as_byte_offset(
    value: int,
    selector_offset: int,
    table_index: int,
    word: int,
    comment: str,
    special_case: str | None,
) -> None:
    result = classify_overworld_hidden_item_value_byte(value, REPLACEMENT_WORDS)
    assert result["consumer_class"] == "extended_secret_selector"
    assert result["selector_byte_offset"] == selector_offset
    assert result["replacement_table_index"] == table_index
    assert result["replacement_word_value"] == word
    assert result["replacement_word_comment"] == comment
    assert result["special_case"] == special_case
    assert result["canonical_item_id_resolved"] is False


def test_unmapped_selector_offset_is_preserved_without_guessing() -> None:
    result = classify_overworld_hidden_item_value_byte(0x81, REPLACEMENT_WORDS)
    assert result["consumer_class"] == "extended_secret_selector"
    assert result["selector_byte_offset"] == 1
    assert result["replacement_table_index"] is None
    assert result["replacement_word_value"] is None
    assert result["replacement_word_comment"] is None


@pytest.mark.parametrize("value", [-1, 256, True, 1.5, "128"])
def test_value_classifier_rejects_non_byte_inputs(value: object) -> None:
    with pytest.raises(OverworldHiddenItemValueSemanticsError):
        classify_overworld_hidden_item_value_byte(value, REPLACEMENT_WORDS)  # type: ignore[arg-type]


def test_schema_pins_replacement_table_source_lines() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$defs"]["source_semantics"]["properties"][
        "replacement_table_comment_lines"
    ]["const"] == [2813, 2814, 2815, 2816]


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_pinned_source_value_semantics_baseline() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    report = audit_overworld_hidden_item_value_semantics(source)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$defs"]["source_semantics"]["properties"][
        "replacement_table_comment_lines"
    ]["const"] == report["source_semantics"]["replacement_table_comment_lines"]

    assert report["format"] == "zelda-suite-overworld-hidden-item-value-semantics"
    assert report["format_version"] == 1
    assert report["source_revision"] == PINNED_REVISION
    assert report["summary"] == {
        "record_count": 351,
        "zero_value_count": 0,
        "ordinary_secret_mask_count": 325,
        "extended_secret_selector_count": 26,
        "extended_selector_unmapped_count": 0,
        "extended_value_distribution": [
            {
                "value_byte": 0x80,
                "value_hex": "$80",
                "record_count": 4,
                "selector_byte_offset": 0,
                "replacement_table_index": 0,
                "replacement_word_comment": "Hole",
            },
            {
                "value_byte": 0x82,
                "value_hex": "$82",
                "record_count": 6,
                "selector_byte_offset": 2,
                "replacement_table_index": 1,
                "replacement_word_comment": "Portal",
            },
            {
                "value_byte": 0x84,
                "value_hex": "$84",
                "record_count": 8,
                "selector_byte_offset": 4,
                "replacement_table_index": 2,
                "replacement_word_comment": "Garbage",
            },
            {
                "value_byte": 0x86,
                "value_hex": "$86",
                "record_count": 8,
                "selector_byte_offset": 6,
                "replacement_table_index": 3,
                "replacement_word_comment": "Bomb hole",
            },
        ],
    }
    assert report["source_semantics"]["sentinel_compare_line"] == 2847
    assert report["source_semantics"]["extended_value_threshold_line"] == 2852
    assert report["source_semantics"]["secret_mask_update_line"] == 2853
    assert report["source_semantics"]["extended_special_case_line"] == 2863
    assert report["source_semantics"]["selector_byte_offset_line"] == 2878
    assert report["source_semantics"]["replacement_table_load_line"] == 2879
    assert report["replacement_words"] == [
        {
            "table_index": 0,
            "source_line": 2813,
            "file_offset": 0x0DC89C,
            "selector_byte_offset": 0,
            "expression": "dw $0DCC",
            "value": 0x0DCC,
            "comment": "Hole",
        },
        {
            "table_index": 1,
            "source_line": 2814,
            "file_offset": 0x0DC89E,
            "selector_byte_offset": 2,
            "expression": "dw $0212",
            "value": 0x0212,
            "comment": "Portal",
        },
        {
            "table_index": 2,
            "source_line": 2815,
            "file_offset": 0x0DC8A0,
            "selector_byte_offset": 4,
            "expression": "dw $FFFF",
            "value": 0xFFFF,
            "comment": "Garbage",
        },
        {
            "table_index": 3,
            "source_line": 2816,
            "file_offset": 0x0DC8A2,
            "selector_byte_offset": 6,
            "expression": "dw $0DB4",
            "value": 0x0DB4,
            "comment": "Bomb hole",
        },
    ]
    assert all(record["canonical_item_id_resolved"] is False for record in report["records"])
    assert report["evidence"] == {
        "source_only": True,
        "source_consumer_patterns_checked": True,
        "rom_bytes_read": False,
        "room_payload_bytes_read": False,
        "canonical_item_ids_resolved": False,
        "value_byte_semantics_verified_in_rom": False,
    }


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_audit_fails_closed_when_the_consumer_changes(tmp_path: Path) -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    altered = source.replace("TSB.w $0B9C", "TSB.w $0B9D", 1)
    assert altered != source
    with pytest.raises(OverworldHiddenItemValueSemanticsError, match="did not match"):
        audit_overworld_hidden_item_value_semantics(altered)


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_cli_writes_report_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "hidden-item-value-semantics.json"
    args = [
        "audit-overworld-hidden-item-value-semantics",
        "--output",
        str(output),
    ]
    runner = CliRunner()
    written = runner.invoke(cli, args)
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["record_count"] == 351
    assert saved["summary"]["extended_secret_selector_count"] == 26
    assert "ordinary_masks=325" in written.output
    assert "extended=26" in written.output

    refused = runner.invoke(cli, args)
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
    assert json.loads(output.read_text(encoding="utf-8")) == saved
