from __future__ import annotations

from dataclasses import dataclass, field

from textifai.bootstrap.contracts import ImportProvenance


EXTRACTION_MODE_CATALOG = (
    "native_text",
    "derived_text_extraction",
)

REVIEW_STATUS_CATALOG = (
    "accepted",
    "rejected",
    "pending",
    "needs_correction",
)

PROMOTION_DECISION_CATALOG = (
    "promote",
    "hold",
    "reject",
    "blocked_by_conflict",
)

OVERWRITE_MODE_CATALOG = (
    "forbid",
    "require_confirm",
    "allow_new_version",
)

STABLE_ARTIFACT_KIND_CATALOG = (
    "note",
    "root_artifact",
)


@dataclass(frozen=True)
class ExtractionProfile:
    source_format: str
    extraction_mode: str
    extraction_confidence: float
    structural_confidence: float
    warnings: list[str] = field(default_factory=list)
    loss_risk_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ensure_catalog_value("extraction_mode", self.extraction_mode, EXTRACTION_MODE_CATALOG)
        if not 0.0 <= self.extraction_confidence <= 1.0:
            raise ValueError("extraction_confidence must be between 0 and 1")
        if not 0.0 <= self.structural_confidence <= 1.0:
            raise ValueError("structural_confidence must be between 0 and 1")


@dataclass(frozen=True)
class StagedArtifactReview:
    draft_id: str
    staging_path: str
    artifact_type: str
    review_status: str
    review_notes: list[str] = field(default_factory=list)
    provenance_ok: bool = False
    coverage_ok: bool = False
    extraction_profile: ExtractionProfile | None = None
    requires_strict_confirmation: bool = False

    def __post_init__(self) -> None:
        _ensure_catalog_value("review_status", self.review_status, REVIEW_STATUS_CATALOG)


@dataclass(frozen=True)
class PromotionDecision:
    draft_id: str
    decision: str
    target_artifact_type: str
    target_slug: str
    target_path: str
    overwrite_mode: str
    reason: str

    def __post_init__(self) -> None:
        _ensure_catalog_value("decision", self.decision, PROMOTION_DECISION_CATALOG)
        _ensure_catalog_value("overwrite_mode", self.overwrite_mode, OVERWRITE_MODE_CATALOG)


@dataclass(frozen=True)
class PromotionPlan:
    plan_id: str
    decisions: list[PromotionDecision] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StableArtifactWrite:
    target_path: str
    artifact_kind: str
    title: str
    body: str
    metadata: dict
    provenance: ImportProvenance
    source_staging_draft: str

    def __post_init__(self) -> None:
        _ensure_catalog_value("artifact_kind", self.artifact_kind, STABLE_ARTIFACT_KIND_CATALOG)


@dataclass(frozen=True)
class ImportAuditEntry:
    entry_id: str
    draft_id: str
    action: str
    timestamp: str
    review_status: str
    stable_target_path: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PromotionResult:
    plan_id: str
    promoted_paths: list[str] = field(default_factory=list)
    pending_drafts: list[str] = field(default_factory=list)
    rejected_drafts: list[str] = field(default_factory=list)
    blocked_drafts: list[str] = field(default_factory=list)
    audit_entries: list[ImportAuditEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
