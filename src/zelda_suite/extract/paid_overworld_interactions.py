"""Parse source-derived non-shop rupee transactions and rewards."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PAID_OVERWORLD_INTERACTIONS_FORMAT = "zelda-suite-paid-overworld-interactions"
PAID_OVERWORLD_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"
PAID_OVERWORLD_SOURCE_FILES = (
    "sprite_archery_game_guy.asm",
    "sprite_digging_game_guy.asm",
    "sprite_fortune_teller.asm",
    "sprite_kiki.asm",
    "sprite_ponds.asm",
    "sprite_zora_king.asm",
)
PAID_OVERWORLD_INTERACTION_COUNT = 7

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_.][A-Za-z0-9_.]*)\s*:\s*$")
_RANGE_RE = re.compile(
    r"^\s*;\s*(?P<annotation>\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+\s+"
    r"(?:DATA|JUMP LOCATION|LOCAL JUMP LOCATION|BRANCH LOCATION))\s*$",
    re.IGNORECASE,
)
_HEX_BYTE_RE = re.compile(r"\$[0-9A-Fa-f]{2}\Z")
_HEX_WORD_RE = re.compile(r"\$[0-9A-Fa-f]{4}\Z")
_DIG_DISPATCH_RE = re.compile(
    r"^\s*dw\s+(?P<handler>[A-Za-z_][A-Za-z0-9_]*)\s*;\s*"
    r"0x(?P<index>[0-9A-Fa-f]{2})\s*-\s*(?P<address>\$[0-9A-Fa-f]{4})\s*$"
)
_FORTUNE_VALUES = (10, 15, 20, 30)
_POND_VALUES = (5, 20, 25, 50)


class PaidOverworldInteractionsParseError(ValueError):
    """Raised when a source-defined paid interaction or reward table is ambiguous."""


def _source_code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _find_label(lines: list[str], label: str) -> int:
    hits = [
        index
        for index, line in enumerate(lines)
        if (match := _LABEL_RE.fullmatch(_source_code(line))) is not None
        and match.group("label") == label
    ]
    if len(hits) != 1:
        raise PaidOverworldInteractionsParseError(
            f"expected exactly one {label!r} label; found {len(hits)}"
        )
    return hits[0]


def _range_annotation(lines: list[str], label_index: int, label: str) -> tuple[str, int]:
    index = label_index - 1
    while index >= 0 and not lines[index].strip():
        index -= 1
    if index < 0:
        raise PaidOverworldInteractionsParseError(
            f"source range annotation is missing above {label!r}"
        )
    match = _RANGE_RE.fullmatch(lines[index])
    if match is None:
        raise PaidOverworldInteractionsParseError(
            f"source range annotation above {label!r} is missing or malformed"
        )
    return match.group("annotation"), index + 1


def _find_block(lines: list[str], label: str) -> tuple[int, int, int]:
    label_index = _find_label(lines, label)
    opening_index = label_index + 1
    while opening_index < len(lines) and not _source_code(lines[opening_index]):
        opening_index += 1
    if opening_index >= len(lines) or _source_code(lines[opening_index]) != "{":
        raise PaidOverworldInteractionsParseError(
            f"opening brace missing after {label!r}"
        )
    depth = 1
    for index in range(opening_index + 1, len(lines)):
        code = _source_code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return label_index, opening_index, index
        if depth < 0:
            break
    raise PaidOverworldInteractionsParseError(f"closing brace missing for {label!r}")


def _matches(
    lines: list[str], start: int, end: int, pattern: re.Pattern[str], label: str
) -> list[tuple[int, re.Match[str]]]:
    found: list[tuple[int, re.Match[str]]] = []
    for index in range(start, end):
        match = pattern.search(_source_code(lines[index]))
        if match is not None:
            found.append((index, match))
    return found


def _single_match(
    lines: list[str], start: int, end: int, pattern: re.Pattern[str], label: str
) -> tuple[int, re.Match[str]]:
    found = _matches(lines, start, end, pattern, label)
    if len(found) != 1:
        raise PaidOverworldInteractionsParseError(
            f"expected one {label}; found {len(found)}"
        )
    return found[0]


def _next_code(lines: list[str], index: int, end: int) -> tuple[str, int] | None:
    for candidate in range(index + 1, end):
        value = _source_code(lines[candidate])
        if value:
            return value, candidate
    return None


def _transaction(
    *,
    interaction_id: str,
    actor_label: str,
    interaction_kind: str,
    source_file: str,
    source_label: str,
    source_range_annotation: str,
    source_annotation_line: int,
    fee_model: str,
    fee_values: list[int],
    fee_expressions: list[str],
    fee_table_label: str | None,
    fee_source_lines: list[int],
    payment_source_lines: list[int],
    outcome_label: str,
    outcome_source_lines: list[int],
    source_revision: str,
) -> dict[str, Any]:
    return {
        "interaction_id": interaction_id,
        "actor_label": actor_label,
        "interaction_kind": interaction_kind,
        "source_file": source_file,
        "source_label": source_label,
        "source_range_annotation": source_range_annotation,
        "source_annotation_line": source_annotation_line,
        "fee_model": fee_model,
        "fee_values": fee_values,
        "fee_expressions": fee_expressions,
        "fee_table_label": fee_table_label,
        "fee_source_lines": fee_source_lines,
        "payment_source_lines": payment_source_lines,
        "outcome_label": outcome_label,
        "outcome_source_lines": outcome_source_lines,
        "source_revision": source_revision,
    }


def parse_paid_overworld_interactions(
    source_files: Mapping[str, str],
    *,
    source_revision: str = PAID_OVERWORLD_SOURCE_REVISION,
) -> dict[str, Any]:
    """Parse seven fee-bearing overworld interactions and the digging prize paths.

    The parser records prices, source labels, and source line evidence. It does
    not establish canonical ROM offsets, guarantee game execution semantics, or
    turn source-commented prize labels into canonical item identifiers.
    """
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    missing = sorted(set(PAID_OVERWORLD_SOURCE_FILES) - set(source_files))
    extra = sorted(set(source_files) - set(PAID_OVERWORLD_SOURCE_FILES))
    if missing or extra:
        raise PaidOverworldInteractionsParseError(
            f"source files mismatch; missing={missing}, extra={extra}"
        )
    lines_by_file: dict[str, list[str]] = {}
    for name in PAID_OVERWORLD_SOURCE_FILES:
        content = source_files[name]
        if not isinstance(content, str) or not content:
            raise ValueError(f"source file {name!r} must contain text")
        lines_by_file[name] = content.splitlines()

    transactions: list[dict[str, Any]] = []

    # Fortune Teller: source table is shared by Light World and Dark World paths.
    fortune_file = "sprite_fortune_teller.asm"
    fortune_lines = lines_by_file[fortune_file]
    fortune_label, fortune_open, fortune_close = _find_block(
        fortune_lines, "FortuneTeller_Prices"
    )
    fortune_range, fortune_range_line = _range_annotation(
        fortune_lines, fortune_label, "FortuneTeller_Prices"
    )
    price_directives = [
        (index, _source_code(fortune_lines[index]))
        for index in range(fortune_open + 1, fortune_close)
        if re.match(r"^\s*dw\b", _source_code(fortune_lines[index]), re.IGNORECASE)
    ]
    if len(price_directives) != 1:
        raise PaidOverworldInteractionsParseError(
            "FortuneTeller_Prices must contain one word directive"
        )
    price_line, price_directive = price_directives[0]
    price_match = re.fullmatch(r"dw\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", price_directive, re.IGNORECASE)
    if price_match is None:
        raise PaidOverworldInteractionsParseError(
            "FortuneTeller_Prices must contain the four source-coded decimal prices"
        )
    fortune_values = [int(value) for value in price_match.groups()]
    if tuple(fortune_values) != _FORTUNE_VALUES:
        raise PaidOverworldInteractionsParseError(
            f"FortuneTeller_Prices changed from {_FORTUNE_VALUES}: {fortune_values}"
        )
    light_check_block = _find_block(fortune_lines, "LW_FortuneTeller_WaitForInquiry")
    light_check = _single_match(
        fortune_lines, light_check_block[1], light_check_block[2],
        re.compile(r"FortuneTeller_Prices,\s*Y"), "Light World fortune price check",
    )[0]
    light_deduct_block = _find_block(fortune_lines, "LW_FortuneTeller_DeductPayment")
    light_deduct = _single_match(
        fortune_lines, light_deduct_block[1], light_deduct_block[2],
        re.compile(r"SBC\s+FortuneTeller_Prices,\s*Y"), "Light World fortune deduction",
    )[0]
    dark_check_block = _find_block(fortune_lines, "DW_FortuneTeller_WaitForInquiry")
    dark_check = _single_match(
        fortune_lines, dark_check_block[1], dark_check_block[2],
        re.compile(r"FortuneTeller_Prices,\s*Y"), "Dark World fortune price check",
    )[0]
    dark_deduct_block = _find_block(fortune_lines, "DW_FortuneTeller_DeductPayment")
    dark_deduct = _single_match(
        fortune_lines, dark_deduct_block[1], dark_deduct_block[2],
        re.compile(r"SBC\s+FortuneTeller_Prices,\s*Y"), "Dark World fortune deduction",
    )[0]
    reading_label = _find_label(fortune_lines, "FortuneTeller_GiveReading")
    transactions.append(_transaction(
        interaction_id="fortune-teller-reading",
        actor_label="FortuneTeller",
        interaction_kind="fortune-reading",
        source_file=fortune_file,
        source_label="FortuneTeller_Prices",
        source_range_annotation=fortune_range,
        source_annotation_line=fortune_range_line,
        fee_model="selected-price-table",
        fee_values=fortune_values,
        fee_expressions=[str(value) for value in fortune_values],
        fee_table_label="FortuneTeller_Prices",
        fee_source_lines=[price_line + 1],
        payment_source_lines=[light_check + 1, light_deduct + 1, dark_check + 1, dark_deduct + 1],
        outcome_label="FortuneTeller_GiveReading",
        outcome_source_lines=[reading_label + 1],
        source_revision=source_revision,
    ))

    # Digging Game: fixed 80-rupee game entry and a source-commented prize table.
    digging_file = "sprite_digging_game_guy.asm"
    digging_lines = lines_by_file[digging_file]
    digging_label, digging_open, digging_close = _find_block(
        digging_lines, "DiggingGameGuy_DoYouWantToPlay"
    )
    digging_range, digging_range_line = _range_annotation(
        digging_lines, digging_label, "DiggingGameGuy_DoYouWantToPlay"
    )
    compare_index = _single_match(
        digging_lines, digging_open, digging_close,
        re.compile(r"CMP\.w\s+#(?P<fee>\$[0-9A-Fa-f]{4})"), "digging game fee comparison",
    )
    deduct_index = _single_match(
        digging_lines, digging_open, digging_close,
        re.compile(r"SBC\.w\s+#(?P<fee>\$[0-9A-Fa-f]{4})"), "digging game fee deduction",
    )
    if compare_index[1].group("fee") != "$0050" or deduct_index[1].group("fee") != "$0050":
        raise PaidOverworldInteractionsParseError("digging game fee comparison/deduction must both use $0050")
    minigame_call = _single_match(
        digging_lines, digging_open, digging_close,
        re.compile(r"Sprite_InitializeSecondaryItemMinigame"), "digging game minigame initialization",
    )[0]
    transactions.append(_transaction(
        interaction_id="digging-game-entry",
        actor_label="DiggingGameGuy",
        interaction_kind="minigame-entry",
        source_file=digging_file,
        source_label="DiggingGameGuy_DoYouWantToPlay",
        source_range_annotation=digging_range,
        source_annotation_line=digging_range_line,
        fee_model="fixed",
        fee_values=[80],
        fee_expressions=["$0050"],
        fee_table_label=None,
        fee_source_lines=[compare_index[0] + 1, deduct_index[0] + 1],
        payment_source_lines=[deduct_index[0] + 1],
        outcome_label="Sprite_InitializeSecondaryItemMinigame",
        outcome_source_lines=[minigame_call + 1],
        source_revision=source_revision,
    ))

    # Zora King: 500-rupee Flippers transaction.
    zora_file = "sprite_zora_king.asm"
    zora_lines = lines_by_file[zora_file]
    zora_label, zora_open, zora_close = _find_block(zora_lines, "ZoraKing_Dialogue")
    zora_range, zora_range_line = _range_annotation(zora_lines, zora_label, "ZoraKing_Dialogue")
    zora_fee = _single_match(
        zora_lines, zora_open, zora_close,
        re.compile(r"SBC\.w\s+#(?P<fee>\$[0-9A-Fa-f]{4})"), "Zora King Flippers price",
    )
    if zora_fee[1].group("fee") != "$01F4":
        raise PaidOverworldInteractionsParseError("Zora King Flippers price must be $01F4")
    flippers_reward = _single_match(
        zora_lines, zora_open, zora_close,
        re.compile(r"Sprite_SpawnFlippersItem"), "Zora King Flippers reward",
    )[0]
    transactions.append(_transaction(
        interaction_id="zora-king-flippers",
        actor_label="ZoraKing",
        interaction_kind="item-sale",
        source_file=zora_file,
        source_label="ZoraKing_Dialogue",
        source_range_annotation=zora_range,
        source_annotation_line=zora_range_line,
        fee_model="fixed",
        fee_values=[500],
        fee_expressions=["$01F4"],
        fee_table_label=None,
        fee_source_lines=[zora_fee[0] + 1],
        payment_source_lines=[zora_fee[0] + 1],
        outcome_label="Sprite_SpawnFlippersItem",
        outcome_source_lines=[flippers_reward + 1],
        source_revision=source_revision,
    ))

    # Kiki charges 10 rupees to follow, then 100 to continue the access sequence.
    kiki_file = "sprite_kiki.asm"
    kiki_lines = lines_by_file[kiki_file]
    follow_label, follow_open, follow_close = _find_block(kiki_lines, "Kiki_OfferToFollowTransaction")
    follow_range, follow_range_line = _range_annotation(kiki_lines, follow_label, "Kiki_OfferToFollowTransaction")
    follow_fee = _single_match(
        kiki_lines, follow_open, follow_close,
        re.compile(r"LDA\.b\s+#(?P<fee>\$0A)"), "Kiki follow fee",
    )
    follow_pay = _single_match(
        kiki_lines, follow_open, follow_close,
        re.compile(r"ShopKeeper_TryToGetPaid"), "Kiki follow payment helper",
    )[0]
    follow_effect = _single_match(
        kiki_lines, follow_open, follow_close,
        re.compile(r"ORA\.b\s+#\$03\s*:\s*STA\.w\s+\$02F2"), "Kiki follow state update",
    )[0]
    if follow_fee[1].group("fee") != "$0A":
        raise PaidOverworldInteractionsParseError("Kiki follow fee must be $0A")
    transactions.append(_transaction(
        interaction_id="kiki-follow-fee",
        actor_label="Kiki",
        interaction_kind="escort-fee",
        source_file=kiki_file,
        source_label="Kiki_OfferToFollowTransaction",
        source_range_annotation=follow_range,
        source_annotation_line=follow_range_line,
        fee_model="fixed",
        fee_values=[10],
        fee_expressions=["$0A"],
        fee_table_label=None,
        fee_source_lines=[follow_fee[0] + 1],
        payment_source_lines=[follow_pay + 1],
        outcome_label="sets follow-related state bits before Kiki despawns",
        outcome_source_lines=[follow_effect + 1],
        source_revision=source_revision,
    ))

    kiki_purchase_label, purchase_open, purchase_close = _find_block(kiki_lines, "Kiki_VerifyPurchase")
    purchase_range, purchase_range_line = _range_annotation(kiki_lines, kiki_purchase_label, "Kiki_VerifyPurchase")
    purchase_fee = _single_match(
        kiki_lines, purchase_open, purchase_close,
        re.compile(r"LDA\.b\s+#(?P<fee>\$64)"), "Kiki follow-up payment amount",
    )
    purchase_pay = _single_match(
        kiki_lines, purchase_open, purchase_close,
        re.compile(r"ShopKeeper_TryToGetPaid"), "Kiki follow-up payment helper",
    )[0]
    purchase_effects = [
        _single_match(kiki_lines, purchase_open, purchase_close, re.compile(pattern), label)[0] + 1
        for pattern, label in (
            (r"INC\.w\s+\$02E4", "Kiki follow-up event update"),
            (r"INC\.w\s+\$0D80,\s*X", "Kiki follow-up AI-state update"),
            (r"STZ\.w\s+\$0DE0,\s*X", "Kiki follow-up sprite-state reset"),
        )
    ]
    if purchase_fee[1].group("fee") != "$64":
        raise PaidOverworldInteractionsParseError("Kiki follow-up payment must be $64")
    transactions.append(_transaction(
        interaction_id="kiki-palace-access-fee",
        actor_label="Kiki",
        interaction_kind="progression-fee",
        source_file=kiki_file,
        source_label="Kiki_VerifyPurchase",
        source_range_annotation=purchase_range,
        source_annotation_line=purchase_range_line,
        fee_model="fixed",
        fee_values=[100],
        fee_expressions=["$64"],
        fee_table_label=None,
        fee_source_lines=[purchase_fee[0] + 1],
        payment_source_lines=[purchase_pay + 1],
        outcome_label="advances Kiki's post-payment state",
        outcome_source_lines=purchase_effects,
        source_revision=source_revision,
    ))

    # Archery game: 20-rupee play fee is deducted when the game is initialized.
    archery_file = "sprite_archery_game_guy.asm"
    archery_lines = lines_by_file[archery_file]
    archery_label, archery_open, archery_close = _find_block(
        archery_lines, "ArcheryGameGuy_RunGame"
    )
    archery_range, archery_range_line = _range_annotation(
        archery_lines, archery_label, "ArcheryGameGuy_RunGame"
    )
    archery_fee = _single_match(
        archery_lines, archery_open, archery_close,
        re.compile(r"SBC\.b\s+#(?P<fee>\$[0-9A-Fa-f]{4})"), "archery game fee deduction",
    )
    if archery_fee[1].group("fee") != "$0014":
        raise PaidOverworldInteractionsParseError("archery game fee must be $0014")
    archery_init = _single_match(
        archery_lines, archery_open, archery_close,
        re.compile(r"Sprite_InitializeSecondaryItemMinigame"), "archery game initialization",
    )[0]
    transactions.append(_transaction(
        interaction_id="archery-game-entry",
        actor_label="ArcheryGameGuy",
        interaction_kind="minigame-entry",
        source_file=archery_file,
        source_label="ArcheryGameGuy_RunGame",
        source_range_annotation=archery_range,
        source_annotation_line=archery_range_line,
        fee_model="fixed",
        fee_values=[20],
        fee_expressions=["$0014"],
        fee_table_label=None,
        fee_source_lines=[archery_fee[0] + 1],
        payment_source_lines=[archery_fee[0] + 1],
        outcome_label="Sprite_InitializeSecondaryItemMinigame",
        outcome_source_lines=[archery_init + 1, archery_fee[0] + 1],
        source_revision=source_revision,
    ))

    # Lake Hylia Fairy: donation values come from FairyPond.prices.
    ponds_file = "sprite_ponds.asm"
    ponds_lines = lines_by_file[ponds_file]
    pond_label, pond_open, pond_close = _find_block(ponds_lines, "FairyPond")
    prices_local = [
        index for index in range(pond_open + 1, pond_close)
        if _source_code(ponds_lines[index]) == ".prices"
    ]
    if len(prices_local) != 1:
        raise PaidOverworldInteractionsParseError(
            f"expected one FairyPond .prices label; found {len(prices_local)}"
        )
    pond_directive = _next_code(ponds_lines, prices_local[0], pond_close)
    if pond_directive is None:
        raise PaidOverworldInteractionsParseError("FairyPond .prices directive is missing")
    pond_match = re.fullmatch(r"db\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", pond_directive[0], re.IGNORECASE)
    if pond_match is None:
        raise PaidOverworldInteractionsParseError("FairyPond .prices must contain four decimal values")
    pond_values = [int(value) for value in pond_match.groups()]
    if tuple(pond_values) != _POND_VALUES:
        raise PaidOverworldInteractionsParseError(
            f"FairyPond prices changed from {_POND_VALUES}: {pond_values}"
        )
    pond_accept_label, pond_accept_open, pond_accept_close = _find_block(
        ponds_lines, "LakeHyliaFairy_AcceptDonation"
    )
    pond_accept_range, pond_accept_range_line = _range_annotation(
        ponds_lines, pond_accept_label, "LakeHyliaFairy_AcceptDonation"
    )
    donation_deduct = _single_match(
        ponds_lines, pond_accept_open, pond_accept_close,
        re.compile(r"SEC\s*:\s*SBC\.b\s+\$00\s*:\s*STA\.l\s+\$7EF360"),
        "Lake Hylia Fairy donation deduction",
    )[0]
    donation_credit = _single_match(
        ponds_lines, pond_accept_open, pond_accept_close,
        re.compile(r"CLC\s*:\s*ADC\.b\s+\$00\s*:\s*STA\.l\s+\$7EF36A"),
        "Lake Hylia Fairy donation credit",
    )[0]
    happiness_call = _single_match(
        ponds_lines, pond_accept_open, pond_accept_close,
        re.compile(r"AddHappinessPondRupees"), "Lake Hylia Fairy donation counter",
    )[0]
    transactions.append(_transaction(
        interaction_id="lake-hylia-fairy-donation",
        actor_label="LakeHyliaFairy",
        interaction_kind="donation",
        source_file=ponds_file,
        source_label="LakeHyliaFairy_AcceptDonation",
        source_range_annotation=pond_accept_range,
        source_annotation_line=pond_accept_range_line,
        fee_model="selected-price-table",
        fee_values=pond_values,
        fee_expressions=[str(value) for value in pond_values],
        fee_table_label="FairyPond.prices",
        fee_source_lines=[pond_directive[1] + 1],
        payment_source_lines=[donation_deduct + 1],
        outcome_label="adds the selected amount to the happiness-pond total",
        outcome_source_lines=[donation_credit + 1, happiness_call + 1],
        source_revision=source_revision,
    ))

    # The digging-game random dispatch preserves source annotations verbatim.
    prize_label, prize_open, prize_close = _find_block(
        digging_lines, "DiggingGameGuy_AttemptPrizeSpawn"
    )
    prize_range, prize_range_line = _range_annotation(
        digging_lines, prize_label, "DiggingGameGuy_AttemptPrizeSpawn"
    )
    jump_calls = _matches(
        digging_lines, prize_open, prize_close,
        re.compile(r"JSL\.l\s+UseImplicitRegIndexedLocalJumpTable"),
        "digging prize jump-table calls",
    )
    if len(jump_calls) != 1:
        raise PaidOverworldInteractionsParseError(
            f"expected one digging prize jump-table call; found {len(jump_calls)}"
        )
    prize_entries: list[dict[str, Any]] = []
    for index in range(jump_calls[0][0] + 1, prize_close):
        if not _source_code(digging_lines[index]):
            continue
        match = _DIG_DISPATCH_RE.fullmatch(digging_lines[index])
        if match is None:
            raise PaidOverworldInteractionsParseError(
                f"unsupported digging prize dispatch syntax on line {index + 1}"
            )
        table_index = int(match.group("index"), 16)
        if table_index != len(prize_entries):
            raise PaidOverworldInteractionsParseError(
                f"digging prize slot {len(prize_entries)} is annotated as {table_index:#x}"
            )
        prize_entries.append({
            "table_index": table_index,
            "handler_label": match.group("handler"),
            "source_address_annotation": match.group("address").upper(),
            "source_comment": _source_code(digging_lines[index]) and digging_lines[index].split(";", 1)[1].strip(),
            "source_line": index + 1,
        })
    if len(prize_entries) != 8:
        raise PaidOverworldInteractionsParseError(
            f"digging prize dispatch contains {len(prize_entries)} entries; expected 8"
        )

    pool_label, pool_open, pool_close = _find_block(
        digging_lines, "Pool_DiggingGameGuy_GiveItem"
    )
    pool_range, pool_range_line = _range_annotation(
        digging_lines, pool_label, "Pool_DiggingGameGuy_GiveItem"
    )
    pool_slots = [
        index for index in range(pool_open + 1, pool_close)
        if _source_code(digging_lines[index]) == ".basic_types"
    ]
    if len(pool_slots) != 1:
        raise PaidOverworldInteractionsParseError(
            f"expected one digging .basic_types pool; found {len(pool_slots)}"
        )
    pool_entries: list[dict[str, Any]] = []
    for index in range(pool_slots[0] + 1, pool_close):
        code = _source_code(digging_lines[index])
        if not code:
            continue
        match = re.fullmatch(r"db\s+(?P<item>\$[0-9A-Fa-f]{2})", code, re.IGNORECASE)
        if match is None:
            break
        comment = digging_lines[index].split(";", 1)[1].strip() if ";" in digging_lines[index] else ""
        pool_entries.append({
            "table_index": len(pool_entries),
            "expression": match.group("item").upper(),
            "source_comment": comment,
            "source_line": index + 1,
        })
    if len(pool_entries) != 4:
        raise PaidOverworldInteractionsParseError(
            f"digging basic item pool contains {len(pool_entries)} entries; expected 4"
        )

    heart_label, heart_open, heart_close = _find_block(
        digging_lines, "DiggingGameGuy_GiveItem_heart_piece"
    )
    heart_range, heart_range_line = _range_annotation(
        digging_lines, heart_label, "DiggingGameGuy_GiveItem_heart_piece"
    )
    heart_lines = [
        (index + 1, _source_code(digging_lines[index]))
        for index in range(heart_open + 1, heart_close)
        if any(token in _source_code(digging_lines[index]) for token in (
            "$7FFE01", "$19", "$7FFE00", "GetRandomInt", "AND.b #$03", "$EB",
        ))
    ]
    if len(heart_lines) != 4:
        raise PaidOverworldInteractionsParseError(
            f"digging heart-piece gate has {len(heart_lines)} relevant condition/effect lines; expected 4"
        )
    heart_conditions = [expression for _line, expression in heart_lines]
    if (
        "$7FFE01" not in heart_conditions[0]
        or "$19" not in heart_conditions[0]
        or "$7FFE00" not in heart_conditions[1]
        or "GetRandomInt" not in heart_conditions[2]
        or "$EB" not in heart_conditions[3]
    ):
        raise PaidOverworldInteractionsParseError("digging heart-piece gate no longer matches expected source shape")

    return {
        "format": PAID_OVERWORLD_INTERACTIONS_FORMAT,
        "format_version": 1,
        "source_revision": source_revision,
        "source_files": list(PAID_OVERWORLD_SOURCE_FILES),
        "interaction_count": len(transactions),
        "interactions": transactions,
        "reward_tables": [
            {
                "table_id": "digging-game-random-reward-dispatch",
                "table_kind": "jump-table",
                "source_file": digging_file,
                "source_label": "DiggingGameGuy_AttemptPrizeSpawn",
                "source_range_annotation": prize_range,
                "source_annotation_line": prize_range_line,
                "entry_count": len(prize_entries),
                "entries": prize_entries,
                "source_revision": source_revision,
            },
            {
                "table_id": "digging-game-basic-reward-pool",
                "table_kind": "item-pool",
                "source_file": digging_file,
                "source_label": "Pool_DiggingGameGuy_GiveItem.basic_types",
                "source_range_annotation": pool_range,
                "source_annotation_line": pool_range_line,
                "entry_count": len(pool_entries),
                "entries": pool_entries,
                "source_revision": source_revision,
            },
        ],
        "reward_gates": [
            {
                "gate_id": "digging-game-heart-piece",
                "source_file": digging_file,
                "source_label": "DiggingGameGuy_GiveItem_heart_piece",
                "source_range_annotation": heart_range,
                "source_annotation_line": heart_range_line,
                "condition_source_lines": [line for line, _expression in heart_lines],
                "condition_expressions": heart_conditions,
                "minimum_hole_count": 25,
                "required_state_expression": "$7FFE00 == 0",
                "random_mask_expression": "#$03",
                "successful_random_value": 0,
                "reward_flag_write_expression": "LDA.b #$EB : STA.l $7FFE00",
                "source_revision": source_revision,
            }
        ],
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "source_range_annotations_verified": False,
            "fee_behavior_runtime_verified": False,
            "reward_probability_runtime_verified": False,
            "item_value_names_resolved": False,
            "payment_semantics_runtime_verified": False,
        },
    }
