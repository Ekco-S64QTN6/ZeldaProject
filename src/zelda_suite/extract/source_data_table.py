"""Parse bounded scalar data tables from Asar source text.

The parser reads source declarations only. It never opens incbin targets,
evaluates assembler expressions, or reads/writes ROM bytes.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}
_LABEL_RE = re.compile(
    r"^\s*(?P<label>\.?[A-Za-z_][A-Za-z0-9_.]*)\s*:?\s*$"
)
_GLOBAL_LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<directive>db|dw|dl)\s+(?P<values>.*?)\s*$",
    re.IGNORECASE,
)
_LITERAL_RE = re.compile(r"(?P<sign>[+-]?)(?P<value>\$[0-9A-Fa-f]+|0[xX][0-9A-Fa-f]+|[0-9]+)\Z")


class DataTableParseError(ValueError):
    """Raised when a bounded source data table cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class DataTableEntry:
    """A scalar declaration paired with its source location and annotation."""

    table_index: int
    entry_file_offset: int
    source_line: int
    directive: str
    source_label: str
    expression: str
    numeric_value: int | None
    inline_comment: str | None
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable entry."""
        return asdict(self)


def _strip_comment(line: str) -> tuple[str, str | None]:
    code, separator, comment = line.partition(";")
    return code, comment.strip() if separator else None


def _label_name(line: str) -> str | None:
    code, _ = _strip_comment(line)
    match = _LABEL_RE.fullmatch(code)
    return match.group("label") if match else None


def _parse_numeric_literal(expression: str) -> int | None:
    match = _LITERAL_RE.fullmatch(expression.strip())
    if match is None:
        return None
    token = match.group("value")
    if token.startswith("$"):
        value = int(token[1:], 16)
    elif token.lower().startswith("0x"):
        value = int(token, 16)
    else:
        value = int(token, 10)
    return -value if match.group("sign") == "-" else value


def _find_target_label(
    lines: list[str], label: str
) -> tuple[int, int | None, str]:
    """Return target line, optional containing-brace line, and active label."""
    if not label or any(character.isspace() for character in label):
        raise ValueError("label must be a non-empty assembly label")

    if "." not in label:
        if _GLOBAL_LABEL_RE.fullmatch(label) is None:
            raise ValueError("global label must be a valid assembly identifier")
        for index, line in enumerate(lines):
            if _label_name(line) == label:
                return index, None, label
        raise DataTableParseError(f"label not found: {label}")

    parent, child = label.split(".", 1)
    if _GLOBAL_LABEL_RE.fullmatch(parent) is None or not child:
        raise ValueError("qualified label must use Parent.local_label syntax")
    child_label = f".{child}"

    parent_line: int | None = None
    for index, line in enumerate(lines):
        if _label_name(line) == parent:
            parent_line = index
            break
    if parent_line is None:
        raise DataTableParseError(f"parent label not found: {parent}")

    opening_line: int | None = None
    depth = 0
    for index in range(parent_line + 1, len(lines)):
        code, _ = _strip_comment(lines[index])
        stripped = code.strip()
        if not stripped:
            continue
        if stripped == "{":
            opening_line = index
            depth = 1
            break
        raise DataTableParseError(
            f"expected '{{' after parent label {parent!r} near line {index + 1}"
        )
    if opening_line is None:
        raise DataTableParseError(f"opening brace not found for parent {parent!r}")

    for index in range(opening_line + 1, len(lines)):
        code, _ = _strip_comment(lines[index])
        stripped = code.strip()
        if not stripped:
            continue
        depth += stripped.count("{")
        depth -= stripped.count("}")
        if depth <= 0:
            break
        if depth == 1 and _label_name(lines[index]) == child_label:
            return index, opening_line, child_label

    raise DataTableParseError(f"local label not found: {label}")


def parse_source_data_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    directive: str = "db",
    entry_count: int,
    stop_before_label: str | None = None,
    source_file: str = "<memory>",
    source_revision: str = "unspecified",
) -> list[DataTableEntry]:
    """Parse exactly entry_count source values from a named Asar data table.

    A qualified local label (Parent.local) requires a brace-delimited parent.
    entry_count is mandatory so a local subtable cannot accidentally consume
    adjacent data. stop_before_label can additionally require a known following
    label, ensuring that the parsed segment ends at an expected boundary.
    Expressions are preserved as written; only simple numeric literals get a
    numeric_value. No expression is evaluated.
    """
    normalized_directive = directive.lower() if isinstance(directive, str) else ""
    if normalized_directive not in DATA_DIRECTIVE_WIDTHS:
        raise ValueError("directive must be 'db', 'dw', or 'dl'")
    if isinstance(table_file_offset, bool) or not isinstance(table_file_offset, int):
        raise TypeError("table_file_offset must be an integer")
    if table_file_offset < 0:
        raise ValueError("table_file_offset must be non-negative")
    if isinstance(entry_count, bool) or not isinstance(entry_count, int):
        raise TypeError("entry_count must be an integer")
    if entry_count <= 0:
        raise ValueError("entry_count must be positive")
    if not source_file:
        raise ValueError("source_file must be non-empty")
    if not source_revision:
        raise ValueError("source_revision must be non-empty")

    lines = source.splitlines()
    target_line, opening_line, target_name = _find_target_label(lines, label)
    start_line = target_line + 1

    if stop_before_label is not None:
        if not stop_before_label or any(c.isspace() for c in stop_before_label):
            raise ValueError("stop_before_label must be a non-empty label")
        stop_name = stop_before_label
    else:
        stop_name = None

    entries: list[DataTableEntry] = []
    active_label = target_name
    in_brace_block = opening_line is not None
    depth = 1 if in_brace_block else 0

    for index in range(start_line, len(lines)):
        original_line = lines[index]
        code, inline_comment = _strip_comment(original_line)
        stripped = code.strip()
        if not stripped:
            continue

        if in_brace_block:
            depth += stripped.count("{")
            depth -= stripped.count("}")
            if depth <= 0:
                if len(entries) != entry_count:
                    raise DataTableParseError(
                        f"table {label!r} ended after {len(entries)} entries; "
                        f"expected {entry_count}"
                    )
                return entries
            if depth != 1:
                raise DataTableParseError(
                    f"nested block encountered while parsing {label!r} on line {index + 1}"
                )

        current_label = _label_name(original_line)
        if current_label is not None:
            if current_label == stop_name or (
                stop_name is not None and current_label.lstrip(".") == stop_name.lstrip(".")
            ):
                if len(entries) != entry_count:
                    raise DataTableParseError(
                        f"table {label!r} reached stop label {stop_name!r} after "
                        f"{len(entries)} entries; expected {entry_count}"
                    )
                return entries

            # The sublabels inside one scalar table annotate contiguous value
            # groups; retain the last label on each value record.
            if current_label.startswith(".") or not in_brace_block:
                active_label = current_label
            elif current_label != label:
                if entries:
                    if len(entries) != entry_count:
                        raise DataTableParseError(
                            f"table {label!r} reached next label {current_label!r} "
                            f"after {len(entries)} entries; expected {entry_count}"
                        )
                    return entries
                active_label = current_label
            continue

        directive_match = _DIRECTIVE_RE.fullmatch(stripped)
        if directive_match is None:
            continue
        actual_directive = directive_match.group("directive").lower()
        if actual_directive != normalized_directive:
            raise DataTableParseError(
                f"expected {normalized_directive} but found {actual_directive} "
                f"on line {index + 1}"
            )

        values = directive_match.group("values").strip()
        expressions = [value.strip() for value in values.split(",")]
        if not values or any(not expression for expression in expressions):
            raise DataTableParseError(
                f"malformed {normalized_directive} directive on line {index + 1}"
            )
        if len(entries) + len(expressions) > entry_count:
            raise DataTableParseError(
                f"table {label!r} contains more than the expected {entry_count} entries"
            )

        for expression in expressions:
            entries.append(
                DataTableEntry(
                    table_index=len(entries),
                    entry_file_offset=table_file_offset
                    + len(entries) * DATA_DIRECTIVE_WIDTHS[normalized_directive],
                    source_line=index + 1,
                    directive=normalized_directive,
                    source_label=active_label,
                    expression=expression,
                    numeric_value=_parse_numeric_literal(expression),
                    inline_comment=inline_comment,
                    source_revision=source_revision,
                )
            )

        if len(entries) == entry_count and stop_name is None:
            return entries

    raise DataTableParseError(
        f"table {label!r} ended at end-of-source after {len(entries)} entries; "
        f"expected {entry_count}"
    )
