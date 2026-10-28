"""Parse mixed-width Asar data rows without evaluating expressions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from zelda_suite.extract.data_table import (
    DATA_DIRECTIVE_WIDTHS,
    DataTableParseError,
    _DATA_DIRECTIVE_RE,
    _SOURCE_LABEL_RE,
    _code,
    _label_hits,
    _literal_value,
)


class MixedDataTableParseError(DataTableParseError):
    """Raised when a mixed-width table is ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class MixedDataEntry:
    """One raw expression in a directive field."""

    entry_index: int
    entry_file_offset: int
    expression: str
    literal_value: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MixedDataField:
    """One db/dw/dl segment within a source row."""

    field_index: int
    field_file_offset: int
    source_line: int
    directive: str
    entry_width: int
    entry_count: int
    entries: tuple[MixedDataEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_index": self.field_index,
            "field_file_offset": self.field_file_offset,
            "source_line": self.source_line,
            "directive": self.directive,
            "entry_width": self.entry_width,
            "entry_count": self.entry_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class MixedDataRecord:
    """One source row composed of multiple directive fields."""

    record_index: int
    record_file_offset: int
    source_line: int
    source_label: str | None
    byte_length: int
    fields: tuple[MixedDataField, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_index": self.record_index,
            "record_file_offset": self.record_file_offset,
            "source_line": self.source_line,
            "source_label": self.source_label,
            "byte_length": self.byte_length,
            "fields": [field.to_dict() for field in self.fields],
        }


@dataclass(frozen=True, slots=True)
class MixedDataTable:
    """A source-commented mixed-width table with byte-accurate field offsets."""

    table_label: str
    table_file_offset: int
    records: tuple[MixedDataRecord, ...]

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def byte_count(self) -> int:
        return sum(record.byte_length for record in self.records)

    def to_dict(self, *, source_file: str, source_revision: str) -> dict[str, Any]:
        """Build the version-1 JSON export envelope for this table."""
        return {
            "format": "zelda-suite-mixed-data-table",
            "format_version": 1,
            "source_file": source_file,
            "source_revision": source_revision,
            "table_label": self.table_label,
            "table_file_offset": self.table_file_offset,
            "record_count": self.record_count,
            "byte_count": self.byte_count,
            "records": [record.to_dict() for record in self.records],
        }


def parse_mixed_data_table(
    source: str,
    label: str,
    table_file_offset: int,
    *,
    expected_record_count: int | None = None,
) -> MixedDataTable:
    """Parse a brace-delimited table whose rows combine db/dw/dl segments.

    A colon separates directive fields on one source line. Each data-bearing
    line becomes one record; expression widths determine all field and entry
    offsets. Expressions are retained verbatim and never evaluated.
    """
    if isinstance(table_file_offset, bool) or not isinstance(table_file_offset, int):
        raise TypeError("table_file_offset must be an integer")
    if table_file_offset < 0:
        raise ValueError("table_file_offset must be non-negative")
    if not isinstance(label, str) or _SOURCE_LABEL_RE.fullmatch(label) is None:
        raise ValueError("label must be a source assembly label")
    if expected_record_count is not None:
        if isinstance(expected_record_count, bool) or not isinstance(
            expected_record_count, int
        ):
            raise TypeError("expected_record_count must be an integer")
        if expected_record_count <= 0:
            raise ValueError("expected_record_count must be positive")

    lines = source.splitlines()
    hits = _label_hits(lines, label, 0, len(lines))
    if not hits:
        raise MixedDataTableParseError(f"label not found: {label}")
    if len(hits) > 1:
        matching_lines = ", ".join(str(index + 1) for index in hits)
        raise MixedDataTableParseError(
            f"label {label!r} occurs multiple times on lines {matching_lines}"
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
        raise MixedDataTableParseError(
            f"expected '{{' after label {label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise MixedDataTableParseError(f"opening brace not found for table {label!r}")

    depth = 1
    closing_line: int | None = None
    for index in range(opening_line + 1, len(lines)):
        code = _code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            closing_line = index
            break
        if depth < 0:
            raise MixedDataTableParseError(
                f"unexpected closing brace in table {label!r} on line {index + 1}"
            )
    if closing_line is None:
        raise MixedDataTableParseError(f"closing brace not found for table {label!r}")

    records: list[MixedDataRecord] = []
    active_source_label: str | None = label
    current_offset = table_file_offset

    for line_index in range(opening_line + 1, closing_line):
        code = _code(lines[line_index])
        if not code:
            continue
        if code in {"{", "}"}:
            raise MixedDataTableParseError(
                f"nested blocks are unsupported in mixed data table {label!r} "
                f"on line {line_index + 1}"
            )

        label_match = _SOURCE_LABEL_RE.fullmatch(code)
        if label_match is not None:
            active_source_label = label_match.group("label")
            continue

        segments = [segment.strip() for segment in code.split(":")]
        if any(not segment for segment in segments):
            raise MixedDataTableParseError(
                f"empty directive segment in table {label!r} on line {line_index + 1}"
            )

        record_offset = current_offset
        fields: list[MixedDataField] = []
        for segment in segments:
            directive_match = _DATA_DIRECTIVE_RE.fullmatch(segment)
            if directive_match is None:
                raise MixedDataTableParseError(
                    f"unsupported syntax in mixed data table {label!r} "
                    f"on line {line_index + 1}: {segment!r}"
                )

            directive = directive_match.group("directive").lower()
            width = DATA_DIRECTIVE_WIDTHS[directive]
            raw_values = directive_match.group("values").strip()
            if not raw_values:
                raise MixedDataTableParseError(
                    f"empty {directive} directive in table {label!r} "
                    f"on line {line_index + 1}"
                )
            expressions = [value.strip() for value in raw_values.split(",")]
            if any(not expression for expression in expressions):
                raise MixedDataTableParseError(
                    f"malformed {directive} directive in table {label!r} "
                    f"on line {line_index + 1}"
                )

            field_offset = current_offset
            entries: list[MixedDataEntry] = []
            literal_limit = 1 << (8 * width)
            for entry_index, expression in enumerate(expressions):
                literal_value = _literal_value(expression)
                if literal_value is not None and literal_value >= literal_limit:
                    raise MixedDataTableParseError(
                        f"literal {expression!r} exceeds {width}-byte directive width "
                        f"in table {label!r} on line {line_index + 1}"
                    )
                entries.append(
                    MixedDataEntry(
                        entry_index=entry_index,
                        entry_file_offset=current_offset,
                        expression=expression,
                        literal_value=literal_value,
                    )
                )
                current_offset += width

            fields.append(
                MixedDataField(
                    field_index=len(fields),
                    field_file_offset=field_offset,
                    source_line=line_index + 1,
                    directive=directive,
                    entry_width=width,
                    entry_count=len(entries),
                    entries=tuple(entries),
                )
            )

        records.append(
            MixedDataRecord(
                record_index=len(records),
                record_file_offset=record_offset,
                source_line=line_index + 1,
                source_label=active_source_label,
                byte_length=current_offset - record_offset,
                fields=tuple(fields),
            )
        )

    if not records:
        raise MixedDataTableParseError(f"mixed data table {label!r} is empty")
    if expected_record_count is not None and len(records) != expected_record_count:
        raise MixedDataTableParseError(
            f"expected {expected_record_count} records in mixed data table {label!r}, "
            f"found {len(records)}"
        )

    return MixedDataTable(
        table_label=label,
        table_file_offset=table_file_offset,
        records=tuple(records),
    )
