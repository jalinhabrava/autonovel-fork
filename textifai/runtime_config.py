from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from textifai import PRODUCT_NAME
from textifai.i18n import DEFAULT_LOCALE, get_translator
from textifai.language_policy import LanguagePolicy, load_language_policy


DEFAULT_VAULT_DIRNAME = "TextifAIVault"
DEFAULT_IMPORT_STAGING_DIRNAME = "99_Import_Staging"
ENV_FILE_NAME = ".env"
ENV_EXAMPLE_NAME = ".env.example"


@dataclass(frozen=True)
class RuntimeEnvironment:
    base_dir: Path
    env_path: Path
    env_exists: bool
    backend: str | None
    vault_root: str | None
    provider: str | None
    writer_model: str | None
    language_policy: LanguagePolicy

    @property
    def locale(self) -> str:
        return self.language_policy.interface_language


def load_runtime_environment(base_dir: str | Path = ".") -> RuntimeEnvironment:
    root = Path(base_dir).resolve()
    env_path = root / ENV_FILE_NAME
    values = _load_env_values(env_path)
    language_policy = load_language_policy(root, env_values=values)
    return RuntimeEnvironment(
        base_dir=root,
        env_path=env_path,
        env_exists=env_path.exists(),
        backend=_clean(values.get("AUTONOVEL_PROJECT_BACKEND")),
        vault_root=_clean(values.get("AUTONOVEL_VAULT_ROOT")),
        provider=_clean(values.get("AUTONOVEL_TEXT_PROVIDER")),
        writer_model=_clean(values.get("AUTONOVEL_WRITER_MODEL")),
        language_policy=language_policy,
    )


def default_vault_path(base_dir: str | Path = ".") -> Path:
    return Path(base_dir).resolve() / DEFAULT_VAULT_DIRNAME


def default_import_staging_path(vault_root: str | Path) -> Path:
    return Path(vault_root).expanduser().resolve() / DEFAULT_IMPORT_STAGING_DIRNAME


def ensure_env_file(base_dir: str | Path = ".") -> Path:
    root = Path(base_dir).resolve()
    env_path = root / ENV_FILE_NAME
    if env_path.exists():
        return env_path
    example_path = root / ENV_EXAMPLE_NAME
    if example_path.exists():
        env_path.write_text(example_path.read_text())
    else:
        env_path.write_text("")
    return env_path


def update_env_values(base_dir: str | Path, updates: dict[str, str]) -> Path:
    env_path = ensure_env_file(base_dir)
    lines = env_path.read_text().splitlines()
    key_to_index: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        key_to_index[key] = index

    for key, value in updates.items():
        rendered = f"{key}={value}"
        if key in key_to_index:
            lines[key_to_index[key]] = rendered
        else:
            lines.append(rendered)

    env_path.write_text("\n".join(lines).rstrip() + "\n")
    return env_path


def synchronize_runtime_environment(base_dir: str | Path = ".") -> dict[str, str]:
    root = Path(base_dir).resolve()
    env_path = root / ENV_FILE_NAME
    values = _load_env_values(env_path)
    keys = {
        "AUTONOVEL_PROJECT_BACKEND",
        "AUTONOVEL_VAULT_ROOT",
        "AUTONOVEL_TEXT_PROVIDER",
        "AUTONOVEL_WRITER_MODEL",
        "AUTONOVEL_OPENAI_API_BASE_URL",
        "OPENAI_API_KEY",
        "AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL",
        "AUTONOVEL_OPENAI_COMPATIBLE_API_KEY",
        "AUTONOVEL_OLLAMA_API_BASE_URL",
        "AUTONOVEL_OLLAMA_API_KEY",
    }
    for key in keys:
        value = values.get(key)
        if value is None or value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return values


def runtime_banner(locale: str = DEFAULT_LOCALE) -> str:
    return get_translator(locale).t("shell.banner.title")


def _load_env_values(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip()
    for key in (
        "AUTONOVEL_PROJECT_BACKEND",
        "AUTONOVEL_VAULT_ROOT",
        "AUTONOVEL_TEXT_PROVIDER",
        "AUTONOVEL_WRITER_MODEL",
        "TEXTIFAI_LOCALE",
        "TEXTIFAI_INTERFACE_LANGUAGE",
        "TEXTIFAI_USER_COMMAND_LANGUAGE",
        "TEXTIFAI_INTERNAL_SYSTEM_LANGUAGE",
        "TEXTIFAI_PROJECT_DEFAULT_LANGUAGE",
        "TEXTIFAI_MIXED_LANGUAGE_ALLOWED",
        "TEXTIFAI_ARTIFACT_LANGUAGES",
    ):
        if key in os.environ and os.environ[key]:
            values[key] = os.environ[key]
    return values


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
