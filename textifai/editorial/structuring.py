from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textifai.editorial.contracts import (
    BeatItem,
    BeatOutline,
    EditorialStructuringResult,
    EntityResolutionResult,
    RevisionIntent,
    StoryFactItem,
    StoryFacts,
)

if TYPE_CHECKING:
    from textifai.conversation.contracts import NarrativeSignals


def build_story_facts(
    *,
    source_text: str,
    language: str,
    entity_results: list[EntityResolutionResult],
    narrative_signals: NarrativeSignals | None = None,
) -> StoryFacts:
    explicit_segments = _split_story_segments(source_text)
    explicit_facts = [
        StoryFactItem(text=segment, fact_kind=_classify_fact_kind(segment), source="explicit_input")
        for segment in explicit_segments
    ]
    inferred_facts: list[StoryFactItem] = []
    characters = _resolved_ids(entity_results, "character")
    premise = explicit_segments[0] if explicit_segments else source_text.strip() or None
    core_conflict = _infer_core_conflict(explicit_segments)
    goals = _infer_goals(explicit_segments)
    constraints = list((narrative_signals.constraint_hints if narrative_signals else []) or [])
    canon_constraints = ["respect_validated_canon"] if narrative_signals and "canon_issue" in narrative_signals.issue_types else []
    if core_conflict:
        inferred_facts.append(StoryFactItem(text=core_conflict, fact_kind="conflict", source="system_inference"))
    for goal in goals:
        inferred_facts.append(StoryFactItem(text=goal, fact_kind="goal", source="system_inference"))
    locations = _resolved_ids(entity_results, "scene")
    objects = _resolved_ids(entity_results, "lore")
    return StoryFacts(
        source_text=source_text,
        language=language,
        characters_involved=characters,
        locations_involved=locations,
        objects_involved=objects,
        premise=premise,
        core_conflict=core_conflict,
        goals=goals,
        constraints=constraints,
        canon_constraints=canon_constraints,
        explicit_facts=explicit_facts,
        inferred_facts=inferred_facts,
        open_questions=[] if explicit_facts else ["Need clearer narrative facts from the author input."],
    )


def build_revision_intent(
    *,
    source_text: str,
    narrative_signals: NarrativeSignals | None = None,
    target_hint: str | None = None,
) -> RevisionIntent | None:
    lowered = source_text.casefold()
    has_revision_language = any(
        phrase in lowered
        for phrase in (
            "quiero que",
            "debería",
            "deberia",
            "no me gusta",
            "funciona hasta",
            "quiero revisar",
            "cambia",
            "ajusta",
        )
    )
    issue_types = list((narrative_signals.issue_types if narrative_signals else []) or [])
    if not has_revision_language and not issue_types:
        return None
    desired_changes = _extract_desired_changes(source_text)
    must_preserve = []
    if "canon_issue" in issue_types:
        must_preserve.append("validated_canon")
    if "character_voice_mismatch" in issue_types:
        must_preserve.append("character_voice")
    return RevisionIntent(
        source_text=source_text,
        target_scope="scene_or_chapter",
        issue_types=issue_types,
        desired_changes=desired_changes,
        must_preserve=must_preserve,
        priority="high" if issue_types else "medium",
        target_hint=target_hint,
    )


def build_beat_outline(
    *,
    story_facts: StoryFacts,
    target_language: str | None = None,
) -> BeatOutline:
    beats: list[BeatItem] = []
    segments = [fact.text for fact in story_facts.explicit_facts if fact.fact_kind in {"event", "conflict", "outcome", "state"}]
    for index, segment in enumerate(segments, start=1):
        beats.append(
            BeatItem(
                index=index,
                summary=segment,
                purpose=_beat_purpose(segment),
                characters=story_facts.characters_involved,
                tension_level=_tension_for_index(index, len(segments)),
            )
        )
    emotional_arc = _emotional_arc_from_beats(beats)
    return BeatOutline(
        source_kind="story_facts",
        title=story_facts.premise,
        beats=beats,
        emotional_arc=emotional_arc,
        target_language=target_language,
        continuity_notes=[],
        canon_checks=list(story_facts.canon_constraints),
    )


