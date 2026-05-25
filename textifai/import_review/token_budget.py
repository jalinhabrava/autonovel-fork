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
