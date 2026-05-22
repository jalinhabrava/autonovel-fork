from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/descriptor_noise_budget")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
DRIFT_EXPECTATIONS_PATH = FIXTURE_ROOT / "expected" / "replay_drift_expectations.json"


class TextifAIDescriptorNoiseBudgetReplayContractsTests(unittest.TestCase):
    def test_provider_free_replay_output_matches_descriptor_noise_budget_contracts_and_drift(self):
        expectations = _load_json(DRIFT_EXPECTATIONS_PATH)
        before_hashes = _hash_replay_input()

        with tempfile.TemporaryDirectory(prefix="textifai_descriptor_noise_budget_contracts_") as temp_root:
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
            self._assert_required_entities_or_declared_drift(expectations=expectations, obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_forbidden_primaries(obsidian_import=obsidian_import)
            self._assert_expected_signals_or_declared_drift(expectations=expectations, review_queue=review_queue)
            self._assert_suppressed_cases(expectations=expectations, obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_no_explosion_or_declared_drift(expectations=expectations, review_queue=review_queue)
            self._assert_drift_expectations_are_explicit(expectations=expectations)
            self._assert_runtime_has_no_fixture_literals()

        self.assertEqual(before_hashes, _hash_replay_input())

    def _assert_shape(self, *, obsidian_import: dict, review_queue: dict, invariants: dict) -> None:
        self.assertEqual((obsidian_import.get("work") or {}).get("language"), "es")
        self.assertIn("chapters", obsidian_import)
        self.assertEqual(review_queue.get("schema_version"), "textifai.review_queue.v1")
        self.assertIsInstance(review_queue.get("items"), list)
        self.assertIn("status", invariants)
        self.assertIsInstance(invariants.get("checks"), list)

    def _assert_required_entities_or_declared_drift(self, *, expectations: dict, obsidian_import: dict, review_queue: dict) -> None:
        names = _all_entity_names(obsidian_import)
        self.assertIn("Ari Mar", names)
        self.assertIn("Luma Ser", names)
        self.assertFalse(_is_top_level_primary_entity(obsidian_import, "Ari Mar"))
        self.assertFalse(_is_top_level_primary_entity(obsidian_import, "Luma Ser"))

        luma_item = _review_item_by_surface(review_queue, "Luma Ser")
        if luma_item is not None:
            self.assertEqual(luma_item.get("suggested_action"), "review_create_primary")
            metadata = luma_item.get("metadata") or {}
            self.assertTrue(metadata.get("do_not_auto_merge"))
            self.assertIn(metadata.get("signal_tier"), {"medium", "low"})

    def _assert_forbidden_primaries(self, *, obsidian_import: dict) -> None:
        for surface in ["él", "mercader distraído", "el viajero", "el caminante"]:
            self.assertFalse(_is_primary_entity(obsidian_import, surface), surface)

    def _assert_expected_signals_or_declared_drift(self, *, expectations: dict, review_queue: dict) -> None:
        for surface, action, drift_id in [
            ("el cartógrafo sin memoria", "review_enrich_existing_entity", "descriptor_signal_missing_for_novel_facts"),
            ("el capitán del paso", "review_attach_role_or_title", "role_descriptor_missing_attach_signal"),
            ("el protector de Luma", "review_enrich_existing_entity", "relationship_descriptor_missing_impact_signal"),
        ]:
            item = _review_item_by_surface(review_queue, surface)
            self.assertIsNotNone(item, drift_id)
            self.assertEqual(item.get("review_type"), "entity_retention_review")
            self.assertEqual(item.get("suggested_action"), action)
            self.assertTrue(_candidate_named(item, "Ari Mar"))
            self.assertIn(drift_id, _resolved_ids(expectations))
            self._assert_modern_descriptor_metadata(item)

    def _assert_suppressed_cases(self, *, expectations: dict, obsidian_import: dict, review_queue: dict) -> None:
        self.assertIsNone(_review_item_by_surface(review_queue, "él"))
        self.assertIsNone(_review_item_by_surface(review_queue, "mercader distraído"))
        self.assertIsNone(_review_item_by_surface(review_queue, "el viajero"))
        caminante = _review_item_by_surface(review_queue, "el caminante")
        if caminante is not None:
            self.assertNotEqual(caminante.get("severity"), "medium")
            self.assertNotEqual(caminante.get("suggested_action"), "review_enrich_existing_entity")
        else:
            self.assertIn("generic_multichapter_descriptor_should_not_escalate_medium", _resolved_ids(expectations))

    def _assert_no_explosion_or_declared_drift(self, *, expectations: dict, review_queue: dict) -> None:
        descriptor_items = [_item for _item in review_queue.get("items") or [] if _is_descriptor_item(_item)]
        medium_descriptor_items = [item for item in descriptor_items if item.get("severity") == "medium"]
        self.assertLessEqual(len(descriptor_items), 6)
        self.assertLessEqual(len(medium_descriptor_items), 6)
        self.assertIn("descriptor_queue_no_explosion_observed", _resolved_ids(expectations))
        dedupe_keys = set()
        for item in descriptor_items:
            metadata = item.get("metadata") or {}
            key = (
                item.get("source_entity"),
                metadata.get("recommended_action") or item.get("suggested_action"),
                metadata.get("descriptor_category"),
            )
            self.assertNotIn(key, dedupe_keys)
            dedupe_keys.add(key)

    def _assert_modern_descriptor_metadata(self, item: dict) -> None:
        metadata = item.get("metadata") or {}
        self.assertIn(item.get("suggested_action"), {metadata.get("recommended_action"), item.get("suggested_action")})
        for key in [
            "signal_tier",
            "candidate_status",
            "candidate_review_state",
            "candidate_note_role",
            "candidate_is_primary",
            "candidate_requires_review",
            "surface_type",
            "semantic_value",
            "descriptor_category",
            "future_viewer_actions",
            "do_not_auto_merge",
            "do_not_auto_promote",
        ]:
            self.assertIn(key, metadata)
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertTrue(metadata.get("do_not_auto_promote"))
        self.assertFalse(metadata.get("candidate_is_primary"))
        self.assertTrue(metadata.get("candidate_requires_review"))
        self.assertEqual(metadata.get("candidate_review_state"), "review")

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
        ]:
            self.assertIn(key, expectations)
        for drift in expectations.get("known_current_drift") or []:
            self.assertIn("drift_id", drift)
            self.assertIn("observed_behavior", drift)
            self.assertIn("accepted_temporarily", drift)
            self.assertIn("reason", drift)
        failures = expectations.get("non_negotiable_failures") or []
        self.assertIn("provider call occurs", failures)
        self.assertIn("output outside tempdir", failures)
        self.assertIn("schema version changes unexpectedly", failures)

    def _assert_runtime_has_no_fixture_literals(self) -> None:
        runtime = Path("textifai/vaerl/review_queue.py").read_text(encoding="utf-8")
        for literal in [
            "Ari Mar",
            "Luma Ser",
            "el viajero",
            "el caminante",
            "el cartógrafo sin memoria",
            "el capitán del paso",
            "el protector de Luma",
            "él",
            "mercader distraído",
            "el guardián del archivo",
            "el custodio del paso",
        ]:
            self.assertNotIn(literal, runtime)

    def _assert_boundary(self, *, output_root: Path, result, system_root: Path) -> None:
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
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())


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


def _is_descriptor_item(item: dict) -> bool:
    metadata = item.get("metadata") or {}
    return bool(metadata.get("descriptor_category") or metadata.get("surface_type") in {"descriptor_like", "role_like", "title_like"})


def _drift_is_declared(expectations: dict, drift_id: str) -> bool:
    return any(item.get("drift_id") == drift_id and item.get("accepted_temporarily") is True for item in expectations.get("known_current_drift") or [])


def _resolved_ids(expectations: dict) -> set[str]:
    return {item.get("drift_id") for item in expectations.get("resolved_current_behavior") or []}


if __name__ == "__main__":
    unittest.main()
