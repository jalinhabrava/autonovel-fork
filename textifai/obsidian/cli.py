from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

from textifai.conversation.runtime_bridge import _load_known_characters, render_execution_result
from textifai.author_understanding.prompt_builder import build_author_understanding_prompt
from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.manager import ConversationManager
from textifai.import_review import load_staging_import_bundle
from textifai.import_review.auxiliary_ingestion import AuxiliaryDocumentInput
from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay
from textifai.obsidian import evaluate_obsidian_operational_readiness, open_obsidian_source, validate_obsidian_snapshot
from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project
from textifai.platform_paths import normalize_user_path, suggest_default_vault_root
from textifai.provider_onboarding import (
    ProviderConfiguration,
    ProviderReadiness,
    configure_provider,
    evaluate_provider_readiness,
)
from textifai.runtime_config import load_runtime_environment, synchronize_runtime_environment
from textifai.session import create_session
from textifai.vaerl.invariants import write_semantic_invariants_audit
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
    status_parser.add_argument("--vault-root", required=False, default=None)
    status_parser.add_argument("--skip-provider-probe", action="store_true")

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

    invariants_parser = subparsers.add_parser(
        "validate-vaerl",
        help="Run Phase 1 semantic invariants against a 99_System directory and optional vault.",
    )
    invariants_parser.add_argument("--system-root", required=True, help="99_System directory containing obsidian_import.json.")
    invariants_parser.add_argument("--vault-root", default=None, help="Optional materialized vault root for wikilink/placeholder checks.")
    invariants_parser.add_argument("--required-primary", action="append", default=[], help="Required primary entity name or alias. Can be repeated.")
    invariants_parser.add_argument("--language", default=None, help="Optional WORK_LANGUAGE override. Defaults to obsidian_import.work.language.")
    invariants_parser.add_argument("--min-primary-count", type=int, default=None)
    invariants_parser.add_argument("--max-primary-count", type=int, default=None)
    invariants_parser.add_argument("--max-review-count", type=int, default=None)
    invariants_parser.add_argument("--language-validator", default="heuristic")
    invariants_parser.add_argument("--output", default=None, help="Where to write the audit. Defaults to <system-root>/semantic_invariants_audit.json.")

    replay_parser = subparsers.add_parser(
        "replay-semantic",
        help="Replay entity resolution, cleanup, and import assembly from frozen semantic ingestion artifacts.",
    )
    replay_parser.add_argument("--input-system", required=True, help="Frozen 99_System directory with global_normalization and chapter_outputs.")
    replay_parser.add_argument("--output-root", required=True, help="Output root for replay artifacts.")
    replay_parser.add_argument("--language", default=None, help="Optional WORK_LANGUAGE override. Defaults to work.language.")
    replay_parser.add_argument("--prose-language-validator", default="heuristic")
    replay_parser.add_argument("--prose-language-validation-mode", choices=["strict", "warn"], default="strict")
    _add_replay_auxiliary_args(replay_parser)
    replay_downstream_parser = subparsers.add_parser(
        "replay-downstream",
        help="Alias for replay-semantic: replay downstream semantic compilation from frozen upstream artifacts.",
    )
    replay_downstream_parser.add_argument("--input-system", required=True, help="Frozen 99_System directory with global_normalization and chapter_outputs.")
    replay_downstream_parser.add_argument("--output-root", required=True, help="Output root for replay artifacts.")
    replay_downstream_parser.add_argument("--language", default=None, help="Optional WORK_LANGUAGE override. Defaults to work.language.")
    replay_downstream_parser.add_argument("--prose-language-validator", default="heuristic")
    replay_downstream_parser.add_argument("--prose-language-validation-mode", choices=["strict", "warn"], default="strict")
    _add_replay_auxiliary_args(replay_downstream_parser)

    ask_parser = subparsers.add_parser(
        "ask",
        help="Run an author-facing interaction against the prepared vault.",
    )
    ask_parser.add_argument("--vault-root", default=None)
    ask_parser.add_argument("--text", default=None, help="Question or request to send to TextifAI.")
    ask_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human summary.")
    ask_parser.add_argument(
        "--trace-output",
        default=None,
        help="Optional JSON file path for persisting the full product interaction trace during validation/debugging.",
    )

    provider_parser = subparsers.add_parser(
        "provider",
        help="Inspect provider configuration and connectivity for author-facing flows.",
    )
    provider_parser.add_argument("--skip-connectivity-test", action="store_true")
    provider_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human summary.")

    configure_provider_parser = subparsers.add_parser(
        "configure-provider",
        help="Configure the provider used for author-facing LLM flows.",
    )
    configure_provider_parser.add_argument(
        "--provider-kind",
        choices=["anthropic", "openai", "openai_compatible", "local_openai_compatible", "ollama", "skip"],
        default=None,
    )
    configure_provider_parser.add_argument("--api-base", default=None)
    configure_provider_parser.add_argument("--api-key", default=None)
    configure_provider_parser.add_argument("--model", default=None)
    configure_provider_parser.add_argument("--skip-connectivity-test", action="store_true")
    configure_provider_parser.add_argument("--json", action="store_true")
    return parser


