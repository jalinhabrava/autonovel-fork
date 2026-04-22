from __future__ import annotations

import shutil
import subprocess
import json
from dataclasses import dataclass, field
from pathlib import Path

from providers.text_provider import get_text_provider_config_error
from textifai.bootstrap.source_reader import build_source_document_inventory, discover_importable_source_paths
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.structured_bootstrap_v1 import NovelBootstrapV1Config, run_structured_bootstrap_v1
from textifai.obsidian.json_import import import_json_to_vault
from textifai.obsidian.readiness import ObsidianOperationalReadiness, evaluate_obsidian_operational_readiness
from textifai.runtime_config import load_runtime_environment, synchronize_runtime_environment
from vault.bootstrap import bootstrap_vault, validate_vault


DEFAULT_BRIDGE_PLUGIN_ID = "textifai-bridge"


@dataclass(frozen=True)
class ObsidianProjectSetupConfig:
    vault_root: str
    mode: str
    project_title: str | None = None
    source_root: str | None = None
    primary_language: str | None = None
    working_languages: list[str] = field(default_factory=list)
    install_bridge_plugin: bool = True
    build_bridge_plugin: bool = False
    plugin_repo_root: str | None = None
    importer_preference: str = "textifai_bootstrap_staging"

    def __post_init__(self) -> None:
        if self.mode not in {"existing_material", "new_project"}:
            raise ValueError("mode must be 'existing_material' or 'new_project'")
        if self.importer_preference not in {"textifai_bootstrap_staging", "obsidian_importer_manual_if_markdown"}:
            raise ValueError("Unsupported importer_preference")


@dataclass(frozen=True)
class ObsidianPluginInstallStatus:
    plugin_repo_root: str
    plugin_id: str
    build_attempted: bool
    build_succeeded: bool
    install_attempted: bool
    install_succeeded: bool
    install_path: str | None = None
    built_main_js: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ObsidianProjectSetupResult:
    mode: str
    vault_root: str
    vault_created: bool
    vault_ready: bool
    bootstrap_warnings: list[str] = field(default_factory=list)
    bootstrap_written_drafts: list[str] = field(default_factory=list)
    import_strategy_used: str = "none"
    official_obsidian_importer_available: bool = True
    official_obsidian_importer_used: bool = False
    official_obsidian_importer_reason: str | None = None
    plugin_status: ObsidianPluginInstallStatus | None = None
    readiness: ObsidianOperationalReadiness | None = None
    vaerl_index_entries: int = 0
    notes: list[str] = field(default_factory=list)
    source_files_considered: list[str] = field(default_factory=list)
    bootstrap_auto_promoted_paths: list[str] = field(default_factory=list)
    bootstrap_pending_candidates: list[str] = field(default_factory=list)
    bootstrap_primary_composed_paths: list[str] = field(default_factory=list)
    bootstrap_story_chapter_paths: list[str] = field(default_factory=list)
    bootstrap_story_summary_paths: list[str] = field(default_factory=list)
    bootstrap_audit_path: str | None = None
    bootstrap_progress_log_path: str | None = None
    source_extraction_audit_path: str | None = None


