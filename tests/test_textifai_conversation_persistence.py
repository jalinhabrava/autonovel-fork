import tempfile
import unittest
from pathlib import Path

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.manager import ConversationManager
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class TextifAIConversationPersistenceTests(unittest.TestCase):
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
                    'TEXTIFAI_ARTIFACT_LANGUAGES={"decision":"es","lore":"es"}',
                ]
            )
            + "\n"
        )
        self.session = create_session(load_runtime_environment(self.base_dir))
        self.manager = ConversationManager(session=self.session)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_persist_decision_requires_complete_payload_before_pending_confirmation(self):
        turn = self.manager.handle_request(_request("decide"))
        self.assertEqual(turn.result_type, "proposal_incomplete")
        self.assertFalse(turn.persisted)
        self.assertIsNone(self.manager.state.pending_operation)
        self.assertIn("missing", turn.result_summary.lower())
        self.assertIn("ask again", turn.result_summary.lower())

    def test_persist_decision_creates_pending_operation_and_executes_only_after_confirm(self):
        turn = self.manager.handle_request(
            _request(
                "decide",
                metadata={
                    "decision_title": "Magic Costs",
                    "decision_body": "Magic always costs something.",
                    "decision_affects": ["Sera"],
                },
            )
        )
        self.assertEqual(turn.result_type, "pending_confirmation")
        self.assertIsNotNone(self.manager.state.pending_operation)
        self.assertEqual(self.manager.state.pending_operation.operation_kind, "persist_decision")

        confirm_turn = self.manager.handle_request(_request("confirm"))
        self.assertEqual(confirm_turn.result_type, "decision_canon")
        self.assertTrue(confirm_turn.persisted)
        self.assertIsNone(self.manager.state.pending_operation)
        decision_path = self.vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
        self.assertTrue(decision_path.exists())

    def test_validate_artifact_requires_resolvable_target(self):
        turn = self.manager.handle_request(_request("validate missing:artifact"))
        self.assertEqual(turn.result_type, "missing_target")
        self.assertIsNone(self.manager.state.pending_operation)

    def test_validate_artifact_uses_confirmation_cycle(self):
        write_or_update_note(
            self.vault_root,
            note_type="lore",
            slug="magic_limits",
            title="Magic Limits",
            status="proposed",
            body="Magic has a cost.",
        )
        turn = self.manager.handle_request(_request("validate lore:magic_limits"))
        self.assertEqual(turn.result_type, "pending_confirmation")
        self.assertEqual(self.manager.state.pending_operation.operation_kind, "validate_artifact")

        confirm_turn = self.manager.handle_request(_request("confirm"))
        self.assertEqual(confirm_turn.result_type, "artifact_state_change")
        self.assertTrue(confirm_turn.persisted)
        text = (self.vault_root / "02_World" / "Lore" / "magic_limits.md").read_text()
        self.assertIn("status: validated", text)

    def test_reject_artifact_uses_confirmation_cycle(self):
        write_or_update_note(
            self.vault_root,
            note_type="lore",
            slug="magic_limits",
            title="Magic Limits",
            status="pending_revision",
            body="Magic has a cost.",
        )
        turn = self.manager.handle_request(_request("reject lore:magic_limits"))
        self.assertEqual(turn.result_type, "pending_confirmation")
        self.assertEqual(self.manager.state.pending_operation.operation_kind, "reject_artifact")

        confirm_turn = self.manager.handle_request(_request("confirm"))
        self.assertEqual(confirm_turn.result_type, "artifact_state_change")
        self.assertTrue(confirm_turn.persisted)
        text = (self.vault_root / "02_World" / "Lore" / "magic_limits.md").read_text()
        self.assertIn("status: rejected", text)

    def test_cancel_clears_pending_operation(self):
        self.manager.handle_request(
            _request(
                "decide",
                metadata={
                    "decision_title": "Magic Costs",
                    "decision_body": "Magic always costs something.",
                },
            )
        )
        cancel_turn = self.manager.handle_request(_request("cancel"))
        self.assertEqual(cancel_turn.result_type, "cancelled")
        self.assertFalse(cancel_turn.persisted)
        self.assertIsNone(self.manager.state.pending_operation)

    def test_confirm_after_cancel_does_not_execute_anything(self):
        self.manager.handle_request(
            _request(
                "decide",
                metadata={
                    "decision_title": "Magic Costs",
                    "decision_body": "Magic always costs something.",
                },
            )
        )
        self.manager.handle_request(_request("cancel"))
        confirm_turn = self.manager.handle_request(_request("confirm"))
        self.assertEqual(confirm_turn.result_type, "no_pending_operation")
        self.assertFalse(confirm_turn.persisted)

    def test_confirm_and_cancel_without_pending_operation_are_clear(self):
        confirm_turn = self.manager.handle_request(_request("confirm"))
        self.assertEqual(confirm_turn.result_type, "no_pending_operation")
        self.assertIn("no pending operation", confirm_turn.result_summary.lower())

        cancel_turn = self.manager.handle_request(_request("cancel"))
        self.assertEqual(cancel_turn.result_type, "no_pending_operation")
        self.assertIn("no pending operation", cancel_turn.result_summary.lower())

    def test_new_persistent_operation_is_blocked_when_one_is_already_pending(self):
        first_turn = self.manager.handle_request(
            _request(
                "decide",
                metadata={
                    "decision_title": "Magic Costs",
                    "decision_body": "Magic always costs something.",
                },
            )
        )
        self.assertEqual(first_turn.result_type, "pending_confirmation")
        pending_id = self.manager.state.pending_operation.operation_id

        write_or_update_note(
            self.vault_root,
            note_type="lore",
            slug="magic_limits",
            title="Magic Limits",
            status="proposed",
            body="Magic has a cost.",
        )
        conflict_turn = self.manager.handle_request(_request("validate lore:magic_limits"))
        self.assertEqual(conflict_turn.result_type, "pending_operation_conflict")
        self.assertIn("confirm or cancel", conflict_turn.result_summary.lower())
        self.assertEqual(self.manager.state.pending_operation.operation_id, pending_id)


def _request(raw_text: str, metadata=None) -> ConversationRequest:
    return ConversationRequest(
        raw_text=raw_text,
        source="user",
        mode="normal",
        interface_language="es",
        user_command_language="es",
        internal_system_language="en",
        project_default_language="es",
        mixed_language_allowed=True,
        artifact_target_language="es",
        explanation_language="es",
        metadata=metadata or {},
    )


if __name__ == "__main__":
    unittest.main()
