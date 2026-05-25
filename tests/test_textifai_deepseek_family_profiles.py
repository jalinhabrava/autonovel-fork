from __future__ import annotations

import json
import unittest
from pathlib import Path

from textifai.import_review.deepseek_family_profiles import (
    DEEPSEEK_REASONER_STATUS,
    build_deepseek_byok_guidance,
    build_deepseek_e2e_readiness_gate,
    build_thin_output_warnings,
    deepseek_family_profiles,
    get_deepseek_family_profile,
)
from textifai.import_review.provider_prompt_profiles import get_provider_prompt_profile

FIXTURE_ROOT = Path("tests/fixtures/textifai/provider_prompt_profiles/expected")
ONT_NAMES = ["セラ", "王者の杖", "アデルマン", "ティセイア", "ベル"]


class DeepSeekFamilyProfilesTests(unittest.TestCase):
    def test_flash_and_pro_profiles_exist(self):
        flash = get_deepseek_family_profile("deepseek-v4-flash")
        pro = get_deepseek_family_profile("deepseek-v4-pro")

        self.assertIsNotNone(flash)
        self.assertIsNotNone(pro)
        assert flash is not None
        assert pro is not None
        self.assertEqual(flash.profile_id, "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1")
        self.assertEqual(pro.profile_id, "deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1")
        self.assertEqual(flash.default_max_output_tokens, 8192)
        self.assertEqual(pro.default_max_output_tokens, 8192)
        self.assertTrue(flash.json_mode)
        self.assertTrue(pro.json_mode)
        self.assertIsInstance(flash.chunking_preferences, dict)
        self.assertIsInstance(pro.chunking_preferences, dict)
        self.assertTrue(pro.chunking_preferences.get("compact_reduction_recommended"))

    def test_provider_profile_auto_resolution_uses_packaged_family_profiles(self):
        flash = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        pro = get_provider_prompt_profile("deepseek", "deepseek-v4-pro", "bootstrap_chapter_extraction")

        self.assertIsNotNone(flash)
        self.assertIsNotNone(pro)
        assert flash is not None
        assert pro is not None
        self.assertEqual(flash.profile_id, "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1")
        self.assertEqual(pro.profile_id, "deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1")

    def test_reasoner_marked_not_visible_and_not_packaged(self):
        self.assertEqual(DEEPSEEK_REASONER_STATUS["discovery_status"], "not_visible_in_sp069")
        self.assertEqual(DEEPSEEK_REASONER_STATUS["profile_status"], "not_packaged")
        self.assertIsNone(get_deepseek_family_profile("deepseek-reasoner"))

    def test_overlays_are_json_first_and_do_not_contain_ont_names(self):
        for profile in deepseek_family_profiles():
            self.assertIn("valid JSON object", profile.prompt_overlay)
            self.assertIn("Do not use markdown", profile.prompt_overlay)
            self.assertIn("Do not invent names", profile.prompt_overlay)
            self.assertLess(len(profile.prompt_overlay), 1400)
            for name in ONT_NAMES:
                self.assertNotIn(name, profile.prompt_overlay)

    def test_byok_guidance_respects_enabled_models(self):
        flash_only = build_deepseek_byok_guidance(["deepseek-v4-flash"])
        pro_only = build_deepseek_byok_guidance(["deepseek-v4-pro"])
        both = build_deepseek_byok_guidance(["deepseek-v4-flash", "deepseek-v4-pro"])

        self.assertEqual([item["model_id"] for item in flash_only["model_guidance"]], ["deepseek-v4-flash"])
        self.assertEqual([item["model_id"] for item in pro_only["model_guidance"]], ["deepseek-v4-pro"])
        self.assertEqual({item["model_id"] for item in both["model_guidance"]}, {"deepseek-v4-flash", "deepseek-v4-pro"})
        self.assertFalse(flash_only["auto_switching"])
        self.assertFalse(pro_only["auto_switching"])
        self.assertFalse(both["global_routing"])
        self.assertTrue(both["informational_comparison_allowed"])
        self.assertIn("deepseek-reasoner", {item["model_id"] for item in both["unavailable_models"]})

    def test_thin_output_warnings_for_poor_valid_payload_metrics(self):
        report = build_thin_output_warnings(
            {
                "response_parseable_json": True,
                "validation_ok": True,
                "density_score": 12,
                "response_text_chars": 1800,
                "counts": {
                    "objects": 0,
                    "events": 1,
                    "relations": 1,
                    "unresolved_mentions": 0,
                },
                "ambiguous_context": True,
            }
        )
        self.assertIn("low_density_score", report["warnings"])
        self.assertIn("zero_unresolved_mentions_in_ambiguous_context", report["warnings"])
        self.assertIn("low_objects_count", report["warnings"])
        self.assertIn("low_events_count", report["warnings"])
        self.assertIn("low_relations_count", report["warnings"])
        self.assertIn("valid_json_but_thin", report["warnings"])
        self.assertIn("model_profile_experimental", report["warnings"])
        self.assertFalse(report["auto_switching"])

    def test_e2e_readiness_gate(self):
        gate = build_deepseek_e2e_readiness_gate()
        self.assertEqual(gate["assessment"], "deepseek_family_profiles_packaged_for_e2e_preflight")
        self.assertTrue(gate["deepseek_family_usable_for_low_cost_e2e_preflight"])
        self.assertFalse(gate["production_quality_claim"])
        self.assertFalse(gate["reasoner_profile_available"])
        self.assertFalse(gate["common_family_profile_viable"])
        self.assertTrue(gate["per_model_profiles_required"])

    def test_expected_reports_parse(self):
        profiles = json.loads((FIXTURE_ROOT / "deepseek_family_profiles_after_sp069.json").read_text(encoding="utf-8"))
        guidance = json.loads((FIXTURE_ROOT / "deepseek_family_byok_guidance_after_sp069.json").read_text(encoding="utf-8"))
        warnings = json.loads((FIXTURE_ROOT / "deepseek_family_thin_output_warnings_after_sp069.json").read_text(encoding="utf-8"))
        gate = json.loads((FIXTURE_ROOT / "deepseek_family_e2e_readiness_gate_after_sp069.json").read_text(encoding="utf-8"))

        self.assertEqual(profiles["assessment"], "deepseek_family_profiles_packaged_for_e2e_preflight")
        self.assertIn("deepseek-v4-flash", profiles["packaged_models"])
        self.assertIn("deepseek-v4-pro", profiles["packaged_models"])
        self.assertEqual(profiles["reasoner"]["profile_status"], "not_packaged")
        self.assertFalse(guidance["auto_switching"])
        self.assertIn("valid_json_but_thin", warnings["warning_codes"])
        self.assertEqual(gate["assessment"], "deepseek_family_profiles_packaged_for_e2e_preflight")


if __name__ == "__main__":
    unittest.main()