def prepare_obsidian_project(
    config: ObsidianProjectSetupConfig,
    *,
    repo_root: str | Path | None = None,
) -> ObsidianProjectSetupResult:
    vault_root = Path(config.vault_root).expanduser().resolve()
    repo_path = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[2]
    plugin_repo_root = (
        Path(config.plugin_repo_root).expanduser().resolve()
        if config.plugin_repo_root is not None
        else repo_path / "integrations" / "obsidian-textifai-bridge"
    )
    source_root_path = (
        Path(config.source_root).expanduser().resolve()
        if config.mode == "existing_material" and config.source_root is not None
        else (vault_root if config.mode == "existing_material" else None)
    )
    preexisting_source_paths = (
        discover_importable_source_paths(source_root_path)
        if source_root_path is not None
        else []
    )

    vault_created = False
    written_drafts: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    import_strategy = "none"
    importer_reason = None
    promoted_paths: list[str] = []
    pending_candidates: list[str] = []
    composed_paths: list[str] = []
    story_chapter_paths: list[str] = []
    story_summary_paths: list[str] = []
    bootstrap_audit_path: str | None = None
    source_extraction_audit_path: str | None = None
    progress_log_path: str | None = None
    progress_log_path = _bootstrap_progress_log_path(vault_root)

    if config.mode == "new_project":
        if not vault_root.exists() or not any(vault_root.iterdir()):
            bootstrap_vault(
                vault_root,
                title=config.project_title or "TextifAI Project",
                force=not vault_root.exists(),
                allow_existing_content=True,
            )
            vault_created = True
        elif validate_vault(vault_root):
            bootstrap_vault(
                vault_root,
                title=config.project_title or "TextifAI Project",
                allow_existing_content=True,
            )
            notes.append("Existing folder was converted into a TextifAI vault without deleting prior material.")
        notes.append("Vault initialized for a new project.")
    else:
        source_root = source_root_path or vault_root
        if not source_root.exists():
            raise FileNotFoundError(f"Source root does not exist: {source_root}")
        if not vault_root.exists() or not any(vault_root.iterdir()):
            bootstrap_vault(
                vault_root,
                title=config.project_title or source_root.name or "TextifAI Project",
                force=not vault_root.exists(),
                allow_existing_content=True,
            )
            vault_created = True
        elif validate_vault(vault_root):
            bootstrap_vault(
                vault_root,
                title=config.project_title or source_root.name or "TextifAI Project",
                allow_existing_content=True,
            )
            notes.append("Existing folder was converted into a TextifAI vault without disturbing prior material.")
        inventory = build_source_document_inventory(
            source_root,
            explicit_paths=[str(path) for path in preexisting_source_paths] or None,
            progress_log_path=progress_log_path,
        )
        source_extraction_audit_path = _write_source_extraction_audit(
            vault_root=vault_root,
            inventory=inventory,
        )
        structured_result = _run_structured_bootstrap_pipeline(
            vault_root=vault_root,
            inventory=inventory,
            repo_path=repo_path,
            progress_log_path=progress_log_path,
        )
        if structured_result is not None:
            import_strategy = "structured_bootstrap_v1_json_import"
            warnings.extend(list(structured_result.warnings))
            import_audit = import_json_to_vault(
                source_json=Path(structured_result.obsidian_import_path),
                vault_root=vault_root,
            )
            composed_paths = list(import_audit.get("primary_paths", []))
            story_chapter_paths = list(import_audit.get("chapter_paths", []))
            story_summary_paths = list(import_audit.get("summary_paths", []))
            bootstrap_audit_path = str(vault_root / "99_System" / "json_import_audit.json")
            notes.append("Existing source material was normalized through the chapter-first JSON bootstrap pipeline.")
            notes.append(f"Global normalization source: {structured_result.source_document}")
            if composed_paths:
                notes.append(f"Imported {len(composed_paths)} primary notes from normalized entity canon.")
            if story_chapter_paths:
                notes.append(f"Wrote {len(story_chapter_paths)} chapter notes from structured chapter outputs.")
            if story_summary_paths:
                notes.append(f"Wrote {len(story_summary_paths)} chapter summaries from structured chapter outputs.")
            _append_bootstrap_progress(
                progress_log_path,
                phase="bootstrap",
                event="structured_bootstrap_imported",
                chapter_count=structured_result.chapter_count,
                primary_count=len(composed_paths),
                summary_count=len(story_summary_paths),
            )
        else:
            import_strategy = "structured_bootstrap_v1_unavailable"
            warnings.append("structured_bootstrap_v1_failed")
            notes.append("Structured bootstrap v1 did not complete, and the legacy staging fallback is now archived and disabled.")
            _append_bootstrap_progress(
                progress_log_path,
                phase="bootstrap",
                event="structured_bootstrap_unavailable",
                source_file_count=len(preexisting_source_paths),
            )
            importer_reason = "Legacy staging fallback archived; rerun with structured bootstrap settings or inspect model plan audit."

    plugin_status = None
    if config.install_bridge_plugin:
        plugin_status = ensure_obsidian_bridge_plugin(
            vault_root=vault_root,
            plugin_repo_root=plugin_repo_root,
            build_plugin=config.build_bridge_plugin,
        )

    readiness = evaluate_obsidian_operational_readiness(vault_root)
    index_entries = 0
    if readiness.can_query_vaerl:
        from textifai.vaerl.index import build_vault_index

        index_entries = len(build_vault_index(vault_path=vault_root))

    return ObsidianProjectSetupResult(
        mode=config.mode,
        vault_root=str(vault_root),
        vault_created=vault_created,
        vault_ready=not validate_vault(vault_root),
        bootstrap_warnings=warnings,
        bootstrap_written_drafts=written_drafts,
        import_strategy_used=import_strategy,
        official_obsidian_importer_available=True,
        official_obsidian_importer_used=False,
        official_obsidian_importer_reason=importer_reason,
        plugin_status=plugin_status,
        readiness=readiness,
        vaerl_index_entries=index_entries,
        notes=notes,
        source_files_considered=[str(path) for path in preexisting_source_paths],
        bootstrap_auto_promoted_paths=promoted_paths,
        bootstrap_pending_candidates=pending_candidates,
        bootstrap_primary_composed_paths=composed_paths,
        bootstrap_story_chapter_paths=story_chapter_paths,
        bootstrap_story_summary_paths=story_summary_paths,
        bootstrap_audit_path=bootstrap_audit_path,
        bootstrap_progress_log_path=progress_log_path,
        source_extraction_audit_path=source_extraction_audit_path,
    )


