import unittest

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.manager import ConversationManager


class TextifAIConversationManagerTests(unittest.TestCase):
    def test_manager_creates_state_and_updates_it_per_turn(self):
        manager = ConversationManager()
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
        turn = manager.handle_request(request)
        self.assertEqual(turn.turn_index, 1)
        self.assertEqual(turn.recognized_intent.intent_name, "inspect_scene")
        self.assertEqual(turn.planned_task.flow_name, "scene_context_flow")
        self.assertEqual(manager.state.turn_count, 1)
        self.assertEqual(manager.state.last_goal, "scene_context_flow")
        self.assertEqual(manager.state.last_target_type, "scene")
        self.assertEqual(manager.state.last_target_id, "scene_054_b")
        self.assertEqual(manager.state.explanation_language, "es")
        self.assertEqual(manager.state.artifact_target_language, "ja")


if __name__ == "__main__":
    unittest.main()
