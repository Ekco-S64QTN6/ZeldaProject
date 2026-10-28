"""Parse source-coded Bomb Shop and Bottle Vendor purchase paths."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

SPECIAL_SHOP_TRANSACTIONS_FORMAT = "zelda-suite-special-shop-transactions"
SPECIAL_SHOP_TRANSACTIONS_ENTRY_COUNT = 3
SPECIAL_SHOP_TRANSACTIONS_SOURCE_REVISION = (
    "347c23f9fc019c72d32da537c9cb235f468d021d"
)
BOMB_SHOP_SOURCE_FILE = "sprite_bomb_shop_entity.asm"
BOTTLE_VENDOR_SOURCE_FILE = "sprite_bottle_vendor.asm"

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_RANGE_RE = re.compile(
    r"^\s*;\s*(?P<range>\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+"
    r"(?:\s+LOCAL)?\s+JUMP LOCATION)\s*$",
    re.IGNORECASE,
)
_PAYMENT_LOW_RE = re.compile(
    r"^\s*LDA\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})(?:\s*:.*)?$",
    re.IGNORECASE,
)
_PAYMENT_HIGH_RE = re.compile(
    r"^\s*LDY\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})(?:\s*:.*)?$",
    re.IGNORECASE,
)
_PAYMENT_CALL_RE = re.compile(
    r"^\s*JSR\.w\s+ShopKeeper_TryToGetPaid(?:\s*:.*)?$", re.IGNORECASE
)
_SHOP_RECEIPT_CALL_RE = re.compile(
    r"^\s*JSR\.w\s+ShopItem_HandleReceipt\s*$", re.IGNORECASE
)
_RECEIVE_ITEM_CALL_RE = re.compile(
    r"^\s*JSL\.l\s+Link_ReceiveItem\s*$", re.IGNORECASE
)
_SELECTOR_RE = re.compile(
    r"^\s*LDY\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})(?:\s*:.*)?$", re.IGNORECASE
)
_PRICE_COMPARE_RE = re.compile(
    r"\bCMP\.w\s+#(?P<literal>\$[0-9A-Fa-f]{4})\b", re.IGNORECASE
)
_PRICE_DEDUCTION_RE = re.compile(
    r"\bSBC\.w\s+#(?P<literal>\$[0-9A-Fa-f]{4})\b", re.IGNORECASE
)
_BALANCE_ADDRESS_RE = re.compile(r"\bLDA\.l\s+(?P<address>\$7EF360)\b", re.IGNORECASE)
_REWARD_FLAG_RE = re.compile(
    r"\bLDA\.b\s+#(?P<value>\$[0-9A-Fa-f]{2})\s*:\s*STA\.l\s+"
    r"(?P<address>\$[0-9A-Fa-f]{6})\b",
    re.IGNORECASE,
)
_TAGALONG_SPAWN_RE = re.compile(
    r"^\s*JSL\.l\s+Tagalong_SpawnFromSprite\s*$", re.IGNORECASE
)
_ITEM_ANNOTATION_RE = re.compile(
    r"^\s*;\s*\\item\((?P<label>[^)]+)\)\s*$", re.IGNORECASE
)


class SpecialShopTransactionsParseError(ValueError):
    """Raised when the pinned special-shop purchase source shape is malformed."""


@dataclass(frozen=True, slots=True)
class SpecialShopTransactionEntry:
    """One source-only Bomb Shop or Bottle Vendor transaction."""

    table_index: int
    transaction_label: str
    shop_type: str
    source_file: str
    source_handler_label: str
    source_handler_range_annotation: str
    source_handler_label_line: int
    reward_handler_label: str
    reward_handler_range_annotation: str
    reward_handler_label_line: int
    price_mode: str
    price_value: int
    price_low_expression: str | None
    price_low_source_line: int | None
    price_high_expression: str | None
    price_high_source_line: int | None
    price_compare_expression: str | None
    price_compare_source_line: int | None
    price_deduction_expression: str | None
    price_deduction_source_line: int | None
    rupee_balance_address_expression: str | None
    payment_call_source_line: int | None
    receipt_method: str
    receipt_item_index: int | None
    receipt_index_expression: str | None
    receipt_selector_source_line: int | None
    receipt_call_source_line: int | None
    source_item_annotation: str | None
    source_item_annotation_line: int | None
    reward_flag_address_expression: str | None
    reward_flag_value_expression: str | None
    reward_flag_source_line: int | None
    source_reward_comment: str | None
    tagalong_spawn_source_line: int | None
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SpecialShopTransactionsTable:
    """Versioned source inventory of Bomb Shop and Bottle Vendor purchases."""

    source_revision: str
    entries: list[SpecialShopTransactionEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": SPECIAL_SHOP_TRANSACTIONS_FORMAT,
            "format_version": 1,
            "source_revision": self.source_revision,
            "source_file": ";".join(sorted({entry.source_file for entry in self.entries})),
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "evidence": {
                "source_only": True,
                "rom_bytes_read": False,
                "source_range_annotations_verified": False,
                "price_behavior_runtime_verified": False,
                "receipt_item_names_resolved": False,
                "room_specific_shop_stock_resolved": False,
                "canonical_item_ids_resolved": False,
                "special_bomb_reward_runtime_verified": False,
            },
        }


def _source_code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _find_label(lines: list[str], label: str, source_file: str) -> int:
    hits = [
        index
        for index, line in enumerate(lines)
        if (match := _LABEL_RE.fullmatch(_source_code(line))) is not None
        and match.group("label") == label
    ]
    if len(hits) != 1:
        raise SpecialShopTransactionsParseError(
            f"{source_file}: expected exactly one {label!r} label; found {len(hits)}"
        )
    return hits[0]


def _find_block(
    lines: list[str], label: str, source_file: str
) -> tuple[int, int, int]:
    label_index = _find_label(lines, label, source_file)
    open_index = label_index + 1
    while open_index < len(lines) and not _source_code(lines[open_index]):
        open_index += 1
    if open_index >= len(lines) or _source_code(lines[open_index]) != "{":
        raise SpecialShopTransactionsParseError(
            f"{source_file}: opening brace missing after {label!r} on line {label_index + 1}"
        )
    depth = 1
    for index in range(open_index + 1, len(lines)):
        code = _source_code(lines[index])
        depth += code.count("{")
        depth -= code.count("}")
        if depth == 0:
            return label_index, open_index, index
        if depth < 0:
            break
    raise SpecialShopTransactionsParseError(
        f"{source_file}: closing brace missing for {label!r}"
    )


def _handler_range(
    lines: list[str], label_index: int, label: str, source_file: str
) -> str:
    if label_index == 0:
        raise SpecialShopTransactionsParseError(
            f"{source_file}: source range annotation missing above {label!r}"
        )
    match = _RANGE_RE.fullmatch(lines[label_index - 1])
    if match is None:
        raise SpecialShopTransactionsParseError(
            f"{source_file}: source range annotation malformed above {label!r}"
        )
    return match.group("range")


def _next_code(
    lines: list[str], start: int, end: int
) -> tuple[str, int] | None:
    for index in range(start + 1, end):
        code = _source_code(lines[index])
        if code:
            return code, index
    return None


def _payment_registers(
    lines: list[str], block: tuple[int, int, int], label: str, source_file: str
) -> tuple[str, int, str, int, int, int]:
    _, open_index, close_index = block
    matches: list[tuple[str, int, str, int, int, int]] = []
    for index in range(open_index + 1, close_index):
        low_match = _PAYMENT_LOW_RE.fullmatch(_source_code(lines[index]))
        if low_match is None:
            continue
        high = _next_code(lines, index, close_index)
        payment = _next_code(lines, high[1], close_index) if high is not None else None
        if high is None or payment is None:
            continue
        high_match = _PAYMENT_HIGH_RE.fullmatch(high[0])
        if high_match is None or _PAYMENT_CALL_RE.fullmatch(payment[0]) is None:
            continue
        low_expression = low_match.group("literal").upper()
        high_expression = high_match.group("literal").upper()
        matches.append((
            low_expression,
            index + 1,
            high_expression,
            high[1] + 1,
            payment[1] + 1,
            (int(high_expression[1:], 16) << 8) | int(low_expression[1:], 16),
        ))
    if len(matches) != 1:
        raise SpecialShopTransactionsParseError(
            f"{source_file}: expected one source-coded price/payment sequence in {label!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _receipt_selector(
    lines: list[str],
    block: tuple[int, int, int],
    label: str,
    source_file: str,
    call_re: re.Pattern[str],
    method: str,
) -> tuple[str, int, int]:
    _, open_index, close_index = block
    matches: list[tuple[str, int, int]] = []
    for index in range(open_index + 1, close_index):
        if call_re.fullmatch(_source_code(lines[index])) is None:
            continue
        selector = None
        for previous in range(index - 1, open_index, -1):
            code = _source_code(lines[previous])
            if not code:
                continue
            match = _SELECTOR_RE.fullmatch(code)
            if match is not None:
                selector = (match.group("literal").upper(), previous + 1, index + 1)
                break
        if selector is None:
            raise SpecialShopTransactionsParseError(
                f"{source_file}: {method} call in {label!r} has no preceding literal Y selector"
            )
        matches.append(selector)
    if len(matches) != 1:
        raise SpecialShopTransactionsParseError(
            f"{source_file}: expected one {method} call in {label!r}; found {len(matches)}"
        )
    return matches[0]


def parse_special_shop_transactions(
    bomb_shop_source: str,
    bottle_vendor_source: str,
    *,
    source_revision: str = SPECIAL_SHOP_TRANSACTIONS_SOURCE_REVISION,
    bomb_shop_source_file: str = BOMB_SHOP_SOURCE_FILE,
    bottle_vendor_source_file: str = BOTTLE_VENDOR_SOURCE_FILE,
    expected_entry_count: int = SPECIAL_SHOP_TRANSACTIONS_ENTRY_COUNT,
) -> SpecialShopTransactionsTable:
    """Parse two Bomb Shop transactions and the Bottle Vendor bottle sale.

    Bomb Shop prices are read from A/Y literals passed to the payment helper.
    The Bottle Vendor price comes from its wallet comparison and deduction.
    The Super Bomb's flag/tagalong reward stays separate from receipt selectors.
    """
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")

    bomb_lines = bomb_shop_source.splitlines()
    bottle_lines = bottle_vendor_source.splitlines()
    entries: list[SpecialShopTransactionEntry] = []

    bomb_definitions = (
        ("Bomb Shop Bomb", "Sprite_BombShopBomb", "$28"),
        ("Bomb Shop Super Bomb", "Sprite_BombShopSuperBomb", None),
    )
    for transaction_label, handler_label, expected_receipt in bomb_definitions:
        block = _find_block(bomb_lines, handler_label, bomb_shop_source_file)
        handler_range = _handler_range(
            bomb_lines, block[0], handler_label, bomb_shop_source_file
        )
        low, low_line, high, high_line, payment_line, price = _payment_registers(
            bomb_lines, block, handler_label, bomb_shop_source_file
        )
        if price != 100 or high != "$00":
            raise SpecialShopTransactionsParseError(
                f"{bomb_shop_source_file}: {handler_label!r} must encode a 100-rupee price"
            )

        if expected_receipt is not None:
            receipt_expression, receipt_line, receipt_call_line = _receipt_selector(
                bomb_lines, block, handler_label, bomb_shop_source_file,
                _SHOP_RECEIPT_CALL_RE, "ShopItem_HandleReceipt",
            )
            if receipt_expression != expected_receipt:
                raise SpecialShopTransactionsParseError(
                    f"{bomb_shop_source_file}: {handler_label!r} receipt selector must be {expected_receipt}"
                )
            receipt_index = int(receipt_expression[1:], 16)
            receipt_method = "ShopItem_HandleReceipt"
            reward_flag_address = None
            reward_flag_value = None
            reward_flag_line = None
            reward_comment = None
            tagalong_line = None
        else:
            receipt_expression = None
            receipt_line = None
            receipt_call_line = None
            receipt_index = None
            receipt_method = "special-bomb-flag-and-tagalong"
            reward_match = None
            reward_line = None
            reward_comment = None
            for index in range(block[1] + 1, block[2]):
                match = _REWARD_FLAG_RE.search(_source_code(bomb_lines[index]))
                if match is not None:
                    reward_match = match
                    reward_line = index + 1
                    reward_comment = (
                        bomb_lines[index].split(";", 1)[1].strip()
                        if ";" in bomb_lines[index]
                        else None
                    )
                    break
            if reward_match is None or reward_line is None:
                raise SpecialShopTransactionsParseError(
                    f"{bomb_shop_source_file}: {handler_label!r} reward flag write missing"
                )
            tagalong_lines = [
                index + 1 for index in range(block[1] + 1, block[2])
                if _TAGALONG_SPAWN_RE.fullmatch(_source_code(bomb_lines[index])) is not None
            ]
            if len(tagalong_lines) != 1:
                raise SpecialShopTransactionsParseError(
                    f"{bomb_shop_source_file}: {handler_label!r} must contain one tagalong spawn call"
                )
            reward_flag_address = reward_match.group("address").upper()
            reward_flag_value = reward_match.group("value").upper()
            reward_flag_line = reward_line
            tagalong_line = tagalong_lines[0]

        entries.append(SpecialShopTransactionEntry(
            table_index=len(entries),
            transaction_label=transaction_label,
            shop_type="bomb-shop",
            source_file=bomb_shop_source_file,
            source_handler_label=handler_label,
            source_handler_range_annotation=handler_range,
            source_handler_label_line=block[0] + 1,
            reward_handler_label=handler_label,
            reward_handler_range_annotation=handler_range,
            reward_handler_label_line=block[0] + 1,
            price_mode="shopkeeper-a-y-registers",
            price_value=price,
            price_low_expression=low,
            price_low_source_line=low_line,
            price_high_expression=high,
            price_high_source_line=high_line,
            price_compare_expression=None,
            price_compare_source_line=None,
            price_deduction_expression=None,
            price_deduction_source_line=None,
            rupee_balance_address_expression=None,
            payment_call_source_line=payment_line,
            receipt_method=receipt_method,
            receipt_item_index=receipt_index,
            receipt_index_expression=receipt_expression,
            receipt_selector_source_line=receipt_line,
            receipt_call_source_line=receipt_call_line,
            source_item_annotation=None,
            source_item_annotation_line=None,
            reward_flag_address_expression=reward_flag_address,
            reward_flag_value_expression=reward_flag_value,
            reward_flag_source_line=reward_flag_line,
            source_reward_comment=reward_comment,
            tagalong_spawn_source_line=tagalong_line,
            source_revision=source_revision,
        ))

    selling_block = _find_block(
        bottle_lines, "BottleVendor_SellingBottle", bottle_vendor_source_file
    )
    giving_block = _find_block(
        bottle_lines, "BottleVendor_GiveBottle", bottle_vendor_source_file
    )
    selling_range = _handler_range(
        bottle_lines, selling_block[0], "BottleVendor_SellingBottle", bottle_vendor_source_file
    )
    giving_range = _handler_range(
        bottle_lines, giving_block[0], "BottleVendor_GiveBottle", bottle_vendor_source_file
    )

    comparisons: list[tuple[str, int, str]] = []
    for index in range(selling_block[1] + 1, selling_block[2]):
        code = _source_code(bottle_lines[index])
        price_match = _PRICE_COMPARE_RE.search(code)
        balance_match = _BALANCE_ADDRESS_RE.search(code)
        if price_match is not None and balance_match is not None:
            comparisons.append((
                price_match.group("literal").upper(), index + 1,
                balance_match.group("address").upper(),
            ))
    if len(comparisons) != 1:
        raise SpecialShopTransactionsParseError(
            f"{bottle_vendor_source_file}: expected one rupee-balance price check; found {len(comparisons)}"
        )
    compare_expression, compare_line, balance_address = comparisons[0]

    deductions: list[tuple[str, int]] = []
    for index in range(giving_block[1] + 1, giving_block[2]):
        match = _PRICE_DEDUCTION_RE.search(_source_code(bottle_lines[index]))
        if match is not None:
            deductions.append((match.group("literal").upper(), index + 1))
    if len(deductions) != 1 or deductions[0][0] != compare_expression:
        raise SpecialShopTransactionsParseError(
            f"{bottle_vendor_source_file}: BottleVendor price check/deduction literals disagree"
        )
    price = int(compare_expression[1:], 16)
    if price != 100:
        raise SpecialShopTransactionsParseError(
            f"{bottle_vendor_source_file}: BottleVendor sale price must be 100; found {price}"
        )

    receipt_expression, receipt_line, receipt_call_line = _receipt_selector(
        bottle_lines, giving_block, "BottleVendor_GiveBottle", bottle_vendor_source_file,
        _RECEIVE_ITEM_CALL_RE, "Link_ReceiveItem",
    )
    if receipt_expression != "$16":
        raise SpecialShopTransactionsParseError(
            f"{bottle_vendor_source_file}: BottleVendor receipt selector must be $16"
        )
    annotations: list[tuple[str, int]] = []
    for index in range(giving_block[1] + 1, giving_block[2]):
        match = _ITEM_ANNOTATION_RE.fullmatch(bottle_lines[index])
        if match is not None:
            annotations.append((match.group("label"), index + 1))
    if len(annotations) != 1:
        raise SpecialShopTransactionsParseError(
            f"{bottle_vendor_source_file}: expected one item source comment"
        )
    item_annotation, item_annotation_line = annotations[0]

    entries.append(SpecialShopTransactionEntry(
        table_index=len(entries),
        transaction_label="Bottle Vendor Bottle Sale",
        shop_type="bottle-vendor",
        source_file=bottle_vendor_source_file,
        source_handler_label="BottleVendor_SellingBottle",
        source_handler_range_annotation=selling_range,
        source_handler_label_line=selling_block[0] + 1,
        reward_handler_label="BottleVendor_GiveBottle",
        reward_handler_range_annotation=giving_range,
        reward_handler_label_line=giving_block[0] + 1,
        price_mode="wallet-balance-compare-and-deduction",
        price_value=price,
        price_low_expression=None,
        price_low_source_line=None,
        price_high_expression=None,
        price_high_source_line=None,
        price_compare_expression=compare_expression,
        price_compare_source_line=compare_line,
        price_deduction_expression=deductions[0][0],
        price_deduction_source_line=deductions[0][1],
        rupee_balance_address_expression=balance_address,
        payment_call_source_line=None,
        receipt_method="Link_ReceiveItem",
        receipt_item_index=int(receipt_expression[1:], 16),
        receipt_index_expression=receipt_expression,
        receipt_selector_source_line=receipt_line,
        receipt_call_source_line=receipt_call_line,
        source_item_annotation=item_annotation,
        source_item_annotation_line=item_annotation_line,
        reward_flag_address_expression=None,
        reward_flag_value_expression=None,
        reward_flag_source_line=None,
        source_reward_comment=None,
        tagalong_spawn_source_line=None,
        source_revision=source_revision,
    ))
    if len(entries) != expected_entry_count:
        raise SpecialShopTransactionsParseError(
            f"found {len(entries)} special shop transactions; expected {expected_entry_count}"
        )
    return SpecialShopTransactionsTable(source_revision=source_revision, entries=entries)
