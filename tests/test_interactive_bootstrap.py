import tempfile
import unittest
from pathlib import Path

from interactive.bootstrap_extract import extract_canon, extract_characters, extract_timeline, extract_voice
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class InteractiveBootstrapTests(unittest.TestCase):
    def test_extract_voice_updates_root_artifact_with_bootstrap_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text(
                "# Chapter One\n\nSera walked through the cold harbor. She counted each bell and touched the wet stone."
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_02.md").write_text(
                "# Chapter Two\n\nShe watched the light break over the salt water and kept her fear quiet."
            )

            result = extract_voice(vault_root, chapter_ids=["ch_01", "ch_02"])

            self.assertEqual(result["status"], "written")
            voice_text = (vault_root / "01_Voice" / "Voice.md").read_text()
            self.assertIn("status: pending_revision", voice_text)
            self.assertIn("source: manuscript_bootstrap", voice_text)
            self.assertIn("chapter_ids: ch_01,ch_02", voice_text)
            self.assertIn("## Preset Reference", voice_text)
            self.assertIn("## Project Overrides", voice_text)
            self.assertIn("## Manuscript Signals", voice_text)

    def test_extract_characters_creates_character_notes_with_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text(
                "# Chapter One\n\nSera met Ren at the gate. Sera asked Ren to wait."
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_02.md").write_text(
                "# Chapter Two\n\nRen warned Sera about the bell tower. Sera ignored Ren."
            )

            results = extract_characters(vault_root)

            self.assertGreaterEqual(len(results), 2)
            sera_text = (vault_root / "03_Characters" / "Profiles" / "sera.md").read_text()
            self.assertIn("source: manuscript_bootstrap", sera_text)
            self.assertIn("chapter_ids: ch_01,ch_02", sera_text)
            self.assertIn("## Character Voice Layer", sera_text)

    def test_extract_canon_creates_proposed_decision_with_explicit_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            (vault_root / "05_Draft" / "Chapters" / "ch_03.md").write_text(
                "# Chapter Three\n\nThe bond always costs memory. No rite can avoid that price."
            )

            results = extract_canon(vault_root, chapter_ids=["ch_03"])

            self.assertGreaterEqual(len(results), 1)
            decision_files = list((vault_root / "06_Canon" / "Decisions").glob("*.md"))
            self.assertTrue(decision_files)
            text = decision_files[0].read_text()
            self.assertIn("source: manuscript_bootstrap", text)
            self.assertIn("canon_source: extracted_proposal", text)
            self.assertIn("It is not a validated canon decision", text)
            self.assertIn("## Evidence", text)
            self.assertIn("ch_03", text)

    def test_extract_timeline_persists_provisional_lore_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            (vault_root / "05_Draft" / "Chapters" / "ch_04.md").write_text(
                "# Chapter Four\n\nAt dawn the market reopened after the storm."
            )

            results = extract_timeline(vault_root, chapter_ids=["ch_04"])

            self.assertEqual(len(results), 1)
            lore_text = (vault_root / "02_World" / "Lore" / "timeline_ch_04.md").read_text()
            self.assertIn("timeline_model: provisional_lore_note", lore_text)
            self.assertIn("source: manuscript_bootstrap", lore_text)
            self.assertIn("not yet the definitive timeline model", lore_text)

    def test_bootstrap_prefers_new_proposal_overwriting_validated_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                status="validated",
                body="Validated profile.",
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text(
                "# Chapter One\n\nSera challenged the council. Sera refused to kneel."
            )

            results = extract_characters(vault_root, chapter_ids=["ch_01"])

            proposal_paths = [Path(result["path"]) for result in results if result["target_id"].startswith("sera__bootstrap__")]
            self.assertTrue(proposal_paths)
            self.assertIn("status: validated", (vault_root / "03_Characters" / "Profiles" / "sera.md").read_text())

    def test_bootstrap_does_not_update_pending_root_voice_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            voice_path = vault_root / "01_Voice" / "Voice.md"
            voice_path.write_text(
                "---\nkind: voice\ntitle: Voice\nstatus: pending_revision\nschema_version: 1.0\n---\n\n# Voice\n\nExisting work.\n"
            )
            (vault_root / "05_Draft" / "Chapters" / "ch_01.md").write_text(
                "# Chapter One\n\nSera walked with deliberate calm."
            )

            result = extract_voice(vault_root, chapter_ids=["ch_01"])

            self.assertEqual(result["status"], "skipped")
            self.assertIn("pending_revision_root_artifact", result["reason"])


if __name__ == "__main__":
    unittest.main()
