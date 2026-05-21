from __future__ import annotations

import unittest

from textifai.vaerl.review_queue import build_review_queue


class TextifAIRetentionReviewPolicyTests(unittest.TestCase):
    def test_omitted_persistent_object_without_candidate_uses_medium_create_primary(self):
        obsidian_import = {
            "entities": [
                _canonical_primary("Mara Elian"),
                _canonical_primary("Toren"),
            ]
        }
        retention_context = {
            "promotion_decisions": [
                {
                    "canonical_name": "brújula de plata",
                    "entity_kind": "object",
                    "surface_type": "object_like",
                    "language_hint": "es",
                    "decision": "discard",
                    "reason": "dropped_durable_object_without_primary_target",
                    "metrics": {
                        "chapter_ref_count": 2,
                        "fact_count": 2,
                        "source_mention_count": 3,
                    },
                }
            ],
            "resolved_entities": [
                {
                    "canonical_name": "brújula de plata",
                    "entity_kind": "object",
                    "preferred_slug": "brujula_de_plata",
                    "aliases": [],
                    "source_mentions": ["brújula de plata"],
                    "key_facts": ["Objeto recurrente clave."],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "relationships": [],
                    "confidence": 0.63,
                    "review_state": "review",
                    "surface_type": "object_like",
                    "language_hint": "es",
                }
            ],
        }

        queue = build_review_queue(obsidian_import=obsidian_import, retention_context=retention_context)
        item = _review_item_by_source(queue, "brújula de plata")
        self.assertIsNotNone(item)
        self.assertEqual(queue.get("schema_version"), "textifai.review_queue.v1")
        self.assertEqual(item.get("suggested_action"), "review_create_primary")
        self.assertEqual(item.get("severity"), "medium")
        self.assertEqual(item.get("candidate_entities"), [])

        metadata = item.get("metadata") or {}
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertEqual(metadata.get("candidate_status"), "no_clear_existing_primary")
        self.assertEqual(metadata.get("semantic_value"), "persistent_object")
        self.assertEqual(metadata.get("surface_type"), "object_like")
        self.assertEqual(metadata.get("language_hint"), "es")
        self.assertTrue(metadata.get("do_not_auto_merge"))

    def test_descriptor_signal_is_language_agnostic_with_surface_type_hint(self):
        obsidian_import = {"entities": [_canonical_primary("Sera")]}
        for surface, language_hint in [("la princesa", "es"), ("the princess", "en")]:
            with self.subTest(surface=surface, language_hint=language_hint):
                queue = build_review_queue(
                    obsidian_import=obsidian_import,
                    retention_context={
                        "promotion_decisions": [
                            {
                                "canonical_name": surface,
                                "entity_kind": "character",
                                "surface_type": "title_like",
                                "language_hint": language_hint,
                                "decision": "discard",
                                "reason": "title_descriptor_overlap_with_primary",
                                "metrics": {
                                    "chapter_ref_count": 2,
                                    "fact_count": 2,
                                    "source_mention_count": 2,
                                },
                            }
                        ],
                        "resolved_entities": [
                            {
                                "canonical_name": surface,
                                "entity_kind": "character",
                                "preferred_slug": surface.replace(" ", "_"),
                                "aliases": ["Sera"],
                                "source_mentions": [surface, "Sera"],
                                "key_facts": [f"{surface} protege la ciudad."],
                                "chapter_refs": ["ch_001", "ch_002"],
                                "relationships": [],
                                "confidence": 0.71,
                                "review_state": "review",
                                "surface_type": "title_like",
                                "language_hint": language_hint,
                            }
                        ],
                    },
                )
                item = _review_item_by_source(queue, surface)
                self.assertIsNotNone(item)
                self.assertEqual(item.get("suggested_action"), "review_attach_role_or_title")
                self.assertTrue(item.get("candidate_entities"))

                metadata = item.get("metadata") or {}
                self.assertEqual(metadata.get("signal_tier"), "medium")
                self.assertIn(metadata.get("candidate_status"), {"strong_candidate", "weak_candidate"})
                self.assertEqual(metadata.get("surface_type"), "title_like")
                self.assertEqual(metadata.get("semantic_value"), "title")
                self.assertEqual(metadata.get("language_hint"), language_hint)
                self.assertTrue(metadata.get("do_not_auto_merge"))

    def test_pronouns_and_ephemeral_mentions_are_suppressed(self):
        obsidian_import = {"entities": [_canonical_primary("Sera")]}

        pronoun_queue = build_review_queue(
            obsidian_import=obsidian_import,
            retention_context={
                "promotion_decisions": [
                    {
                        "canonical_name": "ella",
                        "entity_kind": "character",
                        "surface_type": "pronoun_like",
                        "language_hint": "es",
                        "decision": "discard",
                        "reason": "pronoun_surface_without_anchor",
                        "metrics": {"chapter_ref_count": 2, "fact_count": 2, "source_mention_count": 3},
                    },
                    {
                        "canonical_name": "she",
                        "entity_kind": "character",
                        "surface_type": "pronoun_like",
                        "language_hint": "en",
                        "decision": "discard",
                        "reason": "pronoun_surface_without_anchor",
                        "metrics": {"chapter_ref_count": 2, "fact_count": 2, "source_mention_count": 3},
                    },
                ]
            },
        )
        self.assertIsNone(_review_item_by_source(pronoun_queue, "ella"))
        self.assertIsNone(_review_item_by_source(pronoun_queue, "she"))

        ephemeral_queue = build_review_queue(
            obsidian_import=obsidian_import,
            retention_context={
                "promotion_decisions": [
                    {
                        "canonical_name": "guardia cansado",
                        "entity_kind": "character",
                        "surface_type": "descriptor_like",
                        "language_hint": "es",
                        "decision": "discard",
                        "reason": "single_chapter_ephemeral_descriptor",
                        "metrics": {"chapter_ref_count": 1, "fact_count": 1, "source_mention_count": 1},
                    }
                ],
                "resolved_entities": [
                    {
                        "canonical_name": "guardia cansado",
                        "entity_kind": "character",
                        "preferred_slug": "guardia_cansado",
                        "aliases": [],
                        "source_mentions": ["guardia cansado"],
                        "key_facts": ["Mención episódica breve."],
                        "chapter_refs": ["ch_001"],
                        "relationships": [],
                        "confidence": 0.42,
                        "review_state": "review",
                        "surface_type": "descriptor_like",
                        "language_hint": "es",
                    }
                ],
            },
        )
        self.assertIsNone(_review_item_by_source(ephemeral_queue, "guardia cansado"))


def _canonical_primary(canonical_name: str) -> dict:
    return {
        "canonical_name": canonical_name,
        "preferred_slug": canonical_name.casefold().replace(" ", "_"),
        "entity_kind": "character",
        "aliases": [],
        "source_mentions": [canonical_name],
        "review_state": "canonical",
        "note_role": "primary",
        "relationships": [],
        "key_facts": [f"{canonical_name} entidad principal."],
        "chapter_refs": ["ch_001"],
        "confidence": 0.9,
    }


def _review_item_by_source(queue: dict, source_entity: str) -> dict | None:
    for item in queue.get("items") or []:
        if item.get("source_entity") == source_entity:
            return item
    return None


if __name__ == "__main__":
    unittest.main()
