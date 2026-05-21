from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay


REPLAY_INPUT_ROOT = Path("tests/fixtures/textifai/minimal_novel/replay_input")
DRIFT_EXPECTATIONS_PATH = Path("tests/fixtures/textifai/minimal_novel/expected/replay_drift_expectations.json")


class TextifAIReplayExpectedDriftRulesTests(unittest.TestCase):
    def test_drift_expectations_file_loads(self):
        expectations = _load_expectations()

        self.assertEqual(expectations.get("fixture_id"), "minimal_novel")
        self.assertTrue(expectations.get("required_entities"))
        self.assertTrue(expectations.get("optional_entities"))
        self.assertTrue(expectations.get("forbidden_primary_entities"))
        self.assertTrue(expectations.get("known_current_drift"))
        self.assertIn("review_queue_expectation", expectations)

    def test_replay_output_matches_expected_drift_rules(self):
        expectations = _load_expectations()

        with tempfile.TemporaryDirectory(prefix="textifai_replay_drift_") as temp_root:
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
            entities = obsidian_import.get("entities") or []

            self._assert_required_entities_retained(expectations=expectations, entities=entities)
            self._assert_forbidden_primary_entities_not_promoted(expectations=expectations, entities=entities)
            self._assert_alias_retention(expectations=expectations, entities=entities)
            self._assert_optional_entity_drift_visible(expectations=expectations, entities=entities)
            self._assert_review_queue_expectation(expectations=expectations, review_queue=review_queue)
            self._assert_output_boundary(output_root=output_root, result=result)

    def _assert_required_entities_retained(self, *, expectations: dict, entities: list[dict]) -> None:
        names = {entity.get("canonical_name") for entity in entities}
        for expected in expectations["required_entities"]:
            self.assertIn(expected["canonical_name"], names)

    def _assert_forbidden_primary_entities_not_promoted(self, *, expectations: dict, entities: list[dict]) -> None:
        for forbidden in expectations["forbidden_primary_entities"]:
            entity = _entity_by_name(entities, forbidden["canonical_name"])
            if entity is None:
                continue
            self.assertNotEqual(str(entity.get("review_state") or "").casefold(), "canonical")
            self.assertNotEqual(str(entity.get("note_role") or "").casefold(), "primary")

    def _assert_alias_retention(self, *, expectations: dict, entities: list[dict]) -> None:
        for alias_expectation in expectations["expected_aliases"]:
            entity = _entity_by_name(entities, alias_expectation["canonical_name"])
            self.assertIsNotNone(entity)
            alias = alias_expectation["alias"]
            found = False
            if "aliases" in alias_expectation.get("acceptable_locations", []):
                found = found or alias in (entity.get("aliases") or [])
            if "source_mentions" in alias_expectation.get("acceptable_locations", []):
                found = found or alias in (entity.get("source_mentions") or [])
            self.assertTrue(found, alias_expectation)

    def _assert_optional_entity_drift_visible(self, *, expectations: dict, entities: list[dict]) -> None:
        known_drift_ids = {item.get("drift_id") for item in expectations["known_current_drift"]}
        for optional in expectations["optional_entities"]:
            if optional["canonical_name"] == "brújula de plata":
                self.assertEqual(optional.get("triage_status"), "needs_retention_review")
                if _entity_by_name(entities, optional["canonical_name"]) is None:
                    self.assertIn("missing_persistent_object_brujula_de_plata", known_drift_ids)
                    drift = _drift_by_id(expectations, "missing_persistent_object_brujula_de_plata")
                    self.assertTrue(drift.get("accepted_temporarily"))
                    self.assertEqual(drift.get("triage_status"), "needs_retention_review")

    def _assert_review_queue_expectation(self, *, expectations: dict, review_queue: dict) -> None:
        queue_expectation = expectations["review_queue_expectation"]
        items = review_queue.get("items") or []
        if not items:
            self.assertTrue(queue_expectation.get("current_empty_queue_allowed"))
            self.assertTrue(queue_expectation.get("future_should_surface_retention_question"))
            drift = _drift_by_id(expectations, "empty_review_queue_for_retention_question")
            self.assertTrue(drift.get("accepted_temporarily"))
            self.assertEqual(drift.get("triage_status"), "needs_review_queue_signal_decision")

    def _assert_output_boundary(self, *, output_root: Path, result) -> None:
        expected_prefix = output_root.resolve()
        produced_paths = [
            Path(result.output_root),
            Path(result.obsidian_import_path),
            Path(result.semantic_invariants_audit_path),
            Path(result.review_queue_path),
            Path(result.replay_audit_path),
        ]
        for path in produced_paths:
            resolved = path.resolve()
            self.assertTrue(resolved.is_relative_to(expected_prefix), path)
            normalized = str(resolved).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)


def _load_expectations() -> dict:
    return json.loads(DRIFT_EXPECTATIONS_PATH.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _entity_by_name(entities: list[dict], canonical_name: str) -> dict | None:
    for entity in entities:
        if entity.get("canonical_name") == canonical_name:
            return entity
    return None


def _drift_by_id(expectations: dict, drift_id: str) -> dict:
    for item in expectations.get("known_current_drift") or []:
        if item.get("drift_id") == drift_id:
            return item
    raise AssertionError(f"Missing drift expectation: {drift_id}")


if __name__ == "__main__":
    unittest.main()
