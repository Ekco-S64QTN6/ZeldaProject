"""Deterministic byte-buffer differences for audit-friendly ROM workflows.

The functions in this module accept already-loaded byte buffers. They neither
open files nor write ROMs, patches, or other binary artifacts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_FORMAT_NAME = "zelda-suite-byte-diff"
_FORMAT_VERSION = 1
_BytesLike = bytes | bytearray | memoryview


@dataclass(frozen=True, slots=True)
class DiffRegion:
    """A contiguous span where the original and modified buffers differ.

    Offsets use a half-open range: `[start_offset, end_offset_exclusive)`.
    Original and modified bytes can have different lengths for append/truncate
    operations. Their hexadecimal representations are uppercase and omit
    separators so they remain stable in JSON and Git diffs.
    """

    start_offset: int
    end_offset_exclusive: int
    original_bytes: bytes
    modified_bytes: bytes
    changed_byte_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return an audit-friendly JSON-serializable region."""
        return {
            "start_offset": self.start_offset,
            "end_offset_exclusive": self.end_offset_exclusive,
            "original_hex": self.original_bytes.hex().upper(),
            "modified_hex": self.modified_bytes.hex().upper(),
            "original_length": len(self.original_bytes),
            "modified_length": len(self.modified_bytes),
            "changed_byte_count": self.changed_byte_count,
        }


@dataclass(frozen=True, slots=True)
class ROMByteDiff:
    """A deterministic diff summary between two byte buffers."""

    base_offset: int
    original_size: int
    modified_size: int
    regions: tuple[DiffRegion, ...]

    @property
    def net_size_delta(self) -> int:
        """Number of bytes added (positive) or removed (negative)."""
        return self.modified_size - self.original_size

    @property
    def changed_byte_count(self) -> int:
        """Count changed positions, treating missing bytes as differences."""
        return sum(region.changed_byte_count for region in self.regions)

    def to_dict(self) -> dict[str, Any]:
        """Return the stable version-1 JSON structure."""
        return {
            "format": _FORMAT_NAME,
            "format_version": _FORMAT_VERSION,
            "base_offset": self.base_offset,
            "original_size": self.original_size,
            "modified_size": self.modified_size,
            "net_size_delta": self.net_size_delta,
            "changed_byte_count": self.changed_byte_count,
            "region_count": len(self.regions),
            "regions": [region.to_dict() for region in self.regions],
        }

    def to_json(self) -> str:
        """Serialize deterministically with sorted keys and one trailing LF."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"


def _as_bytes(value: _BytesLike, argument_name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{argument_name} must be bytes, bytearray, or memoryview")
    return bytes(value)


def compare_bytes(
    original: _BytesLike,
    modified: _BytesLike,
    *,
    base_offset: int = 0,
) -> ROMByteDiff:
    """Return contiguous changed regions between two in-memory byte buffers.

    The comparison is by absolute position, not a sequence-alignment algorithm.
    Unchanged positions split regions. Appended/truncated bytes are represented
    as changes at their original byte offsets. `base_offset` lets callers diff
    a slice while preserving offsets into the containing file.

    This function is pure: it does not read or write files, and it does not
    mutate either input buffer.
    """
    original_bytes = _as_bytes(original, "original")
    modified_bytes = _as_bytes(modified, "modified")

    if isinstance(base_offset, bool) or not isinstance(base_offset, int):
        raise TypeError("base_offset must be an integer")
    if base_offset < 0:
        raise ValueError("base_offset must be non-negative")

    max_size = max(len(original_bytes), len(modified_bytes))
    regions: list[DiffRegion] = []
    cursor = 0

    while cursor < max_size:
        original_value = (
            original_bytes[cursor] if cursor < len(original_bytes) else None
        )
        modified_value = (
            modified_bytes[cursor] if cursor < len(modified_bytes) else None
        )

        if original_value == modified_value:
            cursor += 1
            continue

        local_start = cursor
        while cursor < max_size:
            original_value = (
                original_bytes[cursor] if cursor < len(original_bytes) else None
            )
            modified_value = (
                modified_bytes[cursor] if cursor < len(modified_bytes) else None
            )
            if original_value == modified_value:
                break
            cursor += 1

        regions.append(
            DiffRegion(
                start_offset=base_offset + local_start,
                end_offset_exclusive=base_offset + cursor,
                original_bytes=original_bytes[local_start:cursor],
                modified_bytes=modified_bytes[local_start:cursor],
                changed_byte_count=cursor - local_start,
            )
        )

    return ROMByteDiff(
        base_offset=base_offset,
        original_size=len(original_bytes),
        modified_size=len(modified_bytes),
        regions=tuple(regions),
    )
