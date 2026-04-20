import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap import (
    BootstrapDocumentAnalysis,
    BootstrapFragmentAnalysis,
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

    def test_bootstrap_without_llm_stays_structural_and_staged(self):
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
            self.assertIn("promotion_status: staged_candidate", text)
            self.assertIn("semantic_class:", text)
            self.assertNotIn("canonical_subject: Nushi", text)

    def test_bootstrap_llm_analysis_can_supply_semantic_subject_and_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "vault"
            source_root = base_dir / "sources"
            source_root.mkdir()
            (source_root / "lore.md").write_text(
                "\n".join(
                    [
                        "## What Nushi are",
                        "",
                        "### Origin and constraints",
                        "",
                        "Nushi:",
                        "",
                        "- do not reproduce biologically",
                        "- cannot be artificially created",
                        "- break the system when forced into existence",
                    ]
                ),
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

            result = confirm_and_write_bootstrap(
                config,
                source_root=source_root,
                llm_analyzer=_StubBootstrapAnalyzer(
                    dominant_language="en",
                    fragment_blueprints=[
                        {
                            "artifact_type": "lore",
                            "confidence": 0.91,
                            "title_hint": "Nushi - origin and constraints",
                            "canonical_subject": "Nushi",
                            "semantic_class": "world_entity",
                            "promotion_status": "eligible_for_promotion",
                            "fragment_role": "headed_section",
                            "entities": ["Nushi"],
                            "topics": ["origin", "constraints"],
                            "world_terms": ["Nushi"],
                            "lore_refs": ["Nushi"],
                            "language": "en",
                            "detected_languages": ["en"],
                            "register_signals": ["markdown_heading"],
                            "needs_review": False,
                            "notes": ["llm_semantic_normalization"],
                        }
                    ],
                ),
            )

            text = Path(result.written_drafts[0]).read_text(encoding="utf-8")
            self.assertIn("canonical_subject: Nushi", text)
            self.assertIn("semantic_class: world_entity", text)
            self.assertIn("promotion_status: eligible_for_promotion", text)
            self.assertRegex(text, r"title: .*Nushi")

    def test_structural_collection_heading_stays_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "vault"
            source_root = base_dir / "sources"
            source_root.mkdir()
            (source_root / "characters.md").write_text(
                "\n".join(
                    [
                        "## Protagonists",
                        "",
                        "- Sera",
                        "- Kaito",
                        "- Ren",
                    ]
                ),
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

            result = confirm_and_write_bootstrap(config, source_root=source_root)

            text = Path(result.written_drafts[0]).read_text(encoding="utf-8")
            self.assertIn("promotion_status: staged_candidate", text)
            self.assertIn("semantic_class: section_fragment", text)


class _StubBootstrapAnalyzer:
    def __init__(self, *, dominant_language: str, fragment_blueprints: list[dict]) -> None:
        self.dominant_language = dominant_language
        self.fragment_blueprints = fragment_blueprints

    def analyze_document(self, *, config, document, text, fragments):
        fragment_analyses = []
        for index, fragment in enumerate(fragments):
            blueprint = self.fragment_blueprints[min(index, len(self.fragment_blueprints) - 1)]
            fragment_analyses.append(
                BootstrapFragmentAnalysis(
                    fragment_id=fragment.fragment_id,
                    artifact_type=blueprint.get("artifact_type", "mixed_note"),
                    confidence=blueprint.get("confidence", 0.0),
                    title_hint=blueprint.get("title_hint"),
                    canonical_subject=blueprint.get("canonical_subject"),
                    semantic_class=blueprint.get("semantic_class"),
                    promotion_status=blueprint.get("promotion_status"),
                    fragment_role=blueprint.get("fragment_role"),
                    entities=list(blueprint.get("entities", [])),
                    topics=list(blueprint.get("topics", [])),
                    world_terms=list(blueprint.get("world_terms", [])),
                    character_refs=list(blueprint.get("character_refs", [])),
                    lore_refs=list(blueprint.get("lore_refs", [])),
                    language=blueprint.get("language"),
                    detected_languages=list(blueprint.get("detected_languages", [])),
                    register_signals=list(blueprint.get("register_signals", [])),
                    needs_review=bool(blueprint.get("needs_review", False)),
                    notes=list(blueprint.get("notes", [])),
                )
            )
        return BootstrapDocumentAnalysis(
            source_id=document.source_id,
            dominant_language=self.dominant_language,
            source_format=document.extension,
            extraction_mode="native_text",
            extraction_confidence=0.95,
            structural_confidence=0.95,
            llm_used=True,
            detected_languages=[self.dominant_language],
            has_mixed_language=False,
            fragment_analyses=fragment_analyses,
            coverage_notes=[],
            unmapped_fragment_ids=[],
            ambiguous_fragment_ids=[],
            requires_confirmation=False,
            confidence=0.9,
            raw_payload={"stub": True},
        )


if __name__ == "__main__":
    unittest.main()
