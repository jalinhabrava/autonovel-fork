from __future__ import annotations

from context_engine.contracts import Candidate, ContextPolicy, ContextRequest, ResolvedIntent, ResolvedScope, ScoreBreakdown, ScoredCandidate
from interactive.chapter_selection import chapter_number_from_id


def rank_candidates(
    request: ContextRequest,
    intent: ResolvedIntent,
    scope: ResolvedScope,
    policy: ContextPolicy,
    candidates: list[Candidate],
) -> list[ScoredCandidate]:
    ranked: list[ScoredCandidate] = []
    for candidate in candidates:
        section = _assign_section(candidate)
        selection_weight = policy.selection_weights.get(candidate.category, 0.5)
        status_weight = policy.status_priority.get(candidate.status, 0.0)
        scope_bonus = _scope_bonus(candidate, scope, policy)
        query_bonus = _query_bonus(candidate, request.query_text)
        target_bonus = _target_bonus(candidate, scope)
        total = selection_weight + status_weight + scope_bonus + query_bonus + target_bonus
        ranked.append(
            ScoredCandidate(
                candidate=candidate,
                section=section,
                score=ScoreBreakdown(
                    total=round(total, 4),
                    selection_weight=selection_weight,
                    status_weight=status_weight,
                    scope_bonus=scope_bonus,
                    query_bonus=query_bonus,
                    target_bonus=target_bonus,
                    reason=_score_reason(candidate, scope, section),
                ),
                literality=_literality(candidate, policy),
            )
        )
    return sorted(ranked, key=lambda item: item.score.total, reverse=True)


def _assign_section(candidate: Candidate) -> str:
    if candidate.category in {"canon", "lore"} and candidate.status in {"validated", "pending_revision"}:
        return "hard_constraints"
    if candidate.category == "voice":
        return "voice_context"
    if candidate.category == "chapters":
        return "evidence"
    return "narrative_context"


def _scope_bonus(candidate: Candidate, scope: ResolvedScope, policy: ContextPolicy) -> float:
    radius = policy.scope_radius.get(scope.narrative_scope)
    bonus = 0.0
    if candidate.id == scope.target_id:
        bonus += 1.0
    if candidate.chapter_ref and candidate.chapter_ref in scope.chapter_refs:
        bonus += 0.7
    elif candidate.chapter_ref and scope.chapter_refs and radius:
        target_numbers = [chapter_number_from_id(ref) for ref in scope.chapter_refs]
        candidate_number = chapter_number_from_id(candidate.chapter_ref)
        if candidate_number is not None and any(number is not None for number in target_numbers):
            distances = [abs(candidate_number - number) for number in target_numbers if number is not None]
            if distances and min(distances) <= radius.chapter_neighbors:
                bonus += 0.35
    if scope.character_ids and set(scope.character_ids).intersection(set(candidate.character_ids)):
        bonus += 0.5
    if candidate.category in {"canon", "lore", "voice"} and not candidate.chapter_ref:
        bonus += 0.15
    return round(bonus, 4)


def _query_bonus(candidate: Candidate, query_text: str | None) -> float:
    if not query_text:
        return 0.0
    lowered = query_text.lower()
    haystack = f"{candidate.title}\n{candidate.content}".lower()
    if lowered in haystack:
        return 0.45
    return 0.0


def _target_bonus(candidate: Candidate, scope: ResolvedScope) -> float:
    bonuses = 0.0
    if scope.target_id.lower() in candidate.id.lower():
        bonuses += 0.4
    if scope.target_id.lower() in candidate.title.lower():
        bonuses += 0.25
    return round(bonuses, 4)


def _literality(candidate: Candidate, policy: ContextPolicy) -> float:
    return policy.literality_by_artifact_type.get(
        candidate.artifact_type,
        policy.literality_by_artifact_type.get(candidate.category, 0.5),
    )


def _score_reason(candidate: Candidate, scope: ResolvedScope, section: str) -> str:
    if candidate.id == scope.target_id:
        return f"direct target candidate placed in {section}"
    if candidate.chapter_ref and candidate.chapter_ref in scope.chapter_refs:
        return f"same-chapter candidate placed in {section}"
    if candidate.category == "voice":
        return "voice-layer candidate selected for voice_context"
    return f"{candidate.category} candidate selected for {section}"
