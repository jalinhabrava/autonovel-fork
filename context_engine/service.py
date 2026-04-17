from __future__ import annotations

from adapters.vault_adapter import VaultProjectAdapter
from context_engine.builder import build_context_pack as build_context_pack_payload
from context_engine.contracts import ContextDebugResult, ContextPack, ContextRequest
from context_engine.intents import resolve_intent
from context_engine.policies import get_policy
from context_engine.query import fetch_candidates
from context_engine.ranking import rank_candidates
from context_engine.scope import resolve_scope


def build_context_pack(vault_root: str, request: ContextRequest) -> ContextPack:
    adapter = VaultProjectAdapter(vault_root)
    policy = get_policy(request.policy_name)
    intent = resolve_intent(request)
    scope = resolve_scope(adapter, request, intent)
    candidates = fetch_candidates(adapter, scope)
    ranked = rank_candidates(request, intent, scope, policy, candidates)
    return build_context_pack_payload(request, intent, scope, policy, ranked)


def inspect_context(
    vault_root: str,
    request: ContextRequest,
    *,
    debug_mode: str = "summary",
    max_candidates: int = 10,
) -> ContextDebugResult:
    adapter = VaultProjectAdapter(vault_root)
    policy = get_policy(request.policy_name)
    intent = resolve_intent(request)
    scope = resolve_scope(adapter, request, intent)
    candidates = fetch_candidates(adapter, scope)
    ranked = rank_candidates(request, intent, scope, policy, candidates)
    pack = build_context_pack_payload(request, intent, scope, policy, ranked)

    serialized_candidates = _serialize_candidates(ranked, debug_mode=debug_mode, max_candidates=max_candidates)
    return ContextDebugResult(
        request={
            "intent": request.intent,
            "target_id": request.target_id,
            "target_type": request.target_type,
            "narrative_scope": request.narrative_scope,
            "retrieval_scope": request.retrieval_scope,
            "query_text": request.query_text,
            "chapter_refs": request.chapter_refs,
            "character_ids": request.character_ids,
            "policy_name": request.policy_name,
            "token_budget": request.token_budget,
        },
        resolved_intent={
            "name": intent.name,
            "narrative_scope": intent.narrative_scope,
            "retrieval_scope": intent.retrieval_scope,
            "target_type": intent.target_type,
        },
        resolved_scope={
            "narrative_scope": scope.narrative_scope,
            "retrieval_scope": scope.retrieval_scope,
            "target_id": scope.target_id,
            "chapter_refs": scope.chapter_refs,
            "scene_refs": scope.scene_refs,
            "character_ids": scope.character_ids,
        },
        policy={
            "name": policy.name,
            "selection_weights": policy.selection_weights,
            "status_priority": policy.status_priority,
            "section_budgets": {
                "hard_constraints": policy.section_budgets.hard_constraints,
                "narrative_context": policy.section_budgets.narrative_context,
                "voice_context": policy.section_budgets.voice_context,
                "evidence": policy.section_budgets.evidence,
            },
            "literality_by_artifact_type": policy.literality_by_artifact_type,
            "scope_radius": {
                key: {
                    "scene_neighbors": value.scene_neighbors,
                    "chapter_neighbors": value.chapter_neighbors,
                }
                for key, value in policy.scope_radius.items()
            },
        },
        candidates=tuple(serialized_candidates),
        context_pack=pack,
    )


def _serialize_candidates(ranked, *, debug_mode: str, max_candidates: int) -> list[dict]:
    serialized = []
    for index, scored in enumerate(ranked[:max_candidates], start=1):
        item = {
            "rank": index,
            "id": scored.candidate.id,
            "artifact_kind": scored.candidate.artifact_kind,
            "artifact_type": scored.candidate.artifact_type,
            "category": scored.candidate.category,
            "title": scored.candidate.title,
            "status": scored.candidate.status,
            "final_section": scored.section,
            "reason": scored.candidate.reason,
            "score": {
                "total": scored.score.total,
                "selection_weight": scored.score.selection_weight,
                "status_weight": scored.score.status_weight,
                "scope_bonus": scored.score.scope_bonus,
                "query_bonus": scored.score.query_bonus,
                "target_bonus": scored.score.target_bonus,
                "reason": scored.score.reason,
            },
            "literality": scored.literality,
            "path": scored.candidate.path,
            "source_refs": scored.candidate.source_refs,
        }
        if debug_mode == "full":
            item["content_preview"] = scored.candidate.content[:600]
            item["metadata"] = scored.candidate.metadata
            item["chapter_ref"] = scored.candidate.chapter_ref
            item["character_ids"] = scored.candidate.character_ids
        serialized.append(item)
    return serialized
