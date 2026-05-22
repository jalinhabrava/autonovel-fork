from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "provider_comparison_checklist.json"
GAP_REPORT_PATH = FIXTURE_ROOT / "expected" / "provider_extraction_gap_report.json"


class TextifAIRealNovelJPProviderComparisonAuditTests(unittest.TestCase):
    def test_provider_comparison_artifacts_exist_and_parse(self):
        self.assertTrue(CHECKLIST_PATH.exists())
        self.assertTrue(GAP_REPORT_PATH.exists())
        checklist = _load_json(CHECKLIST_PATH)
        gap_report = _load_json(GAP_REPORT_PATH)
        self.assertTrue(checklist)
        self.assertTrue(gap_report)

    def test_checklist_has_required_sections_and_valid_score(self):
        checklist = _load_json(CHECKLIST_PATH)
        for key in [
            "must_have_coverage",
            "should_have_coverage",
            "false_positive_risks",
            "pronoun_promotion_guard",
            "object_retention_guard",
            "lore_concept_retention",
            "relationship_retention",
            "event_retention",
            "shape_compatibility",
            "author_usefulness_score",
            "non_negotiable_failures",
        ]:
            self.assertIn(key, checklist)
        self.assertIn(checklist.get("author_usefulness_score"), {"usable", "partially_usable", "not_usable"})

    def test_gap_report_honestly_identifies_matches_and_weaker_areas(self):
        gap_report = _load_json(GAP_REPORT_PATH)
        for key in [
            "what_matched_curated",
            "what_was_missing",
            "what_was_weaker_than_curated",
            "false_positive_risks",
            "prompt_improvement_notes",
            "downstream_risk_notes",
            "author_review_notes",
            "overall_assessment",
        ]:
            self.assertIn(key, gap_report)
        self.assertTrue(gap_report.get("what_matched_curated"))
        self.assertTrue(gap_report.get("prompt_improvement_notes"))

    def test_non_negotiable_failures_cover_provider_calls_pronouns_bell_and_writeback(self):
        checklist = _load_json(CHECKLIST_PATH)
        failures = checklist.get("non_negotiable_failures") or []
        for required in [
            "provider call in tests",
            "pronoun promoted",
            "ベル missing",
            "Ren/Sera linked magic missing",
            "JSON invalid",
            "full chapter committed",
            "write-back",
        ]:
            self.assertIn(required, failures)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

