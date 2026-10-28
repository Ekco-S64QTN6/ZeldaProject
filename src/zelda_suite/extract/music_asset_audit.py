"""Cross-check registered music-track pointers against source payload declarations."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    INCBIN_INVENTORY_FORMAT,
    MUSIC_TRACK_INDEX_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

MUSIC_ASSET_AUDIT_FORMAT = "zelda-suite-music-asset-audit"


class MusicAssetAuditError(ValueError):
    """Raised when the registered music index or payload inventory cannot be audited."""


def audit_music_assets(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    index_asset_name: str = "music-track-index",
    payload_asset_name: str = "music-payload-inventory",
) -> dict[str, Any]:
    """Join symbolic music targets to their incbin declarations without reading bytes."""
    try:
        registered = list_extracted_assets(registry_path)
        by_name = {asset["name"]: asset for asset in registered}
        index_record = by_name.get(index_asset_name)
        payload_record = by_name.get(payload_asset_name)
        if index_record is None:
            raise MusicAssetAuditError(
                f"music index asset is not registered: {index_asset_name!r}"
            )
        if payload_record is None:
            raise MusicAssetAuditError(
                f"music payload asset is not registered: {payload_asset_name!r}"
            )
        if index_record["format"] != MUSIC_TRACK_INDEX_FORMAT:
            raise MusicAssetAuditError(
                f"asset {index_asset_name!r} must use {MUSIC_TRACK_INDEX_FORMAT!r}"
            )
        if payload_record["format"] != INCBIN_INVENTORY_FORMAT:
            raise MusicAssetAuditError(
                f"asset {payload_asset_name!r} must use {INCBIN_INVENTORY_FORMAT!r}"
            )
        index = load_extracted_asset(index_asset_name, registry_path)
        inventory = load_extracted_asset(payload_asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise MusicAssetAuditError(str(exc)) from exc

    findings: list[dict[str, Any]] = []

    def add_finding(
        code: str,
        severity: str,
        message: str,
        *,
        track_index: int | None = None,
        target_label: str | None = None,
        payload_label: str | None = None,
        incbin_path: str | None = None,
    ) -> None:
        findings.append({
            "code": code,
            "severity": severity,
            "message": message,
            "track_index": track_index,
            "target_label": target_label,
            "payload_label": payload_label,
            "incbin_path": incbin_path,
        })

    if index["source_revision"] != inventory["source_revision"]:
        add_finding(
            "source_provenance_mismatch",
            "error",
            "Music index and payload inventory record different source revisions.",
        )
    if index["source_file"] != inventory["source_file"]:
        add_finding(
            "source_provenance_mismatch",
            "error",
            "Music index and payload inventory record different source files.",
        )

    declarations = inventory["declarations"]
    declaration_counts = Counter(declaration["label"] for declaration in declarations)
    payload_by_label = {
        declaration["label"]: declaration
        for declaration in declarations
        if declaration_counts[declaration["label"]] == 1
    }
    duplicate_payload_labels = sorted(
        label for label, count in declaration_counts.items() if count > 1
    )
    for label in duplicate_payload_labels:
        add_finding(
            "duplicate_payload_label",
            "error",
            f"Payload inventory declares label {label!r} more than once.",
            payload_label=label,
        )

    pointer_entries = index["entries"]
    unique_targets = {
        entry["target_label"]
        for entry in pointer_entries
        if entry["target_label"] is not None
    }
    missing_targets = sorted(unique_targets - set(payload_by_label))
    unreferenced_payloads = sorted(set(payload_by_label) - unique_targets)

    cross_references: list[dict[str, Any]] = []
    missing_payload_reference_count = 0
    for entry in pointer_entries:
        target_label = entry["target_label"]
        declaration = payload_by_label.get(target_label) if target_label is not None else None
        payload_found = declaration is not None
        if target_label is not None and declaration is None:
            missing_payload_reference_count += 1
            add_finding(
                "missing_payload_declaration",
                "warning",
                f"Track {entry['track_index']} targets {target_label!r}, but no unique "
                "payload declaration with that label is registered.",
                track_index=entry["track_index"],
                target_label=target_label,
            )

        cross_references.append({
            "table_index": entry["table_index"],
            "track_index": entry["track_index"],
            "pointer_entry_file_offset": entry["pointer_entry_file_offset"],
            "pointer_expression": entry["pointer_expression"],
            "target_label": target_label,
            "is_empty": entry["is_empty"],
            "alias_of_track_index": entry["alias_of_track_index"],
            "payload_declaration_found": payload_found if target_label is not None else None,
            "payload_label": declaration["label"] if declaration is not None else None,
            "incbin_path": declaration["incbin_path"] if declaration is not None else None,
            "declared_size_bytes": (
                declaration["declared_size_bytes"] if declaration is not None else None
            ),
            "source_file_offset_start": (
                declaration["source_file_offset_start"] if declaration is not None else None
            ),
            "source_file_offset_end": (
                declaration["source_file_offset_end"] if declaration is not None else None
            ),
            "source_range_size_matches": (
                declaration["source_range_size_matches"] if declaration is not None else None
            ),
        })

    for label in unreferenced_payloads:
        declaration = payload_by_label[label]
        add_finding(
            "unreferenced_payload_declaration",
            "warning",
            f"Payload declaration {label!r} is not targeted by any non-empty music pointer.",
            payload_label=label,
            incbin_path=declaration["incbin_path"],
        )

    missing_size_declarations: list[dict[str, Any]] = []
    range_mismatch_count = 0
    for declaration in declarations:
        if declaration["declared_size_bytes"] is None:
            missing_size_declarations.append({
                "label": declaration["label"],
                "incbin_path": declaration["incbin_path"],
                "source_file_offset_start": declaration["source_file_offset_start"],
                "source_file_offset_end": declaration["source_file_offset_end"],
            })
            add_finding(
                "payload_size_missing",
                "warning",
                "Payload declaration has source offsets but no declared byte size.",
                payload_label=declaration["label"],
                incbin_path=declaration["incbin_path"],
            )
        if declaration["source_range_size_matches"] is False:
            range_mismatch_count += 1
            add_finding(
                "payload_source_range_mismatch",
                "warning",
                "Payload source offset range does not match its declared size.",
                payload_label=declaration["label"],
                incbin_path=declaration["incbin_path"],
            )

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    empty_entries = [entry for entry in pointer_entries if entry["is_empty"]]
    alias_entries = [
        entry for entry in pointer_entries if entry["alias_of_track_index"] is not None
    ]
    return {
        "format": MUSIC_ASSET_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "index_asset_name": index_asset_name,
        "payload_asset_name": payload_asset_name,
        "source_file": index["source_file"],
        "source_revision": index["source_revision"],
        "cross_references": cross_references,
        "missing_payload_targets": missing_targets,
        "unreferenced_payload_labels": unreferenced_payloads,
        "payloads_missing_size": missing_size_declarations,
        "findings": findings,
        "summary": {
            "track_entry_count": len(pointer_entries),
            "empty_pointer_count": len(empty_entries),
            "nonempty_pointer_count": len(pointer_entries) - len(empty_entries),
            "alias_entry_count": len(alias_entries),
            "unique_target_label_count": len(unique_targets),
            "payload_declaration_count": len(declarations),
            "matched_payload_label_count": len(set(payload_by_label) & unique_targets),
            "missing_payload_target_count": len(missing_targets),
            "missing_payload_reference_count": missing_payload_reference_count,
            "unreferenced_payload_count": len(unreferenced_payloads),
            "payload_without_size_count": len(missing_size_declarations),
            "payload_source_range_mismatch_count": range_mismatch_count,
            "duplicate_payload_label_count": len(duplicate_payload_labels),
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "audio_payload_bytes_read": False,
            "pointer_values_resolved": False,
            "offsets_verified": False,
        },
    }
