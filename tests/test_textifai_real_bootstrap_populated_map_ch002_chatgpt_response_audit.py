from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
CH001_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054.json"
CH002_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_002_populated_map_after_sp055.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "populated_map_ch002_response_schema_checklist.json"
GENERALIZATION_REPORT_PATH = FIXTURE_ROOT / "expected" / "ch001_ch002_populated_map_generalization_report.json"
ISSUE_REPORT_PATH = FIXTURE_ROOT / "expected" / "bootstrap_populated_map_ch002_issue_report.json"


class TextifAIRealBootstrapPopulatedMapCh002ChatGPTResponseAuditTests(unittest.TestCase):
    def test_sample_exists_and_is_parseable(self):
        self.assertTrue(CH002_SAMPLE_PATH.exists())
        payload = _load_json(CH002_SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("chapters", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")

    def test_schema_and_chapter_identity(self):
        chapter = _first_chapter(_load_json(CH002_SAMPLE_PATH))
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
        self.assertEqual(chapter.get("chapter_id"), "ch_002")
        self.assertEqual(chapter.get("chapter_title_original"), "**第01話：セラの壊れた魔力と黙された継承**")
        self.assertEqual(chapter.get("chapter_title_canonical"), "第01話：セラの壊れた魔力と黙された継承")
        self.assertEqual(chapter.get("chapter_label_type"), "episode")
        self.assertEqual(chapter.get("chapter_number_in_label"), 1)

    def test_v2_contract_is_observable(self):
        chapter = _first_chapter(_load_json(CH002_SAMPLE_PATH))
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

    def test_populated_map_canonical_reuse_for_ch002(self):
        chapter = _first_chapter(_load_json(CH002_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        places = chapter.get("places") or []
        concepts = chapter.get("concepts") or []
        objects = chapter.get("objects") or []
        relations = chapter.get("relations") or []

        protagonist = _find_by_surface(characters, "私")
        self.assertIsNotNone(protagonist)
        assert protagonist is not None
        self.assertEqual(protagonist.get("canonical"), "セラ")
        self.assertEqual(protagonist.get("canonical_candidate"), "セラ")

        regent = _find_by_surface(characters, "摂政")
        self.assertIsNotNone(regent)
        assert regent is not None
        self.assertEqual(regent.get("canonical"), "アデルマン・レオフリック")

        mother = _find_by_surface(characters, "母様")
        self.assertIsNotNone(mother)
        assert mother is not None
        self.assertEqual(mother.get("canonical"), "ネリス女王")
        self.assertTrue(mother.get("needs_review"))

        self.assertTrue(any(item.get("canonical") == "王城" for item in places if isinstance(item, dict)))
        self.assertTrue(_contains_any(_blob(places), ["王族専用の訓練場", "training_ground", "塔"]))

        magic = _find_by_surface(concepts, "セラの壊れた魔力")
        self.assertIsNotNone(magic)
        assert magic is not None
        self.assertEqual(magic.get("canonical"), "セラの魔力")

        catalyst_concept = _find_by_surface(concepts, "触媒")
        self.assertIsNotNone(catalyst_concept)
        assert catalyst_concept is not None
        self.assertEqual(catalyst_concept.get("canonical"), "触媒")

        objects_blob = _blob(objects)
        self.assertIn("アルモナイトの珠", objects_blob)
        self.assertTrue(any(item.get("object_subkind") == "catalyst" for item in objects if isinstance(item, dict)))
        self.assertIn("セラの魔力", _blob(relations))

    def test_useful_coverage_for_ch002_profile(self):
        payload = _load_json(CH002_SAMPLE_PATH)
        blob = _blob(payload)
        for token in ["セラ", "王城", "セラの魔力", "触媒", "アルモナイトの珠"]:
            self.assertIn(token, blob)
        self.assertTrue(_contains_any(blob, ["アデルマン・レオフリック", "摂政"]))
        self.assertTrue(_contains_any(blob, ["ネリス女王", "母様"]))
        self.assertTrue(_contains_any(blob, ["王族専用の訓練場", "訓練場", "training_ground"]))
        self.assertTrue(_contains_any(blob, ["配置", "継承の印", "拒絶"]))
        self.assertTrue(_contains_any(blob, ["孤立", "誰も来なくなった", "補助もいない"]))
        self.assertTrue(_contains_any(blob, ["触媒破壊", "壊した", "爆発した", "灰になった"]))
        self.assertTrue(_contains_any(blob, ["防御壁", "塔", "崩れた", "破壊"]))
        self.assertTrue(_contains_any(blob, ["逃走", "走り出した", "ここにはいられない"]))

    def test_review_and_no_auto_promotion_safety(self):
        chapter = _first_chapter(_load_json(CH002_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        unresolved = chapter.get("unresolved_mentions") or []
        objects = chapter.get("objects") or []
        concepts = chapter.get("concepts") or []
        blob = _blob(chapter)

        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)

        father = _find_by_surface(unresolved, "父様")
        self.assertIsNotNone(father)

        mother = _find_by_surface(characters, "母様")
        self.assertIsNotNone(mother)
        assert mother is not None
        self.assertTrue(mother.get("needs_review"))

        for item in objects:
            if not isinstance(item, dict):
                continue
            if item.get("retention_reason") == "temporary_scene_use":
                self.assertIn(item.get("review_state"), {"local_candidate", "candidate", "review"})

        sera = _find_by_surface(characters, "私")
        self.assertIsNotNone(sera)
        assert sera is not None
        self.assertEqual(sera.get("canonical"), "セラ")
        self.assertEqual(sera.get("review_state"), "canonical")

        regent = _find_by_surface(characters, "摂政")
        self.assertIsNotNone(regent)
        assert regent is not None
        self.assertEqual(regent.get("canonical"), "アデルマン・レオフリック")

        inheritance = _find_by_surface(concepts, "黙された継承")
        self.assertIsNotNone(inheritance)
        assert inheritance is not None
        self.assertTrue(inheritance.get("needs_review"))

    def test_generalization_vs_ch001_is_supported_by_observed_properties(self):
        ch001 = _first_chapter(_load_json(CH001_SAMPLE_PATH))
        ch002 = _first_chapter(_load_json(CH002_SAMPLE_PATH))
        ch001_blob = _blob(ch001)
        ch002_blob = _blob(ch002)

        self.assertIn("証人", ch001_blob)
        self.assertIn("ベル", ch001_blob)
        self.assertIn("杖の一族", ch001_blob)

        self.assertIn("セラ", ch002_blob)
        self.assertIn("セラの魔力", ch002_blob)
        self.assertIn("触媒", ch002_blob)
        self.assertIn("王族専用の訓練場", ch002_blob)

        self.assertTrue(ch001.get("objects"))
        self.assertTrue(ch002.get("objects"))
        self.assertTrue(all("event_importance" in event for event in ch001.get("events") or []))
        self.assertTrue(all("event_importance" in event for event in ch002.get("events") or []))

        for chapter in [ch001, ch002]:
            for relation in chapter.get("relations") or []:
                self.assertIn("relation_category", relation)
                self.assertIn("relation_label", relation)

    def test_checklist_report_and_issue_report_are_consistent(self):
        checklist = _load_json(CHECKLIST_PATH)
        report = _load_json(GENERALIZATION_REPORT_PATH)
        issues = _load_json(ISSUE_REPORT_PATH)

        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_002_populated_map_after_sp055")
        self.assertEqual(report.get("ch002_sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_002_populated_map_after_sp055")
        self.assertIn(report.get("overall_assessment"), {"populated_map_generalizes_to_ch002", "partially_generalizes_needs_more_fixes", "does_not_generalize"})
        self.assertEqual(report.get("overall_assessment"), "populated_map_generalizes_to_ch002")
        self.assertTrue(report.get("what_generalized"))
        self.assertTrue(report.get("downstream_risks"))

        issue_ids = {item.get("id"): item.get("status") for item in issues.get("issues") or []}
        self.assertEqual(issue_ids.get("populated_map_beyond_prologue"), "improved_confirmed_for_ch002")
        self.assertEqual(issue_ids.get("canonical_reuse_explicit_protagonist"), "improved_confirmed")
        self.assertEqual(issue_ids.get("catalyst_object_handling"), "improved_confirmed")
        self.assertEqual(issue_ids.get("event_priority_outburst_escape"), "improved_confirmed")

    def test_provider_free_guarantee_files_only(self):
        for path in [CH002_SAMPLE_PATH, CHECKLIST_PATH, GENERALIZATION_REPORT_PATH, ISSUE_REPORT_PATH]:
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


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _blob(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
