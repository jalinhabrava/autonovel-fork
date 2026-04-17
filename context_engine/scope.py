from __future__ import annotations

from adapters.vault_adapter import VaultProjectAdapter
from context_engine.contracts import ContextRequest, ResolvedIntent, ResolvedScope
from interactive.chapter_selection import normalize_chapter_id
from interactive.query import note_record


def resolve_scope(adapter: VaultProjectAdapter, request: ContextRequest, intent: ResolvedIntent) -> ResolvedScope:
    chapter_refs = tuple(_resolve_chapter_refs(adapter, request))
    scene_refs = tuple(_resolve_scene_refs(request, intent))
    character_ids = tuple(request.character_ids)
    return ResolvedScope(
        narrative_scope=intent.narrative_scope,
        retrieval_scope=intent.retrieval_scope,
        target_id=request.target_id,
        chapter_refs=chapter_refs,
        scene_refs=scene_refs,
        character_ids=character_ids,
    )


def _resolve_chapter_refs(adapter: VaultProjectAdapter, request: ContextRequest) -> list[str]:
    if request.chapter_refs:
        return [normalize_chapter_id(chapter_ref) for chapter_ref in request.chapter_refs]

    if request.target_type == "chapter":
        return [normalize_chapter_id(request.target_id)]

    if request.target_type == "scene":
        scene_path = adapter.note_path("scene", request.target_id)
        if scene_path.exists():
            record = note_record(scene_path, "scene")
            chapter = record["frontmatter"].get("chapter")
            if chapter:
                return [normalize_chapter_id(chapter)]
    return []


def _resolve_scene_refs(request: ContextRequest, intent: ResolvedIntent) -> list[str]:
    if request.target_type == "scene":
        return [request.target_id]
    if intent.narrative_scope == "fragment" and request.target_type == "scene":
        return [request.target_id]
    return []
