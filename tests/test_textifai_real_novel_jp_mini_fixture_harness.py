from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
MANIFEST_PATH = FIXTURE_ROOT / "fixture_manifest.json"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
SOURCE_ROOT = FIXTURE_ROOT / "source"

class TextifAIRealNovelJPMiniFixtureHarnessTests(unittest.TestCase):
    def test_fixture_root_and_expected_files_exist(self):
        self.assertTrue(FIXTURE_ROOT.exists())
        self.assertTrue((FIXTURE_ROOT / "README.md").exists())
        self.assertTrue((SOURCE_ROOT / "README.md").exists())
        self.assertTrue((SOURCE_ROOT / "ch_017_excerpt.md").exists())
        self.assertTrue((SOURCE_ROOT / "ch_018_excerpt.md").exists())
        self.assertTrue((SOURCE_ROOT / "ch_019_excerpt.md").exists())
        self.assertTrue(MANIFEST_PATH.exists())
        self.assertTrue((EXPECTED_ROOT / "README.md").exists())
        self.assertTrue((EXPECTED_ROOT / "usefulness_checklist.json").exists())
        self.assertTrue((EXPECTED_ROOT / "replay_drift_expectations.json").exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "README.md").exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "global_normalization.json").exists())
        for chapter_id in ("ch_017", "ch_018", "ch_019"):
            self.assertTrue((REPLAY_INPUT_ROOT / "chapter_outputs" / f"{chapter_id}.json").exists())

    def test_manifest_declares_real_novel_japanese_provider_free_usefulness_scope(self):
        manifest = _load_json(MANIFEST_PATH)
        self.assertEqual(manifest.get("fixture_id"), "real_novel_jp_linked_power")
        self.assertEqual(manifest.get("source_language"), "ja")
        self.assertEqual(manifest.get("source_title"), "王者の杖")
        self.assertEqual(manifest.get("selected_chapters"), ["ch_017", "ch_018", "ch_019"])
        self.assertEqual(manifest.get("purpose"), "real_novel_usefulness_audit")
        self.assertFalse(manifest.get("provider_calls"))
        self.assertTrue(manifest.get("ip_privacy_note"))

    def test_source_excerpts_are_short_and_safe(self):
        for path in SOURCE_ROOT.glob("*_excerpt.md"):
            text = path.read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), 40, path)
            self.assertLess(len(text), 1200, path)
        for path in FIXTURE_ROOT.rglob("*"):
            if not path.is_file():
                continue
            normalized = str(path).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)
            self.assertNotIn(path.name, {"web_ingestion_job.json", "web_ingestion_job.log"})

    def test_expected_json_files_are_valid(self):
        checklist = _load_json(EXPECTED_ROOT / "usefulness_checklist.json")
        expectations = _load_json(EXPECTED_ROOT / "replay_drift_expectations.json")
        self.assertTrue(checklist.get("must_have"))
        self.assertTrue(checklist.get("should_have"))
        self.assertTrue(checklist.get("accepted_temporary_drift"))
        self.assertTrue(checklist.get("non_negotiable_failures"))
        for key in [
            "manual_expectation",
            "current_observed_behavior",
            "accepted_temporary_drift",
            "resolved_current_behavior",
            "known_current_drift",
            "non_negotiable_failures",
            "future_desired_behavior",
            "language_agnostic_notes",
            "real_novel_usefulness_notes",
        ]:
            self.assertIn(key, expectations)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
