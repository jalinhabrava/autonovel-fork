from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from textifai.conversation.contracts import ConversationTurn, PendingConversationOperation


@dataclass(frozen=True)
class ConversationState:
    conversation_id: str
    turn_count: int
    last_goal: str | None
    last_target_type: str | None
    last_target_id: str | None
    last_context_request: dict | None
    last_context_pack: dict | None
    last_result_summary: str | None
    explanation_language: str
    artifact_target_language: str | None
    last_operation_ephemeral: bool | None
    last_operation_persistent: bool | None
    pending_operation: PendingConversationOperation | None


def create_conversation_state(
    *,
    explanation_language: str,
    artifact_target_language: str | None = None,
) -> ConversationState:
    return ConversationState(
        conversation_id=str(uuid4()),
        turn_count=0,
        last_goal=None,
        last_target_type=None,
        last_target_id=None,
        last_context_request=None,
        last_context_pack=None,
        last_result_summary=None,
        explanation_language=explanation_language,
        artifact_target_language=artifact_target_language,
        last_operation_ephemeral=None,
        last_operation_persistent=None,
        pending_operation=None,
    )


def apply_turn_to_state(
    state: ConversationState,
    turn: ConversationTurn,
    *,
    context_request: dict | None = None,
    context_pack: dict | None = None,
    pending_operation: PendingConversationOperation | None = None,
    clear_pending_operation: bool = False,
) -> ConversationState:
    planned = turn.planned_task
    return replace(
        state,
        turn_count=turn.turn_index,
        last_goal=planned.flow_name if planned else None,
        last_target_type=(planned.target_type if planned else None),
        last_target_id=(planned.target_id if planned else None),
        last_context_request=context_request if context_request is not None else state.last_context_request,
        last_context_pack=context_pack if context_pack is not None else state.last_context_pack,
        last_result_summary=turn.result_summary,
        explanation_language=(
            planned.explanation_language
            if planned is not None
            else turn.request.explanation_language or state.explanation_language
        ),
        artifact_target_language=(
            planned.artifact_target_language if planned is not None else state.artifact_target_language
        ),
        last_operation_ephemeral=(planned.ephemeral if planned is not None else state.last_operation_ephemeral),
        last_operation_persistent=(planned.persistent if planned is not None else state.last_operation_persistent),
        pending_operation=(
            None
            if clear_pending_operation
            else pending_operation
            if pending_operation is not None
            else state.pending_operation
        ),
    )
