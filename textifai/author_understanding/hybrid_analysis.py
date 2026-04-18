from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from providers.text_provider import get_text_provider_config_error
from textifai.author_understanding.contracts import (
    ANALYSIS_SOURCE_CATALOG,
    AUTHOR_INTENT_TYPE_CATALOG,
    AuthorIntentInterpretation,
    DisambiguationResult,
    MixedRequestAnalysis,
    MixedRequestPart,
)
from textifai.author_understanding.disambiguation import disambiguate_targets
from textifai.author_understanding.llm_interpreter import (
    AuthorUnderstandingLLMConfig,
    AuthorUnderstandingLLMInterpreter,
    ProviderBackedAuthorUnderstandingInterpreter,
)
from textifai.author_understanding.normalization import build_rule_based_author_intent
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.state import ConversationState
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityResolutionResult


@dataclass(frozen=True)
class HybridAuthorUnderstandingConfig:
    llm_enabled: bool = True
    llm_task_name: str = "author_understanding"
    llm_provider_name: str | None = None
    llm_model: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1200
    llm_timeout_seconds: int = 120
    llm_retries: int = 1
    llm_trigger_threshold: float = 0.7
    mixed_request_min_tokens: int = 4


class HybridAuthorUnderstandingAnalyzer:
    def __init__(
        self,
        *,
        llm_interpreter: AuthorUnderstandingLLMInterpreter | None = None,
        config: HybridAuthorUnderstandingConfig | None = None,
    ) -> None:
        self.config = config or HybridAuthorUnderstandingConfig()
        self.llm_interpreter = llm_interpreter

    @classmethod
    def from_session(
        cls,
        session=None,
        *,
        llm_interpreter: AuthorUnderstandingLLMInterpreter | None = None,
        config: HybridAuthorUnderstandingConfig | None = None,
    ) -> "HybridAuthorUnderstandingAnalyzer":
        merged_config = config or HybridAuthorUnderstandingConfig(
            llm_provider_name=getattr(session, "provider", None),
        )
        if llm_interpreter is None and merged_config.llm_enabled and getattr(session, "mode", "normal") == "advanced":
            if not get_text_provider_config_error(merged_config.llm_task_name, merged_config.llm_provider_name):
                llm_interpreter = ProviderBackedAuthorUnderstandingInterpreter(
                    config=AuthorUnderstandingLLMConfig(
                        task_name=merged_config.llm_task_name,
                        provider_name=merged_config.llm_provider_name,
                        model=merged_config.llm_model,
                        max_tokens=merged_config.llm_max_tokens,
                        temperature=merged_config.llm_temperature,
                        timeout_seconds=merged_config.llm_timeout_seconds,
                        retries=merged_config.llm_retries,
                    )
                )
        return cls(llm_interpreter=llm_interpreter, config=merged_config)

    def analyze(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        narrative_signals: NarrativeSignals | None,
        entity_results: list[EntityResolutionResult],
        state: ConversationState | None,
    ) -> AuthorIntentInterpretation:
        rule_interpretation = _build_rule_interpretation(
            request=request,
            rule_intent=rule_intent,
            narrative_signals=narrative_signals,
            entity_results=entity_results,
            state=state,
        )
        if not self._should_use_llm(request, rule_intent, rule_interpretation):
            return rule_interpretation

        if self.llm_interpreter is None:
            metadata = dict(rule_interpretation.metadata)
            metadata.update(
                {
                    "gating_reason": "llm_unavailable",
                    "llm_used": False,
                    "analysis_source": "fallback",
                }
            )
            return rule_interpretation.__class__(
                primary_intent_type=rule_interpretation.primary_intent_type,
                secondary_intent_types=list(rule_interpretation.secondary_intent_types),
                confidence=rule_interpretation.confidence,
                has_mixed_request=rule_interpretation.has_mixed_request,
                author_goal_signals=list(rule_interpretation.author_goal_signals),
                preserve_signals=list(rule_interpretation.preserve_signals),
                change_signals=list(rule_interpretation.change_signals),
                followup_reference_text=rule_interpretation.followup_reference_text,
                narrative_content_text=rule_interpretation.narrative_content_text,
                meta_instruction_text=rule_interpretation.meta_instruction_text,
                needs_clarification=rule_interpretation.needs_clarification,
                clarification_reason=rule_interpretation.clarification_reason,
                mixed_request_analysis=rule_interpretation.mixed_request_analysis,
                llm_interpretation=None,
                disambiguation=rule_interpretation.disambiguation,
                source="fallback" if rule_interpretation.needs_clarification else "rule_based",
                metadata=metadata,
            )

        llm_result = self.llm_interpreter.interpret(
            request=request,
            rule_intent=rule_intent,
            narrative_signals=narrative_signals,
            entity_results=entity_results,
            state=state,
        )
        if llm_result is None:
            metadata = dict(rule_interpretation.metadata)
            metadata.update(
                {
                    "gating_reason": "llm_result_unavailable",
                    "llm_used": False,
                    "analysis_source": "fallback",
                }
            )
            return rule_interpretation.__class__(
                primary_intent_type=rule_interpretation.primary_intent_type,
                secondary_intent_types=list(rule_interpretation.secondary_intent_types),
                confidence=rule_interpretation.confidence,
                has_mixed_request=rule_interpretation.has_mixed_request,
                author_goal_signals=list(rule_interpretation.author_goal_signals),
                preserve_signals=list(rule_interpretation.preserve_signals),
                change_signals=list(rule_interpretation.change_signals),
                followup_reference_text=rule_interpretation.followup_reference_text,
                narrative_content_text=rule_interpretation.narrative_content_text,
                meta_instruction_text=rule_interpretation.meta_instruction_text,
                needs_clarification=rule_interpretation.needs_clarification,
                clarification_reason=rule_interpretation.clarification_reason,
                mixed_request_analysis=rule_interpretation.mixed_request_analysis,
                llm_interpretation=None,
                disambiguation=rule_interpretation.disambiguation,
                source="fallback" if rule_interpretation.needs_clarification else "rule_based",
                metadata=metadata,
            )

        disambiguation = disambiguate_targets(_candidate_targets_from_entity_results(entity_results))
        merged = _merge_interpretations(
            rule_interpretation=rule_interpretation,
            llm_interpretation=llm_result,
            disambiguation=disambiguation,
        )
        metadata = dict(merged.metadata)
        metadata.update(
            {
                "gating_reason": "llm_used",
                "llm_used": True,
                "analysis_source": "hybrid",
                "llm_provider_name": llm_result.provider_name,
                "llm_model": llm_result.model,
            }
        )
        return merged.__class__(
            primary_intent_type=merged.primary_intent_type,
            secondary_intent_types=list(merged.secondary_intent_types),
            confidence=merged.confidence,
            has_mixed_request=merged.has_mixed_request,
            author_goal_signals=list(merged.author_goal_signals),
            preserve_signals=list(merged.preserve_signals),
            change_signals=list(merged.change_signals),
            followup_reference_text=merged.followup_reference_text,
            narrative_content_text=merged.narrative_content_text,
            meta_instruction_text=merged.meta_instruction_text,
            needs_clarification=merged.needs_clarification,
            clarification_reason=merged.clarification_reason,
            mixed_request_analysis=merged.mixed_request_analysis,
            llm_interpretation=llm_result,
            disambiguation=disambiguation,
            source="hybrid",
            metadata=metadata,
        )

    def _should_use_llm(
        self,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        interpretation: AuthorIntentInterpretation,
    ) -> bool:
        if not self.config.llm_enabled:
            return False
        if rule_intent.metadata.get("unsupported_capability"):
            return False
        if rule_intent.metadata.get("skip_llm_escalation"):
            if not _looks_like_author_understanding_case(request.raw_text):
                return False
        if interpretation.has_mixed_request:
            return True
        if interpretation.needs_clarification:
            return True
        if _looks_like_author_understanding_case(request.raw_text):
            return True
        if rule_intent.intent_name in {"unknown", "editorial_structuring"} and rule_intent.confidence <= self.config.llm_trigger_threshold:
            return True
        if rule_intent.confidence < self.config.llm_trigger_threshold:
            return True
        if interpretation.followup_reference_text and not interpretation.narrative_content_text:
            return True
        return False


