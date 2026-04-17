import tempfile
import unittest
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.context_commands import (
    build_chapter_context,
    build_find_context,
    build_load_context,
    build_scene_context,
    build_world_context,
)
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class InteractiveContextTests(unittest.TestCase):
    def test_world_context_returns_context_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="kankan",
                title="Kankan",
                status="validated",
                body="The kankan channels memory through touch.",
            )
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="dec_kankan_014",
                title="Kankan Decision",
                status="validated",
                body="The kankan also transmits emotion.",
            )

            payload = build_world_context(VaultProjectAdapter(vault_root))

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["scope"], "world")
            self.assertIn("kankan", payload["lore_refs"])
            self.assertIn("dec_kankan_014", payload["canon_refs"])

    def test_find_context_returns_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                status="proposed",
                body="Sera suspects Ren is hiding something.",
            )

            payload = build_find_context(VaultProjectAdapter(vault_root), "Sera")

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["scope"], "find")
            self.assertGreaterEqual(len(payload.get("matches", [])), 1)

    def test_scene_context_infers_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(vault_root, note_type="character", slug="sera", title="Sera", body="Lead.")
            write_or_update_note(vault_root, note_type="character", slug="ren", title="Ren", body="Support.")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="sundrael_bond",
                title="Sundrael Bond",
                body="A dangerous bond.",
            )
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="dec_sundrael_003",
                title="Sundrael Decision",
                body="The bond prioritizes emotional transmission.",
            )
            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="scene_054_b",
                title="Scene 54B",
                body="POV: Sera\nSera confronts Ren about the Sundrael Bond and dec_sundrael_003.",
                metadata={"chapter": 54},
            )

            payload = build_scene_context(VaultProjectAdapter(vault_root), "scene_054_b")

            self.assertEqual(payload["scope"], "scene")
            self.assertEqual(payload["target_id"], "scene_054_b")
            self.assertEqual(payload["pov"], "Sera")
            self.assertIn("Sera", payload["characters"])
            self.assertIn("Ren", payload["characters"])
            self.assertIn("sundrael_bond", payload["lore_refs"])
            self.assertIn("dec_sundrael_003", payload["canon_refs"])
            self.assertIn("ch_54", payload["chapter_refs"])

    def test_chapter_context_resolves_scene_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(vault_root, note_type="character", slug="sera", title="Sera", body="Lead.")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="kankan",
                title="Kankan",
                body="The kankan is central to the region.",
            )
            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="scene_001_a",
                title="Scene 1A",
                body="POV: Sera\nSera studies the kankan before dawn.",
                metadata={"chapter": 1},
            )
            chapter_path = vault_root / "05_Draft" / "Chapters" / "ch_01.md"
            chapter_path.write_text("# Chapter One\n\nSera crosses the market carrying a kankan token.")

            payload = build_chapter_context(VaultProjectAdapter(vault_root), "ch_01")

            self.assertEqual(payload["scope"], "chapter")
            self.assertEqual(payload["target_id"], "ch_01")
            self.assertEqual(payload["pov"], "Sera")
            self.assertIn("Sera", payload["characters"])
            self.assertIn("kankan", payload["lore_refs"])
            self.assertEqual(payload["chapter_refs"], ["ch_01"])

    def test_load_context_combines_explicit_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(vault_root, note_type="character", slug="sera", title="Sera", body="Lead.")
            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="scene_001_a",
                title="Scene 1A",
                body="POV: Sera\nSera returns to the harbor.",
                metadata={"chapter": 1},
            )
            chapter_path = vault_root / "05_Draft" / "Chapters" / "ch_01.md"
            chapter_path.write_text("# Chapter One\n\nSera returns home.")

            payload = build_load_context(
                VaultProjectAdapter(vault_root),
                artifacts=["world"],
                scene_ids=["scene_001_a"],
                chapter_ids=["ch_01"],
            )

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["scope"], "load")
            self.assertIn("Sera", payload["characters"])
            self.assertIn("ch_01", payload["chapter_refs"])


if __name__ == "__main__":
    unittest.main()
