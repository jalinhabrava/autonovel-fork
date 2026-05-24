from __future__ import annotations

import json
import unittest
from pathlib import Path

from textifai.import_review.provider_prompt_profiles import (
    ProviderPromptProfile,
    apply_provider_prompt_profile,
    get_provider_prompt_profile,
    list_provider_prompt_profiles,
    summarize_provider_prompt_profile,
    validate_extraction_density,
)

FIXTURE_ROOT = Path("tests/fixtures/textifai/provider_prompt_profiles/expected")


class ProviderPromptProfilesTests(unittest.TestCase):
    def test_registry_lists_deepseek_profile(self):
        profiles = list_provider_prompt_profiles()
        self.assertGreaterEqual(len(profiles), 1)
        ids = {item.profile_id for item in profiles}
        self.assertIn("deepseek-v4-flash:bootstrap_chapter_extraction:v1", ids)

    def test_resolve_deepseek_profile_for_bootstrap_chapter_extraction(self):
        profile = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.profile_id, "deepseek-v4-flash:bootstrap_chapter_extraction:v1")
        self.assertTrue(profile.json_mode)
        self.assertEqual(profile.default_max_output_tokens, 8192)

    def test_unknown_provider_or_task_returns_none(self):
        self.assertIsNone(get_provider_prompt_profile("unknown", "model-x", "bootstrap_chapter_extraction"))
        self.assertIsNone(get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "other_task"))

    def test_profile_sections_and_overlay_shape(self):
        profile = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        assert profile is not None
        required = {"characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"}
        self.assertTrue(required.issubset(set(profile.must_include_sections)))

        overlay = profile.prompt_overlay
        self.assertIn("valid JSON object", overlay)
        self.assertIn("Do not use markdown", overlay)
        self.assertIn("Do not compress the extraction", overlay)
        self.assertIn("objects/tools/artifacts/catalysts/weapons", overlay)
        self.assertIn("durable events", overlay)
        self.assertIn("evidence-backed relations", overlay)
        self.assertIn("unresolved mentions", overlay)
        self.assertIn("Keep uncertain identities in review", overlay)
        self.assertLess(len(overlay), 1200)
        self.assertNotIn("セラ", overlay)
        self.assertNotIn("王者の杖", overlay)
        self.assertNotIn("アデルマン", overlay)
        self.assertNotIn("ティセイア", overlay)
        self.assertNotIn("ベル", overlay)

        self.assertEqual(profile.json_reliability_policy, "json_first_no_markdown_single_object")
        self.assertEqual(profile.prompt_density_policy, "compact_high_recall")
        self.assertEqual(profile.overlay_style, "compact_json_first")

    def test_apply_profile_augments_system_prompt_and_is_idempotent(self):
        profile = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        assert profile is not None
        system = "Return only valid JSON for one chapter extraction."
        user = "payload"
        updated_system, updated_user = apply_provider_prompt_profile(system, user, profile)
        self.assertIn("## Provider Profile Overlay", updated_system)
        self.assertEqual(updated_user, user)

        second_system, second_user = apply_provider_prompt_profile(updated_system, updated_user, profile)
        self.assertEqual(second_system.count("## Provider Profile Overlay"), 1)
        self.assertEqual(second_user, user)

    def test_summarize_profile_excludes_overlay_body(self):
        profile = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        assert profile is not None
        summary = summarize_provider_prompt_profile(profile)
        self.assertIn("profile_id", summary)
        self.assertIn("prompt_overlay_preview", summary)
        self.assertEqual(summary["json_reliability_policy"], "json_first_no_markdown_single_object")
        self.assertEqual(summary["prompt_density_policy"], "compact_high_recall")
        self.assertEqual(summary["overlay_style"], "compact_json_first")
        self.assertNotIn("prompt_overlay", summary)

    def test_validate_density_warns_on_thin_payload(self):
        profile = get_provider_prompt_profile("deepseek", "deepseek-v4-flash", "bootstrap_chapter_extraction")
        assert profile is not None
        payload = {
            "work": {"title": "x", "language": "ja"},
            "chapters": [
                {
                    "chapter_id": "ch_002",
                    "characters": [{"surface": "A"}],
                    "places": [],
                    "concepts": [],
                    "objects": [],
                    "events": [{"surface": "evt", "event_importance": "major"}],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
        }
        report = validate_extraction_density(payload, profile)
        self.assertTrue(report["required_sections_present"])
        self.assertIn("low_object_count", report["warnings"])
        self.assertIn("empty_unresolved_mentions", report["warnings"])
        self.assertIn("low_relation_count", report["warnings"])

    def test_expected_reports_parse(self):
        profile = json.loads((FIXTURE_ROOT / "deepseek_v4_flash_bootstrap_chapter_extraction_profile.json").read_text(encoding="utf-8"))
        overlay = (FIXTURE_ROOT / "deepseek_v4_flash_density_prompt_overlay.md").read_text(encoding="utf-8")
        compact_overlay = (FIXTURE_ROOT / "deepseek_v4_flash_compact_json_first_overlay.md").read_text(encoding="utf-8")
        registry = json.loads((FIXTURE_ROOT / "provider_prompt_profiles_registry_report.json").read_text(encoding="utf-8"))
        overlay_revision = json.loads((FIXTURE_ROOT / "deepseek_v4_flash_overlay_revision_report.json").read_text(encoding="utf-8"))

        self.assertEqual(profile["profile_id"], "deepseek-v4-flash:bootstrap_chapter_extraction:v1")
        self.assertEqual(profile["json_reliability_policy"], "json_first_no_markdown_single_object")
        self.assertEqual(profile["prompt_density_policy"], "compact_high_recall")
        self.assertIn("valid JSON object", overlay)
        self.assertIn("Do not use markdown", compact_overlay)
        self.assertLess(len(compact_overlay), 1200)
        self.assertEqual(registry["profiles_count"], 1)
        self.assertEqual(overlay_revision["new_overlay_strategy"], "compact_json_first_density_overlay")


if __name__ == "__main__":
    unittest.main()