def _build_rule_interpretation(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    narrative_signals: NarrativeSignals | None,
    entity_results: list[EntityResolutionResult],
    state: ConversationState | None,
) -> AuthorIntentInterpretation:
    lowered = request.raw_text.strip().casefold()
    parts = _split_mixed_request_parts(request.raw_text)
    candidate_targets = _candidate_targets_from_entity_results(entity_results)
    disambiguation = disambiguate_targets(candidate_targets)
    primary_intent_type = _infer_primary_intent_type(
        lowered=lowered,
        recognized_intent_name=rule_intent.intent_name,
        narrative_signals=narrative_signals,
        parts=parts,
    )
    has_mixed_request = len({part.part_type for part in parts}) > 1 or primary_intent_type == "mixed_request"
    author_goal_signals, preserve_signals, change_signals = _derive_signals(lowered, narrative_signals, parts)
    narrative_content_text = _extract_narrative_content(request.raw_text, parts)
    meta_instruction_text = _extract_meta_instruction(request.raw_text, parts)
    followup_reference_text = _extract_followup_reference(request.raw_text, parts, state)
    needs_clarification = _needs_clarification(
        primary_intent_type=primary_intent_type,
        narrative_content_text=narrative_content_text,
        followup_reference_text=followup_reference_text,
        disambiguation=disambiguation,
    )
    clarification_reason = _clarification_reason(
        primary_intent_type=primary_intent_type,
        narrative_content_text=narrative_content_text,
        followup_reference_text=followup_reference_text,
        disambiguation=disambiguation,
    )
    metadata = {
        "analysis_source": "rule_based",
        "gating_reason": "rule_first",
        "rule_intent_name": rule_intent.intent_name,
        "rule_intent_confidence": rule_intent.confidence,
        "has_narrative_content": bool(narrative_content_text),
        "has_meta_instruction": bool(meta_instruction_text),
        "has_followup_reference": bool(followup_reference_text),
    }
    mixed_request_analysis = MixedRequestAnalysis(
        source_text=request.raw_text,
        parts=parts,
    )
    return build_rule_based_author_intent(
        primary_intent_type=primary_intent_type,
        confidence=_rule_confidence(rule_intent, has_mixed_request=has_mixed_request, narrative_content_text=narrative_content_text),
        has_mixed_request=has_mixed_request,
        author_goal_signals=author_goal_signals,
        preserve_signals=preserve_signals,
        change_signals=change_signals,
        followup_reference_text=followup_reference_text,
        narrative_content_text=narrative_content_text,
        meta_instruction_text=meta_instruction_text,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        mixed_request_analysis=mixed_request_analysis,
        disambiguation=disambiguation,
        source="rule_based",
        metadata=metadata,
    )


