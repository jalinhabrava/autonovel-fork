from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/identity_alias_role")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
DRIFT_EXPECTATIONS_PATH = FIXTURE_ROOT / "expected" / "replay_drift_expectations.json"
EXPECTED_CHAPTER_IDS = {"ch_001", "ch_002", "ch_003"}
KNOWN_STATUSES = {"pass", "warn", "fail", "skip"}


class TextifAISemanticEdgeReplayContractsTests(unittest.TestCase):
    def test_provider_free_replay_output_matches_edge_contracts_and_registered_drift(self):
        expectations = _load_json(DRIFT_EXPECTATIONS_PATH)
        before_hashes = _hash_replay_input()

        with tempfile.TemporaryDirectory(prefix="textifai_semantic_edge_contracts_") as temp_root:
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

            self._assert_output_boundary(output_root=output_root, result=result, system_root=system_root)
            self._assert_shape_contract(obsidian_import=obsidian_import, review_queue=review_queue, invariants=invariants)
            self._assert_required_entities(expectations=expectations, obsidian_import=obsidian_import)
            self._assert_aliases(obsidian_import=obsidian_import)
            self._assert_forbidden_primaries(expectations=expectations, obsidian_import=obsidian_import)
            self._assert_review_queue_actionability(expectations=expectations, obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_drift_expectations_are_explicit(expectations=expectations, obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_language_agnostic_metadata(expectations=expectations)

        self.assertEqual(before_hashes, _hash_replay_input())

    def _assert_shape_contract(self, *, obsidian_import: dict, review_queue: dict, invariants: dict) -> None:
        self.assertIsInstance(obsidian_import.get("entities"), list)
        self.assertTrue(obsidian_import.get("entities"))
        self.assertIsInstance(review_queue.get("items"), list)
        self.assertIn("schema_version", review_queue)
        self.assertIn("status", invariants)
        self.assertIsInstance(invariants.get("checks"), list)
        self.assertTrue(invariants.get("checks"))
        for check in invariants.get("checks") or []:
            self.assertIn(check.get("status"), KNOWN_STATUSES)

    def _assert_required_entities(self, *, expectations: dict, obsidian_import: dict) -> None:
        entities = obsidian_import.get("entities") or []
        for required in expectations.get("required_entities") or []:
            entity = _entity_by_name(entities, required["canonical_name"])
            self.assertIsNotNone(entity, required)
            self.assertTrue(_is_primary(entity), entity)

    def _assert_aliases(self, *, obsidian_import: dict) -> None:
        entities = obsidian_import.get("entities") or []
        sera = _entity_by_name(entities, "Sera Valen")
        ren = _entity_by_name(entities, "Ren Tal")
        self.assertIsNotNone(sera)
        self.assertIsNotNone(ren)
        self.assertTrue(_has_surface(sera, "Sera"), sera)
        self.assertTrue(_has_surface(ren, "Ren"), ren)

    def _assert_forbidden_primaries(self, *, expectations: dict, obsidian_import: dict) -> None:
        entities = obsidian_import.get("entities") or []
        for forbidden in expectations.get("forbidden_primary_entities") or []:
            entity = _entity_by_name(entities, forbidden["canonical_name"])
            if entity is None:
                continue
            self.assertFalse(_is_primary(entity), forbidden)

    def _assert_review_queue_actionability(self, *, expectations: dict, obsidian_import: dict, review_queue: dict) -> None:
        entities = obsidian_import.get("entities") or []
        items = review_queue.get("items") or []

        title_item = _review_item_by_source_or_target(items, "la princesa")
        self.assertIsNotNone(title_item)
        self.assertEqual(title_item.get("review_type"), "entity_retention_review")
        self.assertEqual(title_item.get("suggested_action"), "review_attach_role_or_title")
        self.assertEqual(title_item.get("candidate_entities")[0].get("canonical_name"), "Sera Valen")
        title_metadata = title_item.get("metadata") or {}
        self.assertTrue(title_metadata.get("do_not_auto_merge"))
        self.assertEqual(title_metadata.get("signal_tier"), "medium")
        self.assertIn(title_metadata.get("candidate_status"), {"weak_candidate", "strong_candidate"})
        self.assertEqual(title_metadata.get("surface_type"), "title_like")
        self.assertIn(title_metadata.get("semantic_value"), {"title", "role"})
        self.assertEqual(title_metadata.get("language_hint"), "es")
        self.assertIn("attach_role_or_title", title_metadata.get("future_viewer_actions") or [])
        self.assertTrue(title_item.get("evidence"))

        descriptor_item = _review_item_by_source_or_target(items, "la heredera silenciosa")
        self.assertIsNotNone(descriptor_item)
        self.assertEqual(descriptor_item.get("review_type"), "entity_retention_review")
        self.assertEqual(descriptor_item.get("suggested_action"), "review_enrich_existing_entity")
        self.assertEqual(descriptor_item.get("candidate_entities")[0].get("canonical_name"), "Sera Valen")
        descriptor_metadata = descriptor_item.get("metadata") or {}
        self.assertTrue(descriptor_metadata.get("do_not_auto_merge"))
        self.assertEqual(descriptor_metadata.get("signal_tier"), "medium")
        self.assertIn(descriptor_metadata.get("candidate_status"), {"weak_candidate", "strong_candidate"})
        self.assertEqual(descriptor_metadata.get("surface_type"), "descriptor_like")
        self.assertEqual(descriptor_metadata.get("semantic_value"), "descriptor")
        self.assertEqual(descriptor_metadata.get("language_hint"), "es")
        self.assertIn("enrich_existing_entity", descriptor_metadata.get("future_viewer_actions") or [])
        self.assertTrue(descriptor_item.get("evidence"))

        ren = _entity_by_name(entities, "Ren Tal")
        self.assertIsNotNone(ren)
        if _review_item_by_source_or_target(items, "el muchacho") is None:
            self.assertTrue(_has_surface(ren, "el muchacho"))
            self.assertTrue(_drift_is_declared(expectations, "generic_descriptor_absorbed_without_review_signal"))

        key_entity = _entity_by_name(entities, "llave de cristal")
        key_item = _review_item_by_source_or_target(items, "llave de cristal")
        self.assertIsNotNone(key_entity)
        self.assertFalse(_is_primary(key_entity), key_entity)
        self.assertIsNotNone(key_item)
        self.assertEqual(key_item.get("review_type"), "entity_retention_review")
        self.assertIn(key_item.get("suggested_action"), {"review_create_primary", "review_keep_secondary", "review_insufficient_evidence"})
        metadata = key_item.get("metadata") or {}
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertEqual(metadata.get("surface_type"), "object_like")
        self.assertEqual(metadata.get("semantic_value"), "persistent_object")
        self.assertTrue(metadata.get("do_not_auto_merge"))
        if not (key_item.get("candidate_entities") or []):
            self.assertEqual(metadata.get("candidate_status"), "no_clear_existing_primary")
        viewer_actions = metadata.get("future_viewer_actions") or []
        self.assertIn("promote", viewer_actions)
        self.assertIn("keep_secondary", viewer_actions)
        self.assertIn("reject_noise", viewer_actions)

        self.assertIsNone(_review_item_by_source_or_target(items, "ella"))
        self.assertIsNone(_review_item_by_source_or_target(items, "guardia somnoliento"))

    def _assert_drift_expectations_are_explicit(self, *, expectations: dict, obsidian_import: dict, review_queue: dict) -> None:
        drift_ids = {item.get("drift_id") for item in expectations.get("known_current_drift") or []}
        self.assertTrue(drift_ids)
        self.assertIn("generic_descriptor_absorbed_without_review_signal", drift_ids)
        self.assertNotIn("title_surface_absorbed_without_review_signal", drift_ids)
        self.assertNotIn("descriptor_surface_absorbed_without_enrichment_signal", drift_ids)
        self.assertNotIn("persistent_object_review_entity_without_retention_metadata", drift_ids)
        for drift in expectations.get("known_current_drift") or []:
            self.assertIn("observed", drift)
            self.assertIn("future_desired_behavior", drift)
            self.assertIn("accepted_temporarily", drift)

        resolved = expectations.get("resolved_current_behavior") or []
        resolved_ids = {item.get("drift_id") for item in resolved}
        self.assertIn("persistent_object_review_entity_without_retention_metadata", resolved_ids)
        self.assertIn("title_surface_absorbed_without_review_signal", resolved_ids)
        self.assertIn("descriptor_surface_absorbed_without_enrichment_signal", resolved_ids)

        failures = expectations.get("non_negotiable_failures") or []
        self.assertIn("Sera Valen missing", failures)
        self.assertIn("Ren Tal missing", failures)
        self.assertIn("ella promoted as primary", failures)
        self.assertIn("output outside tempdir", failures)
        self.assertIn("auto-merge occurs", failures)
        self.assertIn("auto-promotion occurs", failures)

    def _assert_language_agnostic_metadata(self, *, expectations: dict) -> None:
        notes = expectations.get("language_agnostic_notes") or []
        self.assertTrue(notes)
        expected_signals = expectations.get("expected_review_signals") or []
        self.assertTrue(expected_signals)
        for optional in expectations.get("optional_or_review_entities") or []:
            if "surface" in optional:
                self.assertIn("surface_type", optional)
                self.assertIn("semantic_value", optional)
            if optional.get("canonical_name") == "llave de cristal":
                self.assertIn("expected_surface_type", optional)
                self.assertIn("expected_semantic_value", optional)

    def _assert_output_boundary(self, *, output_root: Path, result, system_root: Path) -> None:
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
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())


def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_replay_input() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(REPLAY_INPUT_ROOT.rglob("*")):
        if path.is_file():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _entity_by_name(entities: list[dict], canonical_name: str) -> dict | None:
    for entity in entities:
        if entity.get("canonical_name") == canonical_name:
            return entity
    return None


def _review_item_by_source_or_target(items: list[dict], surface: str) -> dict | None:
    for item in items:
        if item.get("source_entity") == surface or item.get("target_text") == surface:
            return item
    return None


def _is_primary(entity: dict) -> bool:
    return str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary"


def _has_surface(entity: dict | None, surface: str) -> bool:
    if not entity:
        return False
    values = [entity.get("canonical_name"), entity.get("preferred_slug"), *(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]
    return surface in values


def _drift_is_declared(expectations: dict, drift_id: str) -> bool:
    return any(item.get("drift_id") == drift_id and item.get("accepted_temporarily") is True for item in expectations.get("known_current_drift") or [])


if __name__ == "__main__":
    unittest.main()
