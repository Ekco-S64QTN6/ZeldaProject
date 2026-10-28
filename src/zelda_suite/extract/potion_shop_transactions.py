"""Parse source-coded potion-shop purchases without claiming runtime verification."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

POTION_SHOP_TRANSACTIONS_FORMAT = "zelda-suite-potion-shop-transactions"
POTION_SHOP_TRANSACTIONS_SOURCE_FILE = "sprite_potion_shop.asm"
POTION_SHOP_TRANSACTION_COUNT = 3
POTION_SHOP_HANDLER_LABELS = (
    "Sprite_GreenPotionItem",
    "Sprite_BluePotionItem",
    "Sprite_RedPotionItem",
)

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_RANGE_RE = re.compile(
    r"^\s*;\s*(?P<range>\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+"
    r"(?:\s+LOCAL)?\s+JUMP LOCATION)\s*$",
    re.IGNORECASE,
)
_PRICE_COMPARE_RE = re.compile(
    r"^\s*LDA\.l\s+(?P<address>\$[0-9A-Fa-f]{6})\s*:\s*"
    r"CMP\.w\s+#(?P<literal>\$[0-9A-Fa-f]{4})\b.*$",
    re.IGNORECASE,
)
_PRICE_DEDUCTION_RE = re.compile(
    r"^\s*LDA\.l\s+(?P<load_address>\$[0-9A-Fa-f]{6})\s*:\s*"
    r"SEC\s*:\s*SBC\.w\s+#(?P<literal>\$[0-9A-Fa-f]{4})\s*:\s*"
    r"STA\.l\s+(?P<store_address>\$[0-9A-Fa-f]{6})\s*$",
    re.IGNORECASE,
)
_EMPTY_BOTTLE_CHECK_RE = re.compile(
    r"^\s*JSL\.l\s+Sprite_GetEmptyBottleIndex\b.*$",
    re.IGNORECASE,
)
_RECEIPT_CALL_RE = re.compile(r"^\s*JSL\.l\s+Link_ReceiveItem\s*$", re.IGNORECASE)
_RECEIPT_SELECTOR_RE = re.compile(
    r"^\s*LDY\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})\s*$",
    re.IGNORECASE,
)


class PotionShopTransactionsParseError(ValueError):
    """Raised when a potion-shop transaction block differs from expected source shape."""


@dataclass(frozen=True, slots=True)
class PotionShopTransactionEntry:
    """One potion-shop handler with source-commented payment and receipt literals."""

    table_index: int
    handler_label: str
    source_handler_range_annotation: str
    source_handler_label_line: int
    rupee_balance_address_expression: str
    price_compare_expression: str
    price_compare_source_line: int
    price_deduction_expression: str
    price_deduction_source_line: int
    price_value: int
    receipt_index_expression: str
    receipt_item_index: int
    receipt_selector_source_line: int
    receipt_call_source_line: int
    empty_bottle_check_source_line: int
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PotionShopTransactionsTable:
    """Versioned source-only catalog of green, blue, and red potion transactions."""

    source_file: str
    source_revision: str
    entries: list[PotionShopTransactionEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": POTION_SHOP_TRANSACTIONS_FORMAT,
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "evidence": {
                "source_only": True,
                "rom_bytes_read": False,
                "price_behavior_runtime_verified": False,
                "source_range_annotations_verified": False,
                "receipt_item_names_resolved": False,
                "room_specific_shop_stock_resolved": False,
                "canonical_item_ids_resolved": False,
            },
        }


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
        raise PotionShopTransactionsParseError(
            f"expected exactly one {label!r} label; found {len(hits)}"
        )
    return hits[0]


def _find_block(lines: list[str], label: str) -> tuple[int, int, int]:
    label_index = _find_label(lines, label)
    open_index = label_index + 1
    while open_index < len(lines) and not _source_code(lines[open_index]):
        open_index += 1
    if open_index >= len(lines) or _source_code(lines[open_index]) != "{":
        raise PotionShopTransactionsParseError(
            f"opening brace missing after {label!r} on line {label_index + 1}"
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
    raise PotionShopTransactionsParseError(
        f"closing brace missing for {label!r} starting on line {open_index + 1}"
    )


def _handler_range(lines: list[str], label_index: int, label: str) -> str:
    if label_index == 0:
        raise PotionShopTransactionsParseError(
            f"source range annotation is missing above {label!r}"
        )
    match = _RANGE_RE.fullmatch(lines[label_index - 1])
    if match is None:
        raise PotionShopTransactionsParseError(
            f"source range annotation immediately above {label!r} is malformed or missing"
        )
    return match.group("range")


def parse_potion_shop_transactions(
    source: str,
    *,
    source_revision: str,
    source_file: str = POTION_SHOP_TRANSACTIONS_SOURCE_FILE,
    expected_entry_count: int = POTION_SHOP_TRANSACTION_COUNT,
) -> PotionShopTransactionsTable:
    """Parse the three potion purchases and preserve source-derived price/selector fields.

    The routine range and table/handler addresses are source comments, not verified
    ROM offsets. The parser confirms literal comparison/deduction parity and the
    nearby receive-item selector but does not assert runtime semantics.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")
    if expected_entry_count != POTION_SHOP_TRANSACTION_COUNT:
        raise PotionShopTransactionsParseError(
            f"expected_entry_count must be {POTION_SHOP_TRANSACTION_COUNT}"
        )

    lines = source.splitlines()
    entries: list[PotionShopTransactionEntry] = []
    for table_index, label in enumerate(POTION_SHOP_HANDLER_LABELS):
        label_index, open_index, close_index = _find_block(lines, label)
        range_annotation = _handler_range(lines, label_index, label)
        compare_lines: list[tuple[int, re.Match[str]]] = []
        deduction_lines: list[tuple[int, re.Match[str]]] = []
        bottle_lines: list[int] = []
        receipt_calls: list[int] = []

        for index in range(open_index + 1, close_index):
            code = _source_code(lines[index])
            compare = _PRICE_COMPARE_RE.fullmatch(code)
            if compare is not None:
                compare_lines.append((index, compare))
            deduction = _PRICE_DEDUCTION_RE.fullmatch(code)
            if deduction is not None:
                deduction_lines.append((index, deduction))
            if _EMPTY_BOTTLE_CHECK_RE.fullmatch(code) is not None:
                bottle_lines.append(index)
            if _RECEIPT_CALL_RE.fullmatch(code) is not None:
                receipt_calls.append(index)

        if len(compare_lines) != 1:
            raise PotionShopTransactionsParseError(
                f"{label!r} has {len(compare_lines)} rupee-balance comparison lines; expected one"
            )
        if len(deduction_lines) != 1:
            raise PotionShopTransactionsParseError(
                f"{label!r} has {len(deduction_lines)} rupee-balance deduction lines; expected one"
            )
        if len(bottle_lines) != 1:
            raise PotionShopTransactionsParseError(
                f"{label!r} has {len(bottle_lines)} empty-bottle checks; expected one"
            )
        if len(receipt_calls) != 1:
            raise PotionShopTransactionsParseError(
                f"{label!r} has {len(receipt_calls)} Link_ReceiveItem calls; expected one"
            )

        compare_line, compare_match = compare_lines[0]
        deduction_line, deduction_match = deduction_lines[0]
        balance_address = compare_match.group("address").upper()
        deduction_load_address = deduction_match.group("load_address").upper()
        deduction_store_address = deduction_match.group("store_address").upper()
        compare_expression = compare_match.group("literal").upper()
        deduction_expression = deduction_match.group("literal").upper()

        if balance_address != deduction_load_address or balance_address != deduction_store_address:
            raise PotionShopTransactionsParseError(
                f"{label!r} compares and deducts from different rupee-balance addresses"
            )
        if compare_expression != deduction_expression:
            raise PotionShopTransactionsParseError(
                f"{label!r} compare literal {compare_expression} does not match "
                f"deduction literal {deduction_expression}"
            )

        receipt_call_line = receipt_calls[0]
        previous_code_indexes = [
            index
            for index in range(open_index + 1, receipt_call_line)
            if _source_code(lines[index])
        ][-4:]
        selector_match: re.Match[str] | None = None
        selector_line = -1
        for index in reversed(previous_code_indexes):
            selector_match = _RECEIPT_SELECTOR_RE.fullmatch(_source_code(lines[index]))
            if selector_match is not None:
                selector_line = index
                break
        if selector_match is None:
            raise PotionShopTransactionsParseError(
                f"{label!r} Link_ReceiveItem call has no nearby literal Y receipt selector"
            )

        receipt_expression = selector_match.group("literal").upper()
        receipt_index = int(receipt_expression[1:], 16)
        price_value = int(compare_expression[1:], 16)
        entries.append(PotionShopTransactionEntry(
            table_index=table_index,
            handler_label=label,
            source_handler_range_annotation=range_annotation,
            source_handler_label_line=label_index + 1,
            rupee_balance_address_expression=balance_address,
            price_compare_expression=compare_expression,
            price_compare_source_line=compare_line + 1,
            price_deduction_expression=deduction_expression,
            price_deduction_source_line=deduction_line + 1,
            price_value=price_value,
            receipt_index_expression=receipt_expression,
            receipt_item_index=receipt_index,
            receipt_selector_source_line=selector_line + 1,
            receipt_call_source_line=receipt_call_line + 1,
            empty_bottle_check_source_line=bottle_lines[0] + 1,
            source_revision=source_revision,
        ))

    return PotionShopTransactionsTable(
        source_file=source_file,
        source_revision=source_revision,
        entries=entries,
    )
