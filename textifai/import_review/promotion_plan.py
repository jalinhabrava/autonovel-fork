from __future__ import annotations

import uuid
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from textifai.import_review.contracts import PromotionDecision, PromotionPlan
from textifai.import_review.reviewer import SUPPORTED_STABLE_ARTIFACT_TYPES
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle
from vault.notes import NOTE_TYPE_DIRS


def build_promotion_plan(
    bundle: StagingImportBundle,
    reviews: list,
    *,
    stable_root: str | Path | None = None,
) -> PromotionPlan:
    stable_root = Path(stable_root or bundle.vault_root).expanduser().resolve()
    adapter = VaultProjectAdapter(stable_root)
    review_by_draft = {review.draft_id: review for review in reviews}
    decisions: list[PromotionDecision] = []
    conflicts: list[str] = []
    warnings: list[str] = []
    requires_confirmation = False
    reserved_target_paths: set[str] = set()

    for draft in bundle.drafts:
        review = review_by_draft.get(draft.draft_id)
        if review is None:
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="hold",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=_stable_target_path(adapter, draft),
                overwrite_mode="forbid",
                reason="missing_review",
            )
            decisions.append(decision)
            requires_confirmation = True
            continue

        target_path = _stable_target_path(adapter, draft)
        if draft.artifact_type not in SUPPORTED_STABLE_ARTIFACT_TYPES:
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="hold",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="forbid",
                reason="unsupported_artifact_type",
            )
            decisions.append(decision)
            requires_confirmation = True
            continue

        if str(draft.frontmatter.get("promotion_status") or "staged_candidate") != "eligible_for_promotion":
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="promote",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="require_confirm",
                reason="staging_candidate_requires_confirmation",
            )
            decisions.append(decision)
            requires_confirmation = True
            continue

        if target_path.exists():
            conflict = f"{draft.draft_id}: target path exists -> {target_path}"
            conflicts.append(conflict)
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="blocked_by_conflict",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="require_confirm",
                reason="target_path_exists",
            )
            decisions.append(decision)
            requires_confirmation = True
            continue

        target_key = str(target_path)
        if target_key in reserved_target_paths:
            conflict = f"{draft.draft_id}: target path duplicated in plan -> {target_path}"
            conflicts.append(conflict)
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="blocked_by_conflict",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="require_confirm",
                reason="duplicate_target_path_in_plan",
            )
            decisions.append(decision)
            requires_confirmation = True
            continue

        if review.review_status == "accepted":
            overwrite_mode = "forbid"
            if review.requires_strict_confirmation:
                overwrite_mode = "require_confirm"
                requires_confirmation = True
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="promote",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode=overwrite_mode,
                reason="accepted",
            )
        elif review.review_status == "rejected":
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="reject",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="forbid",
                reason="review_rejected",
            )
        else:
            decision = PromotionDecision(
                draft_id=draft.draft_id,
                decision="hold",
                target_artifact_type=draft.artifact_type,
                target_slug=draft.target_slug,
                target_path=str(target_path),
                overwrite_mode="forbid",
                reason=review.review_status,
            )
            requires_confirmation = True
            if review.review_notes:
                warnings.extend(review.review_notes)
        decisions.append(decision)
        if decision.decision == "promote":
            reserved_target_paths.add(target_key)

    return PromotionPlan(
        plan_id=uuid.uuid4().hex[:12],
        decisions=decisions,
        conflicts=conflicts,
        requires_confirmation=requires_confirmation or bool(conflicts),
        warnings=_dedupe(warnings),
    )


def _stable_target_path(adapter: VaultProjectAdapter, draft: LoadedStagedDraft) -> Path:
    if draft.artifact_type == "character":
        return adapter.note_path("character", draft.target_slug)
    if draft.artifact_type == "lore":
        return adapter.note_path("lore", draft.target_slug)
    if draft.artifact_type == "scene":
        return adapter.note_path("scene", draft.target_slug)
    if draft.artifact_type == "chapter":
        return adapter.note_path("chapter", draft.target_slug)
    return adapter.vault_root / "99_System" / "import_review" / f"{draft.target_slug}.md"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
