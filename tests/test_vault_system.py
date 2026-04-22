import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.vault_adapter import VaultProjectAdapter
from stores.project_store import ProjectStore
from vault.bootstrap import bootstrap_vault, validate_vault
from vault.ingest import import_existing_chapters, ingest_digested_context
from vault.notes import export_context, write_or_update_note


class VaultSystemTests(unittest.TestCase):
    def test_bootstrap_creates_valid_vault_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")

            errors = validate_vault(vault_root)
            self.assertEqual(errors, [])
            self.assertTrue((vault_root / ".obsidian").exists())
            self.assertTrue((vault_root / "00_Project" / "Project.md").exists())
            self.assertTrue((vault_root / "99_System" / "state.json").exists())

    def test_vault_adapter_reconstructs_world_from_concept_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="concept",
                slug="harmonic-law",
                title="Harmonic Law",
                status="validated",
                body="Specific interval rules go here.",
            )
            write_or_update_note(
                vault_root,
                note_type="concept",
                slug="discarded-note",
                title="Discarded Concept",
                status="rejected",
                body="Should not appear.",
            )

            adapter = VaultProjectAdapter(vault_root)
            world = adapter.read_artifact("world")

            self.assertIn("Concept Notes", world)
            self.assertIn("Harmonic Law", world)
            self.assertNotIn("Discarded Concept", world)

    def test_project_store_can_target_vault_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")

            with patch.dict(
                os.environ,
                {
                    "AUTONOVEL_PROJECT_BACKEND": "vault",
                    "AUTONOVEL_VAULT_ROOT": str(vault_root),
                },
                clear=False,
            ):
                store = ProjectStore(Path(tmp))
                store.write_chapter(1, "# Chapter One\nHello from vault")
                text = store.read_chapter(1)

            self.assertEqual(text, "# Chapter One\nHello from vault")
            self.assertEqual(store.chapter_path(1), vault_root / "04_Story" / "Chapters" / "ch_01.md")

    def test_export_context_all_combines_logical_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="hero",
                title="Hero",
                status="proposed",
                body="A difficult protagonist.",
            )

            payload = export_context(vault_root, "all")
            self.assertIn("# CHARACTERS", payload)
            self.assertIn("Hero", payload)

    def test_import_existing_chapters_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            source_root = Path(tmp) / "source"
            bootstrap_vault(vault_root, title="My Vault Novel")
            source_root.mkdir(parents=True, exist_ok=True)
            (source_root / "01_first.md").write_text("# First Chapter\n\nOld prose.")
            (source_root / "02_second.md").write_text("Second chapter without heading.")

            paths = import_existing_chapters(vault_root, source_root, source_label="legacy_import")

            self.assertEqual(len(paths), 2)
            first_text = paths[0].read_text()
            self.assertIn("source: legacy_import", first_text)
            self.assertIn("origin_type: existing_chapter", first_text)
            self.assertIn("status: pending_revision", first_text)
            self.assertIn("# First Chapter", first_text)

    def test_ingest_digested_context_writes_root_and_structured_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "NovelVault"
            bootstrap_vault(vault_root, title="My Vault Novel")

            written = ingest_digested_context(
                vault_root,
                {
                    "source_id": "session-123",
                    "artifacts": [
                        {
                            "artifact": "world",
                            "title": "World",
                            "status": "pending_revision",
                            "body": "Synthesized world note.",
                            "metadata": {"source_chapters": "1-3"},
                        },
                        {
                            "artifact": "character",
                            "slug": "mara",
                            "title": "Mara",
                            "status": "proposed",
                            "body": "A suspicious ally.",
                        },
                    ],
                },
            )

            self.assertEqual(len(written), 2)
            world_text = (vault_root / "02_World" / "World.md").read_text()
            character_text = (vault_root / "03_Characters" / "Profiles" / "mara.md").read_text()
            self.assertIn("origin_ref: session-123", world_text)
            self.assertIn("source_chapters: 1-3", world_text)
            self.assertIn("origin_type: digested_context", world_text)
            self.assertIn("origin_ref: session-123", character_text)
            self.assertIn("source: obsidian_cli", character_text)


if __name__ == "__main__":
    unittest.main()
