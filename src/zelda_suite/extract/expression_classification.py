"""Conservative classification of raw Asar expressions without evaluation."""
from __future__ import annotations

import re

SIGNED_DECIMAL_LITERAL_RE = re.compile(r"-[0-9]+\Z")
_SYMBOL_RE = re.compile(r"\.?[A-Za-z_][A-Za-z0-9_]*\Z")
_SYMBOL_WITH_NUMERIC_ADDEND_RE = re.compile(
    r"\.?[A-Za-z_][A-Za-z0-9_]*[+-](?:\$[0-9A-Fa-f]+|0[xX][0-9A-Fa-f]+|[0-9]+)\Z"
)
UNRESOLVED_EXPRESSION_REASON = (
    "Expression is not a supported numeric literal; it was not evaluated."
)
EXPRESSION_CLASSIFICATIONS = (
    "symbol",
    "symbol_with_numeric_addend",
    "compound_or_assembler_specific",
    "other",
)


def is_signed_decimal_literal(expression: str) -> bool:
    """Return whether an expression is a bare negative decimal integer."""
    return SIGNED_DECIMAL_LITERAL_RE.fullmatch(expression) is not None


def classify_unresolved_expression(expression: str) -> str:
    """Classify simple expression shapes without resolving or evaluating them."""
    if _SYMBOL_RE.fullmatch(expression) is not None:
        return "symbol"
    if _SYMBOL_WITH_NUMERIC_ADDEND_RE.fullmatch(expression) is not None:
        return "symbol_with_numeric_addend"
    if any(character in expression for character in "()+-*/%&|^~<>"):
        return "compound_or_assembler_specific"
    return "other"
