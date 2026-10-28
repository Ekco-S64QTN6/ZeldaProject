"""Parse the packed source-only Dungeon_ChestData array.

The source comments define the packed fields, but its annotated offsets are
retained as candidates rather than treated as verified ROM offsets.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from zelda_suite.extract.data_table import DataTableParseError, parse_data_table

DUNGEON_CHEST_DATA_FORMAT = "zelda-suite-dungeon-chest-data"
DUNGEON_CHEST_DATA_LABEL = "Dungeon_ChestData"
DUNGEON_CHEST_DATA_SOURCE_FILE = "Bank01.asm"
DUNGEON_CHEST_DATA_ENTRY_WIDTH = 3
DUNGEON_CHEST_DATA_ENTRY_COUNT = 168

_LABEL_RE = re.compile(r"^\s*Dungeon_ChestData\s*:\s*$")
_RANGE_RE = re.compile(
    r"^\s*;\s*(?P<start>\$[0-9A-Fa-f]+)-(?P<end>\$[0-9A-Fa-f]+)\s*$"
)
_LITERAL_RE = re.compile(r"\$[0-9A-Fa-f]{6}\Z")


class DungeonChestDataParseError(ValueError):
    """Raised when the source chest array or its range annotation is malformed."""


@dataclass(frozen=True, slots=True)
class DungeonChestDataEntry:
    """One source-commented packed chest record."""

    table_index: int
    candidate_entry_offset: int
    source_line: int
    expression: str
    literal_value: int
    item_value: int
    room_value: int
    is_big_chest: bool
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly source record."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DungeonChestDataTable:
    """Versioned source inventory for the packed Dungeon_ChestData array."""

    source_file: str
    source_revision: str
    source_range_annotation: str
    source_annotated_start_offset: int
    source_annotated_end_offset: int
    entries: list[DungeonChestDataEntry]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned export without asserting ROM-offset validity."""
        return {
            "format": DUNGEON_CHEST_DATA_FORMAT,
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "table_label": DUNGEON_CHEST_DATA_LABEL,
            "source_range_annotation": self.source_range_annotation,
            "source_annotated_start_offset": self.source_annotated_start_offset,
            "source_annotated_end_offset": self.source_annotated_end_offset,
            "table_size_bytes": self.source_annotated_end_offset
            - self.source_annotated_start_offset
            + 1,
            "entry_width_bytes": DUNGEON_CHEST_DATA_ENTRY_WIDTH,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "evidence": {
                "source_only": True,
                "rom_bytes_read": False,
                "source_range_offsets_verified": False,
                "item_value_names_resolved": False,
                "room_values_verified_against_rom": False,
            },
        }


def parse_dungeon_chest_data(
    source: str,
    *,
    source_revision: str,
    source_file: str = DUNGEON_CHEST_DATA_SOURCE_FILE,
    expected_entry_count: int = DUNGEON_CHEST_DATA_ENTRY_COUNT,
) -> DungeonChestDataTable:
    """Parse and unpack 24-bit chest values while retaining raw expressions.

    The source describes the top byte as the item value, the low 15 bits as the
    room value, and bit 15 as the big-chest flag. These are raw field values;
    this function does not resolve item names or validate offsets against ROM.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")

    lines = source.splitlines()
    label_hits = [
        index
        for index, line in enumerate(lines)
        if _LABEL_RE.fullmatch(line.split(";", 1)[0].strip()) is not None
    ]
    if len(label_hits) != 1:
        raise DungeonChestDataParseError(
            f"expected exactly one {DUNGEON_CHEST_DATA_LABEL!r} label; "
            f"found {len(label_hits)}"
        )
    label_index = label_hits[0]
    if label_index == 0:
        raise DungeonChestDataParseError("source range annotation is missing")

    range_match = _RANGE_RE.fullmatch(lines[label_index - 1])
    if range_match is None:
        raise DungeonChestDataParseError(
            f"source range annotation immediately above {DUNGEON_CHEST_DATA_LABEL!r} "
            "must be '$start-$end'"
        )
    source_range_annotation = lines[label_index - 1].split(";", 1)[1].strip()
    start_offset = int(range_match.group("start")[1:], 16)
    end_offset = int(range_match.group("end")[1:], 16)
    if end_offset < start_offset:
        raise DungeonChestDataParseError("source range end precedes source range start")

    table_size = end_offset - start_offset + 1
    if table_size != expected_entry_count * DUNGEON_CHEST_DATA_ENTRY_WIDTH:
        raise DungeonChestDataParseError(
            f"source range covers {table_size} bytes but "
            f"{expected_entry_count} entries require "
            f"{expected_entry_count * DUNGEON_CHEST_DATA_ENTRY_WIDTH} bytes"
        )

    try:
        raw_entries = parse_data_table(
            source,
            DUNGEON_CHEST_DATA_LABEL,
            start_offset,
            directive="dl",
            source_revision=source_revision,
            expected_entry_count=expected_entry_count,
        )
    except (OSError, ValueError) as exc:
        raise DungeonChestDataParseError(str(exc)) from exc

    entries: list[DungeonChestDataEntry] = []
    for raw_entry in raw_entries:
        expression = raw_entry.expression
        if _LITERAL_RE.fullmatch(expression) is None or raw_entry.literal_value is None:
            raise DungeonChestDataParseError(
                f"entry {raw_entry.table_index} is not a six-digit 24-bit literal: "
                f"{expression!r}"
            )
        literal = raw_entry.literal_value
        if not 0 <= literal <= 0xFFFFFF:
            raise DungeonChestDataParseError(
                f"entry {raw_entry.table_index} does not fit in 24 bits"
            )
        entries.append(
            DungeonChestDataEntry(
                table_index=raw_entry.table_index,
                candidate_entry_offset=raw_entry.entry_file_offset,
                source_line=raw_entry.source_line,
                expression=expression,
                literal_value=literal,
                item_value=(literal >> 16) & 0xFF,
                room_value=literal & 0x7FFF,
                is_big_chest=bool(literal & 0x8000),
                source_revision=source_revision,
            )
        )

    if end_offset != start_offset + len(entries) * DUNGEON_CHEST_DATA_ENTRY_WIDTH - 1:
        raise DungeonChestDataParseError(
            "source range annotation does not match the parsed chest-entry count"
        )

    return DungeonChestDataTable(
        source_file=source_file,
        source_revision=source_revision,
        source_range_annotation=source_range_annotation,
        source_annotated_start_offset=start_offset,
        source_annotated_end_offset=end_offset,
        entries=entries,
    )
