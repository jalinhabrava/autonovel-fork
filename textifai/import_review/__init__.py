from __future__ import annotations

from pathlib import Path

from textifai.import_review.audit import write_import_audit
from textifai.import_review.contracts import (
    EXTRACTION_MODE_CATALOG,
    ExtractionProfile,
    ImportAuditEntry,
    PromotionDecision,
    PromotionPlan,
    PromotionResult,
    StableArtifactWrite,
    StagedArtifactReview,
)
from textifai.import_review.promotion_plan import build_promotion_plan
from textifai.import_review.reviewer import ReviewPolicy, review_staged_artifact, review_staged_import
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle, load_staging_import_bundle
from textifai.import_review.stable_writer import promote_controlled_import as _promote_controlled_import

promote_controlled_import = _promote_controlled_import


def review_import_stage(vault_root: str | Path, plan_id: str | None = None, *, policy: ReviewPolicy | None = None) -> tuple[StagingImportBundle, list[StagedArtifactReview], PromotionPlan]:
    bundle = load_staging_import_bundle(vault_root, plan_id=plan_id)
    reviews = review_staged_import(bundle, policy=policy)
    plan = build_promotion_plan(bundle, reviews, stable_root=bundle.vault_root)
    return bundle, reviews, plan


def promote_reviewed_import(
    vault_root: str | Path,
    plan_id: str | None = None,
    *,
    policy: ReviewPolicy | None = None,
    confirmed: bool = False,
) -> PromotionResult:
    bundle, reviews, plan = review_import_stage(vault_root, plan_id=plan_id, policy=policy)
    result = _promote_controlled_import(bundle=bundle, reviews=reviews, plan=plan, confirmed=confirmed)
    write_import_audit(bundle=bundle, plan=plan, result=result)
    return result


__all__ = [
    "EXTRACTION_MODE_CATALOG",
    "ExtractionProfile",
    "ImportAuditEntry",
    "LoadedStagedDraft",
    "PromotionDecision",
    "PromotionPlan",
    "PromotionResult",
    "ReviewPolicy",
    "StableArtifactWrite",
    "StagedArtifactReview",
    "StagingImportBundle",
    "load_staging_import_bundle",
    "promote_controlled_import",
    "promote_reviewed_import",
    "review_import_stage",
    "review_staged_artifact",
    "review_staged_import",
    "write_import_audit",
]
