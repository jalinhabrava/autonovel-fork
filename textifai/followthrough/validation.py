from __future__ import annotations

from textifai.editorial.contracts import EditorialStructuringResult
from textifai.followthrough.contracts import FollowThroughResult, ValidatedStructuringState


def build_validated_structuring_state(
    source_structuring_result: EditorialStructuringResult,
    *,
    validated_by_user: bool,
    validation_notes: list[str] | None = None,
    allow_conservative_promotion: bool = False,
) -> ValidatedStructuringState:
    notes = list(validation_notes or [])
    if not _has_validatable_material(source_structuring_result):
        notes.extend(_missing_material_notes(source_structuring_result))
        return ValidatedStructuringState(
            source_result_kind=source_structuring_result.result_kind,
            source_structuring_result=source_structuring_result,
            validation_status="insufficient_structure",
            validated_by_user=validated_by_user,
            validation_notes=_dedupe(notes),
            validated_story_facts=source_structuring_result.story_facts,
            validated_beat_outline=source_structuring_result.beat_outline,
            validated_revision_intent=source_structuring_result.revision_intent,
            ready_for_narration_prep=False,
            ready_for_review_handoff=False,
        )

    if validated_by_user:
        validation_status = "validated_with_notes" if notes else "validated"
    elif allow_conservative_promotion:
        validation_status = "validated_with_notes"
        notes.append("Conservatively promoted from a recent structured result for follow-through.")
    else:
        validation_status = "pending_validation"

    ready_for_narration_prep = validation_status in {"validated", "validated_with_notes"}
    ready_for_review_handoff = ready_for_narration_prep and _has_reviewable_material(source_structuring_result)
    return ValidatedStructuringState(
        source_result_kind=source_structuring_result.result_kind,
        source_structuring_result=source_structuring_result,
        validation_status=validation_status,
        validated_by_user=validated_by_user,
        validation_notes=_dedupe(notes),
        validated_story_facts=source_structuring_result.story_facts,
        validated_beat_outline=source_structuring_result.beat_outline,
        validated_revision_intent=source_structuring_result.revision_intent,
        ready_for_narration_prep=ready_for_narration_prep,
        ready_for_review_handoff=ready_for_review_handoff,
    )


def extract_followthrough_state(last_result) -> ValidatedStructuringState | None:
    if not isinstance(last_result, dict):
        return None
    if last_result.get("type") != "followthrough":
        return None
    data = last_result.get("data")
    if not isinstance(data, dict):
        return None
    state = data.get("validated_structuring_state")
    if not isinstance(state, dict):
        return None
    return _validated_state_from_dict(state)


def build_followthrough_result(
    *,
    validated_structuring_state: ValidatedStructuringState | None,
    narration_request,
    narration_prep,
    review_ready_package,
    next_recommended_step: str,
    ready_for_user_confirmation: bool,
) -> FollowThroughResult:
    return FollowThroughResult(
        validated_structuring_state=validated_structuring_state,
        narration_request=narration_request,
        narration_prep=narration_prep,
        review_ready_package=review_ready_package,
        next_recommended_step=next_recommended_step,
        ready_for_user_confirmation=ready_for_user_confirmation,
    )


def _has_validatable_material(source_structuring_result: EditorialStructuringResult) -> bool:
    return bool(
        (source_structuring_result.story_facts is not None and source_structuring_result.story_facts.explicit_facts)
        or (source_structuring_result.beat_outline is not None and source_structuring_result.beat_outline.beats)
        or source_structuring_result.revision_intent is not None
    )


def _has_reviewable_material(source_structuring_result: EditorialStructuringResult) -> bool:
    return bool(
        source_structuring_result.revision_intent is not None
        or (source_structuring_result.story_facts is not None and (
            source_structuring_result.story_facts.canon_constraints
            or source_structuring_result.story_facts.constraints
            or source_structuring_result.story_facts.open_questions
        ))
        or (source_structuring_result.beat_outline is not None and (
            source_structuring_result.beat_outline.canon_checks
            or source_structuring_result.beat_outline.continuity_notes
        ))
    )


