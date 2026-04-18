from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from textifai.author_understanding.contracts import AUTHOR_INTENT_TYPE_CATALOG, MIXED_PART_TYPE_CATALOG
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.state import ConversationState
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityResolutionResult


@dataclass(frozen=True)
class AuthorUnderstandingPrompt:
    system_prompt: str
    user_payload: dict[str, Any]
    required_output_schema: dict[str, Any]
    catalogs: dict[str, list[str]]
    prompt_version: str = "author_understanding.v1"


def build_author_understanding_prompt(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    narrative_signals: NarrativeSignals | None,
    entity_results: list[EntityResolutionResult],
    state: ConversationState | None,
) -> AuthorUnderstandingPrompt:
    candidate_hints = _serialize_candidate_hints(entity_results)
    payload = {
        "request_text": request.raw_text,
        "language_context": {
            "interface_language": request.interface_language,
            "user_command_language": request.user_command_language,
            "internal_system_language": request.internal_system_language,
            "project_default_language": request.project_default_language,
            "mixed_language_allowed": request.mixed_language_allowed,
            "artifact_target_language": request.artifact_target_language,
            "explanation_language": request.explanation_language,
        },
        "rule_based_intent": {
            "intent_name": rule_intent.intent_name,
            "confidence": rule_intent.confidence,
            "target_type": rule_intent.target_type,
            "target_id": rule_intent.target_id,
            "requires_target": rule_intent.requires_target,
            "signals": list(rule_intent.signals),
        },
        "conversation_state": {
            "conversation_id": state.conversation_id if state is not None else None,
            "turn_count": state.turn_count if state is not None else 0,
            "last_goal": state.last_goal if state is not None else None,
            "last_target_type": state.last_target_type if state is not None else None,
            "last_target_id": state.last_target_id if state is not None else None,
            "last_result_summary": state.last_result_summary if state is not None else None,
            "artifact_target_language": state.artifact_target_language if state is not None else None,
            "explanation_language": state.explanation_language if state is not None else None,
            "has_pending_operation": bool(state.pending_operation) if state is not None else False,
        },
        "narrative_signals": asdict(narrative_signals) if narrative_signals is not None else None,
        "vaerl_candidate_hints": candidate_hints,
        "recent_result_summary": state.last_result_summary if state is not None else None,
        "instructions": [
            "Interpret the author's intent structurally, not as a paraphrase of the vault.",
            "Do not invent certainty, targets, or facts.",
            "Prefer conservative clarification when the request is ambiguous.",
            "Separate narrative content from meta-instruction.",
            "Keep the output JSON only and stay within the provided catalogs.",
        ],
    }
    return AuthorUnderstandingPrompt(
        system_prompt=(
            "You are a structured author-understanding interpreter for a narrative editing tool.\n"
            "Return strict JSON only.\n"
            "Use the provided catalogs exactly.\n"
            "Do not invent targets, facts, or certainty.\n"
            "If the request is ambiguous, prefer clarification over false confidence.\n"
            "The vault is the source of truth, but you only interpret the author's request here.\n"
        ),
        user_payload=payload,
        required_output_schema={
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
                {"part_type": "narrative_content", "text": "...", "confidence": 0.0},
                {"part_type": "meta_instruction", "text": "...", "confidence": 0.0},
            ],
            "candidate_targets": [
                {"target_id": "...", "target_type": "...", "confidence": 0.0},
            ],
            "preferred_target": None,
            "disambiguation_reason": None,
        },
        catalogs={
            "primary_intent_type": list(AUTHOR_INTENT_TYPE_CATALOG),
            "part_type": list(MIXED_PART_TYPE_CATALOG),
        },
    )


def _serialize_candidate_hints(entity_results: list[EntityResolutionResult]) -> list[dict[str, Any]]:
    candidates: list[CandidateTarget] = []
    for item in entity_results:
        if item.resolved and item.resolved_entity_id and item.resolved_entity_type:
            candidates.append(
                CandidateTarget(
                    target_id=item.resolved_entity_id,
                    target_type=item.resolved_entity_type,
                    confidence=item.resolution_confidence,
                )
            )
            continue
        if item.candidate_entities:
            top = item.candidate_entities[0]
            candidates.append(
                CandidateTarget(
                    target_id=top.artifact_id,
                    target_type=top.artifact_type,
                    confidence=top.confidence,
                )
            )
    deduped: dict[tuple[str, str], CandidateTarget] = {}
    for candidate in candidates:
        key = (candidate.target_type, candidate.target_id)
        if key not in deduped or candidate.confidence > deduped[key].confidence:
            deduped[key] = candidate
    return [
        {
            "target_id": candidate.target_id,
            "target_type": candidate.target_type,
            "confidence": candidate.confidence,
        }
        for candidate in sorted(deduped.values(), key=lambda item: (item.confidence, item.target_type, item.target_id), reverse=True)
    ]
