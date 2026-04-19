from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.manager import ConversationManager
from textifai.import_review import load_staging_import_bundle
from textifai.obsidian import evaluate_obsidian_operational_readiness, open_obsidian_source, validate_obsidian_snapshot
from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project
from textifai.platform_paths import normalize_user_path, suggest_default_vault_root
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
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
        help="Inspect snapshot, readiness, import state, and VaERL indexing for a vault.",
    )
    inspect_parser.add_argument("--vault-root", required=True)
    inspect_parser.add_argument(
        "--snapshot-path",
        default=None,
        help="Optional snapshot path override. Defaults to the bridge snapshot candidates inside the vault.",
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Run an author-facing interaction against the prepared vault.",
    )
    ask_parser.add_argument("--vault-root", default=None)
    ask_parser.add_argument("--text", default=None, help="Question or request to send to TextifAI.")
    ask_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human summary.")
    return parser


def run_cli(*, argv: list[str] | None = None, repo_root: str | Path) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    known_commands = {"start", "init", "status", "inspect", "ask"}
    if not raw_argv or raw_argv[0] not in known_commands:
        raw_argv = ["start", *raw_argv]

    parser = build_parser()
    args = parser.parse_args(raw_argv)
    command = args.command or "start"

    if command == "status":
        readiness = evaluate_obsidian_operational_readiness(normalize_user_path(args.vault_root))
        print(json.dumps(asdict(readiness), indent=2, ensure_ascii=False))
        return 0

    if command == "inspect":
        payload = _inspect_vault(
            vault_root=normalize_user_path(args.vault_root),
            snapshot_path=args.snapshot_path,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if command == "ask":
        return _run_author_facing_query(
            repo_root=repo_root,
            vault_root=normalize_user_path(args.vault_root) if args.vault_root else None,
            text=args.text,
            emit_json=args.json,
        )

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
            vault_root=str(normalize_user_path(args.vault_root)),
            mode=mode,
            project_title=args.project_title,
            source_root=str(normalize_user_path(args.source_root)) if args.source_root else (
                str(normalize_user_path(args.vault_root)) if args.use_vault_root_as_source else None
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
    vault_root = normalize_user_path(
        args.vault_root or _prompt("Ruta del vault", default=str(suggest_default_vault_root(project_title=project_title)))
    )
    source_root = args.source_root
    use_vault_root_as_source = args.use_vault_root_as_source
    if mode == "existing_material" and not source_root and not use_vault_root_as_source:
        source_choice = _prompt("La documentacion ya esta dentro de esa carpeta? [s/N]", default="n")
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
        normalized_source_root = str(normalize_user_path(source_root))
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


def _inspect_vault(*, vault_root: Path, snapshot_path: str | None = None) -> dict:
    readiness = evaluate_obsidian_operational_readiness(vault_root)
    source = open_obsidian_source(vault_root, snapshot_path=snapshot_path)
    snapshot_validation = None
    if source.status.snapshot_path is not None:
        snapshot_validation = validate_obsidian_snapshot(Path(source.status.snapshot_path))
    notes = source.reader.list_notes()
    entries = build_vault_index(vault_path=vault_root) if readiness.can_query_vaerl else []
    manifest_summary = _latest_manifest_stats(vault_root)
    return {
        "vault_root": str(vault_root),
        "readiness": asdict(readiness),
        "source_status": asdict(source.status),
        "snapshot_validation": asdict(snapshot_validation.status) if snapshot_validation is not None else None,
        "source_note_count": len(notes),
        "raw_fragment_count": manifest_summary.get("raw_fragments"),
        "candidate_artifact_count": sum(
            1 for note in notes if str(note.frontmatter.get("artifact_stage") or "") == "candidate_artifact"
        ),
        "promoted_artifact_count": sum(
            1
            for note in notes
            if str(note.frontmatter.get("artifact_stage") or "") == "promoted_artifact"
            or str(note.frontmatter.get("import_review_state") or "") == "promoted"
        ),
        "staging_note_count": sum(1 for note in notes if "99_Import_Staging" in note.vault_relative_path),
        "canonical_note_count": sum(1 for note in notes if "99_Import_Staging" not in note.vault_relative_path),
        "vaerl_index_entries": len(entries),
        "vaerl_artifact_types": sorted({entry.artifact_type for entry in entries}),
        "semantic_classes": sorted(
            {
                str(note.frontmatter.get("semantic_class"))
                for note in notes
                if note.frontmatter.get("semantic_class")
            }
        ),
        "manifest_summary": manifest_summary,
    }


def _latest_manifest_stats(vault_root: Path) -> dict:
    try:
        bundle = load_staging_import_bundle(vault_root)
    except FileNotFoundError:
        return {}
    coverage = dict(bundle.coverage_summary)
    coverage["draft_count"] = len(bundle.drafts)
    coverage["promotion_eligible_drafts"] = sum(
        1 for draft in bundle.drafts if str(draft.frontmatter.get("promotion_status") or "") == "eligible_for_promotion"
    )
    return coverage


def _run_author_facing_query(
    *,
    repo_root: str | Path,
    vault_root: Path | None,
    text: str | None,
    emit_json: bool,
) -> int:
    repo_path = Path(repo_root).resolve()
    env = load_runtime_environment(repo_path)
    session = create_session(env)
    if vault_root is not None:
        session.vault_path = vault_root
    elif env.vault_root is None:
        session.vault_path = normalize_user_path(
            _prompt("Ruta del vault para esta interacción", default=str(suggest_default_vault_root(project_title="TextifAI Project")))
        )
    query_text = text or _prompt("Que quieres pedirle a TextifAI", default="")
    if not query_text.strip():
        print("No se recibió ninguna petición.")
        return 1

    manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
    turn = manager.handle_request(
        ConversationRequest(
            raw_text=query_text,
            source="user",
            mode="normal",
            interface_language=session.language_policy.interface_language,
            user_command_language=session.language_policy.user_command_language,
            internal_system_language=session.language_policy.internal_system_language,
            project_default_language=session.language_policy.project_default_language,
            mixed_language_allowed=session.language_policy.mixed_language_allowed,
            explanation_language=session.language_policy.interface_language,
            metadata={},
        )
    )
    payload = {
        "vault_root": str(session.vault_path),
        "flow_name": turn.planned_task.flow_name,
        "semantic_response_kind": turn.semantic_response_kind,
        "result_summary": turn.result_summary,
        "author_facing_response": turn.author_facing_response,
        "response_generation_ready": turn.response_generation_ready,
        "response_support_summary": turn.response_support_summary,
        "provider_mode": turn.provider_mode,
        "response_generation_mode": turn.response_generation_mode,
    }
    _append_ask_trace(session.vault_path, payload)
    if emit_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        readiness = ((turn.response_support_summary or {}).get("obsidian_operational_readiness") or {})
        print(f"Flow: {turn.planned_task.flow_name}")
        print(f"Readiness: {readiness.get('operational_mode')}")
        print("")
        print(turn.author_facing_response or turn.result_summary)
    return 0


def _append_ask_trace(vault_root: Path, payload: dict) -> None:
    trace_path = vault_root / "99_System" / "textifai_ask_trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
    if result.bootstrap_auto_promoted_paths:
        print(f"Promoción canónica automática: {len(result.bootstrap_auto_promoted_paths)} notas.")
    print("")
    print("Siguiente paso en Obsidian:")
    print("1. Abre Obsidian Desktop y usa 'Open folder as vault'.")
    print("2. Activa 'TextifAI Bridge' en Community plugins.")
    print("3. Espera unos segundos; el plugin exporta snapshots automáticamente al arrancar y al cambiar notas.")
    print("4. Si quieres forzarlo, ejecuta 'Export TextifAI context snapshot' desde la paleta.")
    print("")
    print("Luego valida con:")
    print(f"uv run python scripts/textifai_obsidian.py inspect --vault-root {result.vault_root}")
    print("Y para la primera interacción real:")
    print(f"uv run python scripts/textifai.py ask --vault-root {result.vault_root}")
