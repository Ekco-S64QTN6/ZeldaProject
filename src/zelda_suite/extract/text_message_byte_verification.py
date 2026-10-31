"""Read-only verification of raw encoded message bytes against pinned source literals."""
from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any

from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    read_rom_bytes,
    sha256_rom_bytes,
)
from zelda_suite.extract.text_message_index import (
    MessageSourceBlock,
    TextMessageIndexError,
    parse_text_message_index,
)

TEXT_MESSAGE_BYTE_VERIFICATION_FORMAT = "zelda-suite-text-message-byte-verification"
PINNED_TEXT_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
MAIN_MESSAGE_BLOCK_LABEL = "Message_Data"
MAIN_MESSAGE_SOURCE_FILE = "Bank1C.asm"
MAIN_MESSAGE_START_OFFSET = 0x0E0000
MAIN_MESSAGE_END_OFFSET = 0x0E7F29
EXTRA_MESSAGE_BLOCK_LABEL = "Message_DataExtra"
EXTRA_MESSAGE_SOURCE_FILE = "Bank0E.asm"
EXTRA_MESSAGE_START_OFFSET = 0x075F40
EXTRA_MESSAGE_END_OFFSET = 0x076E21

_GLOBAL_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_MESSAGE_LABEL_RE = re.compile(r"^\s*Message_(?P<id>[0-9A-Fa-f]{4})\s*:\s*$")
_DB_DIRECTIVE_RE = re.compile(r"^\s*db\s+(?P<values>.*?)\s*$", re.IGNORECASE)
_BYTE_LITERAL_RE = re.compile(r"\$([0-9A-Fa-f]{1,2})\Z")


class TextMessageByteVerificationError(ValueError):
    """Raised when encoded message source bytes or ROM offsets cannot be checked safely."""


def default_text_message_source_blocks(
    main_source_text: str,
    extra_source_text: str,
) -> list[MessageSourceBlock]:
    """Build source block inputs for the pinned main and extra message regions."""
    return [
        MessageSourceBlock(
            source_file=MAIN_MESSAGE_SOURCE_FILE,
            block_label=MAIN_MESSAGE_BLOCK_LABEL,
            block_start_offset=MAIN_MESSAGE_START_OFFSET,
            block_end_offset=MAIN_MESSAGE_END_OFFSET,
            source_text=main_source_text,
        ),
        MessageSourceBlock(
            source_file=EXTRA_MESSAGE_SOURCE_FILE,
            block_label=EXTRA_MESSAGE_BLOCK_LABEL,
            block_start_offset=EXTRA_MESSAGE_START_OFFSET,
            block_end_offset=EXTRA_MESSAGE_END_OFFSET,
            source_text=extra_source_text,
        ),
    ]


