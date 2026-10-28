"""Unit tests for shop-item purchase-handler parsing and CLI export."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.shop_item_handlers import (
    ShopItemHandlersParseError,
    parse_shop_item_handlers,
)

DISPATCH_LINES = [
    "dw Dummy0 ; 0x00 - $8000",
    "dw Dummy1 ; 0x01 - $8001",
    "dw Dummy2 ; 0x02 - $8002",
    "dw Dummy3 ; 0x03 - $8003",
    "dw Dummy4 ; 0x04 - $8004",
    "dw Dummy5 ; 0x05 - $8005",
    "dw Dummy6 ; 0x06 - $8006",
]
PURCHASES = [
    ("ShopItem_RedPotion150", "$96", "$00", "$2E", "$F16E"),
    ("ShopItem_FighterShield", "$32", "$00", "$04", "$F1F2"),
    ("ShopItem_FireShield", "$F4", "$01", "$05", "$F230"),
    ("ShopItem_Heart", "$0A", "$00", "$42", "$F27D"),
    ("ShopItem_Arrows", "$1E", "$00", "$44", "$F2AF"),
    ("ShopItem_Bombs", "$32", "$00", "$31", "$F2F0"),
    ("ShopItem_Bee", "$0A", "$00", "$0E", "$F322"),
]


def _synthetic_source() -> str:
    dispatch = [
        "; $0000-$0041 JUMP LOCATION",
        "Sprite_ShopKeeper:",
        "{",
        "    JSL.l UseImplicitRegIndexedLocalJumpTable",
        *DISPATCH_LINES,
    ]
    for index, (handler, _low, _high, _receipt, address) in enumerate(PURCHASES, start=7):
        dispatch.append(f"    dw {handler} ; 0x{index:02X} - {address}")
    dispatch.append("}")
    for table_index, (handler, low, high, receipt, _address) in enumerate(PURCHASES):
        start = 0x1000 + 0x10 * table_index
        end = start + 0x0F
        dispatch.extend([
            "; $" + f"{start:04X}-$" + f"{end:04X} JUMP LOCATION",
            f"{handler}:",
            "{",
            f"    LDA.b #{low}",
            f"    LDY.b #{high}",
            "    JSR.w ShopKeeper_TryToGetPaid : BCC .cant_afford",
            "    LDY.b #" + receipt,
            "    JSR.w ShopItem_HandleReceipt",
            "}",
        ])
    return "\n".join(dispatch) + "\n"


def test_parser_preserves_source_price_bytes_and_receipt_indexes() -> None:
    payload = parse_shop_item_handlers(
        _synthetic_source(),
        source_revision="synthetic-revision",
    ).to_dict()

    assert validate_source_export(payload) == payload
    assert payload["dispatch_routine_label"] == "Sprite_ShopKeeper"
    assert payload["dispatch_routine_source_range_annotation"] == "$0000-$0041 JUMP LOCATION"
    assert payload["dispatch_table_file_offset"] is None
    assert payload["dispatch_table_offset_established"] is False
    assert payload["dispatch_entry_count"] == 14
    assert payload["entry_count"] == 7
    assert [entry["shopkeeper_variant_id"] for entry in payload["entries"]] == list(range(7, 14))
    assert [entry["price_value"] for entry in payload["entries"]] == [150, 50, 500, 10, 30, 50, 10]
    assert [entry["receipt_item_index"] for entry in payload["entries"]] == [46, 4, 5, 66, 68, 49, 14]
    assert payload["evidence"]["receipt_item_names_resolved"] is False
    assert payload["evidence"]["room_specific_shop_stock_resolved"] is False


def test_loader_rejects_price_or_receipt_fields_that_disagree_with_source_bytes() -> None:
    payload = parse_shop_item_handlers(
        _synthetic_source(),
        source_revision="synthetic-revision",
    ).to_dict()
    payload["entries"][0]["price_value"] = 151
    with pytest.raises(AssetLoadError, match="price_value does not match"):
        validate_source_export(payload)

    payload = parse_shop_item_handlers(
        _synthetic_source(),
        source_revision="synthetic-revision",
    ).to_dict()
    payload["entries"][0]["receipt_item_index"] = 3
    with pytest.raises(AssetLoadError, match="receipt_item_index does not match"):
        validate_source_export(payload)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (_synthetic_source().replace("0x07 - $F16E", "0x09 - $F16E"), "dispatch slot 7 is annotated as 0x9"),
        (_synthetic_source().replace("LDY.b #$00", "LDX.b #$00", 1), "price/payment sequences"),
        (_synthetic_source().replace("LDY.b #$2E", "LDX.b #$2E", 1).replace("LDY.b #$04", "LDX.b #$04", 1), "no literal Y selector"),
        (_synthetic_source().replace("; $0000-$0041 JUMP LOCATION", "; missing range"), "range annotation"),
    ],
)
def test_parser_fails_closed_on_bad_dispatch_or_handler_data(source: str, expected: str) -> None:
    with pytest.raises(ShopItemHandlersParseError, match=expected):
        parse_shop_item_handlers(source, source_revision="synthetic-revision")


def test_inspect_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "sprite_shopkeeper.asm"
    source_path.write_text(_synthetic_source(), encoding="utf-8")
    output = tmp_path / "shop-item-handlers.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "inspect-shop-item-handlers",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["entry_count"] == 7
    assert saved["entries"][2]["price_value"] == 500
    assert "room-specific shop stock" in written.output

    refused = runner.invoke(cli, [
        "inspect-shop-item-handlers",
        str(source_path),
        "--source-revision", "synthetic-revision",
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
