"""Index source message labels without copying encoded message bytes.

The index preserves raw source offset comments alongside offsets inferred by
counting declared data values. It is metadata for audit and discovery only.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from zelda_suite.extract.data_table import DATA_DIRECTIVE_WIDTHS

_MESSAGE_LABEL_RE = re.compile(
    r"^\s*Message_(?P<id>[0-9A-Fa-f]{4})\s*:\s*$"
)
_GLOBAL_LABEL_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$"
)
_OFFSET_ANNOTATION_RE = re.compile(r"^\s*;\s*\$(?P<digits>[0-9A-Fa-f]+)\s*$")
_DATA_DIRECTIVE_RE = re.compile(
    r"^\s*(?P<directive>db|dw|dl)\s+(?P<values>.*?)\s*$",
    re.IGNORECASE,
)


class TextMessageIndexError(ValueError):
    """Raised when source message boundaries are ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class MessageSourceBlock:
    """Input block specification; source text is used only during parsing."""

    source_file: str
    block_label: str
    block_start_offset: int
    block_end_offset: int
    source_text: str


@dataclass(frozen=True, slots=True)
class TextMessageRecord:
    """Metadata for one message label, without its encoded byte payload."""

    message_index: int
    message_id: int
    message_label: str
    source_file: str
    data_block_label: str
    source_line: int
    source_offset_annotation: str | None
    annotated_file_offset: int | None
    source_offset_annotation_valid: bool | None
    source_offset_matches_sequential: bool | None
    sequential_file_offset: int
    declared_byte_count: int
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable message record."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TextMessageBlockRecord:
    """Size and count summary for one ROM-resident message block."""

    source_file: str
    data_block_label: str
    block_start_offset: int
    block_end_offset: int
    block_size_bytes: int
    message_count: int
    declared_byte_count_total: int
    declared_bytes_match_block_size: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable block summary."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TextMessageIndex:
    """Combined message index from one or more pinned source blocks."""

    source_revision: str
    source_blocks: list[TextMessageBlockRecord]
    messages: list[TextMessageRecord]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned JSON export."""
        return {
            "format": "zelda-suite-text-message-index",
            "format_version": 1,
            "source_revision": self.source_revision,
            "source_block_count": len(self.source_blocks),
            "source_blocks": [block.to_dict() for block in self.source_blocks],
            "message_count": len(self.messages),
            "messages": [message.to_dict() for message in self.messages],
        }


def _code(line: str) -> str:
    """Remove an assembly comment from one source line."""
    return line.split(";", 1)[0].strip()


def _find_block(
    lines: list[str], block_label: str
) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", block_label):
        raise ValueError("block_label must be a global assembly identifier")

    label_line: int | None = None
    for index, line in enumerate(lines):
        match = _GLOBAL_LABEL_RE.fullmatch(_code(line))
        if match is not None and match.group("label") == block_label:
            label_line = index
            break
    if label_line is None:
        raise TextMessageIndexError(f"source block label not found: {block_label}")

    opening_line: int | None = None
    for index in range(label_line + 1, len(lines)):
        code = _code(lines[index])
        if not code:
            continue
        if code == "{":
            opening_line = index
            break
        raise TextMessageIndexError(
            f"expected '{{' after block label {block_label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise TextMessageIndexError(f"opening brace not found for {block_label!r}")

    depth = 1
    for index in range(opening_line + 1, len(lines)):
        code = _code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return opening_line + 1, index
        if depth < 0:
            raise TextMessageIndexError(
                f"unexpected closing brace in {block_label!r} on line {index + 1}"
            )
    raise TextMessageIndexError(f"closing brace not found for {block_label!r}")


def _find_offset_annotation(
    lines: list[str], message_line: int, block_start_line: int
) -> tuple[str | None, int | None]:
    """Read the closest standalone address comment before a message label."""
    for index in range(message_line - 1, block_start_line - 1, -1):
        match = _OFFSET_ANNOTATION_RE.fullmatch(lines[index])
        if match is not None:
            digits = match.group("digits")
            return "$" + digits, int(digits, 16)
        if _code(lines[index]):
            break
    return None, None


def _declared_message_bytes(
    lines: list[str], start_line: int, end_line: int, label: str
) -> int:
    declared_bytes = 0
    for index in range(start_line + 1, end_line):
        code = _code(lines[index])
        if not code or code in {"{", "}"}:
            continue

        match = _DATA_DIRECTIVE_RE.fullmatch(code)
        if match is None:
            raise TextMessageIndexError(
                f"unsupported syntax in message {label!r} on line {index + 1}: {code!r}"
            )
        directive = match.group("directive").lower()
        values = [value.strip() for value in match.group("values").split(",")]
        if not match.group("values").strip() or any(not value for value in values):
            raise TextMessageIndexError(
                f"malformed {directive} directive in message {label!r} "
                f"on line {index + 1}"
            )
        declared_bytes += len(values) * DATA_DIRECTIVE_WIDTHS[directive]

    if declared_bytes <= 0:
        raise TextMessageIndexError(f"message {label!r} contains no data values")
    return declared_bytes


def parse_text_message_index(
    source_blocks: list[MessageSourceBlock],
    *,
    source_revision: str,
) -> TextMessageIndex:
    """Parse multiple source blocks into a message index.

    The caller supplies the source block offset range from the pinned
    disassembly header comment. The parser counts declared data values and
    computes a sequential source-derived offset for each message. It records
    source offset comments separately and flags malformed or inconsistent
    annotations rather than silently trusting or correcting them.
    """
    if not source_blocks:
        raise ValueError("source_blocks must not be empty")
    if not source_revision:
        raise ValueError("source_revision must be non-empty")

    block_records: list[TextMessageBlockRecord] = []
    message_records: list[TextMessageRecord] = []
    seen_messages: set[int] = set()
    seen_blocks: set[tuple[str, str]] = set()

    for block in source_blocks:
        if not block.source_file:
            raise ValueError("source_file must be non-empty")
        if isinstance(block.block_start_offset, bool) or not isinstance(
            block.block_start_offset, int
        ):
            raise TypeError("block_start_offset must be an integer")
        if isinstance(block.block_end_offset, bool) or not isinstance(
            block.block_end_offset, int
        ):
            raise TypeError("block_end_offset must be an integer")
        if block.block_start_offset < 0:
            raise ValueError("block_start_offset must be non-negative")
        if block.block_end_offset < block.block_start_offset:
            raise ValueError("block_end_offset must not precede block_start_offset")

        block_identity = (block.source_file, block.block_label)
        if block_identity in seen_blocks:
            raise ValueError(f"duplicate source block: {block.source_file}:{block.block_label}")
        seen_blocks.add(block_identity)

        lines = block.source_text.splitlines()
        block_start_line, block_end_line = _find_block(lines, block.block_label)
        message_labels: list[tuple[int, int, str]] = []
        for index in range(block_start_line, block_end_line):
            match = _MESSAGE_LABEL_RE.fullmatch(_code(lines[index]))
            if match is None:
                continue
            message_id = int(match.group("id"), 16)
            message_label = f"Message_{match.group('id').upper()}"
            if message_id in seen_messages:
                raise TextMessageIndexError(f"duplicate message ID: {message_label}")
            seen_messages.add(message_id)
            message_labels.append((index, message_id, message_label))

        if not message_labels:
            raise TextMessageIndexError(
                f"no Message_#### labels found inside {block.block_label!r}"
            )

        block_bytes = 0
        sequential_offset = block.block_start_offset
        block_message_records: list[TextMessageRecord] = []

        for position, (line_index, message_id, label) in enumerate(message_labels):
            next_line = (
                message_labels[position + 1][0]
                if position + 1 < len(message_labels)
                else block_end_line
            )
            byte_count = _declared_message_bytes(
                lines, line_index, next_line, label
            )
            annotation, annotation_value = _find_offset_annotation(
                lines, line_index, block_start_line
            )
            annotation_valid: bool | None
            if annotation is None or annotation_value is None:
                annotation_valid = None
                annotated_offset = None
                annotation_matches = None
            else:
                annotation_valid = (
                    len(annotation) == 7
                    and block.block_start_offset <= annotation_value <= block.block_end_offset
                )
                annotated_offset = annotation_value if annotation_valid else None
                annotation_matches = annotated_offset == sequential_offset

            record = TextMessageRecord(
                message_index=len(message_records) + len(block_message_records),
                message_id=message_id,
                message_label=label,
                source_file=block.source_file,
                data_block_label=block.block_label,
                source_line=line_index + 1,
                source_offset_annotation=annotation,
                annotated_file_offset=annotated_offset,
                source_offset_annotation_valid=annotation_valid,
                source_offset_matches_sequential=annotation_matches,
                sequential_file_offset=sequential_offset,
                declared_byte_count=byte_count,
                source_revision=source_revision,
            )
            block_message_records.append(record)
            block_bytes += byte_count
            sequential_offset += byte_count

        block_size = block.block_end_offset - block.block_start_offset + 1
        block_records.append(
            TextMessageBlockRecord(
                source_file=block.source_file,
                data_block_label=block.block_label,
                block_start_offset=block.block_start_offset,
                block_end_offset=block.block_end_offset,
                block_size_bytes=block_size,
                message_count=len(block_message_records),
                declared_byte_count_total=block_bytes,
                declared_bytes_match_block_size=block_bytes == block_size,
            )
        )
        message_records.extend(block_message_records)

    return TextMessageIndex(
        source_revision=source_revision,
        source_blocks=block_records,
        messages=message_records,
    )
