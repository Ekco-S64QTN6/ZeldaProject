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
