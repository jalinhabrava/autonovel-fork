import unittest

from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
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

    def test_planner_can_promote_unknown_intent_from_controlled_narrative_signals(self):
        state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        state = state.__class__(
            **{
                **state.__dict__,
                "last_target_type": "scene",
                "last_target_id": "scene_054_b",
            }
        )
        request = ConversationRequest(
            raw_text="no me gusta esta escena porque Sera no diría eso nunca",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = RecognizedIntent(
            intent_name="unknown",
            confidence=0.3,
            narrative_signals=NarrativeSignals(
                mentioned_entities=["Sera"],
                mentioned_character_ids=["sera"],
                target_hint="scene_054_b",
                target_inference_source="conversation_state",
                issue_types=["character_voice_mismatch"],
                constraint_hints=["check_character_voice"],
                confidence=0.83,
            ),
        )
        task = self.planner.plan(request, intent, state)
        self.assertEqual(task.flow_name, "scene_context_flow")
        self.assertEqual(task.metadata["planner_reason"], "narrative_signal_inference")

    def test_planner_marks_unsupported_capability_explicitly(self):
        request = ConversationRequest(
            raw_text="haz bootstrap del canon de los capítulos 1 a 3",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = RecognizedIntent(
            intent_name="unknown",
            confidence=0.35,
            metadata={"unsupported_capability": "bootstrap_extract"},
        )
        task = self.planner.plan(request, intent, self.state)
        self.assertEqual(task.flow_name, "noop_flow")
        self.assertEqual(task.metadata["unsupported_capability"], "bootstrap_extract")
        self.assertEqual(task.metadata["planner_reason"], "unsupported_capability")

    def test_planner_is_conservative_with_recent_target_when_canon_issue_mentions_other_entity(self):
        state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        state = state.__class__(
            **{
                **state.__dict__,
                "last_target_type": "scene",
                "last_target_id": "scene_054_b",
            }
        )
        request = ConversationRequest(
            raw_text="esto contradice el canon del ritual",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = RecognizedIntent(
            intent_name="consistency_check",
            confidence=0.76,
            requires_target=True,
            narrative_signals=NarrativeSignals(
                mentioned_entities=["ritual"],
                target_hint=None,
                target_inference_source=None,
                issue_types=["canon_issue"],
                constraint_hints=["check_validated_canon"],
                confidence=0.75,
            ),
        )
        task = self.planner.plan(request, intent, state)
        self.assertIsNone(task.target_id)


if __name__ == "__main__":
    unittest.main()
