from textifai.author_understanding.contracts import (
    ANALYSIS_SOURCE_CATALOG,
    AUTHOR_INTENT_TYPE_CATALOG,
    MIXED_PART_TYPE_CATALOG,
    AuthorIntentInterpretation,
    DisambiguationResult,
    LLMInterpretationResult,
    MixedRequestAnalysis,
    MixedRequestPart,
)
from textifai.author_understanding.disambiguation import disambiguate_targets
from textifai.author_understanding.normalization import (
    extract_json_payload,
    normalize_author_intent_type,
    normalize_candidate_target,
    normalize_llm_interpretation_result,
    normalize_mixed_request_part,
)

__all__ = [
    "ANALYSIS_SOURCE_CATALOG",
    "AUTHOR_INTENT_TYPE_CATALOG",
    "MIXED_PART_TYPE_CATALOG",
    "AuthorIntentInterpretation",
    "DisambiguationResult",
    "LLMInterpretationResult",
    "MixedRequestAnalysis",
    "MixedRequestPart",
    "disambiguate_targets",
    "extract_json_payload",
    "normalize_author_intent_type",
    "normalize_candidate_target",
    "normalize_llm_interpretation_result",
    "normalize_mixed_request_part",
]