def build_editorial_structuring_result(
    *,
    source_text: str,
    language: str,
    entity_results: list[EntityResolutionResult],
    narrative_signals: NarrativeSignals | None = None,
    artifact_target_language: str | None = None,
) -> EditorialStructuringResult:
    story_facts = build_story_facts(
        source_text=source_text,
        language=language,
        entity_results=entity_results,
        narrative_signals=narrative_signals,
    )
    revision_intent = build_revision_intent(
        source_text=source_text,
        narrative_signals=narrative_signals,
        target_hint=narrative_signals.target_hint if narrative_signals else None,
    )
    beat_outline = build_beat_outline(
        story_facts=story_facts,
        target_language=artifact_target_language,
    )
    result_kind = "mixed"
    if revision_intent is not None and not beat_outline.beats:
        result_kind = "revision_intent"
    elif beat_outline.beats:
        result_kind = "beat_outline"
    elif story_facts.explicit_facts:
        result_kind = "story_facts"
    return EditorialStructuringResult(
        entity_resolution_results=entity_results,
        story_facts=story_facts,
        beat_outline=beat_outline if beat_outline.beats else None,
        revision_intent=revision_intent,
        narration_prep=None,
        result_kind=result_kind,
        ready_for_validation=bool(story_facts.explicit_facts),
    )


def _split_story_segments(source_text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"[,\n;]+", source_text) if part.strip()]
    return parts


def _classify_fact_kind(segment: str) -> str:
    lowered = segment.casefold()
    if any(word in lowered for word in ("pero", "discuten", "acusa", "contradice", "conflicto")):
        return "conflict"
    if any(word in lowered for word in ("quiere", "intenta", "busca", "debe")):
        return "goal"
    if any(word in lowered for word in ("al final", "termina", "terminan", "revela", "rompe")):
        return "outcome"
    if any(word in lowered for word in ("siempre", "nunca", "regla", "canon", "debe")):
        return "constraint"
    if any(word in lowered for word in ("está", "esta", "suena", "parece")):
        return "state"
    return "event"


def _infer_core_conflict(segments: list[str]) -> str | None:
    for segment in segments:
        if _classify_fact_kind(segment) == "conflict":
            return segment
    return None


def _infer_goals(segments: list[str]) -> list[str]:
    goals: list[str] = []
    for segment in segments:
        lowered = segment.casefold()
        if any(word in lowered for word in ("quiere", "intenta", "busca", "debe")):
            goals.append(segment)
    return goals


def _resolved_ids(entity_results: list[EntityResolutionResult], entity_type: str) -> list[str]:
    ids: list[str] = []
    for result in entity_results:
        if result.resolved and result.resolved_entity_type == entity_type and result.resolved_entity_id:
            ids.append(result.resolved_entity_id)
    return ids


def _extract_desired_changes(source_text: str) -> list[str]:
    lowered = source_text.casefold()
    clauses = _split_story_segments(source_text)
    desired = []
    for clause in clauses:
        clause_lower = clause.casefold()
        if any(phrase in clause_lower for phrase in ("quiero que", "debería", "deberia", "cambia", "ajusta", "dure más", "dure mas")):
            desired.append(clause)
    if not desired and "no me gusta" in lowered:
        desired.append("revise the problematic passage while preserving the core scene intent")
    return desired


def _beat_purpose(segment: str) -> str:
    fact_kind = _classify_fact_kind(segment)
    mapping = {
        "event": "advance_scene",
        "state": "establish_state",
        "conflict": "escalate_conflict",
        "goal": "surface_goal",
        "constraint": "establish_constraint",
        "outcome": "change_state",
    }
    return mapping[fact_kind]


def _tension_for_index(index: int, total: int) -> str:
    if total <= 1:
        return "high"
    if index == 1:
        return "low"
    if index < total:
        return "rising" if index < total - 1 else "high"
    return "peak"


def _emotional_arc_from_beats(beats: list[BeatItem]) -> list[str]:
    return [beat.tension_level for beat in beats]