def _run_structured_bootstrap_pipeline(
    *,
    vault_root: Path,
    inventory,
    repo_path: Path,
    progress_log_path: str | None,
):
    import os

    synchronize_runtime_environment(repo_path)
    provider_name, model = _resolve_bootstrap_provider_and_model(repo_path)
    if not provider_name or not model:
        return None
    if get_text_provider_config_error("bootstrap_global_normalization", provider_name) is not None:
        return None
    if get_text_provider_config_error("bootstrap_chapter_extraction", provider_name) is not None:
        return None
    _append_bootstrap_progress(
        progress_log_path,
        phase="structured_bootstrap_v1",
        event="pipeline_started",
        provider_name=provider_name,
        model=model,
        source_document_count=len(getattr(inventory, "documents", []) or []),
    )
    result = run_structured_bootstrap_v1(
        vault_root,
        inventory=inventory,
        config=NovelBootstrapV1Config(
            provider_name=provider_name,
            model=model,
            max_chapters=_coerce_optional_int(os.environ.get("TEXTIFAI_BOOTSTRAP_MAX_CHAPTERS")),
        ),
        progress_log_path=progress_log_path,
    )
    if result is not None:
        _append_bootstrap_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="pipeline_completed",
            source_document=result.source_document,
            chapter_count=result.chapter_count,
            obsidian_import_path=result.obsidian_import_path,
        )
    return result


def _resolve_bootstrap_provider_and_model(repo_root: Path) -> tuple[str | None, str | None]:
    import os

    env = load_runtime_environment(repo_root)
    provider_name = os.environ.get("AUTONOVEL_BOOTSTRAP_PROVIDER", "").strip() or env.provider
    model = os.environ.get("AUTONOVEL_BOOTSTRAP_MODEL", "").strip() or "auto"
    return provider_name or None, model or None


def _coerce_optional_int(value: str | None) -> int | None:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _bootstrap_progress_log_path(vault_root: Path) -> str:
    return str(vault_root / "99_System" / "bootstrap_progress.jsonl")


