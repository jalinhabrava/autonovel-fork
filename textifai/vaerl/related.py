from __future__ import annotations

from textifai.vaerl.contracts import EntityResolutionResult, RelatedArtifactSuggestion, VaultIndexEntry


MAX_RELATED_SUGGESTIONS = 3


def suggest_related_artifacts(
    *,
    resolution: EntityResolutionResult,
    index_entries: list[VaultIndexEntry],
) -> list[RelatedArtifactSuggestion]:
    if not resolution.resolved or not resolution.resolved_entity_id or not resolution.resolved_entity_type:
        return _candidate_backfill_suggestions(resolution)

    suggestions: list[RelatedArtifactSuggestion] = []
    by_id = {entry.artifact_id: entry for entry in index_entries}
    entry = by_id.get(resolution.resolved_entity_id)
    if entry is None:
        return []

    # Direct suggestion first.
    suggestions.append(
        RelatedArtifactSuggestion(
            artifact_id=entry.artifact_id,
            artifact_type=entry.artifact_type,
            relation="direct_profile" if entry.artifact_type == "character" else "direct_note",
            confidence=min(resolution.resolution_confidence + 0.03, 0.99),
            path=entry.path,
        )
    )

    relation_map = {
        "character": {"scene": "linked_scene", "chapter": "linked_chapter", "lore": "linked_lore", "decision": "linked_canon"},
        "lore": {"decision": "linked_canon", "scene": "linked_scene", "chapter": "linked_chapter"},
        "decision": {"lore": "linked_lore", "scene": "linked_scene", "chapter": "linked_chapter"},
        "scene": {"lore": "linked_lore", "decision": "linked_canon", "chapter": "linked_chapter"},
        "chapter": {"scene": "linked_scene", "lore": "linked_lore", "decision": "linked_canon"},
    }
    allowed = relation_map.get(entry.artifact_type, {})

    linked_ids = list(entry.links) + list(entry.backlinks)
    for linked_id in linked_ids:
        linked = by_id.get(linked_id)
        if linked is None:
            continue
        relation = allowed.get(linked.artifact_type)
        if relation is None:
            continue
        suggestions.append(
            RelatedArtifactSuggestion(
                artifact_id=linked.artifact_id,
                artifact_type=linked.artifact_type,
                relation=relation if linked_id in entry.links else "backlinked_context",
                confidence=0.72 if linked_id in entry.links else 0.64,
                path=linked.path,
            )
        )

    deduped: list[RelatedArtifactSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for suggestion in suggestions:
        key = (suggestion.artifact_type, suggestion.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
    return deduped[:MAX_RELATED_SUGGESTIONS]


def _candidate_backfill_suggestions(resolution: EntityResolutionResult) -> list[RelatedArtifactSuggestion]:
    suggestions: list[RelatedArtifactSuggestion] = []
    for candidate in resolution.candidate_entities[:MAX_RELATED_SUGGESTIONS]:
        suggestions.append(
            RelatedArtifactSuggestion(
                artifact_id=candidate.artifact_id,
                artifact_type=candidate.artifact_type,
                relation="direct_profile" if candidate.artifact_type == "character" else "direct_note",
                confidence=max(min(candidate.confidence - 0.08, 0.89), 0.45),
                path=candidate.path,
            )
        )
    return suggestions
