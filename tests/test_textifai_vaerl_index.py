from pathlib import Path
import tempfile
import unittest

from textifai.vaerl.index import build_vault_index
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIVaERLIndexTests(unittest.TestCase):
    def test_vault_index_collects_titles_slugs_aliases_links_and_backlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"])
                + "\n\n[[magic_costs]]\n"
            )
            (vault_root / "06_Canon" / "Decisions" / "magic_costs.md").write_text(
                note_frontmatter("decision", "Magic Costs", slug="magic_costs") + "\n\n[[memory_ritual]]\n"
            )
            entries = build_vault_index(
                vault_path=vault_root,
                known_characters=[{"id": "sera", "names": ["Sera"]}],
            )
            lore_entry = next(entry for entry in entries if entry.artifact_id == "memory_ritual")
            self.assertIn("ritual de memoria", lore_entry.aliases)
            self.assertIn("magic_costs", lore_entry.links)
            self.assertIn("magic_costs", lore_entry.backlinks)

    def test_vault_index_only_promotes_canonical_subject_into_confirmed_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "99_Import_Staging" / "characters").mkdir(parents=True, exist_ok=True)
            (vault_root / "99_Import_Staging" / "characters" / "sera_group_note.md").write_text(
                note_frontmatter(
                    "character",
                    "Sera Group Note",
                    slug="sera_group_note",
                    canonical_subject="Sera",
                    character_refs="Sera,Ren",
                )
                + "\n\nSera keeps her hard edge.\n",
                encoding="utf-8",
            )

            entries = build_vault_index(vault_path=vault_root)
            sera_entry = next(entry for entry in entries if entry.artifact_id == "sera_group_note")

            self.assertIn("Sera", sera_entry.project_confirmed_aliases)
            self.assertNotIn("Ren", sera_entry.project_confirmed_aliases)

    def test_related_subjects_do_not_become_alias_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Places" / "sundrael.md").write_text(
                note_frontmatter(
                    "location",
                    "Sundraël",
                    slug="sundrael",
                    related_subjects="Sera,Ren",
                )
                + "\n\n[[sera]]\n",
                encoding="utf-8",
            )

            entries = build_vault_index(vault_path=vault_root)
            place_entry = next(entry for entry in entries if entry.artifact_id == "sundrael")

            self.assertNotIn("Sera", place_entry.aliases)


if __name__ == "__main__":
    unittest.main()
