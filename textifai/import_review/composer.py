from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle, load_staging_import_bundle
from textifai.obsidian import open_obsidian_source
from textifai.bootstrap.source_reader import read_source_documents, build_source_document_inventory
from vault.notes import artifact_path_for, write_artifact_payload
from vault.schema import slugify


_STRUCTURAL_PREFIX_RE = re.compile(r"^[^A-Za-z0-9À-ÿ一-龯ぁ-んァ-ン]+")


@dataclass(frozen=True)
class CompositionConfig:
    provider_name: str | None
    model: str | None
    task_name: str = "bootstrap_normalization"
    max_tokens: int = 2200
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1
    max_candidates: int = 40
    min_confidence: float = 0.68


@dataclass(frozen=True)
class CanonicalCompositionCandidate:
    subject_key: str
    display_name: str
    draft_ids: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    evidence_labels: list[str] = field(default_factory=list)
    type_hints: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(frozen=True)
class CompositionAuditEntry:
    subject_key: str
    display_name: str
    should_write: bool
    note_type: str | None
    title: str | None
    target_path: str | None
    confidence: float
    supporting_draft_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CanonicalCompositionResult:
    written_paths: list[str] = field(default_factory=list)
    audit_entries: list[CompositionAuditEntry] = field(default_factory=list)
    skipped_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def compose_primary_notes_from_staging(
    vault_root: str | Path,
    *,
    config: CompositionConfig,
    progress_log_path: str | None = None,
) -> CanonicalCompositionResult:
    if get_text_provider_config_error(config.task_name, config.provider_name):
        return CanonicalCompositionResult(warnings=["provider_unavailable_for_primary_note_composition"])
    bundle = load_staging_import_bundle(vault_root)
    candidates = discover_primary_candidates(bundle, max_candidates=config.max_candidates)
    written_paths: list[str] = []
    skipped_candidates: list[str] = []
    warnings: list[str] = []
    audit_entries: list[CompositionAuditEntry] = []
    candidate_subject_keys = {candidate.subject_key for candidate in candidates}
    for index, candidate in enumerate(candidates, start=1):
        _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_started", index=index, total=len(candidates), subject=candidate.display_name)
        draft_map = {draft.draft_id: draft for draft in bundle.drafts if draft.draft_id in set(candidate.draft_ids)}
        selected_drafts = _select_candidate_drafts(candidate, list(draft_map.values()))
        proposal = _compose_candidate(bundle=bundle, candidate=candidate, drafts=selected_drafts, config=config)
        if proposal is None:
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type=None,
                    title=None,
                    target_path=None,
                    confidence=0.0,
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=["llm_proposal_missing"],
                )
            )
            _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_skipped", subject=candidate.display_name, reason="llm_proposal_missing")
            continue
        note_type = str(proposal.get("note_type") or "").strip().casefold()
        if note_type == "skip":
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type="skip",
                    title=None,
                    target_path=None,
                    confidence=_coerce_confidence(proposal.get("confidence")),
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=_string_list(proposal.get("notes")) or ["llm_skipped_candidate"],
                )
            )
            _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_skipped", subject=candidate.display_name, reason="llm_skip")
            continue
        if note_type not in {"character", "place", "lore", "magic", "creature", "faction", "object", "history", "scene", "chapter"}:
            skipped_candidates.append(candidate.subject_key)
            warnings.append(f"unsupported_composed_note_type:{candidate.display_name}:{note_type}")
            continue
        confidence = _coerce_confidence(proposal.get("confidence"))
        if confidence < config.min_confidence:
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type=note_type,
                    title=str(proposal.get("title") or "").strip() or candidate.display_name,
                    target_path=None,
                    confidence=confidence,
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=["confidence_below_threshold", *_string_list(proposal.get("notes"))],
                )
            )
            _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_skipped", subject=candidate.display_name, reason="confidence_below_threshold", confidence=confidence)
            continue
        if not _proposal_is_substantial(proposal):
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type=note_type,
                    title=str(proposal.get("title") or "").strip() or candidate.display_name,
                    target_path=None,
                    confidence=confidence,
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=["proposal_too_thin_for_primary", *_string_list(proposal.get("notes"))],
                )
            )
            _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_skipped", subject=candidate.display_name, reason="proposal_too_thin_for_primary")
            continue
        title = str(proposal.get("title") or candidate.display_name).strip() or candidate.display_name
        slug = slugify(str(proposal.get("slug") or title))
        target_path = artifact_path_for(bundle.vault_root, artifact_kind="note", artifact_type=note_type, entity_id=slug)
        if target_path.exists():
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type=note_type,
                    title=title,
                    target_path=str(target_path),
                    confidence=confidence,
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=["target_exists", *_string_list(proposal.get("notes"))],
                )
            )
            continue
        primary_subject = str(proposal.get("canonical_subject") or title).strip() or title
        related_subjects = _dedupe(_string_list(proposal.get("related_subjects")))
        aliases = _sanitize_aliases(
            [
                *_string_list(proposal.get("aliases")),
                *candidate.aliases,
                *([candidate.display_name] if slugify(candidate.display_name) != slugify(title) else []),
                *([primary_subject] if slugify(primary_subject) != slugify(title) else []),
            ],
            title=title,
            canonical_subject=primary_subject,
            related_subjects=related_subjects,
            blocked_subject_keys=candidate_subject_keys - {candidate.subject_key, slugify(title), slugify(primary_subject)},
        )
        duplicate_primary_path = _existing_primary_conflict_path(
            bundle.vault_root,
            subject_key=candidate.subject_key,
            title=title,
            canonical_subject=primary_subject,
            aliases=aliases,
        )
        if duplicate_primary_path is not None:
            skipped_candidates.append(candidate.subject_key)
            audit_entries.append(
                CompositionAuditEntry(
                    subject_key=candidate.subject_key,
                    display_name=candidate.display_name,
                    should_write=False,
                    note_type=note_type,
                    title=title,
                    target_path=str(duplicate_primary_path),
                    confidence=confidence,
                    supporting_draft_ids=list(candidate.draft_ids),
                    notes=["duplicate_primary_subject_exists", *_string_list(proposal.get("notes"))],
                )
            )
            _emit_progress(
                progress_log_path,
                phase="compose_primary_notes",
                event="candidate_skipped",
                subject=candidate.display_name,
                reason="duplicate_primary_subject_exists",
                existing_path=str(duplicate_primary_path),
            )
            continue
        body = _render_primary_note_body(
            title=title,
            note_type=note_type,
            summary=str(proposal.get("summary") or "").strip(),
            key_facts=_string_list(proposal.get("key_facts")),
            related_subjects=related_subjects,
            source_drafts=selected_drafts,
        )
        composition_language = _draft_language(selected_drafts)
        aggregated_metadata = _aggregate_draft_metadata(selected_drafts)
        metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "primary",
            "entity_kind": note_type,
            "canonical_subject": primary_subject,
            "semantic_class": str(proposal.get("semantic_class") or note_type).strip() or note_type,
            "aliases": ", ".join(aliases),
            "related_subjects": ", ".join(related_subjects),
            "source_staging_drafts": ", ".join(draft.draft_id for draft in selected_drafts),
            "composed_from_staging": "true",
            "note_language": composition_language,
            "evidence_sources": ", ".join(
                _dedupe(
                    [
                        str(draft.provenance.source_path)
                        for draft in selected_drafts
                        if draft.provenance is not None and str(draft.provenance.source_path).strip()
                    ]
                )
            ),
            "confidence": confidence,
            "review_state": "canonical",
            "entities": ", ".join(aggregated_metadata["entities"]),
            "topics": ", ".join(aggregated_metadata["topics"]),
            "world_terms": ", ".join(aggregated_metadata["world_terms"]),
            "character_refs": ", ".join(aggregated_metadata["character_refs"]),
            "lore_refs": ", ".join(aggregated_metadata["lore_refs"]),
        }
        provenance = next((draft.provenance for draft in selected_drafts if draft.provenance is not None), None)
        if provenance is not None:
            metadata.update(
                {
                    "source_format": provenance.source_format,
                    "extraction_mode": provenance.extraction_mode,
                    "extraction_confidence": provenance.extraction_confidence,
                    "structural_confidence": provenance.structural_confidence,
                }
            )
        path = write_artifact_payload(
            bundle.vault_root,
            artifact_kind="note",
            artifact_type=note_type,
            entity_id=slug,
            title=title,
            body=body,
            status="pending_revision",
            metadata=metadata,
        )
        written_paths.append(str(path))
        audit_entries.append(
            CompositionAuditEntry(
                subject_key=candidate.subject_key,
                display_name=candidate.display_name,
                should_write=True,
                note_type=note_type,
                title=title,
                target_path=str(path),
                confidence=confidence,
                supporting_draft_ids=list(candidate.draft_ids),
                notes=_string_list(proposal.get("notes")),
            )
        )
        _emit_progress(progress_log_path, phase="compose_primary_notes", event="candidate_written", subject=candidate.display_name, target_path=str(path), note_type=note_type, confidence=confidence)
    return CanonicalCompositionResult(
        written_paths=written_paths,
        audit_entries=audit_entries,
        skipped_candidates=skipped_candidates,
        warnings=_dedupe(warnings),
    )