def run_cli(*, argv: list[str] | None = None, repo_root: str | Path) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    known_commands = {
        "start",
        "init",
        "status",
        "inspect",
        "validate-vaerl",
        "replay-semantic",
        "replay-downstream",
        "ask",
        "provider",
        "configure-provider",
    }
    if not raw_argv or raw_argv[0] not in known_commands:
        raw_argv = ["start", *raw_argv]

    parser = build_parser()
    args = parser.parse_args(raw_argv)
    command = args.command or "start"

    if command == "provider":
        payload = asdict(
            evaluate_provider_readiness(
                repo_root,
                run_connectivity_test=not args.skip_connectivity_test,
            )
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            _print_provider_summary(ProviderReadiness(**payload))
        return 0 if payload["author_flows_available"] else 1

    if command == "configure-provider":
        readiness = _configure_provider_from_args(args, repo_root=repo_root)
        if args.json:
            print(json.dumps(asdict(readiness), indent=2, ensure_ascii=False))
        else:
            _print_provider_summary(readiness)
        return 0 if readiness.author_flows_available or readiness.provider_name is None else 1

    if command == "status":
        env = load_runtime_environment(repo_root)
        vault_root = normalize_user_path(args.vault_root) if args.vault_root else (
            normalize_user_path(env.vault_root) if env.vault_root else None
        )
        if vault_root is None:
            print(json.dumps({"error": "vault_root_missing"}, indent=2, ensure_ascii=False))
            return 1
        readiness = evaluate_obsidian_operational_readiness(vault_root)
        provider_readiness = evaluate_provider_readiness(
            repo_root,
            run_connectivity_test=not args.skip_provider_probe,
        )
        payload = {
            **asdict(readiness),
            "vault_readiness": asdict(readiness),
            "provider_readiness": asdict(provider_readiness),
            "author_flows_available": bool(
                provider_readiness.author_flows_available and readiness.can_answer_degraded_contextual
            ),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if command == "inspect":
        payload = _inspect_vault(
            vault_root=normalize_user_path(args.vault_root),
            snapshot_path=args.snapshot_path,
            repo_root=repo_root,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if command == "validate-vaerl":
        system_root = normalize_user_path(args.system_root)
        output_path = normalize_user_path(args.output) if args.output else system_root / "semantic_invariants_audit.json"
        audit = write_semantic_invariants_audit(
            output_path=output_path,
            system_root=system_root,
            vault_root=normalize_user_path(args.vault_root) if args.vault_root else None,
            required_primaries=list(args.required_primary),
            language=args.language,
            min_primary_count=args.min_primary_count,
            max_primary_count=args.max_primary_count,
            max_review_count=args.max_review_count,
            language_validator=args.language_validator,
        )
        print(json.dumps(audit, indent=2, ensure_ascii=False))
        return 0 if audit.get("passed") else 1

    if command in {"replay-semantic", "replay-downstream"}:
        result = run_semantic_ingestion_replay(
            input_system_root=normalize_user_path(args.input_system),
            output_root=normalize_user_path(args.output_root),
            language=args.language,
            prose_language_validator=args.prose_language_validator,
            prose_language_validation_mode=args.prose_language_validation_mode,
            auxiliary_documents=_parse_auxiliary_documents(args),
            auxiliary_provider_name=args.auxiliary_provider,
            auxiliary_model=args.auxiliary_model,
        )
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return 0

    if command == "ask":
        return _run_author_facing_query(
            repo_root=repo_root,
            vault_root=normalize_user_path(args.vault_root) if args.vault_root else None,
            text=args.text,
            emit_json=args.json,
            trace_output=normalize_user_path(args.trace_output) if args.trace_output else None,
        )

    if command == "start":
        config = _interactive_config_from_args(args)
        provider_readiness = _interactive_provider_configuration(repo_root=repo_root)
        result = prepare_obsidian_project(config, repo_root=repo_root)
        if args.json:
            payload = {
                **asdict(result),
                "provider_readiness": asdict(provider_readiness),
            }
            print(
                json.dumps(payload, indent=2, ensure_ascii=False)
            )
        else:
            _print_human_start_summary(result, provider_readiness=provider_readiness)
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


def _add_replay_auxiliary_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--auxiliary-document",
        action="append",
        default=[],
        help="Auxiliary author document to ingest during downstream replay. Can be repeated.",
    )
    parser.add_argument(
        "--auxiliary-hint",
        action="append",
        default=[],
        help="Optional PATH=hint guidance for an auxiliary document. Missing hints fall back to the document title.",
    )
    parser.add_argument(
        "--auxiliary-provider",
        default=None,
        help="Provider for auxiliary document extraction. Defaults to the configured bootstrap provider.",
    )
    parser.add_argument(
        "--auxiliary-model",
        default=None,
        help="Fixed model for auxiliary document extraction.",
    )


def _parse_auxiliary_documents(args: argparse.Namespace) -> list[AuxiliaryDocumentInput]:
    documents = [normalize_user_path(path) for path in (getattr(args, "auxiliary_document", None) or [])]
    hints: dict[str, str] = {}
    for raw_hint in getattr(args, "auxiliary_hint", None) or []:
        if "=" not in raw_hint:
            raise ValueError(f"Invalid --auxiliary-hint value, expected PATH=hint: {raw_hint}")
        raw_path, hint = raw_hint.split("=", 1)
        path = normalize_user_path(raw_path)
        hints[str(path.resolve())] = hint.strip()
    return [
        AuxiliaryDocumentInput(path=str(path), author_hint=hints.get(str(path.resolve()), ""))
        for path in documents
    ]


def _interactive_config_from_args(args: argparse.Namespace) -> ObsidianProjectSetupConfig:
    mode = "existing_material" if (args.source_root or args.use_vault_root_as_source) else None
    if mode is None:
        choice = _prompt(
            "How do you want to start? [0] new project, [1] existing documentation",
            default="1",
        )
        mode = "new_project" if choice.strip() == "0" else "existing_material"

    project_title = args.project_title or _prompt("Project title", default="TextifAI Project")
    vault_root = normalize_user_path(
        args.vault_root or _prompt("Vault location", default=str(suggest_default_vault_root(project_title=project_title)))
    )
    source_root = args.source_root
    use_vault_root_as_source = args.use_vault_root_as_source
    if mode == "existing_material" and not source_root and not use_vault_root_as_source:
        source_choice = _prompt("Is the source documentation already inside that folder? [y/N]", default="n")
        if source_choice.strip().lower() in {"y", "yes"}:
            use_vault_root_as_source = True
        else:
            source_root = _prompt("Source documentation location", default="")

    primary_language = args.primary_language or _prompt("Primary project language", default="en")
    working_languages = list(args.working_language) or [
        item.strip()
        for item in _prompt("Working languages, comma-separated", default=primary_language).split(",")
        if item.strip()
    ]
    build_bridge_plugin = bool(args.build_bridge_plugin)
    if not build_bridge_plugin:
        should_build = _prompt("Build/install the TextifAI Bridge plugin now? [Y/n]", default="y")
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


def _inspect_vault(*, vault_root: Path, snapshot_path: str | None = None, repo_root: str | Path = ".") -> dict:
    provider_readiness = evaluate_provider_readiness(repo_root)
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
        "provider_readiness": asdict(provider_readiness),
        "author_flows_available": bool(provider_readiness.author_flows_available and readiness.can_answer_degraded_contextual),
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
    trace_output: Path | None,
) -> int:
    repo_path = Path(repo_root).resolve()
    synchronize_runtime_environment(repo_path)
    env = load_runtime_environment(repo_path)
    session = create_session(env)
    if vault_root is not None:
        session.vault_path = vault_root
    elif env.vault_root is None:
        session.vault_path = normalize_user_path(
            _prompt("Vault location for this interaction", default=str(suggest_default_vault_root(project_title="TextifAI Project")))
        )
    query_text = text or _prompt("What do you want to ask TextifAI?", default="")
    if not query_text.strip():
        print("No request was provided.")
        return 1
    provider_readiness = evaluate_provider_readiness(repo_path)
    readiness = evaluate_obsidian_operational_readiness(session.vault_path)
    if not provider_readiness.author_flows_available:
        preview = _build_preprovider_pipeline_preview(
            session=session,
            query_text=query_text,
        )
        payload = {
            "trace_metadata": _build_trace_metadata(mode="preview", trace_output=trace_output),
            "vault_root": str(session.vault_path),
            "author_facing_available": False,
            "reason": "provider_not_available",
            "provider_readiness": asdict(provider_readiness),
            "readiness": asdict(readiness),
            "pipeline_trace_preview": preview,
            "message": (
                "Author-facing semantic guidance requires a reachable configured text provider. "
                "Inspect and status still work, but ask cannot provide grounded author guidance until provider readiness is green."
            ),
        }
        _append_ask_trace(session.vault_path, payload)
        _write_trace_artifact(trace_output, payload)
        if emit_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["message"])
        return 1

    manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
    known_characters = _load_known_characters(session.vault_path)
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
            metadata={
                "known_characters": known_characters,
                "allow_live_provider": bool(provider_readiness.author_flows_available),
                "allow_simulated_preview": False,
                "provider_name": session.provider,
            },
        )
    )
    execution = manager.last_execution_result
    rendered_response = turn.author_facing_response
    if not rendered_response and execution is not None:
        rendered_response = render_execution_result(session, execution)
    payload = {
        "trace_metadata": _build_trace_metadata(mode="full", trace_output=trace_output),
        "vault_root": str(session.vault_path),
        "author_facing_available": bool(rendered_response),
        "flow_name": turn.planned_task.flow_name,
        "semantic_response_kind": turn.semantic_response_kind,
        "result_summary": turn.result_summary,
        "author_facing_response": rendered_response,
        "response_generation_ready": turn.response_generation_ready,
        "response_support_summary": turn.response_support_summary,
        "provider_readiness": asdict(provider_readiness),
        "readiness": asdict(readiness),
        "provider_mode": turn.provider_mode,
        "response_generation_mode": turn.response_generation_mode,
        "pipeline_trace": _build_pipeline_trace(
            turn=turn,
            vault_root=session.vault_path,
        ),
    }
    _append_ask_trace(session.vault_path, payload)
    _write_trace_artifact(trace_output, payload)
    if emit_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        readiness = ((turn.response_support_summary or {}).get("obsidian_operational_readiness") or {})
        print(f"Flow: {turn.planned_task.flow_name}")
        print(f"Readiness: {readiness.get('operational_mode')}")
        print("")
        print(rendered_response or turn.result_summary)
    return 0


