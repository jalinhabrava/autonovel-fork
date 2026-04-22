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


_MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    "gpt-4o-mini": ModelCapabilities(
        model="gpt-4o-mini",
        context_window=128000,
        max_output_tokens=16384,
        recommended_output_reserve=12000,
        recommended_safety_margin=8000,
    ),
    "gpt-4.1-mini": ModelCapabilities(
        model="gpt-4.1-mini",
        context_window=1047576,
        max_output_tokens=32768,
        recommended_output_reserve=24000,
        recommended_safety_margin=20000,
    ),
    "gpt-4.1": ModelCapabilities(
        model="gpt-4.1",
        context_window=1047576,
        max_output_tokens=32768,
        recommended_output_reserve=24000,
        recommended_safety_margin=24000,
    ),
    "gpt-5.4": ModelCapabilities(
        model="gpt-5.4",
        context_window=1050000,
        max_output_tokens=128000,
        recommended_output_reserve=48000,
        recommended_safety_margin=32000,
    ),
    "gpt-5.4-mini": ModelCapabilities(
        model="gpt-5.4-mini",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
    ),
    "gpt-5.4-nano": ModelCapabilities(
        model="gpt-5.4-nano",
        context_window=400000,
        max_output_tokens=128000,
        recommended_output_reserve=32000,
        recommended_safety_margin=24000,
    ),
}

_DEFAULT_CAPABILITIES = ModelCapabilities(
    model="default",
    context_window=128000,
    max_output_tokens=16384,
    recommended_output_reserve=12000,
    recommended_safety_margin=8000,
)


def get_model_capabilities(model_name: str | None) -> ModelCapabilities:
    normalized = str(model_name or "").strip().casefold()
    for key, capabilities in _MODEL_CAPABILITIES.items():
        if normalized == key.casefold():
            return capabilities
    return _DEFAULT_CAPABILITIES
