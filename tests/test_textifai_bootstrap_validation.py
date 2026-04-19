import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import (
    VaultInitializationConfig,
    confirm_and_write_bootstrap,
    validate_bootstrap_result,
)
from vault.bootstrap import bootstrap_vault


class TextifAIBootstrapValidationTests(unittest.TestCase):
    def test_bootstrap_flow_writes_only_to_staging_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "vault"
            source_root = base_dir / "sources"
            source_root.mkdir()
            (source_root / "meeting.md").write_text("# Meeting Notes\n\nThe client asked for a calmer tone.")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="en",
                working_languages=["en", "es"],
                create_base_structure=True,
                use_import_staging=True,
            )

            result = confirm_and_write_bootstrap(config, source_root=source_root)

            self.assertTrue(vault_root.exists())
            self.assertTrue((vault_root / "99_Import_Staging").exists())
            self.assertTrue(result.written_drafts)
            self.assertTrue(result.coverage_report["staged_fragments"] >= 1)
            self.assertEqual(validate_bootstrap_result(result), [])
            for draft_path in result.written_drafts:
                self.assertIn("99_Import_Staging", draft_path)

    def test_bootstrap_vault_creates_import_staging_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "vault"
            bootstrap_vault(vault_root, title="Project")
            self.assertTrue((vault_root / "99_Import_Staging").exists())
            self.assertTrue((vault_root / "99_Import_Staging" / "_manifests").exists())

    def test_bootstrap_enriches_subject_titles_and_promotion_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "vault"
            source_root = base_dir / "sources"
            source_root.mkdir()
            (source_root / "lore.md").write_text(
                "\n".join(
                    [
                        "## Origen de los Nushi",
                        "",
                        "### No nacen como animales",
                        "",
                        "Un Nushi:",
                        "",
                        "* no se reproduce biológicamente,",
                        "* no es invocado,",
                        "* no puede ser creado artificialmente.",
                    ]
                ),
                encoding="utf-8",
            )

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="es",
                working_languages=["es"],
                create_base_structure=True,
                use_import_staging=True,
            )

            result = confirm_and_write_bootstrap(config, source_root=source_root)

            self.assertTrue(result.written_drafts)
            text = Path(result.written_drafts[0]).read_text(encoding="utf-8")
            self.assertIn("kind: lore", text)
            self.assertIn("canonical_subject: Nushi", text)
            self.assertIn("semantic_class: world_entity", text)
            self.assertIn("promotion_status: eligible_for_promotion", text)
            self.assertRegex(text, r"title: .*Nushi")


if __name__ == "__main__":
    unittest.main()