def _append_bootstrap_progress(path: str | None, **payload) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_source_extraction_audit(
    *,
    vault_root: Path,
    inventory,
) -> str:
    audit_path = vault_root / "99_System" / "source_extraction_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    source_texts = read_source_documents(inventory)
    per_source = []
    total_chars = 0
    for document in inventory.documents:
        text = source_texts.get(document.source_id, "")
        char_count = len(text)
        word_count = len(text.split())
        total_chars += char_count
        per_source.append(
            {
                "source_id": document.source_id,
                "filename": document.filename,
                "path": document.path,
                "source_format": document.extension,
                "size_bytes": document.size_bytes,
                "dominant_language": document.dominant_language,
                "detected_languages": document.detected_languages,
                "likely_content_kinds": document.likely_content_kinds,
                "extraction_method": document.extraction_method,
                "extraction_warnings": document.extraction_warnings,
                "line_count": document.line_count,
                "extracted_page_count": document.extracted_page_count,
                "extracted_char_count": char_count,
                "extracted_word_count": word_count,
                "notes": document.notes,
                "preview": text[:1200],
            }
        )
    audit_path.write_text(
        json.dumps(
            {
                "source_root": inventory.source_root,
                "total_documents": inventory.total_documents,
                "total_source_bytes": inventory.total_bytes,
                "total_extracted_chars": total_chars,
                "documents": per_source,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(audit_path)


def ensure_obsidian_bridge_plugin(
    *,
    vault_root: str | Path,
    plugin_repo_root: str | Path,
    build_plugin: bool,
) -> ObsidianPluginInstallStatus:
    vault_path = Path(vault_root).expanduser().resolve()
    plugin_root = Path(plugin_repo_root).expanduser().resolve()
    plugin_id = DEFAULT_BRIDGE_PLUGIN_ID
    build_attempted = False
    build_succeeded = False
    install_attempted = False
    install_succeeded = False
    warnings: list[str] = []

    main_js_path = plugin_root / "main.js"
    manifest_path = plugin_root / "manifest.json"

    if build_plugin:
        build_attempted = True
        try:
            if not (plugin_root / "node_modules").exists():
                _run_npm_command(plugin_root, ["install"])
            _run_npm_command(plugin_root, ["run", "build"])
            build_succeeded = main_js_path.exists()
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            warnings.append(f"bridge_build_failed:{exc}")
            build_succeeded = False

    if not main_js_path.exists():
        warnings.append("bridge_main_js_missing")
        return ObsidianPluginInstallStatus(
            plugin_repo_root=str(plugin_root),
            plugin_id=plugin_id,
            build_attempted=build_attempted,
            build_succeeded=build_succeeded,
            install_attempted=False,
            install_succeeded=False,
            built_main_js=None,
            warnings=warnings,
        )

    install_attempted = True
    install_path = vault_path / ".obsidian" / "plugins" / plugin_id
    install_path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, install_path / "manifest.json")
    shutil.copy2(main_js_path, install_path / "main.js")
    styles_path = plugin_root / "styles.css"
    if styles_path.exists():
        shutil.copy2(styles_path, install_path / "styles.css")
    install_succeeded = True

    return ObsidianPluginInstallStatus(
        plugin_repo_root=str(plugin_root),
        plugin_id=plugin_id,
        build_attempted=build_attempted,
        build_succeeded=build_succeeded or main_js_path.exists(),
        install_attempted=install_attempted,
        install_succeeded=install_succeeded,
        install_path=str(install_path),
        built_main_js=str(main_js_path),
        warnings=warnings,
    )

def _run_npm_command(plugin_root: Path, args: list[str]) -> None:
    primary = ["npm", *args]
    try:
        subprocess.run(primary, cwd=plugin_root, check=True, capture_output=True, text=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError) as primary_exc:
        fallback = ["npx", "-y", "-p", "node@20", "-p", "npm@10", "npm", *args]
        try:
            subprocess.run(fallback, cwd=plugin_root, check=True, capture_output=True, text=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise primary_exc
