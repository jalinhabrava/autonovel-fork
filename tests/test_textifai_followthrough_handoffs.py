import tempfile
import unittest
from pathlib import Path

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.manager import ConversationManager
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.state import create_conversation_state
from textifai.editorial.contracts import BeatItem, BeatOutline, EditorialStructuringResult, StoryFactItem, StoryFacts
from textifai.followthrough.narration_handoff import build_narration_request
from textifai.followthrough.review_handoff import build_review_ready_package
from textifai.followthrough.validation import build_validated_structuring_state
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class TextifAIFollowThroughHandoffTests(unittest.TestCase):
    def test_narration_request_uses_closed_defaults(self):
        source_result = _make_structuring_result()
        state = build_validated_structuring_state(source_result, validated_by_user=True)
        request = build_narration_request(validated_structuring_state=state, target_language="ja")
        self.assertEqual(request.voice_mode, "inherit_project_voice")
        self.assertEqual(request.continuity_scope, "scene_only")
        self.assertEqual(request.canon_mode, "validated_plus_related")

    def test_review_ready_package_derives_focus_and_related_artifacts(self):
        source_result = _make_structuring_result()
        state = build_validated_structuring_state(source_result, validated_by_user=True)
        package = build_review_ready_package(validated_structuring_state=state)
        self.assertIn("structure", package.review_focus)
        self.assertTrue(package.preserve_constraints)

    def test_manager_validates_structure_then_prepares_narration_then_review_and_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                body="A stubborn courier.",
                status="validated",
            )
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="toma",
                title="Toma",
                body="A cautious gatekeeper.",
                status="validated",
            )
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

            first_turn = manager.handle_request(
                ConversationRequest(
                    raw_text="Sera llega tarde al puerto, Toma la acusa de mentir y ella revela que perdió el mapa",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                    metadata={
                        "known_characters": [
                            {"id": "sera", "names": ["Sera"]},
                            {"id": "toma", "names": ["Toma"]},
                        ]
                    },
                )
            )
            self.assertEqual(first_turn.result_type, "editorial_structuring")

            validate_turn = manager.handle_request(
                ConversationRequest(
                    raw_text="valido esta estructura",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                )
            )
            self.assertEqual(validate_turn.result_type, "followthrough")
            self.assertEqual(session.last_result["type"], "followthrough")
            validated_state = session.last_result["data"]["validated_structuring_state"]
            self.assertEqual(validated_state["validation_status"], "validated")

            narration_turn = manager.handle_request(
                ConversationRequest(
                    raw_text="déjalo listo para narrar",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                )
            )
            self.assertEqual(narration_turn.result_type, "followthrough")
            self.assertEqual(session.last_result["data"]["narration_request"]["voice_mode"], "inherit_project_voice")
            self.assertIsNotNone(session.last_result["data"]["narration_prep"])

            review_turn = manager.handle_request(
                ConversationRequest(
                    raw_text="déjalo listo para revisión",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                )
            )
            self.assertEqual(review_turn.result_type, "followthrough")
            self.assertIsNotNone(session.last_result["data"]["review_ready_package"])

            followup_turn = manager.handle_request(
                ConversationRequest(
                    raw_text="sí, esa",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                )
            )
            self.assertEqual(followup_turn.result_type, "followthrough")
def _make_structuring_result() -> EditorialStructuringResult:
    facts = StoryFacts(
        source_text="Sera llega tarde al puerto.",
        language="es",
        characters_involved=["sera"],
        locations_involved=[],
        objects_involved=[],
        premise="Sera llega tarde al puerto.",
        core_conflict=None,
        goals=["llegar al puerto"],
        constraints=[],
        canon_constraints=["respect_validated_canon"],
        explicit_facts=[StoryFactItem(text="Sera llega tarde al puerto.", fact_kind="event", source="explicit_input")],
        inferred_facts=[],
        open_questions=[],
    )
    outline = BeatOutline(
        source_kind="story_facts",
        title="Sera llega tarde al puerto.",
        beats=[
            BeatItem(
                index=1,
                summary="Sera llega tarde al puerto.",
                purpose="advance_scene",
                characters=["sera"],
                tension_level="low",
            )
        ],
        emotional_arc=["low"],
        target_language="ja",
        continuity_notes=[],
        canon_checks=["respect_validated_canon"],
    )
    return EditorialStructuringResult(
        entity_resolution_results=[],
        story_facts=facts,
        beat_outline=outline,
        revision_intent=None,
        narration_prep=None,
        result_kind="beat_outline",
        ready_for_validation=True,
    )


if __name__ == "__main__":
    unittest.main()
