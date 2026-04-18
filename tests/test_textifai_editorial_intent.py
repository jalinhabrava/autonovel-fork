from pathlib import Path
import tempfile
import unittest

from textifai.conversation.state import create_conversation_state
from textifai.editorial.entity_resolution import resolve_entities
from textifai.editorial_intent.classifier import classify_editorial_intent
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIEditorialIntentTests(unittest.TestCase):
    def test_classifier_distinguishes_structuring_request_from_narrative_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            raw_text = "Estos son los hechos de la escena; quiero convertirlos en una estructura clara y luego dejarla lista para narrar."
            entity_results = resolve_entities(text=raw_text, vault_path=vault_root)
            intent = classify_editorial_intent(
                raw_text=raw_text,
                recognized_intent_name="unknown",
                entity_results=entity_results,
                narrative_signals=None,
                state=None,
            )
            self.assertIsNotNone(intent)
            self.assertEqual(intent.request_type, "mixed_editorial_request")
            self.assertIn("prepare_for_narration", intent.editorial_goals)
            self.assertIsNone(intent.metadata["narrative_source_text"])

    def test_classifier_marks_this_note_as_contextual_followup_and_reuses_recent_lore_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            state = state.__class__(**{**state.__dict__, "last_target_type": "lore", "last_target_id": "magic_limits"})
            entity_results = resolve_entities(text="esta nota", vault_path=vault_root)
            intent = classify_editorial_intent(
                raw_text="esta nota",
                recognized_intent_name="validate_artifact",
                entity_results=entity_results,
                narrative_signals=None,
                state=state,
            )
            self.assertIsNotNone(intent)
            self.assertEqual(intent.request_type, "contextual_followup")
            self.assertEqual(intent.followup_mode, "reuse_recent_target")

    def test_classifier_prefers_candidates_for_lo_del_ritual(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"]) + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "ritual_notes.md").write_text(
                note_frontmatter("lore", "Ritual Notes", slug="ritual_notes", aliases=["ritual"]) + "\n\n"
            )
            entity_results = resolve_entities(text="lo del ritual", vault_path=vault_root)
            intent = classify_editorial_intent(
                raw_text="lo del ritual",
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
