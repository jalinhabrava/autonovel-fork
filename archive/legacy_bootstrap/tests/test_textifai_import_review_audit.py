from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import VaultInitializationConfig, confirm_and_write_bootstrap
from textifai.import_review import promote_controlled_import, review_import_stage, write_import_audit


class TextifAIImportReviewAuditTests(unittest.TestCase):
    def test_audit_manifest_records_promotion_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "sources"
            vault_root = base / "vault"
            source_root.mkdir()
            (source_root / "scene.md").write_text("# Scene\n\nThe room was quiet.")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="en",
                working_languages=["en"],
                create_base_structure=True,
                use_import_staging=True,
            )
            confirm_and_write_bootstrap(config, source_root=source_root)
            bundle, reviews, plan = review_import_stage(vault_root)

            result = promote_controlled_import(bundle=bundle, reviews=reviews, plan=plan, confirmed=True)
            write_import_audit(bundle=bundle, plan=plan, result=result)
            audit_path = vault_root / "99_System" / "import_review" / f"{plan.plan_id}.json"
            self.assertTrue(audit_path.exists())

            audit = json.loads(audit_path.read_text())
            self.assertEqual(audit["plan_id"], plan.plan_id)
            self.assertEqual(audit["bundle"]["vault_root"], str(vault_root.resolve()))
            self.assertEqual(audit["result"]["plan_id"], result.plan_id)
            self.assertIn("promoted_paths", audit["result"])
            self.assertTrue((vault_root / "99_Import_Staging" / "_manifests").exists())


if __name__ == "__main__":
    unittest.main()
