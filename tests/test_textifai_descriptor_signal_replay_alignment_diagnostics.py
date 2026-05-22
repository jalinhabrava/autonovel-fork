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
RUNTIME_GUARD_PATH = Path("textifai/vaerl/review_queue.py")

EXPECTED_DESCRIPTOR_SURFACES = [
    "el cartógrafo sin memoria",
    "el capitán del paso",
    "el protector de Luma",
]
SUPPRESSED_SURFACES = [
    "el viajero",
    "el caminante",
    "él",
    "mercader distraído",
]
FIXTURE_LITERALS = [
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
]
DRIFT_IDS = [
    "candidate_state_blocks_descriptor_signal",
    "descriptor_surface_metadata_not_retained",
    "descriptor_signal_missing_for_novel_facts",
    "role_descriptor_missing_attach_signal",
    "relationship_descriptor_missing_impact_signal",
]


class TextifAIDescriptorSignalReplayAlignmentDiagnosticsTests(unittest.TestCase):
    def test_replay_diagnostics_make_missing_descriptor_signal_cause_explicit(self):
        expectations = _load_json(DRIFT_EXPECTATIONS_PATH)
        before_hashes = _hash_replay_input()

        with tempfile.TemporaryDirectory(prefix="textifai_descriptor_signal_diagnostics_") as temp_root:
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
            resolved_entities = _load_json(system_root / "resolved_entities.json")
            promotion_audit = _load_json(system_root / "promotion_decisions_audit.json")

            self._assert_boundary(output_root=output_root, result=result, system_root=system_root)
            self._assert_candidate_state_diagnosis(
                expectations=expectations,
                obsidian_import=obsidian_import,
                review_queue=review_queue,
                invariants=invariants,
                resolved_entities=resolved_entities,
                promotion_audit=promotion_audit,
            )
            self._assert_descriptor_surface_propagation(expectations=expectations, obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_metadata_presence_diagnosis(expectations=expectations, review_queue=review_queue)
            self._assert_missing_signal_drift_explicit(expectations=expectations)
            self._assert_suppression_regression(obsidian_import=obsidian_import, review_queue=review_queue)
            self._assert_identity_and_object_regression_guards()
            self._assert_anti_hardcode_guardrails()

        self.assertEqual(before_hashes, _hash_replay_input())

    def _assert_boundary(self, *, output_root: Path, result, system_root: Path) -> None:
        self.assertTrue((system_root / "obsidian_import.json").exists())
        self.assertTrue((system_root / "review_queue.json").exists())
        self.assertTrue((system_root / "semantic_invariants_audit.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())
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

    def _assert_candidate_state_diagnosis(
        self,
        *,
        expectations: dict,
        obsidian_import: dict,
        review_queue: dict,
        invariants: dict,
        resolved_entities: list[dict],
        promotion_audit: dict,
    ) -> None:
        ari_top = _entity_by_name(obsidian_import.get("entities") or [], "Ari Mar")
        self.assertIsNotNone(ari_top)
        self.assertEqual(ari_top.get("review_state"), "review")
        self.assertEqual(ari_top.get("note_role"), "review")
        self.assertFalse(ari_top.get("strong_primary_candidate"))
        self.assertEqual(ari_top.get("review_reason_code"), "weak_or_descriptive_naming")
        self.assertIn("el cartógrafo sin memoria", ari_top.get("aliases") or [])
        self.assertIn("el capitán del paso", ari_top.get("aliases") or [])
        self.assertIn("el protector de Luma", ari_top.get("aliases") or [])

        ari_review_item = _review_item_by_source(review_queue, "Ari Mar")
        self.assertIsNotNone(ari_review_item)
        self.assertEqual(ari_review_item.get("review_type"), "review_entity")
        self.assertEqual(ari_review_item.get("suggested_action"), "merge_into_primary_or_keep_review")

        self.assertEqual(invariants.get("primary_count"), 0)
        self.assertEqual(invariants.get("review_count"), 1)

        resolved_ari = _entity_by_name(resolved_entities, "Ari Mar")
        self.assertIsNotNone(resolved_ari)
        self.assertEqual(resolved_ari.get("review_state"), "review")
        self.assertFalse(resolved_ari.get("strong_primary_candidate"))

        decision = _promotion_decision_by_name(promotion_audit, "Ari Mar")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.get("decision"), "review")
        self.assertEqual(decision.get("naming_quality"), "descriptor")

        drift = _drift_by_id(expectations, "candidate_state_blocks_descriptor_signal")
        self.assertEqual(drift.get("candidate"), "Ari Mar")
        self.assertEqual(drift.get("observed_behavior"), "candidate_cluster_retained_as_review_entity_not_primary")
        self.assertTrue(drift.get("accepted_temporarily"))

    def _assert_descriptor_surface_propagation(self, *, expectations: dict, obsidian_import: dict, review_queue: dict) -> None:
        top_entity = _entity_by_name(obsidian_import.get("entities") or [], "Ari Mar")
        self.assertIsNotNone(top_entity)
        aliases = set(top_entity.get("aliases") or [])
        source_mentions = set(top_entity.get("source_mentions") or [])

        for surface in EXPECTED_DESCRIPTOR_SURFACES:
            self.assertTrue(_surface_exists_in_replay_input(surface))
            self.assertIn(surface, aliases)
            self.assertIn(surface, source_mentions)
            self.assertIsNone(_review_item_by_surface(review_queue, surface))
            drift = _drift_by_surface(expectations, "descriptor_surface_metadata_not_retained", surface)
            self.assertEqual(drift.get("observed_behavior"), "surface_absorbed_into_review_entity_without_descriptor_review_signal")
            self.assertTrue(drift.get("accepted_temporarily"))

    def _assert_metadata_presence_diagnosis(self, *, expectations: dict, review_queue: dict) -> None:
        for surface, expected_category, expected_surface_type, expected_semantic_value in [
            ("el cartógrafo sin memoria", "epithet_descriptor", "descriptor_like", "descriptor"),
            ("el capitán del paso", "role_descriptor", "role_like", "role"),
            ("el protector de Luma", "relationship_descriptor", "descriptor_like", "descriptor"),
        ]:
            replay_entity = _replay_input_entity(surface)
            self.assertIsNotNone(replay_entity)
            self.assertEqual(replay_entity.get("descriptor_category"), expected_category)
            self.assertEqual(replay_entity.get("surface_type"), expected_surface_type)
            self.assertEqual(replay_entity.get("semantic_value"), expected_semantic_value)
            self.assertEqual(replay_entity.get("language_hint"), "es")
            self.assertTrue(replay_entity.get("key_facts"))
            self.assertTrue(replay_entity.get("chapter_refs"))
            self.assertTrue(replay_entity.get("source_mentions"))
            self.assertEqual(replay_entity.get("canonical_candidate"), "Ari Mar")

        ari_item = _review_item_by_source(review_queue, "Ari Mar")
        self.assertIsNotNone(ari_item)
        metadata = ari_item.get("metadata") or {}
        self.assertNotIn("surface_type", metadata)
        self.assertNotIn("semantic_value", metadata)
        self.assertNotIn("descriptor_category", metadata)
        self.assertNotIn("future_viewer_actions", metadata)
        self.assertNotIn("do_not_auto_merge", metadata)

        drift = _drift_by_id(expectations, "descriptor_metadata_incomplete")
        self.assertEqual(drift.get("observed_behavior"), "review_entity_generic_without_descriptor_metadata_bundle")

    def _assert_missing_signal_drift_explicit(self, *, expectations: dict) -> None:
        for drift_id in [
            "descriptor_signal_missing_for_novel_facts",
            "role_descriptor_missing_attach_signal",
            "relationship_descriptor_missing_impact_signal",
        ]:
            drift = _drift_by_id(expectations, drift_id)
            self.assertTrue(drift.get("accepted_temporarily"))
            self.assertEqual(drift.get("decision"), "accept_temporarily")

    def _assert_suppression_regression(self, *, obsidian_import: dict, review_queue: dict) -> None:
        for surface in SUPPRESSED_SURFACES:
            self.assertFalse(_is_primary_entity(obsidian_import, surface), surface)
            item = _review_item_by_surface(review_queue, surface)
            if item is None:
                continue
            self.assertNotEqual(item.get("suggested_action"), "review_enrich_existing_entity")
            self.assertNotEqual(item.get("suggested_action"), "review_attach_role_or_title")
            self.assertNotEqual(item.get("review_type"), "entity_retention_review")

    def _assert_identity_and_object_regression_guards(self) -> None:
        role_test_source = Path("tests/test_textifai_descriptor_role_review_signal_decision.py").read_text(encoding="utf-8")
        object_test_source = Path("tests/test_textifai_object_retention_signal_normalization.py").read_text(encoding="utf-8")
        semantic_edge_contract_source = Path("tests/test_textifai_semantic_edge_replay_contracts.py").read_text(encoding="utf-8")
        self.assertIn("review_enrich_existing_entity", role_test_source)
        self.assertIn("review_attach_role_or_title", role_test_source)
        self.assertIn("llave de cristal", object_test_source)
        self.assertIn("la princesa", object_test_source)
        self.assertIn("la heredera silenciosa", role_test_source)
        self.assertIn("ella", semantic_edge_contract_source)

    def _assert_anti_hardcode_guardrails(self) -> None:
        runtime_source = RUNTIME_GUARD_PATH.read_text(encoding="utf-8")
        for literal in FIXTURE_LITERALS:
            self.assertNotIn(literal, runtime_source)
        for drift_id in DRIFT_IDS:
            self.assertNotIn(drift_id, runtime_source)


def _load_json(path: Path):
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


def _review_item_by_source(review_queue: dict, source_entity: str) -> dict | None:
    for item in review_queue.get("items") or []:
        if item.get("source_entity") == source_entity:
            return item
    return None


def _review_item_by_surface(review_queue: dict, surface: str) -> dict | None:
    for item in review_queue.get("items") or []:
        if item.get("source_entity") == surface or item.get("target_text") == surface:
            return item
        evidence = item.get("evidence") or []
        if any(entry.get("text") == surface for entry in evidence if isinstance(entry, dict)):
            return item
    return None


def _promotion_decision_by_name(promotion_audit: dict, canonical_name: str) -> dict | None:
    for item in promotion_audit.get("decisions") or []:
        if item.get("canonical_name") == canonical_name:
            return item
    return None


def _drift_by_id(expectations: dict, drift_id: str) -> dict:
    sections = [
        "accepted_temporary_drift",
        "resolved_current_behavior",
        "known_current_drift",
    ]
    for section in sections:
        for item in expectations.get(section) or []:
            if item.get("drift_id") == drift_id:
                return item
    raise AssertionError(f"Missing drift expectation: {drift_id}")


def _drift_by_surface(expectations: dict, drift_id: str, surface_text: str) -> dict:
    matches = [
        item
        for item in expectations.get("known_current_drift") or []
        if item.get("drift_id") == drift_id and item.get("surface_text") == surface_text
    ]
    if not matches:
        raise AssertionError(f"Missing drift expectation: {drift_id}:{surface_text}")
    return matches[0]


def _surface_exists_in_replay_input(surface_text: str) -> bool:
    return _replay_input_entity(surface_text) is not None


def _replay_input_entity(surface_text: str) -> dict | None:
    for chapter_path in sorted((REPLAY_INPUT_ROOT / "chapter_outputs").glob("*.json")):
        payload = _load_json(chapter_path)
        for chapter in payload.get("chapters") or []:
            for entity in chapter.get("entities") or []:
                if entity.get("canonical_name") == surface_text:
                    return entity
    return None


def _is_primary_entity(obsidian_import: dict, canonical_name: str) -> bool:
    entity = _entity_by_name(obsidian_import.get("entities") or [], canonical_name)
    if entity is None:
        return False
    review_state = str(entity.get("review_state") or "").casefold()
    note_role = str(entity.get("note_role") or "").casefold()
    return review_state == "canonical" or note_role == "primary"


if __name__ == "__main__":
    unittest.main()
