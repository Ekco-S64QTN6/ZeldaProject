"""Regression checks for committed falling-prize parallel tables."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import load_source_export, parse_data_table

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
SOURCE_PATH = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Ancilla" / "ancilla_init.asm"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"

TABLES = [
    {
        "file": "falling-prize-item-values.json",
        "label": ".item_values",
        "end_label": ".fall_height",
        "offset": 0x048B90,
        "directive": "db",
        "values": [0x10, 0x37, 0x39, 0x38, 0x26, 0x0F, 0x20],
    },
    {
        "file": "falling-prize-fall-heights.json",
        "label": ".fall_height",
        "end_label": ".y_offsets",
        "offset": 0x048B97,
        "directive": "db",
        "values": [0x60, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80],
    },
    {
        "file": "falling-prize-y-offsets.json",
        "label": ".y_offsets",
        "end_label": ".x_offsets",
        "offset": 0x048B9E,
        "directive": "dw",
        "values": [0x0048, 0x0078, 0x0078, 0x0078, 0x0078, 0x0068, 0x0078],
    },
    {
        "file": "falling-prize-x-offsets.json",
        "label": ".x_offsets",
        "end_label": ".delay_timers",
        "offset": 0x048BAC,
        "directive": "dw",
        "values": [0x0078, 0x0078, 0x0078, 0x0078, 0x0078, 0x0080, 0x0078],
    },
    {
        "file": "falling-prize-delay-timers.json",
        "label": ".delay_timers",
        "end_label": None,
        "offset": 0x048BBA,
        "directive": "db",
        "values": [0x40, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00],
    },
]


def test_committed_parallel_tables_are_valid_and_share_seven_indices() -> None:
    exports = [load_source_export(DATA_DIR / item["file"]) for item in TABLES]

    assert [payload["table_label"] for payload in exports] == [
        item["label"] for item in TABLES
    ]
    for payload, specification in zip(exports, TABLES, strict=True):
        assert payload["source_revision"] == PINNED_REVISION
        assert payload["parent_label"] == "Pool_AddPendantOrCrystal"
        assert payload["end_label"] == specification["end_label"]
        assert payload["table_file_offset"] == specification["offset"]
        assert payload["directive"] == specification["directive"]
        assert payload["entry_width"] == (1 if specification["directive"] == "db" else 2)
        assert payload["entry_count"] == 7
        assert [entry["literal_value"] for entry in payload["entries"]] == specification["values"]
        assert [entry["table_index"] for entry in payload["entries"]] == list(range(7))
        assert [entry["entry_file_offset"] for entry in payload["entries"]] == [
            specification["offset"] + index * payload["entry_width"]
            for index in range(7)
        ]

    # All four adjacent arrays use the same lookup index, despite having
    # different widths and values.
    assert {payload["entry_count"] for payload in exports} == {7}


@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_parallel_tables_match_the_pinned_source() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")

    for specification in TABLES:
        payload = load_source_export(DATA_DIR / specification["file"])
        parsed = parse_data_table(
            source,
            specification["label"],
            specification["offset"],
            directive=specification["directive"],
            parent_label="Pool_AddPendantOrCrystal",
            end_label=specification["end_label"],
            source_revision=PINNED_REVISION,
        )
        assert payload["entries"] == [entry.to_dict() for entry in parsed]

@pytest.mark.skipif(
    not SOURCE_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_falling_prize_consumer_uses_aligned_parallel_table_indexes() -> None:
    """Keep the source-table consumer relationship covered by a pinned-source test."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    label = "AddPendantOrCrystal:\n{"
    first_routine_marker = source.index(label)
    routine_start = source.index(label, first_routine_marker + len(label))
    routine_end = source.index("\n}\n", routine_start)
    routine = source[routine_start:routine_end]

    # Byte tables use the original selector index loaded from $02D8.
    assert "LDY.w $02D8" in routine
    for table in ("item_values", "fall_height", "delay_timers"):
        assert f"LDA.w Pool_AddPendantOrCrystal_{table}, Y" in routine

    # The word tables use the same index scaled by two; Y offsets occur in
    # both medallion and ordinary-item paths, while X offsets are ordinary-only.
    assert "TYA : ASL : TAY" in routine
    assert routine.count("LDA.w Pool_AddPendantOrCrystal_y_offsets, Y") == 2
    assert routine.count("LDA.w Pool_AddPendantOrCrystal_x_offsets, Y") == 1