def discover_primary_candidates(bundle: StagingImportBundle, *, max_candidates: int) -> list[CanonicalCompositionCandidate]:
    groups: dict[str, dict[str, Any]] = {}
    for draft in bundle.drafts:
        for candidate_value, source_kind, score in _draft_subject_candidates(draft):
            key = slugify(candidate_value)
            if len(key) < 3:
                continue
            record = groups.setdefault(
                key,
                {
                    "display_name": candidate_value,
                    "draft_ids": [],
                    "evidence_paths": [],
                    "evidence_labels": [],
                    "type_hints": [],
                    "aliases": [],
                    "score": 0.0,
                },
            )
            record["draft_ids"].append(draft.draft_id)
            record["evidence_paths"].append(draft.staging_path)
            record["evidence_labels"].append(source_kind)
            record["score"] += score
            type_hint = _draft_type_hint(draft)
            if type_hint:
                record["type_hints"].append(type_hint)
            record["aliases"].extend(_draft_aliases(draft))
            if source_kind == "title":
                record["display_name"] = candidate_value
    candidates: list[CanonicalCompositionCandidate] = []
    for key, record in groups.items():
        unique_drafts = _dedupe(record["draft_ids"])
        if len(unique_drafts) == 1 and record["score"] < 3.0:
            continue
        candidates.append(
            CanonicalCompositionCandidate(
                subject_key=key,
                display_name=record["display_name"],
                draft_ids=unique_drafts[:8],
                evidence_paths=_dedupe(record["evidence_paths"])[:8],
                evidence_labels=_dedupe(record["evidence_labels"]),
                type_hints=_dedupe(record["type_hints"]),
                aliases=_dedupe(record["aliases"]),
                score=float(record["score"]),
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:max_candidates]


def _compose_candidate(
    *,
    bundle: StagingImportBundle,
    candidate: CanonicalCompositionCandidate,
    drafts: list[LoadedStagedDraft],
    config: CompositionConfig,
) -> dict[str, Any] | None:
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Compose a primary Obsidian note only if the evidence supports a stable entity, place, or lore concept.",
        "preferred_output_language": _draft_language(drafts),
        "navigation_preference": {
            "prefer_short_navigable_title": True,
            "keep_formal_or_long_names_in_aliases": True,
        },
        "candidate": {
            "display_name": candidate.display_name,
            "subject_key": candidate.subject_key,
            "type_hints": candidate.type_hints,
            "aliases": candidate.aliases,
        },
        "drafts": [
            {
                "draft_id": draft.draft_id,
                "artifact_type": draft.artifact_type,
                "title": draft.frontmatter.get("title"),
                "canonical_subject": draft.frontmatter.get("canonical_subject"),
                "semantic_class": draft.frontmatter.get("semantic_class"),
                "source_section_title": draft.frontmatter.get("source_section_title"),
                "entities": draft.frontmatter.get("entities"),
                "topics": draft.frontmatter.get("topics"),
                "world_terms": draft.frontmatter.get("world_terms"),
                "character_refs": draft.frontmatter.get("character_refs"),
                "lore_refs": draft.frontmatter.get("lore_refs"),
                "body_excerpt": draft.body[:1500],
            }
            for draft in drafts
        ],
        "source_evidence": _build_source_evidence(bundle=bundle, candidate=candidate, drafts=drafts),
        "required_output_schema": {
            "note_type": "character|place|lore|magic|creature|faction|object|history|scene|chapter|skip",
            "title": "string",
            "slug": "string",
            "canonical_subject": "string",
            "aliases": ["string"],
            "semantic_class": "string",
            "summary": "string",
            "key_facts": ["string"],
            "related_subjects": ["string"],
            "confidence": 0.0,
            "notes": ["string"],
        },
        "rules": [
            "Return JSON only.",
            "Prefer a single strong primary note over many weak notes.",
            "Use primary note types only when evidence is stable enough.",
            "If the evidence is only a local subsection or weak fragment, return note_type='skip'.",
            "When possible, choose a short canonical title that matches how an Obsidian note should be navigated.",
            "Use aliases for alternate names, nicknames, or full forms.",
            "Write summary and key facts in the preferred output language when one is provided.",
            "Make the note useful as a primary Obsidian page, not as a staging fragment.",
        ],
    }
    try:
        source_evidence = payload["source_evidence"]
        source_excerpt_chars = sum(len(str(item.get("excerpt") or "")) for item in source_evidence)
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are composing canonical Obsidian notes for TextifAI bootstrap. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
            )
        )
    except TextProviderError:
        return None
    return extract_json_payload(response.text)


