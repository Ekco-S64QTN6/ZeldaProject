"""Summarize known inconsistencies in registered source text-message indexes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    TEXT_MESSAGE_INDEX_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

TEXT_MESSAGE_INDEX_AUDIT_FORMAT = "zelda-suite-text-message-index-audit"


class TextMessageIndexAuditError(ValueError):
    """Raised when a registered text-message index cannot be audited."""


def audit_text_message_index(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = "text-message-index",
) -> dict[str, Any]:
    """Report source annotation and block-size discrepancies without reading a ROM."""
    try:
        records = list_extracted_assets(registry_path)
        asset = next((record for record in records if record["name"] == asset_name), None)
        if asset is None:
            raise TextMessageIndexAuditError(
                f"text-message index asset is not registered: {asset_name!r}"
            )
        if asset["format"] != TEXT_MESSAGE_INDEX_FORMAT:
            raise TextMessageIndexAuditError(
                f"asset {asset_name!r} must use {TEXT_MESSAGE_INDEX_FORMAT!r}"
            )
        payload = load_extracted_asset(asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise TextMessageIndexAuditError(str(exc)) from exc

    findings: list[dict[str, Any]] = []

    def add_finding(
        *,
        code: str,
        message: str,
        source_file: str,
        block_label: str,
        message_id: int | None = None,
        message_label: str | None = None,
        source_line: int | None = None,
        source_offset_annotation: str | None = None,
        annotated_file_offset: int | None = None,
        sequential_file_offset: int | None = None,
        declared_byte_count: int | None = None,
        block_start_offset: int | None = None,
        block_end_offset: int | None = None,
        block_size_bytes: int | None = None,
        declared_byte_count_total: int | None = None,
        difference_bytes: int | None = None,
    ) -> None:
        findings.append({
            "code": code,
            "severity": "warning",
            "message": message,
            "source_file": source_file,
            "block_label": block_label,
            "message_id": message_id,
            "message_label": message_label,
            "source_line": source_line,
            "source_offset_annotation": source_offset_annotation,
            "annotated_file_offset": annotated_file_offset,
            "sequential_file_offset": sequential_file_offset,
            "declared_byte_count": declared_byte_count,
            "block_start_offset": block_start_offset,
            "block_end_offset": block_end_offset,
            "block_size_bytes": block_size_bytes,
            "declared_byte_count_total": declared_byte_count_total,
            "difference_bytes": difference_bytes,
        })

    offset_annotation_count = 0
    missing_offset_annotation_count = 0
    offset_mismatch_count = 0
    invalid_offset_annotation_count = 0
    block_size_mismatch_count = 0

    for message in payload["messages"]:
        annotation = message["source_offset_annotation"]
        if annotation is None:
            missing_offset_annotation_count += 1
            continue

        offset_annotation_count += 1
        if message["source_offset_matches_sequential"] is False:
            offset_mismatch_count += 1
            common = {
                "source_file": message["source_file"],
                "block_label": message["data_block_label"],
                "message_id": message["message_id"],
                "message_label": message["message_label"],
                "source_line": message["source_line"],
                "source_offset_annotation": annotation,
                "annotated_file_offset": message["annotated_file_offset"],
                "sequential_file_offset": message["sequential_file_offset"],
                "declared_byte_count": message["declared_byte_count"],
            }
            if message["source_offset_annotation_valid"] is False:
                invalid_offset_annotation_count += 1
                add_finding(
                    code="invalid_offset_annotation",
                    message=(
                        "Source offset annotation is malformed or outside the declared "
                        "block range; raw annotation and sequential offset are preserved."
                    ),
                    **common,
                )
            else:
                add_finding(
                    code="offset_annotation_mismatch",
                    message=(
                        "Valid source offset annotation differs from the sequential offset "
                        "computed from declared message lengths."
                    ),
                    **common,
                )
        elif message["source_offset_annotation_valid"] is False:
            # A malformed annotation normally also fails the sequential comparison;
            # keep this branch defensive if the export's contract changes in future.
            invalid_offset_annotation_count += 1
            add_finding(
                code="invalid_offset_annotation",
                message=(
                    "Source offset annotation is malformed or outside the declared "
                    "block range; raw annotation and sequential offset are preserved."
                ),
                source_file=message["source_file"],
                block_label=message["data_block_label"],
                message_id=message["message_id"],
                message_label=message["message_label"],
                source_line=message["source_line"],
                source_offset_annotation=annotation,
                annotated_file_offset=message["annotated_file_offset"],
                sequential_file_offset=message["sequential_file_offset"],
                declared_byte_count=message["declared_byte_count"],
            )

    for block in payload["source_blocks"]:
        if block["declared_bytes_match_block_size"]:
            continue
        block_size_mismatch_count += 1
        difference = block["declared_byte_count_total"] - block["block_size_bytes"]
        add_finding(
            code="block_size_mismatch",
            message=(
                f"Declared message bytes total {block['declared_byte_count_total']} byte(s), "
                f"but the source block range spans {block['block_size_bytes']} byte(s); "
                "neither value was changed by this audit."
            ),
            source_file=block["source_file"],
            block_label=block["data_block_label"],
            block_start_offset=block["block_start_offset"],
            block_end_offset=block["block_end_offset"],
            block_size_bytes=block["block_size_bytes"],
            declared_byte_count_total=block["declared_byte_count_total"],
            difference_bytes=difference,
        )

    return {
        "format": TEXT_MESSAGE_INDEX_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "source_files": list(dict.fromkeys(
            block["source_file"] for block in payload["source_blocks"]
        )),
        "source_revision": payload["source_revision"],
        "source_blocks": [
            {
                "source_file": block["source_file"],
                "block_label": block["data_block_label"],
                "block_start_offset": block["block_start_offset"],
                "block_end_offset": block["block_end_offset"],
                "block_size_bytes": block["block_size_bytes"],
                "message_count": block["message_count"],
                "declared_byte_count_total": block["declared_byte_count_total"],
                "declared_bytes_match_block_size": block["declared_bytes_match_block_size"],
                "difference_bytes": (
                    block["declared_byte_count_total"] - block["block_size_bytes"]
                ),
            }
            for block in payload["source_blocks"]
        ],
        "findings": findings,
        "summary": {
            "source_block_count": payload["source_block_count"],
            "message_count": payload["message_count"],
            "offset_annotation_count": offset_annotation_count,
            "missing_offset_annotation_count": missing_offset_annotation_count,
            "offset_mismatch_count": offset_mismatch_count,
            "invalid_offset_annotation_count": invalid_offset_annotation_count,
            "block_size_mismatch_count": block_size_mismatch_count,
            "warning_count": len(findings),
            "finding_count": len(findings),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "encoded_message_bytes_read": False,
            "decoded_text_produced": False,
            "offsets_verified": False,
        },
    }
