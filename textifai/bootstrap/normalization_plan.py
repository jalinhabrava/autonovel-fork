from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from textifai.bootstrap.analyzer import BootstrapDocumentAnalysis
from textifai.bootstrap.contracts import (
    BOOTSTRAP_ARTIFACT_TYPE_CATALOG,
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
from vault.schema import IMPORT_STAGING_DIRS


@dataclass(frozen=True)
class BootstrapPreparation:
    config: VaultInitializationConfig
    inventory: SourceDocumentInventory
    source_texts: dict[str, str]
    fragments_by_source: dict[str, list[SourceFragment]]
    language_profile: LanguageProfile
    analyses_by_source: dict[str, BootstrapDocumentAnalysis]
    plan: NormalizationPlan


def build_normalization_plan(
    *,
    config: VaultInitializationConfig,
    inventory: SourceDocumentInventory,
    source_texts: dict[str, str],
    fragments_by_source: dict[str, list[SourceFragment]],
    analyses_by_source: dict[str, BootstrapDocumentAnalysis] | None = None,
    language_profile: LanguageProfile | None = None,
) -> tuple[NormalizationPlan, dict[str, int]]:
    analyses_by_source = analyses_by_source or {}
    language_profile = language_profile or build_language_profile(
        inventory,
        fragments_by_source,
        source_texts,
        project_primary_language=config.primary_language,
        working_languages=config.working_languages,
    )
    drafts: list[NormalizedArtifactDraft] = []
    ambiguous_fragments: list[str] = []
    unmapped_fragments: list[str] = []
    coverage = {
        "total_documents": len(inventory.documents),
        "total_fragments": 0,
        "total_chars": 0,
        "covered_chars": 0,
        "ambiguous_chars": 0,
        "unmapped_chars": 0,
        "pending_fragments": 0,
        "staged_fragments": 0,
        "multilingual_documents": 0,
    }

    for document in inventory.documents:
        fragments = fragments_by_source.get(document.source_id, [])
        text = source_texts.get(document.source_id, "")
        analysis = analyses_by_source.get(document.source_id)
        if document.has_mixed_language or len(document.detected_languages) > 1:
            coverage["multilingual_documents"] += 1
        coverage["total_fragments"] += len(fragments)
        coverage["total_chars"] += len(text)
        for index, fragment in enumerate(fragments, start=1):
            fragment_analysis = _fragment_analysis_for(fragment, analysis)
            if fragment_analysis is None:
                unmapped_fragments.append(fragment.fragment_id)
                coverage["unmapped_chars"] += len(fragment.text)
                continue
            artifact_type = fragment_analysis.artifact_type
            if artifact_type not in BOOTSTRAP_ARTIFACT_TYPE_CATALOG:
                artifact_type = "mixed_note"
            if fragment_analysis.needs_review or fragment.kind_confidence < 0.6 or fragment_analysis.confidence < 0.6:
                ambiguous_fragments.append(fragment.fragment_id)
                coverage["ambiguous_chars"] += len(fragment.text)
            coverage["covered_chars"] += len(fragment.text)
            draft = _build_draft(
                config=config,
                document=document,
                fragment=fragment,
                artifact_type=artifact_type,
                analysis=fragment_analysis,
                fragment_index=index,
            )
            drafts.append(draft)
            coverage["staged_fragments"] += 1
        if not fragments:
            unmapped_fragments.append(document.source_id)

    plan = NormalizationPlan(
        plan_id=uuid.uuid4().hex[:12],
        target_vault_root=config.vault_root,
        target_staging_root=str(Path(config.vault_root).expanduser().resolve() / IMPORT_STAGING_DIRS["root"]),
        drafts=drafts,
        unmapped_fragments=unmapped_fragments,
        ambiguous_fragments=ambiguous_fragments,
        coverage_summary=coverage,
        requires_confirmation=bool(unmapped_fragments or ambiguous_fragments or any(doc.has_mixed_language for doc in inventory.documents)),
    )
    return plan, coverage


def build_bootstrap_result(
    *,
    config: VaultInitializationConfig,
    inventory: SourceDocumentInventory | None,
    plan: NormalizationPlan | None,
    created_vault: bool,
    written_drafts: list[str] | None = None,
    coverage_report: dict[str, int] | None = None,
    warnings: list[str] | None = None,
) -> BootstrapResult:
    return BootstrapResult(
        vault_root=config.vault_root,
        staging_root=plan.target_staging_root if plan is not None else None,
        created_vault=created_vault,
        inventory=inventory,
        normalization_plan=plan,
        written_drafts=list(written_drafts or []),
        coverage_report=dict(coverage_report or (plan.coverage_summary if plan is not None else {})),
        warnings=list(warnings or []),
    )


def _build_draft(
    *,
    config: VaultInitializationConfig,
    document: SourceDocumentRecord,
    fragment: SourceFragment,
    artifact_type: str,
    analysis,
    fragment_index: int,
) -> NormalizedArtifactDraft:
    title = analysis.title_hint or _infer_title(document, fragment)
    slug = _build_draft_slug(document, fragment_index)
    target_path = _build_target_path(config.vault_root, artifact_type, slug)
    provenance = ImportProvenance(
        source_id=document.source_id,
        source_path=document.path,
        source_checksum=document.checksum,
        fragment_ids=[fragment.fragment_id],
        char_ranges=[{"start": fragment.char_start, "end": fragment.char_end}],
        import_mode="light_structural_normalization" if fragment.text.lstrip().startswith("#") or len(fragment.text.splitlines()) > 1 else "literal_segmented",
        llm_assisted=analysis is not None and bool(getattr(analysis, "raw_payload", {})),
        notes=list(getattr(analysis, "coverage_notes", [])),
    )
    detected_languages = list(
        dict.fromkeys(
            [
                *([language for language in getattr(analysis, "detected_languages", []) if language]),
                *([fragment.language] if fragment.language else []),
            ]
        )
    )
    return NormalizedArtifactDraft(
        draft_id=f"{document.source_id}__{fragment.fragment_id}",
        artifact_type=artifact_type,
        title=title,
        slug=slug,
        target_path=target_path,
        body=fragment.text.strip(),
        dominant_language=analysis.language if analysis and analysis.language else fragment.language,
        detected_languages=detected_languages,
        register_signals=list(dict.fromkeys([*fragment.register_signals, *(analysis.register_signals if analysis else [])])),
        provenance=provenance,
        normalization_notes=list(analysis.notes) if analysis else [],
        confidence=analysis.confidence if analysis else fragment.kind_confidence,
        status="needs_review" if fragment.needs_review or (analysis.needs_review if analysis else False) else "draft",
    )


def _fragment_analysis_for(fragment: SourceFragment, analysis: BootstrapDocumentAnalysis | None):
    if analysis is None:
        return _FragmentAnalysisProxy(
            fragment_id=fragment.fragment_id,
            artifact_type=fragment.detected_kind if fragment.detected_kind in BOOTSTRAP_ARTIFACT_TYPE_CATALOG else "mixed_note",
            confidence=fragment.kind_confidence,
            title_hint=None,
            language=fragment.language,
            register_signals=list(fragment.register_signals),
            needs_review=fragment.needs_review,
            notes=[],
        )
    for item in analysis.fragment_analyses:
        if item.fragment_id == fragment.fragment_id:
            return item
    if fragment.fragment_id in analysis.unmapped_fragment_ids:
        return None
    return _FragmentAnalysisProxy(
        fragment_id=fragment.fragment_id,
        artifact_type=fragment.detected_kind if fragment.detected_kind in BOOTSTRAP_ARTIFACT_TYPE_CATALOG else "mixed_note",
        confidence=fragment.kind_confidence,
        title_hint=None,
        language=fragment.language,
        register_signals=list(fragment.register_signals),
        needs_review=fragment.needs_review,
        notes=list(analysis.coverage_notes),
    )


def _build_target_path(vault_root: str, artifact_type: str, slug: str) -> str:
    staging_root = Path(vault_root).expanduser().resolve() / IMPORT_STAGING_DIRS["root"]
    folder_map = {
        "character": IMPORT_STAGING_DIRS["characters"],
        "lore": IMPORT_STAGING_DIRS["lore"],
        "scene": IMPORT_STAGING_DIRS["scenes"],
        "chapter": IMPORT_STAGING_DIRS["chapters"],
        "mixed_note": IMPORT_STAGING_DIRS["mixed"],
        "project_note": IMPORT_STAGING_DIRS["mixed"],
    }
    folder = folder_map.get(artifact_type, IMPORT_STAGING_DIRS["mixed"])
    return str((staging_root / folder / f"{slug}.md").resolve())


def _build_draft_slug(document: SourceDocumentRecord, fragment_index: int) -> str:
    stem = "".join(ch for ch in document.filename.rsplit(".", 1)[0].lower() if ch.isalnum())
    stem = stem[:20] or "source"
    return f"{stem}_{document.source_id[-8:]}_{fragment_index:03d}"


def _infer_title(document: SourceDocumentRecord, fragment) -> str:
    first_line = fragment.text.strip().splitlines()[0].strip() if fragment.text.strip() else ""
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip() or document.filename.rsplit(".", 1)[0]
    return document.filename.rsplit(".", 1)[0]


@dataclass(frozen=True)
class _FragmentAnalysisProxy:
    fragment_id: str
    artifact_type: str
    confidence: float = 0.0
    title_hint: str | None = None
    language: str | None = None
    detected_languages: list[str] = field(default_factory=list)
    register_signals: list[str] = field(default_factory=list)
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)
