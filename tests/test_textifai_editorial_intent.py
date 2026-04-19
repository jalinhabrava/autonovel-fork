from pathlib import Path
import tempfile
import unittest

from textifai.author_understanding.contracts import AuthorIntentInterpretation
from textifai.conversation.state import create_conversation_state
from textifai.editorial.entity_resolution import resolve_entities
from textifai.editorial_intent.classifier import classify_editorial_intent
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIEditorialIntentTests(unittest.TestCase):
    def test_classifier_prioritizes_author_understanding_over_surface_wording(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            raw_text = "hazlo más claro"
            entity_results = resolve_entities(text=raw_text, vault_path=vault_root)
            author_understanding = AuthorIntentInterpretation(
                primary_intent_type="structuring_request",
                confidence=0.94,
                author_goal_signals=["structure_scene"],
                preserve_signals=["preserve_validated_canon"],
                change_signals=["structure_scene"],
            )
            intent = classify_editorial_intent(
                raw_text=raw_text,
                recognized_intent_name="unknown",
                entity_results=entity_results,
                narrative_signals=None,
                state=None,
                author_understanding=author_understanding,
            )
            self.assertIsNotNone(intent)
            self.assertEqual(intent.request_type, "structuring_request")
            self.assertEqual(intent.semantic_basis, "author_understanding_validated")
            self.assertIn("structure_scene", intent.editorial_goals)

    def test_classifier_marks_short_followup_as_contextual_and_reuses_recent_lore_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            state = state.__class__(**{**state.__dict__, "last_target_type": "lore", "last_target_id": "magic_limits"})
            entity_results = resolve_entities(text="continuemos", vault_path=vault_root)
            intent = classify_editorial_intent(
                raw_text="continuemos",
                recognized_intent_name="validate_artifact",
                entity_results=entity_results,
                narrative_signals=None,
                state=state,
            )
            self.assertIsNotNone(intent)
            self.assertEqual(intent.request_type, "contextual_followup")
            self.assertEqual(intent.followup_mode, "reuse_recent_target")

    def test_classifier_prefers_candidate_targets_when_the_project_alias_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"]) + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "ritual_notes.md").write_text(
                note_frontmatter("lore", "Ritual Notes", slug="ritual_notes", aliases=["ritual"]) + "\n\n"
            )
            entity_results = resolve_entities(text="ritual", vault_path=vault_root)
            intent = classify_editorial_intent(
                raw_text="ritual",
                recognized_intent_name="unknown",
                entity_results=entity_results,
                narrative_signals=None,
                state=None,
            )
            self.assertIsNotNone(intent)
            self.assertEqual(intent.request_type, "contextual_followup")
            self.assertEqual(intent.followup_mode, "prefer_candidate_targets")
            self.assertTrue(intent.candidate_targets)
            self.assertEqual(intent.candidate_targets[0].target_type, "lore")


if __name__ == "__main__":
    unittest.main()
