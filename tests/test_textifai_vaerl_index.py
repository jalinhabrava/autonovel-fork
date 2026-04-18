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


if __name__ == "__main__":
    unittest.main()
