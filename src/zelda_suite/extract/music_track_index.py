"""Parse the source-declared music track pointer table.

This module records Asar dw expressions and source index comments. It does not
resolve symbols, read song payloads, or confuse SPC RAM addresses with ROM
file offsets.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_MUSIC_TABLE_LABEL_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$"
)
_BASE_RE = re.compile(r"^\s*base\s+(?P<base>[A-Za-z_][A-Za-z0-9_]*)\s*$", re.IGNORECASE)
_POINTER_RE = re.compile(
    r"^\s*dw\s+(?P<expression>\$[0-9A-Fa-f]{4}|[A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)
_TRACK_COMMENT_RE = re.compile(r"^\s*0x(?P<index>[0-9A-Fa-f]{2})\s*$")


class MusicTrackIndexError(ValueError):
    """Raised when the source music pointer table is ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class MusicTrackEntry:
    """One two-byte song-pointer expression and its source audit fields."""

    table_index: int
    track_index: int
    pointer_entry_file_offset: int
    source_line: int
    pointer_expression: str
    target_label: str | None
    is_empty: bool
    alias_of_track_index: int | None
    source_comment_index: int
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable record."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MusicTrackIndex:
    """Metadata for one source-defined music track pointer table."""

    source_file: str
    source_revision: str
    block_label: str
    base_expression: str
    table_file_offset: int
    table_end_offset: int
    entry_width_bytes: int
    track_index_start: int
    track_index_end: int
    entries: list[MusicTrackEntry]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned source export."""
        return {
            "format": "zelda-suite-music-track-index",
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "block_label": self.block_label,
            "base_expression": self.base_expression,
            "table_file_offset": self.table_file_offset,
            "table_end_offset": self.table_end_offset,
            "table_size_bytes": self.table_end_offset - self.table_file_offset + 1,
            "entry_width_bytes": self.entry_width_bytes,
            "track_index_start": self.track_index_start,
            "track_index_end": self.track_index_end,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _find_block(lines: list[str], block_label: str) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", block_label):
        raise ValueError("block_label must be a global assembly identifier")

    hits = [
        index
        for index, line in enumerate(lines)
        if (match := _MUSIC_TABLE_LABEL_RE.fullmatch(_code(line))) is not None
        and match.group("label") == block_label
    ]
    if len(hits) != 1:
        raise MusicTrackIndexError(
            f"expected exactly one {block_label!r} label; found {len(hits)}"
        )

    label_line = hits[0]
    opening_line: int | None = None
    for index in range(label_line + 1, len(lines)):
        code = _code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise MusicTrackIndexError(
            f"expected '{{' after {block_label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise MusicTrackIndexError(f"opening brace not found for {block_label!r}")

    depth = 1
    for index in range(opening_line + 1, len(lines)):
        code = _code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return opening_line + 1, index
        if depth < 0:
            raise MusicTrackIndexError(
                f"unexpected closing brace in {block_label!r} on line {index + 1}"
            )
    raise MusicTrackIndexError(f"closing brace not found for {block_label!r}")


def parse_music_track_index(
    source: str,
    *,
    table_file_offset: int,
    source_revision: str,
    source_file: str = "Bank1B.asm",
    block_label: str = "SongBank_Underworld_Main",
    base_expression: str = "SONG_POINTERS",
    track_index_start: int = 0x01,
    expected_entry_count: int = 0x23,
) -> MusicTrackIndex:
    """Parse bounded dw entries with source-index annotations.

    The default source table has 35 entries at file offset 0x0D8004 inside
    SongBank_Underworld_Main. Zero pointers and duplicate target labels are
    preserved. Duplicate labels point back to their first prior track index.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if isinstance(table_file_offset, bool) or not isinstance(table_file_offset, int):
        raise TypeError("table_file_offset must be an integer")
    if table_file_offset < 0:
        raise ValueError("table_file_offset must be non-negative")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", base_expression):
        raise ValueError("base_expression must be an assembly identifier")
    if isinstance(track_index_start, bool) or not isinstance(track_index_start, int):
        raise TypeError("track_index_start must be an integer")
    if not 0 <= track_index_start <= 0xFFFF:
        raise ValueError("track_index_start must fit in 16 bits")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")
    if track_index_start + expected_entry_count - 1 > 0xFFFF:
        raise ValueError("track index range exceeds 16 bits")

    lines = source.splitlines()
    block_start, block_end = _find_block(lines, block_label)
    base_hits = [
        index
        for index in range(block_start, block_end)
        if (match := _BASE_RE.fullmatch(_code(lines[index]))) is not None
        and match.group("base") == base_expression
    ]
    if len(base_hits) != 1:
        raise MusicTrackIndexError(
            f"expected exactly one 'base {base_expression}' directive inside "
            f"{block_label!r}; found {len(base_hits)}"
        )

    base_line = base_hits[0]
    parsed_rows: list[tuple[int, int, str]] = []
    for index in range(base_line + 1, block_end):
        line = lines[index]
        code = _code(line)
        if not code:
            continue

        pointer = _POINTER_RE.fullmatch(code)
        if pointer is None:
            if len(parsed_rows) == expected_entry_count:
                break
            raise MusicTrackIndexError(
                f"unexpected syntax before all pointer entries were parsed in "
                f"{block_label!r} on line {index + 1}: {code!r}"
            )
        if ";" not in line:
            raise MusicTrackIndexError(
                f"missing track index annotation on line {index + 1}"
            )
        comment_match = _TRACK_COMMENT_RE.fullmatch(line.split(";", 1)[1])
        if comment_match is None:
            raise MusicTrackIndexError(
                f"malformed track index annotation on line {index + 1}"
            )
        source_index = int(comment_match.group("index"), 16)
        expected_index = track_index_start + len(parsed_rows)
        if source_index != expected_index:
            raise MusicTrackIndexError(
                f"table slot {len(parsed_rows)} has source index {source_index:#04x}; "
                f"expected {expected_index:#04x}"
            )
        expression = pointer.group("expression")
        if expression.startswith("$") and expression.upper() != "$0000":
            raise MusicTrackIndexError(
                f"unsupported numeric pointer expression on line {index + 1}: {expression}"
            )
        parsed_rows.append((index + 1, source_index, expression))

    if len(parsed_rows) != expected_entry_count:
        raise MusicTrackIndexError(
            f"music pointer table contains {len(parsed_rows)} entries; "
            f"expected {expected_entry_count}"
        )

    first_track_for_label: dict[str, int] = {}
    entries: list[MusicTrackEntry] = []
    for table_index, (source_line, track_index, expression) in enumerate(parsed_rows):
        is_empty = expression.upper() == "$0000"
        target_label = None if is_empty else expression
        alias_index = None
        if target_label is not None:
            alias_index = first_track_for_label.get(target_label)
            first_track_for_label.setdefault(target_label, track_index)

        entries.append(
            MusicTrackEntry(
                table_index=table_index,
                track_index=track_index,
                pointer_entry_file_offset=table_file_offset + table_index * 2,
                source_line=source_line,
                pointer_expression=expression,
                target_label=target_label,
                is_empty=is_empty,
                alias_of_track_index=alias_index,
                source_comment_index=track_index,
                source_revision=source_revision,
            )
        )

    return MusicTrackIndex(
        source_file=source_file,
        source_revision=source_revision,
        block_label=block_label,
        base_expression=base_expression,
        table_file_offset=table_file_offset,
        table_end_offset=table_file_offset + expected_entry_count * 2 - 1,
        entry_width_bytes=2,
        track_index_start=track_index_start,
        track_index_end=track_index_start + expected_entry_count - 1,
        entries=entries,
    )