def _merge_interpretations(
    *,
    rule_interpretation: AuthorIntentInterpretation,
    llm_interpretation,
    disambiguation: DisambiguationResult,
) -> AuthorIntentInterpretation:
    primary = llm_interpretation.primary_intent_type
    if primary == "unknown":
        primary = rule_interpretation.primary_intent_type
    secondary = _dedupe(
        list(rule_interpretation.secondary_intent_types)
        + list(llm_interpretation.secondary_intent_types)
    )
    if primary in secondary:
        secondary = [item for item in secondary if item != primary]
    if llm_interpretation.has_mixed_request or rule_interpretation.has_mixed_request:
        has_mixed_request = True
    else:
        has_mixed_request = len(secondary) > 0
    narrative_content_text = (
        llm_interpretation.narrative_content_text
        or _join_part_texts(llm_interpretation.parts, {"narrative_content"})
        or rule_interpretation.narrative_content_text
    )
    meta_instruction_text = (
        llm_interpretation.meta_instruction_text
        or _join_part_texts(llm_interpretation.parts, {"meta_instruction", "narration_prep", "review_handoff", "validation_request"})
        or rule_interpretation.meta_instruction_text
    )
    followup_reference_text = llm_interpretation.followup_reference_text or rule_interpretation.followup_reference_text
    author_goal_signals = _dedupe(
        list(rule_interpretation.author_goal_signals)
        + list(llm_interpretation.author_goal_signals)
        + list(llm_interpretation.change_signals)
    )
    preserve_signals = _dedupe(
        list(rule_interpretation.preserve_signals)
        + list(llm_interpretation.preserve_signals)
    )
    change_signals = _dedupe(
        list(rule_interpretation.change_signals)
        + list(llm_interpretation.change_signals)
        + list(llm_interpretation.author_goal_signals)
    )
    confidence = max(rule_interpretation.confidence, llm_interpretation.confidence)
    needs_clarification = llm_interpretation.needs_clarification or (
        rule_interpretation.needs_clarification
        and primary not in {"editorial_revision"}
        and narrative_content_text is None
        and followup_reference_text is None
    )
    if disambiguation.requires_user_confirmation and not disambiguation.preferred_target and primary not in {"mixed_request", "editorial_revision"}:
        needs_clarification = True
    clarification_reason = llm_interpretation.clarification_reason or rule_interpretation.clarification_reason
    if needs_clarification and not clarification_reason:
        clarification_reason = disambiguation.reason
    return rule_interpretation.__class__(
        primary_intent_type=primary,
        secondary_intent_types=secondary,
        confidence=confidence,
        has_mixed_request=has_mixed_request,
        author_goal_signals=author_goal_signals,
        preserve_signals=preserve_signals,
        change_signals=change_signals,
        followup_reference_text=followup_reference_text,
        narrative_content_text=narrative_content_text,
        meta_instruction_text=meta_instruction_text,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        mixed_request_analysis=_merge_mixed_request_analysis(rule_interpretation.mixed_request_analysis, llm_interpretation.parts),
        llm_interpretation=llm_interpretation,
        disambiguation=disambiguation,
        source="hybrid",
        metadata={
            **dict(rule_interpretation.metadata),
            "analysis_source": "hybrid",
            "llm_used": True,
            "llm_primary_intent_type": llm_interpretation.primary_intent_type,
            "llm_confidence": llm_interpretation.confidence,
            "llm_needs_clarification": llm_interpretation.needs_clarification,
            "disambiguation_requires_confirmation": disambiguation.requires_user_confirmation,
        },
    )


