from __future__ import annotations

from adapters.vault_adapter import VaultProjectAdapter
from context_engine.builder import build_context_pack as build_context_pack_payload
from context_engine.contracts import ContextPack, ContextRequest
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
