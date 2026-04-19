from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from typing import Any

from textifai.author_understanding.contracts import (
    ANALYSIS_SOURCE_CATALOG,
    AUTHOR_INTENT_TYPE_CATALOG,
    MIXED_PART_TYPE_CATALOG,
    AuthorIntentInterpretation,
    DisambiguationResult,
    LLMAuthorUnderstandingPayload,
    LLMInterpretationResult,
    MixedRequestAnalysis,
    MixedRequestPart,
)
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityHint
from vault.schema import slugify


_INTENT_SYNONYMS = {
    "narration_prep": "narration_preparation",
    "prepare_narration": "narration_preparation",
    "prepare_for_writing": "narration_preparation",
    "writing_prep": "narration_preparation",
    "prepare review": "review_handoff",
    "prepare_review": "review_handoff",
    "review": "review_handoff",
    "validation": "validation_request",
    "validate": "validation_request",
    "followup": "contextual_followup",
    "follow-up": "contextual_followup",
    "mixed": "mixed_request",
    "structuring": "structuring_request",
    "revision": "editorial_revision",
    "narrative facts": "narrative_facts",
}

_PART_TYPE_SYNONYMS = {
    "narrative": "narrative_content",
    "facts": "narrative_content",
    "content": "narrative_content",
    "change": "revision",
    "revise": "revision",
    "preservation": "preserve",
    "follow-up": "followup_reference",
    "followup": "followup_reference",
    "prep": "narration_prep",
    "narration": "narration_prep",
    "handoff": "narration_prep",
    "review": "review_handoff",
    "validate": "validation_request",
}


