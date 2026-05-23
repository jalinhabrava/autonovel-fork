from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from providers.text_provider import (
    TextGenerationRequest,
    TextMessage,
    get_text_provider,
    get_text_provider_config_error,
    resolve_text_request,
)
from textifai.runtime_config import load_runtime_environment, synchronize_runtime_environment, update_env_values


SUPPORTED_PROVIDER_CHOICES = (
    "anthropic",
    "deepseek",
    "openai",
    "openai_compatible",
    "local_openai_compatible",
    "ollama",
    "skip",
)


@dataclass(frozen=True)
class ProviderConfiguration:
    provider_choice: str
    provider_name: str | None = None
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.provider_choice not in SUPPORTED_PROVIDER_CHOICES:
            raise ValueError(f"Unsupported provider_choice: {self.provider_choice}")


@dataclass(frozen=True)
class ProviderReadiness:
    provider_name: str | None
    provider_mode: str
    provider_model: str | None
    provider_configured: bool
    provider_reachable: bool
    author_flows_available: bool
    available_for_author_response: bool
    configuration_error: str | None = None
    connectivity_error: str | None = None
    api_base: str | None = None


def configure_provider(
    *,
    base_dir: str | Path,
    configuration: ProviderConfiguration,
    test_connectivity: bool = True,
) -> ProviderReadiness:
    updates = _provider_env_updates(configuration)
    update_env_values(base_dir, updates)
    return evaluate_provider_readiness(base_dir, run_connectivity_test=test_connectivity)


def evaluate_provider_readiness(
    base_dir: str | Path = ".",
    *,
    task_name: str = "author_response",
    run_connectivity_test: bool = True,
) -> ProviderReadiness:
    synchronize_runtime_environment(base_dir)
    env = load_runtime_environment(base_dir)
    provider_name = env.provider
    api_base = _provider_api_base(provider_name)
    if not provider_name:
        return ProviderReadiness(
            provider_name=None,
            provider_mode="disabled",
            provider_model=None,
            provider_configured=False,
            provider_reachable=False,
            author_flows_available=False,
            available_for_author_response=False,
            configuration_error="provider_not_configured",
            api_base=None,
        )

    configuration_error = get_text_provider_config_error(task_name, provider_name)
    provider_model = None
    connectivity_error = None
    provider_reachable = False

    if configuration_error is None:
        try:
            resolved = resolve_text_request(
                TextGenerationRequest(
                    task=task_name,
                    provider_name=provider_name,
                    model=env.writer_model,
                    messages=[TextMessage(role="user", content="Return OK.")],
                    system="Reply with the single token OK.",
                    max_tokens=8,
                    temperature=0.0,
                    timeout_seconds=15,
                    retries=0,
                )
            )
            provider_model = resolved.model
            if run_connectivity_test:
                provider = get_text_provider(task_name, provider_name)
                response = provider.generate(
                    TextGenerationRequest(
                        task=task_name,
                        provider_name=provider_name,
                        model=provider_model,
                        messages=[TextMessage(role="user", content="Return OK.")],
                        system="Reply with the single token OK.",
                        max_tokens=8,
                        temperature=0.0,
                        timeout_seconds=15,
                        retries=0,
                    )
                )
                provider_reachable = bool(response.text.strip())
                provider_model = response.model or provider_model
        except Exception as exc:
            connectivity_error = str(exc)

    provider_mode = _provider_mode(provider_name, api_base=api_base)
    author_flows_available = configuration_error is None and provider_reachable
    return ProviderReadiness(
        provider_name=provider_name,
        provider_mode=provider_mode,
        provider_model=provider_model or env.writer_model,
        provider_configured=True,
        provider_reachable=provider_reachable,
        author_flows_available=author_flows_available,
        available_for_author_response=author_flows_available,
        configuration_error=configuration_error,
        connectivity_error=connectivity_error,
        api_base=api_base,
    )


def _provider_env_updates(configuration: ProviderConfiguration) -> dict[str, str]:
    if configuration.provider_choice == "skip":
        return {
            "AUTONOVEL_TEXT_PROVIDER": "",
            "AUTONOVEL_WRITER_MODEL": "",
        }

    provider_name = configuration.provider_name or _canonical_provider_name(configuration.provider_choice)
    updates = {
        "AUTONOVEL_TEXT_PROVIDER": provider_name,
        "AUTONOVEL_WRITER_MODEL": configuration.model or "",
    }
    if provider_name == "anthropic":
        updates["ANTHROPIC_API_KEY"] = configuration.api_key or ""
        if configuration.api_base:
            updates["AUTONOVEL_API_BASE_URL"] = configuration.api_base
    elif provider_name == "deepseek":
        updates["DEEPSEEK_API_KEY"] = configuration.api_key or ""
        if configuration.api_base:
            updates["AUTONOVEL_DEEPSEEK_API_BASE_URL"] = configuration.api_base
    elif provider_name == "openai":
        updates["OPENAI_API_KEY"] = configuration.api_key or ""
        if configuration.api_base:
            updates["AUTONOVEL_OPENAI_API_BASE_URL"] = configuration.api_base
    elif provider_name == "openai_compatible":
        updates["AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL"] = configuration.api_base or ""
        updates["AUTONOVEL_OPENAI_COMPATIBLE_API_KEY"] = configuration.api_key or ""
    elif provider_name == "ollama":
        updates["AUTONOVEL_OLLAMA_API_BASE_URL"] = configuration.api_base or "http://localhost:11434/v1"
        updates["AUTONOVEL_OLLAMA_API_KEY"] = configuration.api_key or ""
    else:
        raise ValueError(f"Unsupported provider_name for configuration: {provider_name}")
    return updates


def _canonical_provider_name(provider_choice: str) -> str | None:
    mappings = {
        "anthropic": "anthropic",
        "deepseek": "deepseek",
        "openai": "openai",
        "openai_compatible": "openai_compatible",
        "local_openai_compatible": "openai_compatible",
        "ollama": "ollama",
        "skip": None,
    }
    return mappings.get(provider_choice)


def _provider_mode(provider_name: str | None, *, api_base: str | None) -> str:
    if not provider_name:
        return "disabled"
    if provider_name == "anthropic":
        return "remote_anthropic"
    if provider_name == "deepseek":
        return "remote_openai_compatible"
    if provider_name == "openai":
        return "remote_openai"
    if provider_name == "openai_compatible":
        normalized = (api_base or "").casefold()
        if "localhost" in normalized or "127.0.0.1" in normalized:
            return "local_openai_compatible"
        return "remote_openai_compatible"
    if provider_name == "ollama":
        return "local_ollama"
    return provider_name


def _provider_api_base(provider_name: str | None) -> str | None:
    import os

    if provider_name == "anthropic":
        return os.environ.get("AUTONOVEL_API_BASE_URL", "").strip() or "https://api.anthropic.com"
    if provider_name == "deepseek":
        return os.environ.get("AUTONOVEL_DEEPSEEK_API_BASE_URL", "").strip() or "https://api.deepseek.com"
    if provider_name == "openai":
        return os.environ.get("AUTONOVEL_OPENAI_API_BASE_URL", "").strip() or "https://api.openai.com/v1"
    if provider_name == "openai_compatible":
        return os.environ.get("AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL", "").strip() or None
    if provider_name == "ollama":
        return os.environ.get("AUTONOVEL_OLLAMA_API_BASE_URL", "").strip() or "http://localhost:11434/v1"
    return None
