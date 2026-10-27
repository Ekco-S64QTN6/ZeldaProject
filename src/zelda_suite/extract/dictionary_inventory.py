"""Inventory text dictionary fragment labels and bounded source extents.

This helper emits metadata only. It counts source declarations and records
annotated offsets; it never stores or evaluates fragment bytes.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Any

from zelda_suite.extract.data_table import parse_data_table

_DATA_DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}
_GLOBAL_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_LOCAL_LABEL_RE = re.compile(r"^\s*(?P<label>\.[A-Za-z_][A-Za-z0-9_]*)\s*$")
_ADDRESS_COMMENT_RE = re.compile(r"^\s*;\s*\$(?P<offset>[0-9A-Fa-f]+)\s*$")
_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<directive>db|dw|dl)\s+(?P<values>.*?)\s*$",
    re.IGNORECASE,
)
_POINTER_TARGET_RE = re.compile(r"DictionaryEntries_(?P<suffix>[A-Za-z_][A-Za-z0-9_]*)\Z")


class DictionaryInventoryError(ValueError):
    """Raised when the source dictionary layout is ambiguous or inconsistent."""


@dataclass(frozen=True, slots=True)
class DictionaryFragment:
    """A symbolic dictionary pointer and its source-declared storage extent."""

    pointer_index: int
    pointer_entry_file_offset: int
    pointer_expression: str
    fragment_label: str
    fragment_source_line: int
    fragment_file_offset: int
    next_fragment_file_offset: int | None
    source_extent_bytes: int | None
    data_directive: str | None
    directive_value_count: int
    directive_width_bytes: int | None
    declared_payload_bytes: int | None
    source_extent_matches_directive: bool | None
    is_end_of_table: bool
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable record."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _FragmentSource:
    label: str
    label_line: int
    file_offset: int
    next_file_offset: int | None
    next_label_line: int | None
    data_directive: str | None
    directive_value_count: int
    directive_width_bytes: int | None
    declared_payload_bytes: int | None


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _find_block(lines: list[str], label: str) -> tuple[int, int]:
    """Return block interior start and exclusive closing-brace line."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label):
        raise ValueError("block label must be a global assembly identifier")

    label_line: int | None = None
    for index, line in enumerate(lines):
        match = _GLOBAL_LABEL_RE.fullmatch(_code(line))
        if match is not None and match.group("label") == label:
            label_line = index
            break
    if label_line is None:
        raise DictionaryInventoryError(f"label not found: {label}")

    opening_line: int | None = None
    for index in range(label_line + 1, len(lines)):
        code = _code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise DictionaryInventoryError(
            f"expected '{{' after label {label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise DictionaryInventoryError(f"opening brace not found for {label!r}")

    depth = 1
    for index in range(opening_line + 1, len(lines)):
        code = _code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return opening_line + 1, index
        if depth < 0:
            raise DictionaryInventoryError(
                f"unexpected closing brace in {label!r} on line {index + 1}"
            )
    raise DictionaryInventoryError(f"closing brace not found for {label!r}")


def _scan_fragment_sources(
    lines: list[str],
    *,
    data_label: str,
    source_start_offset: int,
) -> list[_FragmentSource]:
    interior_start, block_end = _find_block(lines, data_label)
    labels: list[tuple[str, int, int]] = []
    pending_offset: int | None = None

    for index in range(interior_start, block_end):
        address_comment = _ADDRESS_COMMENT_RE.fullmatch(lines[index])
        if address_comment is not None:
            pending_offset = int(address_comment.group("offset"), 16)
            continue

        code = _code(lines[index])
        local_match = _LOCAL_LABEL_RE.fullmatch(code)
        if local_match is None:
            continue
        if pending_offset is None:
            raise DictionaryInventoryError(
                f"missing source offset comment before local label "
                f"{local_match.group('label')!r} on line {index + 1}"
            )
        labels.append((local_match.group("label"), index, pending_offset))
        pending_offset = None

    if not labels:
        raise DictionaryInventoryError(f"no local fragments found under {data_label!r}")
    if labels[0][2] != source_start_offset:
        raise DictionaryInventoryError(
            f"first fragment offset is {labels[0][2]:#x}, expected {source_start_offset:#x}"
        )

    fragments: list[_FragmentSource] = []
    for position, (label, label_line, file_offset) in enumerate(labels):
        if position + 1 < len(labels):
            _, next_line, next_offset = labels[position + 1]
        else:
            next_line, next_offset = None, None

        directive: str | None = None
        value_count = 0
        width: int | None = None
        declared_bytes: int | None = None

        stop_line = next_line if next_line is not None else block_end
        for index in range(label_line + 1, stop_line):
            code = _code(lines[index])
            if not code:
                continue
            match = _DIRECTIVE_RE.fullmatch(code)
            if match is None:
                if code in {"{", "}"}:
                    continue
                raise DictionaryInventoryError(
                    f"unsupported syntax in fragment {label!r} on line {index + 1}: {code!r}"
                )
            if directive is not None:
                raise DictionaryInventoryError(
                    f"multiple data directives found for fragment {label!r}"
                )
            directive = match.group("directive").lower()
            expressions = [value.strip() for value in match.group("values").split(",")]
            if not match.group("values").strip() or any(not value for value in expressions):
                raise DictionaryInventoryError(
                    f"malformed {directive} directive in fragment {label!r} "
                    f"on line {index + 1}"
                )
            value_count = len(expressions)
            width = _DATA_DIRECTIVE_WIDTHS[directive]
            declared_bytes = value_count * width

        fragments.append(
            _FragmentSource(
                label=label,
                label_line=label_line,
                file_offset=file_offset,
                next_file_offset=next_offset,
                next_label_line=next_line,
                data_directive=directive,
                directive_value_count=value_count,
                directive_width_bytes=width,
                declared_payload_bytes=declared_bytes,
            )
        )

    for current, following in pairwise(fragments):
        if following.file_offset <= current.file_offset:
            raise DictionaryInventoryError(
                f"fragment offsets are not strictly increasing at {current.label!r}"
            )
    return fragments


def parse_dictionary_fragment_inventory(
    source: str,
    *,
    pointer_table_file_offset: int,
    data_file_offset: int,
    source_revision: str,
    pointer_table_label: str = "DictionaryPointers",
    data_label: str = "DictionaryEntries",
) -> list[DictionaryFragment]:
    """Pair text dictionary pointer expressions with source fragment metadata.

    The pointer table must use symbols shaped as DictionaryEntries_suffix,
    matching local labels .suffix in the containing data block. This function
    preserves those relationships and checks extents against source directive
    widths/counts, but does not store or interpret any fragment byte values or
    text comments.
    """
    if isinstance(pointer_table_file_offset, bool) or not isinstance(
        pointer_table_file_offset, int
    ):
        raise TypeError("pointer_table_file_offset must be an integer")
    if isinstance(data_file_offset, bool) or not isinstance(data_file_offset, int):
        raise TypeError("data_file_offset must be an integer")
    if pointer_table_file_offset < 0 or data_file_offset < 0:
        raise ValueError("source file offsets must be non-negative")
    if not source_revision:
        raise ValueError("source_revision must be non-empty")

    pointer_entries = parse_data_table(
        source,
        pointer_table_label,
        pointer_table_file_offset,
        directive="dw",
        source_revision=source_revision,
    )
    lines = source.splitlines()
    fragment_sources = _scan_fragment_sources(
        lines, data_label=data_label, source_start_offset=data_file_offset
    )
    fragments_by_label = {fragment.label: fragment for fragment in fragment_sources}
    if len(fragments_by_label) != len(fragment_sources):
        raise DictionaryInventoryError("duplicate local fragment labels found")

    results: list[DictionaryFragment] = []
    used_labels: set[str] = set()
    for pointer in pointer_entries:
        match = _POINTER_TARGET_RE.fullmatch(pointer.expression)
        if match is None:
            raise DictionaryInventoryError(
                f"unsupported dictionary pointer expression at index "
                f"{pointer.table_index}: {pointer.expression!r}"
            )
        local_label = f".{match.group('suffix')}"
        fragment = fragments_by_label.get(local_label)
        if fragment is None:
            raise DictionaryInventoryError(
                f"pointer {pointer.expression!r} has no corresponding fragment label "
                f"{local_label!r}"
            )
        used_labels.add(local_label)

        extent_bytes: int | None = None
        if fragment.next_file_offset is not None:
            extent_bytes = fragment.next_file_offset - fragment.file_offset
        matches_directive: bool | None = None
        if extent_bytes is not None and fragment.declared_payload_bytes is not None:
            matches_directive = extent_bytes == fragment.declared_payload_bytes

        results.append(
            DictionaryFragment(
                pointer_index=pointer.table_index,
                pointer_entry_file_offset=pointer.entry_file_offset,
                pointer_expression=pointer.expression,
                fragment_label=local_label,
                fragment_source_line=fragment.label_line + 1,
                fragment_file_offset=fragment.file_offset,
                next_fragment_file_offset=fragment.next_file_offset,
                source_extent_bytes=extent_bytes,
                data_directive=fragment.data_directive,
                directive_value_count=fragment.directive_value_count,
                directive_width_bytes=fragment.directive_width_bytes,
                declared_payload_bytes=fragment.declared_payload_bytes,
                source_extent_matches_directive=matches_directive,
                is_end_of_table=local_label == ".endOfTable",
                source_revision=source_revision,
            )
        )

    unused = sorted(set(fragments_by_label) - used_labels)
    if unused:
        raise DictionaryInventoryError(
            "source fragments are not referenced by the pointer table: "
            + ", ".join(unused)
        )
    return results
