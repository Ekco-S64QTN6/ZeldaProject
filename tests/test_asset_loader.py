"""Tests for source-export loading and validation."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    INCBIN_INVENTORY_FORMAT,
    POINTER_TABLE_FORMAT,
    AssetLoadError,
    load_source_export,
    validate_source_export,
)


def _pointer_export() -> dict[str, Any]:
    entries = [
        {
            "table_index": 0,
            "pointer_entry_file_offset": 0x1000,
            "source_line": 4,
            "pointer_expression": "TargetA",
            "target_label": "TargetA",
            "target_addend": None,
            "is_empty_target": False,
            "source_revision": "deadbeef",
        },
        {
            "table_index": 1,
            "pointer_entry_file_offset": 0x1003,
            "source_line": 5,
            "pointer_expression": "RoomDataTiles_Empty+$0008",
            "target_label": "RoomDataTiles_Empty",
            "target_addend": 8,
            "is_empty_target": True,
            "source_revision": "deadbeef",
        },
    ]
    return {
        "format": POINTER_TABLE_FORMAT,
        "format_version": 1,
        "source_file": "Bank1F.asm",
        "source_revision": "deadbeef",
        "table_label": "ExamplePointers",
        "table_file_offset": 0x1000,
        "entry_width": 3,
        "entry_count": 2,
        "entries": entries,
    }


def _incbin_export() -> dict[str, Any]:
    declarations = [
        {
            "source_file": "Bank0B.asm",
            "source_revision": "pinned-sha",
            "label": "Screen00_High",
            "source_line": 4,
            "incbin_path": "bin/ow/screen00-h.bin",
            "declared_size_bytes": 4,
            "source_file_offset_start": 0x58000,
            "source_file_offset_end": 0x58003,
            "computed_file_offset_end": 0x58003,
            "source_range_size_matches": True,
        },
        {
            "source_file": "Bank0B.asm",
            "source_revision": "pinned-sha",
            "label": "UnknownSize",
            "source_line": 10,
            "incbin_path": "opaque.bin",
            "declared_size_bytes": None,
            "source_file_offset_start": None,
            "source_file_offset_end": None,
            "computed_file_offset_end": None,
            "source_range_size_matches": None,
        },
    ]
    return {
        "format": INCBIN_INVENTORY_FORMAT,
        "format_version": 1,
        "source_file": "Bank0B.asm",
        "source_revision": "pinned-sha",
        "declaration_count": 2,
        "declarations": declarations,
    }


def _data_table_export() -> dict[str, Any]:
    entries = [
        {
            "table_index": 0,
            "entry_file_offset": 0x048B90,
            "source_line": 8,
            "source_label": ".ether_medallion",
            "expression": "$10",
            "literal_value": 0x10,
            "source_revision": "pinned-sha",
        },
        {
            "table_index": 1,
            "entry_file_offset": 0x048B91,
            "source_line": 12,
            "source_label": ".pendants",
            "expression": "$37",
            "literal_value": 0x37,
            "source_revision": "pinned-sha",
        },
    ]
    return {
        "format": DATA_TABLE_FORMAT,
        "format_version": 1,
        "source_file": "ancilla_init.asm",
        "source_revision": "pinned-sha",
        "parent_label": "Pool_AddPendantOrCrystal",
        "table_label": ".item_values",
        "end_label": ".fall_height",
        "table_file_offset": 0x048B90,
        "directive": "db",
        "entry_width": 1,
        "entry_count": 2,
        "entries": entries,
    }


@pytest.mark.parametrize("payload", [_pointer_export(), _incbin_export(), _data_table_export()])
def test_validate_accepts_supported_export_formats(payload: dict[str, Any]) -> None:
    result = validate_source_export(payload)
    assert result is payload


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p.update(format_version=2), "unsupported pointer-table format version"),
        (lambda p: p.update(entry_count=9), "entry_count"),
        (lambda p: p["entries"][1].update(table_index=0), "table_index"),
        (
            lambda p: p["entries"][1].update(pointer_entry_file_offset=0x2000),
            "pointer_entry_file_offset",
        ),
        (lambda p: p["entries"][1].update(is_empty_target=False), "is_empty_target"),
        (lambda p: p.update(extra_key=True), "unexpected field"),
        (lambda p: p["entries"][0].update(source_revision="other"), "source_revision"),
    ],
)
def test_validate_rejects_inconsistent_pointer_export(
    mutation: Any, message: str
) -> None:
    payload = copy.deepcopy(_pointer_export())
    mutation(payload)

    with pytest.raises(AssetLoadError, match=message):
        validate_source_export(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p.update(declaration_count=3), "declaration_count"),
        (
            lambda p: p["declarations"][0].update(computed_file_offset_end=0x58002),
            "computed_file_offset_end",
        ),
        (
            lambda p: p["declarations"][0].update(source_range_size_matches=False),
            "source_range_size_matches",
        ),
        (
            lambda p: p["declarations"][0].update(source_file="Bank0C.asm"),
            "source_file does not match",
        ),
        (lambda p: p.update(format_version=3), "unsupported incbin inventory format version"),
    ],
)
def test_validate_rejects_inconsistent_incbin_export(
    mutation: Any, message: str
) -> None:
    payload = copy.deepcopy(_incbin_export())
    mutation(payload)

    with pytest.raises(AssetLoadError, match=message):
        validate_source_export(payload)


def test_loader_reads_valid_export_without_changing_file(tmp_path: Path) -> None:
    payload = _pointer_export()
    path = tmp_path / "pointer-export.json"
    original = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    path.write_bytes(original)

    loaded = load_source_export(path)

    assert loaded == payload
    assert path.read_bytes() == original


def test_loader_rejects_malformed_json_and_nonstandard_numbers(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"format":', encoding="utf-8")
    with pytest.raises(AssetLoadError, match="invalid JSON"):
        load_source_export(malformed)

    nonstandard = tmp_path / "nan.json"
    nonstandard.write_text('{"format":"zelda-suite-pointer-table","value":NaN}', encoding="utf-8")
    with pytest.raises(AssetLoadError, match="non-standard JSON constant"):
        load_source_export(nonstandard)


def test_loader_rejects_unknown_format_and_non_object_json(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.json"
    unknown.write_text('{"format":"other"}', encoding="utf-8")
    with pytest.raises(AssetLoadError, match="unsupported source export format"):
        load_source_export(unknown)

    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(AssetLoadError, match="must be a JSON object"):
        load_source_export(array)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p.update(entry_count=8), "entry_count"),
        (
            lambda p: p["entries"][1].update(entry_file_offset=0x5000),
            "entry_file_offset",
        ),
        (
            lambda p: p["entries"][0].update(source_revision="stale"),
            "source_revision",
        ),
        (
            lambda p: p["entries"][0].update(literal_value=0x100),
            "does not fit the db directive",
        ),
        (lambda p: p.update(format_version=2), "unsupported data-table format version"),
        (lambda p: p.update(extra_field=True), "unexpected field"),
    ],
)
def test_validate_rejects_inconsistent_data_table_export(
    mutation: Any, message: str
) -> None:
    payload = copy.deepcopy(_data_table_export())
    mutation(payload)

    with pytest.raises(AssetLoadError, match=message):
        validate_source_export(payload)


def test_validate_rejects_boolean_values_as_integer_fields() -> None:
    payload = _pointer_export()
    payload["entry_count"] = True

    with pytest.raises(AssetLoadError, match="entry_count must be an integer"):
        validate_source_export(payload)


def test_cli_validate_source_export_success_and_failure(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(_incbin_export()), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-source-export", str(valid)])

    assert result.exit_code == 0, result.output
    assert "[OK]" in result.output
    assert "2 declarations" in result.output

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"format":"not-supported"}', encoding="utf-8")
    failed = runner.invoke(cli, ["validate-source-export", str(invalid)])

    assert failed.exit_code == 1
    assert "unsupported source export format" in failed.output
