from __future__ import annotations

import hashlib
import shutil
import subprocess
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from providers.text_provider import get_text_provider_config_error
from textifai.bootstrap.source_reader import build_source_document_inventory, discover_importable_source_paths
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.markdown_graph_index import build_author_graph, build_markdown_graph_index
from textifai.import_review.source_structure import write_chapter_manifest
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
        provider_name, model = _resolve_bootstrap_provider_and_model(repo_path)
        semantic_provider_available = bool(
            provider_name
            and model
            and get_text_provider_config_error("bootstrap_global_normalization", provider_name) is None
            and get_text_provider_config_error("bootstrap_chapter_extraction", provider_name) is None
        )
        _append_bootstrap_progress(
            progress_log_path,
            phase="bootstrap",
            event="semantic_provider_available" if semantic_provider_available else "semantic_provider_unavailable",
            provider_name=provider_name,
            model=model,
        )
        structured_result = _run_structured_bootstrap_pipeline(
            vault_root=vault_root,
            inventory=inventory,
            repo_path=repo_path,
            progress_log_path=progress_log_path,
        )
        if structured_result is not None:
            import_strategy = "structured_bootstrap_v1_json_import"
            _append_bootstrap_progress(
                progress_log_path,
                phase="bootstrap",
                event="semantic_bootstrap_started",
                provider_name=provider_name,
                model=model,
                chapter_count=structured_result.chapter_count,
                semantic_status="running",
            )
            warnings.extend(list(structured_result.warnings))
            import_audit = import_json_to_vault(
                source_json=Path(structured_result.obsidian_import_path),
                vault_root=vault_root,
            )
            semantic_package = _finalize_semantic_project_package(
                vault_root=vault_root,
                structured_result=structured_result,
                project_title=config.project_title or source_root.name or "TextifAI Project",
                language=config.primary_language or "es",
                repo_path=repo_path,
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
                event="semantic_bootstrap_completed",
                provider_name=provider_name,
                model=model,
                chapter_count=structured_result.chapter_count,
                semantic_status=semantic_package.get("semantic_status"),
                chapter_count_completed=structured_result.chapter_count,
            )
            _append_bootstrap_progress(
                progress_log_path,
                phase="bootstrap",
                event="structured_bootstrap_imported",
                chapter_count=structured_result.chapter_count,
                primary_count=len(composed_paths),
                summary_count=len(story_summary_paths),
            )
        else:
            fallback_result = _materialize_chapter_manifest_project(
                vault_root=vault_root,
                inventory=inventory,
                project_title=config.project_title or source_root.name or "TextifAI Project",
                language=config.primary_language or "es",
                repo_path=repo_path,
                progress_log_path=progress_log_path,
            )
            if fallback_result is not None:
                import_strategy = "deterministic_chapter_manifest_project"
                story_chapter_paths = list(fallback_result["chapter_paths"])
                bootstrap_audit_path = str(vault_root / "99_System" / "markdown_manifest.json")
                notes.append("Structured bootstrap v1 was unavailable; created deterministic chapter-manifest project from uploaded Markdown.")
                _append_bootstrap_progress(
                    progress_log_path,
                    phase="bootstrap",
                    event="deterministic_fallback_used",
                    provider_name=provider_name,
                    model=model,
                )
                _append_bootstrap_progress(
                    progress_log_path,
                    phase="bootstrap",
                    event="deterministic_chapter_manifest_project_imported",
                    chapter_count=len(story_chapter_paths),
                    manifest_path=str(vault_root / "textifai.project.json"),
                )
            else:
                import_strategy = "structured_bootstrap_v1_unavailable"
                warnings.append("structured_bootstrap_v1_failed")
                notes.append("Structured bootstrap v1 did not complete, and deterministic chapter-manifest fallback could not identify chapters.")
                _append_bootstrap_progress(
                    progress_log_path,
                    phase="bootstrap",
                    event="structured_bootstrap_unavailable",
                    source_file_count=len(preexisting_source_paths),
                )
                importer_reason = "Structured bootstrap unavailable and deterministic chapter fallback found no chapters."
                fallback_result = None
            if fallback_result is not None:
                importer_reason = "Structured semantic bootstrap unavailable; deterministic chapter-manifest package created without provider calls."

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

