from __future__ import annotations

from context_engine.service import build_context_pack, inspect_context
from interactive.context_requests import (
    build_chapter_request,
    build_explicit_request,
    build_find_request,
    build_load_request,
    build_scene_request,
    build_world_request,
)


def build_world_context(
    vault_root: str,
    *,
    policy: str = "default",
    token_budget: int = 4000,
) -> dict:
    request = build_world_request(policy=policy, token_budget=token_budget)
    return _pack_to_dict(build_context_pack(vault_root, request))


def build_find_context(
    vault_root: str,
    query: str,
    *,
    policy: str = "default",
    token_budget: int = 3500,
) -> dict:
    request = build_find_request(query, policy=policy, token_budget=token_budget)
    return _pack_to_dict(build_context_pack(vault_root, request))


def build_load_context(
    vault_root: str,
    *,
    artifacts: list[str] | None = None,
    scene_ids: list[str] | None = None,
    chapter_ids: list[str] | None = None,
    policy: str = "default",
    token_budget: int = 4000,
) -> dict:
    request = build_load_request(
        artifacts=artifacts,
        scene_ids=scene_ids,
        chapter_ids=chapter_ids,
        policy=policy,
        token_budget=token_budget,
    )
    return _pack_to_dict(build_context_pack(vault_root, request))


def build_scene_context(
    vault_root: str,
    scene_id: str,
    *,
    policy: str = "default",
    token_budget: int = 4000,
) -> dict:
    request = build_scene_request(scene_id, policy=policy, token_budget=token_budget)
    return _pack_to_dict(build_context_pack(vault_root, request))


def build_chapter_context(
    vault_root: str,
    chapter_id: str,
    *,
    policy: str = "default",
    token_budget: int = 4000,
) -> dict:
    request = build_chapter_request(chapter_id, policy=policy, token_budget=token_budget)
    return _pack_to_dict(build_context_pack(vault_root, request))


def debug_context(
    vault_root: str,
    *,
    intent: str,
    narrative_scope: str,
    retrieval_scope: list[str],
    target_id: str,
    target_type: str,
    policy: str = "default",
    token_budget: int = 4000,
    query_text: str | None = None,
    chapter_refs: list[str] | None = None,
    character_ids: list[str] | None = None,
    debug_mode: str = "summary",
    max_candidates: int = 10,
) -> dict:
    request = build_explicit_request(
        intent=intent,
        narrative_scope=narrative_scope,
        retrieval_scope=retrieval_scope,
        target_id=target_id,
        target_type=target_type,
        policy=policy,
        token_budget=token_budget,
        query_text=query_text,
        chapter_refs=chapter_refs,
        character_ids=character_ids,
    )
    result = inspect_context(
        vault_root,
        request,
        debug_mode=debug_mode,
        max_candidates=max_candidates,
    )
    return _debug_to_dict(result)


def _pack_to_dict(pack) -> dict:
    return {
        "type": pack.type,
        "intent": pack.intent,
        "scope": pack.scope,
        "policy": pack.policy,
        "hard_constraints": [_entry_to_dict(entry) for entry in pack.hard_constraints],
        "narrative_context": [_entry_to_dict(entry) for entry in pack.narrative_context],
        "voice_context": {
            "project_voice": [_entry_to_dict(entry) for entry in pack.voice_context["project_voice"]],
            "character_voice": [_entry_to_dict(entry) for entry in pack.voice_context["character_voice"]],
        },
        "evidence": [_entry_to_dict(entry) for entry in pack.evidence],
        "meta": pack.meta,
    }


def _debug_to_dict(result) -> dict:
    return {
        "request": result.request,
        "resolved_intent": result.resolved_intent,
        "resolved_scope": result.resolved_scope,
        "policy": result.policy,
        "candidates": list(result.candidates),
        "context_pack": _pack_to_dict(result.context_pack),
    }


def _entry_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "artifact_kind": entry.artifact_kind,
        "artifact_type": entry.artifact_type,
        "title": entry.title,
        "status": entry.status,
        "reason": entry.reason,
        "content": entry.content,
        "path": entry.path,
        "score": entry.score,
        "score_breakdown": entry.score_breakdown,
        "source_refs": list(entry.source_refs),
        "line_span": entry.line_span,
    }