def _render_primary_note_body(
    *,
    title: str,
    note_type: str,
    summary: str,
    key_facts: list[str],
    related_subjects: list[str],
    source_drafts: list[LoadedStagedDraft],
) -> str:
    wikilink_targets = [subject for subject in [*related_subjects, title] if subject.strip()]
    summary = _wikify_plain_text(summary, wikilink_targets)
    key_facts = [_wikify_plain_text(item, wikilink_targets) for item in key_facts]
    lines = []
    if summary:
        lines.append("## Overview")
        lines.append("")
        lines.append(summary.strip())
        lines.append("")
    if key_facts:
        lines.append("## Key Facts")
        lines.append("")
        for item in key_facts:
            lines.append(f"- {item}")
        lines.append("")
    if related_subjects:
        lines.append("## Related")
        lines.append("")
        for subject in related_subjects:
            lines.append(f"- [[{subject}]]")
        lines.append("")
    if source_drafts:
        lines.append("## Source Basis")
        lines.append("")
        for draft in source_drafts[:6]:
            section = str(draft.frontmatter.get("source_section_title") or draft.frontmatter.get("title") or draft.draft_id).strip()
            lines.append(f"- {section} (`{Path(draft.staging_path).name}`)")
        lines.append("")
    return "\n".join(lines).strip()


