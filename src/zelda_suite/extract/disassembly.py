"""Helpers for reading semantic declarations from the pinned Asar disassembly.

This module parses source declarations only. It never reads or writes ROM bytes,
and it does not resolve symbols to binary offsets.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}
POINTER_DIRECTIVE_WIDTHS = {"dw": 2, "dl": 3}

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_EXPRESSION_RE = re.compile(
    r"(?P<label>[A-Za-z_][A-Za-z0-9_]*)(?:(?P<sign>[+-])\s*(?P<offset>\$[0-9A-Fa-f]+|[0-9]+))?\Z"
)
_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<directive>db|dw|dl)\s+(?P<values>.*?)\s*$",
    re.IGNORECASE,
)


class DisassemblyParseError(ValueError):
    """Raised when a requested source table cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class PointerTableEntry:
    """A source-level pointer-table declaration with an audit location."""

    table_index: int
    pointer_entry_file_offset: int
    source_line: int
    pointer_expression: str
    target_label: str
    target_addend: int | None
    is_empty_target: bool
    source_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable record."""
        return asdict(self)


def _parse_pointer_expression(expression: str, source_line: int) -> tuple[str, int | None]:
    match = _EXPRESSION_RE.fullmatch(expression)
    if match is None:
        raise DisassemblyParseError(
            f"unsupported pointer expression on line {source_line}: {expression!r}"
        )

    offset_token = match.group("offset")
    if offset_token is None:
        return match.group("label"), None

    offset = int(offset_token[1:], 16) if offset_token.startswith("$") else int(offset_token)
    if match.group("sign") == "-":
        offset = -offset
    return match.group("label"), offset


def parse_source_pointer_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    directive: str = "dl",
    entry_width: int | None = None,
    source_revision: str | None = None,
) -> list[PointerTableEntry]:
    """Parse a brace-delimited Asar dw or dl table into audit records.

    The directive determines the default entry width (dw=2, dl=3). A caller
    may supply an explicit width for a documented custom encoding, but that
    width only affects calculated entry locations and does not change how the
    source expressions are parsed. The function never evaluates expressions
    or resolves target symbols to ROM byte offsets.
    """
    normalized_directive = directive.lower() if isinstance(directive, str) else ""
    if normalized_directive not in POINTER_DIRECTIVE_WIDTHS:
        raise ValueError("directive must be 'dw' or 'dl'")
    if table_file_offset < 0:
        raise ValueError("table_file_offset must be non-negative")
    actual_entry_width = (
        POINTER_DIRECTIVE_WIDTHS[normalized_directive]
        if entry_width is None
        else entry_width
    )
    if isinstance(actual_entry_width, bool) or not isinstance(actual_entry_width, int):
        raise TypeError("entry_width must be an integer")
    if actual_entry_width <= 0:
        raise ValueError("entry_width must be positive")
    if not label or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label):
        raise ValueError("label must be a valid assembly identifier")

    lines = source.splitlines()
    label_line: int | None = None
    for index, line in enumerate(lines):
        match = _LABEL_RE.fullmatch(line.split(";", 1)[0])
        if match and match.group("label") == label:
            label_line = index
            break
    if label_line is None:
        raise DisassemblyParseError(f"label not found: {label}")

    opening_line: int | None = None
    for index in range(label_line + 1, len(lines)):
        code = lines[index].split(";", 1)[0].strip()
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise DisassemblyParseError(
            f"expected '{{' after label {label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise DisassemblyParseError(f"opening brace not found for table {label!r}")

    entries: list[PointerTableEntry] = []
    depth = 1
    for index in range(opening_line + 1, len(lines)):
        line = lines[index]
        code = line.split(";", 1)[0].strip()
        if not code:
            continue

        depth += code.count("{")
        depth -= code.count("}")
        if depth < 0:
            raise DisassemblyParseError(
                f"unexpected closing brace while parsing table {label!r} "
                f"on line {index + 1}"
            )
        if depth == 0:
            if not entries:
                raise DisassemblyParseError(f"pointer table {label!r} is empty")
            return entries

        if depth != 1:
            raise DisassemblyParseError(
                f"nested block encountered in pointer table {label!r} "
                f"on line {index + 1}"
            )

        data_directive = _DIRECTIVE_RE.fullmatch(code)
        if data_directive is None:
            # Labels and non-data instructions are not pointer entries.
            continue
        actual_directive = data_directive.group("directive").lower()
        if actual_directive not in DATA_DIRECTIVE_WIDTHS:
            continue
        if actual_directive != normalized_directive:
            raise DisassemblyParseError(
                f"expected {normalized_directive} directive but found "
                f"{actual_directive} in table {label!r} on line {index + 1}"
            )

        values = data_directive.group("values").strip()
        if not values:
            raise DisassemblyParseError(
                f"empty {normalized_directive} directive in table {label!r} "
                f"on line {index + 1}"
            )

        # A comma separates adjacent data expressions in Asar. Accepting
        # multiple values keeps indexing correct if a declaration is compacted.
        expressions = [value.strip() for value in values.split(",")]
        if any(not expression for expression in expressions):
            raise DisassemblyParseError(
                f"malformed {normalized_directive} directive in table {label!r} "
                f"on line {index + 1}"
            )

        for expression in expressions:
            target_label, target_addend = _parse_pointer_expression(
                expression, index + 1
            )
            table_index = len(entries)
            entries.append(
                PointerTableEntry(
                    table_index=table_index,
                    pointer_entry_file_offset=table_file_offset
                    + table_index * actual_entry_width,
                    source_line=index + 1,
                    pointer_expression=expression,
                    target_label=target_label,
                    target_addend=target_addend,
                    is_empty_target=target_label == "RoomDataTiles_Empty",
                    source_revision=source_revision,
                )
            )

    raise DisassemblyParseError(f"closing brace not found for table {label!r}")


def parse_dl_pointer_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    entry_width: int = 3,
    source_revision: str | None = None,
) -> list[PointerTableEntry]:
    """Parse an Asar dl pointer table, preserving the existing public API."""
    return parse_source_pointer_table(
        source,
        label,
        table_file_offset,
        directive="dl",
        entry_width=entry_width,
        source_revision=source_revision,
    )


def parse_dw_pointer_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    entry_width: int = 2,
    source_revision: str | None = None,
) -> list[PointerTableEntry]:
    """Parse an Asar dw pointer table into two-byte-entry source records."""
    return parse_source_pointer_table(
        source,
        label,
        table_file_offset,
        directive="dw",
        entry_width=entry_width,
        source_revision=source_revision,
    )
