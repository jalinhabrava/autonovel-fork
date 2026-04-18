import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from textifai.conversation.runtime_bridge import build_conversation_request, handle_conversational_runtime_input
from textifai.conversation.state import create_conversation_state
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class TextifAIConversationalRuntimeTests(unittest.TestCase):
    def test_build_request_includes_known_characters_and_recent_target_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            write_or_update_note(
                session.vault_path,
                note_type="character",
                slug="sera",
                title="Sera",
                body="A stubborn courier.",
                status="validated",
            )
            session.conversation_state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            session.conversation_state = session.conversation_state.__class__(
                **{
                    **session.conversation_state.__dict__,
                    "last_target_type": "scene",
                    "last_target_id": "scene_054_b",
                }
            )

            request = build_conversation_request(session, "no me gusta esta escena porque Sera no diría eso nunca")

            self.assertIsNone(request.target_hint)
            self.assertEqual(request.metadata["known_characters"][0]["id"], "sera")

    def test_runtime_bridge_uses_recent_scene_context_for_natural_review_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            write_or_update_note(
                session.vault_path,
                note_type="character",
                slug="sera",
                title="Sera",
                body="A stubborn courier.",
                status="validated",
            )
            session.conversation_state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            session.conversation_state = session.conversation_state.__class__(
                **{
                    **session.conversation_state.__dict__,
                    "last_target_type": "scene",
                    "last_target_id": "scene_054_b",
                }
            )

            with patch(
                "textifai.conversation.executor.build_scene_context",
                return_value={
                    "intent": "scene_context",
                    "scope": {"target_id": "scene_054_b"},
                    "policy": {"name": "default"},
                    "hard_constraints": [],
                    "narrative_context": [],
                    "voice_context": {"project_voice": [], "character_voice": []},
                    "evidence": [],
                },
            ), patch(
                "textifai.conversation.executor.build_scene_request",
                return_value=SimpleNamespace(
                    intent="scene_context",
                    target_id="scene_054_b",
                    target_type="scene",
                    narrative_scope="scene",
                    retrieval_scope=["scene"],
                    query_text=None,
                    chapter_refs=[],
                    character_ids=[],
                    policy_name="default",
                    token_budget=4000,
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    operation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                ),
            ):
                response = handle_conversational_runtime_input(
                    session,
                    "no me gusta esta escena porque Sera no diría eso nunca",
                )

            self.assertIn("scene_054_b", response)
            self.assertIsNotNone(session.conversation_state)

    def test_runtime_bridge_returns_conversational_clarification_for_unknown_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            response = handle_conversational_runtime_input(session, "haz algo imposible y raro con esto")
            self.assertIn("could not map", response)

    def test_runtime_bridge_uses_ok_as_conservative_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            session.conversation_state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            session.conversation_state = session.conversation_state.__class__(
                **{
                    **session.conversation_state.__dict__,
                    "last_target_type": "lore",
                    "last_target_id": "magic_limits",
                }
            )
            response = handle_conversational_runtime_input(session, "valida esta nota")
            self.assertIn("confirm", response.lower())
            confirmed = handle_conversational_runtime_input(session, "ok")
            self.assertIn("magic_limits", confirmed)

    def test_runtime_bridge_handles_natural_cancel_phrase_when_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            session.conversation_state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            session.conversation_state = session.conversation_state.__class__(
                **{
                    **session.conversation_state.__dict__,
                    "last_target_type": "lore",
                    "last_target_id": "magic_limits",
                }
            )
            handle_conversational_runtime_input(session, "valida esta nota")
            cancelled = handle_conversational_runtime_input(session, "mejor no, cancélalo")
            self.assertIn("Cancelled pending operation", cancelled)

    def test_runtime_bridge_marks_natural_bootstrap_as_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            response = handle_conversational_runtime_input(session, "haz bootstrap del canon de los capítulos 1 a 3")
            self.assertIn("not supported yet", response)


def _make_session(base_dir: Path):
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
    write_or_update_note(
        vault_root,
        note_type="lore",
        slug="magic_limits",
        title="Magic Limits",
        body="Magic costs blood or memory. No exceptions.",
        status="proposed",
    )
    return create_session(load_runtime_environment(base_dir))


if __name__ == "__main__":
    unittest.main()
