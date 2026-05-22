from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
CH001_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054.json"
CH002_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_002_populated_map_after_sp055.json"
CH003_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_003_populated_map_after_sp056.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "populated_map_ch003_response_schema_checklist.json"
GENERALIZATION_REPORT_PATH = FIXTURE_ROOT / "expected" / "ch001_ch002_ch003_populated_map_generalization_report.json"
ISSUE_REPORT_PATH = FIXTURE_ROOT / "expected" / "bootstrap_populated_map_ch003_issue_report.json"

class TextifAIRealBootstrapPopulatedMapCh003ChatGPTResponseAuditTests(unittest.TestCase):
    def test_sample_exists_and_is_parseable(self):
        self.assertTrue(CH003_SAMPLE_PATH.exists())
        payload = _load_json(CH003_SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("chapters", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")

    def test_schema_and_chapter_identity(self):
        chapter = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        for key in [
            "chapter_extraction_schema_version",
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
            "objects",
            "events",
            "relations",
            "unresolved_mentions",
        ]:
            self.assertIn(key, chapter)
        self.assertEqual(chapter.get("chapter_extraction_schema_version"), "v2")
        self.assertEqual(chapter.get("chapter_id"), "ch_003")
        self.assertEqual(chapter.get("chapter_title_original"), "**第02話：セラの逃げ足と形の限界**")
        self.assertEqual(chapter.get("chapter_title_canonical"), "第02話：セラの逃げ足と形の限界")
        self.assertEqual(chapter.get("chapter_label_type"), "episode")
        self.assertEqual(chapter.get("chapter_number_in_label"), 2)

    def test_v2_contract_is_observable(self):
        chapter = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        objects = chapter.get("objects") or []
        events = chapter.get("events") or []
        relations = chapter.get("relations") or []

        self.assertIsInstance(objects, list)
        if objects:
            self.assertTrue(all("object_subkind" in item for item in objects))
            self.assertTrue(all("retention_reason" in item for item in objects))
            self.assertTrue(all(item.get("needs_review") is not None or item.get("review_state") for item in objects))

        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(all("event_importance" in event for event in events))
        self.assertTrue({event.get("event_importance") for event in events} <= {"major", "supporting", "local"})

        self.assertGreaterEqual(len(relations), 1)
        for relation in relations:
            for key in ["relation_category", "relation_label", "relation_summary", "evidence"]:
                self.assertIn(key, relation)
            self.assertIsInstance(relation.get("evidence"), list)
        self.assertFalse(any("relation_type" in relation and "relation_category" not in relation for relation in relations))

    def test_populated_map_canonical_reuse_for_ch003(self):
        chapter = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        places = chapter.get("places") or []
        concepts = chapter.get("concepts") or []
        objects = chapter.get("objects") or []
        events = chapter.get("events") or []
        blob = _blob(chapter)

        protagonist = _find_by_surface(characters, "私")
        self.assertIsNotNone(protagonist)
        assert protagonist is not None
        self.assertEqual(protagonist.get("canonical"), "セラ")
        self.assertEqual(protagonist.get("canonical_candidate"), "セラ")

        masked = _find_by_surface(characters, "仮面の男")
        self.assertIsNotNone(masked)
        assert masked is not None
        self.assertEqual(masked.get("canonical"), "仮面の男")
        self.assertTrue(masked.get("needs_review"))
        self.assertEqual(masked.get("naming_quality"), "descriptor")

        cuffs = _find_by_surface(objects, "手枷")
        self.assertIsNotNone(cuffs)
        assert cuffs is not None
        self.assertEqual(cuffs.get("canonical"), "封印の手枷")
        self.assertEqual(cuffs.get("review_state"), "canonical")

        magic = _find_by_surface(concepts, "セラの魔力")
        self.assertIsNotNone(magic)
        assert magic is not None
        self.assertEqual(magic.get("canonical"), "セラの魔力")
        self.assertEqual(magic.get("entity_subkind"), "magic_anomaly")

        self.assertTrue(any(item.get("canonical") == "王城" for item in places if isinstance(item, dict)))
        self.assertIn("塔", blob)
        self.assertTrue(any(item.get("canonical") == "セラの逃走" for item in events if isinstance(item, dict)))
        self.assertIn("追跡型の魔導珠", blob)
        self.assertIn("軽量型の魔導機", blob)
        self.assertIn("長い槍みたいな武器", blob)

    def test_useful_coverage_for_chase_sealing_profile(self):
        chapter = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        blob = _blob(chapter)
        for token in [
            "セラ",
            "仮面の男",
            "封印の手枷",
            "セラの魔力",
            "王城",
            "塔",
            "追跡型の魔導珠",
            "長い槍みたいな武器",
            "セラの逃走",
            "遮断",
            "拒絶反応",
        ]:
            self.assertIn(token, blob)

        events_blob = _blob(chapter.get("events") or [])
        for token in ["塔外脱出", "再確保", "包囲", "遮断未遂", "形が崩れる"]:
            self.assertIn(token, events_blob)

    def test_review_safety_and_no_unsafe_promotion(self):
        chapter = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        concepts = chapter.get("concepts") or []
        unresolved = chapter.get("unresolved_mentions") or []
        objects = chapter.get("objects") or []
        blob = _blob(chapter)

        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)
        self.assertNotIn("アデルマン・レオフリック", blob)

        masked = _find_by_surface(characters, "仮面の男")
        self.assertIsNotNone(masked)
        assert masked is not None
        self.assertEqual(masked.get("canonical"), "仮面の男")
        self.assertTrue(masked.get("needs_review"))

        pursuers = _find_by_surface(characters, "やつら")
        self.assertIsNotNone(pursuers)
        assert pursuers is not None
        self.assertIn(pursuers.get("review_state"), {"local_candidate", "candidate", "review"})
        self.assertTrue(pursuers.get("needs_review"))

        shape_limit = _find_by_surface(concepts, "形の限界")
        self.assertIsNotNone(shape_limit)
        assert shape_limit is not None
        self.assertTrue(shape_limit.get("needs_review"))
        self.assertIn(shape_limit.get("review_state"), {"local_candidate", "candidate", "review"})

        attraction = _find_by_surface(unresolved, "胸の奥を引っぱってくるもの")
        self.assertIsNotNone(attraction)

        for item in objects:
            if not isinstance(item, dict):
                continue
            if item.get("surface") in {"追跡型の魔導珠", "軽量型の魔導機", "長い槍みたいな武器"}:
                self.assertIn(item.get("review_state"), {"local_candidate", "candidate", "review"})

    def test_generalization_vs_ch001_ch002_is_supported_by_observed_properties(self):
        ch001 = _first_chapter(_load_json(CH001_SAMPLE_PATH))
        ch002 = _first_chapter(_load_json(CH002_SAMPLE_PATH))
        ch003 = _first_chapter(_load_json(CH003_SAMPLE_PATH))
        ch001_blob = _blob(ch001)
        ch002_blob = _blob(ch002)
        ch003_blob = _blob(ch003)

        self.assertIn("証人", ch001_blob)
        self.assertIn("ベル", ch001_blob)
        self.assertIn("杖の一族", ch001_blob)
        self.assertIn("セラの魔力", ch002_blob)
        self.assertIn("触媒", ch002_blob)
        self.assertIn("王族専用の訓練場", ch002_blob)
        self.assertIn("仮面の男", ch003_blob)
        self.assertIn("封印の手枷", ch003_blob)
        self.assertIn("追跡型の魔導珠", ch003_blob)

        for chapter in [ch001, ch002, ch003]:
            self.assertTrue(chapter.get("objects"))
            self.assertTrue(all("event_importance" in event for event in chapter.get("events") or []))
            for relation in chapter.get("relations") or []:
                self.assertIn("relation_category", relation)
                self.assertIn("relation_label", relation)

    def test_checklist_report_and_issue_report_are_consistent(self):
        checklist = _load_json(CHECKLIST_PATH)
        report = _load_json(GENERALIZATION_REPORT_PATH)
        issues = _load_json(ISSUE_REPORT_PATH)

        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_003_populated_map_after_sp056")
        self.assertEqual(report.get("ch003_sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_003_populated_map_after_sp056")
        self.assertIn(report.get("overall_assessment"), {"populated_map_generalizes_to_ch003", "partially_generalizes_needs_more_fixes", "does_not_generalize"})
        self.assertEqual(report.get("overall_assessment"), "populated_map_generalizes_to_ch003")
        self.assertTrue(report.get("what_generalized"))
        self.assertTrue(report.get("downstream_risks"))

        improved = {item.get("issue"): item.get("status") for item in issues.get("potentially_improved_or_confirmed") or []}
        self.assertEqual(improved.get("populated_map_generalization_across_three_chapter_profiles"), "improved")
        self.assertEqual(improved.get("review_safe_handling_of_unnamed_enemy"), "improved")
        self.assertEqual(improved.get("first_class_handling_of_sealing_artifact"), "improved")

    def test_provider_free_guarantee_files_only(self):
        for path in [CH003_SAMPLE_PATH, CHECKLIST_PATH, GENERALIZATION_REPORT_PATH, ISSUE_REPORT_PATH]:
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", blob)
            self.assertNotIn("ANTHROPIC_API_KEY", blob)
            self.assertNotIn("https://api.", blob)
            self.assertNotIn("/runs/", blob)
            self.assertNotIn("/vault/", blob)

def _first_chapter(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = payload.get("chapters") or []
    assert chapters
    return chapters[0]

def _find_by_surface(items: list[dict[str, Any]], surface: str) -> dict[str, Any] | None:
    return next((item for item in items if isinstance(item, dict) and item.get("surface") == surface), None)

def _blob(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
