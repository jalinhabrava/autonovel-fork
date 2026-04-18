from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import VaultInitializationConfig, confirm_and_write_bootstrap
from textifai.import_review import load_staging_import_bundle, review_import_stage
from textifai.import_review.reviewer import review_staged_artifact


class TextifAIImportReviewReviewerTests(unittest.TestCase):
    def test_loads_staging_bundle_and_reviews_native_text_as_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "sources"
            vault_root = base / "vault"
            source_root.mkdir()
            (source_root / "chapter.md").write_text("# Chapter One\n\nThe meeting began calmly.")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="en",
                working_languages=["en"],
                create_base_structure=True,
                use_import_staging=True,
            )
            result = confirm_and_write_bootstrap(config, source_root=source_root)
            self.assertTrue(result.written_drafts)

            bundle = load_staging_import_bundle(vault_root)
            self.assertEqual(len(bundle.drafts), 1)

            review_bundle, reviews, plan = review_import_stage(vault_root)
            self.assertEqual(review_bundle.manifest_path, bundle.manifest_path)
            self.assertEqual(reviews[0].review_status, "accepted")
            self.assertEqual(plan.decisions[0].decision, "promote")
            self.assertFalse(plan.requires_confirmation)

    def test_review_marks_derived_low_confidence_as_needing_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "vault"
            staging_root = vault_root / "99_Import_Staging"
            manifests_root = staging_root / "_manifests"
            draft_path = staging_root / "chapters" / "extracted-chapter.md"
            manifest_path = manifests_root / "plan-001.json"
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            manifests_root.mkdir(parents=True, exist_ok=True)

            draft_path.write_text(
                "---\n"
                "kind: chapter\n"
                "title: Extracted Chapter\n"
                "status: draft\n"
                "schema_version: 1.0\n"
                "source_id: doc-001\n"
                "source_path: /source/chapter.docx\n"
                "source_checksum: abc123\n"
                "source_format: pdf\n"
                "extraction_mode: derived_text_extraction\n"
                "extraction_confidence: 0.35\n"
                "structural_confidence: 0.40\n"
                "import_mode: literal_segmented\n"
                "llm_assisted: True\n"
                "fragment_ids: frag-001\n"
                "warnings: heading_loss\n"
                "loss_risk_flags: ordering\n"
                "dominant_language: en\n"
                "detected_languages: en\n"
                "---\n\n"
                "# Extracted Chapter\n\n"
                "Body from extracted source.\n"
            )
            manifest = {
                "plan": {
                    "plan_id": "plan-001",
                    "target_vault_root": str(vault_root),
                    "target_staging_root": str(staging_root),
                    "drafts": [
                        {
                            "draft_id": "doc-001__frag-001",
                            "artifact_type": "chapter",
                            "title": "Extracted Chapter",
                            "slug": "extracted_chapter",
                            "target_path": str(draft_path),
                            "provenance": {
                                "source_id": "doc-001",
                                "source_path": "/source/chapter.docx",
                                "source_checksum": "abc123",
                                "source_format": "pdf",
                                "extraction_mode": "derived_text_extraction",
                                "extraction_confidence": 0.35,
                                "structural_confidence": 0.40,
                                "fragment_ids": ["frag-001"],
                                "char_ranges": [{"start": 0, "end": 40}],
                                "import_mode": "literal_segmented",
                                "llm_assisted": True,
                                "warnings": ["heading_loss"],
                                "loss_risk_flags": ["ordering"],
                                "notes": ["literal segment"],
                            },
                            "normalization_notes": ["derived import"],
                        }
                    ],
                    "unmapped_fragments": [],
                    "ambiguous_fragments": ["frag-001"],
                    "coverage_summary": {
                        "total_documents": 1,
                        "total_fragments": 1,
                        "total_chars": 40,
                        "covered_chars": 40,
                        "ambiguous_chars": 40,
                        "unmapped_chars": 0,
                        "pending_fragments": 0,
                        "staged_fragments": 1,
                        "multilingual_documents": 0,
                    },
                    "requires_confirmation": True,
                },
                "inventory": {
                    "source_root": str(base / "sources"),
                    "total_documents": 1,
                    "total_bytes": 40,
                    "detected_working_languages": ["en"],
                    "has_multilingual_material": False,
                    "warnings": [],
                },
                "per_document": [],
                "written_paths": [str(draft_path)],
                "warnings": [],
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))

            bundle = load_staging_import_bundle(vault_root)
            review = review_staged_artifact(bundle, bundle.drafts[0])

            self.assertEqual(review.review_status, "needs_correction")
            self.assertTrue(review.requires_strict_confirmation)
            self.assertIsNotNone(review.extraction_profile)
            self.assertEqual(review.extraction_profile.extraction_mode, "derived_text_extraction")

    def test_multilingual_metadata_survives_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "sources"
            vault_root = base / "vault"
            source_root.mkdir()
            (source_root / "spanish.md").write_text("# Capítulo\n\nLa reunión empezó temprano.")
            (source_root / "japanese.txt").write_text("会議は静かに始まった。")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="es",
                working_languages=["es", "ja"],
                create_base_structure=True,
                use_import_staging=True,
            )
            confirm_and_write_bootstrap(config, source_root=source_root)
            bundle = load_staging_import_bundle(vault_root)

            self.assertTrue(bundle.manifest["inventory"]["has_multilingual_material"])
            self.assertIn("es", bundle.manifest["inventory"]["detected_working_languages"])
            self.assertIn("ja", bundle.manifest["inventory"]["detected_working_languages"])
            self.assertGreaterEqual(len(bundle.drafts), 2)


if __name__ == "__main__":
    unittest.main()
