from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/identity_alias_role")
EXPECTED_ROOT = FIXTURE_ROOT / "expected"
OBSIDIAN_IMPORT_PATH = EXPECTED_ROOT / "obsidian_import.json"
REVIEW_QUEUE_PATH = EXPECTED_ROOT / "review_queue.json"
DRIFT_EXPECTATIONS_PATH = EXPECTED_ROOT / "replay_drift_expectations.json"


class TextifAISemanticEdgeRetentionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.obsidian_import = _load_json(OBSIDIAN_IMPORT_PATH)
        self.review_queue = _load_json(REVIEW_QUEUE_PATH)
        self.drift_expectations = _load_json(DRIFT_EXPECTATIONS_PATH)

    def test_canonical_identity_and_alias_expectations(self):
        entities = self.obsidian_import.get("entities") or []
        sera = _entity_by_name(entities, "Sera Valen")
        ren = _entity_by_name(entities, "Ren Tal")
        self.assertIsNotNone(sera)
        self.assertIsNotNone(ren)
        self.assertEqual(sera.get("review_state"), "canonical")
        self.assertEqual(ren.get("review_state"), "canonical")
        self.assertIn("Sera", sera.get("aliases") or [])
        self.assertIn("Ren", ren.get("aliases") or [])

    def test_pronoun_suppression_expected(self):
        entities = self.obsidian_import.get("entities") or []
        self.assertIsNone(_entity_by_name(entities, "ella"))
        for item in self.review_queue.get("items") or []:
            self.assertNotEqual(item.get("source_entity"), "ella")
            candidates = item.get("candidate_entities") or []
            self.assertFalse(any(candidate.get("canonical_name") == "ella" for candidate in candidates))

    def test_title_role_signal_points_to_sera_valen(self):
        entities = self.obsidian_import.get("entities") or []
        self.assertIsNone(_entity_by_name(entities, "la princesa"))
        item = _review_item_by_source(self.review_queue, "la princesa")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("suggested_action"), "review_attach_role_or_title")
        self.assertEqual(item.get("candidate_entities")[0].get("canonical_name"), "Sera Valen")
        metadata = item.get("metadata") or {}
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertEqual(metadata.get("surface_type"), "title_like")
        self.assertIn(metadata.get("semantic_value"), {"title", "role", "descriptor"})
        self.assertEqual(metadata.get("language_hint"), "es")
        self.assertIn("attach_role_or_title", metadata.get("future_viewer_actions") or [])

    def test_descriptor_with_facts_points_to_enrichment_review(self):
        entities = self.obsidian_import.get("entities") or []
        self.assertIsNone(_entity_by_name(entities, "la heredera silenciosa"))
        item = _review_item_by_source(self.review_queue, "la heredera silenciosa")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("suggested_action"), "review_enrich_existing_entity")
        self.assertEqual(item.get("candidate_entities")[0].get("canonical_name"), "Sera Valen")
        metadata = item.get("metadata") or {}
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertEqual(metadata.get("surface_type"), "descriptor_like")
        self.assertEqual(metadata.get("semantic_value"), "descriptor")
        self.assertIn("enrich_existing_entity", metadata.get("future_viewer_actions") or [])

    def test_persistent_object_has_actionable_contract(self):
        entities = self.obsidian_import.get("entities") or []
        object_entity = _entity_by_name(entities, "llave de cristal")
        self.assertIsNotNone(object_entity)
        self.assertEqual(object_entity.get("entity_kind"), "object")
        item = _review_item_by_source(self.review_queue, "llave de cristal")
        self.assertIsNotNone(item)
        self.assertIn(item.get("suggested_action"), {"review_create_primary", "review_keep_secondary"})
        metadata = item.get("metadata") or {}
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertEqual(metadata.get("candidate_status"), "no_clear_existing_primary")
        self.assertEqual(metadata.get("surface_type"), "object_like")
        self.assertEqual(metadata.get("semantic_value"), "persistent_object")

    def test_ephemeral_mention_not_promoted_and_not_strong_review(self):
        entities = self.obsidian_import.get("entities") or []
        self.assertIsNone(_entity_by_name(entities, "guardia somnoliento"))
        self.assertIsNone(_review_item_by_source(self.review_queue, "guardia somnoliento"))

    def test_language_agnostic_metadata_present_in_review_items(self):
        expected_surfaces = {"la princesa", "la heredera silenciosa", "llave de cristal"}
        items = self.review_queue.get("items") or []
        found_surfaces = {item.get("source_entity") for item in items}
        self.assertTrue(expected_surfaces.issubset(found_surfaces))
        for item in items:
            metadata = item.get("metadata") or {}
            self.assertIn("surface_type", metadata)
            self.assertIn("semantic_value", metadata)
            self.assertIn("candidate_status", metadata)
            self.assertIn("language_hint", metadata)
            self.assertIn("do_not_auto_merge", metadata)
            self.assertIn("future_viewer_actions", metadata)

        notes = self.drift_expectations.get("language_agnostic_notes") or []
        self.assertTrue(notes)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entity_by_name(entities: list[dict], canonical_name: str) -> dict | None:
    for entity in entities:
        if entity.get("canonical_name") == canonical_name:
            return entity
    return None


def _review_item_by_source(queue: dict, source_entity: str) -> dict | None:
    for item in queue.get("items") or []:
        if item.get("source_entity") == source_entity:
            return item
    return None


if __name__ == "__main__":
    unittest.main()
