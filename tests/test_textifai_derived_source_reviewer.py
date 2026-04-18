import tempfile
import unittest
from pathlib import Path

from textifai.derived_sources import decide_llm_escalation, extract_light_source, review_derived_source, validate_derived_extraction


class TextifAIDerivedSourceReviewerTests(unittest.TestCase):
    def test_pdf_scan_requires_strict_confirmation_and_stays_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            seed = extract_light_source(path)
            escalation = decide_llm_escalation(seed)
            validated = validate_derived_extraction(seed=seed, payload=None)
            review = review_derived_source(seed=seed, escalation=escalation, validated_extraction=validated, llm_payload=None)

            self.assertTrue(escalation.required)
            self.assertTrue(review.strict_confirmation_required)
            self.assertIn(review.review_status, {"pending", "needs_correction"})
            self.assertFalse(review.llm_used)
            self.assertGreaterEqual(review.final_confidence, 0.0)

    def test_native_like_docx_can_stay_usable_with_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.docx"
            path.write_bytes(
                b"PK\x03\x04"
            )
            # The fallback extraction will be sparse, but still enough to ensure the path stays derived.
            seed = extract_light_source(path)
            escalation = decide_llm_escalation(seed)
            validated = validate_derived_extraction(seed=seed, payload=None)
            review = review_derived_source(seed=seed, escalation=escalation, validated_extraction=validated, llm_payload=None)

            self.assertEqual(review.source_format, "docx")
            self.assertIn(review.review_status, {"pending", "usable_with_warnings", "needs_correction"})


if __name__ == "__main__":
    unittest.main()
