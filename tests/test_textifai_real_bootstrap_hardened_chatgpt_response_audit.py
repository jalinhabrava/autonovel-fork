from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
BASELINE_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json"
HARDENED_SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "chatgpt_response_after_sp051_schema_checklist.json"
COMPARISON_REPORT_PATH = FIXTURE_ROOT / "expected" / "sp050_vs_sp051_response_comparison_report.json"
ISSUE_REPORT_PATH = FIXTURE_ROOT / "expected" / "bootstrap_prompt_schema_issue_report_after_sp051.json"


class TextifAIRealBootstrapHardenedChatGPTResponseAuditTests(unittest.TestCase):
    def test_hardened_sample_exists_and_is_parseable(self):
        self.assertTrue(HARDENED_SAMPLE_PATH.exists())
        payload = _load_json(HARDENED_SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("chapters", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")

    def test_schema_shape_and_chapter_identity(self):
        chapter = _first_chapter(_load_json(HARDENED_SAMPLE_PATH))
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

    def test_v2_contract_objects_events_and_relations(self):
        chapter = _first_chapter(_load_json(HARDENED_SAMPLE_PATH))
        objects = chapter.get("objects") or []
        events = chapter.get("events") or []
        relations = chapter.get("relations") or []

        self.assertIsInstance(objects, list)
        self.assertGreaterEqual(len(objects), 1)
        self.assertTrue(any("object_subkind" in item for item in objects))
        self.assertTrue(any("retention_reason" in item for item in objects))
        self.assertTrue(any(item.get("needs_review") is not None or item.get("review_state") for item in objects))

        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(all("event_importance" in item for item in events))
        self.assertTrue({item.get("event_importance") for item in events} <= {"major", "supporting", "local"})

        self.assertGreaterEqual(len(relations), 1)
        for relation in relations:
            for key in ["relation_category", "relation_label", "relation_summary", "evidence"]:
                self.assertIn(key, relation)
            self.assertIsInstance(relation.get("evidence"), list)
        self.assertFalse(any("relation_type" in relation and "relation_category" not in relation for relation in relations))

    def test_useful_coverage_is_preserved_with_flexible_matching(self):
        payload = _load_json(HARDENED_SAMPLE_PATH)
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
        self.assertTrue(_contains_any(blob, ["抹消", "消し去られ", "公式記録"]))
        self.assertTrue(_contains_any(blob, ["摂政", "政治", "就任"]))

    def test_improvements_vs_sp050_are_observable(self):
        baseline_chapter = _first_chapter(_load_json(BASELINE_SAMPLE_PATH))
        hardened_chapter = _first_chapter(_load_json(HARDENED_SAMPLE_PATH))

        baseline_objects = baseline_chapter.get("objects")
        baseline_concepts_blob = json.dumps(baseline_chapter.get("concepts") or [], ensure_ascii=False)
        baseline_unresolved_blob = json.dumps(baseline_chapter.get("unresolved_mentions") or [], ensure_ascii=False)
        self.assertTrue(baseline_objects in (None, []))
        self.assertTrue(_contains_any(baseline_concepts_blob + baseline_unresolved_blob, ["ベル", "舌のないベル"]))

        hardened_objects_blob = json.dumps(hardened_chapter.get("objects") or [], ensure_ascii=False)
        self.assertTrue(_contains_any(hardened_objects_blob, ["ベル", "舌のないベル"]))
        self.assertTrue(any(item.get("event_importance") for item in hardened_chapter.get("events") or []))
        self.assertTrue(any(item.get("relation_category") and item.get("relation_label") for item in hardened_chapter.get("relations") or []))

        baseline_blob = json.dumps(baseline_chapter, ensure_ascii=False)
        hardened_blob = json.dumps(hardened_chapter, ensure_ascii=False)
        for token in ["アデルマン・レオフリック", "ティセイア王国", "杖の一族", "均衡", "赤子"]:
            self.assertIn(token, baseline_blob)
            self.assertIn(token, hardened_blob)

    def test_empty_canonical_map_review_behavior_is_cautious(self):
        chapter = _first_chapter(_load_json(HARDENED_SAMPLE_PATH))
        characters = chapter.get("characters") or []
        unresolved = chapter.get("unresolved_mentions") or []

        pronoun_entry = _find_surface(characters, "私")
        self.assertIsNotNone(pronoun_entry)
        assert pronoun_entry is not None
        self.assertEqual(pronoun_entry.get("naming_quality"), "pronoun_like")
        self.assertTrue(pronoun_entry.get("needs_review"))
        self.assertIn(pronoun_entry.get("review_state"), {"local_candidate", "candidate", "needs_review"})

        baby_entry = _find_surface(characters, "赤子")
        self.assertIsNotNone(baby_entry)
        assert baby_entry is not None
        self.assertEqual(baby_entry.get("naming_quality"), "descriptor")
        self.assertTrue(baby_entry.get("needs_review"))
        self.assertIn(baby_entry.get("review_state"), {"local_candidate", "candidate", "needs_review"})

        for surface in ["王", "王妃"]:
            entry = _find_surface(characters, surface)
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertTrue(entry.get("needs_review"))

        unresolved_surfaces = {entry.get("surface") for entry in unresolved}
        self.assertTrue({"杖", "後継者", "お前"} <= unresolved_surfaces)

        blob = json.dumps(chapter, ensure_ascii=False)
        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)

    def test_expected_reports_are_present_and_consistent(self):
        checklist = _load_json(CHECKLIST_PATH)
        comparison = _load_json(COMPARISON_REPORT_PATH)
        issue_report = _load_json(ISSUE_REPORT_PATH)

        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051")
        self.assertEqual(comparison.get("baseline_sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001")
        self.assertEqual(comparison.get("hardened_sample_id"), "chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051")
        self.assertEqual(comparison.get("overall_assessment"), "improved_contract_usable")
        self.assertTrue(comparison.get("what_improved"))
        self.assertTrue(comparison.get("remaining_prompt_schema_issues"))

        issues = {item.get("id"): item.get("status") for item in issue_report.get("issues") or []}
        self.assertEqual(issues.get("chapter_schema_missing_objects_section"), "improved_resolved_at_prompt_schema_level")
        self.assertEqual(issues.get("artifact_retention_not_first_class"), "improved_resolved_at_prompt_schema_level")
        self.assertEqual(issues.get("relation_type_taxonomy_too_narrow"), "improved_with_two_layer_relation_model")
        self.assertEqual(issues.get("event_cap_may_be_too_low_for_dense_chapters"), "improved_with_event_importance_no_hard_cap")
        self.assertEqual(issues.get("empty_canonical_entity_map_in_capture"), "still_open_for_real_e2e")

    def test_provider_free_guarantee_files_only(self):
        for path in [HARDENED_SAMPLE_PATH, CHECKLIST_PATH, COMPARISON_REPORT_PATH, ISSUE_REPORT_PATH]:
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", blob)
            self.assertNotIn("ANTHROPIC_API_KEY", blob)
            self.assertNotIn("https://api.", blob)
            self.assertNotIn("/runs/", blob)
            self.assertNotIn("/vault/", blob)


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _find_surface(items: list[dict[str, Any]], surface: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("surface") == surface), None)


def _first_chapter(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = payload.get("chapters") or []
    assert chapters
    return chapters[0]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
