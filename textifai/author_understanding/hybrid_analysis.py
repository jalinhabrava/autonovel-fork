from __future__ import annotations

from dataclasses import asdict, dataclass
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
from textifai.author_understanding.gating import AuthorUnderstandingRoute, classify_author_understanding_route
from textifai.author_understanding.llm_interpreter import (
    AuthorUnderstandingLLMConfig,
    AuthorUnderstandingLLMInterpreter,
    ProviderBackedAuthorUnderstandingInterpreter,
)
from textifai.author_understanding.normalization import build_rule_based_author_intent
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.state import ConversationState
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityHint, EntityResolutionResult


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
            llm_model=getattr(session, "writer_model", None),
        )
        if llm_interpreter is None and merged_config.llm_enabled:
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
        route = classify_author_understanding_route(
            request=request,
            rule_intent=rule_intent,
            state=state,
            narrative_signals=narrative_signals,
        )
        if route.route_type == "expert_bypass":
            return _annotate_interpretation(route=route, interpretation=rule_interpretation, source="rule_based")
        if route.route_type == "trivial_contextual_case":
            return _build_trivial_contextual_interpretation(
                request=request,
                rule_interpretation=rule_interpretation,
                route=route,
                entity_results=entity_results,
                state=state,
            )
        if not route.should_use_llm:
            return _annotate_interpretation(route=route, interpretation=rule_interpretation, source="rule_based")

        if self.llm_interpreter is None:
            return _annotate_interpretation(route=route, interpretation=rule_interpretation, source="rule_based")

        try:
            llm_result = self.llm_interpreter.interpret(
                request=request,
                rule_intent=rule_intent,
                narrative_signals=narrative_signals,
                entity_results=entity_results,
                state=state,
            )
        except Exception as exc:
            fallback = _annotate_interpretation(route=route, interpretation=rule_interpretation, source="fallback")
            metadata = dict(fallback.metadata)
            metadata.update(
                {
                    "llm_used": False,
                    "llm_error": str(exc),
                    "analysis_source": "fallback",
                }
            )
            return fallback.__class__(
                primary_intent_type=fallback.primary_intent_type,
                secondary_intent_types=list(fallback.secondary_intent_types),
                confidence=fallback.confidence,
                has_mixed_request=fallback.has_mixed_request,
                author_goal_signals=list(fallback.author_goal_signals),
                preserve_signals=list(fallback.preserve_signals),
                change_signals=list(fallback.change_signals),
                entity_hints=list(fallback.entity_hints),
                followup_reference_text=fallback.followup_reference_text,
                narrative_content_text=fallback.narrative_content_text,
                meta_instruction_text=fallback.meta_instruction_text,
                editorial_diagnosis=dict(fallback.editorial_diagnosis),
                needs_clarification=fallback.needs_clarification,
                clarification_reason=fallback.clarification_reason,
                mixed_request_analysis=fallback.mixed_request_analysis,
                llm_interpretation=fallback.llm_interpretation,
                disambiguation=fallback.disambiguation,
                source="fallback",
                metadata=metadata,
            )
        if llm_result is None:
            return _annotate_interpretation(route=route, interpretation=rule_interpretation, source="rule_based")

        merged_candidate_targets = _candidate_targets_from_entity_results(entity_results) + list(llm_result.candidate_targets)
        disambiguation = disambiguate_targets(merged_candidate_targets)
        merged = _merge_interpretations(
            rule_interpretation=rule_interpretation,
            llm_interpretation=llm_result,
            disambiguation=disambiguation,
            route=route,
        )
        metadata = dict(merged.metadata)
        metadata.update(
            {
                "gating_reason": route.reason,
                "llm_used": True,
                "analysis_source": "hybrid",
                "llm_provider_name": llm_result.provider_name,
                "llm_model": llm_result.model,
                "author_understanding_route": route.route_type,
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
            entity_hints=list(merged.entity_hints),
            followup_reference_text=merged.followup_reference_text,
            narrative_content_text=merged.narrative_content_text,
            meta_instruction_text=merged.meta_instruction_text,
            editorial_diagnosis=dict(merged.editorial_diagnosis),
            needs_clarification=merged.needs_clarification,
            clarification_reason=merged.clarification_reason,
            mixed_request_analysis=merged.mixed_request_analysis,
            llm_interpretation=llm_result,
            disambiguation=disambiguation,
            source="hybrid",
            metadata=metadata,
        )


def _build_rule_interpretation(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    narrative_signals: NarrativeSignals | None,
    entity_results: list[EntityResolutionResult],
    state: ConversationState | None,
) -> AuthorIntentInterpretation:
    raw_text = request.raw_text.strip()
    candidate_targets = _candidate_targets_from_entity_results(entity_results)
    entity_hints = _entity_hints_from_entity_results(entity_results)
    disambiguation = disambiguate_targets(candidate_targets)
    primary_intent_type = _minimal_primary_intent_type(
        rule_intent_name=rule_intent.intent_name,
        state=state,
        request=request,
        disambiguation=disambiguation,
    )
    parts = _minimal_parts(raw_text=raw_text, primary_intent_type=primary_intent_type)
    followup_reference_text = raw_text if primary_intent_type == "contextual_followup" else None
    narrative_content_text = raw_text if primary_intent_type == "narrative_facts" else None
    meta_instruction_text = raw_text if primary_intent_type in {
        "narration_preparation",
        "review_handoff",
        "validation_request",
        "structured_followup",
    } else None
    author_goal_signals, preserve_signals, change_signals = _minimal_author_signals(primary_intent_type)
    editorial_diagnosis = {
        "analysis_mode": "deterministic_minimal",
        "supports_anchor_only_guidance": bool(disambiguation.preferred_target),
        "issue_types": list((narrative_signals.issue_types if narrative_signals else []) or []),
    }
    needs_clarification = primary_intent_type == "unknown"
    clarification_reason = "A provider-backed interpretation is required for freeform author requests." if needs_clarification else None
    explicit_grounded_target = bool(rule_intent.target_id or rule_intent.target_type or request.target_hint)
    if primary_intent_type == "validation_request" and not (disambiguation.preferred_target or explicit_grounded_target):
        needs_clarification = True
        clarification_reason = "Validation needs an explicit target or a resolved grounded target."
    metadata = {
        "analysis_source": "rule_based",
        "gating_reason": "deterministic_minimal",
        "rule_intent_name": rule_intent.intent_name,
        "rule_intent_confidence": rule_intent.confidence,
        "has_narrative_content": bool(narrative_content_text),
        "has_meta_instruction": bool(meta_instruction_text),
        "has_followup_reference": bool(followup_reference_text),
    }
    mixed_request_analysis = MixedRequestAnalysis(
        source_text=raw_text,
        parts=parts,
    )
    return build_rule_based_author_intent(
        primary_intent_type=primary_intent_type,
        confidence=max(rule_intent.confidence, 0.2),
        has_mixed_request=False,
        author_goal_signals=author_goal_signals,
        preserve_signals=preserve_signals,
        change_signals=change_signals,
        entity_hints=entity_hints,
        followup_reference_text=followup_reference_text,
        narrative_content_text=narrative_content_text,
        meta_instruction_text=meta_instruction_text,
        editorial_diagnosis=editorial_diagnosis,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        mixed_request_analysis=mixed_request_analysis,
        disambiguation=disambiguation,
        source="rule_based",
        metadata=metadata,
    )


def _minimal_primary_intent_type(
    *,
    rule_intent_name: str,
    state: ConversationState | None,
    request: ConversationRequest,
    disambiguation: DisambiguationResult,
) -> str:
    mapping = {
        "lookup_world": "narrative_facts",
        "search_context": "narrative_facts",
        "inspect_scene": "narrative_facts",
        "inspect_chapter": "narrative_facts",
        "prepare_narration": "narration_preparation",
        "prepare_review": "review_handoff",
        "validate_artifact": "validation_request",
        "consistency_check": "validation_request",
        "structured_followup": "structured_followup",
        "validate_structure": "validation_request",
    }
    if rule_intent_name in mapping:
        return mapping[rule_intent_name]
    if state is not None and state.last_target_id and request.target_hint:
        return "contextual_followup"
    if disambiguation.preferred_target is not None and rule_intent_name == "unknown":
        return "contextual_followup"
    return "unknown"


def _minimal_parts(*, raw_text: str, primary_intent_type: str) -> list[MixedRequestPart]:
    if not raw_text:
        return []
    part_type = {
        "contextual_followup": "followup_reference",
        "narrative_facts": "narrative_content",
        "narration_preparation": "narration_prep",
        "review_handoff": "review_handoff",
        "validation_request": "validation_request",
        "structured_followup": "followup_reference",
    }.get(primary_intent_type, "mixed")
    return [MixedRequestPart(part_type=part_type, text=raw_text, confidence=0.6)]


def _minimal_author_signals(primary_intent_type: str) -> tuple[list[str], list[str], list[str]]:
    mapping = {
        "narrative_facts": (["extract_story_facts"], [], ["extract_story_facts"]),
        "narration_preparation": (["prepare_for_narration"], [], ["prepare_for_narration"]),
        "review_handoff": (["prepare_for_review"], [], ["prepare_for_review"]),
        "validation_request": (["anchor_canon"], ["preserve_validated_canon"], []),
        "structured_followup": ([], [], []),
        "contextual_followup": ([], [], []),
    }
    return mapping.get(primary_intent_type, ([], [], []))


def _build_trivial_contextual_interpretation(
    *,
    request: ConversationRequest,
    rule_interpretation: AuthorIntentInterpretation,
    route: AuthorUnderstandingRoute,
    entity_results: list[EntityResolutionResult],
    state: ConversationState | None,
) -> AuthorIntentInterpretation:
    candidate_targets = _candidate_targets_from_entity_results(entity_results)
    recent_target = None
    if state is not None and state.last_target_id and state.last_target_type:
        recent_target = CandidateTarget(
            target_id=state.last_target_id,
            target_type=state.last_target_type,
            confidence=0.58,
        )
    if candidate_targets:
        disambiguation = disambiguate_targets(candidate_targets)
    elif recent_target is not None:
        disambiguation = DisambiguationResult(
            candidate_targets=[recent_target],
            preferred_target=recent_target,
            confidence=recent_target.confidence,
            reason="Recent conversation state provides a safe contextual anchor.",
            requires_user_confirmation=False,
        )
    else:
        disambiguation = rule_interpretation.disambiguation
    metadata = dict(rule_interpretation.metadata)
    metadata.update(
        {
            "analysis_source": "rule_based",
            "gating_reason": route.reason,
            "llm_used": False,
            "author_understanding_route": route.route_type,
            "recent_context_reused": recent_target is not None,
        }
    )
    followup_reference_text = request.raw_text.strip()
    needs_clarification = False
    clarification_reason = None
    if (state is None or state.last_target_id is None) and not candidate_targets:
        needs_clarification = True
        clarification_reason = "The follow-up is short but still lacks a recent anchor."
    if candidate_targets and disambiguation.requires_user_confirmation and not disambiguation.preferred_target:
        needs_clarification = True
        clarification_reason = disambiguation.reason
    return rule_interpretation.__class__(
        primary_intent_type="contextual_followup",
        secondary_intent_types=list(rule_interpretation.secondary_intent_types),
        confidence=max(rule_interpretation.confidence, 0.55),
        has_mixed_request=False,
        author_goal_signals=list(rule_interpretation.author_goal_signals),
        preserve_signals=list(rule_interpretation.preserve_signals),
        change_signals=list(rule_interpretation.change_signals),
        entity_hints=list(rule_interpretation.entity_hints),
        followup_reference_text=followup_reference_text,
        narrative_content_text=None,
        meta_instruction_text=None,
        editorial_diagnosis=dict(rule_interpretation.editorial_diagnosis),
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        mixed_request_analysis=rule_interpretation.mixed_request_analysis,
        llm_interpretation=None,
        disambiguation=disambiguation,
        source="rule_based",
        metadata=metadata,
    )


def _annotate_interpretation(
    *,
    route: AuthorUnderstandingRoute,
    interpretation: AuthorIntentInterpretation,
    source: str,
) -> AuthorIntentInterpretation:
    metadata = dict(interpretation.metadata)
    metadata.update(
        {
            "analysis_source": source,
            "gating_reason": route.reason,
            "llm_used": False,
            "author_understanding_route": route.route_type,
        }
    )
    return interpretation.__class__(
        primary_intent_type=interpretation.primary_intent_type,
        secondary_intent_types=list(interpretation.secondary_intent_types),
        confidence=interpretation.confidence,
        has_mixed_request=interpretation.has_mixed_request,
        author_goal_signals=list(interpretation.author_goal_signals),
        preserve_signals=list(interpretation.preserve_signals),
        change_signals=list(interpretation.change_signals),
        followup_reference_text=interpretation.followup_reference_text,
        narrative_content_text=interpretation.narrative_content_text,
        meta_instruction_text=interpretation.meta_instruction_text,
        editorial_diagnosis=dict(interpretation.editorial_diagnosis),
        needs_clarification=interpretation.needs_clarification,
        clarification_reason=interpretation.clarification_reason,
        mixed_request_analysis=interpretation.mixed_request_analysis,
        llm_interpretation=interpretation.llm_interpretation,
        disambiguation=interpretation.disambiguation,
        source=source if source in ANALYSIS_SOURCE_CATALOG else "rule_based",
        metadata=metadata,
    )


def _merge_interpretations(
    *,
    rule_interpretation: AuthorIntentInterpretation,
    llm_interpretation,
    disambiguation: DisambiguationResult,
    route: AuthorUnderstandingRoute,
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
    editorial_diagnosis = _merge_editorial_diagnosis(
        dict(rule_interpretation.editorial_diagnosis),
        dict(getattr(llm_interpretation, "editorial_diagnosis", {}) or {}),
    )
    author_goal_signals = _dedupe(
        list(rule_interpretation.author_goal_signals)
        + list(llm_interpretation.author_goal_signals)
        + list(llm_interpretation.change_signals)
    )
    entity_hints = _dedupe_entity_hints(
        list(rule_interpretation.entity_hints)
        + list(llm_interpretation.entity_hints)
        + _entity_hints_from_candidate_targets(list(disambiguation.candidate_targets))
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
        llm_interpretation.primary_intent_type == "unknown"
        and rule_interpretation.needs_clarification
        and primary not in {"editorial_revision"}
        and narrative_content_text is None
        and followup_reference_text is None
    )
    if disambiguation.requires_user_confirmation and not disambiguation.preferred_target and primary in {"contextual_followup", "structured_followup", "mixed_request", "editorial_revision", "structuring_request", "narrative_facts"}:
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
        entity_hints=entity_hints,
        followup_reference_text=followup_reference_text,
        narrative_content_text=narrative_content_text,
        meta_instruction_text=meta_instruction_text,
        editorial_diagnosis=editorial_diagnosis,
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
            "author_understanding_route": route.route_type,
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


def _entity_hints_from_entity_results(entity_results: list[EntityResolutionResult]) -> list[EntityHint]:
    hints: list[EntityHint] = []
    for item in entity_results:
        if item.resolved and item.resolved_entity_id and item.resolved_entity_type:
            hints.append(
                EntityHint(
                    hint_text=item.mention.surface_text,
                    normalized_hint=item.mention.normalized_text,
                    hint_kind="semantic_target",
                    hint_source="author_understanding",
                    confidence=_bounded_confidence(max(item.resolution_confidence, 0.4)),
                    supported_by_author_understanding=True,
                    supported_by_document_analysis=False,
                    candidate_target_id=item.resolved_entity_id,
                    candidate_target_type=item.resolved_entity_type,
                )
            )
            continue
        if item.candidate_entities:
            top = item.candidate_entities[0]
            hints.append(
                EntityHint(
                    hint_text=item.mention.surface_text,
                    normalized_hint=item.mention.normalized_text,
                    hint_kind="semantic_target",
                    hint_source="author_understanding",
                    confidence=_bounded_confidence(max(top.confidence, 0.35)),
                    supported_by_author_understanding=True,
                    supported_by_document_analysis=False,
                    candidate_target_id=top.artifact_id,
                    candidate_target_type=top.artifact_type,
                )
            )
    return _dedupe_entity_hints(hints)


def _entity_hints_from_candidate_targets(candidate_targets: list[CandidateTarget]) -> list[EntityHint]:
    return [
        EntityHint(
            hint_text=f"{candidate.target_type}:{candidate.target_id}",
            normalized_hint=candidate.target_id,
            hint_kind="semantic_target",
            hint_source="author_understanding",
            confidence=_bounded_confidence(candidate.confidence),
            supported_by_author_understanding=True,
            candidate_target_id=candidate.target_id,
            candidate_target_type=candidate.target_type,
        )
        for candidate in candidate_targets
    ]


def _dedupe_entity_hints(hints: list[EntityHint]) -> list[EntityHint]:
    seen: dict[tuple[str, str | None, str | None], EntityHint] = {}
    for hint in hints:
        key = (hint.normalized_hint, hint.candidate_target_id, hint.candidate_target_type)
        if key not in seen or hint.confidence > seen[key].confidence:
            seen[key] = hint
    return sorted(seen.values(), key=lambda item: (item.confidence, item.hint_kind, item.normalized_hint), reverse=True)


def _bounded_confidence(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _infer_primary_intent_type(
    *,
    raw_text: str,
    recognized_intent_name: str,
    narrative_signals: NarrativeSignals | None,
    token_count: int,
    candidate_targets: list[CandidateTarget],
    request: ConversationRequest,
    parts: list[MixedRequestPart],
    state: ConversationState | None,
) -> str:
    lowered = raw_text.casefold()
    if any(
        phrase in lowered
        for phrase in (
            "revísame la voz",
            "revisame la voz",
            "voz interna",
            "grado de explicitud",
            "dinámica verbal",
            "dinamica verbal",
            "cuidar en silencio",
            "ironía suave",
            "ironia suave",
        )
    ):
        return "editorial_revision"
    if any(
        phrase in lowered
        for phrase in (
            "ayúdame a estructurar",
            "ayudame a estructurar",
            "qué beat final",
            "que beat final",
            "bonus cómico",
            "bonus comico",
            "4koma",
            "remate divertido",
        )
    ):
        return "structuring_request"
    if any(
        phrase in lowered
        for phrase in (
            "encaja con el canon",
            "qué pieza habría que ajustar",
            "que pieza habria que ajustar",
            "historia rota",
            "continuidad histórica",
            "continuidad historica",
            "reliquia",
            "campana",
        )
    ):
        return "validation_request"
    if recognized_intent_name in {"validation_request"}:
        return "validation_request"
    if recognized_intent_name in {"prepare_narration"}:
        return "narration_preparation"
    if recognized_intent_name in {"prepare_review"}:
        return "review_handoff"
    if recognized_intent_name in {"structured_followup"}:
        return "structured_followup"
    if _has_recent_anchor(state) and token_count <= 3 and (request.target_hint or candidate_targets):
        return "contextual_followup"
    if narrative_signals is not None and narrative_signals.issue_types:
        if "canon_issue" in narrative_signals.issue_types:
            if len(candidate_targets) >= 2 or len(parts) > 1:
                return "mixed_request"
            return "validation_request"
        if any(issue_type in narrative_signals.issue_types for issue_type in {"tone_issue", "motivation_issue", "character_voice_mismatch", "clarity_issue", "continuity_issue"}):
            return "editorial_revision"
    if len(candidate_targets) >= 2 and (len(parts) > 1 or token_count >= 4):
        return "mixed_request"
    if recognized_intent_name == "editorial_structuring" and (len(parts) > 1 or token_count >= 4):
        return "structuring_request"
    if recognized_intent_name in {"inspect_scene", "inspect_chapter"} and _has_recent_anchor(state):
        return "contextual_followup"
    if candidate_targets and token_count <= 3 and _has_recent_anchor(state):
        return "contextual_followup"
    return "unknown"


def _derive_signals(
    raw_text: str,
    narrative_signals: NarrativeSignals | None,
    *,
    candidate_targets: list[CandidateTarget],
    primary_intent_type: str,
    parts: list[MixedRequestPart],
    token_count: int,
    editorial_diagnosis: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    author_goal_signals: list[str] = []
    preserve_signals: list[str] = []
    change_signals: list[str] = []
    issue_types = list((narrative_signals.issue_types if narrative_signals else []) or [])
    if "canon_issue" in issue_types:
        author_goal_signals.append("anchor_canon")
        preserve_signals.append("preserve_validated_canon")
    if "character_voice_mismatch" in issue_types:
        preserve_signals.append("preserve_character_voice")
    if "tone_issue" in issue_types:
        author_goal_signals.append("align_tone")
        change_signals.append("align_tone")
    if "motivation_issue" in issue_types:
        author_goal_signals.append("clarify_motivation")
        change_signals.append("clarify_motivation")
    if "clarity_issue" in issue_types or "continuity_issue" in issue_types:
        author_goal_signals.append("clarify_structure")
        change_signals.append("clarify_structure")
    if primary_intent_type == "structuring_request":
        author_goal_signals.append("structure_scene")
        change_signals.append("structure_scene")
    if primary_intent_type == "narration_preparation":
        author_goal_signals.append("prepare_for_narration")
        change_signals.append("prepare_for_narration")
    if primary_intent_type == "review_handoff":
        author_goal_signals.append("prepare_for_review")
        change_signals.append("prepare_for_review")
    if primary_intent_type == "validation_request":
        author_goal_signals.append("anchor_canon")
    if (
        (len(candidate_targets) >= 2 or len(parts) > 1)
        and editorial_diagnosis.get("dominant_need") not in {"canon_symbolic_fit", "voice_revision_relational"}
    ):
        author_goal_signals.append("structure_scene")
        change_signals.append("structure_scene")
    diagnosis_signals = _diagnosis_signals(raw_text, primary_intent_type=primary_intent_type, editorial_diagnosis=editorial_diagnosis)
    author_goal_signals.extend(diagnosis_signals["author_goal_signals"])
    preserve_signals.extend(diagnosis_signals["preserve_signals"])
    change_signals.extend(diagnosis_signals["change_signals"])
    return (_dedupe(author_goal_signals), _dedupe(preserve_signals), _dedupe(change_signals))


def _extract_narrative_content(
    text: str,
    *,
    primary_intent_type: str,
    narrative_signals: NarrativeSignals | None,
    candidate_targets: list[CandidateTarget],
    token_count: int,
    editorial_diagnosis: dict[str, Any],
) -> str | None:
    if editorial_diagnosis.get("is_editorial_metacommentary"):
        return None
    if primary_intent_type not in {"narrative_facts", "structuring_request", "mixed_request"}:
        return None
    if token_count < 4 and not candidate_targets and narrative_signals is None:
        return None
    stripped = text.strip()
    return stripped or None


def _extract_meta_instruction(
    text: str,
    *,
    primary_intent_type: str,
    narrative_content_text: str | None,
    editorial_diagnosis: dict[str, Any],
) -> str | None:
    if editorial_diagnosis.get("is_editorial_metacommentary"):
        return text.strip() or None
    if primary_intent_type not in {"narration_preparation", "review_handoff", "validation_request", "structured_followup", "mixed_request"}:
        return None
    if primary_intent_type == "mixed_request" and narrative_content_text is not None:
        return text.strip() or None
    return text.strip() or None


def _extract_followup_reference(
    text: str,
    parts: list[MixedRequestPart],
    state: ConversationState | None,
    candidate_targets: list[CandidateTarget],
    *,
    primary_intent_type: str,
    token_count: int,
    request_target_hint: str | None,
) -> str | None:
    followup_parts = [part.text for part in parts if part.part_type == "followup_reference"]
    if followup_parts:
        content = " ".join(followup_parts).strip()
        if content:
            return content
    if primary_intent_type not in {"contextual_followup", "structured_followup"}:
        return None
    if token_count <= 3 and (_has_recent_anchor(state) or request_target_hint or candidate_targets):
        return text.strip()
    return None


def _needs_clarification(
    *,
    primary_intent_type: str,
    narrative_content_text: str | None,
    followup_reference_text: str | None,
    disambiguation: DisambiguationResult,
    editorial_diagnosis: dict[str, Any],
) -> bool:
    if primary_intent_type == "unknown":
        return True
    if editorial_diagnosis.get("dominant_need") == "canon_symbolic_fit":
        return bool(disambiguation.requires_user_confirmation and not disambiguation.preferred_target)
    if editorial_diagnosis.get("is_editorial_metacommentary") and editorial_diagnosis.get("supports_anchor_only_guidance"):
        return bool(disambiguation.requires_user_confirmation and not disambiguation.preferred_target)
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
    editorial_diagnosis: dict[str, Any],
) -> str | None:
    if primary_intent_type == "unknown":
        return "The request is too ambiguous to classify safely."
    if editorial_diagnosis.get("dominant_need") == "canon_symbolic_fit":
        if disambiguation.requires_user_confirmation and not disambiguation.preferred_target:
            return disambiguation.reason
        return None
    if editorial_diagnosis.get("is_editorial_metacommentary") and editorial_diagnosis.get("supports_anchor_only_guidance"):
        if disambiguation.requires_user_confirmation and not disambiguation.preferred_target:
            return disambiguation.reason
        return None
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


def _split_mixed_request_parts(text: str, *, state: ConversationState | None, candidate_targets: list[CandidateTarget]) -> list[MixedRequestPart]:
    clauses = [clause.strip() for clause in re.split(r"(?:\n+|;|[.!?]+|->|—)", text) if clause.strip()]
    parts: list[MixedRequestPart] = []
    for clause in clauses:
        part_type = _classify_clause_part(clause, state=state, candidate_targets=candidate_targets)
        parts.append(MixedRequestPart(part_type=part_type, text=clause, confidence=_part_confidence(part_type, clause)))
    if not parts and text.strip():
        parts.append(MixedRequestPart(part_type="mixed", text=text.strip(), confidence=0.55))
    return parts


def _classify_clause_part(
    clause: str,
    *,
    state: ConversationState | None,
    candidate_targets: list[CandidateTarget],
) -> str:
    token_count = _token_count(clause)
    lowered = clause.casefold()
    if any(
        phrase in lowered
        for phrase in (
            "quiero montar",
            "quiero trabajar",
            "ayúdame a estructurar",
            "ayudame a estructurar",
            "me interesa que",
            "no quiero caricaturizar",
            "qué beat final",
            "que beat final",
            "estoy revisando",
            "revísame",
            "revisame",
            "voz interna",
            "grado de explicitud",
            "dinámica verbal",
            "dinamica verbal",
            "quiero arreglar una idea de trasfondo",
            "encaja con el canon",
            "qué pieza habría que ajustar",
            "que pieza habria que ajustar",
        )
    ):
        return "meta_instruction"
    if token_count <= 3 and _has_recent_anchor(state):
        return "followup_reference"
    if token_count <= 4 and not candidate_targets:
        return "meta_instruction"
    if token_count >= 4 and candidate_targets:
        return "narrative_content"
    return "mixed"


def _part_confidence(part_type: str, clause: str) -> float:
    confidence = 0.6
    if part_type in {"narrative_content", "revision"}:
        confidence += 0.15
    if part_type in {"followup_reference", "validation_request", "review_handoff", "narration_prep"}:
        confidence += 0.2
    return min(confidence, 0.95)


def _has_recent_anchor(state: ConversationState | None) -> bool:
    return bool(state and state.last_target_id)


def _token_count(raw_text: str) -> int:
    return len([token for token in raw_text.strip().split() if token])


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _build_editorial_diagnosis(
    *,
    text: str,
    primary_intent_type: str,
    candidate_targets: list[CandidateTarget],
    narrative_signals: NarrativeSignals | None,
    parts: list[MixedRequestPart],
) -> dict[str, Any]:
    lowered = text.casefold()
    issue_types = list((narrative_signals.issue_types if narrative_signals else []) or [])
    diagnostic_signals = _diagnostic_markers(lowered)
    is_metacommentary = bool(
        any(diagnostic_signals.values())
        or any(part.part_type == "meta_instruction" for part in parts)
        or ("escena" in lowered and any(phrase in lowered for phrase in ("quiero", "necesito", "me interesa", "no quiero")))
    )
    dominant_need = "general_editorial_guidance"
    if primary_intent_type in {"structuring_request", "mixed_request"} and (
        diagnostic_signals["tonal"] or diagnostic_signals["relational"] or diagnostic_signals["subtext"]
    ):
        dominant_need = "structuring_tonal_relational" if diagnostic_signals["tonal"] or diagnostic_signals["relational"] else "structuring"
    elif primary_intent_type == "editorial_revision":
        dominant_need = "voice_revision_relational"
    elif primary_intent_type in {"validation_request", "mixed_request"} and (
        diagnostic_signals["canon"] or any(target.target_type == "lore" for target in candidate_targets)
    ):
        dominant_need = "canon_symbolic_fit"
    secondary_needs: list[str] = []
    if diagnostic_signals["tonal"]:
        secondary_needs.append("tonal_balance")
    if diagnostic_signals["relational"]:
        secondary_needs.append("relational_progression")
    if diagnostic_signals["subtext"]:
        secondary_needs.append("subtext_control")
    if diagnostic_signals["canon"]:
        secondary_needs.append("canon_fit")
    if diagnostic_signals["symbolic"]:
        secondary_needs.append("symbolic_continuity")
    return {
        "dominant_need": dominant_need,
        "secondary_needs": _dedupe(secondary_needs),
        "diagnostic_signals": _dedupe(
            diagnostic_signals["tonal"]
            + diagnostic_signals["relational"]
            + diagnostic_signals["subtext"]
            + diagnostic_signals["canon"]
            + diagnostic_signals["symbolic"]
        ),
        "is_editorial_metacommentary": is_metacommentary,
        "supports_anchor_only_guidance": is_metacommentary and bool(candidate_targets),
        "has_candidate_anchor_context": bool(candidate_targets),
        "issue_types": issue_types,
    }


def _diagnosis_signals(raw_text: str, *, primary_intent_type: str, editorial_diagnosis: dict[str, Any]) -> dict[str, list[str]]:
    lowered = raw_text.casefold()
    author_goal_signals: list[str] = []
    preserve_signals: list[str] = []
    change_signals: list[str] = []
    diagnostic_signals = set(editorial_diagnosis.get("diagnostic_signals") or [])
    dominant_need = editorial_diagnosis.get("dominant_need")
    if dominant_need == "structuring_tonal_relational":
        author_goal_signals.extend(["shape_comedic_scene_with_relational_subtext", "choose_dual_effect_closing_beat"])
        change_signals.extend(["shape_comedic_scene_with_relational_subtext", "choose_dual_effect_closing_beat"])
    if dominant_need == "voice_revision_relational":
        author_goal_signals.extend(["revise_voice_and_relational_dynamic", "control_subtext_explicitness"])
        change_signals.extend(["guide_sera_intimate_but_guarded_voice", "control_subtext_explicitness"])
        preserve_signals.extend(["preserve_character_voice", "preserve_relational_coherence", "preserve_ren_care_pattern"])
    if dominant_need == "canon_symbolic_fit":
        author_goal_signals.extend(["evaluate_symbolic_canon_link", "test_deformed_historical_continuity"])
        change_signals.extend(["separate_plausible_symbolism_from_hard_canon"])
        preserve_signals.extend(["preserve_validated_canon"])
    if "subtext_control" in diagnostic_signals or "subtexto" in lowered:
        author_goal_signals.append("control_subtext_explicitness")
        change_signals.append("control_subtext_explicitness")
    if "relational_progression" in diagnostic_signals and dominant_need != "canon_symbolic_fit":
        author_goal_signals.append("control_closeness_without_confession")
        change_signals.append("control_closeness_without_confession")
    if "tonal_balance" in diagnostic_signals:
        author_goal_signals.append("balance_light_tone_with_relational_weight")
        change_signals.append("balance_light_tone_with_relational_weight")
    if "symbolic_continuity" in diagnostic_signals:
        author_goal_signals.append("test_deformed_historical_continuity")
    if any(phrase in lowered for phrase in ("ironía suave", "ironia suave", "cuidar en silencio", "cuidado en silencio")):
        preserve_signals.append("preserve_ren_care_pattern")
    if any(phrase in lowered for phrase in ("bajar la guardia", "baje la guardia", "más íntimo", "mas intimo")):
        change_signals.append("guide_sera_intimate_but_guarded_voice")
    if any(phrase in lowered for phrase in ("comedia arriba", "avance afectivo abajo", "bonus cómico", "bonus comico", "4koma", "gag suelto")):
        author_goal_signals.append("shape_comedic_scene_with_relational_subtext")
    if any(phrase in lowered for phrase in ("qué beat final", "que beat final", "doble efecto", "remate divertido")):
        author_goal_signals.append("choose_dual_effect_closing_beat")
        change_signals.append("choose_dual_effect_closing_beat")
    return {
        "author_goal_signals": _dedupe(author_goal_signals),
        "preserve_signals": _dedupe(preserve_signals),
        "change_signals": _dedupe(change_signals),
    }


def _diagnostic_markers(lowered: str) -> dict[str, list[str]]:
    tonal = []
    relational = []
    subtext = []
    canon = []
    symbolic = []
    if any(phrase in lowered for phrase in ("bonus cómico", "bonus comico", "4koma", "gag", "ritmo rápido", "ritmo rapido", "remate divertido", "ligera", "doble efecto")):
        tonal.append("tonal_balance")
    if any(phrase in lowered for phrase in ("avance afectivo", "vínculo", "vinculo", "fricción", "friccion", "bajar la guardia", "cercanía", "cercania", "confesión", "confesion")):
        relational.append("relational_progression")
    if any(phrase in lowered for phrase in ("subtexto", "explícit", "explicit", "doble efecto", "doble plano")):
        subtext.append("subtext_control")
    if any(phrase in lowered for phrase in ("canon", "spelarita", "thiseia", "elthariel", "reliquia", "campana")):
        canon.append("canon_fit")
    if any(phrase in lowered for phrase in ("historia rota", "continuidad histórica", "continuidad historica", "resonancia simbólica", "resonancia simbolica", "deformó", "deformo")):
        symbolic.append("symbolic_continuity")
    return {
        "tonal": tonal,
        "relational": relational,
        "subtext": subtext,
        "canon": canon,
        "symbolic": symbolic,
    }


def _merge_editorial_diagnosis(rule_diagnosis: dict[str, Any], llm_diagnosis: dict[str, Any]) -> dict[str, Any]:
    merged = dict(rule_diagnosis)
    for key, value in llm_diagnosis.items():
        if key in {"secondary_needs", "diagnostic_signals", "issue_types"}:
            merged[key] = _dedupe(list(merged.get(key, [])) + list(value or []))
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged
