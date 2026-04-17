import unittest

from textifai.conversation.contracts import ConversationRequest, RecognizedIntent
from textifai.conversation.planner import TaskPlanner
from textifai.conversation.state import create_conversation_state


class TextifAIConversationPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()
        self.state = create_conversation_state(explanation_language="es", artifact_target_language="ja")

    def test_planner_maps_known_intent_to_controlled_flow(self):
        request = ConversationRequest(
            raw_text="scene scene_054_b",
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
        intent = RecognizedIntent(
            intent_name="inspect_scene",
            confidence=0.95,
            target_type="scene",
            target_id="scene_054_b",
            requires_target=True,
        )
        task = self.planner.plan(request, intent, self.state)
        self.assertEqual(task.task_type, "context_lookup")
        self.assertEqual(task.flow_name, "scene_context_flow")
        self.assertEqual(task.operation_language, "es")
        self.assertEqual(task.artifact_target_language, "ja")
        self.assertEqual(task.step_kinds, ["resolve_target", "build_context", "return_response"])

    def test_planner_uses_unknown_intent_as_noop(self):
        request = ConversationRequest(
            raw_text="haz algo con esto",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = RecognizedIntent(intent_name="unknown", confidence=0.2)
        task = self.planner.plan(request, intent, self.state)
        self.assertEqual(task.task_type, "noop")
        self.assertEqual(task.flow_name, "noop_flow")
        self.assertEqual(task.step_kinds, ["return_response"])


if __name__ == "__main__":
    unittest.main()
