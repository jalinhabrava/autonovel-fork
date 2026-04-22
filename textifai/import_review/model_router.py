from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from textifai.import_review.bootstrap_profile import BootstrapProfile
from textifai.import_review.empirical_ranker import EmpiricalPolicy, build_evidence_map, load_empirical_records, rank_models_with_evidence
from textifai.import_review.model_advisor import AdvisorRecommendation
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.provider_snapshot import ProviderSnapshot


@dataclass(frozen=True)
class ResolvedModelPlan:
    global_normalization_default_model: str
    chapter_extraction_default_model: str
    chapter_extraction_large_chapter_model: str
    chapter_extraction_high_complexity_model: str
    chapter_partial_extraction_default_model: str
    chapter_reduction_default_model: str
    entity_cleanup_default_model: str
    safe_default_model: str
    safe_structured_model: str
    safe_long_context_model: str

    def to_resolution(self) -> dict[str, Any]:
        return {
            "global_normalization": {"default_model": self.global_normalization_default_model},
            "chapter_extraction": {
                "default_model": self.chapter_extraction_default_model,
                "large_chapter_model": self.chapter_extraction_large_chapter_model,
                "high_complexity_model": self.chapter_extraction_high_complexity_model,
            },
            "chapter_partial_extraction": {"default_model": self.chapter_partial_extraction_default_model},
            "chapter_reduction": {"default_model": self.chapter_reduction_default_model},
            "entity_cleanup": {"default_model": self.entity_cleanup_default_model},
            "safe_models": {
                "safe_default_model": self.safe_default_model,
                "safe_structured_model": self.safe_structured_model,
                "safe_long_context_model": self.safe_long_context_model,
            },
        }


def resolve_model_plan(
    *,
    provider_name: str | None,
    requested_model: str | None,
    snapshot: ProviderSnapshot,
    profile: BootstrapProfile,
    advisor: AdvisorRecommendation | None,
    telemetry_path: Path,
    empirical_policy: EmpiricalPolicy,
) -> tuple[ResolvedModelPlan, dict[str, Any]]:
    explicit = str(requested_model or "").strip()
    if explicit and explicit.casefold() != "auto":
        plan = ResolvedModelPlan(
            global_normalization_default_model=explicit,
            chapter_extraction_default_model=explicit,
            chapter_extraction_large_chapter_model=explicit,
            chapter_extraction_high_complexity_model=explicit,
            chapter_partial_extraction_default_model=explicit,
            chapter_reduction_default_model=explicit,
            entity_cleanup_default_model=explicit,
            safe_default_model=explicit,
            safe_structured_model=explicit,
            safe_long_context_model=explicit,
        )
        return plan, {
            "provider_snapshot": _snapshot_to_json(snapshot),
            "bootstrap_profile": profile.to_json(),
            "advisor_recommendation": None,
            "guardrail_checks": [{"phase": "all", "status": "explicit_model_override", "model": explicit}],
            "empirical_evidence": {},
            "final_resolution": plan.to_resolution(),
        }

    safe_default_model = _select_safe_model(snapshot, ("gpt-4o-mini", "gpt-4.1-mini", "gpt-5-mini", "gpt-5.4-mini"))
    safe_structured_model = _select_safe_model(snapshot, ("gpt-5-mini", "gpt-5.4-mini", "gpt-4.1-mini", "gpt-4o-mini"))
    safe_long_context_model = _select_safe_model(snapshot, ("gpt-4.1-mini", "gpt-4.1", "gpt-5.2", "gpt-5.4"))

    empirical_evidence: dict[str, Any] = {}
    guardrail_checks: list[dict[str, Any]] = []
    telemetry_records = load_empirical_records(telemetry_path)

    def resolve_phase(
        *,
        phase: str,
        subcase: str,
        fallback_candidates: tuple[str, ...],
        complexity_bucket: str,
        needs_long_context: bool = False,
    ) -> str:
        nonlocal empirical_evidence, guardrail_checks
        advisor_phase = (advisor.plan.get(phase) if advisor else None) or {}
        advisor_candidate = str(advisor_phase.get(subcase) or "").strip()
        candidates = [candidate for candidate in [advisor_candidate, *fallback_candidates] if candidate]
        valid_candidates: list[str] = []
        invalid_rows: list[dict[str, Any]] = []
        for candidate in _dedupe_preserve_order(candidates):
            valid, reason = _validate_candidate(
                candidate,
                snapshot=snapshot,
                profile=profile,
                phase=phase,
                subcase=subcase,
                needs_long_context=needs_long_context,
            )
            row = {"phase": phase, "subcase": subcase, "model": candidate, "valid": valid, "reason": reason}
            guardrail_checks.append(row)
            if valid:
                valid_candidates.append(candidate)
            else:
                invalid_rows.append(row)
        if not valid_candidates:
            valid_candidates = [
                safe_long_context_model if needs_long_context else safe_structured_model,
                safe_default_model,
            ]
            valid_candidates = [candidate for candidate in _dedupe_preserve_order(valid_candidates) if candidate in snapshot.available_models]
        evidence_map = build_evidence_map(
            records=telemetry_records,
            phase=phase,
            complexity_bucket=complexity_bucket,
            policy=empirical_policy,
        )
        filtered_candidates: list[str] = []
        for candidate in valid_candidates:
            rejected, reason = _empirically_reject_candidate(
                candidate,
                phase=phase,
                evidence_map=evidence_map,
                policy=empirical_policy,
            )
            guardrail_checks.append(
                {
                    "phase": phase,
                    "subcase": subcase,
                    "model": candidate,
                    "valid": not rejected,
                    "reason": reason if rejected else "empirically_allowed",
                }
            )
            if not rejected:
                filtered_candidates.append(candidate)
        if filtered_candidates:
            valid_candidates = filtered_candidates
        else:
            valid_candidates = [
                candidate
                for candidate in _dedupe_preserve_order(
                    [safe_long_context_model if needs_long_context else safe_structured_model, safe_default_model]
                )
                if candidate in snapshot.available_models
            ]
        ranked_candidates, evidence_rows = rank_models_with_evidence(
            models=valid_candidates,
            phase=phase,
            complexity_bucket=complexity_bucket,
            telemetry_path=telemetry_path,
            policy=empirical_policy,
        )
        empirical_evidence[f"{phase}.{subcase}"] = evidence_rows
        return ranked_candidates[0] if ranked_candidates else (safe_long_context_model if needs_long_context else safe_default_model)

    plan = ResolvedModelPlan(
        global_normalization_default_model=resolve_phase(
            phase="global_normalization",
            subcase="default_model",
            fallback_candidates=(safe_long_context_model, safe_structured_model, safe_default_model),
            complexity_bucket="large_or_complex",
            needs_long_context=True,
        ),
        chapter_extraction_default_model=resolve_phase(
            phase="chapter_extraction",
            subcase="default_model",
            fallback_candidates=(safe_default_model, safe_structured_model, safe_long_context_model),
            complexity_bucket="small_clean",
        ),
        chapter_extraction_large_chapter_model=resolve_phase(
            phase="chapter_extraction",
            subcase="large_chapter_model",
            fallback_candidates=(safe_long_context_model, safe_structured_model, safe_default_model),
            complexity_bucket="large_or_complex",
            needs_long_context=True,
        ),
        chapter_extraction_high_complexity_model=resolve_phase(
            phase="chapter_extraction",
            subcase="high_complexity_model",
            fallback_candidates=(safe_structured_model, safe_default_model, safe_long_context_model),
            complexity_bucket="medium_complex",
        ),
        chapter_partial_extraction_default_model=resolve_phase(
            phase="chapter_partial_extraction",
            subcase="default_model",
            fallback_candidates=(safe_default_model, safe_structured_model, safe_long_context_model),
            complexity_bucket="medium_complex",
        ),
        chapter_reduction_default_model=resolve_phase(
            phase="chapter_reduction",
            subcase="default_model",
            fallback_candidates=(safe_default_model, safe_structured_model, safe_long_context_model),
            complexity_bucket="medium_complex",
        ),
        entity_cleanup_default_model=resolve_phase(
            phase="entity_cleanup",
            subcase="default_model",
            fallback_candidates=(safe_structured_model, safe_long_context_model, safe_default_model),
            complexity_bucket="medium_complex",
        ),
        safe_default_model=safe_default_model,
        safe_structured_model=safe_structured_model,
        safe_long_context_model=safe_long_context_model,
    )
    audit = {
        "provider_snapshot": _snapshot_to_json(snapshot),
        "bootstrap_profile": profile.to_json(),
        "advisor_recommendation": {
            "model_used": advisor.model_used,
            "plan": advisor.plan,
        }
        if advisor
        else None,
        "guardrail_checks": guardrail_checks,
        "empirical_evidence": empirical_evidence,
        "final_resolution": plan.to_resolution(),
    }
    return plan, audit


