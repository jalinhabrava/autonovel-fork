from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace

from textifai.conversation.contracts import ConversationRequest, PlannedTask, RecognizedIntent
from textifai.conversation.state import ConversationState

FOLLOWTHROUGH_REQUEST_TYPES = {
    "validation_request",
    "narration_handoff",
    "review_handoff",
    "structured_followup",
}

FOLLOWTHROUGH_INTENTS = {
    "validate_structure",
    "prepare_narration",
    "prepare_review",
    "structured_followup",
}


class TaskPlanner:
    def plan(
        self,
        request: ConversationRequest,
        intent: RecognizedIntent,
        state: ConversationState | None = None,
    ) -> PlannedTask:
        effective_intent_name = _resolve_effective_intent_name(intent, state)
        unsupported_capability = intent.metadata.get("unsupported_capability")
        operation_language = _resolve_operation_language(request)
        explanation_language = request.explanation_language or request.interface_language
        artifact_target_language = request.artifact_target_language or (state.artifact_target_language if state else None)
        target_id = _resolve_target_id(request, intent, state)
        target_type = _resolve_target_type(intent, state)
        followthrough_action = _followthrough_action(intent, effective_intent_name)
        semantic_response_kind = _semantic_response_kind(intent, effective_intent_name, state)
        response_generation_candidate = _response_generation_candidate(
            request=request,
            intent=intent,
            effective_intent_name=effective_intent_name,
            state=state,
        )

        if followthrough_action is not None:
            task_type, flow_name, step_kinds = followthrough_action
            planner_reason = _planner_reason(intent, effective_intent_name)
            semantic_phase = _is_semantic_phase(task_type, flow_name, step_kinds)
            return PlannedTask(
                task_type=task_type,
                flow_name=flow_name,
                target_type=target_type,
                target_id=target_id,
                ephemeral=True,
                persistent=False,
                operation_language=operation_language,
                artifact_target_language=artifact_target_language,
                explanation_language=explanation_language,
                requires_context=False,
                requires_llm=False,
                requires_persistence=False,
                semantic_phase=semantic_phase,
                step_kinds=step_kinds,
                metadata={
                    "intent_name": effective_intent_name,
                    "recognized_intent_name": intent.intent_name,
                    "query_text": _derive_query_text(request, intent),
                    "raw_request_text": request.raw_text,
                    "target_resolution_source": _target_resolution_source(request, intent, state),
                    "confirmation_required": False,
                    "planner_reason": planner_reason,
                    "phase_classification": "semantic" if semantic_phase else "operational",
                    "narrative_signals": asdict(intent.narrative_signals) if intent.narrative_signals is not None else None,
                    "author_understanding": intent.metadata.get("author_understanding"),
                    "editorial_intent": asdict(intent.editorial_intent) if intent.editorial_intent is not None else None,
                    "vaerl_results": intent.metadata.get("vaerl_results"),
                    "unsupported_capability": intent.metadata.get("unsupported_capability"),
                    "editorial_structuring_requested": False,
                    "followthrough_action": intent.editorial_intent.metadata.get("followthrough_action") if intent.editorial_intent else effective_intent_name,
                    "semantic_response_kind": semantic_response_kind,
                    "response_generation_candidate": response_generation_candidate,
                },
            )

        mapping = {
            "editorial_structuring": ("editorial_structuring", "editorial_structuring_flow", True, False, False, False, ["resolve_entities", "structure_editorial", "prepare_narration_context", "return_response"]),
            "confirm_pending": ("conversation_control", "confirm_pending_flow", True, False, False, True, ["confirm_operation", "return_response"]),
            "cancel_pending": ("conversation_control", "cancel_pending_flow", True, False, False, False, ["cancel_operation", "return_response"]),
            "conversation_help": ("respond", "help_flow", True, False, False, False, ["return_response"]),
            "lookup_world": ("context_lookup", "world_lookup_flow", True, False, True, False, ["build_context", "return_response"]),
            "search_context": ("context_lookup", "context_search_flow", True, False, True, False, ["build_context", "return_response"]),
            "inspect_scene": ("context_lookup", "scene_context_flow", True, False, True, False, ["resolve_target", "build_context", "return_response"]),
            "inspect_chapter": ("context_lookup", "chapter_context_flow", True, False, True, False, ["resolve_target", "build_context", "return_response"]),
            "consistency_check": ("consistency_validation", "consistency_check_flow", True, False, True, False, ["resolve_target", "build_context", "run_consistency_check", "return_response"]),
            "persist_decision": ("artifact_persistence", "decision_persistence_flow", False, True, True, True, ["resolve_target", "build_context", "persist_artifact", "return_response"]),
            "validate_artifact": ("artifact_persistence", "validate_artifact_flow", False, True, False, True, ["resolve_target", "persist_artifact", "return_response"]),
            "reject_artifact": ("artifact_persistence", "reject_artifact_flow", False, True, False, True, ["resolve_target", "persist_artifact", "return_response"]),
            "bootstrap_extract": ("bootstrap_operation", "bootstrap_extract_flow", False, True, False, True, ["resolve_target", "persist_artifact", "return_response"]),
            "unknown": ("noop", "noop_flow", True, False, False, False, ["return_response"]),
        }
        task_type, flow_name, ephemeral, persistent, requires_context, requires_persistence, step_kinds = mapping[effective_intent_name]
        if unsupported_capability:
            task_type, flow_name, ephemeral, persistent, requires_context, requires_persistence, step_kinds = (
                "noop",
                "noop_flow",
                True,
                False,
                False,
                False,
                ["return_response"],
            )
        planner_reason = _planner_reason(intent, effective_intent_name)
        semantic_phase = _is_semantic_phase(task_type, flow_name, step_kinds)

        return PlannedTask(
            task_type=task_type,
            flow_name=flow_name,
            target_type=target_type,
            target_id=target_id,
            ephemeral=ephemeral,
            persistent=persistent,
            operation_language=operation_language,
            artifact_target_language=artifact_target_language,
            explanation_language=explanation_language,
            requires_context=requires_context,
            requires_llm=False,
            requires_persistence=requires_persistence,
            semantic_phase=semantic_phase,
            step_kinds=step_kinds,
            metadata={
                "intent_name": effective_intent_name,
                "recognized_intent_name": intent.intent_name,
                "query_text": _derive_query_text(request, intent),
                "raw_request_text": request.raw_text,
                "target_resolution_source": _target_resolution_source(request, intent, state),
                "confirmation_required": flow_name in {"decision_persistence_flow", "validate_artifact_flow", "reject_artifact_flow"},
                "planner_reason": planner_reason,
                "phase_classification": "semantic" if semantic_phase else "operational",
                "narrative_signals": asdict(intent.narrative_signals) if intent.narrative_signals is not None else None,
                "author_understanding": intent.metadata.get("author_understanding"),
                "editorial_intent": asdict(intent.editorial_intent) if intent.editorial_intent is not None else None,
                "vaerl_results": intent.metadata.get("vaerl_results"),
                "unsupported_capability": unsupported_capability,
                "editorial_structuring_requested": effective_intent_name == "editorial_structuring",
                "followthrough_action": intent.editorial_intent.metadata.get("followthrough_action") if intent.editorial_intent else None,
                "semantic_response_kind": semantic_response_kind,
                "response_generation_candidate": response_generation_candidate,
            },
        )


