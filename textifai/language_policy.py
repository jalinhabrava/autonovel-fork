from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from textifai.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, normalize_locale
from vault.notes import NOTE_TYPE_DIRS, ROOT_ARTIFACT_KINDS


DEFAULT_INTERNAL_SYSTEM_LANGUAGE = "en"
DEFAULT_PROJECT_LANGUAGE = "en"
SUPPORTED_ARTIFACT_LANGUAGE_TYPES = tuple(sorted(set(NOTE_TYPE_DIRS) | set(ROOT_ARTIFACT_KINDS)))


@dataclass(frozen=True)
class LanguagePolicy:
    interface_language: str
    user_command_language: str
    internal_system_language: str
    project_default_language: str
    mixed_language_allowed: bool
    artifact_languages: dict[str, str]


def load_language_policy(
    base_dir: str | Path = ".",
    *,
    env_values: dict[str, str] | None = None,
    project_overrides: dict | None = None,
) -> LanguagePolicy:
    root = Path(base_dir).resolve()
    config_values = _load_policy_config(root / "config" / "language_policy.json")
    env = env_values or {}
    overrides = project_overrides or {}

    interface_language = _resolve_interface_language(config_values, env)
    user_command_language = _resolve_language(
        explicit=overrides.get("user_command_language"),
        env_value=env.get("TEXTIFAI_USER_COMMAND_LANGUAGE"),
        config_value=config_values.get("user_command_language"),
        default=interface_language,
    )
    internal_system_language = _resolve_language(
        explicit=overrides.get("internal_system_language"),
        env_value=env.get("TEXTIFAI_INTERNAL_SYSTEM_LANGUAGE"),
        config_value=config_values.get("internal_system_language"),
        default=DEFAULT_INTERNAL_SYSTEM_LANGUAGE,
    )
    project_default_language = _resolve_language(
        explicit=overrides.get("project_default_language"),
        env_value=env.get("TEXTIFAI_PROJECT_DEFAULT_LANGUAGE"),
        config_value=config_values.get("project_default_language"),
        default=DEFAULT_PROJECT_LANGUAGE,
    )
    mixed_language_allowed = _resolve_bool(
        explicit=overrides.get("mixed_language_allowed"),
        env_value=env.get("TEXTIFAI_MIXED_LANGUAGE_ALLOWED"),
        config_value=config_values.get("mixed_language_allowed"),
        default=True,
    )
    artifact_languages = _resolve_artifact_languages(
        project_default_language=project_default_language,
        config_values=config_values.get("artifact_languages", {}),
        env_value=env.get("TEXTIFAI_ARTIFACT_LANGUAGES"),
        explicit=overrides.get("artifact_languages", {}),
    )

    return LanguagePolicy(
        interface_language=interface_language,
        user_command_language=user_command_language,
        internal_system_language=internal_system_language,
        project_default_language=project_default_language,
        mixed_language_allowed=mixed_language_allowed,
        artifact_languages=artifact_languages,
    )


def artifact_language(policy: LanguagePolicy, artifact_type: str) -> str:
    return policy.artifact_languages.get(artifact_type, policy.project_default_language)


def _resolve_interface_language(config_values: dict, env: dict[str, str]) -> str:
    explicit = env.get("TEXTIFAI_INTERFACE_LANGUAGE") or env.get("TEXTIFAI_LOCALE")
    if explicit:
        return normalize_locale(explicit)
    configured = config_values.get("interface_language")
    if configured:
        return normalize_locale(str(configured))
    detected = _detect_locale()
    return normalize_locale(detected or DEFAULT_LOCALE)


def _resolve_language(*, explicit, env_value, config_value, default: str) -> str:
    if explicit:
        return normalize_language_code(str(explicit))
    if env_value:
        return normalize_language_code(str(env_value))
    if config_value:
        return normalize_language_code(str(config_value))
    return normalize_language_code(default)


def _resolve_bool(*, explicit, env_value, config_value, default: bool) -> bool:
    if explicit is not None:
        return bool(explicit)
    if env_value is not None:
        return str(env_value).strip().lower() in {"1", "true", "yes", "y", "on"}
    if config_value is not None:
        return bool(config_value)
    return default


def _resolve_artifact_languages(
    *,
    project_default_language: str,
    config_values: dict,
    env_value: str | None,
    explicit: dict,
) -> dict[str, str]:
    resolved = {artifact_type: project_default_language for artifact_type in SUPPORTED_ARTIFACT_LANGUAGE_TYPES}
    for mapping in (_normalize_artifact_map(config_values), _parse_env_artifact_map(env_value), _normalize_artifact_map(explicit)):
        resolved.update(mapping)
    return resolved


def _parse_env_artifact_map(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return _normalize_artifact_map(data)


def _normalize_artifact_map(values) -> dict[str, str]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if key in SUPPORTED_ARTIFACT_LANGUAGE_TYPES and value:
            normalized[key] = normalize_language_code(str(value))
    return normalized


def _load_policy_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _detect_locale() -> str | None:
    from os import environ

    for key in ("LC_ALL", "LANG"):
        value = environ.get(key, "").strip()
        if not value:
            continue
        primary = value.lower().replace("-", "_").split("_", 1)[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return None


def normalize_language_code(value: str | None) -> str:
    if not value:
        return DEFAULT_PROJECT_LANGUAGE
    lowered = str(value).strip().lower().replace("-", "_")
    primary = lowered.split("_", 1)[0]
    return primary or DEFAULT_PROJECT_LANGUAGE
