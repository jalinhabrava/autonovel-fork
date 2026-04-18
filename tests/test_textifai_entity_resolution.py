from pathlib import Path
import tempfile
import unittest

from textifai.editorial.entity_resolution import resolve_entities
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIEntityResolutionCompatibilityTests(unittest.TestCase):
    def test_editorial_wrapper_returns_vaerl_results_with_candidates_and_related_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            lore_path = vault_root / "02_World" / "Lore" / "memory_ritual.md"
            lore_path.write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"])
                + "\n\n[[magic_costs]]\nThe ritual costs memory.\n"
            )
            decision_path = vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
            decision_path.write_text(note_frontmatter("decision", "Magic Costs", slug="magic_costs") + "\n\nMagic has a cost.\n")

            results = resolve_entities(
                text="El ritual de memoria rompe una regla",
                vault_path=vault_root,
                known_characters=[],
            )
            self.assertTrue(results)
            lore_result = next(result for result in results if result.resolved_entity_type == "lore")
            self.assertEqual(lore_result.candidate_entities[0].match_source, "alias")
            self.assertEqual(lore_result.related_artifacts_suggested[0].relation, "direct_note")

    def test_editorial_wrapper_keeps_non_resolution_conservative(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            results = resolve_entities(
                text="Se no diría eso nunca",
                vault_path=vault_root,
                known_characters=[{"id": "sera", "names": ["Sera"]}],
            )
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
