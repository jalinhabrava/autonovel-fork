from pathlib import Path
import tempfile
import unittest

from textifai.conversation.contracts import NarrativeSignals
from textifai.editorial.entity_resolution import resolve_entities
from textifai.editorial.narration_prep import build_narration_prep
from textifai.editorial.structuring import (
    build_beat_outline,
    build_editorial_structuring_result,
    build_revision_intent,
    build_story_facts,
)
from vault.bootstrap import bootstrap_vault


class TextifAIEditorialStructuringTests(unittest.TestCase):
    def test_story_facts_and_beat_outline_build_from_linear_scene_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            entity_results = resolve_entities(
                text="Sera llega tarde al puerto, Toma la acusa de mentir, ella revela que perdió el mapa",
                vault_path=vault_root,
                known_characters=[
                    {"id": "sera", "names": ["Sera"]},
                    {"id": "toma", "names": ["Toma"]},
                ],
            )
            facts = build_story_facts(
                source_text="Sera llega tarde al puerto, Toma la acusa de mentir, ella revela que perdió el mapa",
                language="es",
                entity_results=entity_results,
                narrative_signals=None,
            )
            outline = build_beat_outline(story_facts=facts, target_language="ja")
            self.assertEqual(facts.characters_involved, ["sera", "toma"])
            self.assertEqual(len(facts.explicit_facts), 3)
            self.assertEqual(len(outline.beats), 3)
            self.assertEqual(outline.beats[0].tension_level, "low")

    def test_revision_intent_builds_from_editorial_critique(self):
        revision = build_revision_intent(
            source_text="La escena funciona hasta que Sera acepta demasiado rápido; quiero que el conflicto dure más",
            narrative_signals=NarrativeSignals(
                mentioned_entities=["Sera"],
                mentioned_character_ids=["sera"],
                issue_types=["continuity_issue"],
                constraint_hints=["check_recent_continuity"],
                confidence=0.8,
            ),
            target_hint="scene_054_b",
        )
        self.assertIsNotNone(revision)
        self.assertEqual(revision.target_hint, "scene_054_b")
        self.assertTrue(revision.desired_changes)

    def test_editorial_structuring_result_can_build_narration_prep(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            entity_results = resolve_entities(
                text="Sera llega tarde al puerto y rompe una regla del canon",
                vault_path=vault_root,
                known_characters=[{"id": "sera", "names": ["Sera"]}],
            )
            result = build_editorial_structuring_result(
                source_text="Sera llega tarde al puerto y rompe una regla del canon",
                language="es",
                entity_results=entity_results,
                narrative_signals=NarrativeSignals(
                    mentioned_entities=["Sera"],
                    mentioned_character_ids=["sera"],
                    issue_types=["canon_issue"],
                    constraint_hints=["check_validated_canon"],
                    confidence=0.82,
                ),
                artifact_target_language="ja",
            )
            prep = build_narration_prep(
                target_language="ja",
                explanation_language="es",
                entity_results=entity_results,
                beat_outline=result.beat_outline,
                story_facts=result.story_facts,
                revision_intent=result.revision_intent,
            )
            self.assertEqual(prep.target_language, "ja")
            self.assertIn("canon", prep.canon_artifacts)
            self.assertIsNotNone(result.story_facts)

    def test_structuring_request_without_narrative_source_text_does_not_create_fake_facts(self):
        result = build_editorial_structuring_result(
            source_text="",
            language="es",
            entity_results=[],
            narrative_signals=None,
            artifact_target_language="ja",
        )
        self.assertEqual(result.story_facts.explicit_facts, [])
        self.assertIsNone(result.story_facts.premise)
        self.assertEqual(result.story_facts.open_questions, ["Need clearer narrative facts from the author input."])
        self.assertIsNone(result.beat_outline)


if __name__ == "__main__":
    unittest.main()
