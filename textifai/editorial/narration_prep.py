from __future__ import annotations

from textifai.editorial.contracts import BeatOutline, EntityResolutionResult, NarrationPrep, RevisionIntent, StoryFacts


def build_narration_prep(
    *,
    target_language: str,
    explanation_language: str,
    entity_results: list[EntityResolutionResult],
    beat_outline: BeatOutline | None = None,
    story_facts: StoryFacts | None = None,
    revision_intent: RevisionIntent | None = None,
) -> NarrationPrep:
    voice_artifacts = ["voice"]
    canon_artifacts = ["canon"]
    continuity_artifacts: list[str] = []
    character_artifacts: list[str] = []
    outline_reference = None

    for result in entity_results:
        if not result.resolved or not result.resolved_entity_id or not result.resolved_entity_type:
            continue
        artifact_ref = f"{result.resolved_entity_type}:{result.resolved_entity_id}"
        if result.resolved_entity_type == "character":
            character_artifacts.append(artifact_ref)
        elif result.resolved_entity_type in {"scene", "chapter"}:
            continuity_artifacts.append(artifact_ref)
            outline_reference = outline_reference or artifact_ref
        elif result.resolved_entity_type in {"lore", "decision"}:
            canon_artifacts.append(artifact_ref)
        for suggestion in result.related_artifacts_suggested:
            suggestion_ref = f"{suggestion.artifact_type}:{suggestion.artifact_id}"
            if suggestion.artifact_type == "character":
                character_artifacts.append(suggestion_ref)
            elif suggestion.artifact_type in {"scene", "chapter"}:
                continuity_artifacts.append(suggestion_ref)
            elif suggestion.artifact_type in {"lore", "decision"}:
                canon_artifacts.append(suggestion_ref)

    narration_constraints: list[str] = []
    if story_facts is not None:
        narration_constraints.extend(story_facts.constraints)
        narration_constraints.extend(story_facts.canon_constraints)
    if revision_intent is not None:
        narration_constraints.extend(revision_intent.must_preserve)

    return NarrationPrep(
        source_kind=_source_kind(beat_outline, story_facts, revision_intent),
        target_language=target_language,
        explanation_language=explanation_language,
        voice_artifacts=sorted(set(voice_artifacts)),
        canon_artifacts=sorted(set(canon_artifacts)),
        continuity_artifacts=sorted(set(continuity_artifacts)),
        character_artifacts=sorted(set(character_artifacts)),
        outline_reference=outline_reference,
        beat_outline=beat_outline,
        story_facts=story_facts,
        revision_intent=revision_intent,
        narration_constraints=sorted(set(filter(None, narration_constraints))),
    )


def _source_kind(
    beat_outline: BeatOutline | None,
    story_facts: StoryFacts | None,
    revision_intent: RevisionIntent | None,
) -> str:
    if beat_outline is not None:
        return "beat_outline"
    if story_facts is not None:
        return "story_facts"
    if revision_intent is not None:
        return "revision_intent"
    return "unknown"