def _source_code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _find_bounded_region(lines: list[str], block_label: str) -> tuple[int, int]:
    label_hits = [
        index
        for index, line in enumerate(lines)
        if (match := _GLOBAL_LABEL_RE.fullmatch(_source_code(line))) is not None
        and match.group("label") == block_label
    ]
    if len(label_hits) != 1:
        raise TextMessageByteVerificationError(
            f"expected exactly one {block_label!r} label; found {len(label_hits)}"
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
        raise TextMessageByteVerificationError(
            f"expected '{{' after {block_label!r} near line {index + 1}"
        )
    if opening_line is None:
        raise TextMessageByteVerificationError(
            f"opening brace not found for {block_label!r}"
        )

    depth = 1
    for index in range(opening_line + 1, len(lines)):
        code = _source_code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return opening_line + 1, index
        if depth < 0:
            raise TextMessageByteVerificationError(
                f"unexpected closing brace in {block_label!r} on line {index + 1}"
            )
    raise TextMessageByteVerificationError(f"closing brace not found for {block_label!r}")


def _parse_message_bytes(
    block: MessageSourceBlock,
    source_messages: list[dict[str, Any]],
) -> dict[str, bytes]:
    """Parse literal db bytes from a bounded block without decoding their meaning."""
    lines = block.source_text.splitlines()
    start_line, end_line = _find_bounded_region(lines, block.block_label)
    messages_by_line = {
        message["source_line"]: message
        for message in source_messages
        if message["source_file"] == block.source_file
        and message["data_block_label"] == block.block_label
    }
    parsed: dict[str, bytearray] = {}
    current_label: str | None = None

    for line_index in range(start_line, end_line):
        code = _source_code(lines[line_index])
        if not code or code in {"{", "}"}:
            continue

        message_match = _MESSAGE_LABEL_RE.fullmatch(code)
        if message_match is not None:
            message_id = int(message_match.group("id"), 16)
            label = f"Message_{message_match.group('id').upper()}"
            source_line = line_index + 1
            metadata = messages_by_line.get(source_line)
            if metadata is None or metadata["message_label"] != label:
                raise TextMessageByteVerificationError(
                    f"{block.source_file}:{source_line} message label {label} "
                    "does not match the source index"
                )
            if label in parsed:
                raise TextMessageByteVerificationError(
                    f"duplicate message label {label} in {block.source_file}"
                )
            parsed[label] = bytearray()
            current_label = label
            if metadata["message_id"] != message_id:
                raise TextMessageByteVerificationError(
                    f"{block.source_file}:{source_line} message ID does not match its label"
                )
            continue

        directive_match = _DB_DIRECTIVE_RE.fullmatch(code)
        if directive_match is None:
            raise TextMessageByteVerificationError(
                f"unsupported syntax in {block.source_file}:{line_index + 1}: {code!r}; "
                "only literal db bytes are accepted inside message-data blocks"
            )
        if current_label is None:
            raise TextMessageByteVerificationError(
                f"data directive appears before the first message label at "
                f"{block.source_file}:{line_index + 1}"
            )

        values_text = directive_match.group("values")
        values = [value.strip() for value in values_text.split(",")]
        if not values_text.strip() or any(not value for value in values):
            raise TextMessageByteVerificationError(
                f"malformed db directive at {block.source_file}:{line_index + 1}"
            )
        for value in values:
            match = _BYTE_LITERAL_RE.fullmatch(value)
            if match is None:
                raise TextMessageByteVerificationError(
                    f"unsupported byte expression {value!r} at "
                    f"{block.source_file}:{line_index + 1}; assembler expressions "
                    "are not evaluated"
                )
            parsed[current_label].append(int(match.group(1), 16))

    expected_labels = {message["message_label"] for message in source_messages
                       if message["source_file"] == block.source_file
                       and message["data_block_label"] == block.block_label}
    if set(parsed) != expected_labels:
        missing = sorted(expected_labels - set(parsed))
        unexpected = sorted(set(parsed) - expected_labels)
        raise TextMessageByteVerificationError(
            f"parsed labels do not match the message index for "
            f"{block.source_file}:{block.block_label}; "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )

    for message in source_messages:
        if message["source_file"] != block.source_file or message["data_block_label"] != block.block_label:
            continue
        actual_count = len(parsed[message["message_label"]])
        if actual_count != message["declared_byte_count"]:
            raise TextMessageByteVerificationError(
                f"{block.source_file}:{message['message_label']} parsed {actual_count} "
                f"literal bytes but the source index declares {message['declared_byte_count']}"
            )
        if actual_count == 0:
            raise TextMessageByteVerificationError(
                f"{block.source_file}:{message['message_label']} has no literal bytes"
            )

    return {label: bytes(values) for label, values in parsed.items()}


def parse_source_message_bytes(
    source_blocks: list[MessageSourceBlock],
    *,
    source_revision: str = PINNED_TEXT_SOURCE_REVISION,
) -> list[dict[str, Any]]:
    """Every message's literal source bytes, in index order, without a ROM.

    Each entry carries the index fields (`message_id`, `message_label`,
    `source_file`, `data_block_label`, `source_line`) plus `data` (bytes) and
    `sequential_file_offset` (its block start plus the bytes declared before it).
    No bytes are interpreted.
    """
    index = parse_text_message_index(source_blocks, source_revision=source_revision)
    out: list[dict[str, Any]] = []
    for block in source_blocks:
        block_messages = [
            message.to_dict()
            for message in index.messages
            if message.source_file == block.source_file
            and message.data_block_label == block.block_label
        ]
        parsed = _parse_message_bytes(block, block_messages)
        cursor = block.block_start_offset
        for message in block_messages:
            data = parsed.get(message["message_label"], b"")
            out.append({**message, "data": data, "sequential_file_offset": cursor})
            cursor += len(data)
    return sorted(out, key=lambda m: m["message_id"])


def verify_text_message_bytes(
    rom_path: str | Path,
    source_blocks: list[MessageSourceBlock],
    *,
    source_revision: str = PINNED_TEXT_SOURCE_REVISION,
) -> dict[str, Any]:
    """Compare every source-literal message byte with a local ROM without decoding text.

    Source block starts are taken from the pinned disassembly declarations. The
    function checks literal bytes only; it does not interpret character codes,
    dictionary compression, message control tokens, or source offset annotations
    as authoritative ROM locations.
    """
    if not source_blocks:
        raise TextMessageByteVerificationError("source_blocks must not be empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise TextMessageByteVerificationError("source_revision must be non-empty")

    image_path = Path(rom_path)
    if not image_path.is_file():
        raise TextMessageByteVerificationError(f"ROM path is not a file: {image_path}")
    try:
        rom = read_rom_bytes(image_path)
    except ROMImageInspectionError as exc:
        raise TextMessageByteVerificationError(str(exc)) from exc
    if len(rom) != EXPECTED_US_ROM_SIZE:
        raise TextMessageByteVerificationError(
            "ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(rom):,}. "
            "Use inspect-rom to diagnose the file; do not adjust it automatically."
        )

    try:
        index = parse_text_message_index(
            source_blocks,
            source_revision=source_revision,
        )
    except (TextMessageIndexError, OSError, UnicodeError, TypeError, ValueError) as exc:
        raise TextMessageByteVerificationError(str(exc)) from exc

    ordered_blocks = sorted(
        index.source_blocks,
        key=lambda block: block.block_start_offset,
    )
    for block_record in ordered_blocks:
        if block_record.block_end_offset >= len(rom):
            raise TextMessageByteVerificationError(
                f"{block_record.source_file}:{block_record.data_block_label} declared range "
                f"0x{block_record.block_start_offset:06X}–0x{block_record.block_end_offset:06X} "
                "extends beyond the ROM image"
            )
        if block_record.declared_byte_count_total > block_record.block_size_bytes:
            excess = block_record.declared_byte_count_total - block_record.block_size_bytes
            raise TextMessageByteVerificationError(
                f"{block_record.source_file}:{block_record.data_block_label} contains "
                f"{excess} literal byte(s) beyond its declared source block range"
            )
    for previous, current in itertools.pairwise(ordered_blocks):
        if current.block_start_offset <= previous.block_end_offset:
            raise TextMessageByteVerificationError(
                "source block offset ranges overlap: "
                f"{previous.source_file}:{previous.data_block_label} "
                f"(0x{previous.block_start_offset:06X}–0x{previous.block_end_offset:06X}) and "
                f"{current.source_file}:{current.data_block_label} "
                f"(0x{current.block_start_offset:06X}–0x{current.block_end_offset:06X})"
            )

    source_bytes_by_label: dict[tuple[str, str, str], bytes] = {}
    for block in source_blocks:
        block_messages = [
            message.to_dict()
            for message in index.messages
            if message.source_file == block.source_file
            and message.data_block_label == block.block_label
        ]
        parsed = _parse_message_bytes(block, block_messages)
        for message_label, data in parsed.items():
            source_bytes_by_label[(block.source_file, block.block_label, message_label)] = data

    entries: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    checked_byte_count = 0
    mismatch_byte_count = 0
    message_mismatch_count = 0
    per_block: dict[tuple[str, str], dict[str, Any]] = {}

    for block_record in index.source_blocks:
        per_block[(block_record.source_file, block_record.data_block_label)] = {
            "source_file": block_record.source_file,
            "block_label": block_record.data_block_label,
            "block_start_offset": block_record.block_start_offset,
            "block_end_offset": block_record.block_end_offset,
            "block_range_byte_count": block_record.block_size_bytes,
            "source_literal_byte_count": block_record.declared_byte_count_total,
            "message_count": block_record.message_count,
            "block_size_matches_source_bytes": block_record.declared_bytes_match_block_size,
            "range_minus_source_bytes": (
                block_record.block_size_bytes - block_record.declared_byte_count_total
            ),
            "checked_byte_count": 0,
            "mismatch_byte_count": 0,
        }

    source_findings: list[dict[str, Any]] = []
    for block_record in index.source_blocks:
        if not block_record.declared_bytes_match_block_size:
            difference = (
                block_record.block_size_bytes - block_record.declared_byte_count_total
            )
            source_findings.append({
                "code": "block_size_mismatch",
                "severity": "warning",
                "source_file": block_record.source_file,
                "block_label": block_record.data_block_label,
                "block_start_offset": block_record.block_start_offset,
                "block_end_offset": block_record.block_end_offset,
                "block_range_byte_count": block_record.block_size_bytes,
                "source_literal_byte_count": block_record.declared_byte_count_total,
                "difference_bytes": difference,
                "message": (
                    f"Source block range spans {block_record.block_size_bytes} byte(s), while "
                    f"its literal message data contains {block_record.declared_byte_count_total} "
                    f"byte(s); range exceeds source bytes by {difference} byte(s)."
                ),
            })

    offset_mismatch_count = 0
    invalid_offset_annotation_count = 0
    missing_offset_annotation_count = 0
    for message in index.messages:
        if message.source_offset_annotation is None:
            missing_offset_annotation_count += 1
        elif message.source_offset_matches_sequential is False:
            offset_mismatch_count += 1
            if message.source_offset_annotation_valid is False:
                invalid_offset_annotation_count += 1
            source_findings.append({
                "code": (
                    "invalid_offset_annotation"
                    if message.source_offset_annotation_valid is False
                    else "offset_annotation_mismatch"
                ),
                "severity": "warning",
                "source_file": message.source_file,
                "block_label": message.data_block_label,
                "message_id": message.message_id,
                "message_label": message.message_label,
                "source_line": message.source_line,
                "source_offset_annotation": message.source_offset_annotation,
                "sequential_file_offset": message.sequential_file_offset,
                "message": (
                    "Source offset annotation is malformed or outside the block range."
                    if message.source_offset_annotation_valid is False
                    else "Source offset annotation differs from the sequential source-derived offset."
                ),
            })

        expected = source_bytes_by_label[
            (message.source_file, message.data_block_label, message.message_label)
        ]
        start = message.sequential_file_offset
        end = start + len(expected)
        if end > len(rom):
            raise TextMessageByteVerificationError(
                f"{message.source_file}:{message.message_label} range "
                f"0x{start:06X}–0x{end - 1:06X} lies outside the ROM image"
            )
        actual = rom[start:end]
        checked_byte_count += len(expected)
        block_summary = per_block[(message.source_file, message.data_block_label)]
        block_summary["checked_byte_count"] += len(expected)
        message_mismatches = 0
        for byte_index, (expected_byte, actual_byte) in enumerate(zip(expected, actual)):
            if expected_byte == actual_byte:
                continue
            message_mismatches += 1
            mismatch_byte_count += 1
            mismatch = {
                "source_file": message.source_file,
                "block_label": message.data_block_label,
                "message_index": message.message_index,
                "message_id": message.message_id,
                "message_label": message.message_label,
                "source_line": message.source_line,
                "offset": start + byte_index,
                "offset_in_message": byte_index,
                "expected_byte": "$" + format(expected_byte, "02X"),
                "actual_byte": "$" + format(actual_byte, "02X"),
            }
            mismatches.append(mismatch)
        block_summary["mismatch_byte_count"] += message_mismatches
        if message_mismatches:
            message_mismatch_count += 1
        entries.append({
            "message_index": message.message_index,
            "message_id": message.message_id,
            "message_label": message.message_label,
            "source_file": message.source_file,
            "block_label": message.data_block_label,
            "source_line": message.source_line,
            "sequential_file_offset": start,
            "source_offset_annotation": message.source_offset_annotation,
            "source_offset_annotation_valid": message.source_offset_annotation_valid,
            "source_offset_matches_sequential": message.source_offset_matches_sequential,
            "source_byte_count": len(expected),
            "checked_byte_count": len(expected),
            "mismatch_byte_count": message_mismatches,
            "status": "fail" if message_mismatches else "pass",
        })

    return {
        "format": TEXT_MESSAGE_BYTE_VERIFICATION_FORMAT,
        "format_version": 1,
        "rom": {
            "filename": image_path.name,
            "size_bytes": len(rom),
            "sha256": sha256_rom_bytes(rom),
            "header_assessment": "headerless-by-expected-size",
            "provenance_verified": False,
        },
        "source_revision": source_revision,
        "source_blocks": list(per_block.values()),
        "summary": {
            "source_block_count": len(source_blocks),
            "message_count": len(index.messages),
            "checked_byte_count": checked_byte_count,
            "mismatch_byte_count": mismatch_byte_count,
            "message_mismatch_count": message_mismatch_count,
            "block_size_mismatch_count": sum(
                not block.declared_bytes_match_block_size for block in index.source_blocks
            ),
            "offset_annotation_mismatch_count": offset_mismatch_count,
            "invalid_offset_annotation_count": invalid_offset_annotation_count,
            "missing_offset_annotation_count": missing_offset_annotation_count,
            "source_finding_count": len(source_findings),
        },
        "entries": entries,
        "mismatches": mismatches,
        "source_findings": source_findings,
        "source_only": False,
        "rom_bytes_read": True,
        "encoded_bytes_compared": True,
        "semantic_text_decoded": False,
        "rom_provenance_verified": False,
        "source_offsets_verified": False,
        "rom_modified": False,
    }
