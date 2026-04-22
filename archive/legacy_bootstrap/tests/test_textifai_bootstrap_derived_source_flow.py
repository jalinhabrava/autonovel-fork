import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.bootstrap import ProviderBackedBootstrapAnalyzer, VaultInitializationConfig, prepare_bootstrap
from textifai.derived_sources import (
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSegmentCandidate,
    DerivedSourceLLMConfig,
    DerivedStructureSignals,
    FormatExtractionProfile,
)


class TextifAIBootstrapDerivedSourceFlowTests(unittest.TestCase):
    def test_bootstrap_uses_llm_recovered_text_for_difficult_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "sources"
            vault_root = base / "vault"
            source_root.mkdir()
            vault_root.mkdir()
            (source_root / "scan.pdf").write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Derived Test",
                primary_language="en",
                working_languages=["en", "es", "ja"],
                create_base_structure=True,
                use_import_staging=True,
            )

            fake_payload = DerivedLLMExtractionPayload(
                source_id="scan_deadbeef",
                source_format="pdf",
                dominant_language="en",
                detected_languages=["en"],
                has_mixed_language=False,
                overall_confidence=0.82,
                structural_confidence=0.76,
                content_mix_signals=[],
                warnings=["llm_recovered_pdf_text"],
                segment_candidates=[
                    DerivedSegmentCandidate(
                        candidate_id="cand_001",
                        segment_text="Recovered chapter",
                        heading_text="Recovered chapter",
                        probable_kind="chapter",
                        language="en",
                        confidence=0.79,
                        mixed_content=False,
                        boundary_hints=["recovered_heading"],
                        notes=["llm_segment"],
                    )
                ],
                structure_signals=DerivedStructureSignals(
                    recovered_headings=["Recovered chapter"],
                    probable_block_order=["cand_001"],
                    recovered_lists=[],
                    ordering_confidence=0.74,
                    structure_warnings=["pdf_layout_uncertain"],
                    confidence=0.75,
                ),
                loss_signals=DerivedLossSignals(
                    missing_structure_signals=["non_extractable_text"],
                    paragraph_merge_signals=[],
                    heading_loss_signals=["missing_visible_headings"],
                    ordering_uncertainty_signals=["pdf_order_uncertain"],
                    coverage_risk_notes=["review_needed"],
                    severity="medium",
                    mixed_language_degradation=[],
                ),
                needs_manual_review=False,
                recognized_or_recovered_text="Recovered chapter\n\nThe scene opens with a quiet room.",
                llm_escalation_reasons=["non_extractable_text"],
                raw_payload={"ok": True},
            )

            with patch("textifai.bootstrap.analyzer.get_text_provider_config_error", return_value=False), patch(
                "textifai.derived_sources.llm_interpreter.ProviderBackedDerivedSourceInterpreter.interpret",
                return_value=fake_payload,
            ):
                result = prepare_bootstrap(
                    config,
                    source_root=source_root,
                    llm_analyzer=ProviderBackedBootstrapAnalyzer(
                        config=DerivedSourceLLMConfig(
                            task_name="derived_source_understanding",
                            provider_name="anthropic",
                            model="test-model",
                        )
                    ),
                )

            self.assertIsNotNone(result.normalization_plan)
            self.assertTrue(result.normalization_plan.requires_confirmation)
            self.assertGreater(len(result.normalization_plan.drafts), 0)
            self.assertIn("Recovered chapter", result.normalization_plan.drafts[0].body)
            self.assertEqual(result.normalization_plan.drafts[0].provenance.source_format, "pdf")
            self.assertEqual(result.normalization_plan.drafts[0].provenance.extraction_mode, "llm_first_derived")
            self.assertTrue(result.normalization_plan.drafts[0].provenance.llm_assisted)


if __name__ == "__main__":
    unittest.main()
