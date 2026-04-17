from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from context_engine.contracts import ContextPolicy, ScopeRadiusConfig, SectionBudgets


POLICY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "context_policies.json"


@lru_cache(maxsize=1)
def load_policy_config() -> dict:
    return json.loads(POLICY_CONFIG_PATH.read_text())


def get_policy(policy_name: str = "default") -> ContextPolicy:
    config = load_policy_config()
    try:
        raw = config["policies"][policy_name]
    except KeyError as exc:
        raise KeyError(f"Unknown context policy: {policy_name}") from exc

    section_budgets = SectionBudgets(**raw["section_budgets"])
    scope_radius = {
        scope_name: ScopeRadiusConfig(**radius_config)
        for scope_name, radius_config in raw["scope_radius"].items()
    }
    literality_by_artifact_type = {
        key: _validate_literality(value, artifact_type=key)
        for key, value in raw["literality_by_artifact_type"].items()
    }
    return ContextPolicy(
        name=policy_name,
        selection_weights=dict(raw["selection_weights"]),
        status_priority=dict(raw["status_priority"]),
        section_budgets=section_budgets,
        literality_by_artifact_type=literality_by_artifact_type,
        scope_radius=scope_radius,
    )


def available_policies() -> tuple[str, ...]:
    config = load_policy_config()
    return tuple(sorted(config["policies"].keys()))


def _validate_literality(value: float, *, artifact_type: str) -> float:
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(
            f"Invalid literality for {artifact_type!r}: {numeric}. Expected a value between 0.0 and 1.0."
        )
    return numeric