def _append_ask_trace(vault_root: Path, payload: dict) -> None:
    trace_path = vault_root / "99_System" / "textifai_ask_trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_trace_artifact(trace_output: Path | None, payload: dict) -> None:
    if trace_output is None:
        return
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    trace_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_trace_metadata(*, mode: str, trace_output: Path | None) -> dict:
    return {
        "trace_schema_version": "1.0",
        "trace_mode": mode,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "trace_output_path": str(trace_output) if trace_output is not None else None,
    }


def _build_pipeline_trace(*, turn, vault_root: Path) -> dict:
    metadata = dict(turn.recognized_intent.metadata or {})
    author_understanding = metadata.get("author_understanding")
    source = open_obsidian_source(vault_root)
    response_support = dict(turn.response_support_summary or {})
    semantic_payload = None
    semantic_result = None
    if isinstance(author_understanding, dict):
        llm_interpretation = author_understanding.get("llm_interpretation") or {}
        if isinstance(llm_interpretation, dict):
            semantic_payload = ((llm_interpretation.get("raw_payload") or {}).get("_trace"))
            semantic_result = {
                "primary_intent_type": llm_interpretation.get("primary_intent_type"),
                "secondary_intent_types": llm_interpretation.get("secondary_intent_types"),
                "confidence": llm_interpretation.get("confidence"),
                "needs_clarification": llm_interpretation.get("needs_clarification"),
                "clarification_reason": llm_interpretation.get("clarification_reason"),
                "candidate_targets": llm_interpretation.get("candidate_targets"),
                "preferred_target": llm_interpretation.get("preferred_target"),
                "entity_hints": llm_interpretation.get("entity_hints"),
                "provider_name": llm_interpretation.get("provider_name"),
                "model": llm_interpretation.get("model"),
            }
    return {
        "deterministic_parse": {
            "recognized_intent_name": turn.recognized_intent.intent_name,
            "target_type": turn.recognized_intent.target_type,
            "target_id": turn.recognized_intent.target_id,
            "signals": list(turn.recognized_intent.signals),
            "requires_target": turn.recognized_intent.requires_target,
        },
        "semantic_interpretation_prompt": semantic_payload,
        "semantic_interpretation_result": semantic_result,
        "grounding": {
            "source_status": asdict(source.status),
            "vaerl_results": metadata.get("vaerl_results"),
            "editorial_intent": metadata.get("editorial_intent"),
            "response_support_summary": response_support,
        },
        "enriched_prompt": turn.anchored_prompt_payload,
        "final_response": {
            "author_facing_response": turn.author_facing_response,
            "provider_mode": turn.provider_mode,
            "response_generation_mode": turn.response_generation_mode,
            "provider_model_used": turn.provider_model_used,
            "response_generation_ready": turn.response_generation_ready,
        },
    }


