from __future__ import annotations

import unittest
from pathlib import Path

from textifai.vaerl.review_queue import build_review_queue


class TextifAIDescriptorRoleReviewSignalDecisionTests(unittest.TestCase):
    def test_absorbed_title_surface_generates_role_attachment_signal(self):
        queue = build_review_queue(
            obsidian_import={"entities": [_primary("Ari Mar", aliases=["captain of glass"])]},
            retention_context={
                "global_entities": [
                    {
                        "canonical_name": "captain of glass",
                        "canonical_candidate": "Ari Mar",
                        "entity_kind": "character",
                        "preferred_slug": "captain_of_glass",
                        "source_mentions": ["captain of glass"],
                        "key_facts": ["Surface marks a title used for Ari Mar."],
                        "chapter_refs": ["ch_001"],
                        "relationships": [{"target": "Ari Mar", "type": "related_to"}],
                        "confidence": 0.72,
                        "review_state": "review",
                        "naming_quality": "descriptor",
                        "surface_type": "title_like",
                        "language_hint": "en",
                        "semantic_value": "title",
                    }
                ]
            },
        )

        item = _review_item_by_source(queue, "captain of glass")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("review_type"), "entity_retention_review")
        self.assertEqual(item.get("suggested_action"), "review_attach_role_or_title")
        self.assertEqual(item.get("candidate_entities")[0].get("canonical_name"), "Ari Mar")
        metadata = item.get("metadata") or {}
        self.assertEqual(metadata.get("surface_type"), "title_like")
        self.assertEqual(metadata.get("semantic_value"), "title")
        self.assertEqual(metadata.get("language_hint"), "en")
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertIn("attach_role_or_title", metadata.get("future_viewer_actions") or [])

    def test_absorbed_descriptor_with_enrichment_evidence_generates_enrichment_signal(self):
        queue = build_review_queue(
            obsidian_import={"entities": [_primary("Ari Mar", aliases=["silent heir"])]},
            retention_context={
                "global_entities": [
                    {
                        "canonical_name": "silent heir",
                        "canonical_candidate": "Ari Mar",
                        "entity_kind": "character",
                        "preferred_slug": "silent_heir",
                        "source_mentions": ["silent heir"],
                        "key_facts": [
                            "Keeps the oath that protects the map.",
                            "Knows the hidden passage under the archive.",
                        ],
                        "chapter_refs": ["ch_002"],
                        "relationships": [{"target": "Ari Mar", "type": "related_to"}],
                        "confidence": 0.76,
                        "review_state": "review",
                        "naming_quality": "descriptor",
                        "surface_type": "descriptor_like",
                        "language_hint": "en",
                        "semantic_value": "descriptor",
                    }
                ]
            },
        )

        item = _review_item_by_source(queue, "silent heir")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("review_type"), "entity_retention_review")
        self.assertEqual(item.get("suggested_action"), "review_enrich_existing_entity")
        self.assertEqual(item.get("candidate_entities")[0].get("canonical_name"), "Ari Mar")
        metadata = item.get("metadata") or {}
        self.assertEqual(metadata.get("surface_type"), "descriptor_like")
        self.assertEqual(metadata.get("semantic_value"), "descriptor")
        self.assertEqual(metadata.get("signal_tier"), "medium")
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertIn("enrich_existing_entity", metadata.get("future_viewer_actions") or [])

    def test_generic_descriptor_with_weak_evidence_remains_suppressed(self):
        queue = build_review_queue(
            obsidian_import={"entities": [_primary("Ari Mar", aliases=["the youth"])]},
            retention_context={
                "global_entities": [
                    {
                        "canonical_name": "the youth",
                        "canonical_candidate": "Ari Mar",
                        "entity_kind": "character",
                        "preferred_slug": "the_youth",
                        "source_mentions": ["the youth"],
                        "key_facts": ["Repeats the plan quietly."],
                        "chapter_refs": ["ch_003"],
                        "relationships": [{"target": "Ari Mar", "type": "related_to"}],
                        "confidence": 0.68,
                        "review_state": "review",
                        "naming_quality": "descriptor",
                        "surface_type": "descriptor_like",
                        "language_hint": "en",
                        "semantic_value": "descriptor",
                    }
                ]
            },
        )

        self.assertIsNone(_review_item_by_source(queue, "the youth"))

    def test_fixture_strings_are_not_runtime_conditions(self):
        runtime_source = Path("textifai/vaerl/review_queue.py").read_text(encoding="utf-8")
        forbidden_runtime_terms = [
            "la princesa",
            "la heredera silenciosa",
            "el muchacho",
            "Sera Valen",
            "Ren Tal",
            "title_surface_alias_without_review_signal",
            "descriptor_surface_alias_without_enrichment_signal",
            "ren_descriptor_alias_without_review_signal",
        ]
        for term in forbidden_runtime_terms:
            self.assertNotIn(term, runtime_source)


def _primary(canonical_name: str, *, aliases: list[str]) -> dict:
    return {
        "canonical_name": canonical_name,
        "preferred_slug": canonical_name.casefold().replace(" ", "_"),
        "entity_kind": "character",
        "aliases": aliases,
        "source_mentions": [canonical_name, *aliases],
        "review_state": "canonical",
        "note_role": "primary",
        "relationships": [],
        "key_facts": [f"{canonical_name} is canonical."],
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
