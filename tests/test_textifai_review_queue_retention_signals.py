from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay
from textifai.vaerl.review_queue import build_review_queue


REPLAY_INPUT_ROOT = Path("tests/fixtures/textifai/minimal_novel/replay_input")


class TextifAIReviewQueueRetentionSignalsTests(unittest.TestCase):
    def test_replay_generates_actionable_object_retention_review_signal(self):
        with tempfile.TemporaryDirectory(prefix="textifai_retention_signal_") as temp_root:
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

            obsidian_import = _load_json(Path(result.obsidian_import_path))
            review_queue = _load_json(Path(result.review_queue_path))

            self.assertIsNone(_primary_entity_by_name(obsidian_import.get("entities") or [], "brújula de plata"))
            self.assertIsNone(_primary_entity_by_name(obsidian_import.get("entities") or [], "guardia cansado"))
            self.assertIsNone(_primary_entity_by_name(obsidian_import.get("entities") or [], "curandera adormilada"))

            item = _review_item_by_source(review_queue, "brújula de plata")
            self.assertIsNotNone(item)
            self.assertEqual(item.get("review_type"), "entity_retention_review")
            self.assertEqual(item.get("severity"), "medium")
            self.assertEqual(item.get("suggested_action"), "review_create_primary")
            self.assertEqual(item.get("target_text"), "brújula de plata")
            self.assertEqual(item.get("candidate_entities"), [])
            self.assertTrue(item.get("evidence"))

            metadata = item.get("metadata") or {}
            self.assertEqual(metadata.get("entity_kind"), "object")
            self.assertTrue(metadata.get("do_not_auto_merge"))
            self.assertTrue(metadata.get("no_clear_existing_primary"))
            self.assertTrue(metadata.get("retention_review_required"))
            self.assertEqual(metadata.get("candidate_status"), "no_clear_existing_primary")
            self.assertEqual(metadata.get("signal_tier"), "medium")
            self.assertEqual(metadata.get("surface_type"), "object_like")
            self.assertEqual(metadata.get("semantic_value"), "persistent_object")
            self.assertIsInstance(metadata.get("future_viewer_actions"), list)
            self.assertIn("promote", metadata.get("future_viewer_actions") or [])
            self.assertIn("ch_001", metadata.get("chapter_refs") or [])

            self.assertIsNone(_review_item_by_source(review_queue, "guardia cansado"))
            self.assertIsNone(_review_item_by_source(review_queue, "curandera adormilada"))

            expected_prefix = output_root.resolve()
            self.assertTrue(Path(result.review_queue_path).resolve().is_relative_to(expected_prefix))

    def test_descriptor_role_signal_suggests_candidate_without_auto_merge(self):
        obsidian_import = {
            "entities": [
                {
                    "canonical_name": "Sera",
                    "preferred_slug": "sera",
                    "entity_kind": "character",
                    "aliases": [],
                    "source_mentions": ["Sera"],
                    "review_state": "canonical",
                    "note_role": "primary",
                    "relationships": [],
                    "key_facts": ["Sera lidera la escena."],
                    "chapter_refs": ["ch_001"],
                }
            ]
        }
        retention_context = {
            "promotion_decisions": [
                {
                    "canonical_name": "la princesa",
                    "entity_kind": "character",
                    "naming_quality": "descriptor",
                    "surface_type": "title_like",
                    "language_hint": "es",
                    "decision": "discard",
                    "reason": "descriptor_with_possible_canonical_target",
                    "metrics": {
                        "chapter_ref_count": 2,
                        "fact_count": 2,
                        "source_mention_count": 2,
                    },
                }
            ],
            "resolved_entities": [
                {
                    "canonical_name": "la princesa",
                    "entity_kind": "character",
                    "preferred_slug": "la_princesa",
                    "aliases": ["Sera"],
                    "source_mentions": ["la princesa", "Sera"],
                    "key_facts": ["La princesa decide proteger la ciudad."],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "relationships": [],
                    "confidence": 0.72,
                    "review_state": "review",
                    "naming_quality": "descriptor",
                    "surface_type": "title_like",
                    "language_hint": "es",
                }
            ],
        }

        queue = build_review_queue(obsidian_import=obsidian_import, retention_context=retention_context)
        item = _review_item_by_source(queue, "la princesa")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("review_type"), "entity_retention_review")
        self.assertEqual(item.get("suggested_action"), "review_attach_role_or_title")
        self.assertTrue(item.get("candidate_entities"))
        self.assertEqual(item["candidate_entities"][0]["canonical_name"], "Sera")

        metadata = item.get("metadata") or {}
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertFalse(metadata.get("no_clear_existing_primary"))
        self.assertEqual(metadata.get("naming_quality"), "descriptor")
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertEqual(metadata.get("candidate_status"), "weak_candidate")
        self.assertEqual(metadata.get("surface_type"), "title_like")
        self.assertEqual(metadata.get("semantic_value"), "title")
        self.assertEqual(metadata.get("language_hint"), "es")
        self.assertIn("attach_role_or_title", metadata.get("future_viewer_actions") or [])

    def test_pronoun_signal_never_gets_strong_primary_candidate(self):
        obsidian_import = {
            "entities": [
                {
                    "canonical_name": "Sera",
                    "preferred_slug": "sera",
                    "entity_kind": "character",
                    "aliases": [],
                    "source_mentions": ["Sera"],
                    "review_state": "canonical",
                    "note_role": "primary",
                    "relationships": [],
                    "key_facts": ["Sera lidera la escena."],
                    "chapter_refs": ["ch_001"],
                }
            ]
        }
        retention_context = {
            "promotion_decisions": [
                {
                    "canonical_name": "ella",
                    "entity_kind": "character",
                    "naming_quality": "pronoun_like",
                    "decision": "discard",
                    "reason": "pronoun_like_surface",
                    "metrics": {
                        "chapter_ref_count": 2,
                        "fact_count": 2,
                        "source_mention_count": 2,
                    },
                }
            ],
            "resolved_entities": [
                {
                    "canonical_name": "ella",
                    "entity_kind": "character",
                    "preferred_slug": "ella",
                    "aliases": ["Sera"],
                    "source_mentions": ["ella", "Sera"],
                    "key_facts": ["Ella protege la ciudad."],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "relationships": [],
                    "confidence": 0.6,
                    "review_state": "review",
                    "naming_quality": "pronoun_like",
                }
            ],
        }

        queue = build_review_queue(obsidian_import=obsidian_import, retention_context=retention_context)
        self.assertIsNone(_review_item_by_source(queue, "ella"))
        self.assertEqual(queue["item_count"], 0)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _primary_entity_by_name(entities: list[dict], canonical_name: str) -> dict | None:
    for entity in entities:
        if entity.get("canonical_name") == canonical_name and (
            str(entity.get("review_state") or "").casefold() == "canonical"
            or str(entity.get("note_role") or "").casefold() == "primary"
        ):
            return entity
    return None


def _review_item_by_source(queue: dict, source_entity: str) -> dict | None:
    for item in queue.get("items") or []:
        if item.get("source_entity") == source_entity:
            return item
    return None


if __name__ == "__main__":
    unittest.main()
