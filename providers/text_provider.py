from __future__ import annotations

import os
import time
import json
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "inference.json"


@dataclass(frozen=True)
class TextMessage:
    role: str
    content: str


@dataclass(frozen=True)
class TextGenerationRequest:
    messages: list[TextMessage]
    task: str | None = None
    system: str | None = None
    model: str | None = None
    provider_name: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_seconds: int | None = None
    retries: int | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TextGenerationResponse:
    text: str
    raw: dict[str, Any]
    provider_name: str
    model: str
    task: str | None


@dataclass(frozen=True)
class ResolvedTextRequest:
    task: str | None
    provider_name: str
    model: str
    messages: list[TextMessage]
    system: str | None
    max_tokens: int
    temperature: float
    timeout_seconds: int
    retries: int
    extra_headers: dict[str, str]


class TextProviderError(RuntimeError):
    def __init__(self, provider_name: str, model: str, message: str):
        super().__init__(f"{provider_name}/{model}: {message}")
        self.provider_name = provider_name
        self.model = model


class TextProvider(Protocol):
    def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        ...


class BaseHTTPTextProvider:
    def __init__(self, provider_name: str, api_key: str = "", api_base: str = ""):
        self.provider_name = provider_name
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")

    def _post_json(
        self,
        resolved: ResolvedTextRequest,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import httpx

        last_error: Exception | None = None
        attempts = resolved.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                resp = httpx.post(
                    f"{self.api_base}{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=resolved.timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                retry_after = 0.0
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    header_value = exc.response.headers.get("retry-after", "").strip()
                    try:
                        retry_after = float(header_value)
                    except ValueError:
                        retry_after = 0.0
                    if exc.response.status_code == 429:
                        retry_after = max(retry_after, min(2 ** attempt, 20))
                sleep_for = retry_after or min(2 ** (attempt - 1), 6)
                sleep_for += random.uniform(0.0, 0.35)
                time.sleep(sleep_for)

        raise TextProviderError(
            self.provider_name,
            resolved.model,
            f"request failed after {attempts} attempt(s): {last_error}",
        )

    def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        raise NotImplementedError


class AnthropicCompatibleTextProvider(BaseHTTPTextProvider):
    """Provider for Anthropic-compatible Messages APIs."""

    def __init__(self, provider_name: str = "anthropic_compatible", api_key: str = "", api_base: str = "https://api.anthropic.com"):
        super().__init__(provider_name=provider_name, api_key=api_key, api_base=api_base)

    def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        resolved = resolve_text_request(request)
        headers = _build_anthropic_headers(api_key=self.api_key, extra_headers=resolved.extra_headers)
        payload = _build_anthropic_payload(resolved)

        raw = self._post_json(
            resolved,
            endpoint="/v1/messages",
            headers=headers,
            payload=payload,
        )
        return TextGenerationResponse(
            text=_extract_anthropic_text(raw),
            raw=raw,
            provider_name=resolved.provider_name,
            model=resolved.model,
            task=resolved.task,
        )


class AnthropicTextProvider(AnthropicCompatibleTextProvider):
    """Anthropic-hosted text provider."""


class OpenAICompatibleTextProvider(BaseHTTPTextProvider):
    """Provider for OpenAI-compatible Chat Completions APIs."""

    def __init__(self, provider_name: str = "openai_compatible", api_key: str = "", api_base: str = "https://api.openai.com/v1"):
        super().__init__(provider_name=provider_name, api_key=api_key, api_base=api_base)

    def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        resolved = resolve_text_request(request)
        headers = _build_openai_headers(api_key=self.api_key, extra_headers=resolved.extra_headers)
        payload = _build_openai_payload(resolved)

        raw = self._post_json(
            resolved,
            endpoint="/chat/completions",
            headers=headers,
            payload=payload,
        )
        return TextGenerationResponse(
            text=_extract_openai_text(raw),
            raw=raw,
            provider_name=resolved.provider_name,
            model=resolved.model,
            task=resolved.task,
        )


class OpenAITextProvider(OpenAICompatibleTextProvider):
    """OpenAI-hosted text provider."""


class LMStudioTextProvider(OpenAICompatibleTextProvider):
    """LM Studio local server through its OpenAI-compatible endpoints."""


class OllamaTextProvider(OpenAICompatibleTextProvider):
    """Ollama local server through its OpenAI-compatible endpoints."""


PROVIDER_ALIASES = {
    "anthropic": "anthropic",
    "anthropic_messages": "anthropic",
    "anthropic_compatible": "anthropic_compatible",
    "openai": "openai",
    "openai_chat": "openai",
    "openai_responses": "openai",
    "openai_compatible": "openai_compatible",
    "lmstudio": "lmstudio",
    "lm_studio": "lmstudio",
    "ollama": "ollama",
}


PROVIDER_REGISTRY = {
    "anthropic": lambda: AnthropicTextProvider(
        provider_name="anthropic",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com"),
    ),
    "openai": lambda: OpenAITextProvider(
        provider_name="openai",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
    ),
    "anthropic_compatible": lambda: AnthropicCompatibleTextProvider(
        provider_name="anthropic_compatible",
        api_key=os.environ.get("AUTONOVEL_ANTHROPIC_COMPATIBLE_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_ANTHROPIC_COMPATIBLE_API_BASE_URL", ""),
    ),
    "openai_compatible": lambda: OpenAICompatibleTextProvider(
        provider_name="openai_compatible",
        api_key=os.environ.get("AUTONOVEL_OPENAI_COMPATIBLE_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL", ""),
    ),
    "lmstudio": lambda: LMStudioTextProvider(
        provider_name="lmstudio",
        api_key=os.environ.get("AUTONOVEL_LMSTUDIO_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_LMSTUDIO_API_BASE_URL", "http://localhost:1234/v1"),
    ),
    "ollama": lambda: OllamaTextProvider(
        provider_name="ollama",
        api_key=os.environ.get("AUTONOVEL_OLLAMA_API_KEY", ""),
        api_base=os.environ.get("AUTONOVEL_OLLAMA_API_BASE_URL", "http://localhost:11434/v1"),
    ),
}


def _extract_anthropic_text(raw: dict[str, Any]) -> str:
    content = raw.get("content", [])
    if isinstance(content, list):
        texts = [block.get("text", "") for block in content if isinstance(block, dict)]
        return "\n".join(t for t in texts if t).strip()
    raise TextProviderError("anthropic_compatible", "unknown", f"unexpected response payload: {raw!r}")


def _extract_openai_text(raw: dict[str, Any]) -> str:
    choices = raw.get("choices", [])
    if not choices:
        raise TextProviderError("openai_compatible", "unknown", f"unexpected response payload: {raw!r}")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(t for t in texts if t).strip()
    return str(content)


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build_anthropic_headers(*, api_key: str, extra_headers: dict[str, str]) -> dict[str, str]:
    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if api_key:
        headers["x-api-key"] = api_key
    headers.update(extra_headers)
    return headers


def _build_anthropic_payload(resolved: ResolvedTextRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": resolved.model,
        "max_tokens": resolved.max_tokens,
        "temperature": resolved.temperature,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in resolved.messages
        ],
    }
    if resolved.system is not None:
        payload["system"] = resolved.system
    return payload


def _build_openai_headers(*, api_key: str, extra_headers: dict[str, str]) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers.update(
        {
            key: value
            for key, value in extra_headers.items()
            if not key.lower().startswith("anthropic-")
        }
    )
    return headers


def _build_openai_messages(resolved: ResolvedTextRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if resolved.system is not None:
        messages.append({"role": "system", "content": resolved.system})
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in resolved.messages
    )
    return messages


def _build_openai_payload(resolved: ResolvedTextRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": resolved.model,
        "messages": _build_openai_messages(resolved),
        "temperature": resolved.temperature,
    }
    token_field = _openai_token_parameter(
        provider_name=resolved.provider_name,
        model=resolved.model,
    )
    payload[token_field] = resolved.max_tokens
    return payload


def _openai_token_parameter(*, provider_name: str, model: str | None) -> str:
    if provider_name == "openai" and _uses_openai_responses_style_limits(model):
        return "max_completion_tokens"
    return "max_tokens"


def _uses_openai_responses_style_limits(model: str | None) -> bool:
    normalized = (model or "").strip().lower()
    return normalized.startswith(("gpt-5", "o1", "o3", "o4"))


@lru_cache(maxsize=1)
def load_inference_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Inference config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open() as f:
        return json.load(f)


def get_task_text_settings(task: str | None) -> dict[str, Any]:
    config = load_inference_config()
    defaults = config.get("defaults", {})
    tasks = config.get("tasks", {})
    roles = config.get("roles", {})

    task_settings = tasks.get(task or "", {})
    role_name = task_settings.get("role")
    role_settings = roles.get(role_name, {}) if role_name else {}

    merged = _deep_merge(defaults, role_settings)
    merged = _deep_merge(merged, task_settings)
    return merged


def _resolve_model(settings: dict[str, Any], request: TextGenerationRequest) -> str:
    if request.model:
        return request.model
    model_env = settings.get("model_env")
    if model_env:
        env_value = os.environ.get(model_env, "").strip()
        if env_value:
            return env_value
    model = settings.get("model")
    if model:
        return str(model)
    raise ValueError(f"No model configured for task {request.task!r}")


def get_text_provider_name(task_name: str | None = None, provider_name: str | None = None) -> str:
    if provider_name:
        raw_name = provider_name
    else:
        task_settings = get_task_text_settings(task_name)
        raw_name = (
            os.environ.get("AUTONOVEL_TEXT_PROVIDER", "").strip().lower()
            or str(task_settings.get("provider", "anthropic"))
        )
    canonical = PROVIDER_ALIASES.get(raw_name)
    if canonical:
        return canonical
    raise ValueError(
        f"Unsupported AUTONOVEL_TEXT_PROVIDER={raw_name!r}. "
        "Supported providers: anthropic, openai, lmstudio, ollama, "
        "anthropic_compatible, openai_compatible."
    )


def resolve_text_request(request: TextGenerationRequest) -> ResolvedTextRequest:
    settings = get_task_text_settings(request.task)
    provider_name = get_text_provider_name(request.task, request.provider_name)
    return ResolvedTextRequest(
        task=request.task,
        provider_name=provider_name,
        model=_resolve_model(settings, request),
        messages=request.messages,
        system=request.system,
        max_tokens=int(request.max_tokens if request.max_tokens is not None else settings.get("max_tokens", 16000)),
        temperature=float(request.temperature if request.temperature is not None else settings.get("temperature", 0.7)),
        timeout_seconds=int(
            request.timeout_seconds
            if request.timeout_seconds is not None
            else settings.get("timeout_seconds", 600)
        ),
        retries=int(request.retries if request.retries is not None else settings.get("retries", 2)),
        extra_headers=_deep_merge(settings.get("extra_headers", {}), request.extra_headers),
    )


def get_text_provider_config_error(task_name: str | None = None, provider_name: str | None = None) -> str | None:
    provider = get_text_provider_name(task_name, provider_name)
    requirements = {
        "anthropic": ("ANTHROPIC_API_KEY",),
        "openai": ("OPENAI_API_KEY",),
        "anthropic_compatible": ("AUTONOVEL_ANTHROPIC_COMPATIBLE_API_BASE_URL",),
        "openai_compatible": ("AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL",),
        "lmstudio": tuple(),
        "ollama": tuple(),
    }
    for env_name in requirements[provider]:
        if not os.environ.get(env_name, "").strip():
            return f"{env_name} not set in .env"
    return None


def get_text_provider(task_name: str | None = None, provider_name: str | None = None) -> TextProvider:
    canonical = get_text_provider_name(task_name, provider_name)
    factory = PROVIDER_REGISTRY.get(canonical)
    if factory is None:
        raise AssertionError(f"Unhandled text provider {canonical!r}")
    return factory()
