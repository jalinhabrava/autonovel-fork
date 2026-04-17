from __future__ import annotations

from context_engine.contracts import ContextEntry, ContextPack, ContextPolicy, ContextRequest, ResolvedIntent, ResolvedScope, ScoredCandidate
from interactive.query import extract_summary


def build_context_pack(
    request: ContextRequest,
    intent: ResolvedIntent,
    scope: ResolvedScope,
    policy: ContextPolicy,
    ranked_candidates: list[ScoredCandidate],
) -> ContextPack:
    budgets = _effective_budgets(policy, request.token_budget)
    hard_constraints = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "hard_constraints"],
        budgets["hard_constraints"],
    )
    narrative_context = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "narrative_context"],
        budgets["narrative_context"],
    )
    evidence = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "evidence"],
        budgets["evidence"],
    )

    voice_candidates = [candidate for candidate in ranked_candidates if candidate.section == "voice_context"]
    project_voice = _consume_section(
        [candidate for candidate in voice_candidates if candidate.candidate.artifact_kind == "root_artifact"],
        int(budgets["voice_context"] * 0.7),
    )
    remaining_voice_budget = max(budgets["voice_context"] - _entry_cost_total(project_voice), 0)
    character_voice = _consume_section(
        [candidate for candidate in voice_candidates if candidate.candidate.artifact_type == "character"],
        remaining_voice_budget,
    )

    return ContextPack(
        type="context_pack",
        intent=intent.name,
        scope={
            "narrative_scope": scope.narrative_scope,
            "retrieval_scope": scope.retrieval_scope,
            "target_id": scope.target_id,
            "chapter_refs": scope.chapter_refs,
            "scene_refs": scope.scene_refs,
            "character_ids": scope.character_ids,
        },
        policy={
            "name": policy.name,
            "token_budget": request.token_budget,
            "section_budgets": {
                "hard_constraints": budgets["hard_constraints"],
                "narrative_context": budgets["narrative_context"],
                "voice_context": budgets["voice_context"],
                "evidence": budgets["evidence"],
            },
        },
        hard_constraints=tuple(hard_constraints),
        narrative_context=tuple(narrative_context),
        voice_context={
            "project_voice": tuple(project_voice),
            "character_voice": tuple(character_voice),
        },
        evidence=tuple(evidence),
        meta={
            "generated_by": "context_engine_v1",
            "candidate_counts": {
                "hard_constraints": len(hard_constraints),
                "narrative_context": len(narrative_context),
                "project_voice": len(project_voice),
                "character_voice": len(character_voice),
                "evidence": len(evidence),
            },
            "target_type": request.target_type,
        },
    )


def _consume_section(candidates: list[ScoredCandidate], budget: int) -> list[ContextEntry]:
    entries: list[ContextEntry] = []
    spent = 0
    for scored in candidates:
        content = _render_content(scored)
        cost = _entry_cost(content)
        if entries and spent + cost > budget:
            continue
        entry = ContextEntry(
            id=scored.candidate.id,
            artifact_kind=scored.candidate.artifact_kind,
            artifact_type=scored.candidate.artifact_type,
            title=scored.candidate.title,
            status=scored.candidate.status,
            reason=scored.candidate.reason,
            content=content,
            path=scored.candidate.path,
            score=scored.score.total,
            score_breakdown={
                "total": scored.score.total,
                "selection_weight": scored.score.selection_weight,
                "status_weight": scored.score.status_weight,
                "scope_bonus": scored.score.scope_bonus,
                "query_bonus": scored.score.query_bonus,
                "target_bonus": scored.score.target_bonus,
                "reason": scored.score.reason,
            },
            source_refs=scored.candidate.source_refs,
            line_span=scored.candidate.line_span,
        )
        entries.append(entry)
        spent += cost
    return entries


def _render_content(scored: ScoredCandidate) -> str:
    content = scored.candidate.content.strip()
    if not content:
        return ""
    if scored.literality >= 0.85:
        return content
    if scored.literality >= 0.5:
        target_words = max(40, int(len(content.split()) * scored.literality * 0.7))
        return _truncate_words(extract_summary(content, content[: max(240, target_words * 6)]), target_words)
    target_words = max(18, int(len(content.split()) * max(scored.literality, 0.1) * 0.45))
    return _truncate_words(extract_summary(content, content[: max(140, target_words * 5)]), target_words)


def _entry_cost(content: str) -> int:
    return max(1, len(content.split()))


def _entry_cost_total(entries: list[ContextEntry]) -> int:
    return sum(_entry_cost(entry.content) for entry in entries)


def _truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip() + "..."


def _effective_budgets(policy: ContextPolicy, token_budget: int) -> dict[str, int]:
    base = {
        "hard_constraints": policy.section_budgets.hard_constraints,
        "narrative_context": policy.section_budgets.narrative_context,
        "voice_context": policy.section_budgets.voice_context,
        "evidence": policy.section_budgets.evidence,
    }
    base_total = sum(base.values())
    if token_budget <= 0 or token_budget == base_total:
        return base
    ratio = token_budget / base_total
    scaled = {key: max(1, int(value * ratio)) for key, value in base.items()}
    return scaled
