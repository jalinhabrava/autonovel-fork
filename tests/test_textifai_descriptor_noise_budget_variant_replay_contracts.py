from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
DRIFT_EXPECTATIONS_PATH = FIXTURE_ROOT / "expected" / "replay_drift_expectations.json"


class TextifAIDescriptorNoiseBudgetVariantReplayContractsTests(unittest.TestCase):
    def test_variant_replay_matches_base_semantic_policy_without_fixture_strings(self):
        expectations = _load_json(DRIFT_EXPECTATIONS_PATH)
        before_hashes = _hash_replay_input()

        with tempfile.TemporaryDirectory(prefix="textifai_descriptor_noise_budget_variant_contracts_") as temp_root:
            output_root = Path(temp_root) / "out"
            with patch(
                "textifai.import_review.structured_bootstrap_v1.get_text_provider",
                side_effect=AssertionError("provider call not allowed"),
            ):
                result = run_semantic_ingestion_replay(
                    input_system_root=REPLAY_INPUT_ROOT,
                    output_root=output_root,
                    language="es",
                )

            system_root = output_root / "99_System"
            obsidian_import = _load_json(system_root / "obsidian_import.json")
            review_queue = _load_json(system_root / "review_queue.json")
            invariants = _load_json(system_root / "semantic_invariants_audit.json")

            self._assert_boundary(output_root=output_root, result=result, system_root=system_root)
            self._assert_shape(obsidian_import=obsidian_import, review_queue=review_queue, invariants=invariants)
            self._assert_required_entities_exist_without_primary_promotion(obsidian_import=obsidian_import, invariants=invariants)
            self._assert_useful_signals(review_queue=review_queue)
            self._assert_suppression_stable(obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_equivalent_descriptors_degraded(review_queue=review_queue)
            self._assert_drift_expectations_are_explicit(expectations=expectations)
            self._assert_runtime_has_no_variant_literals()

        self.assertEqual(before_hashes, _hash_replay_input())

    def _assert_shape(self, *, obsidian_import: dict, review_queue: dict, invariants: dict) -> None:
        self.assertEqual((obsidian_import.get("work") or {}).get("language"), "es")
        self.assertEqual(review_queue.get("schema_version"), "textifai.review_queue.v1")
        self.assertIsInstance(review_queue.get("items"), list)
        self.assertIn("status", invariants)
        self.assertIsInstance(invariants.get("checks"), list)

    def _assert_required_entities_exist_without_primary_promotion(self, *, obsidian_import: dict, invariants: dict) -> None:
        names = _all_entity_names(obsidian_import)
        self.assertIn("Iven Ral", names)
        self.assertIn("Sora Niv", names)
        self.assertFalse(_is_top_level_primary_entity(obsidian_import, "Iven Ral"))
        self.assertFalse(_is_top_level_primary_entity(obsidian_import, "Sora Niv"))
        self.assertEqual(invariants.get("primary_count"), 0)

    def _assert_useful_signals(self, *, review_queue: dict) -> None:
        for surface, action, category in [
            ("el trazador del umbral", "review_enrich_existing_entity", "epithet_descriptor"),
            ("la voz del peaje", "review_attach_role_or_title", "role_descriptor"),
            ("el amparo de Sora", "review_enrich_existing_entity", "relationship_descriptor"),
        ]:
            item = _review_item_by_surface(review_queue, surface)
            self.assertIsNotNone(item, surface)
            self.assertEqual(item.get("review_type"), "entity_retention_review")
            self.assertEqual(item.get("suggested_action"), action)
            self.assertEqual(item.get("severity"), "medium")
            self.assertTrue(_candidate_named(item, "Iven Ral"))
            metadata = item.get("metadata") or {}
            self.assertEqual(metadata.get("descriptor_category"), category)
            self.assertEqual(metadata.get("candidate_review_state"), "review")
            self.assertFalse(metadata.get("candidate_is_primary"))
            self.assertTrue(metadata.get("candidate_requires_review"))
            self.assertTrue(metadata.get("do_not_auto_merge"))
            self.assertTrue(metadata.get("do_not_auto_promote"))

    def _assert_suppression_stable(self, *, obsidian_import: dict, review_queue: dict) -> None:
        for surface in ["ella", "vendedor ausente", "el forastero"]:
            self.assertFalse(_is_primary_entity(obsidian_import, surface), surface)
            self.assertIsNone(_review_item_by_surface(review_queue, surface), surface)
        centinela = _review_item_by_surface(review_queue, "el centinela")
        if centinela is not None:
            self.assertNotEqual(centinela.get("suggested_action"), "review_enrich_existing_entity")
            self.assertNotEqual(centinela.get("severity"), "medium")

    def _assert_equivalent_descriptors_degraded(self, *, review_queue: dict) -> None:
        role_items = [
            item
            for item in review_queue.get("items") or []
            if (item.get("metadata") or {}).get("descriptor_category") == "role_descriptor"
            and item.get("suggested_action") == "review_attach_role_or_title"
            and _candidate_named(item, "Iven Ral")
        ]
        self.assertEqual(len(role_items), 3)
        medium = [item for item in role_items if item.get("severity") == "medium"]
        low = [item for item in role_items if item.get("severity") == "low"]
        self.assertEqual(len(medium), 1)
        self.assertGreaterEqual(len(low), 2)
        self.assertEqual(medium[0].get("source_entity"), "la voz del peaje")
        for item in low:
            metadata = item.get("metadata") or {}
            self.assertTrue(metadata.get("degraded_due_to_equivalent_signal"))
            self.assertTrue(metadata.get("equivalent_signal_group"))
            self.assertEqual(metadata.get("primary_equivalent_surface"), "la voz del peaje")

    def _assert_drift_expectations_are_explicit(self, *, expectations: dict) -> None:
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
        for drift_id in [
            "variant_semantic_behavior_matches_base_policy",
            "variant_equivalent_descriptor_signals_not_all_medium",
            "variant_distinct_descriptor_signals_survive_dedupe",
            "variant_generic_weak_descriptor_suppressed",
            "variant_pronoun_noise_suppressed",
            "variant_no_auto_promotion",
            "variant_no_auto_merge",
        ]:
            self.assertIn(drift_id, resolved_ids)
        failures = expectations.get("non_negotiable_failures") or []
        self.assertIn("variant fixture literal appears in runtime logic", failures)
        self.assertIn("useful descriptor signal missing after surface rename", failures)

    def _assert_runtime_has_no_variant_literals(self) -> None:
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

    def _assert_boundary(self, *, output_root: Path, result, system_root: Path) -> None:
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())
        expected_prefix = output_root.resolve()
        for path in [
            Path(result.output_root),
            Path(result.obsidian_import_path),
            Path(result.semantic_invariants_audit_path),
            Path(result.review_queue_path),
            Path(result.replay_audit_path),
        ]:
            resolved = path.resolve()
            self.assertTrue(resolved.is_relative_to(expected_prefix), path)
            normalized = str(resolved).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)


