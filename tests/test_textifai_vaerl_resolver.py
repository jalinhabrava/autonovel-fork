from pathlib import Path
import tempfile
import unittest

from textifai.vaerl.resolver import resolve_text_against_vault
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIVaERLResolverTests(unittest.TestCase):
    def test_resolver_can_resolve_known_character_and_suggest_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            results = resolve_text_against_vault(
                text="Sera no diría eso nunca",
                vault_path=vault_root,
                known_characters=[{"id": "sera", "names": ["Sera"]}],
            )
            result = results[0]
            self.assertTrue(result.resolved)
            self.assertEqual(result.resolved_entity_id, "sera")
            self.assertEqual(result.related_artifacts_suggested[0].relation, "direct_profile")

    def test_resolver_can_match_lore_by_alias_and_suggest_linked_canon(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"])
                + "\n\n[[magic_costs]]\n"
            )
            (vault_root / "06_Canon" / "Decisions" / "magic_costs.md").write_text(
                note_frontmatter("decision", "Magic Costs", slug="magic_costs") + "\n\n"
            )
            results = resolve_text_against_vault(
                text="El ritual de memoria rompe una regla",
                vault_path=vault_root,
            )
            result = next(item for item in results if item.resolved_entity_id == "memory_ritual")
            self.assertTrue(result.resolved)
            self.assertEqual(result.candidate_entities[0].match_source, "alias")
            self.assertTrue(any(s.artifact_id == "magic_costs" for s in result.related_artifacts_suggested))

    def test_resolver_prefers_candidates_over_false_certainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "ritual_notes.md").write_text(
                note_frontmatter("lore", "Ritual Notes", slug="ritual_notes", aliases=["ritual"])
                + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual"])
                + "\n\n"
            )
            results = resolve_text_against_vault(
                text="Lo del ritual se pisa aquí",
                vault_path=vault_root,
            )
            ritual_result = next(item for item in results if item.mention.normalized_text == "ritual")
            self.assertFalse(ritual_result.resolved)
            self.assertGreaterEqual(len(ritual_result.candidate_entities), 2)


if __name__ == "__main__":
    unittest.main()
