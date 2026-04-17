from __future__ import annotations

from textifai.conversation.contracts import ConversationRequest, ConversationTurn
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer
from textifai.conversation.planner import TaskPlanner
from textifai.conversation.state import ConversationState, apply_turn_to_state, create_conversation_state
from textifai.session import TextifAISession


class ConversationManager:
    def __init__(
        self,
        *,
        session: TextifAISession | None = None,
        state: ConversationState | None = None,
        recognizer: HybridIntentRecognizer | None = None,
        planner: TaskPlanner | None = None,
        executor: MinimalExecutionLayer | None = None,
    ) -> None:
        self.session = session
        self.state = state or (session.conversation_state if session is not None else None)
        self.recognizer = recognizer or HybridIntentRecognizer()
        self.planner = planner or TaskPlanner()
        self.executor = executor or MinimalExecutionLayer(session=session)

    def handle_request(self, request: ConversationRequest) -> ConversationTurn:
        if self.state is None:
            self.state = create_conversation_state(
                explanation_language=request.explanation_language or request.interface_language,
                artifact_target_language=request.artifact_target_language,
            )
        intent = self.recognizer.recognize(request, self.state)
        task = self.planner.plan(request, intent, self.state)
        execution = self.executor.execute(task, request, self.state)
        turn = ConversationTurn(
            turn_index=self.state.turn_count + 1,
            request=request,
            recognized_intent=intent,
            planned_task=task,
            result_type=execution.type,
            result_summary=execution.result_summary,
            artifacts_touched=execution.artifacts_touched,
            context_used=execution.context_pack is not None or task.requires_context,
            persisted=execution.persisted,
        )
        self.state = apply_turn_to_state(
            self.state,
            turn,
            context_request=execution.context_request,
            context_pack=execution.context_pack,
        )
        if self.session is not None:
            self.session.conversation_state = self.state
        return turn
