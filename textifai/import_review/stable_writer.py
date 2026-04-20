from __future__ import annotations

from pathlib import Path

from textifai.import_review.contracts import ImportAuditEntry, PromotionDecision, PromotionPlan, PromotionResult, StableArtifactWrite
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle
from vault.notes import write_artifact_payload


def promote_controlled_import(
    *,
    bundle: StagingImportBundle,
    reviews: list,
    plan: PromotionPlan,
    confirmed: bool = False,
) -> PromotionResult:
    review_by_draft = {review.draft_id: review for review in reviews}
    draft_by_id = {draft.draft_id: draft for draft in bundle.drafts}
    promoted_paths: list[str] = []
    pending_drafts: list[str] = []
    rejected_drafts: list[str] = []
    blocked_drafts: list[str] = []
    audit_entries: list[ImportAuditEntry] = []

    for decision in plan.decisions:
        draft = draft_by_id[decision.draft_id]
        review = review_by_draft.get(decision.draft_id)
        if decision.decision == "promote" and review is not None:
            if decision.overwrite_mode == "require_confirm" and not confirmed:
                pending_drafts.append(decision.draft_id)
                audit_entries.append(
                    _audit(
                        decision.draft_id,
                        "left_pending",
                        review.review_status,
                        None,
                        [decision.reason, "confirmation_required"],
                    )
                )
                continue
            write = _build_stable_write(draft, decision)
            path = _write_stable_artifact(bundle.vault_root, write)
            promoted_paths.append(str(path))
            audit_entries.append(_audit(decision.draft_id, "promoted", review.review_status, str(path), [*review.review_notes, f"promoted_to:{path}"]))
            continue
        if decision.decision == "reject":
            rejected_drafts.append(decision.draft_id)
            audit_entries.append(_audit(decision.draft_id, "rejected", review.review_status if review else "rejected", None, [decision.reason]))
            continue
        if decision.decision == "blocked_by_conflict":
            blocked_drafts.append(decision.draft_id)
            audit_entries.append(_audit(decision.draft_id, "blocked", review.review_status if review else "pending", None, [decision.reason]))
            continue
        pending_drafts.append(decision.draft_id)
        audit_entries.append(_audit(decision.draft_id, "left_pending", review.review_status if review else "pending", None, [decision.reason]))

    return PromotionResult(
        plan_id=plan.plan_id,
        promoted_paths=promoted_paths,
        pending_drafts=pending_drafts,
        rejected_drafts=rejected_drafts,
        blocked_drafts=blocked_drafts,
        audit_entries=audit_entries,
        warnings=list(plan.warnings),
    )


def _build_stable_write(
    draft: LoadedStagedDraft,
    decision: PromotionDecision,
) -> StableArtifactWrite:
    provenance = draft.provenance
    if provenance is None:
        raise ValueError(f"Missing provenance for staged draft: {draft.draft_id}")
    return StableArtifactWrite(
        target_path=decision.target_path,
        artifact_kind="note",
        title=draft.frontmatter.get("title") or Path(draft.target_path).stem.replace("_", " ").title(),
        body=draft.body.strip(),
        metadata={
            "source_staging_draft": draft.draft_id,
            "promotion_plan_target": decision.target_path,
            "import_review_state": "promoted",
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "supporting",
            "source_format": provenance.source_format,
            "extraction_mode": provenance.extraction_mode,
            "extraction_confidence": provenance.extraction_confidence,
            "structural_confidence": provenance.structural_confidence,
            "canonical_subject": draft.frontmatter.get("canonical_subject"),
            "semantic_class": draft.frontmatter.get("semantic_class"),
            "source_section_title": draft.frontmatter.get("source_section_title"),
            "fragment_role": draft.frontmatter.get("fragment_role"),
            "aliases": draft.frontmatter.get("aliases"),
            "related_subjects": draft.frontmatter.get("related_subjects"),
            "entities": draft.frontmatter.get("entities"),
            "topics": draft.frontmatter.get("topics"),
            "world_terms": draft.frontmatter.get("world_terms"),
            "character_refs": draft.frontmatter.get("character_refs"),
            "lore_refs": draft.frontmatter.get("lore_refs"),
        },
        provenance=provenance,
        source_staging_draft=draft.draft_id,
    )


def _write_stable_artifact(vault_root: str, write: StableArtifactWrite) -> Path:
    if write.artifact_kind != "note":
        raise ValueError(f"Unsupported stable write artifact kind: {write.artifact_kind}")
    if write.provenance.source_format and write.provenance.source_format not in {"md", "txt"}:
        if write.provenance.extraction_confidence < 0.9 or write.provenance.structural_confidence < 0.9:
            raise ValueError("Derived extraction is too risky for silent promotion.")
    target = Path(write.target_path)
    if target.exists():
        raise FileExistsError(f"Stable target already exists: {target}")
    path = write_artifact_payload(
        vault_root,
        artifact_kind="note",
        artifact_type=_note_type_from_path(target),
        entity_id=target.stem,
        title=write.title,
        body=write.body,
        status="pending_revision",
        metadata=write.metadata,
    )
    if Path(path).resolve() != target.resolve():
        raise ValueError(f"Stable write path mismatch: expected {target}, wrote {path}")
    return path


def _note_type_from_path(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    if "profiles" in parts:
        return "character"
    if "lore" in parts:
        return "lore"
    if "places" in parts:
        return "place"
    if "scenes" in parts:
        return "scene"
    if "chapters" in parts:
        return "chapter"
    raise ValueError(f"Unable to infer stable note type from path: {path}")


def _audit(draft_id: str, action: str, review_status: str, stable_target_path: str | None, notes: list[str]) -> ImportAuditEntry:
    from datetime import datetime, timezone

    return ImportAuditEntry(
        entry_id=f"{draft_id}__{action}",
        draft_id=draft_id,
        action=action,
        timestamp=datetime.now(timezone.utc).isoformat(),
        review_status=review_status,
        stable_target_path=stable_target_path,
        notes=list(dict.fromkeys(notes)),
    )
