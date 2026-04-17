import unittest

from textifai.conversation.contracts import (
    ConversationRequest,
    ConversationTurn,
    PlannedTask,
    RecognizedIntent,
)
from textifai.conversation.state import create_conversation_state


class TextifAIConversationContractsTests(unittest.TestCase):
    def test_conversation_request_keeps_explanation_language_explicit(self):
        request = ConversationRequest(
            raw_text="Explícame esta escena",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            artifact_target_language="ja",
            explanation_language="es",
        )
        self.assertEqual(request.explanation_language, "es")

    def test_recognized_intent_uses_controlled_catalog(self):
        intent = RecognizedIntent(intent_name="inspect_scene", confidence=0.9)
        self.assertEqual(intent.intent_name, "inspect_scene")
        with self.assertRaises(ValueError):
            RecognizedIntent(intent_name="scene_magic", confidence=0.5)

    def test_planned_task_uses_controlled_flow_and_steps(self):
        task = PlannedTask(
            task_type="context_lookup",
            flow_name="scene_context_flow",
            target_type="scene",
            target_id="scene_001",
            ephemeral=True,
            persistent=False,
            operation_language="es",
            artifact_target_language="ja",
            explanation_language="es",
            requires_context=True,
            requires_llm=False,
            requires_persistence=False,
            step_kinds=["resolve_target", "build_context", "return_response"],
        )
        self.assertEqual(task.flow_name, "scene_context_flow")
        with self.assertRaises(ValueError):
            PlannedTask(
                task_type="context_lookup",
                flow_name="scene_context_flow",
                target_type="scene",
                target_id="scene_001",
                ephemeral=True,
                persistent=False,
                operation_language="es",
                artifact_target_language="ja",
                explanation_language="es",
                requires_context=True,
                requires_llm=False,
                requires_persistence=False,
                step_kinds=["invented_step"],
            )

    def test_conversation_turn_and_state_are_short_and_explicit(self):
        state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        turn = ConversationTurn(
            turn_index=1,
            request=ConversationRequest(
                raw_text="scene scene_001",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                artifact_target_language="ja",
                explanation_language="es",
            ),
            recognized_intent=None,
            planned_task=None,
        )
        self.assertEqual(state.turn_count, 0)
        self.assertEqual(turn.turn_index, 1)


if __name__ == "__main__":
    unittest.main()
