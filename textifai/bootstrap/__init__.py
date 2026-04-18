from __future__ import annotations

from pathlib import Path

from textifai.bootstrap.analyzer import (
    BootstrapDocumentAnalysis,
    BootstrapFragmentAnalysis,
    BootstrapLLMAnalyzer,
    BootstrapLLMConfig,
    ProviderBackedBootstrapAnalyzer,
)
from textifai.bootstrap.contracts import (
    BOOTSTRAP_ARTIFACT_TYPE_CATALOG,
    BOOTSTRAP_FRAGMENT_STATUS_CATALOG,
    BOOTSTRAP_IMPORT_MODE_CATALOG,
    BOOTSTRAP_MODE_CATALOG,
    BootstrapResult,
    ImportProvenance,
    LanguageProfile,
    NormalizationPlan,
    NormalizedArtifactDraft,
    SourceDocumentInventory,
    SourceDocumentRecord,
    SourceFragment,
    VaultInitializationConfig,
)
from textifai.bootstrap.language import build_language_profile
from textifai.bootstrap.normalization_plan import build_bootstrap_result, build_normalization_plan
from textifai.bootstrap.segmenter import segment_source_document
from textifai.bootstrap.source_reader import build_source_document_inventory, read_source_documents
from textifai.bootstrap.staging_writer import write_bootstrap_staging
from textifai.bootstrap.validation import validate_bootstrap_result
from vault.bootstrap import bootstrap_vault, create_import_staging_structure, validate_vault


def prepare_bootstrap(
    config: VaultInitializationConfig,
    *,
    source_root: str | Path | None = None,
    llm_analyzer: BootstrapLLMAnalyzer | None = None,
) -> BootstrapResult:
    vault_root = Path(config.vault_root).expanduser().resolve()
    created_vault = False
    if config.mode == "new_project":
        if not vault_root.exists():
            bootstrap_vault(vault_root, title=config.project_title or "TextifAI Project", force=False)
            created_vault = True
        elif not any(vault_root.iterdir()):
            bootstrap_vault(vault_root, title=config.project_title or "TextifAI Project", force=True)
            created_vault = True
        else:
            if validate_vault(vault_root):
                raise ValueError(f"Existing path is not a valid vault: {vault_root}")
            create_import_staging_structure(vault_root)
    else:
        errors = validate_vault(vault_root)
        if errors:
            raise ValueError("Existing vault is not valid: " + "; ".join(errors))
        create_import_staging_structure(vault_root)

    warnings: list[str] = []
    if not config.use_import_staging:
        warnings.append("Import staging is mandatory in this block; staging has been created regardless of the config flag.")

    if source_root is None:
        plan = None
        inventory = None
        return build_bootstrap_result(
            config=config,
            inventory=inventory,
            plan=plan,
            created_vault=created_vault,
            written_drafts=[],
            coverage_report={
                "total_documents": 0,
                "total_fragments": 0,
                "total_chars": 0,
                "covered_chars": 0,
                "ambiguous_chars": 0,
                "unmapped_chars": 0,
                "pending_fragments": 0,
                "staged_fragments": 0,
                "multilingual_documents": 0,
            },
            warnings=warnings,
        )

    inventory = build_source_document_inventory(source_root)
    source_texts = read_source_documents(inventory)
    fragments_by_source = {
        document.source_id: segment_source_document(document, source_texts[document.source_id])
        for document in inventory.documents
    }
    analyses_by_source: dict[str, BootstrapDocumentAnalysis] = {}
    if llm_analyzer is not None:
        for document in inventory.documents:
            analysis = llm_analyzer.analyze_document(
                config=config,
                document=document,
                text=source_texts.get(document.source_id, ""),
                fragments=fragments_by_source.get(document.source_id, []),
            )
            if analysis is not None:
                analyses_by_source[document.source_id] = analysis

    recovered_source_ids: list[str] = []
    for document in inventory.documents:
        analysis = analyses_by_source.get(document.source_id)
        recovered_text = getattr(analysis, "recognized_or_recovered_text", None) if analysis is not None else None
        if recovered_text and recovered_text != source_texts.get(document.source_id, ""):
            source_texts[document.source_id] = recovered_text
            fragments_by_source[document.source_id] = segment_source_document(document, recovered_text)
            recovered_source_ids.append(document.source_id)

    if llm_analyzer is not None and recovered_source_ids:
        for document in inventory.documents:
            if document.source_id not in recovered_source_ids:
                continue
            analysis = llm_analyzer.analyze_document(
                config=config,
                document=document,
                text=source_texts.get(document.source_id, ""),
                fragments=fragments_by_source.get(document.source_id, []),
            )
            if analysis is not None:
                analyses_by_source[document.source_id] = analysis

    language_profile = build_language_profile(
        inventory,
        fragments_by_source,
        source_texts,
        project_primary_language=config.primary_language,
        working_languages=config.working_languages,
    )
    plan, coverage = build_normalization_plan(
        config=config,
        inventory=inventory,
        source_texts=source_texts,
        fragments_by_source=fragments_by_source,
        analyses_by_source=analyses_by_source,
        language_profile=language_profile,
    )
    return build_bootstrap_result(
        config=config,
        inventory=inventory,
        plan=plan,
        created_vault=created_vault,
        coverage_report=coverage,
        warnings=[*warnings, *inventory.warnings],
    )


def confirm_and_write_bootstrap(
    config: VaultInitializationConfig,
    *,
    source_root: str | Path,
    llm_analyzer: BootstrapLLMAnalyzer | None = None,
) -> BootstrapResult:
    result = prepare_bootstrap(config, source_root=source_root, llm_analyzer=llm_analyzer)
    if result.normalization_plan is None or result.inventory is None:
        return result
    source_texts = read_source_documents(result.inventory)
    fragments_by_source = {
        document.source_id: segment_source_document(document, source_texts[document.source_id])
        for document in result.inventory.documents
    }
    written_paths, coverage, manifest_path = write_bootstrap_staging(
        plan=result.normalization_plan,
        inventory=result.inventory,
        source_texts=source_texts,
        fragments_by_source=fragments_by_source,
        warnings=result.warnings,
    )
    final_result = build_bootstrap_result(
        config=config,
        inventory=result.inventory,
        plan=result.normalization_plan,
        created_vault=result.created_vault,
        written_drafts=written_paths,
        coverage_report=coverage,
        warnings=list(result.warnings),
    )
    validation_errors = validate_bootstrap_result(final_result)
    if validation_errors:
        return build_bootstrap_result(
            config=config,
            inventory=result.inventory,
            plan=result.normalization_plan,
            created_vault=result.created_vault,
            written_drafts=written_paths,
            coverage_report=coverage,
            warnings=[*result.warnings, *validation_errors, f"manifest_path={manifest_path}"],
        )
    return final_result
