from __future__ import annotations

from textifai.derived_sources.contracts import (
    DerivedExtractionSeed,
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSourceReview,
    LLMEscalationDecision,
    DerivedStructureSignals,
    ValidatedDerivedExtraction,
)


def review_derived_source(
    *,
    seed: DerivedExtractionSeed,
    escalation: LLMEscalationDecision,
    validated_extraction: ValidatedDerivedExtraction | None,
    llm_payload: DerivedLLMExtractionPayload | None,
) -> DerivedSourceReview:
    llm_used = llm_payload is not None
    notes: list[str] = []
    final_confidence = seed.format_profile.text_fidelity_confidence if seed.format_profile else 0.0
    strict_confirmation_required = bool(escalation.required)
    review_status = "pending"
    loss_report = validated_extraction.loss_signals if validated_extraction else DerivedLossSignals(
        missing_structure_signals=list(seed.quality_signals),
        coverage_risk_notes=list(seed.warnings),
        severity="high" if escalation.required else "low",
    )
    recovery_report = validated_extraction.structure_signals if validated_extraction else DerivedStructureSignals()

    if validated_extraction is not None:
        final_confidence = validated_extraction.confidence
        if validated_extraction.review_status == "usable":
            review_status = "usable"
        elif validated_extraction.review_status == "usable_with_warnings":
            review_status = "usable_with_warnings"
            strict_confirmation_required = True
        elif validated_extraction.review_status == "pending":
            review_status = "pending"
            strict_confirmation_required = True
        else:
            review_status = "needs_correction"
            strict_confirmation_required = True
        notes.extend(validated_extraction.notes)
    else:
        if seed.format_profile and seed.format_profile.is_native_text:
            review_status = "usable"
        elif seed.format_profile and not seed.format_profile.llm_escalation_required:
            review_status = "usable_with_warnings" if seed.quality_signals else "usable"
        else:
            review_status = "pending"
            strict_confirmation_required = True
        notes.extend(seed.quality_signals)
        notes.extend(seed.warnings)

    if escalation.reasons:
        notes.extend(escalation.reasons)
    if llm_payload is not None:
        notes.extend(llm_payload.warnings)
        notes.extend(llm_payload.content_mix_signals)
    if validated_extraction is not None and validated_extraction.requires_confirmation:
        strict_confirmation_required = True

    return DerivedSourceReview(
        source_id=seed.source_id,
        review_status=review_status,
        strict_confirmation_required=strict_confirmation_required,
        final_confidence=final_confidence,
        llm_used=llm_used,
        notes=list(dict.fromkeys(notes)),
        llm_escalation_decision=escalation,
        format_profile=seed.format_profile,
        loss_report=loss_report,
        recovery_report=recovery_report,
        source_format=seed.source_format,
        needs_manual_review=bool(validated_extraction and validated_extraction.requires_confirmation),
    )
