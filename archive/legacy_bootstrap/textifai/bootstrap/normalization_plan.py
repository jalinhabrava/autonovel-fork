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
from textifai.bootstrap.semantic_enrichment import enrich_fragment_semantics
from textifai.obsidian.parser import parse_obsidian_frontmatter
from vault.schema import IMPORT_STAGING_DIRS
from vault.schema import slugify


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
        "raw_fragments": 0,
        "candidate_artifacts": 0,
        "promotion_eligible_artifacts": 0,
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
        source_frontmatter = parse_obsidian_frontmatter(text)
        analysis = analyses_by_source.get(document.source_id)
        document_requires_confirmation = bool(analysis and analysis.requires_confirmation)
        if document.has_mixed_language or len(document.detected_languages) > 1:
            coverage["multilingual_documents"] += 1
        coverage["total_fragments"] += len(fragments)
        coverage["raw_fragments"] += len(fragments)
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
            if document_requires_confirmation and fragment.fragment_id not in ambiguous_fragments:
                coverage["pending_fragments"] += 1
            coverage["covered_chars"] += len(fragment.text)
            draft = _build_draft(
                config=config,
                document=document,
                source_frontmatter=source_frontmatter,
                document_analysis=analysis,
                fragment=fragment,
                artifact_type=artifact_type,
                fragment_analysis=fragment_analysis,
                fragment_index=index,
            )
            drafts.append(draft)
            coverage["candidate_artifacts"] += 1
            if draft.promotion_status == "eligible_for_promotion":
                coverage["promotion_eligible_artifacts"] += 1
            coverage["staged_fragments"] += 1
        if not fragments:
            unmapped_fragments.append(document.source_id)
        elif document_requires_confirmation:
            coverage["pending_fragments"] += 0

    plan = NormalizationPlan(
        plan_id=uuid.uuid4().hex[:12],
        target_vault_root=config.vault_root,
        target_staging_root=str(Path(config.vault_root).expanduser().resolve() / IMPORT_STAGING_DIRS["root"]),
        drafts=drafts,
        unmapped_fragments=unmapped_fragments,
        ambiguous_fragments=ambiguous_fragments,
        coverage_summary=coverage,
        requires_confirmation=bool(
            unmapped_fragments
            or ambiguous_fragments
            or any(doc.has_mixed_language for doc in inventory.documents)
            or any(analysis.requires_confirmation for analysis in analyses_by_source.values())
        ),
    )
    return plan, coverage


def build_bootstrap_result(
    *,
    config: VaultInitializationConfig,
    inventory: SourceDocumentInventory | None,
    plan: NormalizationPlan | None,
    created_vault: bool,
    written_drafts: list[str] | None = None,
    promoted_paths: list[str] | None = None,
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
        promoted_paths=list(promoted_paths or []),
        coverage_report=dict(coverage_report or (plan.coverage_summary if plan is not None else {})),
        warnings=list(warnings or []),
    )


