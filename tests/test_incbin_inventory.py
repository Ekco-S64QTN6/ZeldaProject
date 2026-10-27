"""Tests for source-level Asar incbin inventory parsing."""
from __future__ import annotations

import pytest

from zelda_suite.extract.incbin_inventory import (
    IncbinInventoryError,
    parse_incbin_inventory,
)


def test_parses_explicit_file_offset_range_and_size() -> None:
    source = """; $058000-$058003 DATA
;org $0B8000
Screen00_High:
{
    incbin "bin/ow/screen00-h.bin" ; Size: 0x0004
}
"""
    records = parse_incbin_inventory(
        source,
        source_file="Bank0B.asm",
        source_revision="pinned-sha",
    )

    assert len(records) == 1
    record = records[0]
    assert record.label == "Screen00_High"
    assert record.source_file == "Bank0B.asm"
    assert record.source_revision == "pinned-sha"
    assert record.source_line == 5
    assert record.incbin_path == "bin/ow/screen00-h.bin"
    assert record.declared_size_bytes == 4
    assert record.source_file_offset_start == 0x058000
    assert record.source_file_offset_end == 0x058003
    assert record.computed_file_offset_end == 0x058003
    assert record.source_range_size_matches is True


def test_computes_end_from_single_start_comment_and_size() -> None:
    source = """; $050000
RoomDataTiles_0104:
incbin "bin/rooms/room0104.bin" ; Size: 0x0047
"""
    record = parse_incbin_inventory(source)[0]

    assert record.source_file_offset_start == 0x050000
    assert record.source_file_offset_end is None
    assert record.declared_size_bytes == 0x47
    assert record.computed_file_offset_end == 0x050046
    assert record.source_range_size_matches is None


def test_reports_range_size_mismatch_without_rewriting_source_facts() -> None:
    source = """; $1000-$1003 DATA
Asset:
    incbin "asset.bin" ; Size: 0x0005
"""
    record = parse_incbin_inventory(source)[0]

    assert record.source_file_offset_start == 0x1000
    assert record.source_file_offset_end == 0x1003
    assert record.declared_size_bytes == 5
    assert record.computed_file_offset_end == 0x1004
    assert record.source_range_size_matches is False


def test_missing_size_and_offset_remain_unresolved() -> None:
    source = """SomeAsset:
{
    incbin "opaque.bin"
}
"""
    record = parse_incbin_inventory(source)[0]

    assert record.label == "SomeAsset"
    assert record.declared_size_bytes is None
    assert record.source_file_offset_start is None
    assert record.source_file_offset_end is None
    assert record.computed_file_offset_end is None
    assert record.source_range_size_matches is None


def test_records_are_json_friendly() -> None:
    record = parse_incbin_inventory(
        """; $2000-$2001 DATA
Blob:
    incbin "blob.bin" ; Size: 2
"""
    )[0]

    serialized = record.to_dict()
    assert serialized["incbin_path"] == "blob.bin"
    assert serialized["source_file_offset_start"] == 0x2000
    assert serialized["source_range_size_matches"] is True


def test_rejects_incbin_without_source_label() -> None:
    with pytest.raises(IncbinInventoryError, match="no preceding label"):
        parse_incbin_inventory('incbin "orphan.bin" ; Size: 3\n')


def test_rejects_reversed_source_range() -> None:
    with pytest.raises(IncbinInventoryError, match="ends before it starts"):
        parse_incbin_inventory(
            """; $2001-$2000 DATA
Blob:
    incbin "blob.bin" ; Size: 2
"""
        )


def test_multiple_declarations_keep_source_order_and_offsets() -> None:
    source = """; $3000-$3001 DATA
First:
    incbin "first.bin" ; Size: 2
; $3100-$3102 DATA
Second:
    incbin "second.bin" ; Size: 3
"""
    records = parse_incbin_inventory(source)

    assert [record.label for record in records] == ["First", "Second"]
    assert [record.source_file_offset_start for record in records] == [0x3000, 0x3100]
    assert [record.source_range_size_matches for record in records] == [True, True]



def test_zero_length_payload_has_no_computed_last_byte() -> None:
    record = parse_incbin_inventory(
        """; $5000-$5000 DATA
EmptyPayload:
    incbin "empty.bin" ; Size: 0
"""
    )[0]

    assert record.declared_size_bytes == 0
    assert record.computed_file_offset_end is None
    assert record.source_range_size_matches is False


def test_rejects_malformed_size_annotation() -> None:
    with pytest.raises(IncbinInventoryError, match="invalid incbin size"):
        parse_incbin_inventory(
            """Blob:
    incbin "blob.bin" ; Size: 0xZZ
"""
        )


def test_rejects_negative_size_annotation() -> None:
    with pytest.raises(IncbinInventoryError, match="non-negative"):
        parse_incbin_inventory(
            """Blob:
    incbin "blob.bin" ; Size: -1
"""
        )
