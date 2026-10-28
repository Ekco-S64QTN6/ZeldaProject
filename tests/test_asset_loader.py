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
    ASSET_REGISTRY_FORMAT,
    DATA_TABLE_FORMAT,
    INCBIN_INVENTORY_FORMAT,
    POINTER_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
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
        (lambda p: p.update(format_version=3), "unsupported data-table format version"),
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



def _test_asset_registry(tmp_path: Path, export: dict[str, Any]) -> Path:
    asset_path = tmp_path / "sample-export.json"
    asset_path.write_text(json.dumps(export), encoding="utf-8")
    registry = {
        "format": ASSET_REGISTRY_FORMAT,
        "format_version": 1,
        "assets": [
            {
                "name": "sample-export",
                "file": asset_path.name,
                "format": export["format"],
                "source_revision": export["source_revision"],
                "record_count": export.get("entry_count", 0),
                "subsystem": "test",
                "description": "Synthetic export used by registry tests.",
            }
        ],
    }
    registry_path = tmp_path / "manifest.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return registry_path


def test_named_asset_loader_lists_and_loads_committed_assets() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    registry_path = repository_root / "data" / "extracted" / "manifest.json"

    assets = list_extracted_assets(registry_path)
    names = {asset["name"] for asset in assets}

    assert len(assets) == 31
    assert names == {
        "crystal-maiden-palette-words",
        "crystal-switch-palette-selectors",
        "falling-prize-item-values",
        "falling-prize-fall-heights",
        "falling-prize-y-offsets",
        "falling-prize-x-offsets",
        "falling-prize-delay-timers",
        "text-dictionary-pointers",
        "text-dictionary-fragments",
        "text-message-index",
        "sprite-active3-dispatch",
        "mad-batter-pseudo-attack-palettes",
        "music-track-index",
        "music-payload-inventory",
        "overworld-hidden-item-pointers",
        "dungeon-room-door-pointers",
        "dungeon-room-object-pointers",
        "dungeon-room-payloads-bank03",
        "dungeon-room-payload-inventory",
        "dungeon-room-payloads-bank1f",
        "overworld-payloads-bank0b",
        "overworld-payloads-bank0c",
        "item-receipt-target-addresses",
        "item-receipt-values",
        "item-receipt-dungeon-masks",
        "item-receipt-y-offsets",
        "item-receipt-x-offsets",
        "item-receipt-wide-flags",
        "item-receipt-properties",
        "item-receipt-layout",
        "item-receipt-graphics-indices",
    }

    loaded = {
        asset["name"]: load_extracted_asset(asset["name"], registry_path)
        for asset in assets
    }
    assert loaded["crystal-maiden-palette-words"]["entry_count"] == 8
    assert loaded["crystal-switch-palette-selectors"]["entry_count"] == 2
    assert loaded["falling-prize-item-values"]["entry_count"] == 7
    assert loaded["text-dictionary-pointers"]["entry_count"] == 98
    assert loaded["text-dictionary-fragments"]["fragment_count"] == 98
    assert loaded["text-message-index"]["message_count"] == 397
    assert loaded["sprite-active3-dispatch"]["entry_count"] == 68
    assert loaded["mad-batter-pseudo-attack-palettes"]["entry_count"] == 8
    assert loaded["music-track-index"]["entry_count"] == 35
    assert loaded["music-payload-inventory"]["declaration_count"] == 15
    assert loaded["overworld-hidden-item-pointers"]["entry_count"] == 128
    assert loaded["dungeon-room-door-pointers"]["entry_count"] == 320
    assert loaded["dungeon-room-object-pointers"]["entry_count"] == 320
    assert loaded["dungeon-room-payloads-bank03"]["declaration_count"] == 34
    assert loaded["dungeon-room-payload-inventory"]["declaration_count"] == 75
    assert loaded["dungeon-room-payloads-bank1f"]["declaration_count"] == 157
    assert loaded["overworld-payloads-bank0b"]["declaration_count"] == 164
    assert loaded["overworld-payloads-bank0c"]["declaration_count"] == 84
    assert loaded["item-receipt-target-addresses"]["entry_count"] == 76
    assert loaded["item-receipt-values"]["entry_count"] == 76
    assert loaded["item-receipt-layout"]["entry_count"] == 76
    assert loaded["item-receipt-layout"]["dungeon_mask_count"] == 14
    assert loaded["item-receipt-layout"]["semantic_item_ids_resolved"] is False
    assert loaded["item-receipt-graphics-indices"]["entry_count"] == 76
    assert loaded["item-receipt-graphics-indices"]["format_version"] == 2
    assert loaded["item-receipt-dungeon-masks"]["entry_count"] == 14
    assert loaded["item-receipt-y-offsets"]["entry_count"] == 76
    assert loaded["item-receipt-x-offsets"]["entry_count"] == 76
    assert loaded["item-receipt-wide-flags"]["entry_count"] == 76
    assert loaded["item-receipt-properties"]["entry_count"] == 76


