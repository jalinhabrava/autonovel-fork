from __future__ import annotations

from textifai.followthrough.contracts import REVIEW_FOCUS_CATALOG, ReviewReadyPackage, ValidatedStructuringState


def build_review_ready_package(
    *,
    validated_structuring_state: ValidatedStructuringState,
    narration_prep=None,
    review_focus: list[str] | None = None,
    preserve_constraints: list[str] | None = None,
    related_artifacts: list[str] | None = None,
    open_questions: list[str] | None = None,
) -> ReviewReadyPackage:
    focus = review_focus or _derive_review_focus(validated_structuring_state)
    return ReviewReadyPackage(
        source_kind=_source_kind(validated_structuring_state),
        validated_structuring_state=validated_structuring_state,
        narration_prep=narration_prep,
        review_focus=_dedupe([item for item in focus if item in REVIEW_FOCUS_CATALOG]),
        preserve_constraints=_dedupe(preserve_constraints or _constraints_from_state(validated_structuring_state)),
        related_artifacts=_dedupe(related_artifacts or _related_artifacts_from_state(validated_structuring_state)),
        open_questions=_dedupe(open_questions or _open_questions_from_state(validated_structuring_state)),
    )


def _derive_review_focus(state: ValidatedStructuringState) -> list[str]:
    focus: list[str] = []
    revision_intent = state.validated_revision_intent
    story_facts = state.validated_story_facts
    beat_outline = state.validated_beat_outline
    if revision_intent is not None:
        issue_types = set(revision_intent.issue_types)
        if "canon_issue" in issue_types:
            focus.append("canon")
        if "continuity_issue" in issue_types:
            focus.append("continuity")
        if "character_voice_mismatch" in issue_types:
            focus.append("voice")
        if "tone_issue" in issue_types:
            focus.append("tone")
        if "motivation_issue" in issue_types:
            focus.append("motivation")
        if "clarity_issue" in issue_types:
            focus.append("structure")
        if not focus:
            focus.append("handoff")
    elif beat_outline is not None:
        focus.extend(["structure", "conflict"])
    elif story_facts is not None:
        focus.append("structure")
    else:
        focus.append("handoff")
    return focus


def _constraints_from_state(state: ValidatedStructuringState) -> list[str]:
    constraints: list[str] = []
    story_facts = state.validated_story_facts
    revision_intent = state.validated_revision_intent
    if story_facts is not None:
        constraints.extend(story_facts.constraints)
        constraints.extend(story_facts.canon_constraints)
    if revision_intent is not None:
        constraints.extend(revision_intent.must_preserve)
    return constraints


def _related_artifacts_from_state(state: ValidatedStructuringState) -> list[str]:
    related: list[str] = []
    for entity_result in state.source_structuring_result.entity_resolution_results:
        if entity_result.resolved and entity_result.resolved_entity_id and entity_result.resolved_entity_type:
            related.append(f"{entity_result.resolved_entity_type}:{entity_result.resolved_entity_id}")
        for suggestion in entity_result.related_artifacts_suggested:
            related.append(f"{suggestion.artifact_type}:{suggestion.artifact_id}")
    return related


def _open_questions_from_state(state: ValidatedStructuringState) -> list[str]:
    story_facts = state.validated_story_facts
    if story_facts is None:
        return []
    return list(story_facts.open_questions)


def _source_kind(state: ValidatedStructuringState) -> str:
    if state.validated_revision_intent is not None:
        return "revision_intent"
    if state.validated_beat_outline is not None:
        return "beat_outline"
    if state.validated_story_facts is not None:
        return "story_facts"
    return "unknown"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
