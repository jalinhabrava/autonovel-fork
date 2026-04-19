from __future__ import annotations

from pathlib import Path

from textifai.obsidian import build_obsidian_context_bundle
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.vaerl.contracts import EntityResolutionResult


def build_response_context(
    *,
    vault_root: str | Path,
    editorial_intent: EditorialIntent | None,
    entity_results: list[EntityResolutionResult],
    include_candidates: bool = True,
) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_target(target_type: str | None, target_id: str | None, *, source: str) -> None:
        if not target_type or not target_id:
            return
        key = (target_type, target_id)
        if key in seen:
            return
        bundle = build_obsidian_context_bundle(vault_root, note_id=target_id, related_limit=3)
        if bundle.primary is None:
            return
        snippets.append(
            {
                "artifact_type": bundle.primary.artifact_type,
                "artifact_id": bundle.primary.note_id,
                "title": bundle.primary.title,
                "excerpt": _trim_excerpt(bundle.primary.body_text),
                "source": source,
                "path": bundle.primary.path,
                "context_source_reliability": bundle.source_status.reliability if bundle.source_status else None,
                "context_source_kind": bundle.source_status.source_kind if bundle.source_status else None,
            }
        )
        seen.add(key)
        for related in bundle.related:
            related_key = (related.artifact_type, related.note_id)
            if related_key in seen:
                continue
            snippets.append(
                {
                    "artifact_type": related.artifact_type,
                    "artifact_id": related.note_id,
                    "title": related.title,
                    "excerpt": _trim_excerpt(related.body_text),
                    "source": f"{source}_obsidian_related",
                    "path": related.path,
                    "context_source_reliability": bundle.source_status.reliability if bundle.source_status else None,
                    "context_source_kind": bundle.source_status.source_kind if bundle.source_status else None,
                }
            )
            seen.add(related_key)

    if editorial_intent is not None:
        add_target(
            editorial_intent.resolved_target_type,
            editorial_intent.resolved_target_id,
            source="resolved_target",
        )
        if include_candidates:
            for candidate in editorial_intent.candidate_targets[:3]:
                add_target(candidate.target_type, candidate.target_id, source="candidate_target")

    for result in entity_results:
        if result.resolved and result.resolved_entity_type and result.resolved_entity_id:
            add_target(result.resolved_entity_type, result.resolved_entity_id, source="vaerl_resolved")
        for suggestion in result.related_artifacts_suggested[:2]:
            add_target(suggestion.artifact_type, suggestion.artifact_id, source="related_artifact")

    return snippets


def _trim_excerpt(text: str, limit: int = 700) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit] + ("..." if len(collapsed) > limit else "")
