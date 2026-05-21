from __future__ import annotations

import json
import unittest
from pathlib import Path


class TextifAIFixtureHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_root = Path("tests/fixtures/textifai/minimal_novel")
        self.manifest_path = self.fixture_root / "fixture_manifest.json"

    def test_minimal_novel_fixture_exists_and_has_safe_structure(self):
        self.assertTrue(self.fixture_root.exists())
        self.assertTrue(self.fixture_root.is_dir())
        self.assertTrue(self.manifest_path.exists())

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["fixture_id"], "minimal_novel")
        self.assertTrue(str(manifest.get("language") or "").strip())
        self.assertTrue(manifest.get("expected_persistent_entities"))
        self.assertTrue(manifest.get("expected_relationships"))
        self.assertIn("expected_non_persistent_mentions", manifest)

        source_files = manifest.get("source_files") or []
        self.assertTrue(source_files)
        for relative_path in source_files:
            path = self.fixture_root / relative_path
            self.assertTrue(path.exists(), relative_path)
            self.assertTrue(path.is_file(), relative_path)

    def test_fixture_contains_no_generated_pipeline_artifacts(self):
        forbidden_names = {
            "obsidian_import.json",
            "review_queue.json",
            "semantic_invariants_audit.json",
            "web_ingestion_job.json",
        }
        found = {
            path.name
            for path in self.fixture_root.rglob("*")
            if path.is_file()
            and path.name in forbidden_names
            and "expected" not in path.parts
        }
        self.assertEqual(found, set())

    def test_fixture_manifest_does_not_point_to_runs_or_vault(self):
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        for relative_path in manifest.get("source_files") or []:
            normalized = str(relative_path).replace("\\", "/")
            self.assertFalse(normalized.startswith("runs/"), relative_path)
            self.assertFalse(normalized.startswith("vault/"), relative_path)
            self.assertNotIn("../runs", normalized, relative_path)
            self.assertNotIn("../vault", normalized, relative_path)


if __name__ == "__main__":
    unittest.main()
