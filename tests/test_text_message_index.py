"""Tests for the metadata-only source text message index."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import (
    MessageSourceBlock,
    load_source_export,
    parse_text_message_index,
)
from zelda_suite.extract.asset_loader import AssetLoadError, validate_source_export

ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1C.asm"
EXTRA_SOURCE = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank0E.asm"
EXPORT_PATH = ROOT / "data" / "extracted" / "text-message-index.json"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _pinned_blocks() -> list[MessageSourceBlock]:
    return [
        MessageSourceBlock(
            source_file="Bank1C.asm",
            block_label="Message_Data",
            block_start_offset=0x0E0000,
            block_end_offset=0x0E7F29,
            source_text=MAIN_SOURCE.read_text(encoding="utf-8"),
        ),
        MessageSourceBlock(
            source_file="Bank0E.asm",
            block_label="Message_DataExtra",
            block_start_offset=0x075F40,
            block_end_offset=0x076E21,
            source_text=EXTRA_SOURCE.read_text(encoding="utf-8"),
        ),
    ]


SYNTHETIC_SOURCE = """Message_Data:
{
    ; $001000
    Message_0000:
    db $7F
    ; $001001
    Message_0001:
    db $01, $7F
}
"""


def test_indexes_pinned_message_blocks_and_preserves_known_anomalies() -> None:
    if not MAIN_SOURCE.is_file() or not EXTRA_SOURCE.is_file():
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")

    index = parse_text_message_index(
        _pinned_blocks(),
        source_revision=PINNED_REVISION,
    )
    payload = index.to_dict()

    assert payload["format"] == "zelda-suite-text-message-index"
    assert payload["message_count"] == 397
    assert payload["source_block_count"] == 2
    assert payload["messages"][0]["message_label"] == "Message_0000"
    assert payload["messages"][-1]["message_label"] == "Message_018C"

    main, extra = payload["source_blocks"]
    assert main["data_block_label"] == "Message_Data"
    assert main["message_count"] == 359
    assert main["declared_byte_count_total"] == 0x7F2A
    assert main["declared_bytes_match_block_size"] is True
    assert extra["data_block_label"] == "Message_DataExtra"
    assert extra["message_count"] == 38
    assert extra["declared_byte_count_total"] == 0xEE1
    assert extra["block_size_bytes"] == 0xEE2
    assert extra["declared_bytes_match_block_size"] is False

    annotation_mismatches = [
        message["message_id"]
        for message in payload["messages"]
        if message["source_offset_matches_sequential"] is False
    ]
    assert annotation_mismatches == [21, 122, 202, 305, 307, 310]

    malformed_annotations = [
        message["message_id"]
        for message in payload["messages"]
        if message["source_offset_annotation_valid"] is False
    ]
    assert malformed_annotations == [21, 305, 310]
    assert all(
        message["source_offset_annotation"] is None
        for message in payload["messages"]
        if message["data_block_label"] == "Message_DataExtra"
    )


def test_cli_exports_synthetic_message_index_and_loader_checks_invariants(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.asm"
    output = tmp_path / "message-index.json"
    source.write_text(SYNTHETIC_SOURCE, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "inspect-text-messages",
            "--block",
            str(source),
            "Message_Data",
            "$001000",
            "$001002",
            "--source-revision",
            "synthetic-revision",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_source_export(output)
    assert payload["message_count"] == 2
    assert payload["messages"][0]["sequential_file_offset"] == 0x1000
    assert payload["messages"][1]["sequential_file_offset"] == 0x1001
    assert payload["source_blocks"][0]["declared_bytes_match_block_size"] is True

    malformed = json.loads(output.read_text(encoding="utf-8"))
    malformed["messages"][1]["sequential_file_offset"] += 1
    with pytest.raises(AssetLoadError, match="sequential_file_offset"):
        validate_source_export(malformed)

    refused = CliRunner().invoke(
        cli,
        [
            "inspect-text-messages",
            "--block",
            str(source),
            "Message_Data",
            "$001000",
            "$001002",
            "--output",
            str(output),
        ],
    )
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output


@pytest.mark.skipif(
    not MAIN_SOURCE.is_file() or not EXTRA_SOURCE.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_committed_text_message_index_matches_pinned_source() -> None:
    payload = load_source_export(EXPORT_PATH)
    parsed = parse_text_message_index(
        _pinned_blocks(),
        source_revision=PINNED_REVISION,
    ).to_dict()

    assert payload["source_blocks"] == parsed["source_blocks"]
    assert payload["messages"] == parsed["messages"]
    assert payload["message_count"] == parsed["message_count"]