def _resolve_operation_language(request: ConversationRequest) -> str:
    if request.source == "user":
        return request.user_command_language or request.interface_language or "en"
    return request.internal_system_language or "en"


def _derive_query_text(request: ConversationRequest, intent: RecognizedIntent) -> str | None:
    lowered = request.raw_text.strip()
    if intent.intent_name == "search_context" and lowered.lower().startswith("find "):
        return lowered.split(maxsplit=1)[1].strip()
    if intent.intent_name == "search_context":
        return lowered
    if intent.intent_name == "unknown" and intent.narrative_signals and intent.narrative_signals.mentioned_entities:
        return ", ".join(intent.narrative_signals.mentioned_entities)
    return None


def _resolve_target_type(intent: RecognizedIntent, state: ConversationState | None) -> str | None:
    editorial_intent = intent.editorial_intent
    author_understanding = _author_understanding_from_intent(intent)
    if (
        editorial_intent
        and editorial_intent.metadata.get("multi_target")
        and intent.intent_name != "consistency_check"
        and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
        "structured_followup",
    }
    ):
        return None
    if author_understanding is not None and _author_understanding_requires_clarification(author_understanding) and not _intent_has_explicit_target(intent):
        return None
    preferred_target = _preferred_target_from_author_understanding(author_understanding)
    if preferred_target is not None:
        return preferred_target.target_type
    if editorial_intent and editorial_intent.resolved_target_type:
        return editorial_intent.resolved_target_type
    if editorial_intent and editorial_intent.followup_mode == "prefer_candidate_targets" and editorial_intent.candidate_targets:
        return editorial_intent.candidate_targets[0].target_type
    if intent.target_type:
        return intent.target_type
    if editorial_intent and editorial_intent.followup_mode == "reuse_recent_target":
        return state.last_target_type if state else None
    if (
        intent.intent_name == "consistency_check"
        and intent.narrative_signals is not None
        and "canon_issue" in intent.narrative_signals.issue_types
        and intent.narrative_signals.mentioned_entities
    ):
        return None
    if intent.narrative_signals and intent.narrative_signals.target_hint:
        return state.last_target_type if state else None
    return state.last_target_type if state else None