def test_named_asset_loader_validates_registry_provenance_and_name(
    tmp_path: Path,
) -> None:
    registry_path = _test_asset_registry(tmp_path, _pointer_export())

    assert list_extracted_assets(registry_path)[0]["name"] == "sample-export"
    assert load_extracted_asset("sample-export", registry_path) == _pointer_export()

    with pytest.raises(AssetLoadError, match="unknown extracted asset"):
        load_extracted_asset("missing-asset", registry_path)

    with pytest.raises(AssetLoadError, match="lowercase kebab-case"):
        load_extracted_asset("../sample-export", registry_path)


def test_named_asset_loader_rejects_path_traversal_and_format_mismatch(
    tmp_path: Path,
) -> None:
    export_path = tmp_path / "sample-export.json"
    export_path.write_text(json.dumps(_pointer_export()), encoding="utf-8")
    unsafe_registry = {
        "format": ASSET_REGISTRY_FORMAT,
        "format_version": 1,
        "assets": [
            {
                "name": "sample-export",
                "file": "../sample-export.json",
                "format": POINTER_TABLE_FORMAT,
                "source_revision": "deadbeef",
                "record_count": 2,
                "subsystem": "test",
                "description": "Invalid path must be rejected.",
            }
        ],
    }
    registry_path = tmp_path / "unsafe-manifest.json"
    registry_path.write_text(json.dumps(unsafe_registry), encoding="utf-8")

    with pytest.raises(AssetLoadError, match="JSON filename inside the registry directory"):
        list_extracted_assets(registry_path)

    registry_path = _test_asset_registry(tmp_path, _pointer_export())
    manifest = json.loads(registry_path.read_text(encoding="utf-8"))
    manifest["assets"][0]["format"] = DATA_TABLE_FORMAT
    registry_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AssetLoadError, match="declares format"):
        load_extracted_asset("sample-export", registry_path)



@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_revision", "different-revision", "source_revision does not match"),
        ("record_count", 99, "record_count is 99"),
    ],
)
def test_named_asset_loader_rejects_stale_registry_provenance_or_count(
    tmp_path: Path,
    field: str,
    value: Any,
    message: str,
) -> None:
    registry_path = _test_asset_registry(tmp_path, _pointer_export())
    manifest = json.loads(registry_path.read_text(encoding="utf-8"))
    manifest["assets"][0][field] = value
    registry_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AssetLoadError, match=message):
        load_extracted_asset("sample-export", registry_path)



def test_every_registered_export_is_canonical_sorted_json() -> None:
    """Ensure committed exports are byte-stable under the project JSON convention."""
    repository_root = Path(__file__).resolve().parents[1]
    registry_path = repository_root / "data" / "extracted" / "manifest.json"
    assets = list_extracted_assets(registry_path)

    assert assets
    for asset in assets:
        export_path = registry_path.parent / asset["file"]
        raw = export_path.read_text(encoding="utf-8")
        payload = load_source_export(export_path)
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"

        assert raw == canonical, (
            f"{asset['name']} is not canonical sorted JSON; "
            "regenerate or normalize the export without reordering arrays"
        )
