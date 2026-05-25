from __future__ import annotations

import json
import unittest
from pathlib import Path

from textifai.import_review.prompt_experiment_observability import (
    FAILURE_MODE_TAXONOMY,
    PROMPT_CHANGE_TYPES,
    SAFE_VARIANT_DECISIONS,
    build_experiment_entry,
    classify_failure_mode,
    classify_variant_decision,
)

FIXTURE_ROOT = Path("tests/fixtures/textifai/prompt_experiments/expected")
ONT_NAMES = ["セラ", "王者の杖", "アデルマン", "ティセイア", "ベル"]


class PromptExperimentObservabilityTests(unittest.TestCase):
    def test_failure_mode_enum_contains_expected_values(self):
        expected = {
            "invalid_json_markdown",
            "invalid_json_extra_text",
            "invalid_json_truncated",
            "invalid_json_reasoning_leak",
            "invalid_json_unknown",
            "valid_json_wrong_shape",
            "valid_json_missing_required_sections",
            "valid_json_wrong_chapter",
            "valid_json_thin",
            "valid_json_low_objects",
            "valid_json_low_events",
            "valid_json_low_relations",
            "valid_json_zero_unresolved",
            "provider_empty_response",
            "provider_error",
            "validation_failed_missing_event_importance",
            "validation_failed_missing_relation_category",
        }
        self.assertTrue(expected.issubset(set(FAILURE_MODE_TAXONOMY)))
        self.assertIn("balanced_knowledge_base", PROMPT_CHANGE_TYPES)

    def test_classifies_thin_payload_and_missing_sections(self):
        thin = classify_failure_mode(
            {
                "parseable_json": True,
                "validation_ok": True,
                "score": 12,
                "counts": {"objects": 0, "events": 1, "relations": 1, "unresolved_mentions": 0},
                "ambiguous_context": True,
                "response_text_chars": 1500,
            }
        )
        missing = classify_failure_mode(
            {
                "parseable_json": True,
                "validation_ok": False,
                "missing_required_sections": ["objects", "relations"],
                "counts": {},
            }
        )
        self.assertEqual(thin, "valid_json_low_objects")
        self.assertEqual(missing, "valid_json_missing_required_sections")

    def test_classifies_decisions_keep_mutate_discard(self):
        keep = classify_variant_decision(
            {"parseable_json": True, "validation_ok": True, "score": 26, "counts": {"objects": 3, "events": 2, "relations": 3}},
            packaged=True,
        )
        mutate = classify_variant_decision(
            {
                "parseable_json": True,
                "validation_ok": True,
                "score": 18,
                "counts": {"objects": 0, "events": 1, "relations": 1, "unresolved_mentions": 0},
                "ambiguous_context": True,
            }
        )
        discard = classify_variant_decision({"parseable_json": False, "validation_ok": False, "failure_hint": "markdown fenced output"})
        self.assertEqual(keep, "keep")
        self.assertEqual(mutate, "mutate")
        self.assertEqual(discard, "discard")

    def test_build_experiment_entry(self):
        entry = build_experiment_entry(
            experiment_id="exp-1",
            provider_family="deepseek",
            model="deepseek-v4-flash",
            task="bootstrap_chapter_extraction",
            chapter_id="ch_002",
            variant_id="family_variant_2_oer_focus",
            parent_variant_id="variant_e_objects_events_relations_boost",
            variant_goal="Goal",
            hypothesis="Hypothesis",
            prompt_change_type=["json_reliability", "objects_events_relations_focus"],
            expected_effect="Effect",
            risk="Risk",
            result_summary={"parseable_json": True, "validation_ok": True, "score": 26.5, "counts": {"objects": 4, "events": 1, "relations": 3}},
            decision="keep",
        )
        self.assertEqual(entry["variant_id"], "family_variant_2_oer_focus")
        self.assertIn(entry["decision"], SAFE_VARIANT_DECISIONS)

    def test_expected_reports_parse_and_are_privacy_safe(self):
        files = [
            FIXTURE_ROOT / "deepseek_prompt_experiment_taxonomy_after_sp070.json",
            FIXTURE_ROOT / "deepseek_variant_diff_report_after_sp070.json",
            FIXTURE_ROOT / "deepseek_failure_mode_taxonomy_after_sp070.json",
            FIXTURE_ROOT / "deepseek_variant_decision_report_after_sp070.json",
        ]
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False)
            self.assertIn("assessment", data)
            self.assertNotIn("sk-", text)
            self.assertNotIn("BEGIN PRIVATE", text)
            self.assertNotIn("provider_response.json", text)
            for name in ONT_NAMES:
                self.assertNotIn(name, text)
            self.assertLess(len(text), 50000)

        taxonomy = json.loads((FIXTURE_ROOT / "deepseek_prompt_experiment_taxonomy_after_sp070.json").read_text(encoding="utf-8"))
        diff = json.loads((FIXTURE_ROOT / "deepseek_variant_diff_report_after_sp070.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_variant_decision_report_after_sp070.json").read_text(encoding="utf-8"))
        failure = json.loads((FIXTURE_ROOT / "deepseek_failure_mode_taxonomy_after_sp070.json").read_text(encoding="utf-8"))

        self.assertEqual(taxonomy["assessment"], "prompt_experiment_observability_ready_for_chunking_preflight")
        self.assertEqual(diff["variant_diffs"][0]["variant_id"], "family_variant_2_oer_focus")
        self.assertEqual(decision["packaged_flash_profile"], "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1")
        self.assertEqual(failure["failure_modes"][0]["code"], "invalid_json_markdown")


if __name__ == "__main__":
    unittest.main()
