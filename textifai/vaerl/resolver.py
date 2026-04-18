from __future__ import annotations

from textifai.vaerl.contracts import EntityResolutionResult
from textifai.vaerl.detection import detect_mentions
from textifai.vaerl.index import build_vault_index
from textifai.vaerl.matching import match_candidates
from textifai.vaerl.related import suggest_related_artifacts


RESOLUTION_THRESHOLD = 0.9
AMBIGUITY_MARGIN = 0.08


def resolve_text_against_vault(
    *,
    text: str,
    vault_path,
    known_characters: list[dict[str, object]] | None = None,
    entity_hints: list[str] | None = None,
) -> list[EntityResolutionResult]:
    index_entries = build_vault_index(vault_path=vault_path, known_characters=known_characters)
    mentions = detect_mentions(text=text, index_entries=index_entries, entity_hints=entity_hints)
    results: list[EntityResolutionResult] = []
    for mention in mentions:
        candidates = match_candidates(mention=mention, index_entries=index_entries)
        result = _resolve_mention(text=text, mention=mention, candidates=candidates)
        related = suggest_related_artifacts(resolution=result, index_entries=index_entries)
        results.append(
            EntityResolutionResult(
                query_text=result.query_text,
                mention=result.mention,
                candidate_entities=result.candidate_entities,
                resolved=result.resolved,
                resolution_confidence=result.resolution_confidence,
                resolution_source=result.resolution_source,
                resolved_entity_id=result.resolved_entity_id,
                resolved_entity_type=result.resolved_entity_type,
                related_artifacts_suggested=related,
                metadata=result.metadata,
            )
        )
    return results


def _resolve_mention(
    *,
    text: str,
    mention,
    candidates,
) -> EntityResolutionResult:
    if not candidates:
        return EntityResolutionResult(
            query_text=text,
            mention=mention,
            candidate_entities=[],
            resolved=False,
            resolution_confidence=0.0,
            resolution_source=None,
            metadata={"resolution_status": "no_match"},
        )

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    ambiguous = (
        second is not None
        and abs(top.confidence - second.confidence) <= AMBIGUITY_MARGIN
        and second.confidence >= top.confidence - AMBIGUITY_MARGIN
    )
    if top.confidence >= RESOLUTION_THRESHOLD and not ambiguous:
        return EntityResolutionResult(
            query_text=text,
            mention=mention,
            candidate_entities=candidates,
            resolved=True,
            resolution_confidence=top.confidence,
            resolution_source=top.match_source,
            resolved_entity_id=top.artifact_id,
            resolved_entity_type=top.artifact_type,
            metadata={"resolution_status": "resolved"},
        )
    return EntityResolutionResult(
        query_text=text,
        mention=mention,
        candidate_entities=candidates,
        resolved=False,
        resolution_confidence=top.confidence,
        resolution_source=top.match_source,
        metadata={"resolution_status": "ambiguous" if ambiguous else "candidate_only"},
    )
