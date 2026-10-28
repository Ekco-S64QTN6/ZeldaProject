"""Parse the inline SpritePrep_Main dispatch table from pinned assembly source.

The source exposes a routine-region comment, not a byte-accurate annotation for
this inline table. The parser deliberately keeps the table offset unset and
stores handler addresses only as unverified source-comment annotations.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_ROUTINE_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_LITERAL_RE = re.compile(r"\$[0-9A-Fa-f]{1,4}\Z")
_RANGE_ANNOTATION_RE = re.compile(
    r"^\s*;\s*\$(?P<start>[0-9A-Fa-f]+)-\$(?P<end>[0-9A-Fa-f]+)\s+JUMP LOCATION\s*$",
    re.IGNORECASE,
)
_ENTRY_COMMENT_RE = re.compile(
    r"0x(?P<sprite_id>[0-9A-Fa-f]{2})\s*-\s*"
    r"(?P<address>\$[0-9A-Fa-f]{4})\s*(?P<description>.*)\Z"
)
_DISPATCH_CALL_RE = re.compile(
    r"^\s*JSL\.l\s+UseImplicitRegIndexedLocalJumpTable\s*$", re.IGNORECASE
)
_DW_RE = re.compile(r"^\s*dw\s+(?P<expression>[^;]+?)\s*$", re.IGNORECASE)


class SpritePrepDispatchParseError(ValueError):
    """Raised when SpritePrep_Main or its inline dispatch table is malformed."""


@dataclass(frozen=True, slots=True)
class SpritePrepDispatchEntry:
    """One source-commented SpritePrep_Main dispatch entry."""

    table_index: int
    sprite_type_id: int
    source_line: int
    handler_expression: str
    handler_label: str | None
    source_comment_sprite_type_id: int
    source_handler_address_annotation: str
    source_description: str
    source_comment: str
    source_comment_continuations: list[str]
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly record."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SpritePrepDispatchTable:
    """Inline SpritePrep_Main dispatch table with source-only provenance."""

    source_file: str
    source_revision: str
    routine_label: str
    routine_source_range_annotation: str
    table_file_offset: None
    table_offset_established: bool
    sprite_type_id_start: int
    sprite_type_id_end: int
    entries: list[SpritePrepDispatchEntry]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned source export."""
        return {
            "format": "zelda-suite-sprite-prep-dispatch",
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "routine_label": self.routine_label,
            "routine_source_range_annotation": self.routine_source_range_annotation,
            "table_file_offset": None,
            "table_offset_established": False,
            "sprite_type_id_start": self.sprite_type_id_start,
            "sprite_type_id_end": self.sprite_type_id_end,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "evidence": {
                "source_only": True,
                "rom_bytes_read": False,
                "table_offset_established": False,
                "handler_address_annotations_verified": False,
                "runtime_behavior_verified": False,
            },
        }


def _source_code(line: str) -> str:
    """Remove one semicolon comment from an assembly source line."""
    return line.split(";", 1)[0].strip()


