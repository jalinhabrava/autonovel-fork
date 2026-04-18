from __future__ import annotations

from dataclasses import asdict

from textifai.conversation.contracts import ConversationRequest, PlannedTask, RecognizedIntent
from textifai.conversation.state import ConversationState


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
            step_kinds=step_kinds,
            metadata={
                "intent_name": effective_intent_name,
                "recognized_intent_name": intent.intent_name,
                "query_text": _derive_query_text(request, intent),
                "target_resolution_source": _target_resolution_source(request, intent, state),
                "confirmation_required": flow_name in {"decision_persistence_flow", "validate_artifact_flow", "reject_artifact_flow"},
                "planner_reason": planner_reason,
                "narrative_signals": asdict(intent.narrative_signals) if intent.narrative_signals is not None else None,
                "editorial_intent": asdict(intent.editorial_intent) if intent.editorial_intent is not None else None,
                "vaerl_results": intent.metadata.get("vaerl_results"),
                "unsupported_capability": unsupported_capability,
                "editorial_structuring_requested": effective_intent_name == "editorial_structuring",
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
    if editorial_intent and editorial_intent.metadata.get("multi_target") and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
    }:
        return None
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
    if editorial_intent and editorial_intent.metadata.get("multi_target") and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
    }:
        return None
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
    if editorial_intent and editorial_intent.metadata.get("multi_target") and editorial_intent.request_type in {
        "narrative_facts",
        "structuring_request",
        "editorial_revision",
        "narration_preparation",
        "mixed_editorial_request",
    }:
        return "editorial_intent_multi_target"
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
    if editorial_intent is not None:
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
            "narrative_facts",
            "structuring_request",
            "editorial_revision",
            "narration_preparation",
            "mixed_editorial_request",
            "contextual_followup",
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


def _planner_reason(intent: RecognizedIntent, effective_intent_name: str) -> str:
    if intent.metadata.get("unsupported_capability"):
        return "unsupported_capability"
    if intent.editorial_intent is not None and effective_intent_name == "editorial_structuring":
        return "editorial_intent_routing"
    if effective_intent_name == intent.intent_name:
        return "direct_intent_mapping"
    return "narrative_signal_inference"
