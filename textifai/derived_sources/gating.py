from __future__ import annotations

from textifai.derived_sources.contracts import LLMEscalationDecision
from textifai.derived_sources.contracts import DerivedExtractionSeed


def decide_llm_escalation(seed: DerivedExtractionSeed) -> LLMEscalationDecision:
    reasons = list(seed.format_profile.llm_escalation_reasons if seed.format_profile else [])
    if seed.format_profile and seed.format_profile.is_native_text:
        return LLMEscalationDecision(required=False, reasons=[])
    if seed.source_format == "docx" and seed.raw_extracted_text.strip() and not seed.has_mixed_language:
        if seed.format_profile and seed.format_profile.structural_fidelity_confidence >= 0.85 and not reasons:
            return LLMEscalationDecision(required=False, reasons=[])
    if seed.source_format == "pdf" and not seed.raw_extracted_text.strip():
        reasons.append("non_extractable_text")
    if seed.source_format == "doc" and len(seed.raw_extracted_text.strip()) < 80:
        reasons.append("extraction_too_sparse")
    if seed.has_mixed_language:
        reasons.append("mixed_language_detected")
    if len(seed.quality_signals) > 0:
        reasons.extend(seed.quality_signals)
    reasons = _dedupe(reasons)
    return LLMEscalationDecision(required=bool(reasons), reasons=reasons)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
