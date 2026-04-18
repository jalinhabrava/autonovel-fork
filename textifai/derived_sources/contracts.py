from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DERIVED_SOURCE_FORMAT_CATALOG = (
    "txt",
    "md",
    "docx",
    "pdf",
    "doc",
)

DERIVED_EXTRACTION_METHOD_CATALOG = (
    "native_text",
    "light_extraction",
    "llm_assisted_derived",
    "llm_first_derived",
)

DERIVED_STRUCTURE_KIND_CATALOG = (
    "chapter",
    "scene",
    "character",
    "lore",
    "mixed_note",
    "project_note",
    "uncertain",
)

DERIVED_REVIEW_STATUS_CATALOG = (
    "usable",
    "usable_with_warnings",
    "pending",
    "needs_correction",
)


@dataclass(frozen=True)
class LLMEscalationDecision:
    required: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FormatExtractionProfile:
    source_format: str
    extraction_method: str
    is_native_text: bool
    text_fidelity_confidence: float
    structural_fidelity_confidence: float
    loss_risk_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm_escalation_required: bool = False
    llm_escalation_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ensure_catalog_value("source_format", self.source_format, DERIVED_SOURCE_FORMAT_CATALOG)
        _ensure_catalog_value("extraction_method", self.extraction_method, DERIVED_EXTRACTION_METHOD_CATALOG)
        if not 0.0 <= self.text_fidelity_confidence <= 1.0:
            raise ValueError("text_fidelity_confidence must be between 0 and 1")
        if not 0.0 <= self.structural_fidelity_confidence <= 1.0:
            raise ValueError("structural_fidelity_confidence must be between 0 and 1")


@dataclass(frozen=True)
class LightExtractionBlock:
    block_id: str
    text: str
    heading_text: str | None = None
    probable_kind: str = "uncertain"
    language: str | None = None
    mixed_content: bool = False
    confidence: float = 0.0
    boundary_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ensure_catalog_value("probable_kind", self.probable_kind, DERIVED_STRUCTURE_KIND_CATALOG)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class DerivedExtractionSeed:
    source_id: str
    source_path: str
    source_format: str
    raw_extracted_text: str
    lightweight_blocks: list[LightExtractionBlock] = field(default_factory=list)
    detected_languages: list[str] = field(default_factory=list)
    dominant_language: str | None = None
    has_mixed_language: bool = False
    quality_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_profile: FormatExtractionProfile | None = None
    checksum: str | None = None
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DerivedSegmentCandidate:
    candidate_id: str
    segment_text: str
    heading_text: str | None = None
    probable_kind: str = "uncertain"
    language: str | None = None
    confidence: float = 0.0
    mixed_content: bool = False
    boundary_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ensure_catalog_value("probable_kind", self.probable_kind, DERIVED_STRUCTURE_KIND_CATALOG)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class DerivedStructureSignals:
    recovered_headings: list[str] = field(default_factory=list)
    probable_block_order: list[str] = field(default_factory=list)
    recovered_lists: list[str] = field(default_factory=list)
    ordering_confidence: float = 0.0
    structure_warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(frozen=True)
class DerivedLossSignals:
    missing_structure_signals: list[str] = field(default_factory=list)
    paragraph_merge_signals: list[str] = field(default_factory=list)
    heading_loss_signals: list[str] = field(default_factory=list)
    ordering_uncertainty_signals: list[str] = field(default_factory=list)
    coverage_risk_notes: list[str] = field(default_factory=list)
    severity: str = "low"
    mixed_language_degradation: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DerivedLLMExtractionPayload:
    source_id: str
    source_format: str
    dominant_language: str | None
    detected_languages: list[str] = field(default_factory=list)
    has_mixed_language: bool = False
    overall_confidence: float = 0.0
    structural_confidence: float = 0.0
    content_mix_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    segment_candidates: list[DerivedSegmentCandidate] = field(default_factory=list)
    structure_signals: DerivedStructureSignals = field(default_factory=DerivedStructureSignals)
    loss_signals: DerivedLossSignals = field(default_factory=DerivedLossSignals)
    needs_manual_review: bool = False
    recognized_or_recovered_text: str = ""
    llm_escalation_reasons: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidatedDerivedExtraction:
    source_id: str
    source_format: str
    recognized_or_recovered_text: str
    segment_candidates: list[DerivedSegmentCandidate] = field(default_factory=list)
    structure_signals: DerivedStructureSignals = field(default_factory=DerivedStructureSignals)
    loss_signals: DerivedLossSignals = field(default_factory=DerivedLossSignals)
    detected_languages: list[str] = field(default_factory=list)
    dominant_language: str | None = None
    has_mixed_language: bool = False
    format_profile: FormatExtractionProfile | None = None
    llm_used: bool = False
    confidence: float = 0.0
    structural_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    requires_confirmation: bool = True
    review_status: str = "pending"


@dataclass(frozen=True)
class DerivedSourceReview:
    source_id: str
    review_status: str
    strict_confirmation_required: bool
    final_confidence: float
    llm_used: bool
    notes: list[str] = field(default_factory=list)
    llm_escalation_decision: LLMEscalationDecision = field(default_factory=lambda: LLMEscalationDecision(required=False))
    format_profile: FormatExtractionProfile | None = None
    loss_report: DerivedLossSignals = field(default_factory=DerivedLossSignals)
    recovery_report: DerivedStructureSignals = field(default_factory=DerivedStructureSignals)
    source_format: str | None = None
    needs_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_catalog_value("review_status", self.review_status, DERIVED_REVIEW_STATUS_CATALOG)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
