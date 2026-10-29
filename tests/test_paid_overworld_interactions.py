"""Tests for paid overworld interaction source extraction and validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from zelda_suite.extract import AssetLoadError, validate_source_export
from zelda_suite.extract.paid_overworld_interactions import (
    PAID_OVERWORLD_SOURCE_FILES,
    PaidOverworldInteractionsParseError,
    parse_paid_overworld_interactions,
)

ROOT = Path(__file__).resolve().parents[1]
PINNED_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
EXPORT_PATH = ROOT / "data" / "extracted" / "paid-overworld-interactions.json"
SOURCE_DIR = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Sprites"


def _block(annotation: str, label: str, *body: str) -> str:
    return "\n".join([f"; {annotation}", f"{label}:", "{", *body, "}"])


def _synthetic_sources() -> dict[str, str]:
    fortune = "\n".join([
        *_block("$000100-$000107 DATA", "FortuneTeller_Prices", "    dw 10, 15, 20, 30").splitlines(),
        *_block("$000108-$000110 JUMP LOCATION", "LW_FortuneTeller_WaitForInquiry", "    LDA.l $7EF360 : CMP FortuneTeller_Prices, Y").splitlines(),
        *_block("$000111-$000120 JUMP LOCATION", "LW_FortuneTeller_DeductPayment", "    LDA.l $7EF360 : SEC : SBC FortuneTeller_Prices, Y").splitlines(),
        *_block("$000121-$000130 JUMP LOCATION", "DW_FortuneTeller_WaitForInquiry", "    LDA.l $7EF360 : CMP FortuneTeller_Prices, Y").splitlines(),
        *_block("$000131-$000140 JUMP LOCATION", "DW_FortuneTeller_DeductPayment", "    LDA.l $7EF360 : SEC : SBC FortuneTeller_Prices, Y").splitlines(),
        *_block("$000141-$000150 JUMP LOCATION", "FortuneTeller_GiveReading", "    RTS").splitlines(),
    ])
    dig_lines = [
        *_block(
            "$000200-$000220 JUMP LOCATION",
            "DiggingGameGuy_DoYouWantToPlay",
            "    LDA.l $7EF360 : CMP.w #$0050 : BCC .cant_afford",
            "    LDA.l $7EF360 : SEC : SBC.w #$0050 : STA.l $7EF360",
            "    JSL.l Sprite_InitializeSecondaryItemMinigame",
        ).splitlines(),
        *_block(
            "$000221-$000240 LOCAL JUMP LOCATION",
            "DiggingGameGuy_AttemptPrizeSpawn",
            "    JSL.l UseImplicitRegIndexedLocalJumpTable",
            "    dw DiggingGameGuy_GiveItem_basic ; 0x00 - $FD8A",
            "    dw DiggingGameGuy_GiveItem_basic ; 0x01 - $FD8A",
            "    dw DiggingGameGuy_GiveItem_basic ; 0x02 - $FD8A",
            "    dw DiggingGameGuy_GiveItem_basic ; 0x03 - $FD8A",
            "    dw DiggingGameGuy_GiveItem_heart_piece ; 0x04 - $FDAC",
            "    dw DiggingGameGuy_GiveItem_nothing ; 0x05 - $FD8F",
            "    dw DiggingGameGuy_GiveItem_nothing ; 0x06 - $FD8F",
            "    dw DiggingGameGuy_GiveItem_nothing ; 0x07 - $FD8F",
        ).splitlines(),
        *_block(
            "$000241-$000248 DATA",
            "Pool_DiggingGameGuy_GiveItem",
            "    .x_speeds",
            "    db $F0",
            "    .x_offsets",
            "    db $00",
            "    .basic_types",
            "    db $DB ; Red Rupee",
            "    db $DA ; Blue Rupee",
            "    db $D9 ; Green Rupee",
            "    db $DF ; Small magic refill",
        ).splitlines(),
        *_block(
            "$000249-$000260 JUMP LOCATION",
            "DiggingGameGuy_GiveItem_heart_piece",
            "    LDA.l $7FFE01 : CMP.b #$19 : BCC DiggingGameGuy_GiveItem_nothing",
            "    LDA.l $7FFE00 : BNE DiggingGameGuy_GiveItem_nothing",
            "    JSL.l GetRandomInt : AND.b #$03 : BNE DiggingGameGuy_GiveItem_nothing",
            "    LDA.b #$EB : STA.l $7FFE00",
        ).splitlines(),
    ]
    digging = "\n".join(dig_lines)
    zora = "\n".join(_block(
        "$000300-$000350 JUMP LOCATION",
        "ZoraKing_Dialogue",
        "    LDA.l $7EF360 : SEC : SBC.w #$01F4 : BCC .cant_afford",
        "    STA.l $7EF360",
        "    JSL.l Sprite_SpawnFlippersItem",
    ).splitlines())
    kiki = "\n".join([
        *_block(
            "$000400-$000440 JUMP LOCATION",
            "Kiki_OfferToFollowTransaction",
            "    LDA.b #$0A",
            "    JSR.w ShopKeeper_TryToGetPaid : BCC .cant_afford",
            "    LDA.w $02F2 : ORA.b #$03 : STA.w $02F2",
        ).splitlines(),
        *_block(
            "$000441-$000480 JUMP LOCATION",
            "Kiki_VerifyPurchase",
            "    LDA.b #$64",
            "    JSR.w ShopKeeper_TryToGetPaid : BCC .cant_afford",
            "    INC.w $02E4",
            "    INC.w $0D80, X",
            "    STZ.w $0DE0, X",
        ).splitlines(),
    ])
    archery = "\n".join(_block(
        "$000500-$000530 BRANCH LOCATION",
        "ArcheryGameGuy_RunGame",
        "    JSL.l Sprite_InitializeSecondaryItemMinigame",
        "    LDA.l $7EF360 : SEC : SBC.b #$0014 : STA.l $7EF360",
    ).splitlines())
    ponds = "\n".join([
        *_block(
            "$000600-$000607 DATA",
            "FairyPond",
            "    .prices",
            "    db 5, 20, 25, 50",
            "    .bcd_prices",
            "    db $05, $20, $25, $50",
        ).splitlines(),
        *_block(
            "$000608-$000650 JUMP LOCATION",
            "LakeHyliaFairy_AcceptDonation",
            "    LDA.l $7EF360 : SEC : SBC.b $00 : STA.l $7EF360",
            "    LDA.l $7EF36A : CLC : ADC.b $00 : STA.l $7EF36A",
            "    JSL.l AddHappinessPondRupees",
        ).splitlines(),
    ])
    return dict(zip(
        PAID_OVERWORLD_SOURCE_FILES,
        [
            archery,
            digging,
            fortune,
            kiki,
            ponds,
            zora,
        ],
        strict=True,
    ))


def test_parser_extracts_variable_and_fixed_fees_and_reward_gates() -> None:
    payload = parse_paid_overworld_interactions(
        _synthetic_sources(),
        source_revision="synthetic-revision",
    )
    assert validate_source_export(payload) == payload
    assert payload["interaction_count"] == 7
    by_id = {entry["interaction_id"]: entry for entry in payload["interactions"]}
    assert by_id["fortune-teller-reading"]["fee_values"] == [10, 15, 20, 30]
    assert by_id["digging-game-entry"]["fee_values"] == [80]
    assert by_id["zora-king-flippers"]["fee_values"] == [500]
    assert by_id["kiki-follow-fee"]["fee_values"] == [10]
    assert by_id["kiki-palace-access-fee"]["fee_values"] == [100]
    assert by_id["archery-game-entry"]["fee_values"] == [20]
    assert by_id["lake-hylia-fairy-donation"]["fee_values"] == [5, 20, 25, 50]
    assert len(payload["reward_tables"][0]["entries"]) == 8
    assert len(payload["reward_tables"][1]["entries"]) == 4
    assert payload["reward_gates"][0]["minimum_hole_count"] == 25
    assert payload["evidence"]["fee_behavior_runtime_verified"] is False


def test_validator_rejects_fee_value_or_reward_index_drift() -> None:
    payload = parse_paid_overworld_interactions(_synthetic_sources(), source_revision="synthetic-revision")
    payload["interactions"][1]["fee_values"][0] = 81
    with pytest.raises(AssetLoadError, match="does not match its source expression"):
        validate_source_export(payload)

    payload = parse_paid_overworld_interactions(_synthetic_sources(), source_revision="synthetic-revision")
    payload["reward_tables"][0]["entries"][0]["table_index"] = 2
    with pytest.raises(AssetLoadError, match="table_index must be 0"):
        validate_source_export(payload)


def test_parser_fails_closed_on_missing_price_or_reward_entries() -> None:
    sources = _synthetic_sources()
    sources["sprite_fortune_teller.asm"] = sources["sprite_fortune_teller.asm"].replace(
        "dw 10, 15, 20, 30", "dw 10, 15, 20, 31"
    )
    with pytest.raises(PaidOverworldInteractionsParseError, match="FortuneTeller_Prices changed"):
        parse_paid_overworld_interactions(sources)

    sources = _synthetic_sources()
    sources["sprite_digging_game_guy.asm"] = sources["sprite_digging_game_guy.asm"].replace(
        "0x07 - $FD8F", "0x08 - $FD8F"
    )
    with pytest.raises(PaidOverworldInteractionsParseError, match="annotated as"):
        parse_paid_overworld_interactions(sources)


def test_registered_export_matches_pinned_sources_when_submodule_exists() -> None:
    if not all((SOURCE_DIR / name).is_file() for name in PAID_OVERWORLD_SOURCE_FILES):
        pytest.skip("AsarUSALTTPDisassembly submodule is not checked out")
    sources = {
        name: (SOURCE_DIR / name).read_text(encoding="utf-8")
        for name in PAID_OVERWORLD_SOURCE_FILES
    }
    parsed = parse_paid_overworld_interactions(sources)
    assert parsed == __import__("zelda_suite.extract", fromlist=["load_source_export"]).load_source_export(EXPORT_PATH)