def _merge_mixed_request_analysis(
    existing: MixedRequestAnalysis | None,
    llm_parts: list[MixedRequestPart],
) -> MixedRequestAnalysis | None:
    if existing is None and not llm_parts:
        return None
    parts = list(existing.parts if existing is not None else [])
    for part in llm_parts:
        if part not in parts:
            parts.append(part)
    source_text = existing.source_text if existing is not None else ""
    return MixedRequestAnalysis(source_text=source_text, parts=parts)


def _join_part_texts(parts: list[MixedRequestPart], part_types: set[str]) -> str | None:
    texts = [part.text for part in parts if part.part_type in part_types and part.text.strip()]
    if not texts:
        return None
    content = " ".join(texts).strip()
    return content or None


def _candidate_targets_from_entity_results(entity_results: list[EntityResolutionResult]) -> list[CandidateTarget]:
    targets: list[CandidateTarget] = []
    for item in entity_results:
        if item.resolved and item.resolved_entity_id and item.resolved_entity_type:
            targets.append(
                CandidateTarget(
                    target_id=item.resolved_entity_id,
                    target_type=item.resolved_entity_type,
                    confidence=item.resolution_confidence,
                )
            )
            continue
        if item.candidate_entities:
            top = item.candidate_entities[0]
            targets.append(
                CandidateTarget(
                    target_id=top.artifact_id,
                    target_type=top.artifact_type,
                    confidence=top.confidence,
                )
            )
    deduped: dict[tuple[str, str], CandidateTarget] = {}
    for target in targets:
        key = (target.target_type, target.target_id)
        if key not in deduped or target.confidence > deduped[key].confidence:
            deduped[key] = target
    return sorted(deduped.values(), key=lambda item: (item.confidence, item.target_type, item.target_id), reverse=True)


