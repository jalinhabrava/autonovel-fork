import tempfile
import unittest
from pathlib import Path

from interactive.context_commands import build_chapter_context, build_find_context, build_load_context, build_scene_context, build_world_context, debug_context
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

            payload = build_world_context(str(vault_root))

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["scope"]["narrative_scope"], "project")
            ids = [entry["id"] for entry in payload["hard_constraints"] + payload["narrative_context"]]
            self.assertIn("kankan", ids)
            self.assertIn("dec_kankan_014", ids)

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

            payload = build_find_context(str(vault_root), "Sera")

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["intent"], "context_search")
            self.assertGreaterEqual(len(payload["narrative_context"]) + len(payload["evidence"]), 1)

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

            payload = build_scene_context(str(vault_root), "scene_054_b")

            self.assertEqual(payload["scope"]["narrative_scope"], "scene")
            self.assertEqual(payload["scope"]["target_id"], "scene_054_b")
            self.assertIn("ch_54", payload["scope"]["chapter_refs"])
            joined = " ".join(entry["content"] for entry in payload["hard_constraints"] + payload["narrative_context"])
            self.assertIn("Sera", joined)
            self.assertIn("sundrael bond", joined.lower())

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

            payload = build_chapter_context(str(vault_root), "ch_01")

            self.assertEqual(payload["scope"]["narrative_scope"], "chapter")
            self.assertEqual(payload["scope"]["target_id"], "ch_01")
            self.assertEqual(list(payload["scope"]["chapter_refs"]), ["ch_01"])
            evidence_text = " ".join(entry["content"] for entry in payload["evidence"] + payload["narrative_context"])
            self.assertIn("Sera", evidence_text)
            self.assertIn("kankan", evidence_text.lower())

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
                str(vault_root),
                artifacts=["world"],
                scene_ids=["scene_001_a"],
                chapter_ids=["ch_01"],
            )

            self.assertEqual(payload["type"], "context_pack")
            self.assertEqual(payload["scope"]["target_id"], "scene_001_a")
            self.assertIn("ch_01", payload["scope"]["chapter_refs"])
            text = " ".join(entry["content"] for entry in payload["narrative_context"] + payload["evidence"])
            self.assertIn("Sera", text)

    def test_context_debug_returns_request_candidates_and_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="dec_magic_cost",
                title="Magic Cost",
                status="validated",
                body="Every spell has a cost.",
            )

            payload = debug_context(
                str(vault_root),
                intent="consistency_check",
                narrative_scope="fragment",
                retrieval_scope=["canon", "lore", "voice", "characters"],
                target_id="test_target",
                target_type="scene",
                policy="strict_canon",
                token_budget=2500,
                debug_mode="summary",
                max_candidates=5,
            )

            self.assertEqual(payload["resolved_intent"]["name"], "consistency_check")
            self.assertEqual(payload["policy"]["name"], "strict_canon")
            self.assertLessEqual(len(payload["candidates"]), 5)
            self.assertEqual(payload["context_pack"]["type"], "context_pack")


if __name__ == "__main__":
    unittest.main()