def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_replay_input() -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(REPLAY_INPUT_ROOT.rglob("*")) if path.is_file()}


def _all_entities(obsidian_import: dict) -> list[dict]:
    entities = [item for item in (obsidian_import.get("entities") or []) if isinstance(item, dict)]
    for chapter in obsidian_import.get("chapters") or []:
        if isinstance(chapter, dict):
            entities.extend([item for item in (chapter.get("entities") or []) if isinstance(item, dict)])
    return entities


def _all_entity_names(obsidian_import: dict) -> set[str]:
    return {str(entity.get("canonical_name") or "") for entity in _all_entities(obsidian_import)}


def _is_primary_entity(obsidian_import: dict, canonical_name: str) -> bool:
    for entity in _all_entities(obsidian_import):
        if entity.get("canonical_name") != canonical_name:
            continue
        if str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary":
            return True
    return False


def _is_top_level_primary_entity(obsidian_import: dict, canonical_name: str) -> bool:
    for entity in obsidian_import.get("entities") or []:
        if entity.get("canonical_name") != canonical_name:
            continue
        if str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary":
            return True
    return False


def _review_item_by_surface(review_queue: dict, surface: str) -> dict | None:
    for item in review_queue.get("items") or []:
        if item.get("source_entity") == surface or item.get("target_text") == surface:
            return item
    return None


def _candidate_named(item: dict, canonical_name: str) -> bool:
    return any(candidate.get("canonical_name") == canonical_name for candidate in item.get("candidate_entities") or [])


if __name__ == "__main__":
    unittest.main()
