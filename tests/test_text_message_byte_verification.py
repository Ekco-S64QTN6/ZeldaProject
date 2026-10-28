"""Tests for read-only byte comparison of pinned source message streams."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.text_message_index import MessageSourceBlock
from zelda_suite.extract.text_message_byte_verification import (
    TextMessageByteVerificationError,
    verify_text_message_bytes,
)
from zelda_suite.extract.rom_image import EXPECTED_US_ROM_SIZE

SYNTHETIC_MAIN = """Message_Data:
{
    ; $001000
    Message_0000:
    db $7F
    ; $001001
    Message_0001:
    db $01, $7F
}
"""
SYNTHETIC_EXTRA = """Message_DataExtra:
{
    ; $002000
    Message_0002:
    db $44, $7F
}
"""


def _source_blocks() -> list[MessageSourceBlock]:
    return [
        MessageSourceBlock(
            source_file="Bank1C.asm",
            block_label="Message_Data",
            block_start_offset=0x1000,
            block_end_offset=0x1002,
            source_text=SYNTHETIC_MAIN,
        ),
        MessageSourceBlock(
            source_file="Bank0E.asm",
            block_label="Message_DataExtra",
            block_start_offset=0x2000,
            block_end_offset=0x2002,
            source_text=SYNTHETIC_EXTRA,
        ),
    ]


def _write_rom(path: Path) -> Path:
    rom = bytearray(EXPECTED_US_ROM_SIZE)
    rom[0x1000:0x1003] = bytes([0x7F, 0x01, 0x7F])
    rom[0x2000:0x2002] = bytes([0x44, 0x7F])
    path.write_bytes(rom)
    return path


def test_verifier_compares_all_literal_bytes_and_keeps_block_size_warning(
    tmp_path: Path,
) -> None:
    rom_path = _write_rom(tmp_path / "synthetic.smc")
    before = rom_path.read_bytes()

    report = verify_text_message_bytes(
        rom_path,
        _source_blocks(),
        source_revision="synthetic-revision",
    )

    assert report["format"] == "zelda-suite-text-message-byte-verification"
    assert report["format_version"] == 1
    assert report["source_revision"] == "synthetic-revision"
    assert report["summary"] == {
        "source_block_count": 2,
        "message_count": 3,
        "checked_byte_count": 5,
        "mismatch_byte_count": 0,
        "message_mismatch_count": 0,
        "block_size_mismatch_count": 1,
        "offset_annotation_mismatch_count": 0,
        "invalid_offset_annotation_count": 0,
        "missing_offset_annotation_count": 0,
        "source_finding_count": 1,
    }
    assert report["source_blocks"][0]["source_file"] == "Bank1C.asm"
    assert report["source_blocks"][0]["block_size_matches_source_bytes"] is True
    assert report["source_blocks"][1]["block_size_matches_source_bytes"] is False
    assert report["source_blocks"][1]["range_minus_source_bytes"] == 1
    assert report["entries"][1]["message_id"] == 1
    assert report["entries"][1]["checked_byte_count"] == 2
    assert report["entries"][1]["status"] == "pass"
    assert report["mismatches"] == []
    assert report["source_findings"][0]["code"] == "block_size_mismatch"
    assert report["source_findings"][0]["difference_bytes"] == 1
    assert report["rom_bytes_read"] is True
    assert report["encoded_bytes_compared"] is True
    assert report["semantic_text_decoded"] is False
    assert report["rom_provenance_verified"] is False
    assert report["source_offsets_verified"] is False
    assert report["rom_modified"] is False
    assert rom_path.read_bytes() == before


def test_verifier_identifies_the_message_and_offset_of_a_byte_mismatch(
    tmp_path: Path,
) -> None:
    rom_path = _write_rom(tmp_path / "synthetic-mismatch.smc")
    rom = bytearray(rom_path.read_bytes())
    rom[0x1001] = 0x02
    rom_path.write_bytes(rom)

    report = verify_text_message_bytes(
        rom_path,
        _source_blocks(),
        source_revision="synthetic-revision",
    )

    assert report["summary"]["mismatch_byte_count"] == 1
    assert report["summary"]["message_mismatch_count"] == 1
    assert report["entries"][1]["status"] == "fail"
    assert report["entries"][1]["mismatch_byte_count"] == 1
    assert report["mismatches"] == [{
        "source_file": "Bank1C.asm",
        "block_label": "Message_Data",
        "message_index": 1,
        "message_id": 1,
        "message_label": "Message_0001",
        "source_line": 7,
        "offset": 0x1001,
        "offset_in_message": 0,
        "expected_byte": "$01",
        "actual_byte": "$02",
    }]


def test_byte_parser_refuses_nonliteral_assembler_expressions(tmp_path: Path) -> None:
    bad_block = MessageSourceBlock(
        source_file="Bank1C.asm",
        block_label="Message_Data",
        block_start_offset=0x1000,
        block_end_offset=0x1001,
        source_text="""Message_Data:
{
    Message_0000:
    db $7F, UnresolvedByte
}
""",
    )
    with pytest.raises(TextMessageByteVerificationError, match="assembler expressions are not evaluated"):
        verify_text_message_bytes(
            _write_rom(tmp_path / "synthetic.smc"),
            [bad_block],
            source_revision="synthetic-revision",
        )


def test_verifier_rejects_wrong_rom_size(tmp_path: Path) -> None:
    short_rom = tmp_path / "short.smc"
    short_rom.write_bytes(bytes(1024))
    with pytest.raises(TextMessageByteVerificationError, match="expected headerless 1 MiB image"):
        verify_text_message_bytes(
            short_rom,
            _source_blocks(),
            source_revision="synthetic-revision",
        )


def test_cli_writes_report_refuses_overwrite_and_exits_nonzero_on_mismatch(
    tmp_path: Path,
) -> None:
    main_source = tmp_path / "Bank1C.asm"
    extra_source = tmp_path / "Bank0E.asm"
    main_source.write_text(SYNTHETIC_MAIN, encoding="utf-8")
    extra_source.write_text(SYNTHETIC_EXTRA, encoding="utf-8")
    rom_path = _write_rom(tmp_path / "synthetic.smc")
    output = tmp_path / "message-byte-verification.json"
    runner = CliRunner()
    arguments = [
        "verify-text-message-bytes",
        str(rom_path),
        "--block",
        str(main_source), "Message_Data", "$001000", "$001002",
        "--block",
        str(extra_source), "Message_DataExtra", "$002000", "$002002",
        "--source-revision", "synthetic-revision",
    ]

    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["summary"]["checked_byte_count"] == 5
    assert report["summary"]["mismatch_byte_count"] == 0

    written = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert written.exit_code == 0, written.output
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert "checked=5, mismatches=0" in written.output

    refused = runner.invoke(cli, [*arguments, "--output", str(output)])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output

    rom = bytearray(rom_path.read_bytes())
    rom[0x2000] ^= 0x01
    rom_path.write_bytes(rom)
    failed = runner.invoke(cli, arguments)
    assert failed.exit_code == 1
    assert '"mismatch_byte_count": 1' in failed.output
