"""Validate source-labelled overworld High/Low payload pairs.

This module validates declaration metadata only. It never opens incbin payloads
or reads/writes ROM bytes.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

INCBIN_INVENTORY_FORMAT = "zelda-suite-incbin-inventory"
_SCREEN_LABEL = re.compile(r"^OverworldMap32_Screen([0-9A-Fa-f]{2})_(High|Low)$")


class OverworldPayloadPairError(ValueError):
    """Raised when overworld source inventories do not contain complete pairs."""


def validate_overworld_payload_pairs(
    inventories: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate that each source-local screen token has exactly one High and Low.

    The source filename is part of the key because physical source order and
    screen-token order are not interchangeable across disassembly banks. The
    returned report is deterministic and contains metadata only.
    """
    if isinstance(inventories, (str, bytes)) or not inventories:
        raise OverworldPayloadPairError("provide at least one overworld inventory")

    seen_sources: set[str] = set()
    revisions: set[str] = set()
    pairs: dict[tuple[str, str], dict[str, list[str]]] = {}

    for inventory_index, payload in enumerate(inventories):
        context = f"inventories[{inventory_index}]"
        if not isinstance(payload, Mapping):
            raise OverworldPayloadPairError(f"{context} must be a JSON object")
        if payload.get("format") != INCBIN_INVENTORY_FORMAT:
            raise OverworldPayloadPairError(
                f"{context}.format must be {INCBIN_INVENTORY_FORMAT!r}"
            )
        if payload.get("format_version") != 1:
            raise OverworldPayloadPairError(f"{context}.format_version must be 1")
        source_file = payload.get("source_file")
        if not isinstance(source_file, str) or not source_file.strip():
            raise OverworldPayloadPairError(
                f"{context}.source_file must be a non-empty string"
            )
        if source_file in seen_sources:
            raise OverworldPayloadPairError(
                f"duplicate source_file inventory: {source_file}"
            )
        seen_sources.add(source_file)

        revision = payload.get("source_revision")
        if not isinstance(revision, str) or not revision.strip():
            raise OverworldPayloadPairError(
                f"{context}.source_revision must be a non-empty string"
            )
        revisions.add(revision)

        declarations = payload.get("declarations")
        if not isinstance(declarations, list):
            raise OverworldPayloadPairError(
                f"{context}.declarations must be an array"
            )
        declaration_count = payload.get("declaration_count")
        if (
            isinstance(declaration_count, bool)
            or not isinstance(declaration_count, int)
            or declaration_count != len(declarations)
        ):
            raise OverworldPayloadPairError(
                f"{context}.declaration_count does not match declarations"
            )
        if not declarations:
            raise OverworldPayloadPairError(
                f"{context} contains no overworld declarations"
            )

        for declaration_index, declaration in enumerate(declarations):
            declaration_context = f"{context}.declarations[{declaration_index}]"
            if not isinstance(declaration, Mapping):
                raise OverworldPayloadPairError(
                    f"{declaration_context} must be a JSON object"
                )
            label = declaration.get("label")
            if not isinstance(label, str):
                raise OverworldPayloadPairError(
                    f"{declaration_context}.label must be a string"
                )
            match = _SCREEN_LABEL.fullmatch(label)
            if match is None:
                raise OverworldPayloadPairError(
                    f"{declaration_context} has unsupported overworld label {label!r}"
                )
            if declaration.get("source_file") != source_file:
                raise OverworldPayloadPairError(
                    f"{declaration_context}.source_file does not match {source_file!r}"
                )
            if declaration.get("source_revision") != revision:
                raise OverworldPayloadPairError(
                    f"{declaration_context}.source_revision does not match "
                    f"{revision!r}"
                )
            incbin_path = declaration.get("incbin_path")
            if not isinstance(incbin_path, str) or not incbin_path.startswith(
                "bin/ow/"
            ):
                raise OverworldPayloadPairError(
                    f"{declaration_context}.incbin_path must start with 'bin/ow/'"
                )

            screen_token = match.group(1).upper()
            layer = match.group(2)
            pair_key = (source_file, screen_token)
            members = pairs.setdefault(pair_key, {"High": [], "Low": []})
            members[layer].append(label)

    if len(revisions) != 1:
        raise OverworldPayloadPairError(
            "all overworld inventories must use the same source_revision"
        )

    problems: list[str] = []
    for (source_file, screen_token), members in sorted(pairs.items()):
        for layer in ("High", "Low"):
            count = len(members[layer])
            if count != 1:
                problems.append(
                    f"{source_file} Screen{screen_token}: expected exactly one "
                    f"{layer} declaration, found {count}"
                )
    if problems:
        raise OverworldPayloadPairError(
            "invalid overworld High/Low screen pairs:\n- "
            + "\n- ".join(problems)
        )

    sources: dict[str, list[str]] = {}
    for source_file, screen_token in pairs:
        sources.setdefault(source_file, []).append(screen_token)

    revision = next(iter(revisions))
    return {
        "valid": True,
        "source_revision": revision,
        "source_count": len(sources),
        "screen_pair_count": len(pairs),
        "sources": [
            {
                "source_file": source_file,
                "source_revision": revision,
                "screen_count": len(tokens),
                "screen_tokens": sorted(tokens),
            }
            for source_file, tokens in sorted(sources.items())
        ],
    }


OVERWORLD_PAYLOAD_LAYOUT_AUDIT_FORMAT = "zelda-suite-overworld-payload-layout-audit"


