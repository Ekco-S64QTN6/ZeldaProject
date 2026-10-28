"""Read-only verification of registered scalar data-table literals against a ROM."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    DATA_TABLE_FORMAT,
    list_extracted_assets,
    load_extracted_asset,
)
from zelda_suite.extract.expression_classification import (
    UNRESOLVED_EXPRESSION_REASON,
    classify_unresolved_expression,
    is_signed_decimal_literal,
)
from zelda_suite.extract.rom_image import (
    EXPECTED_US_ROM_SIZE,
    ROMImageInspectionError,
    read_rom_bytes,
    sha256_rom_bytes,
)

ROM_TABLE_VERIFICATION_FORMAT = "zelda-suite-rom-table-verification"
DIRECTIVE_WIDTHS = {"db": 1, "dw": 2, "dl": 3}
remove classifierclass ROMTableVerificationError(ValueError):
    """Raised when a ROM or registry cannot be used for scalar-table verification."""


def verify_registered_scalar_tables(
    rom_path: str | Path,
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    include_skipped_expressions: bool = False,
) -> dict[str, Any]:
    """Compare registered numeric data-table literals to a local headerless US ROM.

    This performs read-only byte comparisons. Direct numeric expressions are
    checked; unresolved expressions are skipped, never evaluated or guessed.
    Data-table entry offsets already account for the export's configured stride,
    while literal bytes use the width of the declared db/dw/dl directive.
    """
    image_path = Path(rom_path)
    if not image_path.is_file():
        raise ROMTableVerificationError(f"ROM path is not a file: {image_path}")

    try:
        rom = read_rom_bytes(image_path)
    except ROMImageInspectionError as exc:
        raise ROMTableVerificationError(str(exc)) from exc

    if len(rom) != EXPECTED_US_ROM_SIZE:
        raise ROMTableVerificationError(
            "ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(rom):,}. "
            "Use inspect-rom to diagnose the file; do not adjust it automatically."
        )

    registered_assets = list_extracted_assets(registry_path)

    table_assets = [
        record for record in registered_assets if record["format"] == DATA_TABLE_FORMAT
    ]
    if not table_assets:
        raise ROMTableVerificationError(
            f"registry contains no {DATA_TABLE_FORMAT!r} assets: {registry_path}"
        )

    asset_reports: list[dict[str, Any]] = []
    checked_total = 0
    skipped_total = 0
    mismatch_total = 0
    resolved_signed_decimal_total = 0
    unresolved_expression_total = 0

    for asset in table_assets:
        payload = load_extracted_asset(asset["name"], registry_path)
        directive = payload["directive"]
        literal_width = DIRECTIVE_WIDTHS[directive]
        entry_stride = payload["entry_width"]
        checked = 0
        skipped = 0
        resolved_signed_decimal = 0
        unresolved_expressions: list[dict[str, Any]] = []
        mismatches: list[dict[str, Any]] = []

        for entry in payload["entries"]:
            value = entry["literal_value"]
            if value is None:
                expression = entry["expression"]
                if not is_signed_decimal_literal(expression):
                    skipped += 1
                    if include_skipped_expressions:
                        unresolved_expressions.append({
                            "table_index": entry["table_index"],
                            "offset": entry["entry_file_offset"],
                            "source_line": entry["source_line"],
                            "expression": expression,
                            "classification": classify_unresolved_expression(expression),
                            "reason": UNRESOLVED_EXPRESSION_REASON,
                        })
                    continue

                signed_value = int(expression, 10)
                signed_minimum = -(1 << (8 * literal_width - 1))
                if signed_value < signed_minimum:
                    mismatches.append({
                        "table_index": entry["table_index"],
                        "offset": entry["entry_file_offset"],
                        "expression": expression,
                        "reason": (
                            "negative decimal literal is outside the signed range "
                            "for the declared directive width"
                        ),
                        "expected_hex": None,
                        "actual_hex": None,
                    })
                    continue
                value = signed_value & ((1 << (8 * literal_width)) - 1)
                resolved_signed_decimal += 1

            offset = entry["entry_file_offset"]
            context = {
                "table_index": entry["table_index"],
                "offset": offset,
                "expression": entry["expression"],
            }
            if value >= 1 << (8 * literal_width):
                mismatches.append({
                    **context,
                    "reason": "literal does not fit the declared directive width",
                    "expected_hex": None,
                    "actual_hex": None,
                })
                continue

            expected = value.to_bytes(literal_width, "little")
            end_offset = offset + literal_width
            if end_offset > len(rom):
                mismatches.append({
                    **context,
                    "reason": "entry extends beyond the ROM image",
                    "expected_hex": expected.hex().upper(),
                    "actual_hex": None,
                })
                continue

            actual = rom[offset:end_offset]
            checked += 1
            if actual != expected:
                mismatches.append({
                    **context,
                    "reason": "ROM bytes do not match the source literal",
                    "expected_hex": expected.hex().upper(),
                    "actual_hex": actual.hex().upper(),
                })

        status = (
            "fail" if mismatches
            else "skip" if checked == 0
            else "partial" if skipped
            else "pass"
        )
        asset_report = {
            "name": asset["name"],
            "source_file": payload["source_file"],
            "source_revision": payload["source_revision"],
            "table_label": payload["table_label"],
            "directive": directive,
            "literal_width_bytes": literal_width,
            "entry_stride_bytes": entry_stride,
            "entry_count": payload["entry_count"],
            "checked_entries": checked,
            "skipped_entries": skipped,
            "resolved_signed_decimal_entries": resolved_signed_decimal,
            "mismatch_count": len(mismatches),
            "status": status,
            "mismatches": mismatches,
        }
        if include_skipped_expressions:
            asset_report["unresolved_expressions"] = unresolved_expressions
            unresolved_expression_total += len(unresolved_expressions)
        asset_reports.append(asset_report)
        checked_total += checked
        skipped_total += skipped
        mismatch_total += len(mismatches)
        resolved_signed_decimal_total += resolved_signed_decimal

    status_counts = {
        status: sum(report["status"] == status for report in asset_reports)
        for status in ("pass", "partial", "skip", "fail")
    }
    summary = {
        "table_asset_count": len(asset_reports),
        "pass_asset_count": status_counts["pass"],
        "partial_asset_count": status_counts["partial"],
        "skipped_asset_count": status_counts["skip"],
        "failed_asset_count": status_counts["fail"],
        "checked_entries": checked_total,
        "skipped_entries": skipped_total,
        "resolved_signed_decimal_entries": resolved_signed_decimal_total,
        "mismatches": mismatch_total,
    }
    if include_skipped_expressions:
        summary["unresolved_expression_count"] = unresolved_expression_total

    return {
        "format": ROM_TABLE_VERIFICATION_FORMAT,
        "format_version": 2 if include_skipped_expressions else 1,
        "rom": {
            "filename": image_path.name,
            "size_bytes": len(rom),
            "sha256": sha256_rom_bytes(rom),
            "header_assessment": "headerless-by-expected-size",
            "provenance_verified": False,
        },
        "registry": str(registry_path),
        "assets": asset_reports,
        "summary": summary,
    }
