"""Parse raw Asar data tables while preserving source expressions."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}

_GLOBAL_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_SOURCE_LABEL_RE = re.compile(
    r"^\s*(?P<label>\.?[A-Za-z_][A-Za-z0-9_]*)\s*:?[ \t]*$"
)
_DATA_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<directive>db|dw|dl)\s+(?P<values>.*?)\s*$",
    re.IGNORECASE,
)
_HEX_DOLLAR_RE = re.compile(r"\$[0-9A-Fa-f]+\Z")
_HEX_PREFIX_RE = re.compile(r"0[xX][0-9A-Fa-f]+\Z")
_DECIMAL_RE = re.compile(r"[0-9]+\Z")


class DataTableParseError(ValueError):
    """Raised when a source data table is ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class DataTableEntry:
    """A single source expression within a fixed-width data table."""

    table_index: int
    entry_file_offset: int
    source_line: int
    source_label: str | None
    expression: str
    literal_value: int | None
    source_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable record."""
        return asdict(self)


def _code(line: str) -> str:
    """Strip a source comment from a line."""
    return line.split(";", 1)[0].strip()


def _find_parent_block(
    lines: list[str], parent_label: str
) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", parent_label):
        raise ValueError("parent_label must be a global assembly identifier")

    parent_line: int | None = None
    for index, line in enumerate(lines):
        match = _GLOBAL_LABEL_RE.fullmatch(_code(line))
        if match is not None and match.group("label") == parent_label:
            parent_line = index
            break
    if parent_line is None:
        raise DataTableParseError(f"parent label not found: {parent_label}")

    opening_line: int | None = None
    for index in range(parent_line + 1, len(lines)):
        code = _code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise DataTableParseError(
            f"expected '{{' after parent label {parent_label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise DataTableParseError(f"opening brace not found for parent {parent_label!r}")

    depth = 1
    for index in range(opening_line + 1, len(lines)):
        code = _code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return opening_line + 1, index
        if depth < 0:
            raise DataTableParseError(
                f"unexpected closing brace in parent block {parent_label!r} "
                f"on line {index + 1}"
            )
    raise DataTableParseError(f"closing brace not found for parent {parent_label!r}")


def _label_hits(
    lines: list[str], label: str, start: int, end: int
) -> list[int]:
    hits: list[int] = []
    for index in range(start, end):
        match = _SOURCE_LABEL_RE.fullmatch(_code(lines[index]))
        if match is not None and match.group("label") == label:
            hits.append(index)
    return hits


def _literal_value(expression: str) -> int | None:
    if _HEX_DOLLAR_RE.fullmatch(expression):
        return int(expression[1:], 16)
    if _HEX_PREFIX_RE.fullmatch(expression):
        return int(expression, 16)
    if _DECIMAL_RE.fullmatch(expression):
        return int(expression, 10)
    return None


def parse_data_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    directive: str = "db",
    entry_width: int | None = None,
    parent_label: str | None = None,
    end_label: str | None = None,
    source_revision: str | None = None,
) -> list[DataTableEntry]:
    """Parse raw db/dw/dl expressions, preserving both literals and symbols.

    The optional parent label scopes local labels such as `.item_values` to a
    containing Asar block. An optional end label gives an explicit exclusive
    table boundary when several arrays share one block. Expressions are never
    evaluated; simple numeric literals are additionally exposed as integers.
    """
    normalized_directive = directive.lower() if isinstance(directive, str) else ""
    if normalized_directive not in DATA_DIRECTIVE_WIDTHS:
        raise ValueError("directive must be 'db', 'dw', or 'dl'")
    if isinstance(table_file_offset, bool) or not isinstance(table_file_offset, int):
        raise TypeError("table_file_offset must be an integer")
    if table_file_offset < 0:
        raise ValueError("table_file_offset must be non-negative")

    actual_entry_width = (
        DATA_DIRECTIVE_WIDTHS[normalized_directive]
        if entry_width is None
        else entry_width
    )
    if isinstance(actual_entry_width, bool) or not isinstance(actual_entry_width, int):
        raise TypeError("entry_width must be an integer")
    if actual_entry_width <= 0:
        raise ValueError("entry_width must be positive")

    if not isinstance(label, str) or not label:
        raise ValueError("label must be a non-empty source label")
    if _SOURCE_LABEL_RE.fullmatch(label) is None:
        raise ValueError("label must be a source assembly label")
    if end_label is not None and _SOURCE_LABEL_RE.fullmatch(end_label) is None:
        raise ValueError("end_label must be a source assembly label")

    lines = source.splitlines()
    if parent_label is not None:
        scope_start, scope_end = _find_parent_block(lines, parent_label)
    else:
        scope_start, scope_end = 0, len(lines)

    start_hits = _label_hits(lines, label, scope_start, scope_end)
    if not start_hits:
        if parent_label is None:
            raise DataTableParseError(f"label not found: {label}")
        raise DataTableParseError(
            f"label {label!r} not found inside parent block {parent_label!r}"
        )
    if len(start_hits) != 1:
        raise DataTableParseError(
            f"label {label!r} is ambiguous; provide a parent_label that scopes it"
        )
    table_start_line = start_hits[0]

    if end_label is None:
        table_end_line = scope_end
    else:
        end_hits = [
            index
            for index in _label_hits(lines, end_label, table_start_line + 1, scope_end)
        ]
        if len(end_hits) != 1:
            if not end_hits:
                raise DataTableParseError(
                    f"end label {end_label!r} not found after {label!r}"
                )
            raise DataTableParseError(
                f"end label {end_label!r} is ambiguous after {label!r}"
            )
        table_end_line = end_hits[0]

    entries: list[DataTableEntry] = []
    active_source_label: str | None = label
    for index in range(table_start_line + 1, table_end_line):
        code = _code(lines[index])
        if not code or code in {"{", "}"}:
            continue

        label_match = _SOURCE_LABEL_RE.fullmatch(code)
        if label_match is not None:
            active_source_label = label_match.group("label")
            continue

        directive_match = _DATA_DIRECTIVE_RE.fullmatch(code)
        if directive_match is None:
            raise DataTableParseError(
                f"unsupported syntax in data table {label!r} on line {index + 1}: "
                f"{code!r}"
            )

        actual_directive = directive_match.group("directive").lower()
        if actual_directive != normalized_directive:
            raise DataTableParseError(
                f"expected {normalized_directive} directive but found "
                f"{actual_directive} in table {label!r} on line {index + 1}"
            )

        values = directive_match.group("values").strip()
        if not values:
            raise DataTableParseError(
                f"empty {normalized_directive} directive in table {label!r} "
                f"on line {index + 1}"
            )
        expressions = [value.strip() for value in values.split(",")]
        if any(not expression for expression in expressions):
            raise DataTableParseError(
                f"malformed {normalized_directive} directive in table {label!r} "
                f"on line {index + 1}"
            )

        for expression in expressions:
            value = _literal_value(expression)
            if value is not None and value >= 1 << (8 * actual_entry_width):
                raise DataTableParseError(
                    f"literal {expression!r} exceeds {actual_entry_width}-byte "
                    f"width in table {label!r} on line {index + 1}"
                )
            table_index = len(entries)
            entries.append(
                DataTableEntry(
                    table_index=table_index,
                    entry_file_offset=table_file_offset
                    + table_index * actual_entry_width,
                    source_line=index + 1,
                    source_label=active_source_label,
                    expression=expression,
                    literal_value=value,
                    source_revision=source_revision,
                )
            )

    if not entries:
        raise DataTableParseError(f"data table {label!r} is empty")
    return entries
