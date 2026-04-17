from __future__ import annotations

from pathlib import Path

from textifai.i18n import get_translator
from vault.bootstrap import validate_vault

from textifai.runtime_config import load_runtime_environment


def run_doctor(*, base_dir: str | Path = ".") -> dict:
    env = load_runtime_environment(base_dir)
    tr = get_translator(env.locale)
    checks: list[dict] = []

    if env.env_exists:
        checks.append(_check("env_file", "ok", tr.t("doctor.check.env.ok", env_path=env.env_path)))
    else:
        checks.append(_check("env_file", "warning", tr.t("doctor.check.env.missing")))

    if env.backend == "vault":
        checks.append(_check("project_backend", "ok", tr.t("doctor.check.backend.vault")))
    elif env.backend:
        checks.append(_check("project_backend", "warning", tr.t("doctor.check.backend.other", backend=env.backend)))
    else:
        checks.append(_check("project_backend", "warning", tr.t("doctor.check.backend.missing")))

    if env.vault_root:
        vault_path = Path(env.vault_root).expanduser()
        if vault_path.exists():
            errors = validate_vault(vault_path)
            if errors:
                checks.append(_check("vault", "warning", tr.t("doctor.check.vault.invalid"), details=errors))
            else:
                checks.append(_check("vault", "ok", tr.t("doctor.check.vault.valid", vault_path=vault_path)))
        else:
            checks.append(_check("vault", "warning", tr.t("doctor.check.vault.missing_path", vault_path=vault_path)))
    else:
        checks.append(_check("vault", "warning", tr.t("doctor.check.vault.unconfigured")))

    if env.provider:
        checks.append(_check("provider", "ok", tr.t("doctor.check.provider.ok", provider=env.provider)))
    else:
        checks.append(_check("provider", "warning", tr.t("doctor.check.provider.missing")))

    if env.provider == "anthropic":
        status = "ok" if _env_var("ANTHROPIC_API_KEY") else "warning"
        checks.append(
            _check(
                "provider_key",
                status,
                tr.t("doctor.check.provider_key.anthropic.ok")
                if status == "ok"
                else tr.t("doctor.check.provider_key.anthropic.missing"),
            )
        )
    elif env.provider == "openai":
        status = "ok" if _env_var("OPENAI_API_KEY") else "warning"
        checks.append(
            _check(
                "provider_key",
                status,
                tr.t("doctor.check.provider_key.openai.ok")
                if status == "ok"
                else tr.t("doctor.check.provider_key.openai.missing"),
            )
        )
    elif env.provider in {"lmstudio", "ollama"}:
        checks.append(_check("provider_key", "ok", tr.t("doctor.check.provider_key.local", provider=env.provider)))

    overall = "ok"
    if any(check["status"] == "warning" for check in checks):
        overall = "warning"

    return {
        "product": tr.t("common.product_name"),
        "locale": env.language_policy.interface_language,
        "language_policy": {
            "interface_language": env.language_policy.interface_language,
            "user_command_language": env.language_policy.user_command_language,
            "internal_system_language": env.language_policy.internal_system_language,
            "project_default_language": env.language_policy.project_default_language,
            "mixed_language_allowed": env.language_policy.mixed_language_allowed,
        },
        "overall": overall,
        "checks": checks,
        "recommended_next_step": _recommended_next_step(checks, tr),
    }


def format_doctor_report(report: dict) -> str:
    tr = get_translator(report.get("locale"))
    lines = [tr.t("doctor.title"), tr.t("doctor.overall", overall=report["overall"])]
    for check in report["checks"]:
        lines.append(f"- [{check['status']}] {check['name']}: {check['message']}")
        for detail in check.get("details", []):
            lines.append(f"  {detail}")
    lines.append(tr.t("doctor.next_step", next_step=report["recommended_next_step"]))
    return "\n".join(lines)


def _check(name: str, status: str, message: str, *, details: list[str] | None = None) -> dict:
    return {"name": name, "status": status, "message": message, "details": details or []}


def _recommended_next_step(checks: list[dict], tr) -> str:
    if any(check["name"] == "vault" and check["status"] != "ok" for check in checks):
        return tr.t("doctor.next_step.vault")
    if any(check["name"] == "provider" and check["status"] != "ok" for check in checks):
        return tr.t("doctor.next_step.provider")
    return tr.t("doctor.next_step.ready")


def _env_var(name: str) -> str | None:
    from os import environ

    value = environ.get(name, "").strip()
    return value or None
