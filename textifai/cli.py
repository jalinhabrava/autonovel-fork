from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from textifai import PRODUCT_NAME
from textifai.doctor import format_doctor_report, run_doctor
from textifai.obsidian.cli import run_cli as run_obsidian_cli
from textifai.provider_onboarding import evaluate_provider_readiness
from textifai.runtime_config import load_runtime_environment, runtime_banner, synchronize_runtime_environment
from textifai.session import create_session
from textifai.shell import run_shell


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv:
        return run_obsidian_cli(argv=["start"], repo_root=".")

    if raw_argv[0] in {"start", "init", "status", "inspect", "ask", "provider", "configure-provider"}:
        return run_obsidian_cli(argv=raw_argv, repo_root=".")

    parser = argparse.ArgumentParser(prog="textifai", description=f"{PRODUCT_NAME} product runtime")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Run the guided TextifAI setup wizard.")
    start_parser.add_argument("--json", action="store_true", help="Emit machine-readable setup output.")

    init_parser = subparsers.add_parser("init", help="Initialize a vault or import existing documentation.")
    init_parser.add_argument("passthrough", nargs="*")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect vault readiness, snapshot state, and VaERL.")
    inspect_parser.add_argument("passthrough", nargs="*")

    ask_parser = subparsers.add_parser("ask", help="Run a single author-facing query against the prepared vault.")
    ask_parser.add_argument("passthrough", nargs="*")

    provider_parser = subparsers.add_parser("provider", help="Inspect the configured LLM provider.")
    provider_parser.add_argument("passthrough", nargs="*")

    configure_provider_parser = subparsers.add_parser("configure-provider", help="Configure the LLM provider.")
    configure_provider_parser.add_argument("passthrough", nargs="*")

    chat_parser = subparsers.add_parser("chat", help="Enter the interactive TextifAI shell.")
    chat_parser.add_argument("--base-dir", default=".", help="Base project directory")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the local TextifAI runtime environment.")
    doctor_parser.add_argument("--base-dir", default=".", help="Base project directory")
    doctor_parser.add_argument("--json", action="store_true", help="Print doctor report as JSON")

    args = parser.parse_args(raw_argv)
    command = args.command or "start"

    if command in {"start", "init", "inspect", "ask", "status", "provider", "configure-provider"}:
        return run_obsidian_cli(argv=raw_argv, repo_root=".")
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
    synchronize_runtime_environment(base_dir)
    env = load_runtime_environment(base_dir)
    if not _is_environment_ready(env):
        print(runtime_banner(env.locale))
        print("The runtime is not configured yet. Launching the setup wizard.")
        run_obsidian_cli(argv=["start"], repo_root=base_dir)
        env = load_runtime_environment(base_dir)
    provider_readiness = evaluate_provider_readiness(base_dir)
    if not provider_readiness.author_flows_available:
        print("Author-facing chat requires a reachable configured LLM provider. Launching provider setup.")
        run_obsidian_cli(argv=["configure-provider"], repo_root=base_dir)
        provider_readiness = evaluate_provider_readiness(base_dir)
        if not provider_readiness.author_flows_available:
            print("Provider setup is still incomplete. Chat is unavailable until provider readiness is green.")
            return 1
        synchronize_runtime_environment(base_dir)
        env = load_runtime_environment(base_dir)
    session = create_session(env)
    return run_shell(session)


def _is_environment_ready(env) -> bool:
    return env.backend == "vault" and bool(env.vault_root)
