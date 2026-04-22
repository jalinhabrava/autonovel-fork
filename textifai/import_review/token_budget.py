from __future__ import annotations

from dataclasses import dataclass

from textifai.import_review.model_registry import ModelCapabilities


@dataclass(frozen=True)
class TokenBudget:
    context_window: int
    reserved_output_tokens: int
    safety_margin: int
    usable_input_budget: int


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
