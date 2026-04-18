from __future__ import annotations

from typing import Any

from textifai.derived_sources.contracts import (
    DERIVED_REVIEW_STATUS_CATALOG,
    DERIVED_STRUCTURE_KIND_CATALOG,
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSegmentCandidate,
    DerivedSourceReview,
    DerivedStructureSignals,
    FormatExtractionProfile,
    ValidatedDerivedExtraction,
)


def normalize_derived_llm_payload(
    *,
    payload: dict[str, Any],
    source_id: str,
    source_format: str,
    llm_used: bool,
    format_profile: FormatExtractionProfile,
) -> DerivedLLMExtractionPayload | None:
    if not isinstance(payload, dict):
        return None
    segment_candidates = [
        candidate
        for item in payload.get("segment_candidates", [])
        if (candidate := _normalize_segment_candidate(item)) is not None
    ]
    structure_signals = _normalize_structure_signals(payload.get("structure_signals"))
    loss_signals = _normalize_loss_signals(payload.get("loss_signals"))
    return DerivedLLMExtractionPayload(
        source_id=source_id,
        source_format=source_format,
        dominant_language=_clean_text(payload.get("dominant_language")),
        detected_languages=_normalize_string_list(payload.get("detected_languages")),
        has_mixed_language=bool(payload.get("has_mixed_language", False)),
        overall_confidence=_coerce_float(payload.get("overall_confidence")),
        structural_confidence=_coerce_float(payload.get("structural_confidence")),
        content_mix_signals=_normalize_string_list(payload.get("content_mix_signals")),
        warnings=_normalize_string_list(payload.get("warnings")),
        segment_candidates=segment_candidates,
        structure_signals=structure_signals,
        loss_signals=loss_signals,
        needs_manual_review=bool(payload.get("needs_manual_review", False)),
        recognized_or_recovered_text=_clean_text(payload.get("recognized_or_recovered_text")) or "",
        llm_escalation_reasons=list(format_profile.llm_escalation_reasons),
        raw_payload=dict(payload),
    )


def validate_derived_extraction(
    *,
    seed,
    payload: DerivedLLMExtractionPayload | None,
) -> ValidatedDerivedExtraction:
    if payload is None:
        if seed.format_profile is None:
            review_status = "pending"
            requires_confirmation = True
            confidence = 0.0
            structural_confidence = 0.0
        else:
            profile = seed.format_profile
            if profile.is_native_text:
                review_status = "usable"
                requires_confirmation = False
            elif profile.llm_escalation_required:
                review_status = "pending"
                requires_confirmation = True
            elif profile.text_fidelity_confidence >= 0.85 and profile.structural_fidelity_confidence >= 0.8:
                review_status = "usable_with_warnings"
                requires_confirmation = False
            else:
                review_status = "pending"
                requires_confirmation = True
            confidence = profile.text_fidelity_confidence
            structural_confidence = profile.structural_fidelity_confidence
        return ValidatedDerivedExtraction(
            source_id=seed.source_id,
            source_format=seed.source_format,
            recognized_or_recovered_text=seed.raw_extracted_text,
            segment_candidates=[],
            structure_signals=DerivedStructureSignals(),
            loss_signals=DerivedLossSignals(
                missing_structure_signals=list(seed.quality_signals),
                severity="high" if seed.format_profile and seed.format_profile.llm_escalation_required else "low",
            ),
            detected_languages=list(seed.detected_languages),
            dominant_language=seed.dominant_language,
            has_mixed_language=seed.has_mixed_language,
            format_profile=seed.format_profile,
            llm_used=False,
            confidence=confidence,
            structural_confidence=structural_confidence,
            warnings=list(seed.warnings),
            notes=["llm_unavailable_or_not_used"],
            requires_confirmation=requires_confirmation,
            review_status=review_status,
        )

    review_status = "usable"
    notes: list[str] = []
    if payload.needs_manual_review or payload.loss_signals.severity in {"high", "critical"}:
        review_status = "needs_correction"
    elif payload.warnings or payload.content_mix_signals or payload.has_mixed_language:
        review_status = "usable_with_warnings"
    if payload.overall_confidence < 0.45 or payload.structural_confidence < 0.45:
        review_status = "pending"
    if payload.overall_confidence < 0.25 or payload.structural_confidence < 0.25:
        review_status = "needs_correction"
    if seed.format_profile and seed.format_profile.llm_escalation_required and review_status == "usable":
        review_status = "usable_with_warnings"
    if payload.recognized_or_recovered_text.strip():
        notes.append("llm_recovered_text")
    if payload.loss_signals.heading_loss_signals:
        notes.extend(payload.loss_signals.heading_loss_signals)
    if payload.loss_signals.ordering_uncertainty_signals:
        notes.extend(payload.loss_signals.ordering_uncertainty_signals)
    if payload.loss_signals.paragraph_merge_signals:
        notes.extend(payload.loss_signals.paragraph_merge_signals)
    if payload.loss_signals.coverage_risk_notes:
        notes.extend(payload.loss_signals.coverage_risk_notes)
    if payload.content_mix_signals:
        notes.extend(payload.content_mix_signals)
    return ValidatedDerivedExtraction(
        source_id=payload.source_id,
        source_format=payload.source_format,
        recognized_or_recovered_text=payload.recognized_or_recovered_text or seed.raw_extracted_text,
        segment_candidates=payload.segment_candidates,
        structure_signals=payload.structure_signals,
        loss_signals=payload.loss_signals,
        detected_languages=payload.detected_languages or list(seed.detected_languages),
        dominant_language=payload.dominant_language or seed.dominant_language,
        has_mixed_language=payload.has_mixed_language or seed.has_mixed_language,
        format_profile=seed.format_profile,
        llm_used=True,
        confidence=payload.overall_confidence,
        structural_confidence=payload.structural_confidence,
        warnings=list(dict.fromkeys([*seed.warnings, *payload.warnings])),
        notes=list(dict.fromkeys(notes)),
        requires_confirmation=payload.needs_manual_review or payload.loss_signals.severity in {"high", "critical"},
        review_status=review_status,
    )