def _resolve_target_id(
    request: ConversationRequest,
    intent: RecognizedIntent,
    state: ConversationState | None,
) -> str | None:
    editorial_intent = intent.editorial_intent
    author_understanding = _author_understanding_from_intent(intent)
    if (
        editorial_intent
        and editorial_intent.metadata.get("multi_target")
        and intent.intent_name != "consistency_check"
        and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
        "structured_followup",
    }
    ):
        return None
    if author_understanding is not None:
        if _author_understanding_requires_clarification(author_understanding) and not _intent_has_explicit_target(intent):
            return None
        preferred_target = _preferred_target_from_author_understanding(author_understanding)
        if preferred_target is not None:
            return preferred_target.target_id
    if editorial_intent and editorial_intent.resolved_target_id:
        return editorial_intent.resolved_target_id
    if editorial_intent and editorial_intent.followup_mode == "prefer_candidate_targets" and editorial_intent.candidate_targets:
        return editorial_intent.candidate_targets[0].target_id
    if editorial_intent and editorial_intent.followup_mode == "reuse_recent_target":
        return state.last_target_id if state else None
    if intent.target_id:
        return intent.target_id
    if (
        intent.intent_name == "consistency_check"
        and intent.narrative_signals is not None
        and "canon_issue" in intent.narrative_signals.issue_types
        and intent.narrative_signals.mentioned_entities
    ):
        return None
    if intent.narrative_signals and intent.narrative_signals.target_hint:
        return intent.narrative_signals.target_hint
    return request.target_hint or (state.last_target_id if state else None)


def _target_resolution_source(
    request: ConversationRequest,
    intent: RecognizedIntent,
    state: ConversationState | None,
) -> str:
    editorial_intent = intent.editorial_intent
    author_understanding = _author_understanding_from_intent(intent)
    if (
        editorial_intent
        and editorial_intent.metadata.get("multi_target")
        and intent.intent_name != "consistency_check"
        and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
        "structured_followup",
    }
    ):
        return "editorial_intent_multi_target"
    if author_understanding is not None:
        if _author_understanding_requires_clarification(author_understanding):
            return "author_understanding_clarification"
        if _preferred_target_from_author_understanding(author_understanding) is not None:
            return "author_understanding_disambiguation"
    if editorial_intent and editorial_intent.resolved_target_id:
        return "editorial_intent_resolved"
    if editorial_intent and editorial_intent.followup_mode == "prefer_candidate_targets" and editorial_intent.candidate_targets:
        return "editorial_intent_candidate"
    if editorial_intent and editorial_intent.followup_mode == "reuse_recent_target":
        return "editorial_intent_followup"
    if intent.target_id:
        return "recognized_intent"
    if (
        intent.intent_name == "consistency_check"
        and intent.narrative_signals is not None
        and "canon_issue" in intent.narrative_signals.issue_types
        and intent.narrative_signals.mentioned_entities
    ):
        return "conservative_none"
    if intent.narrative_signals and intent.narrative_signals.target_hint:
        return intent.narrative_signals.target_inference_source or "narrative_signals"
    if request.target_hint:
        return "request_hint"
    if state and state.last_target_id:
        return "conversation_state"
    return "none"


