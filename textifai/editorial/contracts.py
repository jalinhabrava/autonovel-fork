from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textifai.vaerl.contracts import (
    ARTIFACT_RELATION_CATALOG,
    ENTITY_KIND_CATALOG,
    EntityResolutionResult,
    RelatedArtifactSuggestion as ArtifactSuggestion,
)

STORY_FACT_KIND_CATALOG = (
    "event",
    "state",
    "conflict",
    "goal",
    "constraint",
    "outcome",
)

BEAT_TENSION_LEVEL_CATALOG = (
    "low",
    "rising",
    "high",
    "peak",
    "release",
)

EDITORIAL_RESULT_KIND_CATALOG = (
    "story_facts",
    "beat_outline",
    "revision_intent",
    "narration_prep",
    "mixed",
)

@dataclass(frozen=True)
class StoryFactItem:
    text: str
    fact_kind: str
    source: str

    def __post_init__(self) -> None:
        _ensure_catalog_value("fact_kind", self.fact_kind, STORY_FACT_KIND_CATALOG)
        if self.source not in {"explicit_input", "system_inference"}:
            raise ValueError(f"Unsupported source: {self.source}")


@dataclass(frozen=True)
class StoryFacts:
    """Structured narrative facts extracted from author input.

    `goals` refers to in-world character or scene goals stated or strongly implied by
    the source narrative situation, not to the author's meta-intent.
    """

    source_text: str
    language: str
    characters_involved: list[str] = field(default_factory=list)
    locations_involved: list[str] = field(default_factory=list)
    objects_involved: list[str] = field(default_factory=list)
    premise: str | None = None
    core_conflict: str | None = None
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    canon_constraints: list[str] = field(default_factory=list)
    explicit_facts: list[StoryFactItem] = field(default_factory=list)
    inferred_facts: list[StoryFactItem] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BeatItem:
    index: int
    summary: str
    purpose: str
    characters: list[str] = field(default_factory=list)
    tension_level: str = "low"

    def __post_init__(self) -> None:
        _ensure_catalog_value("tension_level", self.tension_level, BEAT_TENSION_LEVEL_CATALOG)


@dataclass(frozen=True)
class BeatOutline:
    source_kind: str
    title: str | None = None
    beats: list[BeatItem] = field(default_factory=list)
    emotional_arc: list[str] = field(default_factory=list)
    target_language: str | None = None
    continuity_notes: list[str] = field(default_factory=list)
    canon_checks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RevisionIntent:
    source_text: str
    target_scope: str | None = None
    issue_types: list[str] = field(default_factory=list)
    desired_changes: list[str] = field(default_factory=list)
    must_preserve: list[str] = field(default_factory=list)
    priority: str | None = None
    target_hint: str | None = None


@dataclass(frozen=True)
class NarrationPrep:
    """Context package for later narration. This prepares; it does not narrate."""

    source_kind: str
    target_language: str
    explanation_language: str
    voice_artifacts: list[str] = field(default_factory=list)
    canon_artifacts: list[str] = field(default_factory=list)
    continuity_artifacts: list[str] = field(default_factory=list)
    character_artifacts: list[str] = field(default_factory=list)
    outline_reference: str | None = None
    beat_outline: BeatOutline | None = None
    story_facts: StoryFacts | None = None
    revision_intent: RevisionIntent | None = None
    narration_constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EditorialStructuringResult:
    entity_resolution_results: list[EntityResolutionResult] = field(default_factory=list)
    story_facts: StoryFacts | None = None
    beat_outline: BeatOutline | None = None
    revision_intent: RevisionIntent | None = None
    narration_prep: NarrationPrep | None = None
    result_kind: str = "mixed"
    ready_for_validation: bool = False

    def __post_init__(self) -> None:
        _ensure_catalog_value("result_kind", self.result_kind, EDITORIAL_RESULT_KIND_CATALOG)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