def _build_preprovider_pipeline_preview(*, session, query_text: str) -> dict:
    manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
    request = ConversationRequest(
        raw_text=query_text,
        source="user",
        mode="normal",
        interface_language=session.language_policy.interface_language,
        user_command_language=session.language_policy.user_command_language,
        internal_system_language=session.language_policy.internal_system_language,
        project_default_language=session.language_policy.project_default_language,
        mixed_language_allowed=session.language_policy.mixed_language_allowed,
        explanation_language=session.language_policy.interface_language,
        metadata={
            "known_characters": _load_known_characters(session.vault_path),
            "allow_live_provider": False,
            "allow_simulated_preview": False,
            "provider_name": session.provider,
        },
    )
    if manager.state is None:
        from textifai.conversation.state import create_conversation_state

        manager.state = create_conversation_state(
            explanation_language=request.explanation_language or request.interface_language,
            artifact_target_language=request.artifact_target_language,
        )
    rule_intent = manager.recognizer.recognize(request, manager.state)
    prompt = build_author_understanding_prompt(
        request=request,
        rule_intent=rule_intent,
        narrative_signals=rule_intent.narrative_signals,
        entity_results=[],
        state=manager.state,
    )
    return {
        "deterministic_parse": {
            "recognized_intent_name": rule_intent.intent_name,
            "target_type": rule_intent.target_type,
            "target_id": rule_intent.target_id,
            "signals": list(rule_intent.signals),
            "requires_target": rule_intent.requires_target,
        },
        "semantic_interpretation_prompt": {
            "prompt_version": prompt.prompt_version,
            "system_prompt": prompt.system_prompt,
            "user_payload": prompt.user_payload,
            "required_output_schema": prompt.required_output_schema,
            "catalogs": prompt.catalogs,
        },
        "grounding": {
            "status": "not_started",
            "reason": "provider_unavailable_before_semantic_interpretation",
        },
        "enriched_prompt": None,
        "final_response": None,
    }


