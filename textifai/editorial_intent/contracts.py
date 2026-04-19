from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textifai.vaerl.contracts import EntityHint


EDITORIAL_REQUEST_TYPE_CATALOG = (
    "narrative_facts",
    "structuring_request",
    "editorial_revision",
    "narration_preparation",
    "contextual_followup",
    "mixed_editorial_request",
    "validation_request",
    "narration_handoff",
    "review_handoff",
    "structured_followup",
)

FOLLOWUP_MODE_CATALOG = (
    "none",
    "reuse_recent_target",
    "prefer_candidate_targets",
    "require_clarification",
)

PRESERVE_CONSTRAINT_CATALOG = (
    "preserve_character_voice",
    "preserve_validated_canon",
    "preserve_character_empathy",
    "preserve_scene_conflict",
    "preserve_relational_coherence",
    "preserve_ren_care_pattern",
)

EDITORIAL_GOAL_CATALOG = (
    "extract_story_facts",
    "structure_scene",
    "prepare_for_narration",
    "prepare_for_review",
    "extend_conflict",
    "align_tone",
    "clarify_motivation",
    "anchor_canon",
    "shape_comedic_scene_with_relational_subtext",
    "choose_dual_effect_closing_beat",
    "revise_voice_and_relational_dynamic",
    "control_subtext_explicitness",
    "guide_sera_intimate_but_guarded_voice",
    "control_closeness_without_confession",
    "balance_light_tone_with_relational_weight",
    "evaluate_symbolic_canon_link",
    "test_deformed_historical_continuity",
    "separate_plausible_symbolism_from_hard_canon",
)

SEMANTIC_BASIS_CATALOG = (
    "author_understanding_validated",
    "recognized_intent",
    "narrative_signals",
    "surface_fallback",
    "mixed",
)


@dataclass(frozen=True)
class CandidateTarget:
    target_id: str
    target_type: str
    confidence: float


@dataclass(frozen=True)
class EditorialIntent:
    request_type: str
    confidence: float
    semantic_basis: str = "surface_fallback"
    target_scope: str | None = None
    resolved_target_type: str | None = None
    resolved_target_id: str | None = None
    candidate_targets: list[CandidateTarget] = field(default_factory=list)
    entity_hints: list[EntityHint] = field(default_factory=list)
    followup_mode: str = "none"
    preserve_constraints: list[str] = field(default_factory=list)
    editorial_goals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("request_type", self.request_type, EDITORIAL_REQUEST_TYPE_CATALOG)
        _ensure_catalog_value("semantic_basis", self.semantic_basis, SEMANTIC_BASIS_CATALOG)
        _ensure_catalog_value("followup_mode", self.followup_mode, FOLLOWUP_MODE_CATALOG)
        for constraint in self.preserve_constraints:
            _ensure_catalog_value("preserve_constraint", constraint, PRESERVE_CONSTRAINT_CATALOG)
        for goal in self.editorial_goals:
            _ensure_catalog_value("editorial_goal", goal, EDITORIAL_GOAL_CATALOG)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
