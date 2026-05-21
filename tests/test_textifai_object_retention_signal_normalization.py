from __future__ import annotations

import unittest

from textifai.vaerl.review_queue import build_review_queue


class TextifAIObjectRetentionSignalNormalizationTests(unittest.TestCase):
    def test_durable_object_review_entity_is_normalized_to_retention_signal(self):
        queue = build_review_queue(
            obsidian_import={
                "entities": [
                    {
                        "canonical_name": "Sera Valen",
                        "preferred_slug": "sera_valen",
                        "entity_kind": "character",
                        "aliases": ["Sera"],
                        "source_mentions": ["Sera Valen", "Sera"],
                        "review_state": "canonical",
                        "note_role": "primary",
                        "relationships": [],
                        "key_facts": ["Primary entity."],
                        "chapter_refs": ["ch_001"],
                        "confidence": 0.93,
                    },
                    {
                        "canonical_name": "llave de cristal",
                        "preferred_slug": "llave_de_cristal",
                        "entity_kind": "object",
                        "aliases": [],
                        "source_mentions": ["llave de cristal"],
                        "review_state": "review",
                        "note_role": "review",
                        "relationships": [],
                        "key_facts": [
                            "Aparece en varios capítulos.",
                            "Permite abrir la salida."
                        ],
                        "chapter_refs": ["ch_001", "ch_002", "ch_003"],
                        "confidence": 0.83,
                        "review_reason": "Objeto durable no retenido como primary.",
                        "review_reason_code": "weak_or_descriptive_naming",
                        "surface_type": "object_like",
                        "language_hint": "es",
                    },
                ]
            }
        )
        item = next(item for item in (queue.get("items") or []) if item.get("source_entity") == "llave de cristal")
        self.assertEqual(item.get("review_type"), "entity_retention_review")
        self.assertEqual(item.get("suggested_action"), "review_create_primary")
        metadata = item.get("metadata") or {}
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertEqual(metadata.get("candidate_status"), "no_clear_existing_primary")
        self.assertEqual(metadata.get("surface_type"), "object_like")
        self.assertEqual(metadata.get("semantic_value"), "persistent_object")
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertIn("promote", metadata.get("future_viewer_actions") or [])
        self.assertIn("keep_secondary", metadata.get("future_viewer_actions") or [])
        self.assertIn("reject_noise", metadata.get("future_viewer_actions") or [])

    def test_descriptor_review_entity_is_not_broadly_reclassified_in_this_phase(self):
        queue = build_review_queue(
            obsidian_import={
                "entities": [
                    {
                        "canonical_name": "Sera Valen",
                        "preferred_slug": "sera_valen",
                        "entity_kind": "character",
                        "aliases": ["Sera"],
                        "source_mentions": ["Sera Valen", "Sera"],
                        "review_state": "canonical",
                        "note_role": "primary",
                        "relationships": [],
                        "key_facts": ["Primary entity."],
                        "chapter_refs": ["ch_001"],
                        "confidence": 0.93,
                    },
                    {
                        "canonical_name": "la princesa",
                        "preferred_slug": "la_princesa",
                        "entity_kind": "character",
                        "aliases": [],
                        "source_mentions": ["la princesa"],
                        "review_state": "review",
                        "note_role": "review",
                        "relationships": [],
                        "key_facts": ["Descriptor absorbido."],
                        "chapter_refs": ["ch_001"],
                        "confidence": 0.7,
                        "review_reason": "Descriptor absorbido como alias/source mention.",
                        "review_reason_code": "weak_or_descriptive_naming",
                        "surface_type": "title_like",
                        "language_hint": "es",
                    },
                ]
            }
        )
        item = next(item for item in (queue.get("items") or []) if item.get("source_entity") == "la princesa")
        self.assertEqual(item.get("review_type"), "review_entity")
        self.assertEqual(item.get("suggested_action"), "merge_into_primary_or_keep_review")


if __name__ == "__main__":
    unittest.main()
