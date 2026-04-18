from __future__ import annotations

from textifai.author_understanding.contracts import DisambiguationResult
from textifai.author_understanding.normalization import normalize_candidate_target
from textifai.editorial_intent.contracts import CandidateTarget


def disambiguate_targets(
    candidate_targets: list[CandidateTarget],
    *,
    minimum_confidence: float = 0.8,
    minimum_gap: float = 0.12,
) -> DisambiguationResult:
    targets = _dedupe_candidate_targets(candidate_targets)
    if not targets:
        return DisambiguationResult(
            candidate_targets=[],
            preferred_target=None,
            confidence=0.0,
            reason="No vault-backed target candidates were available.",
            requires_user_confirmation=True,
        )

    top = targets[0]
    second = targets[1] if len(targets) > 1 else None
    if len(targets) == 1 and top.confidence >= minimum_confidence:
        return DisambiguationResult(
            candidate_targets=targets,
            preferred_target=top,
            confidence=top.confidence,
            reason="A single vault-backed candidate was strong enough to use safely.",
            requires_user_confirmation=False,
        )

    if top.confidence >= minimum_confidence and (
        second is None or (top.confidence - second.confidence) >= minimum_gap
    ):
        return DisambiguationResult(
            candidate_targets=targets,
            preferred_target=top,
            confidence=top.confidence,
            reason="The top vault-backed candidate clearly dominates the alternatives.",
            requires_user_confirmation=False,
        )

    return DisambiguationResult(
        candidate_targets=targets,
        preferred_target=None,
        confidence=top.confidence,
        reason="Multiple plausible vault-backed targets remain; user confirmation is safer.",
        requires_user_confirmation=True,
    )


def _dedupe_candidate_targets(candidate_targets: list[CandidateTarget]) -> list[CandidateTarget]:
    deduped: dict[tuple[str, str], CandidateTarget] = {}
    for target in candidate_targets:
        normalized = normalize_candidate_target(target)
        if normalized is None:
            continue
        key = (normalized.target_type, normalized.target_id)
        if key not in deduped or normalized.confidence > deduped[key].confidence:
            deduped[key] = normalized
    return sorted(deduped.values(), key=lambda item: (item.confidence, item.target_type, item.target_id), reverse=True)
