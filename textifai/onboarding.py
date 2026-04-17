from __future__ import annotations

from pathlib import Path

from vault.bootstrap import bootstrap_vault, validate_vault
from vault.ingest import import_existing_chapters

from textifai import PRODUCT_NAME
from textifai.runtime_config import default_vault_path, update_env_values


def run_onboarding(
    *,
    base_dir: str | Path = ".",
    input_fn=input,
    output_fn=print,
) -> dict:
    root = Path(base_dir).resolve()
    output_fn(f"{PRODUCT_NAME} setup")

    suggested_vault = default_vault_path(root)
    vault_input = input_fn(f"Vault path [{suggested_vault}]: ").strip()
    vault_path = Path(vault_input).expanduser() if vault_input else suggested_vault

    if vault_path.exists():
        errors = validate_vault(vault_path)
        if errors:
            create_choice = _ask_choice(
                input_fn,
                "The path exists but is not a valid vault. Create a new vault here? [Y/n]: ",
                default="y",
            )
            if create_choice == "n":
                raise ValueError(f"{PRODUCT_NAME} setup aborted: invalid vault path {vault_path}")
            title = input_fn("Project title [TextifAI Project]: ").strip() or "TextifAI Project"
            bootstrap_vault(vault_path, title=title, force=True)
    else:
        create_choice = _ask_choice(input_fn, "Create a new vault? [Y/n]: ", default="y")
        if create_choice == "n":
            raise ValueError(f"{PRODUCT_NAME} setup aborted: vault path does not exist {vault_path}")
        title = input_fn("Project title [TextifAI Project]: ").strip() or "TextifAI Project"
        bootstrap_vault(vault_path, title=title, force=False)

    start_mode = _ask_choice(
        input_fn,
        "Start from [e]mpty vault or [m]anuscript import? [e/m]: ",
        default="e",
        allowed={"e", "m"},
    )
    imported_paths: list[str] = []
    if start_mode == "m":
        source_dir = input_fn("Manuscript chapters directory: ").strip()
        if source_dir:
            imported_paths = [str(path) for path in import_existing_chapters(vault_path, source_dir)]

    provider = input_fn("Primary text provider [anthropic/openai/lmstudio/ollama] (default: anthropic): ").strip() or "anthropic"
    writer_model = input_fn("Writer model override (leave blank for default): ").strip()

    env_updates = {
        "AUTONOVEL_PROJECT_BACKEND": "vault",
        "AUTONOVEL_VAULT_ROOT": str(vault_path),
        "AUTONOVEL_TEXT_PROVIDER": provider,
    }
    if writer_model:
        env_updates["AUTONOVEL_WRITER_MODEL"] = writer_model

    env_path = update_env_values(root, env_updates)
    output_fn(f"{PRODUCT_NAME} setup complete.")
    output_fn(f"Vault: {vault_path}")
    output_fn(f"Provider: {provider}")
    output_fn(f"Env file: {env_path}")

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