def _normalize_segment_candidate(value: Any) -> DerivedSegmentCandidate | None:
    if not isinstance(value, dict):
        return None
    candidate_id = _clean_text(value.get("candidate_id"))
    segment_text = _clean_text(value.get("segment_text"))
    if not candidate_id or not segment_text:
        return None
    probable_kind = _clean_text(value.get("probable_kind")) or "uncertain"
    if probable_kind not in DERIVED_STRUCTURE_KIND_CATALOG:
        probable_kind = "uncertain"
    return DerivedSegmentCandidate(
        candidate_id=candidate_id,
        segment_text=segment_text,
        heading_text=_clean_text(value.get("heading_text")),
        probable_kind=probable_kind,
        language=_clean_text(value.get("language")),
        confidence=_coerce_float(value.get("confidence")),
        mixed_content=bool(value.get("mixed_content", False)),
        boundary_hints=_normalize_string_list(value.get("boundary_hints")),
        notes=_normalize_string_list(value.get("notes")),
    )


def _normalize_structure_signals(value: Any) -> DerivedStructureSignals:
    if not isinstance(value, dict):
        return DerivedStructureSignals()
    return DerivedStructureSignals(
        recovered_headings=_normalize_string_list(value.get("recovered_headings")),
        probable_block_order=_normalize_string_list(value.get("probable_block_order")),
        recovered_lists=_normalize_string_list(value.get("recovered_lists")),
        ordering_confidence=_coerce_float(value.get("ordering_confidence")),
        structure_warnings=_normalize_string_list(value.get("structure_warnings")),
        confidence=_coerce_float(value.get("confidence")),
    )


def _normalize_loss_signals(value: Any) -> DerivedLossSignals:
    if not isinstance(value, dict):
        return DerivedLossSignals()
    return DerivedLossSignals(
        missing_structure_signals=_normalize_string_list(value.get("missing_structure_signals")),
        paragraph_merge_signals=_normalize_string_list(value.get("paragraph_merge_signals")),
        heading_loss_signals=_normalize_string_list(value.get("heading_loss_signals")),
        ordering_uncertainty_signals=_normalize_string_list(value.get("ordering_uncertainty_signals")),
        coverage_risk_notes=_normalize_string_list(value.get("coverage_risk_notes")),
        severity=_clean_text(value.get("severity")) or "low",
        mixed_language_degradation=_normalize_string_list(value.get("mixed_language_degradation")),
    )


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _coerce_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
