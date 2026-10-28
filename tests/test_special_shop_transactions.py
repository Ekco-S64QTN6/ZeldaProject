"""Tests for Bomb Shop and Bottle Vendor transaction extraction."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.special_shop_transactions import (
    SpecialShopTransactionsParseError,
    parse_special_shop_transactions,
)

BOMB_SOURCE = """; $0010-$0020 JUMP LOCATION
Sprite_BombShopBomb:
{
    LDA.b #$64
    LDY.b #$00
    JSR.w ShopKeeper_TryToGetPaid : BCC .player_cant_afford
    LDY.b #$28
    JSR.w ShopItem_HandleReceipt
}
; $0021-$0030 JUMP LOCATION
Sprite_BombShopSuperBomb:
{
    LDA.b #$64
    LDY.b #$00
    JSR.w ShopKeeper_TryToGetPaid : BCC .player_cant_afford
    LDA.b #$0D : STA.l $7EF3CC ; Super Bomb sprite
    JSL.l Tagalong_LoadGfx
    JSL.l Tagalong_SpawnFromSprite
}
"""

BOTTLE_SOURCE = """; $0040-$0050 JUMP LOCATION
BottleVendor_SellingBottle:
{
    LDA.w $1CE8 : BNE .no_selected
    LDA.l $7EF360 : CMP.w #$0064 : SEP #$30 : BCC .player_cant_afford
}
; $0051-$0060 JUMP LOCATION
BottleVendor_GiveBottle:
{
    ; \\item(Bottle)
    LDY.b #$16
    STZ.w $02E9
    JSL.l Link_ReceiveItem
    LDA.l $7EF360 : SEC : SBC.w #$0064 : STA.l $7EF360
}
"""


def test_parser_preserves_each_special_shop_reward_mechanism() -> None:
    table = parse_special_shop_transactions(
        BOMB_SOURCE,
        BOTTLE_SOURCE,
        source_revision="synthetic-revision",
    )
    payload = table.to_dict()

    assert payload["entry_count"] == 3
    assert payload["source_file"] == "sprite_bomb_shop_entity.asm;sprite_bottle_vendor.asm"
    assert [entry["price_value"] for entry in payload["entries"]] == [100, 100, 100]
    assert [entry["receipt_item_index"] for entry in payload["entries"]] == [0x28, None, 0x16]
    assert payload["entries"][0]["receipt_method"] == "ShopItem_HandleReceipt"
    assert payload["entries"][1]["receipt_method"] == "special-bomb-flag-and-tagalong"
    assert payload["entries"][1]["reward_flag_address_expression"] == "$7EF3CC"
    assert payload["entries"][1]["reward_flag_value_expression"] == "$0D"
    assert payload["entries"][1]["tagalong_spawn_source_line"] is not None
    assert payload["entries"][2]["source_item_annotation"] == "Bottle"
    assert payload["entries"][2]["price_compare_expression"] == "$0064"
    assert payload["entries"][2]["price_deduction_expression"] == "$0064"
    assert payload["entries"][2]["rupee_balance_address_expression"] == "$7EF360"
    assert payload["evidence"]["canonical_item_ids_resolved"] is False


@pytest.mark.parametrize(
    ("bomb_source", "bottle_source", "expected"),
    [
        (BOMB_SOURCE.replace("LDY.b #$00", "LDY.b #$01", 1), BOTTLE_SOURCE, "100-rupee price"),
        (BOMB_SOURCE.replace("Tagalong_SpawnFromSprite", "OtherSpawn"), BOTTLE_SOURCE, "one tagalong spawn"),
        (BOMB_SOURCE, BOTTLE_SOURCE.replace("CMP.w #$0064", "CMP.w #$0063"), "literals disagree"),
        (BOMB_SOURCE, BOTTLE_SOURCE.replace(r"\item(Bottle)", "no item comment"), "item source comment"),
    ],
)
def test_parser_rejects_unresolved_special_shop_shapes(
    bomb_source: str, bottle_source: str, expected: str
) -> None:
    with pytest.raises(SpecialShopTransactionsParseError, match=expected):
        parse_special_shop_transactions(
            bomb_source, bottle_source, source_revision="synthetic-revision"
        )


def test_export_validator_rejects_false_receipt_selector_or_price() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (repo_root / "data" / "extracted" / "special-shop-transactions.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_source_export(payload) == payload

    invalid = json.loads(json.dumps(payload))
    invalid["entries"][1]["receipt_item_index"] = 0x28
    invalid["entries"][1]["receipt_index_expression"] = "$28"
    with pytest.raises(AssetLoadError, match="must not claim a receipt selector"):
        validate_source_export(invalid)

    invalid = json.loads(json.dumps(payload))
    invalid["entries"][2]["price_value"] = 101
    with pytest.raises(AssetLoadError, match="price_value must be 100"):
        validate_source_export(invalid)


def test_inspect_cli_writes_json_and_refuses_to_overwrite(tmp_path: Path) -> None:
    bomb_path = tmp_path / "sprite_bomb_shop_entity.asm"
    bottle_path = tmp_path / "sprite_bottle_vendor.asm"
    bomb_path.write_text(BOMB_SOURCE, encoding="utf-8")
    bottle_path.write_text(BOTTLE_SOURCE, encoding="utf-8")
    output = tmp_path / "special-shop-transactions.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "inspect-special-shop-transactions",
        str(bomb_path),
        str(bottle_path),
        "--source-revision", "synthetic-revision",
        "--output", str(output),
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["entry_count"] == 3
    assert saved["entries"][1]["receipt_item_index"] is None
    assert "non_receipt_rewards=1" in written.output

    refused = runner.invoke(cli, [
        "inspect-special-shop-transactions",
        str(bomb_path),
        str(bottle_path),
        "--source-revision", "synthetic-revision",
        "--output", str(output),
    ])
    assert refused.exit_code != 0
    assert "refusing to overwrite existing output" in refused.output
