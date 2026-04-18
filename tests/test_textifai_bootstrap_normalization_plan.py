import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import (
    BootstrapDocumentAnalysis,
    BootstrapFragmentAnalysis,
    VaultInitializationConfig,
    build_normalization_plan,
    build_source_document_inventory,
    read_source_documents,
    segment_source_document,
)


class TextifAIBootstrapNormalizationPlanTests(unittest.TestCase):
    def test_normalization_plan_builds_conservative_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "sources"
            vault_root = Path(tmp) / "vault"
            source_root.mkdir()
            vault_root.mkdir()
            (source_root / "chapter.md").write_text("# Chapter One\n\nThe meeting began.\n\n# Chapter Two\n\nThe client left.")
            (source_root / "notes.txt").write_text("Remember to call the client.\n\nAnd keep the tone calm.")

            config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Project",
                primary_language="en",
                working_languages=["en", "es"],
                create_base_structure=True,
                use_import_staging=True,
            )
            inventory = build_source_document_inventory(source_root)
            source_texts = read_source_documents(inventory)
            fragments_by_source = {
                document.source_id: segment_source_document(document, source_texts[document.source_id])
                for document in inventory.documents
            }
            first_document = inventory.documents[0]
            first_fragments = fragments_by_source[first_document.source_id]
            analyses_by_source = {
                first_document.source_id: BootstrapDocumentAnalysis(
                    source_id=first_document.source_id,
                    dominant_language="en",
                    detected_languages=["en"],
                    has_mixed_language=False,
                    fragment_analyses=[
                        BootstrapFragmentAnalysis(
                            fragment_id=first_fragments[0].fragment_id,
                            artifact_type="chapter",
                            confidence=0.55,
                            title_hint="Chapter One",
                            language="en",
                            detected_languages=["en"],
                            register_signals=["markdown_heading"],
                            needs_review=True,
                            notes=["literal"],
                        )
                    ],
                    coverage_notes=["conservative mapping"],
                    unmapped_fragment_ids=[first_fragments[1].fragment_id],
                    ambiguous_fragment_ids=[first_fragments[0].fragment_id],
                    requires_confirmation=True,
                    confidence=0.8,
                    raw_payload={"source": "fake"},
                )
            }

            plan, coverage = build_normalization_plan(
                config=config,
                inventory=inventory,
                source_texts=source_texts,
                fragments_by_source=fragments_by_source,
                analyses_by_source=analyses_by_source,
            )

            self.assertGreaterEqual(len(plan.drafts), 1)
            self.assertIn(first_fragments[1].fragment_id, plan.unmapped_fragments)
            self.assertIn(first_fragments[0].fragment_id, plan.ambiguous_fragments)
            self.assertGreaterEqual(coverage["staged_fragments"], 1)
            self.assertGreater(coverage["covered_chars"], 0)
            self.assertGreaterEqual(plan.coverage_summary["ambiguous_chars"], 0)


if __name__ == "__main__":
    unittest.main()
