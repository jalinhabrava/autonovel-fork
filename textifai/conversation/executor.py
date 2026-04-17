from __future__ import annotations

from textifai.conversation.contracts import PlannedTask
from textifai.conversation.state import ConversationState


class StubExecutionLayer:
    def execute(self, task: PlannedTask, state: ConversationState | None = None) -> dict:
        return {
            "type": "conversation_execution_stub",
            "task_type": task.task_type,
            "flow_name": task.flow_name,
            "executed": False,
            "summary": f"Stub executor prepared {task.flow_name}.",
            "state_turn_count": state.turn_count if state is not None else 0,
        }
