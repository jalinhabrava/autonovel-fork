from __future__ import annotations

from context_engine.contracts import ContextRequest
from interactive.payloads import validate_artifact_payload


def build_world_request(*, policy: str = "default", token_budget: int = 4000) -> ContextRequest:
    return ContextRequest(
        intent="world_lookup",
        target_id="world",
        target_type="project",
        narrative_scope="project",
        retrieval_scope=("canon", "lore", "voice", "characters", "timeline", "outline"),
        policy_name=policy,
        token_budget=token_budget,
    )


def build_find_request(
    query: str,
    *,
    policy: str = "default",
    token_budget: int = 3500,
) -> ContextRequest:
    return ContextRequest(
        intent="context_search",
        target_id=query,
        target_type="lookup",
        narrative_scope="fragment",
        retrieval_scope=("canon", "lore", "voice", "characters", "scenes", "chapters", "timeline", "outline"),
        query_text=query,
        policy_name=policy,
        token_budget=token_budget,
    )


def build_load_request(
    *,
    artifacts: list[str] | None = None,
    scene_ids: list[str] | None = None,
    chapter_ids: list[str] | None = None,
    policy: str = "default",
    token_budget: int = 4000,
) -> ContextRequest:
    retrieval_scope = []
    if artifacts:
        retrieval_scope.extend(_artifact_to_retrieval(artifact) for artifact in artifacts)
    if scene_ids:
        retrieval_scope.append("scenes")
    if chapter_ids:
        retrieval_scope.append("chapters")
    if not retrieval_scope:
        retrieval_scope = ["canon", "lore", "voice", "characters", "scenes", "chapters", "outline"]
    return ContextRequest(
        intent="chapter_context" if chapter_ids else "context_search",
        target_id=(scene_ids or chapter_ids or artifacts or ["load-context"])[0],
        target_type="scene" if scene_ids else "chapter" if chapter_ids else "load",
        narrative_scope="scene" if scene_ids else "chapter" if chapter_ids else "project",
        retrieval_scope=tuple(_dedupe(retrieval_scope)),
        chapter_refs=tuple(chapter_ids or []),
        policy_name=policy,
        token_budget=token_budget,
    )


def build_scene_request(scene_id: str, *, policy: str = "default", token_budget: int = 4000) -> ContextRequest:
    return ContextRequest(
        intent="scene_rewrite",
        target_id=scene_id,
        target_type="scene",
        narrative_scope="scene",
        retrieval_scope=("canon", "lore", "voice", "characters", "scenes", "chapters", "outline"),
        policy_name=policy,
        token_budget=token_budget,
    )


def build_chapter_request(chapter_id: str, *, policy: str = "default", token_budget: int = 4000) -> ContextRequest:
    return ContextRequest(
        intent="chapter_context",
        target_id=chapter_id,
        target_type="chapter",
        narrative_scope="chapter",
        retrieval_scope=("canon", "lore", "voice", "characters", "scenes", "chapters", "outline"),
        chapter_refs=(chapter_id,),
        policy_name=policy,
        token_budget=token_budget,
    )


def build_consistency_request(payload: dict, *, policy: str = "strict_canon", token_budget: int = 3200) -> ContextRequest:
    artifact = validate_artifact_payload(payload)
    text = f"{artifact['title']}\n{artifact['body']}"
    return ContextRequest(
        intent="consistency_check",
        target_id=artifact["entity_id"],
        target_type=artifact["artifact_type"],
        narrative_scope="fragment",
        retrieval_scope=("canon", "lore", "voice", "characters"),
        query_text=text[:1000],
        policy_name=policy,
        token_budget=token_budget,
    )


def build_explicit_request(
    *,
    intent: str,
    narrative_scope: str,
    retrieval_scope: list[str],
    target_id: str,
    target_type: str,
    policy: str,
    token_budget: int,
    query_text: str | None = None,
    chapter_refs: list[str] | None = None,
    character_ids: list[str] | None = None,
) -> ContextRequest:
    return ContextRequest(
        intent=intent,
        target_id=target_id,
        target_type=target_type,
        narrative_scope=narrative_scope,
        retrieval_scope=tuple(retrieval_scope),
        query_text=query_text,
        chapter_refs=tuple(chapter_refs or []),
        character_ids=tuple(character_ids or []),
        policy_name=policy,
        token_budget=token_budget,
    )


def _artifact_to_retrieval(artifact: str) -> str:
    mapping = {
        "world": "lore",
        "canon": "canon",
        "voice": "voice",
        "characters": "characters",
        "outline": "outline",
        "timeline": "timeline",
    }
    return mapping.get(artifact, "lore")


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
