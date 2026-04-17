import tempfile
import unittest
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.persistence_commands import consistency_check, create_note, decide, reject, update_note, validate
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class InteractivePersistenceTests(unittest.TestCase):
    def test_decide_persists_decision_canon_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")

            result = decide(
                vault_root,
                {
                    "type": "decision_canon",
                    "state": "validated",
                    "title": "El kankan en Sundrael prioriza transmision emocional",
                    "body": "La evidencia de capitulos 12 y 13 favorece esta lectura.",
                    "affects": ["Liora", "Nael", "Kankan"],
                    "origin": {
                        "source": "interactive_cli",
                        "chapter_ids": ["ch_12", "ch_13"],
                        "user_action": "validated_from_chat",
                    },
                },
            )

            self.assertEqual(result["type"], "decision_canon")
            self.assertEqual(result["state"], "validated")
            decision_path = vault_root / "06_Canon" / "Decisions" / "el_kankan_en_sundrael_prioriza_transmision_emocional.md"
            self.assertTrue(decision_path.exists())
            text = decision_path.read_text()
            self.assertIn("status: validated", text)
            self.assertIn("source: interactive_cli", text)
            self.assertIn("chapter_ids: ch_12,ch_13", text)
            self.assertIn("affects: Liora,Nael,Kankan", text)

    def test_validate_updates_existing_artifact_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                status="proposed",
                body="Working profile.",
            )

            result = validate(
                vault_root,
                {
                    "type": "artifact_state_change",
                    "target_type": "character",
                    "target_id": "sera",
                    "state": "validated",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertEqual(result["state"], "validated")
            text = (vault_root / "03_Characters" / "Profiles" / "sera.md").read_text()
            self.assertIn("status: validated", text)

    def test_reject_updates_existing_artifact_and_hides_from_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="sundrael_bond",
                title="Sundrael Bond",
                status="pending_revision",
                body="A disputed lore note.",
            )

            result = reject(
                vault_root,
                {
                    "type": "artifact_state_change",
                    "target_type": "lore",
                    "target_id": "sundrael_bond",
                    "state": "rejected",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertEqual(result["state"], "rejected")
            text = (vault_root / "02_World" / "Lore" / "sundrael_bond.md").read_text()
            self.assertIn("status: rejected", text)

            world = VaultProjectAdapter(vault_root).read_artifact("world")
            self.assertNotIn("Sundrael Bond", world)

    def test_consistency_check_blocks_out_of_context_magic_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="magic_limits",
                title="Magic Limits",
                status="validated",
                body="Magic always has a cost and a strict limit.",
            )

            report = consistency_check(
                vault_root,
                {
                    "type": "artifact_payload",
                    "artifact_type": "lore",
                    "entity_id": "ultimate_spell",
                    "title": "Ultimate Spell",
                    "body": "This spell makes the caster invincible and works without cost.",
                    "state": "proposed",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertFalse(report["ok"])
            self.assertGreaterEqual(len(report["issues"]), 1)
            self.assertEqual(report["issues"][0]["blocking"], True)

    def test_create_note_writes_when_consistency_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")

            result = create_note(
                vault_root,
                {
                    "type": "artifact_payload",
                    "artifact_type": "lore",
                    "entity_id": "harbor_customs",
                    "title": "Harbor Customs",
                    "body": "Merchants exchange brass tokens before sunrise.",
                    "state": "proposed",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertEqual(result["status"], "written")
            note_path = vault_root / "02_World" / "Lore" / "harbor_customs.md"
            self.assertTrue(note_path.exists())

    def test_create_note_is_blocked_when_verify_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="decision",
                slug="magic_bounds",
                title="Magic Bounds",
                status="validated",
                body="No school of magic grants invincible or costless power.",
            )

            result = create_note(
                vault_root,
                {
                    "type": "artifact_payload",
                    "artifact_type": "scene",
                    "entity_id": "scene_999_a",
                    "title": "Scene 999A",
                    "body": "The ritual makes Sera invincible without cost.",
                    "state": "pending_revision",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertEqual(result["status"], "blocked")
            self.assertFalse((vault_root / "04_Outline" / "Scenes" / "scene_999_a.md").exists())

    def test_update_note_updates_existing_when_verify_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                status="proposed",
                body="A wary protagonist.",
            )

            result = update_note(
                vault_root,
                {
                    "type": "artifact_payload",
                    "artifact_type": "character",
                    "entity_id": "sera",
                    "title": "Sera",
                    "body": "A wary protagonist with a sharper sense of duty.",
                    "state": "pending_revision",
                    "origin": {"source": "interactive_cli"},
                },
            )

            self.assertEqual(result["status"], "written")
            text = (vault_root / "03_Characters" / "Profiles" / "sera.md").read_text()
            self.assertIn("sharper sense of duty", text)


if __name__ == "__main__":
    unittest.main()