def _materialize_chapter_manifest_project(
    *,
    vault_root: Path,
    inventory,
    project_title: str,
    language: str,
    repo_path: Path,
    progress_log_path: str | None,
) -> dict[str, object] | None:
    texts = read_source_documents(inventory, progress_log_path=progress_log_path)
    documents = list(getattr(inventory, "documents", []) or [])
    if not documents:
        return None
    primary = max(documents, key=lambda item: int(getattr(item, "extracted_char_count", 0) or len(texts.get(item.source_id, ""))))
    source_text = texts.get(primary.source_id, "")
    if not source_text.strip():
        return None

    chapter_manifest, _ = write_chapter_manifest(vault_root, source_text, str(getattr(primary, "path", "") or getattr(primary, "filename", "")))
    chapters = [chapter for chapter in chapter_manifest.get("chapters", []) if isinstance(chapter, dict)]
    if not chapters:
        return None

    system_root = vault_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    markdown_manifest = _build_markdown_manifest(vault_root, chapter_manifest)
    (system_root / "markdown_manifest.json").write_text(json.dumps(markdown_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_index = build_markdown_graph_index(vault_root)
    (system_root / "markdown_graph_index.json").write_text(json.dumps(markdown_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_queue = _empty_review_queue()
    vaerl = _minimal_vaerl(project_title=project_title, language=language, chapters=chapters)
    author_graph = build_author_graph(markdown_index=markdown_index, review_queue=review_queue)
    (vault_root / "vaerl").mkdir(parents=True, exist_ok=True)
    (vault_root / "graph").mkdir(parents=True, exist_ok=True)
    (vault_root / "reports").mkdir(parents=True, exist_ok=True)
    (vault_root / "vaerl" / "vaerl.json").write_text(json.dumps(vaerl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vault_root / "vaerl" / "review_queue.json").write_text(json.dumps(review_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vault_root / "graph" / "author_graph.json").write_text(json.dumps(author_graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    writer_outcome = _writer_outcome(len(chapters))
    (system_root / "writer_outcome.json").write_text(json.dumps(writer_outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = _textifai_project_manifest(
        project_title=project_title,
        language=language,
        source_path=str(getattr(primary, "path", "") or getattr(primary, "filename", "")),
        source_text=source_text,
        chapter_count=len(chapters),
        graph_summary={
            "node_count": len(author_graph.get("nodes") or []),
            "edge_count": len(author_graph.get("edges") or []),
        },
    )
    (vault_root / "textifai.project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _register_local_project(repo_path, vault_root / "textifai.project.json")
    return {"chapter_paths": [str(chapter.get("markdown_path") or "") for chapter in chapters if chapter.get("markdown_path")]}

def _finalize_semantic_project_package(
    *,
    vault_root: Path,
    structured_result,
    project_title: str,
    language: str,
    repo_path: Path,
) -> dict[str, object]:
    system_root = vault_root / "99_System"
    vaerl_root = vault_root / "vaerl"
    graph_root = vault_root / "graph"
    vaerl_root.mkdir(parents=True, exist_ok=True)
    graph_root.mkdir(parents=True, exist_ok=True)

    obsidian_import = _read_json(Path(structured_result.obsidian_import_path), default={})
    review_queue_path = getattr(structured_result, "review_queue_path", None)
    review_queue = _read_json(Path(review_queue_path), default=_empty_review_queue()) if review_queue_path else _empty_review_queue()
    entities = list(obsidian_import.get("entities") or []) if isinstance(obsidian_import, dict) else []
    chapters = list(obsidian_import.get("chapters") or []) if isinstance(obsidian_import, dict) else []
    relationships = _semantic_relationships_from_entities(entities)

    vaerl = {
        "work": obsidian_import.get("work") if isinstance(obsidian_import.get("work"), dict) else {"title": project_title, "language": language},
        "entities": entities,
        "chapters": chapters,
        "reviews": review_queue.get("items", []) if isinstance(review_queue, dict) else [],
        "provider_calls": True,
    }
    (vaerl_root / "vaerl.json").write_text(json.dumps(vaerl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vaerl_root / "entities.json").write_text(json.dumps({"entities": entities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vaerl_root / "relationships.json").write_text(json.dumps({"relationships": relationships}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vaerl_root / "review_queue.json").write_text(json.dumps(review_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown_index = build_markdown_graph_index(vault_root)
    (system_root / "markdown_graph_index.json").write_text(json.dumps(markdown_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (graph_root / "graph.json").write_text(json.dumps(markdown_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    author_graph = build_author_graph(markdown_index=markdown_index, review_queue=review_queue if isinstance(review_queue, dict) else _empty_review_queue())
    (graph_root / "author_graph.json").write_text(json.dumps(author_graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown_manifest = _build_semantic_markdown_manifest(vault_root, markdown_index)
    (system_root / "markdown_manifest.json").write_text(json.dumps(markdown_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    writer_outcome = _writer_outcome(int(structured_result.chapter_count or len(chapters)))
    (system_root / "writer_outcome.json").write_text(json.dumps(writer_outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    graph_summary = markdown_index if isinstance(markdown_index, dict) else {}
    manifest = _semantic_textifai_project_manifest(
        project_title=project_title,
        language=language,
        source_path=str(structured_result.source_document),
        chapter_count=int(structured_result.chapter_count or len(chapters)),
        review_count=int(review_queue.get("item_count") or len(review_queue.get("items") or []) if isinstance(review_queue, dict) else 0),
        graph_summary={
            "node_count": int(graph_summary.get("node_count") or len(graph_summary.get("nodes") or [])),
            "edge_count": int(graph_summary.get("edge_count") or len(graph_summary.get("edges") or [])),
        },
    )
    (vault_root / "textifai.project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _register_local_project(repo_path, vault_root / "textifai.project.json")
    return {"semantic_status": "semantic_ready", "entity_count": len(entities), "relationship_count": len(relationships)}

def _read_json(path: Path, *, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _semantic_relationships_from_entities(entities: list[object]) -> list[dict[str, object]]:
    relationships: list[dict[str, object]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        source = str(entity.get("canonical_name") or entity.get("canonical_label") or "").strip()
        for relation in entity.get("relationships") or []:
            if not isinstance(relation, dict):
                continue
            target = str(relation.get("target") or relation.get("to") or relation.get("to_canonical") or "").strip()
            relationships.append({**relation, "source": source, "target": target})
    return relationships

def _build_semantic_markdown_manifest(project_root: Path, markdown_index: dict[str, object]) -> dict[str, object]:
    notes = [item for item in markdown_index.get("notes", []) if isinstance(item, dict)]
    return {
        "schema_version": "textifai.vaerl_markdown_manifest.v1",
        "output_root": str(project_root),
        "folders": sorted({str(Path(str(item.get("path") or "")).parent) for item in notes if item.get("path")}),
        "notes": notes,
        "note_count": len(notes),
        "source_prose_included": True,
        "provider_calls": True,
        "editable_policy": {"editable_markdown": True, "semantic_artifacts_provider_backed": True},
    }

def _semantic_textifai_project_manifest(*, project_title: str, language: str, source_path: str, chapter_count: int, review_count: int, graph_summary: dict[str, int]) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    project_id = project_title.lower().replace(" ", "-")[:80] or "textifai-project"
    return {
        "schema": "textifai.project",
        "schema_version": 1,
        "project_id": project_id,
        "title": project_title,
        "language": language,
        "created_at": now,
        "updated_at": now,
        "textifai_version": "sp148-upload-semantic-bootstrap",
        "source": {"kind": "manuscript_markdown", "original_filename": Path(source_path).name, "stored_in_project": False},
        "paths": {"markdown_root": ".", "chapters_root": "04_Story/Chapters", "characters_root": "03_Characters/Profiles", "places_root": "02_World/Places", "events_root": "02_World/Events", "objects_root": "02_World/Objects", "concepts_root": "02_World/Concepts", "reviews_root": "90_Review", "vaerl": "vaerl/vaerl.json", "entities": "vaerl/entities.json", "relationships": "vaerl/relationships.json", "review_queue": "vaerl/review_queue.json", "graph": "graph/graph.json", "author_graph": "graph/author_graph.json", "markdown_graph_index": "99_System/markdown_graph_index.json", "markdown_manifest": "99_System/markdown_manifest.json", "writer_outcome": "99_System/writer_outcome.json", "reports": "reports"},
        "status": {"chapters_total": chapter_count, "chapters_ready": chapter_count, "chapters_ready_with_review_warnings": 0, "chapters_needs_author_review": review_count, "chapters_retry_required": 0, "chapters_still_failed": 0, "review_items": review_count, "graph_nodes": graph_summary.get("node_count", 0), "graph_edges": graph_summary.get("edge_count", 0), "vaerl_ready": True, "graph_ready": True, "review_ready": True, "semantic_ready": True},
        "capabilities": {"read_only": False, "editable_markdown": True, "drafts": False, "patch_queue": False, "chapter_mini_ingestion": False, "vaerl_update": False},
        "privacy": {"contains_source_prose": True, "contains_provider_outputs": True, "safe_to_commit": False, "shareable_package": False},
        "dev": {"runtime_origin": "sp148_upload_semantic_bootstrap", "contains_private_provider_outputs": True},
        "workspace_entry": {"default_screen": "Project Hub", "editor_source": "04_Story/Chapters", "graph_source": "graph/graph.json", "review_source": "vaerl/review_queue.json"},
        "ingestion_policy": {"provider_calls": True, "deterministic_chapter_manifest": False, "semantic_bootstrap": True},
    }

def _build_markdown_manifest(project_root: Path, chapter_manifest: dict[str, object]) -> dict[str, object]:
    notes = []
    for chapter in chapter_manifest.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        path = str(chapter.get("markdown_path") or "")
        if not path:
            continue
        notes.append({
            "path": path,
            "kind": "chapter",
            "title": str(chapter.get("display_title") or chapter.get("title") or chapter.get("chapter_id") or "chapter"),
            "display_title": str(chapter.get("display_title") or chapter.get("title") or chapter.get("chapter_id") or "chapter"),
            "canonical_label": str(chapter.get("display_title") or chapter.get("title") or chapter.get("chapter_id") or "chapter"),
            "chapter_id": str(chapter.get("chapter_id") or ""),
            "status": "ready",
            "review_state": "ready",
            "tags": ["chapter", "ready"],
        })
    return {
        "schema_version": "textifai.vaerl_markdown_manifest.v1",
        "output_root": str(project_root),
        "folders": ["Chapters", "System"],
        "notes": notes,
        "note_count": len(notes),
        "source_prose_included": False,
        "provider_calls": False,
    }

def _minimal_vaerl(*, project_title: str, language: str, chapters: list[dict[str, object]]) -> dict[str, object]:
    return {
        "work": {"title": project_title, "language": language, "source": "deterministic_chapter_manifest_project"},
        "chapters": [
            {
                "chapter_id": str(chapter.get("chapter_id") or ""),
                "sequence_index": int(chapter.get("order") or index),
                "chapter_title_original": str(chapter.get("display_title") or chapter.get("title") or chapter.get("chapter_id") or "chapter"),
                "chapter_title_canonical": str(chapter.get("display_title") or chapter.get("title") or chapter.get("chapter_id") or "chapter"),
                "status": "ready",
                "review_state": "ready",
            }
            for index, chapter in enumerate(chapters, start=1)
        ],
        "entities": [],
        "relationships": [],
        "provider_calls": False,
    }

def _empty_review_queue() -> dict[str, object]:
    return {"schema_version": "textifai.review_queue.v1", "item_count": 0, "items": [], "decision_items": [], "policy": {"pending_reviews_are_expected": True, "can_auto_apply_default": False}}

def _writer_outcome(chapter_count: int) -> dict[str, object]:
    return {"status": "success_ready", "total_chapters": chapter_count, "chapters_ready": chapter_count, "chapters_needing_retry": 0, "chapters_needing_review": 0, "chapters_failed": 0, "user_summary": f"{chapter_count} capítulos detectados. {chapter_count} listos.", "primary_action": {"label": "Abrir workspace", "action_id": "open_workspace"}, "secondary_action": {"label": "Abrir grafo", "action_id": "open_graph"}}

def _textifai_project_manifest(*, project_title: str, language: str, source_path: str, source_text: str, chapter_count: int, graph_summary: dict[str, int]) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    project_id = project_title.lower().replace(" ", "-")[:80] or "textifai-project"
    return {
        "schema": "textifai.project",
        "schema_version": 1,
        "project_id": project_id,
        "title": project_title,
        "language": language,
        "created_at": now,
        "updated_at": now,
        "textifai_version": "sp145-upload-deterministic",
        "source": {"kind": "manuscript_markdown", "original_filename": Path(source_path).name, "source_hash": f"sha256:{source_hash}", "stored_in_project": False},
        "paths": {"markdown_root": "markdown", "chapters_root": "markdown/Chapters", "chapter_manifest": "chapters/chapter_manifest.json", "vaerl": "vaerl/vaerl.json", "review_queue": "vaerl/review_queue.json", "graph": "graph/author_graph.json", "markdown_graph_index": "99_System/markdown_graph_index.json", "markdown_manifest": "99_System/markdown_manifest.json", "writer_outcome": "99_System/writer_outcome.json", "reports": "reports"},
        "status": {"chapters_total": chapter_count, "chapters_ready": chapter_count, "chapters_ready_with_review_warnings": 0, "chapters_needs_author_review": 0, "chapters_retry_required": 0, "chapters_still_failed": 0, "review_items": 0, "graph_nodes": graph_summary.get("node_count", 0), "graph_edges": graph_summary.get("edge_count", 0), "vaerl_ready": True, "graph_ready": True, "review_ready": True},
        "capabilities": {"read_only": False, "editable_markdown": True, "drafts": False, "patch_queue": False, "chapter_mini_ingestion": False, "vaerl_update": False},
        "privacy": {"contains_source_prose": True, "contains_provider_outputs": False, "safe_to_commit": False, "shareable_package": False},
        "dev": {"runtime_origin": "sp145_upload_deterministic_chapter_manifest", "contains_private_provider_outputs": False},
        "workspace_entry": {"default_screen": "Project Hub", "editor_source": "markdown/Chapters", "graph_source": "graph/author_graph.json", "review_source": "vaerl/review_queue.json"},
        "ingestion_policy": {"provider_calls": False, "deterministic_chapter_manifest": True},
    }

def _register_local_project(repo_path: Path, manifest_path: Path) -> None:
    registry_path = repo_path / ".textifai_runs" / "registry.local.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"schema": "textifai.local_registry", "schema_version": 2, "projects": [], "deleted_projects": []}
    projects = [item for item in payload.get("projects", []) if isinstance(item, dict)]
    deleted_projects = [item for item in payload.get("deleted_projects", []) if isinstance(item, dict)]
    manifest_text = str(manifest_path.resolve())
    if not any(str(item.get("manifest_path") or "") == manifest_text for item in projects):
        deleted_projects = [item for item in deleted_projects if str(item.get("manifest_path") or "") != manifest_text]
        projects.append({"manifest_path": manifest_text, "added_at": datetime.now(timezone.utc).isoformat()})
    payload["projects"] = projects
    payload["deleted_projects"] = deleted_projects
    payload["schema"] = "textifai.local_registry"
    payload["schema_version"] = max(int(payload.get("schema_version") or 1), 2)
    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
