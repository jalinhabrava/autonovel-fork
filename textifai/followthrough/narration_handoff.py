from __future__ import annotations

from textifai.editorial.contracts import NarrationPrep
from textifai.editorial.narration_prep import build_narration_prep as build_editorial_narration_prep
from textifai.followthrough.contracts import (
    NarrationRequest,
    ValidatedStructuringState,
)


def build_narration_request(
    *,
    validated_structuring_state: ValidatedStructuringState,
    target_language: str | None,
    voice_mode: str | None = None,
    continuity_scope: str | None = None,
    canon_mode: str | None = None,
    constraints: list[str] | None = None,
) -> NarrationRequest:
    voice_mode = voice_mode or _infer_voice_mode(validated_structuring_state)
    continuity_scope = continuity_scope or _infer_continuity_scope(validated_structuring_state)
    canon_mode = canon_mode or _infer_canon_mode(validated_structuring_state)
    return NarrationRequest(
        source_kind=_source_kind(validated_structuring_state),
        validated_structuring_state=validated_structuring_state,
        target_language=target_language,
        voice_mode=voice_mode,
        continuity_scope=continuity_scope,
        canon_mode=canon_mode,
        constraints=_dedupe(constraints or _constraints_from_state(validated_structuring_state)),
    )


def build_narration_prep(
    *,
    validated_structuring_state: ValidatedStructuringState,
    target_language: str,
    explanation_language: str,
) -> NarrationPrep:
    source = validated_structuring_state.source_structuring_result
    return build_editorial_narration_prep(
        target_language=target_language,
        explanation_language=explanation_language,
        entity_results=source.entity_resolution_results,
        beat_outline=validated_structuring_state.validated_beat_outline,
        story_facts=validated_structuring_state.validated_story_facts,
        revision_intent=validated_structuring_state.validated_revision_intent,
    )


def _infer_voice_mode(state: ValidatedStructuringState) -> str:
    revision_intent = state.validated_revision_intent
    if revision_intent is not None and (
        "character_voice_mismatch" in revision_intent.issue_types
        or "character_voice" in revision_intent.must_preserve
    ):
        return "emphasize_character_voice"
    return "inherit_project_voice"


def _infer_continuity_scope(state: ValidatedStructuringState) -> str:
    beat_outline = state.validated_beat_outline
    revision_intent = state.validated_revision_intent
    if beat_outline is not None and len(beat_outline.beats) > 1:
        return "chapter_local"
    if revision_intent is not None and revision_intent.target_scope == "scene_or_chapter":
        return "chapter_local"
    return "scene_only"


def _infer_canon_mode(state: ValidatedStructuringState) -> str:
    source = state.source_structuring_result
    if (
        source.entity_resolution_results
        and any(result.related_artifacts_suggested for result in source.entity_resolution_results)
    ) or (
        state.validated_story_facts is not None
        and (state.validated_story_facts.canon_constraints or state.validated_story_facts.constraints)
    ):
        return "validated_plus_related"
    return "validated_only"


def _constraints_from_state(state: ValidatedStructuringState) -> list[str]:
    constraints: list[str] = []
    story_facts = state.validated_story_facts
    revision_intent = state.validated_revision_intent
    if story_facts is not None:
        constraints.extend(story_facts.constraints)
        constraints.extend(story_facts.canon_constraints)
    if revision_intent is not None:
        constraints.extend(revision_intent.must_preserve)
    if _infer_voice_mode(state) == "emphasize_character_voice":
        constraints.append("preserve_character_voice")
    return constraints


def _source_kind(state: ValidatedStructuringState) -> str:
    if state.validated_beat_outline is not None:
        return "beat_outline"
    if state.validated_story_facts is not None:
        return "story_facts"
    if state.validated_revision_intent is not None:
        return "revision_intent"
    return "unknown"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
