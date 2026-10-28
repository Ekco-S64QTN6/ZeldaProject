"""Regression baseline for the full source-commented SpritePrep_Main dispatch table."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_sprite_prep_dispatch_table

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "extracted" / "sprite-prep-dispatch.json"
SOURCE_PATH = (
    ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites" / "sprite_prep.asm"
)
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def test_committed_sprite_prep_export_has_243_sequential_ids() -> None:
    payload = load_source_export(EXPORT_PATH)

    assert payload["source_file"] == "sprite_prep.asm"
    assert payload["source_revision"] == PINNED_REVISION
    assert payload["routine_label"] == "SpritePrep_Main"
    assert payload["routine_source_range_annotation"] == "$03064D-$030840 JUMP LOCATION"
    assert payload["table_file_offset"] is None
    assert payload["table_offset_established"] is False
    assert payload["sprite_type_id_start"] == 0
    assert payload["sprite_type_id_end"] == 0xF2
    assert payload["entry_count"] == 243
    assert [entry["table_index"] for entry in payload["entries"]] == list(range(243))
    assert [entry["sprite_type_id"] for entry in payload["entries"]] == list(range(243))
    assert [entry["source_comment_sprite_type_id"] for entry in payload["entries"]] == list(range(243))
    assert payload["entries"][0]["handler_expression"] == "SpritePrep_Raven"
    assert payload["entries"][3]["handler_expression"] == "$0000"
    assert payload["entries"][3]["handler_label"] is None
    assert payload["entries"][-1]["handler_expression"] == "SpritePrep_MedallionTableTrampoline"
    assert payload["entries"][26]["source_comment_continuations"] == ["sprites"]
    assert sum(bool(entry["source_comment_continuations"]) for entry in payload["entries"]) == 22
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "table_offset_established": False,
        "handler_address_annotations_verified": False,
        "runtime_behavior_verified": False,
    }


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_sprite_prep_export_matches_pinned_source_parser() -> None:
    payload = load_source_export(EXPORT_PATH)
    table = parse_sprite_prep_dispatch_table(
        SOURCE_PATH.read_text(encoding="utf-8"),
        source_revision=PINNED_REVISION,
        source_file="sprite_prep.asm",
        expected_entry_count=243,
    )
    parsed = table.to_dict()

    assert payload == parsed