def _infer_primary_intent_type(
    *,
    lowered: str,
    recognized_intent_name: str,
    narrative_signals: NarrativeSignals | None,
    parts: list[MixedRequestPart],
) -> str:
    if recognized_intent_name in {"validate_structure"}:
        return "validation_request"
    if recognized_intent_name in {"prepare_narration"}:
        return "narration_preparation"
    if recognized_intent_name in {"prepare_review"}:
        return "review_handoff"
    if recognized_intent_name in {"structured_followup"}:
        return "structured_followup"
    if _looks_like_followup_request(lowered):
        if _looks_like_narration_prep(lowered):
            return "narration_preparation"
        if _looks_like_structured_followup(lowered, parts, narrative_signals):
            return "structured_followup"
        return "contextual_followup"
    if _looks_like_review_request(lowered):
        return "review_handoff"
    if _looks_like_validation_request(lowered):
        return "validation_request"
    if _looks_like_narration_prep(lowered):
        return "narration_preparation"
    if _looks_like_structuring_request(lowered):
        if _looks_like_revision_request(lowered, narrative_signals) or _has_mixed_parts(parts):
            return "mixed_request"
        return "structuring_request"
    if _looks_like_revision_request(lowered, narrative_signals):
        if _has_mixed_parts(parts):
            return "mixed_request"
        return "editorial_revision"
    if _looks_like_narrative_facts(lowered):
        return "narrative_facts"
    if _has_mixed_parts(parts):
        return "mixed_request"
    return "unknown"


def _derive_signals(
    lowered: str,
    narrative_signals: NarrativeSignals | None,
    parts: list[MixedRequestPart],
) -> tuple[list[str], list[str], list[str]]:
    author_goal_signals: list[str] = []
    preserve_signals: list[str] = []
    change_signals: list[str] = []
    issue_types = list((narrative_signals.issue_types if narrative_signals else []) or [])
    if "canon_issue" in issue_types or "canon" in lowered:
        author_goal_signals.append("anchor_canon")
        preserve_signals.append("preserve_validated_canon")
    if "character_voice_mismatch" in issue_types or "voz" in lowered or "voice" in lowered:
        preserve_signals.append("preserve_character_voice")
    if "tone_issue" in issue_types or "más contenida" in lowered or "mas contenida" in lowered:
        author_goal_signals.append("align_tone")
        change_signals.append("align_tone")
    if "motivation_issue" in issue_types or "no entiendo por qué" in lowered or "no entiendo por que" in lowered:
        author_goal_signals.append("clarify_motivation")
        change_signals.append("clarify_motivation")
    if any(phrase in lowered for phrase in ("dure más", "dure mas", "cede tan rápido", "cede tan rapido", "last longer", "sostener el conflicto")):
        author_goal_signals.append("extend_conflict")
        change_signals.append("extend_conflict")
        preserve_signals.append("preserve_scene_conflict")
    if _looks_like_structuring_request(lowered):
        author_goal_signals.append("structure_scene")
        change_signals.append("structure_scene")
    if _looks_like_narration_prep(lowered):
        author_goal_signals.append("prepare_for_narration")
        change_signals.append("prepare_for_narration")
    if _looks_like_review_request(lowered):
        author_goal_signals.append("prepare_for_review")
        change_signals.append("prepare_for_review")
    if _has_mixed_parts(parts):
        author_goal_signals.append("mixed_request")
        change_signals.append("mixed_request")
    if "sin que" in lowered or "sin perder" in lowered or "sin romper" in lowered:
        preserve_signals.append("preserve_scene_conflict")
    if "sin que" in lowered and any(term in lowered for term in ("cruel", "cruelty")):
        preserve_signals.append("preserve_character_empathy")
    return (_dedupe(author_goal_signals), _dedupe(preserve_signals), _dedupe(change_signals))


def _extract_narrative_content(text: str, parts: list[MixedRequestPart]) -> str | None:
    narrative_parts = [part.text for part in parts if part.part_type == "narrative_content"]
    if narrative_parts:
        content = " ".join(narrative_parts).strip()
        if content:
            return content
    stripped = text.strip()
    if _looks_like_narrative_facts(stripped.casefold()) and not _looks_like_pure_meta_instruction(stripped.casefold()):
        return stripped
    return None


def _extract_meta_instruction(text: str, parts: list[MixedRequestPart]) -> str | None:
    meta_parts = [part.text for part in parts if part.part_type in {"meta_instruction", "narration_prep", "review_handoff", "validation_request"}]
    if meta_parts:
        content = " ".join(meta_parts).strip()
        if content:
            return content
    stripped = text.strip()
    if _looks_like_pure_meta_instruction(stripped.casefold()):
        return stripped
    return None