def _build_source_evidence(
    *,
    bundle: StagingImportBundle,
    candidate: CanonicalCompositionCandidate,
    drafts: list[LoadedStagedDraft],
    max_sources: int = 4,
    max_excerpts_per_source: int = 2,
) -> list[dict[str, Any]]:
    source_paths: list[Path] = []
    all_terms = _dedupe(
        [
            candidate.display_name,
            *candidate.aliases,
            *[
                _clean_subject(draft.frontmatter.get("canonical_subject"))
                for draft in drafts
                if _clean_subject(draft.frontmatter.get("canonical_subject"))
            ],
            *[
                _clean_subject(draft.frontmatter.get("title"))
                for draft in drafts
                if _clean_subject(draft.frontmatter.get("title"))
            ],
        ]
    )
    candidate_term_keys = {slugify(term) for term in all_terms if term}
    evidence_drafts = list(drafts)
    for draft in bundle.drafts:
        if draft in evidence_drafts:
            continue
        body_text = draft.body.casefold()
        frontmatter_text = " ".join(str(value) for value in draft.frontmatter.values()).casefold()
        if any(term.casefold() in body_text or term.casefold() in frontmatter_text for term in all_terms if term):
            evidence_drafts.append(draft)
            continue
        draft_keys = {
            slugify(_clean_subject(draft.frontmatter.get("canonical_subject")) or ""),
            slugify(_clean_subject(draft.frontmatter.get("title")) or ""),
            *(slugify(item) for item in _split_values(draft.frontmatter.get("aliases"))),
            *(slugify(item) for item in _split_values(draft.frontmatter.get("character_refs"))),
            *(slugify(item) for item in _split_values(draft.frontmatter.get("lore_refs"))),
            *(slugify(item) for item in _split_values(draft.frontmatter.get("entities"))),
        }
        if candidate_term_keys & {key for key in draft_keys if key}:
            evidence_drafts.append(draft)
    for draft in evidence_drafts:
        if draft.provenance and draft.provenance.source_path:
            source_paths.append(Path(draft.provenance.source_path).expanduser())
    unique_paths: list[Path] = []
    seen: set[str] = set()
    for path in source_paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    terms = all_terms
    evidence: list[dict[str, Any]] = []
    for path in unique_paths[:max_sources]:
        if not path.exists():
            continue
        try:
            inventory = build_source_document_inventory(path.parent, explicit_paths=[path])
            source_texts = read_source_documents(inventory)
            document = inventory.documents[0] if inventory.documents else None
            source_text = source_texts.get(document.source_id, "") if document is not None else ""
        except Exception:
            source_text = ""
            document = None
        if not source_text.strip():
            continue
        excerpts = _extract_source_excerpts(source_text, terms, limit=max_excerpts_per_source)
        if not excerpts:
            continue
        evidence.append(
            {
                "source_path": str(path),
                "source_format": document.extension if document is not None else path.suffix.lstrip(".").casefold(),
                "dominant_language": document.dominant_language if document is not None else None,
                "matched_terms": _dedupe([term for excerpt in excerpts for term in excerpt["matched_terms"]]),
                "excerpts": excerpts,
            }
        )
    return evidence