def extract_json_payload(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else stripped
    if candidate.startswith("{") and candidate.endswith("}"):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_author_intent_type(value: Any, *, default: str = "unknown") -> str:
    normalized = _normalize_catalog_value(value, AUTHOR_INTENT_TYPE_CATALOG, default=default)
    return normalized


def normalize_mixed_request_part(value: Any) -> MixedRequestPart | None:
    raw = _coerce_mapping(value)
    if raw is None:
        return None
    part_type = _normalize_catalog_value(raw.get("part_type"), MIXED_PART_TYPE_CATALOG, default="mixed")
    text = str(raw.get("text") or "").strip()
    confidence = _coerce_confidence(raw.get("confidence"), default=0.0)
    if not text:
        return None
    if part_type is None:
        part_type = "mixed"
    return MixedRequestPart(part_type=part_type, text=text, confidence=confidence)


def normalize_candidate_target(value: Any) -> CandidateTarget | None:
    raw = _coerce_mapping(value)
    if raw is None:
        return None
    target_id = str(raw.get("target_id") or raw.get("artifact_id") or "").strip()
    target_type = str(raw.get("target_type") or raw.get("artifact_type") or "").strip()
    if not target_id or not target_type:
        return None
    return CandidateTarget(
        target_id=target_id,
        target_type=target_type,
        confidence=_coerce_confidence(raw.get("confidence"), default=0.0),
    )


def normalize_disambiguation_result(value: Any) -> DisambiguationResult | None:
    raw = _coerce_mapping(value)
    if raw is None:
        return None
    candidate_targets = [
        candidate
        for item in raw.get("candidate_targets", [])
        if (candidate := normalize_candidate_target(item)) is not None
    ]
    preferred_target = normalize_candidate_target(raw.get("preferred_target"))
    if preferred_target is not None and preferred_target not in candidate_targets:
        candidate_targets = [preferred_target, *candidate_targets]
    reason = str(raw.get("reason") or "").strip()
    return DisambiguationResult(
        candidate_targets=_dedupe_candidate_targets(candidate_targets),
        preferred_target=preferred_target,
        confidence=_coerce_confidence(raw.get("confidence"), default=0.0),
        reason=reason,
        requires_user_confirmation=bool(raw.get("requires_user_confirmation", False)),
    )


def normalize_author_understanding_payload(
    *,
    raw_text: str,
    payload: dict[str, Any],
    provider_name: str | None,
    model: str | None,
) -> LLMAuthorUnderstandingPayload | None:
    if not isinstance(payload, dict):
        return None

    primary_intent_type = _normalize_catalog_value(payload.get("primary_intent_type"), AUTHOR_INTENT_TYPE_CATALOG, default="unknown")
    secondary_intent_types = [
        item
        for item in (
            _normalize_catalog_value(value, AUTHOR_INTENT_TYPE_CATALOG, default=None)
            for value in payload.get("secondary_intent_types", [])
        )
        if item is not None and item != primary_intent_type
    ]
    parts = [
        part
        for item in payload.get("parts", [])
        if (part := normalize_mixed_request_part(item)) is not None
    ]
    entity_hints = [
        hint
        for item in payload.get("entity_hints", [])
        if (hint := normalize_entity_hint(item)) is not None
    ]
    candidate_targets = [
        candidate
        for item in payload.get("candidate_targets", [])
        if (candidate := normalize_candidate_target(item)) is not None
    ]
    preferred_target = normalize_candidate_target(payload.get("preferred_target"))
    if preferred_target is not None and preferred_target not in candidate_targets:
        candidate_targets = [preferred_target, *candidate_targets]
    raw_payload = dict(payload)
    return LLMAuthorUnderstandingPayload(
        raw_text=raw_text,
        provider_name=provider_name,
        model=model,
        primary_intent_type=primary_intent_type,
        secondary_intent_types=secondary_intent_types,
        confidence=_coerce_confidence(payload.get("confidence"), default=0.0),
        has_mixed_request=bool(payload.get("has_mixed_request", False)) or len(parts) > 1,
        author_goal_signals=_normalize_signal_list(payload.get("author_goal_signals")),
        preserve_signals=_normalize_signal_list(payload.get("preserve_signals")),
        change_signals=_normalize_signal_list(payload.get("change_signals")),
        entity_hints=entity_hints,
        followup_reference_text=_clean_text(payload.get("followup_reference_text")),
        narrative_content_text=_clean_text(payload.get("narrative_content_text")) or _join_part_texts(parts, {"narrative_content"}),
        meta_instruction_text=_clean_text(payload.get("meta_instruction_text"))
        or _join_part_texts(parts, {"meta_instruction", "narration_prep", "review_handoff", "validation_request"}),
        editorial_diagnosis=dict(payload.get("editorial_diagnosis") or {}),
        needs_clarification=bool(payload.get("needs_clarification", False)),
        clarification_reason=_clean_text(payload.get("clarification_reason")),
        parts=parts,
        candidate_targets=_dedupe_candidate_targets(candidate_targets),
        preferred_target=preferred_target,
        disambiguation_reason=_clean_text(payload.get("disambiguation_reason")),
        raw_payload=raw_payload,
    )


def normalize_llm_interpretation_result(
    *,
    raw_text: str,
    payload: dict[str, Any],
    provider_name: str | None,
    model: str | None,
) -> LLMInterpretationResult | None:
    return normalize_author_understanding_payload(
        raw_text=raw_text,
        payload=payload,
        provider_name=provider_name,
        model=model,
    )


def build_rule_based_author_intent(
    *,
    primary_intent_type: str,
    confidence: float,
    has_mixed_request: bool = False,
    author_goal_signals: list[str] | None = None,
    preserve_signals: list[str] | None = None,
    change_signals: list[str] | None = None,
    entity_hints: list[EntityHint] | None = None,
    followup_reference_text: str | None = None,
    narrative_content_text: str | None = None,
    meta_instruction_text: str | None = None,
    editorial_diagnosis: dict[str, Any] | None = None,
    needs_clarification: bool = False,
    clarification_reason: str | None = None,
    mixed_request_analysis: MixedRequestAnalysis | None = None,
    disambiguation: DisambiguationResult | None = None,
    source: str = "rule_based",
    metadata: dict[str, Any] | None = None,
) -> AuthorIntentInterpretation:
    return AuthorIntentInterpretation(
        primary_intent_type=normalize_author_intent_type(primary_intent_type),
        secondary_intent_types=[],
        confidence=_coerce_confidence(confidence, default=0.0),
        has_mixed_request=has_mixed_request,
        author_goal_signals=_dedupe_strings(author_goal_signals or []),
        preserve_signals=_dedupe_strings(preserve_signals or []),
        change_signals=_dedupe_strings(change_signals or []),
        entity_hints=list(entity_hints or []),
        followup_reference_text=_clean_text(followup_reference_text),
        narrative_content_text=_clean_text(narrative_content_text),
        meta_instruction_text=_clean_text(meta_instruction_text),
        editorial_diagnosis=dict(editorial_diagnosis or {}),
        needs_clarification=needs_clarification,
        clarification_reason=_clean_text(clarification_reason),
        mixed_request_analysis=mixed_request_analysis,
        disambiguation=disambiguation,
        source=source if source in ANALYSIS_SOURCE_CATALOG else "rule_based",
        metadata=dict(metadata or {}),
    )


def _normalize_signal_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return _dedupe_strings([str(value).strip() for value in values if str(value).strip()])


def normalize_entity_hint(value: Any) -> EntityHint | None:
    raw = _coerce_mapping(value)
    if raw is None:
        text = _clean_text(value)
        if text is None:
            return None
        return EntityHint(
            hint_text=text,
            normalized_hint=slugify(text),
            hint_kind="semantic_target",
            hint_source="conversation",
            confidence=0.4,
        )
    hint_text = _clean_text(raw.get("hint_text") or raw.get("surface_text") or raw.get("text"))
    normalized_hint = _clean_text(raw.get("normalized_hint")) or (hint_text.casefold().replace(" ", "_") if hint_text else None)
    if normalized_hint is not None:
        normalized_hint = slugify(normalized_hint)
    if hint_text is None or normalized_hint is None:
        return None
    return EntityHint(
        hint_text=hint_text,
        normalized_hint=normalized_hint,
        hint_kind=_normalize_catalog_value(
            raw.get("hint_kind"),
            ("semantic_target", "alias", "document_analysis", "narrative_signal", "project_alias"),
            default="semantic_target",
        )
        or "semantic_target",
        hint_source=_normalize_catalog_value(
            raw.get("hint_source"),
            ("author_understanding", "conversation", "document_analysis", "derived_source", "project_alias"),
            default="author_understanding",
        )
        or "author_understanding",
        language=_clean_text(raw.get("language")),
        confidence=_coerce_confidence(raw.get("confidence"), default=0.0),
        supported_by_author_understanding=bool(raw.get("supported_by_author_understanding", False)),
        supported_by_document_analysis=bool(raw.get("supported_by_document_analysis", False)),
        candidate_target_id=_clean_text(raw.get("candidate_target_id")),
        candidate_target_type=_clean_text(raw.get("candidate_target_type")),
    )


def _normalize_catalog_value(value: Any, catalog: tuple[str, ...], *, default: str | None) -> str | None:
    if value is None:
        return default
    normalized = str(value).strip().casefold().replace(" ", "_").replace("-", "_")
    normalized = _INTENT_SYNONYMS.get(normalized, normalized)
    normalized = _PART_TYPE_SYNONYMS.get(normalized, normalized)
    if normalized in catalog:
        return normalized
    return default


def _coerce_confidence(value: Any, *, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return None


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _dedupe_candidate_targets(targets: list[CandidateTarget]) -> list[CandidateTarget]:
    seen: dict[tuple[str, str], CandidateTarget] = {}
    for target in targets:
        key = (target.target_type, target.target_id)
        if key not in seen or target.confidence > seen[key].confidence:
            seen[key] = target
    return sorted(seen.values(), key=lambda item: (item.confidence, item.target_type, item.target_id), reverse=True)


def _join_part_texts(parts: list[MixedRequestPart], part_types: set[str]) -> str | None:
    texts = [part.text for part in parts if part.part_type in part_types and part.text.strip()]
    if not texts:
        return None
    content = " ".join(texts).strip()
    return content or None