def _extract_followup_reference(text: str, parts: list[MixedRequestPart], state: ConversationState | None) -> str | None:
    followup_parts = [part.text for part in parts if part.part_type == "followup_reference"]
    if followup_parts:
        content = " ".join(followup_parts).strip()
        if content:
            return content
    lowered = text.casefold().strip()
    if lowered.startswith("de lo anterior"):
        return text.strip()
    if lowered.startswith("lo del ") or "lo anterior" in lowered:
        return text.strip()
    if lowered in {"esta nota", "esta escena", "este capítulo", "este capitulo", "sí, esa", "si, esa", "usa la anterior"}:
        return text.strip()
    if state is not None and state.last_target_id and lowered.startswith("lo del "):
        return text.strip()
    return None


def _needs_clarification(
    *,
    primary_intent_type: str,
    narrative_content_text: str | None,
    followup_reference_text: str | None,
    disambiguation: DisambiguationResult,
) -> bool:
    if primary_intent_type == "unknown":
        return True
    if primary_intent_type in {"structuring_request", "mixed_request", "narration_preparation", "review_handoff"} and narrative_content_text is None:
        return True
    if primary_intent_type in {"contextual_followup", "structured_followup"} and followup_reference_text is None and not disambiguation.preferred_target:
        return True
    return bool(disambiguation.requires_user_confirmation and not disambiguation.preferred_target)


def _clarification_reason(
    *,
    primary_intent_type: str,
    narrative_content_text: str | None,
    followup_reference_text: str | None,
    disambiguation: DisambiguationResult,
) -> str | None:
    if primary_intent_type == "unknown":
        return "The request is too ambiguous to classify safely."
    if primary_intent_type in {"structuring_request", "mixed_request", "narration_preparation", "review_handoff"} and narrative_content_text is None:
        return "The request needs concrete narrative content before it can be structured or handed off."
    if primary_intent_type in {"contextual_followup", "structured_followup"} and followup_reference_text is None and not disambiguation.preferred_target:
        return "The follow-up reference is still too implicit to anchor safely."
    if disambiguation.requires_user_confirmation and not disambiguation.preferred_target:
        return disambiguation.reason
    return None


def _rule_confidence(
    rule_intent: RecognizedIntent,
    *,
    has_mixed_request: bool,
    narrative_content_text: str | None,
) -> float:
    confidence = max(rule_intent.confidence, 0.45)
    if has_mixed_request:
        confidence = min(confidence, 0.84)
    if narrative_content_text is None and rule_intent.intent_name in {"unknown", "editorial_structuring"}:
        confidence = min(confidence, 0.78)
    return confidence


def _looks_like_author_understanding_case(raw_text: str) -> bool:
    lowered = raw_text.casefold().strip()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "pero sin",
            "sin perder",
            "sin romper",
            "quédate con",
            "quedate con",
            "de lo anterior",
            "de la anterior",
            "prepáralo para narrar",
            "preparalo para narrar",
            "déjalo listo para revisión",
            "dejalo listo para revision",
            "más contenida",
            "mas contenida",
            "lista para revisar",
            "listo para revisar",
            "luego",
            "y luego",
        )
    )


def _looks_like_followup_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "de lo anterior",
            "lo anterior",
            "esta nota",
            "esta escena",
            "este capítulo",
            "este capitulo",
            "sí, esa",
            "si, esa",
            "usa la anterior",
            "lo del ",
            "de la anterior",
            "de lo de antes",
        )
    )


def _looks_like_structured_followup(
    lowered: str,
    parts: list[MixedRequestPart],
    narrative_signals: NarrativeSignals | None,
) -> bool:
    if any(
        phrase in lowered
        for phrase in (
            "quédate con",
            "quedate con",
            "usa la anterior",
            "sí, esa",
            "si, esa",
            "de lo anterior",
            "de la anterior",
        )
    ):
        return True
    if _has_mixed_parts(parts) and (narrative_signals is not None and bool(narrative_signals.issue_types)):
        return True
    return False


def _split_mixed_request_parts(text: str) -> list[MixedRequestPart]:
    lowered = text.casefold()
    clauses = [clause.strip() for clause in re.split(r"(?:;|,|\band then\b|\by luego\b|\bluego\b|\bpero\b)", lowered) if clause.strip()]
    parts: list[MixedRequestPart] = []
    for clause in clauses:
        part_type = _classify_part_type(clause)
        if part_type == "mixed":
            continue
        original = _extract_original_clause(text, clause)
        parts.append(MixedRequestPart(part_type=part_type, text=original, confidence=_part_confidence(part_type, clause)))
    if not parts and text.strip():
        parts.append(MixedRequestPart(part_type=_classify_part_type(lowered), text=text.strip(), confidence=0.55))
    return parts


