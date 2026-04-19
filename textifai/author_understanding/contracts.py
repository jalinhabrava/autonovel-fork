from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityHint


AUTHOR_INTENT_TYPE_CATALOG = (
    "unknown",
    "narrative_facts",
    "editorial_revision",
    "structuring_request",
    "narration_preparation",
    "contextual_followup",
    "validation_request",
    "narration_handoff",
    "review_handoff",
    "structured_followup",
    "mixed_request",
)

AUTHOR_UNDERSTANDING_ROUTE_CATALOG = (
    "expert_bypass",
    "trivial_contextual_case",
    "freeform_author_request",
)

MIXED_PART_TYPE_CATALOG = (
    "narrative_content",
    "revision",
    "preserve",
    "meta_instruction",
    "followup_reference",
    "narration_prep",
    "review_handoff",
    "validation_request",
    "mixed",
)

ANALYSIS_SOURCE_CATALOG = (
    "rule_based",
    "llm_assisted",
    "hybrid",
    "fallback",
)


@dataclass(frozen=True)
class MixedRequestPart:
    part_type: str
    text: str
    confidence: float

    def __post_init__(self) -> None:
        _ensure_catalog_value("part_type", self.part_type, MIXED_PART_TYPE_CATALOG)


@dataclass(frozen=True)
class MixedRequestAnalysis:
    source_text: str
    parts: list[MixedRequestPart] = field(default_factory=list)


@dataclass(frozen=True)
class DisambiguationResult:
    candidate_targets: list[CandidateTarget] = field(default_factory=list)
    preferred_target: CandidateTarget | None = None
    confidence: float = 0.0
    reason: str = ""
    requires_user_confirmation: bool = False


@dataclass(frozen=True)
class LLMAuthorUnderstandingPayload:
    raw_text: str
    provider_name: str | None
    model: str | None
    primary_intent_type: str
    secondary_intent_types: list[str] = field(default_factory=list)
    confidence: float = 0.0
    has_mixed_request: bool = False
    author_goal_signals: list[str] = field(default_factory=list)
    preserve_signals: list[str] = field(default_factory=list)
    change_signals: list[str] = field(default_factory=list)
    entity_hints: list[EntityHint] = field(default_factory=list)
    followup_reference_text: str | None = None
    narrative_content_text: str | None = None
    meta_instruction_text: str | None = None
    editorial_diagnosis: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_reason: str | None = None
    parts: list[MixedRequestPart] = field(default_factory=list)
    candidate_targets: list[CandidateTarget] = field(default_factory=list)
    preferred_target: CandidateTarget | None = None
    disambiguation_reason: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("primary_intent_type", self.primary_intent_type, AUTHOR_INTENT_TYPE_CATALOG)
        for item in self.secondary_intent_types:
            _ensure_catalog_value("secondary_intent_type", item, AUTHOR_INTENT_TYPE_CATALOG)
        for part in self.parts:
            _ensure_catalog_value("part_type", part.part_type, MIXED_PART_TYPE_CATALOG)


LLMInterpretationResult = LLMAuthorUnderstandingPayload


@dataclass(frozen=True)
class AuthorIntentInterpretation:
    primary_intent_type: str
    secondary_intent_types: list[str] = field(default_factory=list)
    confidence: float = 0.0
    has_mixed_request: bool = False
    author_goal_signals: list[str] = field(default_factory=list)
    preserve_signals: list[str] = field(default_factory=list)
    change_signals: list[str] = field(default_factory=list)
    entity_hints: list[EntityHint] = field(default_factory=list)
    followup_reference_text: str | None = None
    narrative_content_text: str | None = None
    meta_instruction_text: str | None = None
    editorial_diagnosis: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_reason: str | None = None
    mixed_request_analysis: MixedRequestAnalysis | None = None
    llm_interpretation: LLMInterpretationResult | None = None
    disambiguation: DisambiguationResult | None = None
    source: str = "rule_based"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("primary_intent_type", self.primary_intent_type, AUTHOR_INTENT_TYPE_CATALOG)
        for item in self.secondary_intent_types:
            _ensure_catalog_value("secondary_intent_type", item, AUTHOR_INTENT_TYPE_CATALOG)
        _ensure_catalog_value("analysis_source", self.source, ANALYSIS_SOURCE_CATALOG)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
