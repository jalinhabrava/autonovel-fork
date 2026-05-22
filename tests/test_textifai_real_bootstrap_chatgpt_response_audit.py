from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "chatgpt_response_schema_checklist.json"
GAP_REPORT_PATH = FIXTURE_ROOT / "expected" / "chatgpt_response_gap_report.json"
ISSUE_REPORT_PATH = FIXTURE_ROOT / "expected" / "bootstrap_prompt_schema_issue_report.json"


class TextifAIRealBootstrapChatGPTResponseAuditTests(unittest.TestCase):
    def test_sample_exists_and_is_parseable(self):
        self.assertTrue((FIXTURE_ROOT / "provider_samples" / "README.md").exists())
        self.assertTrue(SAMPLE_PATH.exists())
        payload = _load_json(SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("chapters", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")

    def test_schema_shape_and_chapter_identity(self):
        payload = _load_json(SAMPLE_PATH)
        chapters = payload.get("chapters") or []
        self.assertGreaterEqual(len(chapters), 1)
        chapter = chapters[0]
        for key in [
            "chapter_id",
            "chapter_title_original",
            "chapter_title_canonical",
            "sequence_index",
            "chapter_label_type",
            "chapter_number_in_label",
            "title_parse_signals",
            "chapter_summary",
            "characters",
            "places",
            "concepts",
            "events",
            "relations",
            "unresolved_mentions",
        ]:
            self.assertIn(key, chapter)
        self.assertEqual(chapter.get("chapter_id"), "ch_001")
        self.assertEqual(chapter.get("chapter_title_original"), "**（仮）証人**")
        self.assertEqual(chapter.get("chapter_title_canonical"), "（仮）証人")
        self.assertIn(chapter.get("chapter_label_type"), {"other", "prologue"})

    def test_useful_coverage_is_present_with_flexible_matching(self):
        payload = _load_json(SAMPLE_PATH)
        blob = json.dumps(payload, ensure_ascii=False)
        for token in [
            "アデルマン・レオフリック",
            "ティセイア王国",
            "杖の一族",
            "均衡",
            "赤子",
        ]:
            self.assertIn(token, blob)
        self.assertTrue(_contains_any(blob, ["王と杖", "王者の杖"]))
        self.assertTrue(_contains_any(blob, ["ベル", "舌のないベル"]))
        self.assertTrue(_contains_any(blob, ["崩壊", "破壊", "滅び"]))
        self.assertTrue(_contains_any(blob, ["救出", "救い出し", "逃亡"]))
        self.assertTrue(_contains_any(blob, ["抹消", "消し去られ", "公式記録からも消された"]))
        self.assertTrue(_contains_any(blob, ["摂政", "政治", "就任"]))

    def test_noise_and_review_behavior_is_cautious(self):
        payload = _load_json(SAMPLE_PATH)
        chapter = (payload.get("chapters") or [{}])[0]
        characters = chapter.get("characters") or []
        unresolved = chapter.get("unresolved_mentions") or []

        pronoun_entry = next((entry for entry in characters if entry.get("surface") == "私"), None)
        self.assertIsNotNone(pronoun_entry)
        assert pronoun_entry is not None
        self.assertEqual(pronoun_entry.get("naming_quality"), "pronoun_like")
        self.assertTrue(pronoun_entry.get("needs_review"))

        unresolved_surfaces = {entry.get("surface") for entry in unresolved}
        self.assertIn("お前", unresolved_surfaces)

        baby_entry = next((entry for entry in characters if entry.get("surface") == "赤子"), None)
        self.assertIsNotNone(baby_entry)
        assert baby_entry is not None
        self.assertEqual(baby_entry.get("naming_quality"), "descriptor")
        self.assertTrue(baby_entry.get("needs_review"))

        for surface in ["王", "王妃"]:
            entry = next((item for item in characters if item.get("surface") == surface), None)
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertTrue(entry.get("needs_review"))

        blob = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)

    def test_known_schema_limitation_objects_missing_is_recognized_without_failure(self):
        payload = _load_json(SAMPLE_PATH)
        chapter = (payload.get("chapters") or [{}])[0]
        self.assertNotIn("objects", chapter)
        concepts_blob = json.dumps(chapter.get("concepts") or [], ensure_ascii=False)
        unresolved_blob = json.dumps(chapter.get("unresolved_mentions") or [], ensure_ascii=False)
        self.assertTrue(_contains_any(concepts_blob + unresolved_blob, ["ベル", "舌のないベル"]))

        issues = _load_json(ISSUE_REPORT_PATH)
        issue_ids = {item.get("id") for item in issues.get("issues") or []}
        self.assertIn("chapter_schema_missing_objects_section", issue_ids)
        self.assertIn("artifact_retention_not_first_class", issue_ids)

    def test_checklist_gap_and_issue_reports_are_present_and_consistent(self):
        checklist = _load_json(CHECKLIST_PATH)
        gap_report = _load_json(GAP_REPORT_PATH)
        issue_report = _load_json(ISSUE_REPORT_PATH)
        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001")
        self.assertEqual(gap_report.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001")
        self.assertEqual(issue_report.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001")
        self.assertIn(
            gap_report.get("overall_assessment"),
            {"usable_with_minor_schema_fixes", "usable_with_major_prompt_fixes", "not_usable"},
        )
        self.assertTrue(gap_report.get("what_worked"))
        self.assertTrue(gap_report.get("schema_limitations_observed"))
        self.assertTrue(gap_report.get("prompt_limitations_observed"))
        self.assertTrue(issue_report.get("issues"))

    def test_provider_free_guarantee_files_only(self):
        for path in [SAMPLE_PATH, CHECKLIST_PATH, GAP_REPORT_PATH, ISSUE_REPORT_PATH]:
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", blob)
            self.assertNotIn("ANTHROPIC_API_KEY", blob)
            self.assertNotIn("https://api.", blob)
            self.assertNotIn("/runs/", blob)
            self.assertNotIn("/vault/", blob)


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
