import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.conversation.contracts import ConversationRequest, PlannedTask
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.state import create_conversation_state
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault


class TextifAIConversationExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tempdir.name)
        self.vault_root = self.base_dir / "Vault"
        bootstrap_vault(self.vault_root, title="Test Project")
        (self.base_dir / ".env").write_text(
            "\n".join(
                [
                    "AUTONOVEL_PROJECT_BACKEND=vault",
                    f"AUTONOVEL_VAULT_ROOT={self.vault_root}",
                    "AUTONOVEL_TEXT_PROVIDER=ollama",
                    "TEXTIFAI_INTERFACE_LANGUAGE=es",
                    "TEXTIFAI_USER_COMMAND_LANGUAGE=es",
                    'TEXTIFAI_ARTIFACT_LANGUAGES={"chapter":"ja","scene":"ja","lore":"es","world":"es"}',
                ]
            )
            + "\n"
        )
        self.session = create_session(load_runtime_environment(self.base_dir))
        self.state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        self.executor = MinimalExecutionLayer(session=self.session)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_help_flow_reuses_product_help(self):
        task = PlannedTask(
            task_type="respond",
            flow_name="help_flow",
            target_type=None,
            target_id=None,
            ephemeral=True,
            persistent=False,
            operation_language="es",
            artifact_target_language="ja",
            explanation_language="es",
            requires_context=False,
            requires_llm=False,
            requires_persistence=False,
            step_kinds=["return_response"],
        )
        request = _request("help")
        result = self.executor.execute(task, request, self.state)
        self.assertEqual(result.type, "conversation_help")
        self.assertTrue(result.success)
        self.assertIn("world", result.result)
        self.assertIn("bootstrap", result.result)

    def test_world_search_scene_and_chapter_delegate_to_existing_context_layer(self):
        with patch("textifai.conversation.executor.build_world_context", return_value={"type": "context_pack"}) as world_mock:
            result = self.executor.execute(_task("world_lookup_flow"), _request("world"), self.state)
        world_mock.assert_called_once()
        self.assertEqual(result.type, "context_pack")
        self.assertEqual(result.context_request["intent"], "world_lookup")

        with patch("textifai.conversation.executor.build_find_context", return_value={"type": "context_pack"}) as find_mock:
            result = self.executor.execute(_task("context_search_flow", metadata={"query_text": "Sera"}), _request("find Sera"), self.state)
        find_mock.assert_called_once()
        self.assertEqual(result.type, "context_pack")
        self.assertEqual(result.context_request["intent"], "context_search")

        with patch("textifai.conversation.executor.build_scene_context", return_value={"type": "context_pack"}) as scene_mock:
            result = self.executor.execute(_task("scene_context_flow", target_type="scene", target_id="scene_054_b"), _request("scene scene_054_b"), self.state)
        scene_mock.assert_called_once()
        self.assertEqual(result.context_request["artifact_target_language"], "ja")

        with patch("textifai.conversation.executor.build_chapter_context", return_value={"type": "context_pack"}) as chapter_mock:
            result = self.executor.execute(_task("chapter_context_flow", target_type="chapter", target_id="ch_12"), _request("chapter ch_12"), self.state)
        chapter_mock.assert_called_once()
        self.assertEqual(result.context_request["artifact_target_language"], "ja")

    def test_consistency_check_delegates_to_existing_persistence_layer(self):
        decision_path = self.vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
        decision_path.write_text(
            "---\nkind: canon_decision\ntitle: Magic Costs\nstatus: proposed\nschema_version: 1.0\nartifact_language: es\n---\n\n# Magic Costs\n\nMagic has a visible cost.\n"
        )
        with patch(
            "textifai.conversation.executor.consistency_check",
            return_value={"type": "consistency_report", "summary": "No blocking issues detected.", "context_request": {"intent": "consistency_check"}, "context_pack": {"type": "context_pack"}},
        ) as check_mock:
            result = self.executor.execute(
                _task("consistency_check_flow", target_type="decision", target_id="magic_costs"),
                _request("check decision:magic_costs"),
                self.state,
            )
        check_mock.assert_called_once()
        payload = check_mock.call_args.args[1]
        self.assertEqual(payload["artifact_language"], "es")
        self.assertEqual(payload["operation_language"], "es")
        self.assertEqual(result.type, "consistency_report")

    def test_missing_target_is_controlled(self):
        result = self.executor.execute(
            _task("scene_context_flow", target_type="scene", target_id=None),
            _request("quiero ver esta escena"),
            self.state,
        )
        self.assertEqual(result.type, "missing_target")
        self.assertTrue(result.missing_target)
        self.assertFalse(result.success)


def _request(raw_text: str) -> ConversationRequest:
    return ConversationRequest(
        raw_text=raw_text,
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


def _task(flow_name: str, *, target_type=None, target_id=None, metadata=None) -> PlannedTask:
    task_type = "respond" if flow_name == "help_flow" else "context_lookup"
    if flow_name == "consistency_check_flow":
        task_type = "consistency_validation"
    return PlannedTask(
        task_type=task_type,
        flow_name=flow_name,
        target_type=target_type,
        target_id=target_id,
        ephemeral=True,
        persistent=False,
        operation_language="es",
        artifact_target_language="ja",
        explanation_language="es",
        requires_context=flow_name != "help_flow",
        requires_llm=False,
        requires_persistence=False,
        step_kinds=["return_response"],
        metadata=metadata or {},
    )


if __name__ == "__main__":
    unittest.main()
