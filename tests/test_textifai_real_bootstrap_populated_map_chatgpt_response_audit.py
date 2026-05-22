from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
BASELINE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051.json"
POPULATED_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "populated_map_chapter_response_schema_checklist.json"
COMPARISON_PATH = FIXTURE_ROOT / "expected" / "sp052_vs_populated_map_response_comparison_report.json"
ISSUE_REPORT_PATH = FIXTURE_ROOT / "expected" / "bootstrap_populated_map_issue_report_after_sp054.json"


class TextifAIRealBootstrapPopulatedMapChatGPTResponseAuditTests(unittest.TestCase):
    def test_sample_exists_and_is_parseable(self):
        self.assertTrue(POPULATED_SAMPLE_PATH.exists())
        payload = _load_json(POPULATED_SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("chapters", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")

    def test_schema_and_chapter_identity(self):
        chapter = _first_chapter(_load_json(POPULATED_SAMPLE_PATH))
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
        self.assertEqual(chapter.get("chapter_id"), "ch_001")
        self.assertEqual(chapter.get("chapter_title_original"), "**（仮）証人**")
        self.assertEqual(chapter.get("chapter_title_canonical"), "（仮）証人")
        self.assertIn(chapter.get("chapter_label_type"), {"other", "prologue"})

    def test_v2_contract_is_present(self):
        chapter = _first_chapter(_load_json(POPULATED_SAMPLE_PATH))
        objects = chapter.get("objects") or []
        events = chapter.get("events") or []
        relations = chapter.get("relations") or []

        self.assertIsInstance(objects, list)
        self.assertGreaterEqual(len(objects), 1)
        self.assertTrue(any("object_subkind" in obj for obj in objects))
        self.assertTrue(any("retention_reason" in obj for obj in objects))

        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(all("event_importance" in event for event in events))

        self.assertGreaterEqual(len(relations), 1)
        for relation in relations:
            for key in ["relation_category", "relation_label", "relation_summary", "evidence"]:
                self.assertIn(key, relation)
        self.assertFalse(any("relation_type" in relation and "relation_category" not in relation for relation in relations))

    def test_populated_map_canonical_reuse(self):
        chapter = _first_chapter(_load_json(POPULATED_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        places = chapter.get("places") or []
        concepts = chapter.get("concepts") or []
        objects = chapter.get("objects") or []

        narrator = _find_by_surface(characters, "私")
        self.assertIsNotNone(narrator)
        assert narrator is not None
        self.assertEqual(narrator.get("canonical"), "証人")
        self.assertEqual(narrator.get("canonical_candidate"), "証人")
        self.assertTrue(narrator.get("needs_review"))
        self.assertIn(narrator.get("review_state"), {"review", "local_candidate", "candidate"})

        bell = _find_by_surface(objects, "舌のない、ベル")
        self.assertIsNotNone(bell)
        assert bell is not None
        self.assertEqual(bell.get("canonical"), "ベル")
        self.assertEqual(bell.get("object_subkind"), "ritual_key")
        self.assertTrue(bool(str(bell.get("retention_reason") or "").strip()))

        castle = _find_by_surface(places, "城")
        self.assertIsNotNone(castle)
        assert castle is not None
        self.assertEqual(castle.get("canonical"), "王城")

        queen = _find_by_surface(characters, "王妃")
        self.assertIsNotNone(queen)
        assert queen is not None
        self.assertEqual(queen.get("canonical"), "ネリス女王")
        self.assertTrue(queen.get("needs_review"))

        baby = _find_by_surface(characters, "赤子")
        self.assertIsNotNone(baby)
        assert baby is not None
        self.assertTrue(baby.get("needs_review"))

        ouja = _find_by_surface(concepts, "王者の杖")
        self.assertIsNotNone(ouja)
        assert ouja is not None
        self.assertTrue(ouja.get("needs_review"))

    def test_useful_coverage_is_preserved(self):
        payload = _load_json(POPULATED_SAMPLE_PATH)
        blob = _blob(payload)
        for token in ["アデルマン・レオフリック", "ティセイア王国", "杖の一族", "均衡", "赤子", "証人"]:
            self.assertIn(token, blob)
        self.assertTrue(_contains_any(blob, ["王と杖", "王者の杖"]))
        self.assertTrue(_contains_any(blob, ["ベル", "舌のないベル"]))
        self.assertTrue(_contains_any(blob, ["崩壊", "破壊", "滅び"]))
        self.assertTrue(_contains_any(blob, ["救出", "救い出し", "逃亡"]))
        self.assertTrue(_contains_any(blob, ["抹消", "消し去られ", "沈黙"]))
        self.assertTrue(_contains_any(blob, ["摂政", "就任", "政治的秩序"]))

    def test_improvements_vs_sp052(self):
        baseline_chapter = _first_chapter(_load_json(BASELINE_PATH))
        populated_chapter = _first_chapter(_load_json(POPULATED_SAMPLE_PATH))

        baseline_narrator = _find_by_surface(baseline_chapter.get("characters") or [], "私")
        populated_narrator = _find_by_surface(populated_chapter.get("characters") or [], "私")
        self.assertIsNotNone(baseline_narrator)
        self.assertIsNotNone(populated_narrator)
        assert baseline_narrator is not None and populated_narrator is not None
        self.assertNotEqual(baseline_narrator.get("canonical"), "証人")
        self.assertEqual(populated_narrator.get("canonical"), "証人")
        self.assertTrue(populated_narrator.get("needs_review"))

        baseline_places_blob = _blob(baseline_chapter.get("places") or [])
        populated_places_blob = _blob(populated_chapter.get("places") or [])
        self.assertTrue("王城" not in baseline_places_blob or "城" in baseline_places_blob)
        self.assertIn("王城", populated_places_blob)

        baseline_objects = baseline_chapter.get("objects") or []
        populated_objects = populated_chapter.get("objects") or []
        self.assertTrue(any("ベル" in _blob(item) for item in baseline_objects))
        self.assertTrue(any(item.get("canonical") == "ベル" for item in populated_objects if isinstance(item, dict)))

        populated_relations_blob = _blob(populated_chapter.get("relations") or [])
        self.assertIn("証人", populated_relations_blob)
        self.assertIn("ベル", populated_relations_blob)

        populated_concepts_blob = _blob(populated_chapter.get("concepts") or [])
        self.assertTrue(_contains_any(populated_concepts_blob, ["review", "needs_review"]))
        self.assertTrue("王者の杖" in populated_concepts_blob or "王と杖" in populated_concepts_blob)

    def test_review_and_no_auto_promotion_safety(self):
        chapter = _first_chapter(_load_json(POPULATED_SAMPLE_PATH))
        blob = _blob(chapter)

        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)

        narrator = _find_by_surface(chapter.get("characters") or [], "私")
        self.assertIsNotNone(narrator)
        assert narrator is not None
        self.assertEqual(narrator.get("naming_quality"), "pronoun_like")
        self.assertTrue(narrator.get("needs_review"))

        baby = _find_by_surface(chapter.get("characters") or [], "赤子")
        self.assertIsNotNone(baby)
        assert baby is not None
        self.assertTrue(baby.get("needs_review"))

        queen = _find_by_surface(chapter.get("characters") or [], "王妃")
        self.assertIsNotNone(queen)
        assert queen is not None
        self.assertTrue(queen.get("needs_review"))

        unresolved_surfaces = {item.get("surface") for item in chapter.get("unresolved_mentions") or [] if isinstance(item, dict)}
        self.assertTrue({"後継者", "杖", "お前"} <= unresolved_surfaces)

    def test_checklist_comparison_and_issue_reports(self):
        checklist = _load_json(CHECKLIST_PATH)
        comparison = _load_json(COMPARISON_PATH)
        issue_report = _load_json(ISSUE_REPORT_PATH)

        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054")
        self.assertEqual(comparison.get("overall_assessment"), "populated_map_improves_resolution_without_auto_promotion")
        self.assertEqual(comparison.get("chapter_id"), "ch_001")
        self.assertEqual(comparison.get("source_language"), "ja")
        self.assertTrue(comparison.get("what_improved"))
        self.assertTrue(comparison.get("downstream_risks"))

        issue_ids = {item.get("id"): item.get("status") for item in issue_report.get("issues") or []}
        self.assertEqual(issue_ids.get("empty_canonical_entity_map_in_capture"), "improved_resolved_for_capture_harness_audit")
        self.assertEqual(issue_ids.get("canonical_reuse_in_chapter_prompt"), "improved")
        self.assertEqual(issue_ids.get("object_retention_with_map"), "improved")
        self.assertEqual(issue_ids.get("relation_endpoint_resolution"), "improved")
        self.assertEqual(issue_ids.get("review_safety_under_populated_map"), "acceptable")

    def test_provider_free_guarantee_files_only(self):
        for path in [POPULATED_SAMPLE_PATH, CHECKLIST_PATH, COMPARISON_PATH, ISSUE_REPORT_PATH]:
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
