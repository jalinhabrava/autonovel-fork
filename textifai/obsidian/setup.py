from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from providers.text_provider import get_text_provider_config_error
from textifai.bootstrap import (
    BootstrapLLMConfig,
    ProviderBackedBootstrapAnalyzer,
    VaultInitializationConfig,
    confirm_and_write_bootstrap,
)
from textifai.bootstrap.source_reader import discover_importable_source_paths
from textifai.import_review import ReviewPolicy, promote_reviewed_import, review_import_stage
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
    bootstrap_llm_analyzer = _resolve_bootstrap_llm_analyzer(repo_path)

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
        bootstrap_mode = "import_into_existing_vault"
        if not vault_root.exists() or not any(vault_root.iterdir()):
            bootstrap_vault(
                vault_root,
                title=config.project_title or source_root.name or "TextifAI Project",
                force=not vault_root.exists(),
                allow_existing_content=True,
            )
            vault_created = True
            bootstrap_mode = "new_project"
        elif validate_vault(vault_root):
            bootstrap_vault(
                vault_root,
                title=config.project_title or source_root.name or "TextifAI Project",
                allow_existing_content=True,
            )
            bootstrap_mode = "import_into_existing_vault"
            notes.append("Existing folder was converted into a TextifAI vault without disturbing prior material.")
        bootstrap_result = confirm_and_write_bootstrap(
            VaultInitializationConfig(
                vault_root=str(vault_root),
                mode=bootstrap_mode,
                project_title=config.project_title or source_root.name or "TextifAI Project",
                primary_language=config.primary_language,
                working_languages=list(config.working_languages),
                create_base_structure=True,
                use_import_staging=True,
            ),
            source_root=source_root,
            source_paths=preexisting_source_paths or None,
            llm_analyzer=bootstrap_llm_analyzer,
        )
        written_drafts = list(bootstrap_result.written_drafts)
        warnings.extend(list(bootstrap_result.warnings))
        import_strategy = "textifai_bootstrap_staging"
        notes.append("Existing source material was staged into the vault import workspace.")
        if written_drafts:
            bundle, reviews, plan = review_import_stage(vault_root, policy=ReviewPolicy())
            promotion = promote_reviewed_import(vault_root, policy=ReviewPolicy(), confirmed=False)
            promoted_paths = list(promotion.promoted_paths)
            pending_candidates = list(promotion.pending_drafts)
            if promoted_paths:
                notes.append(f"Automatically promoted {len(promoted_paths)} low-risk canonical artifacts.")
            elif pending_candidates:
                notes.append("Imported material remains in staging until explicit promotion or stronger context is available.")
        if _all_markdown_sources(source_root) and config.importer_preference == "obsidian_importer_manual_if_markdown":
            importer_reason = (
                "The official Obsidian Importer exists for Markdown, but TextifAI keeps using its own staging flow "
                "because it needs a reproducible, provenance-aware, reviewable path outside the app."
            )

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
    )


def _resolve_bootstrap_llm_analyzer(repo_root: Path) -> ProviderBackedBootstrapAnalyzer | None:
    synchronize_runtime_environment(repo_root)
    env = load_runtime_environment(repo_root)
    provider_name = env.provider
    if not provider_name or not env.writer_model:
        return None
    if get_text_provider_config_error("bootstrap_normalization", provider_name) is not None:
        return None
    return ProviderBackedBootstrapAnalyzer(
        config=BootstrapLLMConfig(
            task_name="bootstrap_normalization",
            provider_name=provider_name,
            model=env.writer_model,
            max_tokens=4000,
            temperature=0.1,
            timeout_seconds=120,
            retries=1,
        )
    )


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


def _all_markdown_sources(source_root: Path) -> bool:
    files = [path for path in source_root.rglob("*") if path.is_file()]
    return bool(files) and all(path.suffix.lower() == ".md" for path in files)


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
