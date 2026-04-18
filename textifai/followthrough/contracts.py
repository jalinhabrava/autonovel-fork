from __future__ import annotations

from dataclasses import dataclass, field

from textifai.editorial.contracts import BeatOutline, EditorialStructuringResult, NarrationPrep, RevisionIntent, StoryFacts

VALIDATION_STATUS_CATALOG = (
    "pending_validation",
    "validated",
    "validated_with_notes",
    "insufficient_structure",
    "rejected",
)

VOICE_MODE_CATALOG = (
    "inherit_project_voice",
    "emphasize_character_voice",
    "neutral",
)

CONTINUITY_SCOPE_CATALOG = (
    "scene_only",
    "chapter_local",
    "project_wide",
)

CANON_MODE_CATALOG = (
    "validated_only",
    "validated_plus_related",
)

REVIEW_FOCUS_CATALOG = (
    "structure",
    "canon",
    "voice",
    "continuity",
    "motivation",
    "tone",
    "conflict",
    "handoff",
)

NEXT_RECOMMENDED_STEP_CATALOG = (
    "validate_structure",
    "prepare_narration",
    "prepare_review",
    "continue_followup",
    "clarify_structure",
    "done",
)


@dataclass(frozen=True)
class ValidatedStructuringState:
    source_result_kind: str
    source_structuring_result: EditorialStructuringResult
    validation_status: str
    validated_by_user: bool
    validation_notes: list[str] = field(default_factory=list)
    validated_story_facts: StoryFacts | None = None
    validated_beat_outline: BeatOutline | None = None
    validated_revision_intent: RevisionIntent | None = None
    ready_for_narration_prep: bool = False
    ready_for_review_handoff: bool = False

    def __post_init__(self) -> None:
        if self.validation_status not in VALIDATION_STATUS_CATALOG:
            raise ValueError(f"Unsupported validation_status: {self.validation_status}")
        if self.validation_status == "validated" and not self.validated_by_user:
            raise ValueError("validated states must be explicitly validated by the user")
        if self.validation_status in {"insufficient_structure", "rejected"} and (
            self.ready_for_narration_prep or self.ready_for_review_handoff
        ):
            raise ValueError("insufficient or rejected states cannot be marked ready for handoff")


@dataclass(frozen=True)
class NarrationRequest:
    source_kind: str
    validated_structuring_state: ValidatedStructuringState
    target_language: str | None
    voice_mode: str
    continuity_scope: str
    canon_mode: str
    constraints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.voice_mode not in VOICE_MODE_CATALOG:
            raise ValueError(f"Unsupported voice_mode: {self.voice_mode}")
        if self.continuity_scope not in CONTINUITY_SCOPE_CATALOG:
            raise ValueError(f"Unsupported continuity_scope: {self.continuity_scope}")
        if self.canon_mode not in CANON_MODE_CATALOG:
            raise ValueError(f"Unsupported canon_mode: {self.canon_mode}")


@dataclass(frozen=True)
class ReviewReadyPackage:
    source_kind: str
    validated_structuring_state: ValidatedStructuringState
    narration_prep: NarrationPrep | None
    review_focus: list[str] = field(default_factory=list)
    preserve_constraints: list[str] = field(default_factory=list)
    related_artifacts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for item in self.review_focus:
            if item not in REVIEW_FOCUS_CATALOG:
                raise ValueError(f"Unsupported review_focus: {item}")


@dataclass(frozen=True)
class FollowThroughResult:
    validated_structuring_state: ValidatedStructuringState | None
    narration_request: NarrationRequest | None
    narration_prep: NarrationPrep | None
    review_ready_package: ReviewReadyPackage | None
    next_recommended_step: str
    ready_for_user_confirmation: bool

    def __post_init__(self) -> None:
        if self.next_recommended_step not in NEXT_RECOMMENDED_STEP_CATALOG:
            raise ValueError(f"Unsupported next_recommended_step: {self.next_recommended_step}")
