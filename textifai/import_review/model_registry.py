from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCapabilities:
    model: str
    context_window: int
    max_output_tokens: int
    recommended_output_reserve: int
    recommended_safety_margin: int
    supports_structured_outputs: bool = True
    family: str = "generic"
    relative_cost: float = 1.0
    quality_score: float = 0.5
    speed_score: float = 0.5
    safe_default_for: tuple[str, ...] = ()


_MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    "gpt-4o-mini": ModelCapabilities(
        model="gpt-4o-mini",
        context_window=128000,
        max_output_tokens=16384,
        recommended_output_reserve=12000,
        recommended_safety_margin=8000,
        family="gpt-4o",
        relative_cost=0.4,
        quality_score=0.66,
        speed_score=0.9,
        safe_default_for=("chapter_extraction", "chapter_partial_extraction", "chapter_reduction", "model_advisor"),
    ),
    "gpt-4o": ModelCapabilities(
        model="gpt-4o",
        context_window=128000,
        max_output_tokens=16384,
        recommended_output_reserve=12000,
        recommended_safety_margin=8000,
        family="gpt-4o",
        relative_cost=0.75,
        quality_score=0.78,
        speed_score=0.82,
    ),
    "gpt-4.1-mini": ModelCapabilities(
        model="gpt-4.1-mini",
        context_window=1047576,
        max_output_tokens=32768,
        recommended_output_reserve=24000,
        recommended_safety_margin=20000,
        family="gpt-4.1",
        relative_cost=0.55,
        quality_score=0.8,
        speed_score=0.72,
        safe_default_for=("global_normalization", "safe_long_context_model", "entity_cleanup"),
    ),
    "gpt-4.1-nano": ModelCapabilities(
        model="gpt-4.1-nano",
        context_window=1047576,
        max_output_tokens=32768,
        recommended_output_reserve=20000,
        recommended_safety_margin=18000,
        family="gpt-4.1",
        relative_cost=0.25,
        quality_score=0.56,
        speed_score=0.88,
    ),
    "gpt-4.1": ModelCapabilities(
        model="gpt-4.1",
        context_window=1047576,
        max_output_tokens=32768,
        recommended_output_reserve=24000,
        recommended_safety_margin=24000,
        family="gpt-4.1",
        relative_cost=0.9,
        quality_score=0.86,
        speed_score=0.64,
    ),
    "gpt-5.2": ModelCapabilities(
        model="gpt-5.2",
        context_window=1050000,
        max_output_tokens=128000,
        recommended_output_reserve=48000,
        recommended_safety_margin=32000,
        family="gpt-5",
        relative_cost=1.0,
        quality_score=0.94,
        speed_score=0.62,
    ),
    "gpt-5-mini": ModelCapabilities(
        model="gpt-5-mini",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
        family="gpt-5",
        relative_cost=0.65,
        quality_score=0.84,
        speed_score=0.78,
        safe_default_for=("safe_structured_model",),
    ),
    "gpt-5-nano": ModelCapabilities(
        model="gpt-5-nano",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
        family="gpt-5",
        relative_cost=0.3,
        quality_score=0.68,
        speed_score=0.92,
        safe_default_for=("model_advisor",),
    ),
    # Legacy aliases kept because this repo previously used 5.4-specific names.
    "gpt-5.4": ModelCapabilities(
        model="gpt-5.4",
        context_window=1050000,
        max_output_tokens=128000,
        recommended_output_reserve=48000,
        recommended_safety_margin=32000,
        family="gpt-5",
        relative_cost=1.0,
        quality_score=0.94,
        speed_score=0.62,
    ),
    "gpt-5.4-mini": ModelCapabilities(
        model="gpt-5.4-mini",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
        family="gpt-5",
        relative_cost=0.65,
        quality_score=0.84,
        speed_score=0.78,
        safe_default_for=("safe_structured_model",),
    ),
    "gpt-5.4-nano": ModelCapabilities(
        model="gpt-5.4-nano",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
        family="gpt-5",
        relative_cost=0.3,
        quality_score=0.68,
        speed_score=0.92,
        safe_default_for=("model_advisor",),
    ),
    "deepseek-v4-flash": ModelCapabilities(
        model="deepseek-v4-flash",
        context_window=128000,
        max_output_tokens=8192,
        recommended_output_reserve=8192,
        recommended_safety_margin=8000,
        family="deepseek",
        relative_cost=0.35,
        quality_score=0.68,
        speed_score=0.84,
        safe_default_for=("chapter_partial_extraction",),
    ),
    "deepseek-v4-pro": ModelCapabilities(
        model="deepseek-v4-pro",
        context_window=128000,
        max_output_tokens=8192,
        recommended_output_reserve=8192,
        recommended_safety_margin=8000,
        family="deepseek",
        relative_cost=0.7,
        quality_score=0.78,
        speed_score=0.7,
        safe_default_for=("chapter_extraction", "chapter_reduction"),
    ),
}

_DEFAULT_CAPABILITIES = ModelCapabilities(
    model="default",
    context_window=128000,
    max_output_tokens=16384,
    recommended_output_reserve=12000,
    recommended_safety_margin=8000,
    family="generic",
    relative_cost=1.0,
    quality_score=0.5,
    speed_score=0.5,
)


def get_model_capabilities(model_name: str | None) -> ModelCapabilities:
    normalized = str(model_name or "").strip().casefold()
    for key, capabilities in _MODEL_CAPABILITIES.items():
        if normalized == key.casefold():
            return capabilities
    inferred = infer_model_capabilities(model_name)
    if inferred is not None:
        return inferred
    return _DEFAULT_CAPABILITIES


def infer_model_capabilities(model_name: str | None) -> ModelCapabilities | None:
    normalized = str(model_name or "").strip().casefold()
    if not normalized:
        return None
    if normalized.startswith("gpt-4o-mini"):
        return _MODEL_CAPABILITIES["gpt-4o-mini"]
    if normalized.startswith("gpt-4o"):
        return _MODEL_CAPABILITIES["gpt-4o"]
    if normalized.startswith("gpt-4.1-mini"):
        return _MODEL_CAPABILITIES["gpt-4.1-mini"]
    if normalized.startswith("gpt-4.1-nano"):
        return _MODEL_CAPABILITIES["gpt-4.1-nano"]
    if normalized.startswith("gpt-4.1"):
        return _MODEL_CAPABILITIES["gpt-4.1"]
    if normalized.startswith(("gpt-5.4-mini", "gpt-5-mini")):
        return _MODEL_CAPABILITIES["gpt-5-mini"]
    if normalized.startswith(("gpt-5.4-nano", "gpt-5-nano")):
        return _MODEL_CAPABILITIES["gpt-5-nano"]
    if normalized.startswith(("gpt-5.4", "gpt-5.2", "gpt-5")):
        return _MODEL_CAPABILITIES["gpt-5.2"]
    if normalized.startswith("deepseek-v4-flash"):
        return _MODEL_CAPABILITIES["deepseek-v4-flash"]
    if normalized.startswith("deepseek-v4-pro"):
        return _MODEL_CAPABILITIES["deepseek-v4-pro"]
    return None


def list_known_models() -> list[str]:
    return sorted(_MODEL_CAPABILITIES)
