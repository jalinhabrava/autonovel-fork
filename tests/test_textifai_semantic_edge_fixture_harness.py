from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/identity_alias_role")
MANIFEST_PATH = FIXTURE_ROOT / "fixture_manifest.json"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"


class TextifAISemanticEdgeFixtureHarnessTests(unittest.TestCase):
    def test_fixture_root_and_source_files_exist(self):
        self.assertTrue(FIXTURE_ROOT.exists())
        self.assertTrue(MANIFEST_PATH.exists())

        manifest = _load_json(MANIFEST_PATH)
        self.assertEqual(manifest.get("fixture_id"), "identity_alias_role")
        self.assertEqual(manifest.get("language"), "es")
        self.assertTrue(manifest.get("source_files"))

        for relative_path in manifest.get("source_files") or []:
            path = FIXTURE_ROOT / relative_path
            self.assertTrue(path.exists(), relative_path)
            self.assertTrue(path.is_file(), relative_path)

    def test_manifest_has_expected_semantic_sections(self):
        manifest = _load_json(MANIFEST_PATH)
        self.assertTrue(manifest.get("expected_canonical_entities"))
        self.assertTrue(manifest.get("expected_alias_cases"))
        self.assertTrue(manifest.get("expected_title_role_descriptor_cases"))
        self.assertTrue(manifest.get("expected_pronoun_suppression_cases"))
        self.assertTrue(manifest.get("expected_persistent_object_cases"))
        self.assertTrue(manifest.get("expected_ephemeral_mentions"))
        self.assertTrue(manifest.get("expected_relationships"))
        self.assertTrue(manifest.get("expected_review_signals"))
        self.assertTrue(manifest.get("language_agnostic_notes"))

    def test_expected_artifacts_exist_and_are_valid_json(self):
        expected_files = [
            EXPECTED_ROOT / "obsidian_import.json",
            EXPECTED_ROOT / "review_queue.json",
            EXPECTED_ROOT / "semantic_invariants_audit.json",
            EXPECTED_ROOT / "replay_drift_expectations.json",
        ]
        for path in expected_files:
            self.assertTrue(path.exists(), path)
            self.assertIsInstance(_load_json(path), dict)

    def test_fixture_is_safe_and_has_no_generated_logs(self):
        forbidden_names = {
            "web_ingestion_job.log",
            "web_ingestion_job.json",
            "obsidian_import_audit.json",
        }
        replay_input_root = FIXTURE_ROOT / "replay_input"
        if replay_input_root.exists():
            self.assertTrue((replay_input_root / "global_normalization.json").exists())
            chapter_outputs = replay_input_root / "chapter_outputs"
            self.assertTrue(chapter_outputs.exists())
            for chapter_id in ("ch_001", "ch_002", "ch_003"):
                self.assertTrue((chapter_outputs / f"{chapter_id}.json").exists())
        for path in FIXTURE_ROOT.rglob("*"):
            if not path.is_file():
                continue
            normalized = str(path).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)
            self.assertNotIn(path.name, forbidden_names)

    def test_manifest_paths_do_not_point_to_runs_or_vault(self):
        manifest = _load_json(MANIFEST_PATH)
        for relative_path in manifest.get("source_files") or []:
            normalized = str(relative_path).replace("\\", "/")
            self.assertFalse(normalized.startswith("runs/"), relative_path)
            self.assertFalse(normalized.startswith("vault/"), relative_path)
            self.assertNotIn("../runs", normalized, relative_path)
            self.assertNotIn("../vault", normalized, relative_path)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
