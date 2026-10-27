"""Inventory Asar incbin source declarations without reading payload bytes.

This helper records source annotations for future extraction planning. It does
not open the paths in incbin directives or assert that those payloads exist.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_ADDRESS_COMMENT_RE = re.compile(
    r"^\s*;\s*\$(?P<start>[0-9A-Fa-f]+)"
    r"(?:\\s*-\\s*\\$(?P<end>[0-9A-Fa-f]+))?(?:\\s+.*)?\\s*$"
)
_INCBIN_RE = re.compile(
    r'^\s*incbin\s+"(?P<path>[^"]+)"(?P<tail>.*)$',
    re.IGNORECASE,
)
_SIZE_RE = re.compile(
    r"\bSize\s*:\s*(?P<size>[^\s;]+)",
    re.IGNORECASE,
)


class IncbinInventoryError(ValueError):
    """Raised when a source-level incbin declaration cannot be inventoried."""


@dataclass(frozen=True, slots=True)
class IncbinDeclaration:
    """An incbin declaration with source comments kept distinct from calculations."""

    source_file: str
    source_revision: str
    label: str
    source_line: int
    incbin_path: str
    declared_size_bytes: int | None
    source_file_offset_start: int | None
    source_file_offset_end: int | None
    computed_file_offset_end: int | None
    source_range_size_matches: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Return this record as a JSON-serializable dictionary."""
        return asdict(self)


def _parse_integer(token: str) -> int:
    if token.startswith("$"):
        return int(token[1:], 16)
    if token.lower().startswith("0x"):
        return int(token, 16)
    return int(token, 10)


def _parse_declared_size(tail: str, source_line: int) -> int | None:
    match = _SIZE_RE.search(tail)
    if match is None:
        return None

    try:
        size = _parse_integer(match.group("size"))
    except ValueError as exc:
        raise IncbinInventoryError(
            f"invalid incbin size annotation on line {source_line}"
        ) from exc

    if size < 0:
        raise IncbinInventoryError(
            f"incbin size must be non-negative on line {source_line}"
        )
    return size


def parse_incbin_inventory(
    source: str,
    *,
    source_file: str = "<memory>",
    source_revision: str = "unspecified",
) -> list[IncbinDeclaration]:
    """Inventory labelled Asar `incbin` declarations in source order.

    File-offset comments such as `;$058000-$058003 DATA` and single-start
    comments such as `;$050000` are retained as stated source metadata. If an
    explicit range and declared size disagree, the record reports
    `source_range_size_matches=False` rather than silently correcting either
    annotation. If the start and size are both available, a computed end offset
    is included separately from the source-comment end offset.

    The function never opens referenced payload paths and does not read or
    write ROM bytes.
    """
    declarations: list[IncbinDeclaration] = []
    pending_range_start: int | None = None
    pending_range_end: int | None = None
    current_label: str | None = None
    current_start: int | None = None
    current_end: int | None = None

    for line_number, line in enumerate(source.splitlines(), start=1):
        address_match = _ADDRESS_COMMENT_RE.fullmatch(line)
        if address_match is not None:
            start_offset = int(address_match.group("start"), 16)
            end_token = address_match.group("end")
            end_offset = int(end_token, 16) if end_token is not None else None
            if end_offset is not None and end_offset < start_offset:
                raise IncbinInventoryError(
                    f"source offset range ends before it starts on line {line_number}"
                )
            pending_range_start = start_offset
            pending_range_end = end_offset
            continue

        code = line.split(";", 1)[0]
        label_match = _LABEL_RE.fullmatch(code)
        if label_match is not None:
            current_label = label_match.group("label")
            current_start = pending_range_start
            current_end = pending_range_end
            pending_range_start = None
            pending_range_end = None
            continue

        incbin_match = _INCBIN_RE.fullmatch(line.rstrip())
        if incbin_match is None:
            continue

        if current_label is None:
            raise IncbinInventoryError(
                f"incbin declaration on line {line_number} has no preceding label"
            )

        declared_size = _parse_declared_size(
            incbin_match.group("tail"), line_number
        )
        computed_end = (
            current_start + declared_size - 1
            if current_start is not None
            and declared_size is not None
            and declared_size > 0
            else None
        )

        source_range_matches: bool | None = None
        if (
            current_start is not None
            and current_end is not None
            and declared_size is not None
        ):
            source_range_matches = (
                current_end - current_start + 1 == declared_size
            )

        declarations.append(
            IncbinDeclaration(
                source_file=source_file,
                source_revision=source_revision,
                label=current_label,
                source_line=line_number,
                incbin_path=incbin_match.group("path"),
                declared_size_bytes=declared_size,
                source_file_offset_start=current_start,
                source_file_offset_end=current_end,
                computed_file_offset_end=computed_end,
                source_range_size_matches=source_range_matches,
            )
        )
        current_label = None
        current_start = None
        current_end = None

    return declarations
