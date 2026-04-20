from __future__ import annotations

import unittest

from textifai.import_review.contracts import (
    ExtractionProfile,
    ImportAuditEntry,
    PromotionDecision,
    PromotionResult,
    StagedArtifactReview,
)


class TextifAIImportReviewContractsTests(unittest.TestCase):
    def test_extraction_profile_validates_catalogs_and_confidence(self):
        profile = ExtractionProfile(
            source_format="pdf",
            extraction_mode="derived_text_extraction",
            extraction_confidence=0.8,
            structural_confidence=0.7,
            warnings=["heading_loss"],
            loss_risk_flags=["ordering"],
        )

        self.assertEqual(profile.source_format, "pdf")
        self.assertEqual(profile.extraction_mode, "derived_text_extraction")

        with self.assertRaises(ValueError):
            ExtractionProfile(
                source_format="txt",
                extraction_mode="unsupported",
                extraction_confidence=0.8,
                structural_confidence=0.8,
            )

    def test_staged_review_and_promotion_contract_shapes(self):
        review = StagedArtifactReview(
            draft_id="draft-1",
            staging_path="/tmp/stage/draft.md",
            artifact_type="chapter",
            review_status="accepted",
            provenance_ok=True,
            coverage_ok=True,
        )
        decision = PromotionDecision(
            draft_id="draft-1",
            decision="promote",
            target_artifact_type="chapter",
            target_slug="chapter-one",
            target_path="/tmp/vault/04_Story/Chapters/chapter_one.md",
            overwrite_mode="forbid",
            reason="accepted",
        )
        audit_entry = ImportAuditEntry(
            entry_id="draft-1__promoted",
            draft_id="draft-1",
            action="promoted",
            timestamp="2026-01-01T00:00:00+00:00",
            review_status="accepted",
            stable_target_path="/tmp/vault/04_Story/Chapters/chapter_one.md",
        )
        result = PromotionResult(
            plan_id="plan-1",
            promoted_paths=["/tmp/vault/04_Story/Chapters/chapter_one.md"],
            audit_entries=[audit_entry],
        )

        self.assertEqual(review.review_status, "accepted")
        self.assertEqual(decision.decision, "promote")
        self.assertEqual(result.plan_id, "plan-1")


if __name__ == "__main__":
    unittest.main()
