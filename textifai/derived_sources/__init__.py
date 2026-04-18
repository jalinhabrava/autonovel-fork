from __future__ import annotations

from importlib import import_module

from textifai.derived_sources.contracts import (
    DERIVED_EXTRACTION_METHOD_CATALOG,
    DERIVED_REVIEW_STATUS_CATALOG,
    DERIVED_SOURCE_FORMAT_CATALOG,
    DERIVED_STRUCTURE_KIND_CATALOG,
)

__all__ = [
    "DERIVED_EXTRACTION_METHOD_CATALOG",
    "DERIVED_REVIEW_STATUS_CATALOG",
    "DERIVED_SOURCE_FORMAT_CATALOG",
    "DERIVED_STRUCTURE_KIND_CATALOG",
    "DerivedExtractionSeed",
    "DerivedLLMExtractionPayload",
    "DerivedLossSignals",
    "DerivedSegmentCandidate",
    "DerivedSourceLLMConfig",
    "DerivedSourceLLMInterpreter",
    "DerivedSourcePrompt",
    "DerivedSourceReview",
    "DerivedStructureSignals",
    "FormatExtractionProfile",
    "LLMEscalationDecision",
    "LightExtractionBlock",
    "ProviderBackedDerivedSourceInterpreter",
    "ValidatedDerivedExtraction",
    "build_derived_understanding_prompt",
    "decide_llm_escalation",
    "detect_source_format",
    "extract_light_source",
    "normalize_derived_llm_payload",
    "review_derived_source",
    "validate_derived_extraction",
]


def __getattr__(name: str):
    if name in {
        "DerivedExtractionSeed",
        "DerivedLLMExtractionPayload",
        "DerivedLossSignals",
        "DerivedSegmentCandidate",
        "DerivedSourceReview",
        "DerivedStructureSignals",
        "FormatExtractionProfile",
        "LLMEscalationDecision",
        "LightExtractionBlock",
        "ValidatedDerivedExtraction",
    }:
        module = import_module("textifai.derived_sources.contracts")
        return getattr(module, name)
    if name in {
        "detect_source_format",
        "extract_light_source",
    }:
        module = import_module("textifai.derived_sources.extractors")
        return getattr(module, name)
    if name in {
        "decide_llm_escalation",
    }:
        module = import_module("textifai.derived_sources.gating")
        return getattr(module, name)
    if name in {
        "DerivedSourceLLMConfig",
        "DerivedSourceLLMInterpreter",
        "ProviderBackedDerivedSourceInterpreter",
    }:
        module = import_module("textifai.derived_sources.llm_interpreter")
        return getattr(module, name)
    if name in {
        "build_derived_understanding_prompt",
        "DerivedSourcePrompt",
    }:
        module = import_module("textifai.derived_sources.prompt_builder")
        return getattr(module, name)
    if name in {
        "normalize_derived_llm_payload",
        "validate_derived_extraction",
    }:
        module = import_module("textifai.derived_sources.normalization")
        return getattr(module, name)
    if name in {
        "review_derived_source",
    }:
        module = import_module("textifai.derived_sources.reviewer")
        return getattr(module, name)
    raise AttributeError(name)
