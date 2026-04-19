from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from textifai.obsidian import evaluate_obsidian_operational_readiness, open_obsidian_source, validate_obsidian_snapshot
from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project
from textifai.vaerl.index import build_vault_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TextifAI + Obsidian operational commands.")
    subparsers = parser.add_subparsers(dest="command", required=False)

    start_parser = subparsers.add_parser("start", help="Interactive TextifAI onboarding for Obsidian.")
    _add_init_like_args(start_parser)
    start_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human summary.")

    init_parser = subparsers.add_parser("init", help="Initialize a new project vault or import existing material.")
    _add_init_like_args(init_parser)

    status_parser = subparsers.add_parser("status", help="Inspect operational readiness for a vault.")
    status_parser.add_argument("--vault-root", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect snapshot, readiness, and VaERL indexing for a vault.",
    )
    inspect_parser.add_argument("--vault-root", required=True)
    inspect_parser.add_argument(
        "--snapshot-path",
        default=None,
        help="Optional snapshot path override. Defaults to the bridge snapshot candidates inside the vault.",
    )
    return parser


def run_cli(*, argv: list[str] | None = None, repo_root: str | Path) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    known_commands = {"start", "init", "status", "inspect"}
    if not raw_argv or raw_argv[0] not in known_commands:
        raw_argv = ["start", *raw_argv]

    parser = build_parser()
    args = parser.parse_args(raw_argv)
    command = args.command or "start"

    if command == "status":
        readiness = evaluate_obsidian_operational_readiness(_normalize_user_path(args.vault_root))
        print(json.dumps(asdict(readiness), indent=2, ensure_ascii=False))
        return 0

    if command == "inspect":
        vault_root = _normalize_user_path(args.vault_root)
        readiness = evaluate_obsidian_operational_readiness(vault_root)
        source = open_obsidian_source(vault_root, snapshot_path=args.snapshot_path)
        snapshot_validation = None
        if source.status.snapshot_path is not None:
            snapshot_validation = validate_obsidian_snapshot(Path(source.status.snapshot_path))
        entries = []
        if readiness.can_query_vaerl:
            entries = build_vault_index(vault_path=vault_root)
        payload = {
            "vault_root": str(vault_root),
            "readiness": asdict(readiness),
            "source_status": asdict(source.status),
            "snapshot_validation": asdict(snapshot_validation.status) if snapshot_validation is not None else None,
            "source_note_count": len(source.reader.list_notes()),
            "vaerl_index_entries": len(entries),
            "vaerl_artifact_types": sorted({entry.artifact_type for entry in entries}),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if command == "start":
        config = _interactive_config_from_args(args)
        result = prepare_obsidian_project(config, repo_root=repo_root)
        if args.json:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        else:
            _print_human_start_summary(result)
        return 0

    mode = "existing_material" if (args.source_root or args.use_vault_root_as_source) else "new_project"
    result = prepare_obsidian_project(
        ObsidianProjectSetupConfig(
            vault_root=str(_normalize_user_path(args.vault_root)),
            mode=mode,
            project_title=args.project_title,
            source_root=str(_normalize_user_path(args.source_root)) if args.source_root else (
                str(_normalize_user_path(args.vault_root)) if args.use_vault_root_as_source else None
            ),
            primary_language=args.primary_language,
            working_languages=list(args.working_language),
            install_bridge_plugin=not args.skip_plugin_install,
            build_bridge_plugin=args.build_bridge_plugin,
            plugin_repo_root=args.plugin_repo_root,
            importer_preference=args.importer_preference,
        ),
        repo_root=repo_root,
    )
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


def _add_init_like_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault-root", default=None)
    parser.add_argument("--project-title", default=None)
    parser.add_argument("--source-root", default=None, help="If present, imports existing material.")
    parser.add_argument(
        "--use-vault-root-as-source",
        action="store_true",
        help="Treat the target folder itself as existing author material to ingest while converting it into a vault.",
    )
    parser.add_argument("--primary-language", default=None)
    parser.add_argument("--working-language", action="append", default=[])
    parser.add_argument("--build-bridge-plugin", action="store_true")
    parser.add_argument("--skip-plugin-install", action="store_true")
    parser.add_argument("--plugin-repo-root", default=None)
    parser.add_argument(
        "--importer-preference",
        choices=["textifai_bootstrap_staging", "obsidian_importer_manual_if_markdown"],
        default="textifai_bootstrap_staging",
    )


def _interactive_config_from_args(args: argparse.Namespace) -> ObsidianProjectSetupConfig:
    mode = "existing_material" if (args.source_root or args.use_vault_root_as_source) else None
    if mode is None:
        choice = _prompt(
            "Como quieres empezar? [0] proyecto nuevo, [1] documentacion previa",
            default="1",
        )
        mode = "new_project" if choice.strip() == "0" else "existing_material"

    project_title = args.project_title or _prompt("Nombre del proyecto", default="TextifAI Project")
    vault_root = _normalize_user_path(
        args.vault_root or _prompt("Ruta del vault (WSL o Windows)", default="")
    )
    source_root = args.source_root
    use_vault_root_as_source = args.use_vault_root_as_source
    if mode == "existing_material" and not source_root and not use_vault_root_as_source:
        source_choice = _prompt(
            "La documentacion ya esta dentro de esa carpeta? [s/N]",
            default="n",
        )
        if source_choice.strip().lower() in {"s", "si", "sí", "y", "yes"}:
            use_vault_root_as_source = True
        else:
            source_root = _prompt("Ruta de la documentacion fuente", default="")

    primary_language = args.primary_language or _prompt("Idioma principal", default="es")
    working_languages = list(args.working_language) or [
        item.strip()
        for item in _prompt("Idiomas de trabajo separados por comas", default=f"{primary_language},ja").split(",")
        if item.strip()
    ]
    build_bridge_plugin = bool(args.build_bridge_plugin)
    if not build_bridge_plugin:
        should_build = _prompt("Compilar/instalar el plugin bridge ahora? [S/n]", default="s")
        build_bridge_plugin = should_build.strip().lower() not in {"n", "no"}

    normalized_source_root = None
    if source_root:
        normalized_source_root = str(_normalize_user_path(source_root))
    elif use_vault_root_as_source:
        normalized_source_root = str(vault_root)

    return ObsidianProjectSetupConfig(
        vault_root=str(vault_root),
        mode=mode,
        project_title=project_title,
        source_root=normalized_source_root,
        primary_language=primary_language,
        working_languages=working_languages,
        install_bridge_plugin=not args.skip_plugin_install,
        build_bridge_plugin=build_bridge_plugin,
        plugin_repo_root=args.plugin_repo_root,
        importer_preference=args.importer_preference,
    )


def _normalize_user_path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value.expanduser().resolve()
    text = str(value).strip()
    if re.match(r"^[A-Za-z]:[\\/]", text):
        win = PureWindowsPath(text)
        drive = win.drive.rstrip(":").lower()
        parts = [part for part in win.parts[1:] if part not in {"\\", "/"}]
        return Path("/mnt") / drive / Path(*parts)
    return Path(text).expanduser().resolve()


def _prompt(message: str, *, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or default


def _print_human_start_summary(result) -> None:
    print(f"Vault listo: {result.vault_root}")
    print(f"Modo: {result.mode}")
    print(f"Readiness actual: {result.readiness.operational_mode if result.readiness else 'unknown'}")
    if result.plugin_status and result.plugin_status.install_succeeded:
        print("Plugin TextifAI Bridge instalado en el vault.")
    if result.bootstrap_written_drafts:
        print(f"Material importado en staging: {len(result.bootstrap_written_drafts)} borradores.")
    print("")
    print("Siguiente paso en Windows:")
    print("1. Abre Obsidian Desktop y usa 'Open folder as vault'.")
    print("2. Activa 'TextifAI Bridge' en Community plugins.")
    print("3. Espera unos segundos; el plugin exporta snapshots automaticamente al arrancar y al cambiar notas.")
    print("4. Si quieres forzarlo, ejecuta 'Export TextifAI context snapshot' desde la paleta.")
    print("")
    print("Luego, desde WSL, valida con:")
    print(f"uv run python scripts/textifai_obsidian.py inspect --vault-root {result.vault_root}")
