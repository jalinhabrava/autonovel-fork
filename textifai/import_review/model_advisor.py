from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider
from textifai.author_understanding.normalization import extract_json_payload
from textifai.import_review.bootstrap_profile import BootstrapProfile
from textifai.import_review.provider_snapshot import ProviderSnapshot


MODEL_ADVISOR_PROMPT = """You are a bootstrap model planner.

Choose the best model for each bootstrap phase using only the provided AVAILABLE_MODELS.
Balance cost, latency, and structured JSON reliability.

Return ONLY valid JSON.
Do not include markdown fences.
Do not include commentary.

Schema:
{
  "global_normalization": {"default_model": "...", "reason": "..."},
  "chapter_extraction": {
    "default_model": "...",
    "large_chapter_model": "...",
    "high_complexity_model": "...",
    "reason": "..."
  },
  "chapter_partial_extraction": {"default_model": "...", "reason": "..."},
  "chapter_reduction": {"default_model": "...", "reason": "..."},
  "entity_cleanup": {"default_model": "...", "reason": "..."}
}
"""


@dataclass(frozen=True)
class AdvisorRecommendation:
    plan: dict[str, Any]
    model_used: str
    raw: dict[str, Any]


def maybe_advise_model_plan(
    *,
    provider_name: str | None,
    advisor_task_name: str,
    requested_model: str | None,
    snapshot: ProviderSnapshot,
    profile: BootstrapProfile,
    timeout_seconds: int,
    retries: int,
) -> AdvisorRecommendation | None:
    provider = str(provider_name or "").strip().casefold()
    if provider != "openai":
        return None
    if str(requested_model or "").strip() and str(requested_model or "").strip().casefold() != "auto":
        return None
    advisor_model = _pick_advisor_model(snapshot)
    if not advisor_model:
        return None
    provider_client = get_text_provider(advisor_task_name, provider_name)
    prompt = (
        f"{MODEL_ADVISOR_PROMPT}\n\n"
        f"AVAILABLE_MODELS:\n{json.dumps(snapshot.available_models, ensure_ascii=False)}\n\n"
        f"PROVIDER_SNAPSHOT:\n{json.dumps({'source': snapshot.source, 'models': snapshot.available_models}, ensure_ascii=False)}\n\n"
        f"BOOTSTRAP_PROFILE:\n{json.dumps(profile.to_json(), ensure_ascii=False)}"
    )
    try:
        response = provider_client.generate(
            TextGenerationRequest(
                task=advisor_task_name,
                provider_name=provider_name,
                model=advisor_model,
                system="Return only valid JSON for model routing.",
                messages=[TextMessage(role="user", content=prompt)],
                max_tokens=1200,
                temperature=0.0,
                timeout_seconds=min(timeout_seconds, 120),
                retries=retries,
                response_format={"type": "json_object"},
            )
        )
    except TextProviderError:
        return None
    payload = extract_json_payload(response.text)
    if not isinstance(payload, dict):
        return None
    return AdvisorRecommendation(
        plan=payload,
        model_used=advisor_model,
        raw=payload,
    )


def _pick_advisor_model(snapshot: ProviderSnapshot) -> str | None:
    candidates = snapshot.available_models
    for preferred in ("gpt-4o-mini", "gpt-5-nano", "gpt-5.4-nano", "gpt-4.1-nano", "gpt-4.1-mini"):
        if preferred in candidates:
            return preferred
    return candidates[0] if candidates else None
