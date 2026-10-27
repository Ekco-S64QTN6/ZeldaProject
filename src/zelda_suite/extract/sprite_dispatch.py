"""Parse source metadata for the SpriteActive3 handler dispatch table."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_TABLE_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_ENTRY_RE = re.compile(r"^\s*dw\s+(?P<handler>[A-Za-z_][A-Za-z0-9_]*)\s*$", re.IGNORECASE)
_COMMENT_RE = re.compile(
    r"0x(?P<sprite_id>[0-9A-Fa-f]+)\s*-\s*"
    r"\$(?P<handler_address>[0-9A-Fa-f]+)\s*(?P<description>.*)\Z"
)


class SpriteDispatchParseError(ValueError):
    """Raised when the source sprite dispatch table is ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class SpriteDispatchEntry:
    """Source-mapped dispatch handler for one actual sprite type ID."""

    table_index: int
    sprite_type_id: int
    pointer_entry_file_offset: int
    source_line: int
    handler_expression: str
    handler_label: str
    source_comment_sprite_type_id: int
    source_handler_address_annotation: str
    source_description: str
    source_comment: str
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly entry."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SpriteDispatchTable:
    """Metadata for the source-defined SpriteActive3 jump table."""

    source_file: str
    source_revision: str
    table_label: str
    table_file_offset: int
    table_end_offset: int
    table_size_bytes: int
    entry_width_bytes: int
    sprite_type_id_start: int
    sprite_type_id_end: int
    entries: list[SpriteDispatchEntry]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned source export."""
        return {
            "format": "zelda-suite-sprite-dispatch",
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "table_label": self.table_label,
            "table_file_offset": self.table_file_offset,
            "table_end_offset": self.table_end_offset,
            "table_size_bytes": self.table_size_bytes,
            "entry_width_bytes": self.entry_width_bytes,
            "sprite_type_id_start": self.sprite_type_id_start,
            "sprite_type_id_end": self.sprite_type_id_end,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def _source_code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def parse_sprite_dispatch_table(
    source: str,
    *,
    table_file_offset: int,
    table_end_offset: int,
    source_revision: str,
    source_file: str = "Bank1E.asm",
    table_label: str = "SpriteActive3_Table",
    sprite_type_id_start: int = 0x79,
    expected_entry_count: int = 68,
) -> SpriteDispatchTable:
    """Parse handler labels and the source comments that identify sprite IDs.

    Source-comment handler addresses are preserved as annotations only. They
    are not converted to ROM file offsets or claimed to be independently
    verified pointer targets.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_label):
        raise ValueError("table_label must be a global assembly identifier")
    if isinstance(table_file_offset, bool) or not isinstance(table_file_offset, int):
        raise TypeError("table_file_offset must be an integer")
    if isinstance(table_end_offset, bool) or not isinstance(table_end_offset, int):
        raise TypeError("table_end_offset must be an integer")
    if table_file_offset < 0 or table_end_offset < table_file_offset:
        raise ValueError("table offsets must be non-negative and ordered")
    if isinstance(sprite_type_id_start, bool) or not isinstance(sprite_type_id_start, int):
        raise TypeError("sprite_type_id_start must be an integer")
    if not 0 <= sprite_type_id_start <= 0xFFFF:
        raise ValueError("sprite_type_id_start must fit in 16 bits")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")

    expected_size = expected_entry_count * 2
    actual_size = table_end_offset - table_file_offset + 1
    if actual_size != expected_size:
        raise ValueError(
            f"table range covers {actual_size} bytes but {expected_entry_count} "
            f"two-byte entries require {expected_size}"
        )

    lines = source.splitlines()
    label_hits = [
        index
        for index, line in enumerate(lines)
        if (match := _TABLE_LABEL_RE.fullmatch(_source_code(line))) is not None
        and match.group("label") == table_label
    ]
    if len(label_hits) != 1:
        raise SpriteDispatchParseError(
            f"expected exactly one {table_label!r} label; found {len(label_hits)}"
        )
    label_line = label_hits[0]

    opening_line: int | None = None
    for index in range(label_line + 1, len(lines)):
        code = _source_code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise SpriteDispatchParseError(
            f"expected '{{' after {table_label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise SpriteDispatchParseError(f"opening brace not found for {table_label!r}")

    depth = 1
    closing_line: int | None = None
    for index in range(opening_line + 1, len(lines)):
        code = _source_code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            closing_line = index
            break
        if depth < 0:
            raise SpriteDispatchParseError(
                f"unexpected closing brace in {table_label!r} on line {index + 1}"
            )
    if closing_line is None:
        raise SpriteDispatchParseError(f"closing brace not found for {table_label!r}")

    entries: list[SpriteDispatchEntry] = []
    for index in range(opening_line + 1, closing_line):
        line = lines[index]
        code = _source_code(line)
        if not code:
            continue

        entry_match = _ENTRY_RE.fullmatch(code)
        if entry_match is None:
            raise SpriteDispatchParseError(
                f"unsupported syntax in {table_label!r} on line {index + 1}: {code!r}"
            )
        if ";" not in line:
            raise SpriteDispatchParseError(
                f"missing sprite ID/handler annotation on line {index + 1}"
            )
        source_comment = line.split(";", 1)[1].strip()
        comment_match = _COMMENT_RE.fullmatch(source_comment)
        if comment_match is None:
            raise SpriteDispatchParseError(
                f"malformed sprite dispatch comment on line {index + 1}: {source_comment!r}"
            )

        table_index = len(entries)
        sprite_id = int(comment_match.group("sprite_id"), 16)
        expected_sprite_id = sprite_type_id_start + table_index
        if sprite_id != expected_sprite_id:
            raise SpriteDispatchParseError(
                f"table slot {table_index} is annotated with sprite ID {sprite_id:#x}; "
                f"expected {expected_sprite_id:#x}"
            )
        handler = entry_match.group("handler")
        entries.append(
            SpriteDispatchEntry(
                table_index=table_index,
                sprite_type_id=sprite_id,
                pointer_entry_file_offset=table_file_offset + table_index * 2,
                source_line=index + 1,
                handler_expression=handler,
                handler_label=handler,
                source_comment_sprite_type_id=sprite_id,
                source_handler_address_annotation="$" + comment_match.group("handler_address"),
                source_description=comment_match.group("description"),
                source_comment=source_comment,
                source_revision=source_revision,
            )
        )

    if len(entries) != expected_entry_count:
        raise SpriteDispatchParseError(
            f"{table_label!r} contains {len(entries)} entries; "
            f"expected {expected_entry_count}"
        )
    sprite_type_id_end = sprite_type_id_start + expected_entry_count - 1
    if sprite_type_id_end > 0xFFFF:
        raise ValueError("sprite ID range exceeds 16 bits")

    return SpriteDispatchTable(
        source_file=source_file,
        source_revision=source_revision,
        table_label=table_label,
        table_file_offset=table_file_offset,
        table_end_offset=table_end_offset,
        table_size_bytes=actual_size,
        entry_width_bytes=2,
        sprite_type_id_start=sprite_type_id_start,
        sprite_type_id_end=sprite_type_id_end,
        entries=entries,
    )
