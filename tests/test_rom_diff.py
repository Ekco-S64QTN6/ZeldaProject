"""Tests for deterministic byte-buffer diffing."""
from __future__ import annotations

import json

import pytest

from zelda_suite.diff import compare_bytes


def test_identical_buffers_have_no_regions() -> None:
    result = compare_bytes(b"\x00\x01\x02", b"\x00\x01\x02")

    assert result.regions == ()
    assert result.changed_byte_count == 0
    assert result.original_size == 3
    assert result.modified_size == 3
    assert result.net_size_delta == 0


def test_adjacent_changes_are_grouped_and_unchanged_bytes_split_regions() -> None:
    original = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06])
    modified = bytes([0x00, 0xAA, 0xBB, 0x03, 0x44, 0x05, 0x66])

    result = compare_bytes(original, modified)

    assert len(result.regions) == 3
    first, second, third = result.regions
    assert (first.start_offset, first.end_offset_exclusive) == (1, 3)
    assert first.original_bytes == b"\x01\x02"
    assert first.modified_bytes == b"\xAA\xBB"
    assert first.changed_byte_count == 2
    assert (second.start_offset, second.end_offset_exclusive) == (4, 5)
    assert second.original_bytes == b"\x04"
    assert second.modified_bytes == b"\x44"
    assert (third.start_offset, third.end_offset_exclusive) == (6, 7)
    assert result.changed_byte_count == 4


def test_appended_bytes_form_a_region_with_absolute_offsets() -> None:
    result = compare_bytes(b"abc", b"abc\xDE\xFF", base_offset=0x8000)

    assert result.base_offset == 0x8000
    assert result.original_size == 3
    assert result.modified_size == 5
    assert result.net_size_delta == 2
    assert result.changed_byte_count == 2
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.start_offset == 0x8003
    assert region.end_offset_exclusive == 0x8005
    assert region.original_bytes == b""
    assert region.modified_bytes == b"\xDE\xFF"


def test_truncated_bytes_form_a_deletion_region() -> None:
    result = compare_bytes(b"abc\xDE\xFF", b"abc", base_offset=0x100)

    assert result.net_size_delta == -2
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.start_offset == 0x103
    assert region.end_offset_exclusive == 0x105
    assert region.original_bytes == b"\xDE\xFF"
    assert region.modified_bytes == b""
    assert region.changed_byte_count == 2


def test_replacement_and_appended_bytes_can_share_one_region() -> None:
    result = compare_bytes(b"abc", b"aXYz")

    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.start_offset == 1
    assert region.end_offset_exclusive == 4
    assert region.original_bytes == b"bc"
    assert region.modified_bytes == b"XYz"
    assert region.changed_byte_count == 3


def test_bytearray_and_memoryview_inputs_are_not_mutated() -> None:
    original = bytearray(b"original")
    modified = bytearray(b"modifYed")
    original_before = original[:]
    modified_before = modified[:]

    result = compare_bytes(memoryview(original), modified)

    assert result.changed_byte_count > 0
    assert original == original_before
    assert modified == modified_before


def test_json_output_is_stable_uppercase_and_newline_terminated() -> None:
    result = compare_bytes(b"\x01\x02\x03", b"\x01\xAB\x03")
    first = result.to_json()
    second = result.to_json()

    assert first == second
    assert first.endswith("\n")
    assert "\r\n" not in first
    payload = json.loads(first)
    assert payload["format"] == "zelda-suite-byte-diff"
    assert payload["format_version"] == 1
    assert payload["changed_byte_count"] == 1
    assert payload["regions"][0]["original_hex"] == "02"
    assert payload["regions"][0]["modified_hex"] == "AB"
    assert payload["regions"][0]["start_offset"] == 1
    assert payload["regions"][0]["end_offset_exclusive"] == 2


@pytest.mark.parametrize("offset", [-1, -100])
def test_negative_base_offset_is_rejected(offset: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compare_bytes(b"a", b"b", base_offset=offset)


@pytest.mark.parametrize("offset", [True, 1.5, "12", None])
def test_non_integer_base_offset_is_rejected(offset: object) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        compare_bytes(b"a", b"b", base_offset=offset)  # type: ignore[arg-type]


@pytest.mark.parametrize("buffer", [None, "not bytes", [1, 2, 3], 123])
def test_non_bytes_input_is_rejected(buffer: object) -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        compare_bytes(buffer, b"valid")  # type: ignore[arg-type]


def test_empty_buffers_are_equal() -> None:
    result = compare_bytes(b"", b"")

    assert result.regions == ()
    assert result.changed_byte_count == 0
    assert result.net_size_delta == 0