def _validate_candidate(
    candidate: str,
    *,
    snapshot: ProviderSnapshot,
    profile: BootstrapProfile,
    phase: str,
    subcase: str,
    needs_long_context: bool,
) -> tuple[bool, str]:
    if candidate not in snapshot.available_models:
        return False, "not_available_in_snapshot"
    if phase == "global_normalization" and candidate in {"gpt-4-turbo", "gpt-4-turbo-2024-04-09"}:
        return False, "phase_denylist_global_normalization"
    capabilities = get_model_capabilities(candidate)
    if not capabilities.supports_structured_outputs:
        return False, "structured_outputs_required"
    if needs_long_context and capabilities.context_window < max(128000, profile.token_p95 * 8):
        return False, "insufficient_long_context"
    if phase == "global_normalization" and capabilities.max_output_tokens < 12000:
        return False, "insufficient_output_for_global_normalization"
    if phase == "chapter_reduction" and capabilities.max_output_tokens < 3000:
        return False, "insufficient_output_for_chapter_reduction"
    return True, "ok"


def _empirically_reject_candidate(
    candidate: str,
    *,
    phase: str,
    evidence_map: dict[str, Any],
    policy: EmpiricalPolicy,
) -> tuple[bool, str]:
    evidence = evidence_map.get(candidate)
    if evidence is None:
        return False, "no_empirical_evidence"
    if evidence.weighted_samples < max(1.0, float(policy.min_samples_for_hard_preference) * 0.5):
        return False, "insufficient_empirical_samples"
    if phase == "global_normalization" and evidence.json_valid_rate <= 0.25:
        return True, "empirical_reject_low_json_valid_rate"
    if phase == "global_normalization" and evidence.stall_rate >= 0.5:
        return True, "empirical_reject_high_stall_rate"
    return False, "empirically_allowed"


def _select_safe_model(snapshot: ProviderSnapshot, preferred: tuple[str, ...]) -> str:
    for candidate in preferred:
        if candidate in snapshot.available_models:
            return candidate
    return snapshot.available_models[0]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _snapshot_to_json(snapshot: ProviderSnapshot) -> dict[str, Any]:
    return {
        "provider_name": snapshot.provider_name,
        "fetched_at": snapshot.fetched_at,
        "source": snapshot.source,
        "available_models": snapshot.available_models,
        "models": [
            {
                "model": item.model,
                "available": item.available,
                "capabilities": asdict(item.capabilities),
            }
            for item in snapshot.models
        ],
    }
