from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textifai.import_review.model_registry import ModelCapabilities


@dataclass(frozen=True)
class TokenBudget:
    context_window: int
    reserved_output_tokens: int
    safety_margin: int
    usable_input_budget: int

@dataclass(frozen=True)
class TokenPlanningRequest:
    provider: str
    model: str
    task: str
    provider_profile_id: str | None
    max_output_tokens: int
    prompt_overhead_tokens: int
    source_text_budget_tokens: int
    safety_margin: int

@dataclass(frozen=True)
class EffectiveOutputBudget:
    provider: str
    model: str
    task: str
    provider_profile_id: str | None
    effective_max_output_tokens: int
    decision_source: str
    model_registry_max_output_tokens: int | None
    profile_default_max_output_tokens: int | None
    override_max_output_tokens: int | None


def build_token_budget(
    *,
    capabilities: ModelCapabilities,
    requested_output_tokens: int | None = None,
    safety_margin: int | None = None,
) -> TokenBudget:
    reserved_output_tokens = min(
        requested_output_tokens or capabilities.recommended_output_reserve,
        capabilities.max_output_tokens,
    )
    margin = safety_margin if safety_margin is not None else capabilities.recommended_safety_margin
    usable_input_budget = max(1000, capabilities.context_window - reserved_output_tokens - margin)
    return TokenBudget(
        context_window=capabilities.context_window,
        reserved_output_tokens=reserved_output_tokens,
        safety_margin=margin,
        usable_input_budget=usable_input_budget,
    )


def fits_within_budget(*, input_tokens: int, budget: TokenBudget) -> bool:
    return input_tokens <= budget.usable_input_budget

def build_token_budget_from_planning_request(
    *,
    capabilities: ModelCapabilities,
    planning: TokenPlanningRequest,
) -> dict[str, Any]:
    budget = build_token_budget(
        capabilities=capabilities,
        requested_output_tokens=planning.max_output_tokens,
        safety_margin=planning.safety_margin,
    )
    return {
        "provider": planning.provider,
        "model": planning.model,
        "task": planning.task,
        "provider_profile_id": planning.provider_profile_id,
        "context_window": budget.context_window,
        "max_output_tokens": planning.max_output_tokens,
        "reserved_output_tokens": budget.reserved_output_tokens,
        "prompt_overhead_tokens": planning.prompt_overhead_tokens,
        "source_text_budget_tokens": planning.source_text_budget_tokens,
        "safety_margin": budget.safety_margin,
        "usable_input_budget": budget.usable_input_budget,
    }

def resolve_effective_output_budget(
    *,
    provider: str,
    model: str,
    task: str,
    capabilities: ModelCapabilities | None = None,
    provider_profile_id: str | None = None,
    profile_default_max_output_tokens: int | None = None,
    user_override_max_output_tokens: int | None = None,
    cli_override_max_output_tokens: int | None = None,
    provider_default_max_output_tokens: int | None = None,
) -> EffectiveOutputBudget:
    registry_max = capabilities.max_output_tokens if capabilities is not None else None
    candidates = [
        ("cli_override", cli_override_max_output_tokens),
        ("user_override", user_override_max_output_tokens),
        ("profile_default", profile_default_max_output_tokens),
        ("model_registry", registry_max),
        ("provider_default", provider_default_max_output_tokens),
    ]
    selected_source = "provider_default"
    selected_value = provider_default_max_output_tokens or 4096
    for source, value in candidates:
        if value is None:
            continue
        selected_source = source
        selected_value = int(value)
        break
    if registry_max is not None:
        selected_value = min(selected_value, int(registry_max))
    return EffectiveOutputBudget(
        provider=provider,
        model=model,
        task=task,
        provider_profile_id=provider_profile_id,
        effective_max_output_tokens=max(1, selected_value),
        decision_source=selected_source,
        model_registry_max_output_tokens=registry_max,
        profile_default_max_output_tokens=profile_default_max_output_tokens,
        override_max_output_tokens=cli_override_max_output_tokens or user_override_max_output_tokens,
    )