def _missing_material_notes(source_structuring_result: EditorialStructuringResult) -> list[str]:
    notes: list[str] = []
    if source_structuring_result.story_facts is None or not source_structuring_result.story_facts.explicit_facts:
        notes.append("Need explicit narrative facts before validation can proceed.")
    if source_structuring_result.beat_outline is None or not source_structuring_result.beat_outline.beats:
        notes.append("Need real beats before narration or review handoff.")
    if source_structuring_result.revision_intent is None:
        notes.append("Need a concrete revision intent when the request is about changes.")
    return notes


def _validated_state_from_dict(value: dict) -> ValidatedStructuringState:
    source_result = _editorial_structuring_result_from_dict(
        value.get("source_structuring_result"),
        fallback_kind=value.get("source_result_kind", "mixed"),
    )
    return ValidatedStructuringState(
        source_result_kind=value.get("source_result_kind", "mixed"),
        source_structuring_result=source_result,
        validation_status=value.get("validation_status", "pending_validation"),
        validated_by_user=bool(value.get("validated_by_user", False)),
        validation_notes=list(value.get("validation_notes", [])),
        validated_story_facts=_story_facts_from_dict(value.get("validated_story_facts")),
        validated_beat_outline=_beat_outline_from_dict(value.get("validated_beat_outline")),
        validated_revision_intent=_revision_intent_from_dict(value.get("validated_revision_intent")),
        ready_for_narration_prep=bool(value.get("ready_for_narration_prep", False)),
        ready_for_review_handoff=bool(value.get("ready_for_review_handoff", False)),
    )


def _editorial_structuring_result_from_dict(value, *, fallback_kind: str) -> EditorialStructuringResult:
    if not isinstance(value, dict):
        return EditorialStructuringResult(
            entity_resolution_results=[],
            story_facts=_story_facts_from_dict(None),
            beat_outline=_beat_outline_from_dict(None),
            revision_intent=_revision_intent_from_dict(None),
            narration_prep=None,
            result_kind=fallback_kind,
            ready_for_validation=False,
        )
    return EditorialStructuringResult(
        entity_resolution_results=_entity_results_from_dict(value.get("entity_resolution_results")),
        story_facts=_story_facts_from_dict(value.get("story_facts")),
        beat_outline=_beat_outline_from_dict(value.get("beat_outline")),
        revision_intent=_revision_intent_from_dict(value.get("revision_intent")),
        narration_prep=None,
        result_kind=value.get("result_kind", fallback_kind),
        ready_for_validation=bool(value.get("ready_for_validation", False)),
    )


def _story_facts_from_dict(value) -> "StoryFacts" | None:
    if not value:
        return None
    from textifai.editorial.contracts import StoryFactItem, StoryFacts

    return StoryFacts(
        source_text=value["source_text"],
        language=value["language"],
        characters_involved=list(value.get("characters_involved", [])),
        locations_involved=list(value.get("locations_involved", [])),
        objects_involved=list(value.get("objects_involved", [])),
        premise=value.get("premise"),
        core_conflict=value.get("core_conflict"),
        goals=list(value.get("goals", [])),
        constraints=list(value.get("constraints", [])),
        canon_constraints=list(value.get("canon_constraints", [])),
        explicit_facts=[StoryFactItem(**item) for item in value.get("explicit_facts", [])],
        inferred_facts=[StoryFactItem(**item) for item in value.get("inferred_facts", [])],
        open_questions=list(value.get("open_questions", [])),
    )