def _resolve_effective_intent_name(intent: RecognizedIntent, state: ConversationState | None) -> str:
    editorial_intent = intent.editorial_intent
    if intent.intent_name in FOLLOWTHROUGH_INTENTS:
        if (
            editorial_intent is not None
            and intent.intent_name in {"prepare_narration", "prepare_review"}
            and editorial_intent.request_type in {
                "editorial_revision",
                "structuring_request",
                "mixed_editorial_request",
            }
        ):
            return "editorial_structuring"
        if (
            intent.intent_name == "structured_followup"
            and editorial_intent is not None
            and editorial_intent.metadata.get("multi_target")
        ):
            return "editorial_structuring"
        return intent.intent_name
    if editorial_intent is not None:
        if intent.intent_name == "consistency_check" and editorial_intent.request_type in {
            "validation_request",
            "mixed_editorial_request",
        }:
            return "consistency_check"
        if editorial_intent.request_type == "contextual_followup" and intent.intent_name in {"unknown", "inspect_scene"}:
            return "editorial_structuring"
        if editorial_intent.metadata.get("multi_target") and editorial_intent.request_type == "structured_followup":
            return "editorial_structuring"
        if editorial_intent.request_type in {"narration_preparation", "review_handoff"} and intent.intent_name == "unknown":
            return "editorial_structuring"
        if editorial_intent.request_type in FOLLOWTHROUGH_REQUEST_TYPES:
            return intent.intent_name if intent.intent_name != "unknown" else "structured_followup"
        if editorial_intent.metadata.get("multi_target") and editorial_intent.request_type in {
            "narrative_facts",
            "structuring_request",
            "editorial_revision",
            "narration_preparation",
            "mixed_editorial_request",
        }:
            return "editorial_structuring"
        if intent.intent_name == "consistency_check" and editorial_intent.request_type in {
            "editorial_revision",
            "contextual_followup",
            "structuring_request",
        } and not editorial_intent.resolved_target_id:
            return "editorial_structuring"
        if intent.intent_name in {"unknown", "inspect_scene"} and editorial_intent.request_type in {
            "editorial_revision",
            "structuring_request",
            "mixed_editorial_request",
            "narration_preparation",
        }:
            return "editorial_structuring"
    if intent.intent_name != "unknown":
        return intent.intent_name
    signals = intent.narrative_signals
    if signals is None:
        return intent.intent_name
    issue_types = set(signals.issue_types)
    target_type = intent.target_type or (state.last_target_type if state else None)
    if issue_types & {"canon_issue", "continuity_issue"} and (signals.target_hint or (state and state.last_target_id)):
        return "consistency_check"
    if target_type == "scene" and signals.target_hint:
        return "inspect_scene"
    if target_type == "chapter" and signals.target_hint:
        return "inspect_chapter"
    return intent.intent_name


def _followthrough_action(
    intent: RecognizedIntent,
    effective_intent_name: str,
) -> tuple[str, str, list[str]] | None:
    editorial_intent = intent.editorial_intent
    request_type = editorial_intent.request_type if editorial_intent is not None else None
    if (
        request_type == "structured_followup"
        and editorial_intent is not None
        and editorial_intent.metadata.get("multi_target")
    ):
        return None
    if (
        intent.intent_name != "consistency_check"
        and (effective_intent_name == "validate_structure" or request_type == "validation_request")
    ):
        return (
            "editorial_followthrough",
            "validate_structuring_flow",
            ["resolve_followthrough_source", "validate_structuring", "return_response"],
        )
    if effective_intent_name == "prepare_narration" or request_type == "narration_handoff":
        return (
            "editorial_followthrough",
            "narration_handoff_flow",
            ["resolve_followthrough_source", "prepare_narration_handoff", "return_response"],
        )
    if effective_intent_name == "prepare_review" or request_type == "review_handoff":
        return (
            "editorial_followthrough",
            "review_handoff_flow",
            ["resolve_followthrough_source", "prepare_review_handoff", "return_response"],
        )
    if effective_intent_name == "structured_followup" or request_type == "structured_followup":
        return (
            "editorial_followthrough",
            "structured_followup_flow",
            ["resolve_followthrough_source", "resume_structured_followup", "return_response"],
        )
    return None


def _planner_reason(intent: RecognizedIntent, effective_intent_name: str) -> str:
    if intent.metadata.get("unsupported_capability"):
        return "unsupported_capability"
    author_understanding = _author_understanding_from_intent(intent)
    if author_understanding is not None and author_understanding.get("analysis_source") in {"hybrid", "llm_assisted"}:
        return "author_understanding_routing"
    if intent.editorial_intent is not None and effective_intent_name == "editorial_structuring":
        return "editorial_intent_routing"
    if effective_intent_name == intent.intent_name:
        return "direct_intent_mapping"
    return "narrative_signal_inference"


def _author_understanding_from_intent(intent: RecognizedIntent) -> dict | None:
    value = intent.metadata.get("author_understanding")
    return value if isinstance(value, dict) else None