def _build_draft(
    *,
    config: VaultInitializationConfig,
    document: SourceDocumentRecord,
    source_frontmatter: dict[str, object] | None,
    document_analysis: BootstrapDocumentAnalysis | None,
    fragment: SourceFragment,
    artifact_type: str,
    fragment_analysis,
    fragment_index: int,
) -> NormalizedArtifactDraft:
    source_frontmatter = dict(source_frontmatter or {})
    explicit_kind = str(source_frontmatter.get("kind") or "").strip()
    if explicit_kind not in BOOTSTRAP_ARTIFACT_TYPE_CATALOG:
        explicit_kind = ""
    title = (
        fragment_analysis.title_hint
        or str(source_frontmatter.get("title") or "").strip()
        or _infer_title(document, fragment)
    )
    source_format = document_analysis.source_format if document_analysis else document.extension
    extraction_mode = document_analysis.extraction_mode if document_analysis else ("native_text" if document.extension in {"md", "txt"} else "light_structural_normalization")
    semantic = enrich_fragment_semantics(
        document=document,
        fragment=fragment,
        artifact_type=explicit_kind or artifact_type,
        fragment_title_hint=title,
        fragment_notes=list(fragment_analysis.notes) if fragment_analysis else [],
    )
    if fragment_analysis is not None:
        semantic = _merge_llm_semantics(
            fallback=semantic,
            fragment_analysis=fragment_analysis,
        )
    if explicit_kind:
        explicit_title = str(source_frontmatter.get("title") or semantic.title).strip() or semantic.title
        explicit_slug = str(source_frontmatter.get("slug") or semantic.slug).strip() or semantic.slug
        explicit_notes = list(dict.fromkeys([*semantic.notes, "explicit_source_frontmatter"]))
        semantic = semantic.__class__(
            artifact_type=explicit_kind,
            title=explicit_title,
            slug=explicit_slug,
            artifact_stage=semantic.artifact_stage,
            promotion_status="eligible_for_promotion",
            canonical_subject=semantic.canonical_subject or explicit_title,
            semantic_class=semantic.semantic_class or "explicit_source_artifact",
            source_section_title=semantic.source_section_title,
            fragment_role=semantic.fragment_role,
            entities=list(semantic.entities),
            topics=list(semantic.topics),
            world_terms=list(semantic.world_terms),
            character_refs=list(semantic.character_refs),
            lore_refs=list(semantic.lore_refs),
            notes=explicit_notes,
        )
    title = semantic.title
    slug = _resolved_semantic_slug(
        document=document,
        semantic_slug=semantic.slug,
        artifact_type=semantic.artifact_type,
        source_format=source_format,
        extraction_mode=extraction_mode,
    )
    target_path = _build_target_path(config.vault_root, semantic.artifact_type, _build_draft_filename(document, fragment_index, slug))
    extraction_confidence = document_analysis.extraction_confidence if document_analysis else fragment.kind_confidence
    structural_confidence = document_analysis.structural_confidence if document_analysis else fragment.kind_confidence
    if explicit_kind and source_format in {"md", "txt"} and extraction_mode == "native_text":
        extraction_confidence = max(extraction_confidence, 0.95)
        structural_confidence = max(structural_confidence, 0.95)
    provenance = ImportProvenance(
        source_id=document.source_id,
        source_path=document.path,
        source_checksum=document.checksum,
        source_format=source_format,
        extraction_mode=extraction_mode,
        extraction_confidence=extraction_confidence,
        structural_confidence=structural_confidence,
        fragment_ids=[fragment.fragment_id],
        char_ranges=[{"start": fragment.char_start, "end": fragment.char_end}],
        import_mode="literal_copy"
        if source_format in {"md", "txt"} and extraction_mode == "native_text"
        else "light_structural_normalization",
        llm_assisted=bool(document_analysis and document_analysis.llm_used),
        warnings=list(document_analysis.coverage_notes if document_analysis else []),
        loss_risk_flags=list(document_analysis.coverage_notes if document_analysis else []),
        notes=list(document_analysis.coverage_notes if document_analysis else []),
    )
    detected_languages = list(
        dict.fromkeys(
            [
                *([language for language in getattr(document_analysis, "detected_languages", []) if language]),
                *([fragment.language] if fragment.language else []),
            ]
        )
    )
    return NormalizedArtifactDraft(
        draft_id=f"{document.source_id}__{fragment.fragment_id}",
        artifact_type=semantic.artifact_type,
        title=title,
        slug=slug,
        target_path=target_path,
        body=fragment.text.strip(),
        dominant_language=fragment_analysis.language if fragment_analysis and fragment_analysis.language else fragment.language,
        detected_languages=detected_languages,
        register_signals=list(dict.fromkeys([*fragment.register_signals, *(fragment_analysis.register_signals if fragment_analysis else [])])),
        provenance=provenance,
        normalization_notes=list(semantic.notes),
        artifact_stage=semantic.artifact_stage,
        promotion_status=semantic.promotion_status,
        canonical_subject=semantic.canonical_subject,
        semantic_class=semantic.semantic_class,
        source_section_title=semantic.source_section_title,
        fragment_role=semantic.fragment_role,
        entities=list(semantic.entities),
        topics=list(semantic.topics),
        world_terms=list(semantic.world_terms),
        character_refs=list(semantic.character_refs),
        lore_refs=list(semantic.lore_refs),
        confidence=max(fragment_analysis.confidence if fragment_analysis else fragment.kind_confidence, 0.9 if explicit_kind else 0.0),
        status="needs_review" if fragment.needs_review or (fragment_analysis.needs_review if fragment_analysis else False) else "draft",
    )


def _merge_llm_semantics(*, fallback, fragment_analysis):
    title = getattr(fragment_analysis, "title_hint", None) or fallback.title
    artifact_type = getattr(fragment_analysis, "artifact_type", None) or fallback.artifact_type
    canonical_subject = getattr(fragment_analysis, "canonical_subject", None)
    semantic_class = getattr(fragment_analysis, "semantic_class", None)
    promotion_status = getattr(fragment_analysis, "promotion_status", None)
    fragment_role = getattr(fragment_analysis, "fragment_role", None)
    entities = list(getattr(fragment_analysis, "entities", []) or fallback.entities)
    topics = list(getattr(fragment_analysis, "topics", []) or fallback.topics)
    world_terms = list(getattr(fragment_analysis, "world_terms", []) or fallback.world_terms)
    character_refs = list(getattr(fragment_analysis, "character_refs", []) or fallback.character_refs)
    lore_refs = list(getattr(fragment_analysis, "lore_refs", []) or fallback.lore_refs)
    return fallback.__class__(
        artifact_type=artifact_type,
        title=title,
        slug=slugify(title) or fallback.slug,
        artifact_stage=fallback.artifact_stage,
        promotion_status=promotion_status or fallback.promotion_status,
        canonical_subject=canonical_subject or fallback.canonical_subject,
        semantic_class=semantic_class or fallback.semantic_class,
        source_section_title=fallback.source_section_title,
        fragment_role=fragment_role or fallback.fragment_role,
        entities=entities,
        topics=topics,
        world_terms=world_terms,
        character_refs=character_refs,
        lore_refs=lore_refs,
        notes=list(dict.fromkeys([*fallback.notes, *getattr(fragment_analysis, "notes", [])])),
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


def _build_draft_filename(document: SourceDocumentRecord, fragment_index: int, semantic_slug: str) -> str:
    prefix = _build_draft_slug(document, fragment_index)
    if semantic_slug and semantic_slug != prefix:
        return f"{prefix}__{semantic_slug}"
    return prefix


def _resolved_semantic_slug(
    *,
    document: SourceDocumentRecord,
    semantic_slug: str,
    artifact_type: str,
    source_format: str,
    extraction_mode: str,
) -> str:
    slug = semantic_slug or _build_draft_slug(document, 1)
    if source_format in {"pdf", "docx", "doc"} or extraction_mode != "native_text":
        if artifact_type in {"scene", "chapter"}:
            return f"{slug}_{document.source_id[-6:]}"
    return slug


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
