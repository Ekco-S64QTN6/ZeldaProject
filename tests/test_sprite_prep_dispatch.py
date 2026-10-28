"""Unit tests for the inline SpritePrep dispatch parser and CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.sprite_prep_dispatch import (
    SpritePrepDispatchParseError,
    parse_sprite_prep_dispatch_table,
)

SYNTHETIC_SOURCE = """; $0000-$0010 JUMP LOCATION
SpritePrep_Main:
{
    LDA.w $0E20, X
    JSL.l UseImplicitRegIndexedLocalJumpTable
    dw SpritePrep_Raven ; 0x00 - $1234 Raven
                                      ; continuation detail
    dw $0000 ; 0x01 - $0000 Null sprite
}
"""


def test_parser_preserves_ids_handlers_comments_and_unestablished_offset() -> None:
    table = parse_sprite_prep_dispatch_table(
        SYNTHETIC_SOURCE,
        source_revision="synthetic-revision",
        expected_entry_count=2,
    )
    payload = table.to_dict()
    assert validate_source_export(payload) == payload

    assert payload["format"] == "zelda-suite-sprite-prep-dispatch"
    assert payload["routine_label"] == "SpritePrep_Main"
    assert payload["routine_source_range_annotation"] == "$0000-$0010 JUMP LOCATION"
    assert payload["table_file_offset"] is None
    assert payload["table_offset_established"] is False
    assert [entry["sprite_type_id"] for entry in payload["entries"]] == [0, 1]
    assert payload["entries"][0]["handler_expression"] == "SpritePrep_Raven"
    assert payload["entries"][0]["handler_label"] == "SpritePrep_Raven"
    assert payload["entries"][0]["source_handler_address_annotation"] == "$1234"
    assert payload["entries"][0]["source_comment_continuations"] == ["continuation detail"]
    assert payload["entries"][1]["handler_expression"] == "$0000"
    assert payload["entries"][1]["handler_label"] is None
    assert payload["evidence"]["handler_address_annotations_verified"] is False


def test_loader_rejects_a_claimed_inline_table_offset() -> None:
    payload = parse_sprite_prep_dispatch_table(
        SYNTHETIC_SOURCE,
        source_revision="synthetic-revision",
        expected_entry_count=2,
    ).to_dict()
    payload["table_file_offset"] = 0x03064D

    with pytest.raises(AssetLoadError, match="table_file_offset must be null"):
        validate_source_export(payload)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SYNTHETIC_SOURCE.replace("0x01 - $0000", "0x03 - $0000"), "expected 0x1"),
        (SYNTHETIC_SOURCE.replace("0x01 - $0000 Null sprite", "0x01 Null sprite"), "malformed sprite prep comment"),
        (SYNTHETIC_SOURCE.replace("; $0000-$0010 JUMP LOCATION", "; routine comment"), "source range annotation"),
        (SYNTHETIC_SOURCE.replace("UseImplicitRegIndexedLocalJumpTable", "SomeOtherTable"), "expected one UseImplicit"),
    ],
)
def test_parser_fails_closed_on_bad_source(source: str, expected: str) -> None:
    with pytest.raises(SpritePrepDispatchParseError, match=expected):
        parse_sprite_prep_dispatch_table(
            source,
            source_revision="synthetic-revision",
            expected_entry_count=2,
        )


def test_inspect_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "sprite_prep.asm"
    source_path.write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    output = tmp_path / "sprite-prep.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "inspect-sprite-prep-dispatch",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--entry-count", "2",
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["entry_count"] == 2
    assert payload["table_file_offset"] is None
    assert "inline table offset remains unestablished" in written.output

    refused = runner.invoke(cli, [
        "inspect-sprite-prep-dispatch",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--entry-count", "2",
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
