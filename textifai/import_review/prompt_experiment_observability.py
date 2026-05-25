from __future__ import annotations

from copy import deepcopy
from typing import Any

PROMPT_CHANGE_TYPES = [
    "json_reliability",
    "density_boost",
    "section_completion",
    "objects_events_relations_focus",
    "unresolved_mentions_focus",
    "internal_check",
    "schema_skeleton",
    "balanced_knowledge_base",
]

FAILURE_MODE_TAXONOMY: dict[str, str] = {
    "invalid_json_markdown": "Output used markdown fences or markdown structure instead of raw JSON object.",
    "invalid_json_extra_text": "Output wrapped JSON with extra narrative or prefatory text.",
    "invalid_json_truncated": "Output appears cut off before closing JSON structure.",
    "invalid_json_reasoning_leak": "Output leaked hidden reasoning or checklist text into final response.",
    "invalid_json_unknown": "Output was not parseable JSON, but exact cause is unknown from safe metadata.",
    "valid_json_wrong_shape": "JSON parsed but top-level or chapter structure did not match expected schema shape.",
    "valid_json_missing_required_sections": "JSON parsed but required extraction sections were missing.",
    "valid_json_wrong_chapter": "JSON parsed but chapter identifier did not match requested chapter.",
    "valid_json_thin": "JSON parsed and shape passed, but semantic density stayed too low for useful extraction.",
    "valid_json_low_objects": "JSON parsed but object coverage stayed too low.",
    "valid_json_low_events": "JSON parsed but event coverage stayed too low.",
    "valid_json_low_relations": "JSON parsed but relation coverage stayed too low.",
    "valid_json_zero_unresolved": "JSON parsed but unresolved important mentions collapsed to zero in ambiguous context.",
    "provider_empty_response": "Provider returned empty text or no usable content.",
    "provider_error": "Provider call failed before usable response payload.",
    "validation_failed_missing_event_importance": "Validation failed because events lacked event_importance.",
    "validation_failed_missing_relation_category": "Validation failed because relations lacked relation_category.",
}

SAFE_VARIANT_DECISIONS = {"keep", "mutate", "discard", "needs_repeat"}


def classify_failure_mode(result_summary: dict[str, Any]) -> str | None:
    parseable = bool(result_summary.get("parseable_json", result_summary.get("response_parseable_json", False)))
    validation_ok = bool(result_summary.get("validation_ok", False))
    failure_hint = str(result_summary.get("failure_hint", result_summary.get("json_failure_hint", ""))).strip().casefold()
    missing_sections = list(result_summary.get("missing_required_sections", []) or result_summary.get("missing_sections", []) or [])
    chapter_id_ok = result_summary.get("chapter_id_ok", True)
    counts = deepcopy(result_summary.get("counts", {}) or {})
    ambiguous_context = bool(result_summary.get("ambiguous_context", False))
    warnings = {str(item) for item in (result_summary.get("warnings") or [])}

    if result_summary.get("provider_error"):
        return "provider_error"
    if result_summary.get("provider_empty_response"):
        return "provider_empty_response"

    if not parseable:
        if "markdown" in failure_hint:
            return "invalid_json_markdown"
        if "trunc" in failure_hint:
            return "invalid_json_truncated"
        if "reason" in failure_hint or "checklist" in failure_hint:
            return "invalid_json_reasoning_leak"
        if "extra" in failure_hint or "prefix" in failure_hint or "suffix" in failure_hint:
            return "invalid_json_extra_text"
        return "invalid_json_unknown"

    if result_summary.get("wrong_shape"):
        return "valid_json_wrong_shape"
    if missing_sections:
        return "valid_json_missing_required_sections"
    if chapter_id_ok is False:
        return "valid_json_wrong_chapter"
    if not validation_ok:
        if "events_missing_event_importance" in warnings or result_summary.get("event_importance_present") is False:
            return "validation_failed_missing_event_importance"
        if "relations_missing_relation_category" in warnings or result_summary.get("relation_category_present") is False:
            return "validation_failed_missing_relation_category"

    score = _number(result_summary.get("score"), result_summary.get("density_score"))
    if score is not None and score < 20:
        if counts.get("objects", 0) <= 1:
            return "valid_json_low_objects"
        if counts.get("events", 0) <= 1:
            return "valid_json_low_events"
        if counts.get("relations", 0) <= 2:
            return "valid_json_low_relations"
        if ambiguous_context and counts.get("unresolved_mentions", 0) == 0:
            return "valid_json_zero_unresolved"
        return "valid_json_thin"

    if counts.get("objects", 0) <= 1 and score is not None and score < 24:
        return "valid_json_low_objects"
    if counts.get("events", 0) <= 1 and score is not None and score < 24:
        return "valid_json_low_events"
    if counts.get("relations", 0) <= 2 and score is not None and score < 24:
        return "valid_json_low_relations"
    if ambiguous_context and counts.get("unresolved_mentions", 0) == 0 and score is not None and score < 24:
        return "valid_json_zero_unresolved"
    return None


def classify_variant_decision(
    result_summary: dict[str, Any], *, packaged: bool = False, keep_for_mutation: bool = False, repeat_needed: bool = False
) -> str:
    if packaged:
        return "keep"
    if repeat_needed:
        return "needs_repeat"

    failure_mode = classify_failure_mode(result_summary)
    parseable = bool(result_summary.get("parseable_json", result_summary.get("response_parseable_json", False)))
    validation_ok = bool(result_summary.get("validation_ok", False))
    score = _number(result_summary.get("score"), result_summary.get("density_score"))

    if not parseable:
        return "discard"
    if keep_for_mutation:
        return "mutate"
    if validation_ok and score is not None and score >= 25:
        return "keep"
    if failure_mode in {
        "valid_json_thin",
        "valid_json_low_objects",
        "valid_json_low_events",
        "valid_json_low_relations",
        "valid_json_zero_unresolved",
    }:
        return "mutate"
    return "needs_repeat" if validation_ok else "discard"


def build_experiment_entry(
    *,
    experiment_id: str,
    provider_family: str,
    model: str,
    task: str,
    chapter_id: str,
    variant_id: str,
    parent_variant_id: str | None,
    variant_goal: str,
    hypothesis: str,
    prompt_change_type: list[str],
    expected_effect: str,
    risk: str,
    result_summary: dict[str, Any],
    decision: str | None = None,
) -> dict[str, Any]:
    if decision is None:
        decision = classify_variant_decision(result_summary)
    if decision not in SAFE_VARIANT_DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    return {
        "experiment_id": experiment_id,
        "provider_family": provider_family,
        "model": model,
        "task": task,
        "chapter_id": chapter_id,
        "variant_id": variant_id,
        "parent_variant_id": parent_variant_id,
        "variant_goal": variant_goal,
        "hypothesis": hypothesis,
        "prompt_change_type": list(prompt_change_type),
        "expected_effect": expected_effect,
        "risk": risk,
        "result_summary": deepcopy(result_summary),
        "failure_mode": classify_failure_mode(result_summary),
        "decision": decision,
    }


def _number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
