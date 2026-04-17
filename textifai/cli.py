from __future__ import annotations

import argparse
import json
from pathlib import Path

from textifai import PRODUCT_NAME
from textifai.doctor import format_doctor_report, run_doctor
from textifai.onboarding import run_onboarding
from textifai.runtime_config import load_runtime_environment, runtime_banner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="textifai", description=f"{PRODUCT_NAME} product runtime")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="Run guided setup for TextifAI")
    setup_parser.add_argument("--base-dir", default=".", help="Base project directory")
    setup_parser.add_argument("--json", action="store_true", help="Print machine-readable setup summary")

    chat_parser = subparsers.add_parser("chat", help="Enter the TextifAI product runtime")
    chat_parser.add_argument("--base-dir", default=".", help="Base project directory")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the basic TextifAI runtime environment")
    doctor_parser.add_argument("--base-dir", default=".", help="Base project directory")
    doctor_parser.add_argument("--json", action="store_true", help="Print doctor report as JSON")

    args = parser.parse_args(argv)
    command = args.command or "chat"

    if command == "setup":
        summary = run_onboarding(base_dir=args.base_dir)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 0

    if command == "doctor":
        report = run_doctor(base_dir=args.base_dir)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(format_doctor_report(report))
        return 0 if report["overall"] == "ok" else 1

    if command == "chat":
        return _run_chat_entry(args.base_dir)

    return 0


def _run_chat_entry(base_dir: str | Path) -> int:
    env = load_runtime_environment(base_dir)
    print(runtime_banner())
    if not _is_environment_ready(env):
        print("TextifAI needs a valid vault-backed environment before chat can start.")
        summary = run_onboarding(base_dir=base_dir)
        print(json.dumps(summary, indent=2))
        print("TextifAI environment is ready. The full interactive shell will arrive in the next runtime block.")
        return 0

    print(f"Vault: {env.vault_root}")
    print(f"Provider: {env.provider or 'not configured'}")
    print("TextifAI chat entry is ready. The full interactive shell lands in the next runtime block.")
    print("For now, use `textifai doctor` to validate the environment or continue with the next runtime phase.")
    return 0


def _is_environment_ready(env) -> bool:
    return env.backend == "vault" and bool(env.vault_root)
