from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
PROVIDER_SAMPLES_ROOT = FIXTURE_ROOT / "provider_samples"
CODEX_SAMPLE_PATH = PROVIDER_SAMPLES_ROOT / "codex_blind_simulated_extraction_ch_017_019.json"
CHATGPT_OPTIONAL_PATH = PROVIDER_SAMPLES_ROOT / "chatgpt_response_ch_017_019.json"
CHATGPT_README_PATH = PROVIDER_SAMPLES_ROOT / "chatgpt_response_ch_017_019.README.md"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "provider_dual_comparison_checklist.json"
AUDIT_REPORT_PATH = FIXTURE_ROOT / "expected" / "prompt_packet_audit_report.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "extraction_metadata",
    "entities",
    "objects",
    "places",
    "lore_concepts",
    "events",
    "relationships",
    "review_suggestions",
    "suppression_candidates",
    "quality_notes",
}

ASSESSMENT_STATES = {
    "prompt_promising",
    "prompt_needs_minor_revision",
    "prompt_needs_major_revision",
    "prompt_not_usable",
}


class TextifAIRealNovelJPDualLLMExtractionAuditTests(unittest.TestCase):
    def test_codex_blind_sample_exists_parseable_and_has_provider_free_flags(self):
        self.assertTrue(CODEX_SAMPLE_PATH.exists())
        sample = _load_json(CODEX_SAMPLE_PATH)
        self.assertEqual(sample.get("sample_type"), "codex_blind_self_simulated_extraction")
        self.assertFalse(sample.get("provider_calls"))
        self.assertTrue(sample.get("not_runtime_provider_output"))
        self.assertTrue(sample.get("not_canon_approval"))
        self.assertTrue(sample.get("for_tests"))
        self.assertTrue(sample.get("blind_prompt"))

    def test_codex_blind_sample_has_required_shape_and_safety_guards(self):
        sample = _load_json(CODEX_SAMPLE_PATH)
        self.assertTrue(REQUIRED_TOP_LEVEL_KEYS.issubset(sample.keys()))
        self.assertIn(sample.get("quality_notes", {}).get("prompt_packet_assessment"), ASSESSMENT_STATES)
        blob = json.dumps(sample, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", blob)
        self.assertNotIn("ANTHROPIC_API_KEY", blob)
        self.assertNotIn("https://api.", blob)
        self.assertNotIn("/runs/", blob)
        self.assertNotIn("/vault/", blob)

    def test_codex_blind_sample_can_be_evaluated_against_post_prompt_must_haves(self):
        sample = _load_json(CODEX_SAMPLE_PATH)
        entity_names = {entry.get("canonical_name_guess") for entry in sample.get("entities") or []}
        self.assertIn("レン", entity_names)
        self.assertIn("セラ", entity_names)

        object_names = {entry.get("canonical_name_guess") for entry in sample.get("objects") or []}
        self.assertIn("ベル", object_names)

        place_names = {entry.get("canonical_name_guess") for entry in sample.get("places") or []}
        self.assertIn("エルサリエル", place_names)

        blob = json.dumps(sample, ensure_ascii=False)
        for token in ["王者と杖", "ベルド", "オヤジ", "魔力", "死"]:
            self.assertIn(token, blob)

    def test_pronouns_are_not_promoted_in_codex_blind_sample(self):
        sample = _load_json(CODEX_SAMPLE_PATH)
        entity_names = {entry.get("canonical_name_guess") for entry in sample.get("entities") or []}
        suppression = {entry.get("surface") for entry in sample.get("suppression_candidates") or []}
        for pronoun in ["彼", "彼女", "俺", "私"]:
            self.assertNotIn(pronoun, entity_names)
            self.assertIn(pronoun, suppression)

    def test_dual_comparison_checklist_and_audit_report_parse(self):
        checklist = _load_json(CHECKLIST_PATH)
        audit_report = _load_json(AUDIT_REPORT_PATH)
        for key in [
            "comparison_targets",
            "must_have_coverage",
            "should_have_coverage",
            "cross_sample_consistency",
            "pronoun_promotion_guard",
            "object_retention_guard",
            "lore_concept_retention",
            "relationship_retention",
            "event_retention",
            "hallucination_risk",
            "json_validity",
            "shape_compatibility",
            "author_usefulness",
            "anti_leakage_policy",
            "pass_fail_states",
            "non_negotiable_failures",
        ]:
            self.assertIn(key, checklist)
        self.assertIn(audit_report.get("overall_prompt_readiness"), ASSESSMENT_STATES)
        self.assertEqual(audit_report.get("packet_status"), "ready_for_manual_chatgpt_trial")
        self.assertEqual(audit_report.get("blind_prompt_status"), "passed_no_expected_leakage")
        self.assertEqual(audit_report.get("chatgpt_response_status"), "not_provided_yet")

    def test_non_negotiable_failures_include_core_safety_and_usefulness_guards(self):
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

    def test_chatgpt_middleman_readme_exists_and_optional_response_is_non_blocking(self):
        self.assertTrue(CHATGPT_README_PATH.exists())
        readme = CHATGPT_README_PATH.read_text(encoding="utf-8")
        self.assertIn("extraction_prompt_packet_ch_017_019.md", readme)
        self.assertIn("chatgpt_response_ch_017_019.json", readme)
        if not CHATGPT_OPTIONAL_PATH.exists():
            self.skipTest("Optional ChatGPT response not provided yet.")
        response = _load_json(CHATGPT_OPTIONAL_PATH)
        self.assertTrue(REQUIRED_TOP_LEVEL_KEYS.issubset(response.keys()))
        blob = json.dumps(response, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", blob)
        self.assertNotIn("ANTHROPIC_API_KEY", blob)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
