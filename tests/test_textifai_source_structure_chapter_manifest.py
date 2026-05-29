"""Tests for source structure detection, chapter manifest, and evidence store."""

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / "tests/fixtures/textifai/source_structure_chapter_manifest/expected"


class SourceStructureChapterManifestTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path("/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai")
        self.assertTrue(self.project_root.exists(), f"Project not found at {self.project_root}")

    def test_reports_parse(self):
        for report_file in EXPECTED.glob("*.json"):
            data = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertIn("assessment", data, report_file.name)

    def test_source_structure_classifier_contract(self):
        report = json.loads((EXPECTED / "source_structure_classifier_contract_after_sp110.json").read_text())
        self.assertIn("structures", report)
        self.assertIn("chaptered", report["structures"])
        self.assertIn("unstructured", report["structures"])
        self.assertIn("recommended_pipelines", report)

    def test_chapter_manifest_contract(self):
        report = json.loads((EXPECTED / "chapter_manifest_contract_after_sp110.json").read_text())
        self.assertIn("schema", report)
        self.assertEqual(report["schema"], "textifai.chapter_manifest")
        self.assertIn("required_fields", report)

    def test_chapter_manifest_exists_and_valid(self):
        manifest_path = self.project_root / "chapters/chapter_manifest.json"
        self.assertTrue(manifest_path.exists(), "Chapter manifest not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_chapters"], 20)
        self.assertEqual(len(manifest["chapters"]), 20)
        # Check chapter IDs are sequential
        for i, ch in enumerate(manifest["chapters"]):
            expected_id = f"ch_{i+1:03d}"
            self.assertEqual(ch["chapter_id"], expected_id)
            self.assertEqual(ch["order"], i + 1)
            self.assertTrue(ch["char_count"] > 0)

    def test_deterministic_splitter_no_duplicates(self):
        manifest_path = self.project_root / "chapters/chapter_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = [ch["chapter_id"] for ch in manifest["chapters"]]
        paths = [ch["markdown_path"] for ch in manifest["chapters"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate chapter IDs found")
        self.assertEqual(len(paths), len(set(paths)), "Duplicate chapter paths found")

    def test_editor_chapter_source(self):
        report = json.loads((EXPECTED / "editor_chapter_source_after_sp110.json").read_text())
        self.assertTrue(report["editor_consumes_chapter_manifest"])
        self.assertTrue(report["editor_excludes_vault_tree"])
        self.assertTrue(report["editor_excludes_rglob"])

    def test_source_map_schema(self):
        sm_path = self.project_root / "evidence/source_map.json"
        self.assertTrue(sm_path.exists(), "Source map not found")
        sm = json.loads(sm_path.read_text(encoding="utf-8"))
        self.assertIn("schema", sm)
        self.assertEqual(sm["schema"], "textifai.source_map")
        self.assertEqual(len(sm["chapters"]), 20)

    def test_evidence_index_schema(self):
        ei_path = self.project_root / "evidence/evidence_index.json"
        self.assertTrue(ei_path.exists(), "Evidence index not found")
        ei = json.loads(ei_path.read_text(encoding="utf-8"))
        self.assertIn("schema", ei)
        self.assertEqual(ei["schema"], "textifai.evidence_index")
        self.assertGreater(len(ei["items"]), 0)

    def test_review_evidence_refs_have_chapter_label(self):
        report = json.loads((EXPECTED / "review_evidence_materialization_after_sp110.json").read_text())
        self.assertTrue(report["evidence_refs_have_chapter_label"])
        self.assertTrue(report["has_text_boolean"])

    def test_entitycard_runtime_wiring(self):
        report = json.loads((EXPECTED / "entitycard_runtime_wiring_fix_after_sp110.json").read_text())
        self.assertGreater(report["ren_relationship_count"], 0)
        self.assertTrue(report["author_markdown_hides_frontmatter"])

    def test_no_provider_calls(self):
        decision = json.loads((EXPECTED / "source_structure_chapter_manifest_decision_after_sp110.json").read_text())
        self.assertFalse(decision["provider_calls"])
        self.assertFalse(decision["write_back"])
        self.assertFalse(decision.get("private_data_staged", False))

    def test_no_source_prose_in_reports(self):
        for report_file in EXPECTED.glob("*.json"):
            text = report_file.read_text(encoding="utf-8")
            self.assertNotIn("Me llamaron muchas cosas", text, f"Source prose found in {report_file.name}")
            self.assertNotIn("mayordomo", text, f"Source prose found in {report_file.name}")

    def test_unstructured_document_policy(self):
        report = json.loads((EXPECTED / "unstructured_document_policy_after_sp110.json").read_text())
        self.assertEqual(report["policy"], "no_fake_chapters")
        self.assertTrue(report["no_chapter_manifest"])
        self.assertTrue(report["direct_chunking"])


if __name__ == "__main__":
    unittest.main()
