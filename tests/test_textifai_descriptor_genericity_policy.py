from __future__ import annotations

import unittest
from pathlib import Path

from textifai.vaerl.review_queue import build_review_queue


class TextifAIDescriptorGenericityPolicyTests(unittest.TestCase):
    def test_generic_weak_descriptor_is_suppressed(self):
        queue = _queue_for_absorbed_surface(
            surface="the youth",
            canonical="Ari Mar",
            source_mentions=["the youth"],
            key_facts=[],
            chapter_refs=["ch_003"],
            confidence=0.68,
            category="generic_descriptor",
        )
        self.assertIsNone(_review_item_by_source(queue, "the youth"))

    def test_generic_multichapter_without_novel_facts_is_not_medium_by_default(self):
        queue = _queue_for_absorbed_surface(
            surface="the youth",
            canonical="Ari Mar",
            source_mentions=["the youth", "the youth"],
            key_facts=["Waits near the gate."],
            chapter_refs=["ch_001", "ch_003"],
            confidence=0.73,
            category="generic_descriptor",
        )
        item = _review_item_by_source(queue, "the youth")
        if item is not None:
            self.assertIn(item.get("severity"), {"low"})
            self.assertNotEqual(item.get("suggested_action"), "review_enrich_existing_entity")

    def test_descriptor_with_novel_facts_emits_enrich(self):
        queue = _queue_for_absorbed_surface(
            surface="silent heir",
            canonical="Ari Mar",
            source_mentions=["silent heir", "silent heir"],
            key_facts=[
                "Keeps the oath that protects the map.",
                "Knows the hidden passage under the archive.",
            ],
            chapter_refs=["ch_002", "ch_003"],
            confidence=0.78,
            category="epithet_descriptor",
        )
        item = _review_item_by_source(queue, "silent heir")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("suggested_action"), "review_enrich_existing_entity")
        self.assertEqual(item.get("severity"), "medium")
        self.assertTrue((item.get("metadata") or {}).get("do_not_auto_merge"))

    def test_role_title_status_descriptor_emits_attach_or_enrich(self):
        role_queue = _queue_for_absorbed_surface(
            surface="captain of glass",
            canonical="Ari Mar",
            source_mentions=["captain of glass"],
            key_facts=["Surface marks formal role used for Ari Mar."],
            chapter_refs=["ch_001"],
            confidence=0.72,
            category="role_descriptor",
            surface_type="role_like",
            semantic_value="role",
        )
        role_item = _review_item_by_source(role_queue, "captain of glass")
        self.assertIsNotNone(role_item)
        self.assertEqual(role_item.get("suggested_action"), "review_attach_role_or_title")
        self.assertEqual(role_item.get("severity"), "medium")

        status_queue = _queue_for_absorbed_surface(
            surface="the fallen heir",
            canonical="Ari Mar",
            source_mentions=["the fallen heir", "the fallen heir"],
            key_facts=["Lost formal standing after the council vote."],
            chapter_refs=["ch_002", "ch_003"],
            confidence=0.79,
            category="status_descriptor",
        )
        status_item = _review_item_by_source(status_queue, "the fallen heir")
        self.assertIsNotNone(status_item)
        self.assertIn(status_item.get("suggested_action"), {"review_attach_role_or_title", "review_enrich_existing_entity"})

    def test_relationship_descriptor_impact_emits_review(self):
        queue = _queue_for_absorbed_surface(
            surface="oathbound ally",
            canonical="Ari Mar",
            source_mentions=["oathbound ally", "oathbound ally"],
            key_facts=["Shares a binding oath with Nera Sol."],
            chapter_refs=["ch_001", "ch_002"],
            confidence=0.77,
            category="relationship_descriptor",
            relationships=[{"target": "Nera Sol", "type": "alliance"}],
        )
        item = _review_item_by_source(queue, "oathbound ally")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("severity"), "medium")

    def test_pronoun_like_stays_suppressed(self):
        queue = build_review_queue(
            obsidian_import={"entities": [_primary("Ari Mar")]},
            retention_context={
                "global_entities": [
                    {
                        "canonical_name": "they",
                        "entity_kind": "character",
                        "preferred_slug": "they",
                        "source_mentions": ["they", "they"],
                        "key_facts": ["Pronoun only."],
                        "chapter_refs": ["ch_001", "ch_002"],
                        "relationships": [],
                        "confidence": 0.9,
                        "review_state": "review",
                        "naming_quality": "pronoun_like",
                        "surface_type": "pronoun_like",
                        "language_hint": "en",
                        "semantic_value": "noise",
                    }
                ]
            },
        )
        self.assertIsNone(_review_item_by_source(queue, "they"))

    def test_language_agnostic_equivalent_surfaces_get_same_decision(self):
        first = _queue_for_absorbed_surface(
            surface="the youth",
            canonical="Ari Mar",
            source_mentions=["the youth"],
            key_facts=[],
            chapter_refs=["ch_003"],
            confidence=0.68,
            category="generic_descriptor",
            language_hint="en",
        )
        second = _queue_for_absorbed_surface(
            surface="joven guardián",
            canonical="Ari Mar",
            source_mentions=["joven guardián"],
            key_facts=[],
            chapter_refs=["ch_003"],
            confidence=0.68,
            category="generic_descriptor",
            language_hint="es",
        )
        self.assertEqual(_review_item_by_source(first, "the youth") is None, _review_item_by_source(second, "joven guardián") is None)

    def test_review_state_candidate_emits_descriptor_signal_without_primary_promotion(self):
        queue = build_review_queue(
            obsidian_import={
                "entities": [
                    {
                        "canonical_name": "Atlas Vey",
                        "preferred_slug": "atlas_vey",
                        "entity_kind": "character",
                        "aliases": ["silent heir"],
                        "source_mentions": ["Atlas Vey", "silent heir"],
                        "review_state": "review",
                        "note_role": "review",
                        "chapter_refs": ["ch_001", "ch_002"],
                        "key_facts": ["Stable cluster in review.", "Carries map memory."],
                        "relationships": [],
                        "confidence": 0.77,
                        "naming_quality": "descriptor",
                        "surface_type": "named_entity_like",
                        "semantic_value": "durable_entity",
                    }
                ]
            },
            retention_context={
                "global_entities": [
                    {
                        "canonical_name": "silent heir",
                        "canonical_candidate": "Atlas Vey",
                        "entity_kind": "character",
                        "preferred_slug": "silent_heir",
                        "source_mentions": ["silent heir", "silent heir"],
                        "key_facts": ["Knows the hidden passage under the archive.", "Protects map oath details."],
                        "chapter_refs": ["ch_002"],
                        "relationships": [{"target": "Atlas Vey", "type": "related_to"}],
                        "confidence": 0.79,
                        "review_state": "review",
                        "naming_quality": "descriptor",
                        "surface_type": "descriptor_like",
                        "language_hint": "en",
                        "semantic_value": "descriptor",
                        "descriptor_category": "epithet_descriptor",
                    }
                ]
            },
        )
        item = _review_item_by_source(queue, "silent heir")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("suggested_action"), "review_enrich_existing_entity")
        metadata = item.get("metadata") or {}
        self.assertEqual(metadata.get("candidate_review_state"), "review")
        self.assertFalse(metadata.get("candidate_is_primary"))
        self.assertTrue(metadata.get("candidate_requires_review"))
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertTrue(metadata.get("do_not_auto_promote"))

    def test_antihardcode_static_guard(self):
        runtime_source = Path("textifai/vaerl/review_queue.py").read_text(encoding="utf-8")
        for term in [
            "el muchacho",
            "la princesa",
            "la heredera silenciosa",
            "Sera Valen",
            "Ren Tal",
        ]:
            self.assertNotIn(term, runtime_source)


def _queue_for_absorbed_surface(
    *,
    surface: str,
    canonical: str,
    source_mentions: list[str],
    key_facts: list[str],
    chapter_refs: list[str],
    confidence: float,
    category: str,
    surface_type: str = "descriptor_like",
    semantic_value: str = "descriptor",
    language_hint: str = "en",
    relationships: list[dict] | None = None,
) -> dict:
    return build_review_queue(
        obsidian_import={"entities": [_primary(canonical, aliases=[surface])]},
        retention_context={
            "global_entities": [
                {
                    "canonical_name": surface,
                    "canonical_candidate": canonical,
                    "entity_kind": "character",
                    "preferred_slug": surface.casefold().replace(" ", "_"),
                    "source_mentions": source_mentions,
                    "key_facts": key_facts,
                    "chapter_refs": chapter_refs,
                    "relationships": relationships or [],
                    "confidence": confidence,
                    "review_state": "review",
                    "naming_quality": "descriptor",
                    "surface_type": surface_type,
                    "language_hint": language_hint,
                    "semantic_value": semantic_value,
                    "descriptor_category": category,
                }
            ]
        },
    )


def _primary(canonical_name: str, *, aliases: list[str] | None = None) -> dict:
    aliases = aliases or []
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
