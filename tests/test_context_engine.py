import tempfile
import unittest
from pathlib import Path

from context_engine.contracts import ContextRequest
from context_engine.service import build_context_pack
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class ContextEngineTests(unittest.TestCase):
    def test_scene_rewrite_context_pack_separates_sections(self):
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
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="harbor_law",
                title="Harbor Law",
                status="validated",
                body="The harbor closes at dawn.",
            )
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                status="pending_revision",
                body="# Sera\n\n## Character Voice Layer\n\n- clipped, precise answers under stress",
            )
            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="scene_001_a",
                title="Scene 1A",
                status="pending_revision",
                body="POV: Sera\nThe harbor opens before dawn.",
                metadata={"chapter": 1},
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text(
                "# Chapter One\n\nSera enters the harbor and prepares a costly spell."
            )
            (vault_root / "01_Voice" / "Voice.md").write_text(
                "---\nkind: voice\ntitle: Project Voice\nstatus: pending_revision\nschema_version: 1.0\n---\n\n# Project Voice\n\nKeep narration concrete and tactile.\n"
            )

            pack = build_context_pack(
                str(vault_root),
                ContextRequest(
                    intent="scene_rewrite",
                    target_id="scene_001_a",
                    target_type="scene",
                    character_ids=("sera",),
                    policy_name="default",
                    token_budget=4000,
                ),
            )

            self.assertEqual(pack.type, "context_pack")
            self.assertEqual(pack.scope["narrative_scope"], "scene")
            self.assertIn("canon", pack.scope["retrieval_scope"])
            self.assertGreaterEqual(len(pack.hard_constraints), 1)
            self.assertGreaterEqual(len(pack.narrative_context), 1)
            self.assertGreaterEqual(len(pack.voice_context["project_voice"]), 1)
            self.assertGreaterEqual(len(pack.voice_context["character_voice"]), 1)
            self.assertGreaterEqual(len(pack.evidence), 1)
            self.assertTrue(all(entry.reason for entry in pack.hard_constraints))
            self.assertTrue(all("reason" in entry.score_breakdown for entry in pack.hard_constraints))

    def test_rejected_and_superseded_candidates_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="valid_lore",
                title="Valid Lore",
                status="validated",
                body="This lore should appear.",
            )
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="rejected_lore",
                title="Rejected Lore",
                status="rejected",
                body="This lore should not appear.",
            )
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="superseded_decision",
                title="Old Decision",
                status="superseded",
                body="This canon note should not appear.",
            )

            pack = build_context_pack(
                str(vault_root),
                ContextRequest(
                    intent="world_lookup",
                    target_id="world",
                    target_type="project",
                    policy_name="default",
                    token_budget=4000,
                ),
            )

            contents = " ".join(entry.content for entry in pack.hard_constraints + pack.narrative_context)
            self.assertIn("This lore should appear", contents)
            self.assertNotIn("This lore should not appear", contents)
            self.assertNotIn("This canon note should not appear", contents)

    def test_strict_canon_policy_prioritizes_hard_constraints(self):
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
            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="scene_001_a",
                title="Scene 1A",
                status="pending_revision",
                body="POV: Sera\nA local scene note.",
                metadata={"chapter": 1},
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text("# Chapter One\n\nCostly ritual.")

            pack = build_context_pack(
                str(vault_root),
                ContextRequest(
                    intent="consistency_check",
                    target_id="scene_001_a",
                    target_type="scene",
                    policy_name="strict_canon",
                    token_budget=3000,
                ),
            )

            self.assertGreaterEqual(len(pack.hard_constraints), 1)
            self.assertGreaterEqual(pack.hard_constraints[0].score, pack.narrative_context[0].score if pack.narrative_context else 0)

    def test_literality_is_applied_by_artifact_type_within_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="dec_cost",
                title="Spell Cost",
                status="validated",
                body="Every spell requires breath, blood, or memory, and no rite bypasses that requirement under any circumstance.",
            )
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="market_law",
                title="Market Law",
                status="validated",
                body="The market opens before dawn, closes at noon, and rotates stewards every third day under guild supervision.",
            )

            pack = build_context_pack(
                str(vault_root),
                ContextRequest(
                    intent="world_lookup",
                    target_id="world",
                    target_type="project",
                    policy_name="default",
                    token_budget=4000,
                ),
            )

            hard_by_type = {entry.artifact_type: entry for entry in pack.hard_constraints}
            self.assertIn("decision", hard_by_type)
            self.assertIn("lore", hard_by_type)
            self.assertGreater(
                len(hard_by_type["decision"].content.split()),
                len(hard_by_type["lore"].content.split()),
            )


if __name__ == "__main__":
    unittest.main()
