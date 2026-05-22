from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from textifai.import_review.structured_bootstrap_v1 import build_canonical_entity_map

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture")
SAMPLE_PATH = FIXTURE_ROOT / "provider_samples" / "chatgpt_response_bootstrap_global_normalization_ja_batch_001_after_sp051.json"
CANONICAL_MAP_PATH = FIXTURE_ROOT / "expected" / "canonical_entity_map_from_manual_global_ja_batch_001_after_sp051.json"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "global_normalization_manual_sample_checklist.json"
GAP_REPORT_PATH = FIXTURE_ROOT / "expected" / "global_normalization_to_canonical_map_gap_report.json"


class TextifAIRealBootstrapManualGlobalNormalizationAuditTests(unittest.TestCase):
    def test_global_sample_exists_and_is_parseable(self):
        self.assertTrue(SAMPLE_PATH.exists())
        payload = _load_json(SAMPLE_PATH)
        self.assertIn("work", payload)
        self.assertIn("entities", payload)
        self.assertIn("merge_plan", payload)
        self.assertEqual(payload["work"].get("title"), "王者の杖")
        self.assertEqual(payload["work"].get("language"), "ja")
        self.assertIsInstance(payload.get("entities"), list)
        self.assertGreater(len(payload.get("entities") or []), 0)

    def test_relevant_entities_have_expected_shape(self):
        payload = _load_json(SAMPLE_PATH)
        required_keys = [
            "canonical_name",
            "canonical_candidate",
            "entity_kind",
            "entity_subkind",
            "preferred_slug",
            "aliases",
            "summary",
            "key_facts",
            "relationships",
            "chapter_refs",
            "source_mentions",
            "confidence",
            "review_state",
            "naming_quality",
            "is_stable_entity",
            "needs_review",
            "review_reason",
        ]
        for entity in payload.get("entities") or []:
            for key in required_keys:
                self.assertIn(key, entity, entity.get("canonical_name"))
            self.assertIsInstance(entity.get("aliases"), list)
            self.assertIsInstance(entity.get("key_facts"), list)
            self.assertIsInstance(entity.get("relationships"), list)
            self.assertIsInstance(entity.get("chapter_refs"), list)
            self.assertIsInstance(entity.get("source_mentions"), list)

    def test_useful_global_coverage_is_present_with_flexible_matching(self):
        payload = _load_json(SAMPLE_PATH)
        searchable = _searchable_text(payload)
        for token in [
            "アデルマン・レオフリック",
            "ティセイア王国",
            "杖の一族",
            "均衡",
            "赤子",
            "セラ",
        ]:
            self.assertIn(token, searchable)
        self.assertTrue(_contains_any(searchable, ["王と杖", "王者の杖"]))
        self.assertTrue(_contains_any(searchable, ["ベル", "舌のないベル"]))
        self.assertTrue(_contains_any(searchable, ["触媒", "アルモナイト"]))
        self.assertTrue(_contains_any(searchable, ["ティセイア王国の崩壊", "王国崩壊", "ひとつの時代の終わり"]))

    def test_build_canonical_entity_map_matches_generated_fixture(self):
        payload = _load_json(SAMPLE_PATH)
        generated = build_canonical_entity_map(payload)
        fixture = _load_json(CANONICAL_MAP_PATH)
        self.assertIsInstance(generated, list)
        self.assertGreater(len(generated), 0)
        self.assertEqual(generated, fixture)

    def test_canonical_map_has_expected_shape_and_targets(self):
        canonical_map = _load_json(CANONICAL_MAP_PATH)
        self.assertIsInstance(canonical_map, list)
        self.assertGreaterEqual(len(canonical_map), 8)
        for entry in canonical_map:
            for key in [
                "canonical_name",
                "entity_kind",
                "aliases",
                "summary",
                "key_facts",
                "review_state",
                "confidence",
                "canonical_candidate",
                "entity_subkind",
                "naming_quality",
                "needs_review",
            ]:
                self.assertIn(key, entry, entry.get("canonical_name"))
        searchable = _searchable_text(canonical_map)
        for token in ["アデルマン・レオフリック", "ティセイア王国", "杖の一族", "ベル", "均衡"]:
            self.assertIn(token, searchable)

    def test_review_and_no_auto_canon_safety(self):
        payload = _load_json(SAMPLE_PATH)
        entities = payload.get("entities") or []
        review_names = {entity.get("canonical_name") for entity in entities if entity.get("review_state") == "review" or entity.get("needs_review")}
        self.assertIn("赤子", review_names)
        self.assertIn("証人", review_names)
        self.assertIn("王と杖", review_names)
        self.assertIn("ネリス女王", review_names)

        baby = _find_entity(entities, "赤子")
        self.assertIsNotNone(baby)
        assert baby is not None
        self.assertTrue(baby.get("needs_review"))
        self.assertLess(float(baby.get("confidence") or 0), 0.9)

        witness = _find_entity(entities, "証人")
        self.assertIsNotNone(witness)
        assert witness is not None
        self.assertTrue(witness.get("needs_review"))
        self.assertIn("私", witness.get("aliases") or [])

        for merge in payload.get("merge_plan") or []:
            self.assertIn("canonical_name", merge)
            self.assertIn("merged_surfaces", merge)
            self.assertIn("reason", merge)
            self.assertIn("confidence", merge)
            self.assertTrue(merge.get("reason"))
            self.assertGreaterEqual(float(merge.get("confidence") or 0), 0.0)
            self.assertLessEqual(float(merge.get("confidence") or 0), 1.0)

        blob = _searchable_text(payload)
        self.assertNotIn("auto_merge_approved", blob)
        self.assertNotIn("canon_approved", blob)

    def test_checklist_and_gap_report_are_present_and_consistent(self):
        checklist = _load_json(CHECKLIST_PATH)
        gap_report = _load_json(GAP_REPORT_PATH)
        self.assertEqual(checklist.get("sample_id"), "chatgpt_response_bootstrap_global_normalization_ja_batch_001_after_sp051")
        self.assertEqual(gap_report.get("sample_id"), "chatgpt_response_bootstrap_global_normalization_ja_batch_001_after_sp051")
        self.assertEqual(gap_report.get("overall_assessment"), "usable_for_populated_map_reaudit")
        self.assertEqual(gap_report.get("source_language"), "ja")
        self.assertEqual(gap_report.get("batch_scope"), ["ch_001", "ch_002", "ch_003"])
        self.assertTrue(checklist.get("non_negotiable_failures"))
        self.assertTrue(gap_report.get("what_worked"))
        self.assertTrue(gap_report.get("downstream_risks"))

    def test_provider_free_guarantee_files_only(self):
        for path in [SAMPLE_PATH, CANONICAL_MAP_PATH, CHECKLIST_PATH, GAP_REPORT_PATH]:
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", blob)
            self.assertNotIn("ANTHROPIC_API_KEY", blob)
            self.assertNotIn("https://api.", blob)
            self.assertNotIn("/runs/", blob)
            self.assertNotIn("/vault/", blob)


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _find_entity(entities: list[dict[str, Any]], canonical_name: str) -> dict[str, Any] | None:
    return next((entity for entity in entities if entity.get("canonical_name") == canonical_name), None)


def _searchable_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
