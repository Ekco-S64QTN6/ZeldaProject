"""Source-only audit of unresolved expressions in registered data-table exports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.extract.expression_classification import (
    EXPRESSION_CLASSIFICATIONS,
    UNRESOLVED_EXPRESSION_REASON,
    classify_unresolved_expression,
    is_signed_decimal_literal,
)

SOURCE_EXPRESSION_AUDIT_FORMAT = "zelda-suite-source-expression-audit"


class SourceExpressionAuditError(ValueError):
    """Raised when the registered data-table exports cannot be audited safely."""


def audit_unresolved_table_expressions(
    registry_path: str | Path = "data/extracted/manifest.json",
) -> dict[str, Any]:
    """Inventory non-numeric data-table expressions without a ROM or assembler."""
    try:
        registered_assets = list_extracted_assets(registry_path)
    except (AssetLoadError, OSError) as exc:
        raise SourceExpressionAuditError(str(exc)) from exc

    assets = sorted(
        (asset for asset in registered_assets if asset["format"] == DATA_TABLE_FORMAT),
        key=lambda asset: asset["name"],
    )
    if not assets:
        raise SourceExpressionAuditError(
            f"registry contains no {DATA_TABLE_FORMAT!r} assets: {registry_path}"
        )

    asset_reports: list[dict[str, Any]] = []
    unresolved_expressions: list[dict[str, Any]] = []
    classification_counts = {name: 0 for name in EXPRESSION_CLASSIFICATIONS}
    total_entries = direct_numeric_entries = signed_decimal_entries = 0

    for asset in assets:
        try:
            payload = load_extracted_asset(asset["name"], registry_path)
        except (AssetLoadError, OSError) as exc:
            raise SourceExpressionAuditError(str(exc)) from exc

        asset_unresolved = asset_direct_numeric = asset_signed_decimal = 0
        for entry in payload["entries"]:
            expression = entry["expression"]
            if entry["literal_value"] is not None:
                direct_numeric_entries += 1
                asset_direct_numeric += 1
                continue
            if is_signed_decimal_literal(expression):
                signed_decimal_entries += 1
                asset_signed_decimal += 1
                continue

            classification = classify_unresolved_expression(expression)
            classification_counts[classification] += 1
            asset_unresolved += 1
            unresolved_expressions.append({
                "asset_name": asset["name"],
                "source_file": payload["source_file"],
                "source_revision": payload["source_revision"],
                "table_label": payload["table_label"],
                "directive": payload["directive"],
                "table_index": entry["table_index"],
                "entry_file_offset": entry["entry_file_offset"],
                "source_line": entry["source_line"],
                "source_label": entry["source_label"],
                "expression": expression,
                "classification": classification,
                "reason": UNRESOLVED_EXPRESSION_REASON,
            })

        asset_reports.append({
            "asset_name": asset["name"],
            "source_file": payload["source_file"],
            "source_revision": payload["source_revision"],
            "table_label": payload["table_label"],
            "directive": payload["directive"],
            "entry_count": payload["entry_count"],
            "direct_numeric_entry_count": asset_direct_numeric,
            "signed_decimal_entry_count": asset_signed_decimal,
            "unresolved_expression_count": asset_unresolved,
        })
        total_entries += payload["entry_count"]

    return {
        "format": SOURCE_EXPRESSION_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "assets": asset_reports,
        "unresolved_expressions": unresolved_expressions,
        "summary": {
            "table_asset_count": len(asset_reports),
            "entry_count": total_entries,
            "direct_numeric_entry_count": direct_numeric_entries,
            "signed_decimal_entry_count": signed_decimal_entries,
            "unresolved_expression_count": len(unresolved_expressions),
            "classification_counts": classification_counts,
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "assembler_expressions_evaluated": False,
        },
    }
