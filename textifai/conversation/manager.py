from __future__ import annotations

from textifai.conversation.contracts import ConversationRequest, ConversationTurn
from textifai.conversation.executor import StubExecutionLayer
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer
from textifai.conversation.planner import TaskPlanner
from textifai.conversation.state import ConversationState, apply_turn_to_state, create_conversation_state


class ConversationManager:
    def __init__(
        self,
        *,
        state: ConversationState | None = None,
        recognizer: HybridIntentRecognizer | None = None,
        planner: TaskPlanner | None = None,
        executor: StubExecutionLayer | None = None,
    ) -> None:
        self.state = state
        self.recognizer = recognizer or HybridIntentRecognizer()
        self.planner = planner or TaskPlanner()
        self.executor = executor or StubExecutionLayer()

    def handle_request(self, request: ConversationRequest) -> ConversationTurn:
        if self.state is None:
            self.state = create_conversation_state(
                explanation_language=request.explanation_language or request.interface_language,
                artifact_target_language=request.artifact_target_language,
            )
        intent = self.recognizer.recognize(request, self.state)
        task = self.planner.plan(request, intent, self.state)
        execution = self.executor.execute(task, self.state)
        turn = ConversationTurn(
            turn_index=self.state.turn_count + 1,
            request=request,
            recognized_intent=intent,
            planned_task=task,
            result_type=execution["type"],
            result_summary=execution["summary"],
            artifacts_touched=[],
            context_used=task.requires_context,
            persisted=task.requires_persistence,
        )
        self.state = apply_turn_to_state(self.state, turn)
        return turn
