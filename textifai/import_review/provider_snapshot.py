from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from textifai.import_review.model_registry import ModelCapabilities, get_model_capabilities, list_known_models


_OPENAI_TEXT_MODEL_BLOCKLIST = (
    "audio",
    "realtime",
    "image",
    "transcribe",
    "tts",
    "embedding",
    "moderation",
    "deep-research",
    "search-preview",
    "chatgpt",
)


@dataclass(frozen=True)
class ProviderModelSnapshot:
    model: str
    available: bool
    capabilities: ModelCapabilities


@dataclass(frozen=True)
class ProviderSnapshot:
    provider_name: str
    fetched_at: str
    source: str
    available_models: list[str]
    models: list[ProviderModelSnapshot]


def build_provider_snapshot(
    *,
    provider_name: str | None,
    requested_model: str | None,
    timeout_seconds: int,
    cache_path: Path | None = None,
) -> ProviderSnapshot:
    provider = str(provider_name or "").strip().casefold() or "openai"
    if provider == "openai":
        snapshot = _build_openai_snapshot(timeout_seconds=timeout_seconds)
    elif provider == "lmstudio":
        model_name = str(requested_model or os.environ.get("AUTONOVEL_BOOTSTRAP_MODEL") or "qwen/qwen3.5-9b").strip()
        snapshot = ProviderSnapshot(
            provider_name="lmstudio",
            fetched_at=_utc_now_iso(),
            source="static_local_provider",
            available_models=[model_name],
            models=[ProviderModelSnapshot(model=model_name, available=True, capabilities=get_model_capabilities(model_name))],
        )
    else:
        model_name = str(requested_model or "").strip() or "default"
        snapshot = ProviderSnapshot(
            provider_name=provider,
            fetched_at=_utc_now_iso(),
            source="static_requested_model",
            available_models=[model_name],
            models=[ProviderModelSnapshot(model=model_name, available=True, capabilities=get_model_capabilities(model_name))],
        )
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "provider_name": snapshot.provider_name,
                    "fetched_at": snapshot.fetched_at,
                    "source": snapshot.source,
                    "available_models": snapshot.available_models,
                    "models": [
                        {
                            "model": item.model,
                            "available": item.available,
                            "capabilities": asdict(item.capabilities),
                        }
                        for item in snapshot.models
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return snapshot


def _build_openai_snapshot(*, timeout_seconds: int) -> ProviderSnapshot:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    api_base = os.environ.get("AUTONOVEL_OPENAI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    fetched_at = _utc_now_iso()
    if not api_key:
        return _fallback_snapshot("openai", fetched_at=fetched_at, source="fallback_no_api_key")
    try:
        response = httpx.get(
            f"{api_base}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=min(timeout_seconds, 60),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return _fallback_snapshot("openai", fetched_at=fetched_at, source="fallback_list_models_failed")
    model_ids = [
        str(item.get("id") or "").strip()
        for item in (payload.get("data") or [])
        if isinstance(item, dict)
    ]
    filtered_models = [model_id for model_id in model_ids if _is_candidate_text_model(model_id)]
    if not filtered_models:
        return _fallback_snapshot("openai", fetched_at=fetched_at, source="fallback_no_text_models")
    filtered_models = sorted(dict.fromkeys(filtered_models))
    return ProviderSnapshot(
        provider_name="openai",
        fetched_at=fetched_at,
        source="openai_models_api",
        available_models=filtered_models,
        models=[
            ProviderModelSnapshot(
                model=model_name,
                available=True,
                capabilities=get_model_capabilities(model_name),
            )
            for model_name in filtered_models
        ],
    )


def _fallback_snapshot(provider_name: str, *, fetched_at: str, source: str) -> ProviderSnapshot:
    known_models = [model for model in list_known_models() if model.startswith(("gpt-", "o"))]
    return ProviderSnapshot(
        provider_name=provider_name,
        fetched_at=fetched_at,
        source=source,
        available_models=known_models,
        models=[
            ProviderModelSnapshot(
                model=model_name,
                available=True,
                capabilities=get_model_capabilities(model_name),
            )
            for model_name in known_models
        ],
    )


def _is_candidate_text_model(model_name: str) -> bool:
    normalized = str(model_name or "").strip().casefold()
    if not normalized:
        return False
    if not normalized.startswith(("gpt-", "o")):
        return False
    return not any(token in normalized for token in _OPENAI_TEXT_MODEL_BLOCKLIST)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
