from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant")
MANIFEST_PATH = FIXTURE_ROOT / "fixture_manifest.json"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
CHAPTER_OUTPUTS_ROOT = REPLAY_INPUT_ROOT / "chapter_outputs"


class TextifAIDescriptorNoiseBudgetVariantFixtureHarnessTests(unittest.TestCase):
    def test_fixture_root_manifest_and_replay_input_exist(self):
        self.assertTrue(FIXTURE_ROOT.exists())
        self.assertTrue((FIXTURE_ROOT / "README.md").exists())
        self.assertTrue(MANIFEST_PATH.exists())
        self.assertTrue((EXPECTED_ROOT / "README.md").exists())
        self.assertTrue((EXPECTED_ROOT / "replay_drift_expectations.json").exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "README.md").exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "global_normalization.json").exists())
        for chapter_id in ("ch_001", "ch_002", "ch_003"):
            self.assertTrue((CHAPTER_OUTPUTS_ROOT / f"{chapter_id}.json").exists())

    def test_manifest_has_variant_contract_sections(self):
        manifest = _load_json(MANIFEST_PATH)
        self.assertEqual(manifest.get("fixture_id"), "descriptor_noise_budget_variant")
        self.assertEqual(manifest.get("language"), "es")
        self.assertTrue(manifest.get("replay_input_only"))
        self.assertEqual(manifest.get("source_files"), [])
        for key in [
            "expected_descriptor_cases",
            "expected_suppressed_cases",
            "expected_review_signals",
            "expected_dedupe_or_budget_cases",
            "language_agnostic_notes",
            "anti_overfitting_notes",
        ]:
            self.assertTrue(manifest.get(key), key)

    def test_expected_drift_file_has_anti_overfitting_sections(self):
        expectations = _load_json(EXPECTED_ROOT / "replay_drift_expectations.json")
        self.assertEqual(expectations.get("fixture_id"), "descriptor_noise_budget_variant")
        for key in [
            "manual_expectation",
            "current_observed_behavior",
            "accepted_temporary_drift",
            "resolved_current_behavior",
            "known_current_drift",
            "non_negotiable_failures",
            "future_desired_behavior",
            "language_agnostic_notes",
            "anti_overfitting_notes",
        ]:
            self.assertIn(key, expectations)
        resolved_ids = {item.get("drift_id") for item in expectations.get("resolved_current_behavior") or []}
        self.assertIn("variant_semantic_behavior_matches_base_policy", resolved_ids)
        self.assertIn("variant_equivalent_descriptor_signals_not_all_medium", resolved_ids)
        self.assertIn("variant_distinct_descriptor_signals_survive_dedupe", resolved_ids)

    def test_fixture_is_safe_and_contains_no_generated_outputs(self):
        forbidden_names = {
            "web_ingestion_job.log",
            "web_ingestion_job.json",
            "obsidian_import.json",
            "review_queue.json",
            "semantic_invariants_audit.json",
        }
        for path in FIXTURE_ROOT.rglob("*"):
            if not path.is_file():
                continue
            normalized = str(path).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)
            self.assertNotIn(path.name, forbidden_names)
            self.assertLess(path.stat().st_size, 150_000, path)

    def test_variant_strings_not_hardcoded_in_runtime_logic(self):
        runtime = Path("textifai/vaerl/review_queue.py").read_text(encoding="utf-8")
        for literal in [
            "Iven Ral",
            "Sora Niv",
            "el forastero",
            "el centinela",
            "el trazador del umbral",
            "la voz del peaje",
            "el amparo de Sora",
            "vendedor ausente",
            "el custodio del pórtico",
            "el guarda del arco",
        ]:
            self.assertNotIn(literal, runtime)


def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
