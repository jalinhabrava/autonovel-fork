from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.contracts import LLMInterpretationResult
from textifai.author_understanding.normalization import extract_json_payload, normalize_llm_interpretation_result
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.state import ConversationState
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityResolutionResult


class AuthorUnderstandingLLMInterpreter(Protocol):
    def interpret(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        narrative_signals: NarrativeSignals | None,
        entity_results: list[EntityResolutionResult],
        state: ConversationState | None,
    ) -> LLMInterpretationResult | None: ...


@dataclass(frozen=True)
class AuthorUnderstandingLLMConfig:
    task_name: str = "author_understanding"
    provider_name: str | None = None
    model: str | None = None
    max_tokens: int = 1200
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1


class ProviderBackedAuthorUnderstandingInterpreter:
    def __init__(self, *, config: AuthorUnderstandingLLMConfig | None = None) -> None:
        self.config = config or AuthorUnderstandingLLMConfig()

    def interpret(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        narrative_signals: NarrativeSignals | None,
        entity_results: list[EntityResolutionResult],
        state: ConversationState | None,
    ) -> LLMInterpretationResult | None:
        if get_text_provider_config_error(self.config.task_name, self.config.provider_name):
            return None

        prompt_payload = _build_prompt_payload(
            request=request,
            rule_intent=rule_intent,
            narrative_signals=narrative_signals,
            entity_results=entity_results,
            state=state,
        )
        system_prompt = (
            "You analyze an author's editorial request for a narrative tool.\n"
            "Return strict JSON only. Do not include markdown or prose.\n"
            "Use the closed catalog provided in the prompt.\n"
            "Do not invent targets, facts, or certainty.\n"
            "Prefer conservative answers when the request is ambiguous.\n"
        )
        user_prompt = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)
        provider = get_text_provider(self.config.task_name, self.config.provider_name)
        response = provider.generate(
            TextGenerationRequest(
                task=self.config.task_name,
                provider_name=self.config.provider_name,
                model=self.config.model,
                system=system_prompt,
                messages=[TextMessage(role="user", content=user_prompt)],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds,
                retries=self.config.retries,
            )
        )
        payload = extract_json_payload(response.text)
        if payload is None:
            return None
        return normalize_llm_interpretation_result(
            raw_text=request.raw_text,
            payload=payload,
            provider_name=response.provider_name,
            model=response.model,
        )


def _build_prompt_payload(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    narrative_signals: NarrativeSignals | None,
    entity_results: list[EntityResolutionResult],
    state: ConversationState | None,
) -> dict:
    return {
        "request_text": request.raw_text,
        "language_context": {
            "interface_language": request.interface_language,
            "user_command_language": request.user_command_language,
            "project_default_language": request.project_default_language,
            "mixed_language_allowed": request.mixed_language_allowed,
        },
        "recognized_intent": {
            "intent_name": rule_intent.intent_name,
            "confidence": rule_intent.confidence,
            "target_type": rule_intent.target_type,
            "target_id": rule_intent.target_id,
            "signals": list(rule_intent.signals),
        },
        "narrative_signals": narrative_signals.__dict__ if narrative_signals is not None else None,
        "conversation_state": {
            "last_target_type": state.last_target_type if state is not None else None,
            "last_target_id": state.last_target_id if state is not None else None,
            "turn_count": state.turn_count if state is not None else 0,
        },
        "vault_candidates": _serialize_candidate_targets(entity_results),
        "required_output": {
            "primary_intent_type": "unknown",
            "secondary_intent_types": [],
            "confidence": 0.0,
            "has_mixed_request": False,
            "author_goal_signals": [],
            "preserve_signals": [],
            "change_signals": [],
            "followup_reference_text": None,
            "narrative_content_text": None,
            "meta_instruction_text": None,
            "needs_clarification": False,
            "clarification_reason": None,
            "parts": [
                {"part_type": "narrative_content", "text": "..." , "confidence": 0.0},
            ],
            "candidate_targets": [
                {"target_id": "...", "target_type": "...", "confidence": 0.0},
            ],
            "preferred_target": None,
            "disambiguation_reason": None,
        },
        "catalogs": {
            "primary_intent_type": [
                "unknown",
                "narrative_facts",
                "editorial_revision",
                "structuring_request",
                "narration_preparation",
                "contextual_followup",
                "validation_request",
                "narration_handoff",
                "review_handoff",
                "structured_followup",
                "mixed_request",
            ],
            "part_type": [
                "narrative_content",
                "revision",
                "preserve",
                "meta_instruction",
                "followup_reference",
                "narration_prep",
                "review_handoff",
                "validation_request",
                "mixed",
            ],
        },
        "instructions": [
            "Classify the author's actual intent, not the vault content.",
            "Separate content from meta-instruction when both are present.",
            "If the request is ambiguous, prefer needs_clarification over certainty.",
            "If a target is not strongly anchored, keep candidate_targets empty or conservative.",
        ],
    }


def _serialize_candidate_targets(entity_results: list[EntityResolutionResult]) -> list[dict]:
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
    return [
        {
            "target_id": target.target_id,
            "target_type": target.target_type,
            "confidence": target.confidence,
        }
        for target in sorted(deduped.values(), key=lambda item: (item.confidence, item.target_type, item.target_id), reverse=True)
    ]
