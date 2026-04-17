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
    hard_constraints, hard_meta = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "hard_constraints"],
        budgets["hard_constraints"],
    )
    narrative_context, narrative_meta = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "narrative_context"],
        budgets["narrative_context"],
    )
    evidence, evidence_meta = _consume_section(
        [candidate for candidate in ranked_candidates if candidate.section == "evidence"],
        budgets["evidence"],
    )

    voice_candidates = [candidate for candidate in ranked_candidates if candidate.section == "voice_context"]
    project_voice, project_voice_meta = _consume_section(
        [candidate for candidate in voice_candidates if candidate.candidate.artifact_kind == "root_artifact"],
        int(budgets["voice_context"] * 0.7),
    )
    remaining_voice_budget = max(budgets["voice_context"] - project_voice_meta["used_budget"], 0)
    character_voice, character_voice_meta = _consume_section(
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
            "budget_usage": {
                "hard_constraints": hard_meta,
                "narrative_context": narrative_meta,
                "project_voice": project_voice_meta,
                "character_voice": character_voice_meta,
                "evidence": evidence_meta,
            },
            "target_type": request.target_type,
        },
    )


def _consume_section(candidates: list[ScoredCandidate], budget: int) -> tuple[list[ContextEntry], dict]:
    entries: list[ContextEntry] = []
    excluded: list[dict] = []
    spent = 0
    for index, scored in enumerate(candidates, start=1):
        content, render_meta = _render_content(scored, budget_remaining=max(budget - spent, 1))
        cost = _entry_cost(content)
        if cost <= 0:
            excluded.append(
                {
                    "id": scored.candidate.id,
                    "reason": "empty_content_after_render",
                    "score": scored.score.total,
                }
            )
            continue
        if spent + cost > budget:
            if cost > budget and not entries and scored.score.total >= 1.8:
                content, render_meta = _render_content(
                    scored,
                    budget_remaining=max(int(budget * 0.75), 1),
                    force_stronger_compression=True,
                )
                cost = _entry_cost(content)
            if spent + cost > budget:
                excluded.append(
                    {
                        "id": scored.candidate.id,
                        "reason": "excluded_by_budget",
                        "score": scored.score.total,
                        "budget_remaining": max(budget - spent, 0),
                    }
                )
                continue
        if scored.score.total < 0.95 and spent > 0:
            excluded.append(
                {
                    "id": scored.candidate.id,
                    "reason": "below_relevance_threshold",
                    "score": scored.score.total,
                }
            )
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
            section_reason=scored.score.reason,
            selection_rank=index,
            effective_literality=render_meta["effective_literality"],
            content_mode_info=render_meta,
            source_refs=scored.candidate.source_refs,
            line_span=scored.candidate.line_span,
        )
        entries.append(entry)
        spent += cost
    return entries, {
        "available_budget": budget,
        "used_budget": spent,
        "remaining_budget": max(budget - spent, 0),
        "selected_count": len(entries),
        "excluded_count": len(excluded),
        "excluded_preview": excluded[:5],
    }


def _render_content(
    scored: ScoredCandidate,
    *,
    budget_remaining: int,
    force_stronger_compression: bool = False,
) -> tuple[str, dict]:
    content = scored.candidate.content.strip()
    if not content:
        return "", {
            "effective_literality": scored.literality,
            "artifact_type": scored.candidate.artifact_type,
            "source_words": 0,
            "rendered_words": 0,
            "compression_ratio": 1.0,
        }

    source_words = len(content.split())
    effective_literality = _effective_literality(scored.literality, budget_remaining, source_words, force_stronger_compression)
    if effective_literality >= 0.9:
        rendered = _truncate_words(content, min(source_words, budget_remaining))
    elif effective_literality >= 0.6:
        target_words = max(28, int(source_words * effective_literality * 0.75))
        rendered = _truncate_words(extract_summary(content, content[: max(220, target_words * 7)]), min(target_words, budget_remaining))
    else:
        target_words = max(14, int(source_words * max(effective_literality, 0.15) * 0.55))
        rendered = _truncate_words(extract_summary(content, content[: max(120, target_words * 6)]), min(target_words, budget_remaining))

    rendered_words = len(rendered.split())
    return rendered, {
        "effective_literality": round(effective_literality, 3),
        "artifact_type": scored.candidate.artifact_type,
        "source_words": source_words,
        "rendered_words": rendered_words,
        "compression_ratio": round(rendered_words / max(source_words, 1), 3),
    }


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


def _effective_literality(
    base_literality: float,
    budget_remaining: int,
    source_words: int,
    force_stronger_compression: bool,
) -> float:
    effective = base_literality
    if source_words > budget_remaining * 1.5:
        effective -= 0.15
    if source_words > budget_remaining * 2.5:
        effective -= 0.15
    if force_stronger_compression:
        effective -= 0.2
    return max(0.05, min(1.0, effective))
