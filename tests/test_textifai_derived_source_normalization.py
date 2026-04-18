import tempfile
import unittest
import zipfile
from pathlib import Path

from textifai.derived_sources import (
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSegmentCandidate,
    DerivedStructureSignals,
    FormatExtractionProfile,
    extract_light_source,
    normalize_derived_llm_payload,
    validate_derived_extraction,
)


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    content = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
    ]
    for paragraph in paragraphs:
        content.append(f"<w:p><w:r><w:t>{_escape_xml(paragraph)}</w:t></w:r></w:p>")
    content.append("</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", "".join(content))


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class TextifAIDerivedSourceNormalizationTests(unittest.TestCase):
    def test_validates_llm_payload_and_preserves_coverage_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.docx"
            _write_docx(path, ["Narration prep", "The scene is quiet.", "Luego entra otro personaje."])
            seed = extract_light_source(path)

            payload = normalize_derived_llm_payload(
                payload={
                    "source_id": seed.source_id,
                    "dominant_language": "es",
                    "detected_languages": ["es", "en"],
                    "has_mixed_language": True,
                    "overall_confidence": 0.78,
                    "structural_confidence": 0.74,
                    "content_mix_signals": ["narrative_and_note_mix"],
                    "warnings": ["mixed_language"],
                    "segment_candidates": [
                        {
                            "candidate_id": "cand_001",
                            "segment_text": "Narration prep",
                            "heading_text": "Narration prep",
                            "probable_kind": "project_note",
                            "language": "en",
                            "confidence": 0.72,
                            "mixed_content": False,
                            "boundary_hints": ["heading"],
                            "notes": ["llm_suggested_heading"],
                        }
                    ],
                    "structure_signals": {
                        "recovered_headings": ["Narration prep"],
                        "probable_block_order": ["cand_001"],
                        "recovered_lists": [],
                        "ordering_confidence": 0.71,
                        "structure_warnings": ["lightly_recovered"],
                        "confidence": 0.73,
                    },
                    "loss_signals": {
                        "missing_structure_signals": ["paragraph_merge_risk"],
                        "paragraph_merge_signals": ["possible_merge"],
                        "heading_loss_signals": [],
                        "ordering_uncertainty_signals": ["minor_order_uncertainty"],
                        "coverage_risk_notes": ["needs_review"],
                        "severity": "medium",
                        "mixed_language_degradation": ["es_en_mix"],
                    },
                    "needs_manual_review": False,
                    "recognized_or_recovered_text": "Narration prep\n\nThe scene is quiet.\n\nLuego entra otro personaje.",
                },
                source_id=seed.source_id,
                source_format=seed.source_format,
                llm_used=True,
                format_profile=seed.format_profile,
            )

            self.assertIsInstance(payload, DerivedLLMExtractionPayload)
            self.assertTrue(payload.has_mixed_language)
            self.assertEqual(payload.segment_candidates[0].probable_kind, "project_note")

            validated = validate_derived_extraction(seed=seed, payload=payload)
            self.assertEqual(validated.review_status, "usable_with_warnings")
            self.assertTrue(validated.llm_used)
            self.assertIn("llm_recovered_text", validated.notes)
            self.assertIn("needs_review", validated.notes)

    def test_missing_llm_payload_keeps_derived_sources_conservative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            seed = extract_light_source(path)
            validated = validate_derived_extraction(seed=seed, payload=None)

            self.assertFalse(validated.llm_used)
            self.assertEqual(validated.review_status, "pending")
            self.assertTrue(validated.requires_confirmation)
            self.assertGreaterEqual(validated.structural_confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