def _prompt(message: str, *, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{message}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def _print_human_start_summary(result, *, provider_readiness) -> None:
    print(f"Vault ready: {result.vault_root}")
    print(f"Mode: {result.mode}")
    print(f"Current readiness: {result.readiness.operational_mode if result.readiness else 'unknown'}")
    print(f"Provider mode: {provider_readiness.provider_mode}")
    print(f"Provider ready for author flows: {'yes' if provider_readiness.author_flows_available else 'no'}")
    if result.plugin_status and result.plugin_status.install_succeeded:
        print("TextifAI Bridge was installed into the vault.")
    if result.bootstrap_written_drafts:
        print(f"Imported staging drafts: {len(result.bootstrap_written_drafts)}")
    if result.bootstrap_auto_promoted_paths:
        print(f"Auto-promoted canonical notes: {len(result.bootstrap_auto_promoted_paths)}")
    print("")
    print("Next step in Obsidian:")
    print("1. Open Obsidian Desktop and choose 'Open folder as vault'.")
    print("2. Enable 'TextifAI Bridge' in Community plugins.")
    print("3. Wait a few seconds; the plugin auto-exports snapshots on startup and after note changes.")
    print("4. If you need a force refresh, run 'Export TextifAI context snapshot' from the command palette.")
    print("")
    if not provider_readiness.author_flows_available:
        print("Provider status:")
        print("1. Run `textifai provider` to inspect the current provider configuration.")
        print("2. Run `textifai configure-provider` if you still need to configure or fix connectivity.")
        print("")
    print("Then validate with:")
    print(f"uv run python scripts/textifai_obsidian.py inspect --vault-root {result.vault_root}")
    print("And for the first author-facing interaction:")
    print(f"uv run python scripts/textifai.py ask --vault-root {result.vault_root}")


def _interactive_provider_configuration(*, repo_root: str | Path):
    choice = _prompt(
        "Select an LLM provider [1] Anthropic, [2] OpenAI, [3] remote OpenAI-compatible, [4] local OpenAI-compatible, [5] Ollama, [6] skip for now",
        default="5",
    ).strip()
    mapped = {
        "1": "anthropic",
        "2": "openai",
        "3": "openai_compatible",
        "4": "local_openai_compatible",
        "5": "ollama",
        "6": "skip",
    }.get(choice, choice or "skip")
    configuration = _build_provider_configuration(
        provider_kind=mapped,
        api_base=None,
        api_key=None,
        model=None,
        interactive=True,
    )
    return configure_provider(base_dir=repo_root, configuration=configuration, test_connectivity=True)


def _configure_provider_from_args(args: argparse.Namespace, *, repo_root: str | Path):
    configuration = _build_provider_configuration(
        provider_kind=args.provider_kind,
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
        interactive=args.provider_kind is None,
    )
    return configure_provider(
        base_dir=repo_root,
        configuration=configuration,
        test_connectivity=not args.skip_connectivity_test,
    )


def _build_provider_configuration(
    *,
    provider_kind: str | None,
    api_base: str | None,
    api_key: str | None,
    model: str | None,
    interactive: bool,
) -> ProviderConfiguration:
    kind = provider_kind or "skip"
    if interactive:
        kind = _prompt(
            "Provider kind [anthropic|openai|openai_compatible|local_openai_compatible|ollama|skip]",
            default="skip",
        ).strip() or "skip"
    if kind == "skip":
        return ProviderConfiguration(provider_choice="skip")
    if kind == "anthropic":
        return ProviderConfiguration(
            provider_choice="anthropic",
            provider_name="anthropic",
            api_base=api_base or (_prompt("Anthropic API base URL", default="https://api.anthropic.com") if interactive else "https://api.anthropic.com"),
            api_key=api_key or (_prompt("Anthropic API key", default="") if interactive else ""),
            model=model or (_prompt("Anthropic model", default="claude-sonnet-4-6") if interactive else None),
        )
    if kind == "openai":
        return ProviderConfiguration(
            provider_choice="openai",
            provider_name="openai",
            api_base=api_base or (_prompt("OpenAI API base URL", default="https://api.openai.com/v1") if interactive else "https://api.openai.com/v1"),
            api_key=api_key or (_prompt("OpenAI API key", default="") if interactive else ""),
            model=model or (_prompt("OpenAI model", default="gpt-4.1-mini") if interactive else None),
        )
    if kind == "openai_compatible":
        return ProviderConfiguration(
            provider_choice="openai_compatible",
            provider_name="openai_compatible",
            api_base=api_base or (_prompt("OpenAI-compatible base URL", default="https://api.openai.com/v1") if interactive else None),
            api_key=api_key or (_prompt("OpenAI-compatible API key", default="") if interactive else ""),
            model=model or (_prompt("Model name", default="gpt-4.1-mini") if interactive else None),
        )
    if kind == "local_openai_compatible":
        return ProviderConfiguration(
            provider_choice="local_openai_compatible",
            provider_name="openai_compatible",
            api_base=api_base or (_prompt("Local OpenAI-compatible base URL", default="http://localhost:1234/v1") if interactive else "http://localhost:1234/v1"),
            api_key=api_key or (_prompt("Local server API key (optional)", default="") if interactive else ""),
            model=model or (_prompt("Local model name", default="local-model") if interactive else None),
        )
    if kind == "ollama":
        return ProviderConfiguration(
            provider_choice="ollama",
            provider_name="ollama",
            api_base=api_base or (_prompt("Ollama OpenAI-compatible base URL", default="http://localhost:11434/v1") if interactive else "http://localhost:11434/v1"),
            api_key=api_key or (_prompt("Ollama API key (optional)", default="") if interactive else ""),
            model=model or (_prompt("Ollama model", default="llama3.1") if interactive else None),
        )
    raise ValueError(f"Unsupported provider kind: {kind}")


def _print_provider_summary(readiness) -> None:
    print(f"Provider: {readiness.provider_name or 'not configured'}")
    print(f"Mode: {readiness.provider_mode}")
    print(f"Model: {readiness.provider_model or 'unknown'}")
    print(f"Configured: {'yes' if readiness.provider_configured else 'no'}")
    print(f"Reachable: {'yes' if readiness.provider_reachable else 'no'}")
    print(f"Author flows available: {'yes' if readiness.author_flows_available else 'no'}")
    if readiness.configuration_error:
        print(f"Configuration error: {readiness.configuration_error}")
    if readiness.connectivity_error:
        print(f"Connectivity error: {readiness.connectivity_error}")
