import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import (
    VaultInitializationConfig,
    build_bootstrap_result,
    build_normalization_plan,
    build_source_document_inventory,
    read_source_documents,
    segment_source_document,
)
from textifai.bootstrap.staging_writer import ensure_import_staging_structure, write_bootstrap_staging


class TextifAIBootstrapStagingWriterTests(unittest.TestCase):
    def test_staging_writer_creates_manifest_and_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "sources"
            vault_root = Path(tmp) / "vault"
            source_root.mkdir()
            vault_root.mkdir()
            (source_root / "chapter.md").write_text("# Chapter One\n\nThe meeting began.")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="en",
                working_languages=["en"],
                create_base_structure=True,
                use_import_staging=True,
            )
            inventory = build_source_document_inventory(source_root)
            source_texts = read_source_documents(inventory)
            fragments_by_source = {
                document.source_id: segment_source_document(document, source_texts[document.source_id])
                for document in inventory.documents
            }
            plan, coverage = build_normalization_plan(
                config=config,
                inventory=inventory,
                source_texts=source_texts,
                fragments_by_source=fragments_by_source,
            )

            staging_root = ensure_import_staging_structure(vault_root)
            self.assertTrue(staging_root.exists())

            written_paths, report, manifest_path = write_bootstrap_staging(
                plan=plan,
                inventory=inventory,
                source_texts=source_texts,
                fragments_by_source=fragments_by_source,
                warnings=[],
            )

            self.assertTrue(written_paths)
            self.assertTrue(manifest_path.exists())
            draft_path = Path(written_paths[0])
            self.assertTrue(draft_path.exists())
            draft_text = draft_path.read_text()
            self.assertIn("## Imported Material", draft_text)
            self.assertIn("Chapter One", draft_text)
            manifest = json.loads(manifest_path.read_text())
            self.assertIn("per_document", manifest)
            self.assertIn("written_paths", manifest)
            self.assertEqual(report["total_documents"], coverage["total_documents"])


if __name__ == "__main__":
    unittest.main()
