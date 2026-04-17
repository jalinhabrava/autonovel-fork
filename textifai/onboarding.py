from __future__ import annotations

from pathlib import Path

from textifai.i18n import get_translator
from vault.bootstrap import bootstrap_vault, validate_vault
from vault.ingest import import_existing_chapters

from textifai.runtime_config import default_vault_path, load_runtime_environment, update_env_values


def run_onboarding(
    *,
    base_dir: str | Path = ".",
    input_fn=input,
    output_fn=print,
) -> dict:
    root = Path(base_dir).resolve()
    tr = get_translator(load_runtime_environment(root).locale)
    output_fn(tr.t("onboarding.title"))

    suggested_vault = default_vault_path(root)
    vault_input = input_fn(tr.t("onboarding.prompt.vault_path", suggested_vault=suggested_vault)).strip()
    vault_path = Path(vault_input).expanduser() if vault_input else suggested_vault

    if vault_path.exists():
        errors = validate_vault(vault_path)
        if errors:
            create_choice = _ask_choice(
                input_fn,
                tr.t("onboarding.prompt.invalid_vault_create"),
                default="y",
            )
            if create_choice == "n":
                raise ValueError(tr.t("onboarding.errors.invalid_vault_abort", vault_path=vault_path))
            title = input_fn(tr.t("onboarding.prompt.project_title")).strip() or "TextifAI Project"
            bootstrap_vault(vault_path, title=title, force=True)
    else:
        create_choice = _ask_choice(input_fn, tr.t("onboarding.prompt.create_vault"), default="y")
        if create_choice == "n":
            raise ValueError(tr.t("onboarding.errors.vault_missing_abort", vault_path=vault_path))
        title = input_fn(tr.t("onboarding.prompt.project_title")).strip() or "TextifAI Project"
        bootstrap_vault(vault_path, title=title, force=False)

    start_mode = _ask_choice(
        input_fn,
        tr.t("onboarding.prompt.start_mode"),
        default="e",
        allowed={"e", "m"},
    )
    imported_paths: list[str] = []
    if start_mode == "m":
        source_dir = input_fn(tr.t("onboarding.prompt.manuscript_dir")).strip()
        if source_dir:
            imported_paths = [str(path) for path in import_existing_chapters(vault_path, source_dir)]

    provider = input_fn(tr.t("onboarding.prompt.provider")).strip() or "anthropic"
    writer_model = input_fn(tr.t("onboarding.prompt.writer_model")).strip()

    env_updates = {
        "AUTONOVEL_PROJECT_BACKEND": "vault",
        "AUTONOVEL_VAULT_ROOT": str(vault_path),
        "AUTONOVEL_TEXT_PROVIDER": provider,
    }
    if writer_model:
        env_updates["AUTONOVEL_WRITER_MODEL"] = writer_model

    env_path = update_env_values(root, env_updates)
    output_fn(tr.t("onboarding.complete"))
    output_fn(tr.t("onboarding.summary.vault", vault_path=vault_path))
    output_fn(tr.t("onboarding.summary.provider", provider=provider))
    output_fn(tr.t("onboarding.summary.env_path", env_path=env_path))

    return {
        "vault_path": str(vault_path),
        "provider": provider,
        "writer_model": writer_model or None,
        "env_path": str(env_path),
        "imported_paths": imported_paths,
        "start_mode": "manuscript" if start_mode == "m" else "empty",
    }


def _ask_choice(input_fn, prompt: str, *, default: str, allowed: set[str] | None = None) -> str:
    value = input_fn(prompt).strip().lower() or default
    if allowed and value not in allowed:
        return default
    return value
