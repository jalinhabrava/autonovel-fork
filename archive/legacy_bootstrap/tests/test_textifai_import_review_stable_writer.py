from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import VaultInitializationConfig, confirm_and_write_bootstrap
from textifai.bootstrap.contracts import ImportProvenance
from textifai.import_review import promote_controlled_import, review_import_stage, write_import_audit
from textifai.import_review.contracts import ExtractionProfile, PromotionDecision, PromotionPlan
from textifai.import_review.reviewer import review_staged_artifact
from textifai.import_review.staging_loader import LoadedStagedDraft, StagingImportBundle


class TextifAIImportReviewStableWriterTests(unittest.TestCase):
    def test_promotion_writes_stable_artifact_and_keeps_staging_intact(self):
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
            confirm_and_write_bootstrap(config, source_root=source_root)
            bundle, reviews, plan = review_import_stage(vault_root)

            result = promote_controlled_import(bundle=bundle, reviews=reviews, plan=plan, confirmed=True)
            write_import_audit(bundle=bundle, plan=plan, result=result)

            self.assertEqual(len(result.promoted_paths), 1)
            promoted_path = Path(result.promoted_paths[0])
            self.assertTrue(promoted_path.exists())
            self.assertTrue(Path(bundle.staging_root).exists())
            self.assertTrue(Path(bundle.manifest_path).exists())
            audit_path = vault_root / "99_System" / "import_review" / f"{plan.plan_id}.json"
            self.assertTrue(audit_path.exists())
            audit = json.loads(audit_path.read_text())
            self.assertEqual(audit["plan_id"], plan.plan_id)
            self.assertEqual(audit["result"]["plan_id"], plan.plan_id)

    def test_confirmation_required_keeps_promotion_pending_until_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "vault"
            staging_root = vault_root / "99_Import_Staging"
            manifests_root = staging_root / "_manifests"
            draft_path = staging_root / "chapters" / "extracted-chapter.md"
            manifest_path = manifests_root / "plan-002.json"
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            manifests_root.mkdir(parents=True, exist_ok=True)

            draft_path.write_text(
                "---\n"
                "kind: chapter\n"
                "title: Extracted Chapter\n"
                "status: draft\n"
                "schema_version: 1.0\n"
                "source_id: doc-002\n"
                "source_path: /source/chapter.docx\n"
                "source_checksum: def456\n"
                "source_format: pdf\n"
                "extraction_mode: derived_text_extraction\n"
                "extraction_confidence: 0.95\n"
                "structural_confidence: 0.95\n"
                "import_mode: literal_segmented\n"
                "llm_assisted: True\n"
                "fragment_ids: frag-002\n"
                "warnings: heading_loss\n"
                "loss_risk_flags: ordering\n"
                "dominant_language: en\n"
                "detected_languages: en\n"
                "---\n\n"
                "# Extracted Chapter\n\n"
                "Body from extracted source.\n"
            )
            provenance = {
                "source_id": "doc-002",
                "source_path": "/source/chapter.docx",
                "source_checksum": "def456",
                "source_format": "pdf",
                "extraction_mode": "derived_text_extraction",
                "extraction_confidence": 0.95,
                "structural_confidence": 0.95,
                "fragment_ids": ["frag-002"],
                "char_ranges": [{"start": 0, "end": 40}],
                "import_mode": "literal_segmented",
                "llm_assisted": True,
                "warnings": ["heading_loss"],
                "loss_risk_flags": ["ordering"],
                "notes": ["literal segment"],
            }
            manifest = {
                "plan": {
                    "plan_id": "plan-002",
                    "target_vault_root": str(vault_root),
                    "target_staging_root": str(staging_root),
                    "drafts": [
                        {
                            "draft_id": "doc-002__frag-002",
                            "artifact_type": "chapter",
                            "title": "Extracted Chapter",
                            "slug": "extracted_chapter",
                            "target_path": str(draft_path),
                            "provenance": provenance,
                            "normalization_notes": ["derived import"],
                        }
                    ],
                    "unmapped_fragments": [],
                    "ambiguous_fragments": [],
                    "coverage_summary": {
                        "total_documents": 1,
                        "total_fragments": 1,
                        "total_chars": 40,
                        "covered_chars": 40,
                        "ambiguous_chars": 0,
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

            extraction_profile = ExtractionProfile(
                source_format="pdf",
                extraction_mode="derived_text_extraction",
                extraction_confidence=0.95,
                structural_confidence=0.95,
                warnings=["heading_loss"],
                loss_risk_flags=["ordering"],
            )
            provenance_object = ImportProvenance(
                source_id="doc-002",
                source_path="/source/chapter.docx",
                source_checksum="def456",
                source_format="pdf",
                extraction_mode="derived_text_extraction",
                extraction_confidence=0.95,
                structural_confidence=0.95,
                fragment_ids=["frag-002"],
                char_ranges=[{"start": 0, "end": 40}],
                import_mode="literal_segmented",
                llm_assisted=True,
                warnings=["heading_loss"],
                loss_risk_flags=["ordering"],
                notes=["literal segment"],
            )
            bundle = StagingImportBundle(
                vault_root=str(vault_root),
                staging_root=str(staging_root),
                manifest_path=str(manifest_path),
                manifest=manifest,
                coverage_summary=manifest["plan"]["coverage_summary"],
                drafts=[
                    LoadedStagedDraft(
                        draft_id="doc-002__frag-002",
                        staging_path=str(draft_path),
                        body="Body from extracted source.",
                        frontmatter={
                            "kind": "chapter",
                            "title": "Extracted Chapter",
                            "status": "draft",
                            "schema_version": "1.0",
                            "source_id": "doc-002",
                            "source_path": "/source/chapter.docx",
                            "source_checksum": "def456",
                            "source_format": "pdf",
                            "extraction_mode": "derived_text_extraction",
                            "extraction_confidence": "0.95",
                            "structural_confidence": "0.95",
                            "import_mode": "literal_segmented",
                            "llm_assisted": "True",
                            "fragment_ids": "frag-002",
                            "warnings": "heading_loss",
                            "loss_risk_flags": "ordering",
                            "dominant_language": "en",
                            "detected_languages": "en",
                        },
                        manifest_draft=manifest["plan"]["drafts"][0],
                        provenance=provenance_object,
                        extraction_profile=extraction_profile,
                        artifact_type="chapter",
                        target_slug="extracted_chapter",
                        target_path=str(draft_path),
                        source_format="pdf",
                        notes=["derived import"],
                    )
                ],
                warnings=[],
            )
            review = review_staged_artifact(bundle, bundle.drafts[0])
            plan = PromotionPlan(
                plan_id="plan-002",
                decisions=[
                    PromotionDecision(
                        draft_id=bundle.drafts[0].draft_id,
                        decision="promote",
                        target_artifact_type="chapter",
                        target_slug="extracted_chapter",
                        target_path=str(vault_root / "05_Draft" / "Chapters" / "extracted_chapter.md"),
                        overwrite_mode="require_confirm",
                        reason="accepted",
                    )
                ],
                conflicts=[],
                requires_confirmation=True,
                warnings=[],
            )

            pending_result = promote_controlled_import(bundle=bundle, reviews=[review], plan=plan, confirmed=False)
            self.assertEqual(pending_result.promoted_paths, [])
            self.assertIn(bundle.drafts[0].draft_id, pending_result.pending_drafts)

            confirmed_result = promote_controlled_import(bundle=bundle, reviews=[review], plan=plan, confirmed=True)
            self.assertEqual(len(confirmed_result.promoted_paths), 1)
            self.assertTrue(Path(confirmed_result.promoted_paths[0]).exists())


if __name__ == "__main__":
    unittest.main()
