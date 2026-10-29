"""Audit the committed catalog of fee-bearing overworld interactions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zelda_suite.extract.asset_loader import (
    PAID_OVERWORLD_INTERACTIONS_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
)

PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT = "zelda-suite-paid-overworld-interactions-audit"
PAID_OVERWORLD_INTERACTIONS_ASSET_NAME = "paid-overworld-interactions"


class PaidOverworldInteractionsAuditError(ValueError):
    """Raised when the registered paid-overworld inventory cannot be audited."""


def audit_paid_overworld_interactions(
    registry_path: str | Path = "data/extracted/manifest.json",
    *,
    asset_name: str = PAID_OVERWORLD_INTERACTIONS_ASSET_NAME,
) -> dict[str, Any]:
    """Summarize source-coded fees and the Digging Game's raw reward dispatch."""
    try:
        records = list_extracted_assets(registry_path)
        by_name = {record["name"]: record for record in records}
        record = by_name.get(asset_name)
        if record is None:
            raise PaidOverworldInteractionsAuditError(
                f"paid-overworld interaction asset is not registered: {asset_name!r}"
            )
        if record["format"] != PAID_OVERWORLD_INTERACTIONS_FORMAT:
            raise PaidOverworldInteractionsAuditError(
                f"asset {asset_name!r} must use {PAID_OVERWORLD_INTERACTIONS_FORMAT!r}"
            )
        payload = load_extracted_asset(asset_name, registry_path)
    except (AssetLoadError, OSError) as exc:
        raise PaidOverworldInteractionsAuditError(str(exc)) from exc

    interactions = payload["interactions"]
    values = sorted({
        value for interaction in interactions for value in interaction["fee_values"]
    })
    fixed_count = sum(interaction["fee_model"] == "fixed" for interaction in interactions)
    table_count = len(interactions) - fixed_count
    digging_dispatch = next(
        table for table in payload["reward_tables"]
        if table["table_id"] == "digging-game-random-reward-dispatch"
    )
    digging_pool = next(
        table for table in payload["reward_tables"]
        if table["table_id"] == "digging-game-basic-reward-pool"
    )
    heart_gate = payload["reward_gates"][0]

    return {
        "format": PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT,
        "format_version": 1,
        "registry": str(registry_path),
        "asset_name": asset_name,
        "source_revision": payload["source_revision"],
        "source_files": payload["source_files"],
        "transactions": [
            {
                "interaction_id": interaction["interaction_id"],
                "actor_label": interaction["actor_label"],
                "interaction_kind": interaction["interaction_kind"],
                "fee_model": interaction["fee_model"],
                "fee_values": interaction["fee_values"],
                "fee_expressions": interaction["fee_expressions"],
                "source_file": interaction["source_file"],
                "source_label": interaction["source_label"],
                "source_range_annotation": interaction["source_range_annotation"],
                "outcome_label": interaction["outcome_label"],
            }
            for interaction in interactions
        ],
        "digging_game_rewards": {
            "dispatch_table_id": digging_dispatch["table_id"],
            "dispatch_entries": digging_dispatch["entries"],
            "basic_reward_pool_id": digging_pool["table_id"],
            "basic_reward_pool": digging_pool["entries"],
            "heart_piece_gate": heart_gate,
        },
        "summary": {
            "interaction_count": len(interactions),
            "fixed_fee_interaction_count": fixed_count,
            "selected_price_table_interaction_count": table_count,
            "unique_fee_value_count": len(values),
            "minimum_fee_value": min(values),
            "maximum_fee_value": max(values),
            "digging_game_dispatch_entry_count": len(digging_dispatch["entries"]),
            "digging_game_basic_reward_count": len(digging_pool["entries"]),
            "digging_game_minimum_hole_count_for_heart_piece_gate": heart_gate[
                "minimum_hole_count"
            ],
        },
        "evidence": {
            "source_only": True,
            "rom_bytes_read": False,
            "source_range_annotations_verified": False,
            "fee_behavior_runtime_verified": False,
            "reward_probability_runtime_verified": False,
            "item_value_names_resolved": False,
            "payment_semantics_runtime_verified": False,
        },
    }