def _preferred_target_from_author_understanding(author_understanding: dict | None):
    if not author_understanding:
        return None
    disambiguation = author_understanding.get("disambiguation")
    if not isinstance(disambiguation, dict):
        return None
    preferred = disambiguation.get("preferred_target")
    if not isinstance(preferred, dict):
        return None
    target_id = preferred.get("target_id")
    target_type = preferred.get("target_type")
    if not target_id or not target_type:
        return None
    return SimpleNamespace(target_id=target_id, target_type=target_type)


def _author_understanding_requires_clarification(author_understanding: dict | None) -> bool:
    if not author_understanding:
        return False
    if author_understanding.get("needs_clarification"):
        return True
    disambiguation = author_understanding.get("disambiguation")
    if isinstance(disambiguation, dict):
        return bool(disambiguation.get("requires_user_confirmation", False)) and disambiguation.get("preferred_target") is None
    return False


def _intent_has_explicit_target(intent: RecognizedIntent) -> bool:
    return bool(intent.target_type and intent.target_id)


def _is_semantic_phase(task_type: str, flow_name: str, step_kinds: list[str]) -> bool:
    if task_type in {"editorial_structuring", "editorial_followthrough"}:
        return True
    if flow_name in {
        "editorial_structuring_flow",
        "validate_structuring_flow",
        "narration_handoff_flow",
        "review_handoff_flow",
        "structured_followup_flow",
        "world_lookup_flow",
        "context_search_flow",
        "scene_context_flow",
        "chapter_context_flow",
        "consistency_check_flow",
    }:
        return True
    semantic_steps = {
        "resolve_entities",
        "resolve_followthrough_source",
        "build_context",
        "structure_editorial",
        "prepare_narration_context",
        "validate_structuring",
        "prepare_narration_handoff",
        "prepare_review_handoff",
        "resume_structured_followup",
        "run_consistency_check",
    }
    return any(step in semantic_steps for step in step_kinds)


def _semantic_response_kind(intent: RecognizedIntent, effective_intent_name: str, state: ConversationState | None) -> str | None:
    editorial_intent = intent.editorial_intent
    if effective_intent_name == "consistency_check":
        return "canon_answer"
    if effective_intent_name in {"prepare_narration", "prepare_review"}:
        return "narration_handoff"
    if effective_intent_name == "structured_followup":
        if state is not None and state.last_target_id and state.last_target_type:
            return "contextual_followup_response"
        if editorial_intent is not None and editorial_intent.followup_mode == "require_clarification":
            return "clarification_with_candidates"
        return "contextual_followup_response"
    if editorial_intent is None:
        return None
    if editorial_intent.followup_mode == "require_clarification" and editorial_intent.request_type in {
        "contextual_followup",
        "structured_followup",
    }:
        return "clarification_with_candidates"
    mapping = {
        "structuring_request": "structuring_suggestion",
        "editorial_revision": "revision_guidance",
        "narration_preparation": "narration_handoff",
        "contextual_followup": "contextual_followup_response",
        "structured_followup": "contextual_followup_response",
        "validation_request": "canon_answer",
        "review_handoff": "revision_guidance",
        "mixed_editorial_request": "revision_guidance",
    }
    if editorial_intent.request_type == "mixed_editorial_request" and intent.intent_name == "consistency_check":
        return "canon_answer"
    return mapping.get(editorial_intent.request_type)


def _response_generation_candidate(
    *,
    request: ConversationRequest,
    intent: RecognizedIntent,
    effective_intent_name: str,
    state: ConversationState | None,
) -> bool:
    editorial_intent = intent.editorial_intent
    author_understanding = _author_understanding_from_intent(intent)
    if effective_intent_name in {"confirm_pending", "cancel_pending", "validate_artifact", "reject_artifact", "persist_decision"}:
        return False
    if effective_intent_name == "consistency_check":
        return bool(_resolve_target_id(request, intent, state) or (editorial_intent and editorial_intent.candidate_targets))
    if editorial_intent is None or author_understanding is None:
        return False
    if _author_understanding_requires_clarification(author_understanding):
        return 0 < len(editorial_intent.candidate_targets) <= 3
    if editorial_intent.resolved_target_id and editorial_intent.resolved_target_type:
        return True
    if editorial_intent.followup_mode == "reuse_recent_target" and state and state.last_target_id and state.last_target_type:
        return True
    return 0 < len(editorial_intent.candidate_targets) <= 3
