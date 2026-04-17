from __future__ import annotations

from pathlib import Path

from vault.bootstrap import validate_vault

from textifai import PRODUCT_NAME
from textifai.runtime_config import load_runtime_environment


def run_doctor(*, base_dir: str | Path = ".") -> dict:
    env = load_runtime_environment(base_dir)
    checks: list[dict] = []

    if env.env_exists:
        checks.append(_check("env_file", "ok", f"Environment file found at {env.env_path}"))
    else:
        checks.append(_check("env_file", "warning", "No .env file found. Run `textifai setup`."))

    if env.backend == "vault":
        checks.append(_check("project_backend", "ok", "Project backend is set to vault."))
    elif env.backend:
        checks.append(_check("project_backend", "warning", f"Project backend is set to {env.backend!r}, not vault."))
    else:
        checks.append(_check("project_backend", "warning", "Project backend is not configured."))

    if env.vault_root:
        vault_path = Path(env.vault_root).expanduser()
        if vault_path.exists():
            errors = validate_vault(vault_path)
            if errors:
                checks.append(_check("vault", "warning", "Vault path exists but is not valid.", details=errors))
            else:
                checks.append(_check("vault", "ok", f"Vault is valid at {vault_path}"))
        else:
            checks.append(_check("vault", "warning", f"Vault path does not exist: {vault_path}"))
    else:
        checks.append(_check("vault", "warning", "Vault path is not configured."))

    if env.provider:
        checks.append(_check("provider", "ok", f"Primary provider is {env.provider}"))
    else:
        checks.append(_check("provider", "warning", "Primary provider is not configured."))

    if env.provider == "anthropic":
        status = "ok" if _env_var("ANTHROPIC_API_KEY") else "warning"
        checks.append(_check("provider_key", status, "Anthropic API key present." if status == "ok" else "Missing ANTHROPIC_API_KEY for hosted Anthropic usage."))
    elif env.provider == "openai":
        status = "ok" if _env_var("OPENAI_API_KEY") else "warning"
        checks.append(_check("provider_key", status, "OpenAI API key present." if status == "ok" else "Missing OPENAI_API_KEY for hosted OpenAI usage."))
    elif env.provider in {"lmstudio", "ollama"}:
        checks.append(_check("provider_key", "ok", f"{env.provider} selected. Local providers do not require hosted API keys by default."))

    overall = "ok"
    if any(check["status"] == "warning" for check in checks):
        overall = "warning"

    return {
        "product": PRODUCT_NAME,
        "overall": overall,
        "checks": checks,
        "recommended_next_step": _recommended_next_step(checks),
    }


def format_doctor_report(report: dict) -> str:
    lines = [f"{report['product']} doctor", f"Overall: {report['overall']}"]
    for check in report["checks"]:
        lines.append(f"- [{check['status']}] {check['name']}: {check['message']}")
        for detail in check.get("details", []):
            lines.append(f"  {detail}")
    lines.append(f"Next step: {report['recommended_next_step']}")
    return "\n".join(lines)


def _check(name: str, status: str, message: str, *, details: list[str] | None = None) -> dict:
    return {"name": name, "status": status, "message": message, "details": details or []}


def _recommended_next_step(checks: list[dict]) -> str:
    if any(check["name"] == "vault" and check["status"] != "ok" for check in checks):
        return "Run `textifai setup` to create or select a valid vault."
    if any(check["name"] == "provider" and check["status"] != "ok" for check in checks):
        return "Run `textifai setup` to choose a provider."
    return "Run `textifai` or `textifai chat` to continue."


def _env_var(name: str) -> str | None:
    from os import environ

    value = environ.get(name, "").strip()
    return value or None
