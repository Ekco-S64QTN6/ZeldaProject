"""End-to-end checks from pinned source files through CLI exports into the loader."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.asset_loader import load_source_export

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "AsarUSALTTPDisassembly"
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
BANK1F_PATH = REFERENCE / "Bank1F.asm"
BANK0B_PATH = REFERENCE / "Bank0B.asm"
BANK1B_PATH = REFERENCE / "Bank1B.asm"


@pytest.mark.skipif(
    not BANK1F_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_real_pointer_table_export_round_trips_through_loader(
    tmp_path: Path,
) -> None:
    export_path = tmp_path / "room-object-pointers.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(BANK1F_PATH),
            "RoomData_ObjectDataPointers",
            "--table-offset",
            "$0F8000",
            "--source-revision",
            PINNED_REVISION,
            "--output",
            str(export_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_source_export(export_path)
    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["entry_count"] == 320
    assert payload["entries"][0]["pointer_entry_file_offset"] == 0x0F8000
    assert payload["entries"][-1]["pointer_entry_file_offset"] == 0x0F83BD
    assert payload["source_revision"] == PINNED_REVISION


@pytest.mark.skipif(
    not BANK0B_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_real_incbin_inventory_export_round_trips_through_loader(
    tmp_path: Path,
) -> None:
    export_path = tmp_path / "overworld-incbin-inventory.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-incbin",
            str(BANK0B_PATH),
            "--source-revision",
            PINNED_REVISION,
            "--output",
            str(export_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_source_export(export_path)
    declarations = payload["declarations"]
    by_label = {item["label"]: item for item in declarations}

    assert payload["format"] == "zelda-suite-incbin-inventory"
    assert payload["declaration_count"] == len(declarations)
    assert by_label["OverworldMap32_Screen00_High"]["declared_size_bytes"] == 4
    assert by_label["OverworldMap32_Screen00_Low"]["declared_size_bytes"] == 0xD2
    assert payload["source_revision"] == PINNED_REVISION



@pytest.mark.skipif(
    not BANK1B_PATH.is_file(),
    reason="AsarUSALTTPDisassembly submodule is not checked out",
)
def test_real_dw_hidden_item_export_loads_as_128_entries(tmp_path: Path) -> None:
    export_path = tmp_path / "hidden-item-pointers.json"
    result = CliRunner().invoke(
        cli,
        [
            "inspect-pointer-table",
            str(BANK1B_PATH),
            "OverworldData_HiddenItems",
            "--table-offset",
            "$0DC2F9",
            "--directive",
            "dw",
            "--source-revision",
            PINNED_REVISION,
            "--output",
            str(export_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_source_export(export_path)
    assert payload["format"] == "zelda-suite-pointer-table"
    assert payload["entry_width"] == 2
    assert payload["entry_count"] == 128
    assert payload["entries"][0]["pointer_entry_file_offset"] == 0x0DC2F9
    assert payload["entries"][-1]["pointer_entry_file_offset"] == 0x0DC3F7
