from __future__ import annotations

from dataclasses import dataclass

from textifai.import_review.contracts import ExtractionProfile, StagedArtifactReview
from textifai.import_review.extraction import extraction_requires_strict_confirmation, is_native_text
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle


SUPPORTED_STABLE_ARTIFACT_TYPES = {"character", "lore", "scene", "chapter"}


@dataclass(frozen=True)
class ReviewPolicy:
    native_accept_threshold: float = 0.8
    derived_accept_threshold: float = 0.9
    native_pending_threshold: float = 0.65
    derived_pending_threshold: float = 0.75


def review_staged_artifact(
    bundle: StagingImportBundle,
    draft: LoadedStagedDraft,
    *,
    policy: ReviewPolicy | None = None,
    llm_suggestions: list[str] | None = None,
) -> StagedArtifactReview:
    policy = policy or ReviewPolicy()
    notes: list[str] = []
    if llm_suggestions:
        notes.extend([f"llm:{suggestion}" for suggestion in llm_suggestions if suggestion.strip()])

    provenance_ok = bool(draft.provenance and draft.provenance.source_id and draft.provenance.source_path and draft.provenance.source_checksum)
    coverage_ok = _coverage_ok(bundle, draft)
    extraction_profile = draft.extraction_profile
    strict_confirmation = extraction_requires_strict_confirmation(extraction_profile)

    if not draft.body.strip():
        notes.append("empty_body")
        return _review_result(
            draft,
            "rejected",
            notes,
            provenance_ok,
            coverage_ok,
            extraction_profile,
            strict_confirmation,
        )

    if draft.artifact_type not in SUPPORTED_STABLE_ARTIFACT_TYPES:
        notes.append("unsupported_artifact_type")
        return _review_result(
            draft,
            "needs_correction",
            notes,
            provenance_ok,
            coverage_ok,
            extraction_profile,
            strict_confirmation,
        )

    if not provenance_ok:
        notes.append("provenance_incomplete")
    if not coverage_ok:
        notes.append("coverage_incomplete")
    if extraction_profile is None:
        notes.append("missing_extraction_profile")
        strict_confirmation = True

    if extraction_profile is not None:
        notes.extend(extraction_profile.warnings)
        notes.extend(extraction_profile.loss_risk_flags)
        if not is_native_text(extraction_profile):
            notes.append(f"derived_source:{extraction_profile.source_format}")

    if strict_confirmation:
        review_status = "pending"
        if extraction_profile is not None and (
            extraction_profile.extraction_confidence < policy.derived_pending_threshold
            or extraction_profile.structural_confidence < policy.derived_pending_threshold
        ):
            review_status = "needs_correction"
    elif extraction_profile is not None and (
        extraction_profile.extraction_confidence < policy.native_pending_threshold
        or extraction_profile.structural_confidence < policy.native_pending_threshold
    ):
        review_status = "pending"
    else:
        review_status = "accepted"

    if not provenance_ok and review_status == "accepted":
        review_status = "pending"
    if not coverage_ok and review_status == "accepted":
        review_status = "pending"

    return _review_result(
        draft,
        review_status,
        notes,
        provenance_ok,
        coverage_ok,
        extraction_profile,
        strict_confirmation,
    )


def review_staged_import(
    bundle: StagingImportBundle,
    *,
    policy: ReviewPolicy | None = None,
    llm_suggestions_by_draft: dict[str, list[str]] | None = None,
) -> list[StagedArtifactReview]:
    reviews: list[StagedArtifactReview] = []
    for draft in bundle.drafts:
        reviews.append(
            review_staged_artifact(
                bundle,
                draft,
                policy=policy,
                llm_suggestions=(llm_suggestions_by_draft or {}).get(draft.draft_id),
            )
        )
    return reviews


def _coverage_ok(bundle: StagingImportBundle, draft: LoadedStagedDraft) -> bool:
    manifest_draft = draft.manifest_draft
    if not manifest_draft:
        return False
    provenance = manifest_draft.get("provenance") or {}
    fragment_ids = set(str(value) for value in provenance.get("fragment_ids", []))
    if not fragment_ids:
        return False
    plan_drafts = bundle.manifest.get("plan", {}).get("drafts", [])
    return any(str(item.get("draft_id")) == draft.draft_id for item in plan_drafts)


def _review_result(
    draft: LoadedStagedDraft,
    review_status: str,
    notes: list[str],
    provenance_ok: bool,
    coverage_ok: bool,
    extraction_profile: ExtractionProfile | None,
    strict_confirmation: bool,
) -> StagedArtifactReview:
    return StagedArtifactReview(
        draft_id=draft.draft_id,
        staging_path=draft.staging_path,
        artifact_type=draft.artifact_type,
        review_status=review_status,
        review_notes=list(dict.fromkeys(notes)),
        provenance_ok=provenance_ok,
        coverage_ok=coverage_ok,
        extraction_profile=extraction_profile,
        requires_strict_confirmation=strict_confirmation,
    )
