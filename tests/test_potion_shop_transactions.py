"""Unit tests for the source-coded potion-shop transaction parser and CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.potion_shop_transactions import (
    PotionShopTransactionsParseError,
    parse_potion_shop_transactions,
)

SOURCE_REVISION = "synthetic-revision"
SYNTHETIC_SOURCE = """; $001000-$0010FF LOCAL JUMP LOCATION
Sprite_GreenPotionItem:
{
    LDA.l $7EF360 : CMP.w #$003C : SEP #$30 : BCC .cant_afford
    JSL.l Sprite_GetEmptyBottleIndex : BMI .no_bottle
    LDA.l $7EF360 : SEC : SBC.w #$003C : STA.l $7EF360
    LDY.b #$2F
    STZ.w $02E9
    JSL.l Link_ReceiveItem
}
; $001100-$0011FF JUMP LOCATION
Sprite_BluePotionItem:
{
    LDA.l $7EF360 : CMP.w #$00A0 : SEP #$30 : BCC .cant_afford
    JSL.l Sprite_GetEmptyBottleIndex : BMI .no_bottle
    LDA.l $7EF360 : SEC : SBC.w #$00A0 : STA.l $7EF360
    LDY.b #$30
    STZ.w $02E9
    JSL.l Link_ReceiveItem
}
; $001200-$0012FF JUMP LOCATION
Sprite_RedPotionItem:
{
    LDA.l $7EF360 : CMP.w #$0078 : SEP #$30 : BCC .cant_afford
    JSL.l Sprite_GetEmptyBottleIndex : BMI .no_bottle
    LDA.l $7EF360 : SEC : SBC.w #$0078 : STA.l $7EF360
    LDY.b #$2E
    STZ.w $02E9
    JSL.l Link_ReceiveItem
}
"""


def test_parser_preserves_price_literals_ranges_and_receipt_selectors() -> None:
    payload = parse_potion_shop_transactions(
        SYNTHETIC_SOURCE,
        source_revision=SOURCE_REVISION,
    ).to_dict()

    assert validate_source_export(payload) == payload
    assert payload["source_file"] == "sprite_potion_shop.asm"
    assert payload["entry_count"] == 3
    assert [
        entry["handler_label"] for entry in payload["entries"]
    ] == [
        "Sprite_GreenPotionItem",
        "Sprite_BluePotionItem",
        "Sprite_RedPotionItem",
    ]
    assert [
        entry["price_value"] for entry in payload["entries"]
    ] == [60, 160, 120]
    assert [
        entry["receipt_item_index"] for entry in payload["entries"]
    ] == [47, 48, 46]
    assert [
        entry["source_handler_range_annotation"] for entry in payload["entries"]
    ] == [
        "$001000-$0010FF LOCAL JUMP LOCATION",
        "$001100-$0011FF JUMP LOCATION",
        "$001200-$0012FF JUMP LOCATION",
    ]
    assert all(
        entry["price_compare_expression"] == entry["price_deduction_expression"]
        for entry in payload["entries"]
    )
    assert all(entry["empty_bottle_check_source_line"] > 0 for entry in payload["entries"])
    assert payload["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "price_behavior_runtime_verified": False,
        "source_range_annotations_verified": False,
        "receipt_item_names_resolved": False,
        "room_specific_shop_stock_resolved": False,
        "canonical_item_ids_resolved": False,
    }


def test_loader_rejects_price_and_receipt_fields_that_disagree() -> None:
    payload = parse_potion_shop_transactions(
        SYNTHETIC_SOURCE,
        source_revision=SOURCE_REVISION,
    ).to_dict()
    payload["entries"][0]["price_value"] = 61
    with pytest.raises(AssetLoadError, match="price_value does not match"):
        validate_source_export(payload)

    payload = parse_potion_shop_transactions(
        SYNTHETIC_SOURCE,
        source_revision=SOURCE_REVISION,
    ).to_dict()
    payload["entries"][0]["receipt_item_index"] = 46
    with pytest.raises(AssetLoadError, match="receipt_item_index must be"):
        validate_source_export(payload)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            SYNTHETIC_SOURCE.replace(
                "SBC.w #$003C", "SBC.w #$003D", 1
            ),
            "does not match deduction literal",
        ),
        (
            SYNTHETIC_SOURCE.replace(
                "JSL.l Sprite_GetEmptyBottleIndex", "JSL.l OtherCheck", 1
            ),
            "empty-bottle checks",
        ),
        (
            SYNTHETIC_SOURCE.replace(
                "; $001100-$0011FF JUMP LOCATION",
                "; invalid range annotation",
                1,
            ),
            "source range annotation",
        ),
        (
            SYNTHETIC_SOURCE.replace(
                "JSL.l Link_ReceiveItem", "JSL.l OtherReceive", 1
            ),
            "Link_ReceiveItem calls",
        ),
    ],
)
def test_parser_fails_closed_on_malformed_transaction_source(
    source: str,
    expected: str,
) -> None:
    with pytest.raises(PotionShopTransactionsParseError, match=expected):
        parse_potion_shop_transactions(
            source,
            source_revision=SOURCE_REVISION,
        )


def test_inspect_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "sprite_potion_shop.asm"
    source_path.write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    output = tmp_path / "potion-shop-transactions.json"
    runner = CliRunner()

    written = runner.invoke(cli, [
        "inspect-potion-shop-transactions",
        str(source_path),
        "--source-revision", SOURCE_REVISION,
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["entry_count"] == 3
    assert saved["entries"][1]["price_value"] == 160
    assert "receipt item names remain unverified" in written.output

    refused = runner.invoke(cli, [
        "inspect-potion-shop-transactions",
        str(source_path),
        "--source-revision", SOURCE_REVISION,
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