def _extract_source_excerpts(text: str, terms: list[str], *, limit: int) -> list[dict[str, Any]]:
    if not text.strip() or not terms:
        return []
    blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(blocks) <= 1:
        blocks = [line.strip() for line in text.splitlines() if line.strip()]
    scored: list[tuple[int, dict[str, Any]]] = []
    normalized_terms = [(term, term.casefold()) for term in terms if term.strip()]
    for block in blocks:
        haystack = block.casefold()
        matched_terms = [term for term, lowered in normalized_terms if lowered in haystack]
        if not matched_terms:
            continue
        score = sum(haystack.count(term.casefold()) for term in matched_terms)
        scored.append(
            (
                score,
                {
                    "matched_terms": _dedupe(matched_terms),
                    "excerpt": block[:1600],
                },
            )
        )
    scored.sort(key=lambda item: (item[0], len(str(item[1]["excerpt"]))), reverse=True)
    return [item for _, item in scored[:limit]]


def _draft_language(drafts: list[LoadedStagedDraft]) -> str | None:
    candidates: list[str] = []
    for draft in drafts:
        frontmatter = draft.frontmatter
        for raw in (
            frontmatter.get("note_language"),
            frontmatter.get("dominant_language"),
            frontmatter.get("detected_languages"),
        ):
            if raw is None:
                continue
            if isinstance(raw, str):
                values = [item.strip() for item in raw.split(",")]
            else:
                values = [str(item).strip() for item in raw]
            for value in values:
                if value and value not in {"unknown", "mixed"}:
                    candidates.append(value)
    return candidates[0] if candidates else None


