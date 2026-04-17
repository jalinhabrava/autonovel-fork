from __future__ import annotations

from context_engine.contracts import ContextRequest, IntentName, ResolvedIntent


DEFAULT_RETRIEVAL_SCOPE: dict[IntentName, tuple[str, ...]] = {
    "scene_write": ("canon", "lore", "voice", "characters", "scenes", "chapters", "outline"),
    "scene_rewrite": ("canon", "lore", "voice", "characters", "scenes", "chapters", "outline"),
    "chapter_context": ("canon", "lore", "voice", "characters", "scenes", "chapters", "outline"),
    "consistency_check": ("canon", "lore", "voice", "characters"),
    "canon_decision": ("canon", "lore", "characters", "chapters", "outline"),
    "bootstrap_extract": ("chapters", "voice", "characters", "canon", "lore", "timeline"),
    "world_lookup": ("canon", "lore", "voice", "characters", "timeline", "outline"),
    "context_search": ("canon", "lore", "voice", "characters", "scenes", "chapters", "timeline", "outline"),
}


DEFAULT_NARRATIVE_SCOPE: dict[IntentName, str] = {
    "scene_write": "scene",
    "scene_rewrite": "scene",
    "chapter_context": "chapter",
    "consistency_check": "fragment",
    "canon_decision": "chapter",
    "bootstrap_extract": "chapter",
    "world_lookup": "project",
    "context_search": "fragment",
}


INTENT_ALIASES: dict[str, IntentName] = {
    "scene_write": "scene_write",
    "write_scene": "scene_write",
    "scene_rewrite": "scene_rewrite",
    "rewrite_scene": "scene_rewrite",
    "chapter_context": "chapter_context",
    "consistency_check": "consistency_check",
    "verify": "consistency_check",
    "canon_decision": "canon_decision",
    "decide": "canon_decision",
    "bootstrap_extract": "bootstrap_extract",
    "world_lookup": "world_lookup",
    "world": "world_lookup",
    "context_search": "context_search",
    "artifact_search": "context_search",
    "lookup": "context_search",
}


def resolve_intent(request: ContextRequest) -> ResolvedIntent:
    raw = request.intent.strip().lower()
    try:
        name = INTENT_ALIASES[raw]
    except KeyError as exc:
        raise ValueError(f"Unsupported context intent: {request.intent}") from exc

    retrieval_scope = request.retrieval_scope or tuple(DEFAULT_RETRIEVAL_SCOPE[name])
    narrative_scope = request.narrative_scope or DEFAULT_NARRATIVE_SCOPE[name]
    return ResolvedIntent(
        name=name,
        narrative_scope=narrative_scope,
        retrieval_scope=tuple(retrieval_scope),
        target_type=request.target_type,
    )
