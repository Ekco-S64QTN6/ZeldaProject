"""Parse source-commented standard shopkeeper purchase handlers."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

SHOP_ITEM_HANDLERS_FORMAT = "zelda-suite-shop-item-handlers"
SHOP_ITEM_HANDLERS_SOURCE_FILE = "sprite_shopkeeper.asm"
SHOP_ITEM_HANDLERS_DISPATCH_LABEL = "Sprite_ShopKeeper"
SHOP_ITEM_HANDLERS_ENTRY_COUNT = 7
SHOP_ITEM_HANDLERS_DISPATCH_COUNT = 14

_LABEL_RE = re.compile(r"^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_DISPATCH_RE = re.compile(r"^\s*JSL\.l\s+UseImplicitRegIndexedLocalJumpTable\s*$", re.IGNORECASE)
_DISPATCH_ENTRY_RE = re.compile(r"^\s*dw\s+(?P<handler>[A-Za-z_][A-Za-z0-9_]*)\s*$", re.IGNORECASE)
_DISPATCH_COMMENT_RE = re.compile(
    r"0x(?P<selector>[0-9A-Fa-f]{2})\s*-\s*(?P<address>\$[0-9A-Fa-f]{4})(?:\s+(?P<description>.*))?\Z"
)
_RANGE_RE = re.compile(
    r"^\s*;\s*(?P<range>\$[0-9A-Fa-f]+-\$[0-9A-Fa-f]+\s+JUMP LOCATION)\s*$",
    re.IGNORECASE,
)
_LOW_PRICE_RE = re.compile(r"^\s*LDA\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})\s*$", re.IGNORECASE)
_HIGH_PRICE_RE = re.compile(r"^\s*LDY\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})\s*$", re.IGNORECASE)
_PAYMENT_RE = re.compile(r"^\s*JSR\.w\s+ShopKeeper_TryToGetPaid(?:\s*:.*)?\s*$", re.IGNORECASE)
_RECEIPT_RE = re.compile(r"^\s*JSR\.w\s+ShopItem_HandleReceipt\s*$", re.IGNORECASE)
_RECEIPT_SELECTOR_RE = re.compile(r"^\s*LDY\.b\s+#(?P<literal>\$[0-9A-Fa-f]{2})\s*$", re.IGNORECASE)


class ShopItemHandlersParseError(ValueError):
    """Raised when source shop-item dispatch or purchase data is malformed."""


@dataclass(frozen=True, slots=True)
class ShopItemHandlerEntry:
    """One source-derived standard-shopkeeper purchase handler."""

    table_index: int
    shopkeeper_variant_id: int
    handler_label: str
    source_handler_address_annotation: str
    source_dispatch_comment: str
    source_dispatch_line: int
    source_handler_range_annotation: str
    source_handler_label_line: int
    price_low_expression: str
    price_low_source_line: int
    price_high_expression: str
    price_high_source_line: int
    price_value: int
    payment_call_source_line: int
    receipt_item_index: int
    receipt_index_expression: str
    receipt_selector_source_line: int
    receipt_call_source_line: int
    source_revision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ShopItemHandlersTable:
    """Source-only catalog of the seven standard shopkeeper purchase handlers."""

    source_file: str
    source_revision: str
    dispatch_routine_label: str
    dispatch_routine_source_range_annotation: str
    entries: list[ShopItemHandlerEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": SHOP_ITEM_HANDLERS_FORMAT,
            "format_version": 1,
            "source_file": self.source_file,
            "source_revision": self.source_revision,
            "dispatch_routine_label": self.dispatch_routine_label,
            "dispatch_routine_source_range_annotation": self.dispatch_routine_source_range_annotation,
            "dispatch_table_file_offset": None,
            "dispatch_table_offset_established": False,
            "dispatch_entry_count": SHOP_ITEM_HANDLERS_DISPATCH_COUNT,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "evidence": {
                "source_only": True,
                "rom_bytes_read": False,
                "dispatch_table_offset_established": False,
                "handler_address_annotations_verified": False,
                "price_behavior_runtime_verified": False,
                "receipt_item_names_resolved": False,
                "room_specific_shop_stock_resolved": False,
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
        raise ShopItemHandlersParseError(
            f"expected exactly one {label!r} label; found {len(hits)}"
        )
    return hits[0]


def _find_block(lines: list[str], label: str) -> tuple[int, int, int]:
    label_index = _find_label(lines, label)
    open_index = label_index + 1
    while open_index < len(lines) and not _source_code(lines[open_index]):
        open_index += 1
    if open_index >= len(lines) or _source_code(lines[open_index]) != "{":
        raise ShopItemHandlersParseError(
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
    raise ShopItemHandlersParseError(
        f"closing brace missing for {label!r} starting on line {open_index + 1}"
    )


def _next_code(lines: list[str], start: int, end: int) -> tuple[str, int] | None:
    for index in range(start + 1, end):
        value = _source_code(lines[index])
        if value:
            return value, index
    return None


def _routine_range(lines: list[str], label_index: int, label: str) -> str:
    for index in range(label_index - 1, max(-1, label_index - 5), -1):
        if not lines[index].strip():
            continue
        match = _RANGE_RE.fullmatch(lines[index])
        if match is None:
            break
        return match.group("range")
    raise ShopItemHandlersParseError(
        f"source JUMP LOCATION range annotation is missing above {label!r}"
    )


def parse_shop_item_handlers(
    source: str,
    *,
    source_revision: str,
    source_file: str = SHOP_ITEM_HANDLERS_SOURCE_FILE,
    dispatch_routine_label: str = SHOP_ITEM_HANDLERS_DISPATCH_LABEL,
    expected_entry_count: int = SHOP_ITEM_HANDLERS_ENTRY_COUNT,
) -> ShopItemHandlersTable:
    """Parse purchase prices and receive-item slot selectors without naming items.

    The inline dispatch table offset remains unset: only the containing routine
    range is annotated. Handler addresses and range annotations are preserved
    as source comments, not verified ROM offsets.
    """
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("source_file must be non-empty")
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError("source_revision must be non-empty")
    if isinstance(expected_entry_count, bool) or not isinstance(expected_entry_count, int):
        raise TypeError("expected_entry_count must be an integer")
    if expected_entry_count <= 0:
        raise ValueError("expected_entry_count must be positive")

    lines = source.splitlines()
    dispatch_label_index, dispatch_open, dispatch_close = _find_block(
        lines, dispatch_routine_label
    )
    dispatch_range = _routine_range(lines, dispatch_label_index, dispatch_routine_label)
    calls = [
        index
        for index in range(dispatch_open + 1, dispatch_close)
        if _DISPATCH_RE.fullmatch(_source_code(lines[index])) is not None
    ]
    if len(calls) != 1:
        raise ShopItemHandlersParseError(
            f"expected one implicit jump-table call in {dispatch_routine_label!r}; found {len(calls)}"
        )

    dispatch_entries: list[dict[str, Any]] = []
    for index in range(calls[0] + 1, dispatch_close):
        code = _source_code(lines[index])
        if not code:
            continue
        match = _DISPATCH_ENTRY_RE.fullmatch(code)
        if match is None:
            raise ShopItemHandlersParseError(
                f"unsupported dispatch syntax on line {index + 1}: {code!r}"
            )
        comment = lines[index].split(";", 1)[1].strip() if ";" in lines[index] else ""
        comment_match = _DISPATCH_COMMENT_RE.fullmatch(comment)
        if comment_match is None:
            raise ShopItemHandlersParseError(
                f"malformed sprite variant annotation on line {index + 1}: {comment!r}"
            )
        selector = int(comment_match.group("selector"), 16)
        if selector != len(dispatch_entries):
            raise ShopItemHandlersParseError(
                f"dispatch slot {len(dispatch_entries)} is annotated as {selector:#x}"
            )
        dispatch_entries.append({
            "selector": selector,
            "handler": match.group("handler"),
            "address": comment_match.group("address").upper(),
            "comment": comment,
            "line": index + 1,
        })

    if len(dispatch_entries) != SHOP_ITEM_HANDLERS_DISPATCH_COUNT:
        raise ShopItemHandlersParseError(
            f"dispatch table contains {len(dispatch_entries)} entries; expected "
            f"{SHOP_ITEM_HANDLERS_DISPATCH_COUNT}"
        )

    purchase_entries: list[ShopItemHandlerEntry] = []
    for dispatch_entry in dispatch_entries:
        selector = dispatch_entry["selector"]
        if selector < 7:
            continue
        label = dispatch_entry["handler"]
        label_index, open_index, close_index = _find_block(lines, label)
        handler_range = _routine_range(lines, label_index, label)

        price_sequences: list[dict[str, Any]] = []
        for index in range(open_index + 1, close_index):
            low_match = _LOW_PRICE_RE.fullmatch(_source_code(lines[index]))
            if low_match is None:
                continue
            high = _next_code(lines, index, close_index)
            payment = _next_code(lines, high[1], close_index) if high is not None else None
            if high is None or payment is None:
                continue
            high_match = _HIGH_PRICE_RE.fullmatch(high[0])
            if high_match is None or _PAYMENT_RE.fullmatch(payment[0]) is None:
                continue
            low_expression = low_match.group("literal").upper()
            high_expression = high_match.group("literal").upper()
            price_sequences.append({
                "low_expression": low_expression,
                "low_line": index + 1,
                "high_expression": high_expression,
                "high_line": high[1] + 1,
                "payment_line": payment[1] + 1,
            })
        if len(price_sequences) != 1:
            raise ShopItemHandlersParseError(
                f"{label!r} contains {len(price_sequences)} unambiguous price/payment sequences"
            )

        receipt_sequences: list[dict[str, Any]] = []
        for index in range(open_index + 1, close_index):
            if _RECEIPT_RE.fullmatch(_source_code(lines[index])) is None:
                continue
            previous = index - 1
            while previous > open_index and not _source_code(lines[previous]):
                previous -= 1
            selector_match = _RECEIPT_SELECTOR_RE.fullmatch(_source_code(lines[previous]))
            if selector_match is None:
                raise ShopItemHandlersParseError(
                    f"{label!r} receipt call on line {index + 1} has no literal Y selector"
                )
            expression = selector_match.group("literal").upper()
            receipt_sequences.append({
                "expression": expression,
                "index": int(expression[1:], 16),
                "selector_line": previous + 1,
                "call_line": index + 1,
            })
        if len(receipt_sequences) != 1:
            raise ShopItemHandlersParseError(
                f"{label!r} contains {len(receipt_sequences)} receipt calls; expected one"
            )

        price = price_sequences[0]
        receipt = receipt_sequences[0]
        price_value = (int(price["high_expression"][1:], 16) << 8) | int(
            price["low_expression"][1:], 16
        )
        purchase_entries.append(ShopItemHandlerEntry(
            table_index=len(purchase_entries),
            shopkeeper_variant_id=selector,
            handler_label=label,
            source_handler_address_annotation=dispatch_entry["address"],
            source_dispatch_comment=dispatch_entry["comment"],
            source_dispatch_line=dispatch_entry["line"],
            source_handler_range_annotation=handler_range,
            source_handler_label_line=label_index + 1,
            price_low_expression=price["low_expression"],
            price_low_source_line=price["low_line"],
            price_high_expression=price["high_expression"],
            price_high_source_line=price["high_line"],
            price_value=price_value,
            payment_call_source_line=price["payment_line"],
            receipt_item_index=receipt["index"],
            receipt_index_expression=receipt["expression"],
            receipt_selector_source_line=receipt["selector_line"],
            receipt_call_source_line=receipt["call_line"],
            source_revision=source_revision,
        ))

    if len(purchase_entries) != expected_entry_count:
        raise ShopItemHandlersParseError(
            f"found {len(purchase_entries)} purchase handlers; expected {expected_entry_count}"
        )
    return ShopItemHandlersTable(
        source_file=source_file,
        source_revision=source_revision,
        dispatch_routine_label=dispatch_routine_label,
        dispatch_routine_source_range_annotation=dispatch_range,
        entries=purchase_entries,
    )