def parse_sprite_prep_dispatch_table(
    source: str,
    *,
    source_revision: str,
    source_file: str = "sprite_prep.asm",
    routine_label: str = "SpritePrep_Main",
    expected_entry_count: int = 243,
) -> SpritePrepDispatchTable:
    """Parse SpritePrep_Main's inline word table without inventing a table offset.

    The source ID annotations must be sequential and match table positions.
    Address annotations and wrapped descriptions are preserved as source
    metadata; no assembler expressions are evaluated.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if not isinstance(routine_label, str) or _SYMBOL_RE.fullmatch(routine_label) is None:
        raise ValueError("routine_label must be an assembly identifier")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")

    lines = source.splitlines()
    label_hits = [
        i for i, line in enumerate(lines)
        if (match := _ROUTINE_LABEL_RE.fullmatch(_source_code(line))) is not None
        and match.group("label") == routine_label
    ]
    if len(label_hits) != 1:
        raise SpritePrepDispatchParseError(
            f"expected exactly one {routine_label!r} label; found {len(label_hits)}"
        )
    label_index = label_hits[0]

    range_annotation: str | None = None
    for index in range(label_index - 1, max(-1, label_index - 6), -1):
        raw = lines[index].strip()
        if not raw:
            continue
        if _RANGE_ANNOTATION_RE.fullmatch(raw) is not None:
            range_annotation = raw[1:].strip()
        break
    if range_annotation is None:
        raise SpritePrepDispatchParseError(
            f"source range annotation for {routine_label!r} was not found above the routine"
        )

    opening_index: int | None = None
    for index in range(label_index + 1, len(lines)):
        code = _source_code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_index = index
            break
        raise SpritePrepDispatchParseError(
            f"expected '{{' after {routine_label!r} near line {index + 1}"
        )
    if opening_index is None:
        raise SpritePrepDispatchParseError(f"opening brace not found for {routine_label!r}")

    depth = 1
    closing_index: int | None = None
    for index in range(opening_index + 1, len(lines)):
        code = _source_code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            closing_index = index
            break
        if depth < 0:
            raise SpritePrepDispatchParseError(
                f"unexpected closing brace in {routine_label!r} on line {index + 1}"
            )
    if closing_index is None:
        raise SpritePrepDispatchParseError(f"closing brace not found for {routine_label!r}")

    dispatch_calls = [
        i for i in range(opening_index + 1, closing_index)
        if _DISPATCH_CALL_RE.fullmatch(_source_code(lines[i])) is not None
    ]
    if len(dispatch_calls) != 1:
        raise SpritePrepDispatchParseError(
            f"expected one UseImplicitRegIndexedLocalJumpTable call in {routine_label!r}; "
            f"found {len(dispatch_calls)}"
        )
    dispatch_index = dispatch_calls[0]

    entries: list[SpritePrepDispatchEntry] = []
    for index in range(dispatch_index + 1, closing_index):
        raw_line = lines[index]
        code = _source_code(raw_line)
        if not code:
            comment = raw_line.split(";", 1)[1].strip() if ";" in raw_line else ""
            if comment and entries and not set(comment) <= {"="}:
                entries[-1].source_comment_continuations.append(comment)
            continue

        entry_match = _DW_RE.fullmatch(code)
        if entry_match is None:
            raise SpritePrepDispatchParseError(
                f"unsupported syntax after dispatch call on line {index + 1}: {code!r}"
            )
        if ";" not in raw_line:
            raise SpritePrepDispatchParseError(
                f"missing sprite ID/handler annotation on line {index + 1}"
            )
        source_comment = raw_line.split(";", 1)[1].strip()
        comment_match = _ENTRY_COMMENT_RE.fullmatch(source_comment)
        if comment_match is None:
            raise SpritePrepDispatchParseError(
                f"malformed sprite prep comment on line {index + 1}: {source_comment!r}"
            )

        table_index = len(entries)
        sprite_id = int(comment_match.group("sprite_id"), 16)
        if sprite_id != table_index:
            raise SpritePrepDispatchParseError(
                f"table slot {table_index} is annotated with sprite ID {sprite_id:#x}; "
                f"expected {table_index:#x}"
            )

        expression = entry_match.group("expression").strip()
        if _SYMBOL_RE.fullmatch(expression) is not None:
            handler_label: str | None = expression
        elif _LITERAL_RE.fullmatch(expression) is not None:
            handler_label = None
        else:
            raise SpritePrepDispatchParseError(
                f"unsupported handler expression on line {index + 1}: {expression!r}"
            )

        entries.append(
            SpritePrepDispatchEntry(
                table_index=table_index,
                sprite_type_id=sprite_id,
                source_line=index + 1,
                handler_expression=expression,
                handler_label=handler_label,
                source_comment_sprite_type_id=sprite_id,
                source_handler_address_annotation=comment_match.group("address"),
                source_description=comment_match.group("description").strip(),
                source_comment=source_comment,
                source_comment_continuations=[],
                source_revision=source_revision,
            )
        )

    if len(entries) != expected_entry_count:
        raise SpritePrepDispatchParseError(
            f"{routine_label!r} contains {len(entries)} dispatch entries; "
            f"expected {expected_entry_count}"
        )
    if not entries:
        raise SpritePrepDispatchParseError(f"{routine_label!r} dispatch table is empty")

    return SpritePrepDispatchTable(
        source_file=source_file,
        source_revision=source_revision,
        routine_label=routine_label,
        routine_source_range_annotation=range_annotation,
        table_file_offset=None,
        table_offset_established=False,
        sprite_type_id_start=entries[0].sprite_type_id,
        sprite_type_id_end=entries[-1].sprite_type_id,
        entries=entries,
    )
