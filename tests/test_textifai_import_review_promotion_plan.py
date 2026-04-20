from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from textifai.bootstrap import VaultInitializationConfig, confirm_and_write_bootstrap
from textifai.import_review import build_promotion_plan, load_staging_import_bundle, review_import_stage
from vault.notes import write_or_update_note


class TextifAIImportReviewPromotionPlanTests(unittest.TestCase):
    def test_conflicting_stable_target_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "sources"
            vault_root = base / "vault"
            source_root.mkdir()
            (source_root / "character.md").write_text(
                "---\nkind: character\ntitle: Sera\nslug: sera\n---\n\n# Sera\n\n"
                "Sera leads the group, protects the map, and keeps the others aligned when the ritual fails.",
                encoding="utf-8",
            )

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
            bundle, reviews, _ = review_import_stage(vault_root)
            draft = bundle.drafts[0]
            adapter = VaultProjectAdapter(vault_root)
            conflict_path = adapter.note_path(draft.artifact_type, draft.target_slug)
            write_or_update_note(
                vault_root,
                note_type=draft.artifact_type,
                slug=draft.target_slug,
                title="Existing Character",
                status="pending_revision",
                body="Already promoted content.",
            )

            plan = build_promotion_plan(bundle, reviews, stable_root=vault_root)

            self.assertIn(str(conflict_path), " ".join(plan.conflicts))
            self.assertTrue(plan.requires_confirmation)
            self.assertEqual(plan.decisions[0].decision, "blocked_by_conflict")
            self.assertEqual(plan.decisions[0].overwrite_mode, "require_confirm")


if __name__ == "__main__":
    unittest.main()