def _beat_outline_from_dict(value) -> "BeatOutline" | None:
    if not value:
        return None
    from textifai.editorial.contracts import BeatItem, BeatOutline

    return BeatOutline(
        source_kind=value["source_kind"],
        title=value.get("title"),
        beats=[BeatItem(**item) for item in value.get("beats", [])],
        emotional_arc=list(value.get("emotional_arc", [])),
        target_language=value.get("target_language"),
        continuity_notes=list(value.get("continuity_notes", [])),
        canon_checks=list(value.get("canon_checks", [])),
    )


def _revision_intent_from_dict(value) -> "RevisionIntent" | None:
    if not value:
        return None
    from textifai.editorial.contracts import RevisionIntent

    return RevisionIntent(
        source_text=value["source_text"],
        target_scope=value.get("target_scope"),
        issue_types=list(value.get("issue_types", [])),
        desired_changes=list(value.get("desired_changes", [])),
        must_preserve=list(value.get("must_preserve", [])),
        priority=value.get("priority"),
        target_hint=value.get("target_hint"),
    )


def _narration_prep_from_dict(value):
    if not value:
        return None
    from textifai.editorial.contracts import NarrationPrep

    return NarrationPrep(
        source_kind=value["source_kind"],
        target_language=value["target_language"],
        explanation_language=value["explanation_language"],
        voice_artifacts=list(value.get("voice_artifacts", [])),
        canon_artifacts=list(value.get("canon_artifacts", [])),
        continuity_artifacts=list(value.get("continuity_artifacts", [])),
        character_artifacts=list(value.get("character_artifacts", [])),
        outline_reference=value.get("outline_reference"),
        beat_outline=_beat_outline_from_dict(value.get("beat_outline")),
        story_facts=_story_facts_from_dict(value.get("story_facts")),
        revision_intent=_revision_intent_from_dict(value.get("revision_intent")),
        narration_constraints=list(value.get("narration_constraints", [])),
    )


def _review_ready_package_from_dict(value):
    if not value:
        return None
    from textifai.followthrough.contracts import ReviewReadyPackage

    narration_prep = _narration_prep_from_dict(value.get("narration_prep")) if isinstance(value.get("narration_prep"), dict) else None
    return ReviewReadyPackage(
        source_kind=value["source_kind"],
        validated_structuring_state=_validated_state_from_dict(value["validated_structuring_state"]),
        narration_prep=narration_prep,
        review_focus=list(value.get("review_focus", [])),
        preserve_constraints=list(value.get("preserve_constraints", [])),
        related_artifacts=list(value.get("related_artifacts", [])),
        open_questions=list(value.get("open_questions", [])),
    )


def _entity_results_from_dict(value) -> list:
    if not isinstance(value, list):
        return []
    from textifai.vaerl.contracts import EntityCandidate, EntityMention, EntityResolutionResult, RelatedArtifactSuggestion

    results = []
    for item in value:
        if not isinstance(item, dict):
            continue
        mention = item.get("mention") or {}
        results.append(
            EntityResolutionResult(
                query_text=item.get("query_text", ""),
                mention=EntityMention(
                    surface_text=mention.get("surface_text", ""),
                    normalized_text=mention.get("normalized_text", ""),
                    mention_kind_hint=mention.get("mention_kind_hint"),
                    source=mention.get("source", "raw_text"),
                    confidence=float(mention.get("confidence", 0.0)),
                    context_hint=mention.get("context_hint"),
                    span_start=mention.get("span_start"),
                    span_end=mention.get("span_end"),
                ),
                candidate_entities=[EntityCandidate(**candidate) for candidate in item.get("candidate_entities", [])],
                resolved=bool(item.get("resolved", False)),
                resolution_confidence=float(item.get("resolution_confidence", 0.0)),
                resolution_source=item.get("resolution_source"),
                resolved_entity_id=item.get("resolved_entity_id"),
                resolved_entity_type=item.get("resolved_entity_type"),
                related_artifacts_suggested=[RelatedArtifactSuggestion(**suggestion) for suggestion in item.get("related_artifacts_suggested", [])],
                metadata=dict(item.get("metadata", {})),
            )
        )
    return results


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