def _layout_declaration(declaration: Mapping[str, Any]) -> dict[str, Any]:
    """Expose source annotations and calculations with no ROM-offset implication."""
    return {
        "label": declaration["label"],
        "incbin_path": declaration["incbin_path"],
        "source_line": declaration["source_line"],
        "declared_size_bytes": declaration["declared_size_bytes"],
        "source_annotated_offset_start": declaration["source_file_offset_start"],
        "source_annotated_offset_end": declaration["source_file_offset_end"],
        "computed_offset_end": declaration["computed_file_offset_end"],
        "source_range_size_matches": declaration["source_range_size_matches"],
    }


def audit_overworld_payload_layout(
    inventories: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Audit paired High/Low declarations, sizes, and candidate source ranges.

    The result connects each source-local screen token to its two incbin
    declarations and reports all range/size diagnostics. Offsets are copied
    from source comments or calculated from those comments; no incbin target
    files or ROM bytes are opened.
    """
    paired_report = validate_overworld_payload_pairs(inventories)
    declaration_by_key: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = {}
    declarations: list[Mapping[str, Any]] = []

    for inventory in inventories:
        source_file = inventory["source_file"]
        for declaration in inventory["declarations"]:
            declarations.append(declaration)
            label = declaration["label"]
            match = _SCREEN_LABEL.fullmatch(label)
            if match is None:
                # validate_overworld_payload_pairs already rejects this case.
                raise OverworldPayloadPairError(
                    f"unsupported overworld label {label!r} during layout audit"
                )
            screen_token = match.group(1).upper()
            layer = match.group(2)
            declaration_by_key.setdefault((source_file, screen_token), {})[layer] = declaration

    screen_pairs: list[dict[str, Any]] = []
    for source_file, source_report in (
        (source["source_file"], source)
        for source in paired_report["sources"]
    ):
        for screen_token in source_report["screen_tokens"]:
            layers = declaration_by_key[(source_file, screen_token)]
            high_decl = layers["High"]
            low_decl = layers["Low"]
            high_end = high_decl["source_file_offset_end"]
            low_start = low_decl["source_file_offset_start"]
            candidate_adjacent = (
                high_end + 1 == low_start
                if isinstance(high_end, int) and isinstance(low_start, int)
                else None
            )
            screen_pairs.append({
                "source_file": source_file,
                "screen_token": screen_token,
                "high": _layout_declaration(high_decl),
                "low": _layout_declaration(low_decl),
                "candidate_source_ranges_adjacent": candidate_adjacent,
            })

    range_mismatches: list[dict[str, Any]] = []
    range_unknowns: list[dict[str, Any]] = []
    for declaration in declarations:
        matches = declaration["source_range_size_matches"]
        if matches is False:
            kind = "range_size_mismatch"
        elif matches is None:
            kind = "range_size_unknown"
        else:
            continue
        match = _SCREEN_LABEL.fullmatch(declaration["label"])
        if match is None:
            continue
        detail = {
            "kind": kind,
            "source_file": declaration["source_file"],
            "screen_token": match.group(1).upper(),
            "layer": match.group(2),
            **_layout_declaration(declaration),
        }
        (range_mismatches if matches is False else range_unknowns).append(detail)

    adjacency_known = [
        pair for pair in screen_pairs
        if pair["candidate_source_ranges_adjacent"] is not None
    ]
    adjacency_nonadjacent = [
        pair for pair in adjacency_known
        if pair["candidate_source_ranges_adjacent"] is False
    ]
    revision = paired_report["source_revision"]

    return {
        "format": OVERWORLD_PAYLOAD_LAYOUT_AUDIT_FORMAT,
        "format_version": 1,
        "source_revision": revision,
        "source_files": [source["source_file"] for source in paired_report["sources"]],
        "screen_pairs": screen_pairs,
        "range_size_mismatches": range_mismatches,
        "range_size_unknowns": range_unknowns,
        "summary": {
            "source_count": paired_report["source_count"],
            "declaration_count": len(declarations),
            "screen_pair_count": len(screen_pairs),
            "high_layer_count": sum(
                pair["high"]["label"].endswith("_High") for pair in screen_pairs
            ),
            "low_layer_count": sum(
                pair["low"]["label"].endswith("_Low") for pair in screen_pairs
            ),
            "range_size_match_count": sum(
                declaration["source_range_size_matches"] is True
                for declaration in declarations
            ),
            "range_size_mismatch_count": len(range_mismatches),
            "range_size_unknown_count": len(range_unknowns),
            "candidate_source_ranges_adjacent_count": sum(
                pair["candidate_source_ranges_adjacent"] is True
                for pair in screen_pairs
            ),
            "candidate_source_ranges_nonadjacent_count": len(adjacency_nonadjacent),
            "candidate_source_ranges_adjacency_unknown_count": sum(
                pair["candidate_source_ranges_adjacent"] is None
                for pair in screen_pairs
            ),
        },
        "source_semantics": {
            "description": (
                "The pinned disassembly's ROM log describes the High and Low "
                "streams as compressed high-byte and low-byte components of "
                "Map32 words. Bank0A.asm calls Overworld_LoadAndBuildScreen_long "
                "with a comment that it loads Map32 and subsequently builds Map16."
            ),
            "source_log_file": "Logs/Zelda_3_ROM.log",
            "source_log_revision": revision,
            "source_log_lines": [969, 970],
            "consumer_source_file": "Bank0A.asm",
            "consumer_source_revision": revision,
            "consumer_source_line": 673,
            "consumer_label": "Overworld_LoadAndBuildScreen_long",
            "consumer_comment": (
                "Loads overworld map32 data (and subsequently map16, etc etc)."
            ),
            "semantic_decode_completed": False,
        },
        "evidence": {
            "source_only": True,
            "incbin_target_files_opened": False,
            "rom_bytes_read": False,
            "source_range_offsets_verified": False,
            "compressed_payloads_decoded": False,
            "editable_map_layers_emitted": False,
            "runtime_map_semantics_verified": False,
        },
    }