def _classify_part_type(clause: str) -> str:
    if _looks_like_validation_request(clause):
        return "validation_request"
    if _looks_like_review_request(clause):
        return "review_handoff"
    if _looks_like_narration_prep(clause):
        return "narration_prep"
    if _looks_like_followup_reference(clause):
        return "followup_reference"
    if _looks_like_pure_meta_instruction(clause):
        return "meta_instruction"
    if _looks_like_revision_request(clause, None):
        if any(phrase in clause for phrase in ("sin perder", "sin romper", "sin que")):
            return "preserve"
        return "revision"
    if _looks_like_structuring_request(clause):
        return "narrative_content" if _looks_like_narrative_facts(clause) else "meta_instruction"
    if _looks_like_narrative_facts(clause):
        return "narrative_content"
    return "mixed"


def _looks_like_narrative_facts(lowered: str) -> bool:
    return any(
        token in lowered
        for token in (
            "llega",
            "encuentra",
            "acusa",
            "revela",
            "rompe",
            "falla",
            "improvisa",
            "oculta",
            "enfría",
            "enfria",
            "termina",
            "terminan",
            "confiesa",
            "decide",
            "pasa a",
        )
    )


def _looks_like_structuring_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "ordena",
            "reordena",
            "estructura clara",
            "convertir",
            "estructura",
            "beat by beat",
            "outline",
        )
    )


def _looks_like_revision_request(lowered: str, narrative_signals: NarrativeSignals | None) -> bool:
    return bool(
        any(
            phrase in lowered
            for phrase in (
                "quiero que",
                "no me gusta",
                "sin que",
                "demasiado",
                "más contenida",
                "mas contenida",
                "no cede",
                "cede tan rápido",
                "cede tan rapido",
                "version",
                "versión",
            )
        )
        or (narrative_signals is not None and bool(narrative_signals.issue_types))
    )


def _looks_like_narration_prep(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "prepáralo para narrar",
            "preparalo para narrar",
            "déjalo listo para narrar",
            "dejalo listo para narrar",
            "lista para narrar",
            "listo para narrar",
            "preparada para narrar",
            "preparado para narrar",
        )
    )


def _looks_like_review_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "déjalo listo para revisión",
            "dejalo listo para revision",
            "prepáralo para revisión",
            "preparalo para revision",
            "listo para revisión",
            "lista para revisión",
            "listo para revision",
            "lista para revision",
        )
    )


def _looks_like_validation_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "valida esta estructura",
            "valido esta estructura",
            "validate this structure",
        )
    )


def _looks_like_followup_reference(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "de lo anterior",
            "lo anterior",
            "esta nota",
            "esta escena",
            "este capítulo",
            "este capitulo",
            "sí, esa",
            "si, esa",
            "usa la anterior",
            "lo del ",
        )
    )


def _looks_like_pure_meta_instruction(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "ordena esta escena",
            "ordénala",
            "ordénalo",
            "ordena esto",
            "prepáralo para narrar",
            "preparalo para narrar",
            "prepáralo para revisión",
            "preparalo para revision",
            "déjame",
            "dejame",
            "déjalo",
            "dejalo",
        )
    )


def _has_mixed_parts(parts: list[MixedRequestPart]) -> bool:
    return len({part.part_type for part in parts}) > 1


def _part_confidence(part_type: str, clause: str) -> float:
    confidence = 0.6
    if part_type in {"narrative_content", "revision"}:
        confidence += 0.15
    if part_type in {"followup_reference", "validation_request", "review_handoff", "narration_prep"}:
        confidence += 0.2
    if "sin perder" in clause or "sin romper" in clause:
        confidence += 0.05
    return min(confidence, 0.95)


def _extract_original_clause(original_text: str, lowered_clause: str) -> str:
    original_lowered = original_text.casefold()
    index = original_lowered.find(lowered_clause)
    if index == -1:
        return lowered_clause.strip()
    return original_text[index : index + len(lowered_clause)].strip()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
