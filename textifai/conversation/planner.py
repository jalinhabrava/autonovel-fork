from __future__ import annotations

from textifai.conversation.contracts import ConversationRequest, PlannedTask, RecognizedIntent
from textifai.conversation.state import ConversationState


class TaskPlanner:
    def plan(
        self,
        request: ConversationRequest,
        intent: RecognizedIntent,
        state: ConversationState | None = None,
    ) -> PlannedTask:
        operation_language = _resolve_operation_language(request)
        explanation_language = request.explanation_language or request.interface_language
        artifact_target_language = request.artifact_target_language or (state.artifact_target_language if state else None)
        target_id = _resolve_target_id(request, intent, state)
        target_type = intent.target_type or _resolve_target_type(intent, state)

        mapping = {
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
        task_type, flow_name, ephemeral, persistent, requires_context, requires_persistence, step_kinds = mapping[intent.intent_name]

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
                "intent_name": intent.intent_name,
                "query_text": _derive_query_text(request, intent),
                "target_resolution_source": _target_resolution_source(request, intent, state),
                "confirmation_required": flow_name in {"decision_persistence_flow", "validate_artifact_flow", "reject_artifact_flow"},
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
    return None


def _resolve_target_type(intent: RecognizedIntent, state: ConversationState | None) -> str | None:
    return intent.target_type or (state.last_target_type if state else None)


def _resolve_target_id(
    request: ConversationRequest,
    intent: RecognizedIntent,
    state: ConversationState | None,
) -> str | None:
    return intent.target_id or request.target_hint or (state.last_target_id if state else None)


def _target_resolution_source(
    request: ConversationRequest,
    intent: RecognizedIntent,
    state: ConversationState | None,
) -> str:
    if intent.target_id:
        return "recognized_intent"
    if request.target_hint:
        return "request_hint"
    if state and state.last_target_id:
        return "conversation_state"
    return "none"