def _wikify_plain_text(text: str, targets: list[str]) -> str:
    result = text
    protected: dict[str, str] = {}

    def _protect(match: re.Match[str]) -> str:
        token = f"__LINK_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    result = re.sub(r"\[\[[^\]]+\]\]", _protect, result)
    for target in sorted({item.strip() for item in targets if item.strip()}, key=len, reverse=True):
        escaped = re.escape(target)
        pattern = re.compile(rf"(?<!\[\[)(?<![\w]){escaped}(?![\w])(?!\]\])")
        result = pattern.sub(f"[[{target}]]", result)
    for token, original in protected.items():
        result = result.replace(token, original)
    return result


def _aggregate_draft_metadata(drafts: list[LoadedStagedDraft]) -> dict[str, list[str]]:
    buckets = {
        "entities": [],
        "topics": [],
        "world_terms": [],
        "character_refs": [],
        "lore_refs": [],
    }
    for draft in drafts:
        frontmatter = draft.frontmatter
        for key in buckets:
            buckets[key].extend(_split_values(frontmatter.get(key)))
    return {key: _dedupe(values) for key, values in buckets.items()}


def _draft_subject_candidates(draft: LoadedStagedDraft) -> list[tuple[str, str, float]]:
    values: list[tuple[str, str, float]] = []
    frontmatter = draft.frontmatter
    for raw in (
        frontmatter.get("canonical_subject"),
        frontmatter.get("title"),
    ):
        candidate = _clean_subject(raw)
        if candidate:
            values.append((candidate, "title", 3.0))
    for field_name, score in (("character_refs", 2.0), ("lore_refs", 2.0), ("entities", 1.25), ("world_terms", 1.25), ("aliases", 1.5)):
        for item in _split_values(frontmatter.get(field_name)):
            candidate = _clean_subject(item)
            if candidate:
                values.append((candidate, field_name, score))
    return values


def _draft_aliases(draft: LoadedStagedDraft) -> list[str]:
    aliases = _split_values(draft.frontmatter.get("aliases"))
    canonical_subject = _clean_subject(draft.frontmatter.get("canonical_subject"))
    title = _clean_subject(draft.frontmatter.get("title"))
    if canonical_subject and slugify(canonical_subject) != slugify(title or ""):
        aliases.append(canonical_subject)
    return _dedupe(aliases)


def _select_candidate_drafts(
    candidate: CanonicalCompositionCandidate,
    drafts: list[LoadedStagedDraft],
    *,
    limit: int = 6,
) -> list[LoadedStagedDraft]:
    scored: list[tuple[float, LoadedStagedDraft]] = []
    for draft in drafts:
        score = _candidate_evidence_score(candidate, draft)
        if score <= 0.0:
            continue
        scored.append((score, draft))
    if not scored:
        return drafts[:limit]
    scored.sort(key=lambda item: (item[0], item[1].draft_id), reverse=True)
    return [draft for _, draft in scored[:limit]]


def _candidate_evidence_score(candidate: CanonicalCompositionCandidate, draft: LoadedStagedDraft) -> float:
    subject_key = slugify(candidate.display_name)
    title_key = slugify(str(draft.frontmatter.get("title") or ""))
    canonical_key = slugify(str(draft.frontmatter.get("canonical_subject") or ""))
    title_text = str(draft.frontmatter.get("title") or "")
    semantic_class = str(draft.frontmatter.get("semantic_class") or "").casefold()
    fragment_role = str(draft.frontmatter.get("fragment_role") or "").casefold()
    score = 0.0
    if canonical_key == subject_key:
        score += 5.0
    if title_key == subject_key:
        score += 4.0
    if draft.artifact_type == "character" and "character_profile" in semantic_class and "—" not in title_text and ":" not in title_text:
        score += 1.2
    if fragment_role in {"character_sheet", "place_sheet", "lore_sheet"} and "—" not in title_text and ":" not in title_text:
        score += 0.8
    if "—" in title_text or ":" in title_text:
        score -= 0.45
    for field_name, weight in (
        ("aliases", 2.4),
        ("character_refs", 2.0),
        ("lore_refs", 2.0),
        ("entities", 1.4),
        ("world_terms", 1.2),
    ):
        values = {slugify(item) for item in _split_values(draft.frontmatter.get(field_name))}
        if subject_key in values:
            score += weight
    lowered_body = draft.body.casefold()
    if candidate.display_name.casefold() in lowered_body:
        score += 0.8
    if candidate.display_name.casefold() in lowered_body[:320]:
        score += 1.0
    if slugify(draft.artifact_type) in {"character", "lore", "location", "magic", "creature", "faction", "object", "history", "scene", "chapter"}:
        score += 0.15
    return score


