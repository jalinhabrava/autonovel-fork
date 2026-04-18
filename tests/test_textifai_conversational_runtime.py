import tempfile
import unittest
from pathlib import Path

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

    def test_runtime_bridge_routes_natural_review_request_into_editorial_structuring(self):
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

            response = handle_conversational_runtime_input(
                session,
                "no me gusta esta escena porque Sera no diría eso nunca",
            )

            self.assertIn("needs a concrete narrative passage", response)
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

    def test_runtime_bridge_handles_followthrough_validation_and_narration_handoff(self):
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
            response = handle_conversational_runtime_input(
                session,
                "Sera llega tarde al puerto, Toma la acusa de mentir y ella revela que perdió el mapa",
            )
            self.assertIn("Prepared editorial structure", response)
            validated = handle_conversational_runtime_input(session, "valido esta estructura")
            self.assertIn("Validated structured editorial state", validated)
            narration = handle_conversational_runtime_input(session, "déjalo listo para narrar")
            self.assertIn("Prepared narration handoff", narration)

    def test_runtime_bridge_treats_prepare_without_execution_as_editorial_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(Path(tmp))
            response = handle_conversational_runtime_input(session, "todavía no lo escribas, pero sí déjalo preparado")
            self.assertNotIn("could not map", response)
            self.assertNotIn("noop", response.lower())
            self.assertTrue(
                any(
                    phrase in response.lower()
                    for phrase in (
                        "clarif",
                        "prepare",
                        "narrat",
                        "estructura",
                    )
                )
            )


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
