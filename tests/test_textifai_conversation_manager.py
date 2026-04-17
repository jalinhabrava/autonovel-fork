import unittest

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer
from textifai.conversation.manager import ConversationManager
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from pathlib import Path
import tempfile
from vault.bootstrap import bootstrap_vault


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

    def test_manager_can_use_hybrid_recognizer_and_preserve_trace(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier(
                {
                    "intent_name": "inspect_scene",
                    "confidence": 0.88,
                    "target_type": "scene",
                    "target_id": "scene_054_b",
                    "classification_note": "LLM disambiguated a freeform scene request.",
                }
            )
        )
        manager = ConversationManager(recognizer=recognizer)
        request = ConversationRequest(
            raw_text="quiero ver esta escena",
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
        self.assertEqual(turn.recognized_intent.recognizer_kind, "hybrid_llm")
        self.assertEqual(turn.recognized_intent.metadata["recognition_source"], "hybrid_llm")
        self.assertEqual(turn.planned_task.flow_name, "scene_context_flow")

    def test_manager_syncs_real_execution_context_into_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="world",
                source="user",
                mode="normal",
                interface_language="en",
                user_command_language="en",
                internal_system_language="en",
                project_default_language="en",
                mixed_language_allowed=True,
                explanation_language="en",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "context_pack")
            self.assertIsNotNone(manager.state.last_context_request)
            self.assertIsNotNone(manager.state.last_context_pack)
            self.assertIs(session.conversation_state, manager.state)


class _StubClassifier:
    def __init__(self, result):
        self.result = result

    def classify_intent(self, *, request, rule_intent, state):
        return dict(self.result)


if __name__ == "__main__":
    unittest.main()