def _sanitize_aliases(
    aliases: list[str],
    *,
    title: str,
    canonical_subject: str,
    related_subjects: list[str],
    blocked_subject_keys: set[str] | None = None,
) -> list[str]:
    blocked = {slugify(title), slugify(canonical_subject), *(slugify(item) for item in related_subjects)}
    blocked.update(blocked_subject_keys or set())
    cleaned: list[str] = []
    for alias in aliases:
        normalized = str(alias).strip()
        if not normalized:
            continue
        if slugify(normalized) in blocked:
            continue
        if len(normalized.split()) > 4:
            continue
        if any(mark in normalized for mark in {":", ";", ",", "(", ")", "—"}):
            continue
        cleaned.append(normalized)
    return _dedupe(cleaned)


def _existing_primary_conflict_path(
    vault_root: str | Path,
    *,
    subject_key: str,
    title: str,
    canonical_subject: str,
    aliases: list[str],
) -> str | None:
    identity_keys = {slugify(subject_key), slugify(title), slugify(canonical_subject)}
    source = open_obsidian_source(vault_root)
    for note in source.reader.list_notes():
        frontmatter = note.frontmatter or {}
        if str(frontmatter.get("note_role") or "").strip().casefold() != "primary":
            continue
        note_keys = {
            slugify(note.title),
            slugify(note.note_id),
            slugify(str(frontmatter.get("canonical_subject") or "")),
        }
        if identity_keys & {key for key in note_keys if key}:
            return note.path
    return None


def _draft_type_hint(draft: LoadedStagedDraft) -> str | None:
    semantic_class = str(draft.frontmatter.get("semantic_class") or "").casefold()
    artifact_type = str(draft.artifact_type or "").casefold()
    if artifact_type == "character" or "character" in semantic_class:
        return "character"
    if semantic_class in {"world_entity", "place", "location"}:
        return "place"
    if artifact_type in {"magic", "creature", "faction", "object", "history"}:
        return artifact_type
    if semantic_class in {"magic", "magic_system", "mana", "spellcraft"}:
        return "magic"
    if semantic_class in {"creature", "beast", "spirit"}:
        return "creature"
    if semantic_class in {"faction", "institution", "organization", "council"}:
        return "faction"
    if semantic_class in {"object", "artifact", "relic"}:
        return "object"
    if semantic_class in {"history", "event_history", "era"}:
        return "history"
    if artifact_type == "lore":
        return "lore"
    if artifact_type in {"scene", "chapter"}:
        return artifact_type
    return None


def _clean_subject(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = _STRUCTURAL_PREFIX_RE.sub("", text).strip()
    if ":" in text:
        left, right = text.split(":", 1)
        right = right.strip()
        if len(slugify(right)) >= 4:
            text = right
    text = re.sub(r"^[#*_\-\s]+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(slugify(text)) < 3:
        return None
    return text


def _split_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def _coerce_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _proposal_is_substantial(proposal: dict[str, Any]) -> bool:
    summary = str(proposal.get("summary") or "").strip()
    key_facts = _string_list(proposal.get("key_facts"))
    related = _string_list(proposal.get("related_subjects"))
    return bool(summary and len(summary) >= 80) or len(key_facts) >= 2 or (len(key_facts) >= 1 and len(related) >= 2)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _emit_progress(path: str | None, **payload: Any) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
