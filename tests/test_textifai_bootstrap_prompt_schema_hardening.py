from __future__ import annotations

import json
import unittest

from textifai.import_review.structured_bootstrap_v1 import (
    CHAPTER_EXTRACTION_PROMPT,
    GLOBAL_NORMALIZATION_PROMPT,
    _build_global_normalization_prompt,
    _normalize_chapter_payload,
)


class TextifAIBootstrapPromptSchemaHardeningTests(unittest.TestCase):
    def test_chapter_prompt_contains_objects_first_class_contract(self):
        self.assertIn('"objects"', CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("persistent_artifact|weapon|tool|ritual_key|catalyst|temporary_prop|unknown", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Persistent objects/artifacts must go in objects, not concepts.", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Do not suppress durable artifacts because they are not characters.", CHAPTER_EXTRACTION_PROMPT)

    def test_chapter_prompt_contains_empty_canonical_map_mode(self):
        self.assertIn("CANONICAL_MAP_MODE", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("If CANONICAL_ENTITY_MAP is empty or incomplete", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Never auto-merge.", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Never auto-promote.", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Do not discard important candidates merely because the canonical map is empty.", CHAPTER_EXTRACTION_PROMPT)

    def test_chapter_prompt_contains_relation_two_layer_contract(self):
        self.assertIn("relation_category", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("relation_label", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("unknown_association", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Use relation_label as a short free label", CHAPTER_EXTRACTION_PROMPT)
        self.assertNotIn("relation_type must be one of:", CHAPTER_EXTRACTION_PROMPT)

    def test_chapter_prompt_contains_event_importance_policy(self):
        self.assertIn("event_importance", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("major|supporting|local", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("Do not use a hard cap of 3 if the chapter is dense.", CHAPTER_EXTRACTION_PROMPT)

    def test_chapter_prompt_contains_concept_object_event_boundaries(self):
        self.assertIn("CONCEPT / OBJECT / EVENT BOUNDARIES", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("A persistent artifact belongs in objects.", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("A magic law belongs in concepts.", CHAPTER_EXTRACTION_PROMPT)
        self.assertIn("A kingdom collapse belongs in events.", CHAPTER_EXTRACTION_PROMPT)

    def test_global_prompt_contains_incremental_batch_wording(self):
        self.assertIn("incremental global normalization", GLOBAL_NORMALIZATION_PROMPT)
        prompt = _build_global_normalization_prompt(
            work_title="Test",
            language="ja",
            batch_index=1,
            batch=[{"sequence_index": 1, "title": "第1話", "text": "短い本文"}],
            novel_index={"work": {"title": "Test"}, "chapters": []},
            pass1_payload={},
            ambiguity_queue={},
        )
        self.assertIn("NOVEL_INDEX_METADATA for structure, ordering, and navigation only", prompt)
        self.assertIn("Do not assert facts from chapters outside BATCH_SCOPE.", prompt)
        self.assertIn("confirmed_global", prompt)
        self.assertIn("global_candidate", prompt)

    def test_normalizer_tolerates_v2_objects_and_relation_shape(self):
        normalized = _normalize_chapter_payload(
            {
                "chapter_extraction_schema_version": "v2",
                "work": {"title": "Test", "language": "ja"},
                "chapters": [
                    {
                        "chapter_id": "ch_001",
                        "chapter_title_original": "第1話",
                        "chapter_title_canonical": "第1話",
                        "sequence_index": 1,
                        "chapter_label_type": "episode",
                        "chapter_number_in_label": 1,
                        "title_parse_signals": {},
                        "chapter_summary": "要約。",
                        "characters": [],
                        "places": [],
                        "concepts": [],
                        "objects": [
                            {
                                "surface": "鐘",
                                "canonical": "鐘",
                                "canonical_candidate": "鐘",
                                "object_subkind": "ritual_key",
                                "naming_quality": "descriptor",
                                "needs_review": True,
                                "review_reason": "durable artifact candidate",
                                "facts": ["鳴ると場面が変わる。"],
                                "relationships": [],
                                "confidence": 0.8,
                                "retention_reason": "event_trigger",
                            }
                        ],
                        "events": [{"surface": "崩壊", "canonical": "崩壊", "facts": [], "event_importance": "major", "confidence": 0.9}],
                        "relations": [
                            {
                                "from_surface": "証人",
                                "from_canonical": "証人",
                                "from_canonical_candidate": "証人",
                                "to_surface": "鐘",
                                "to_canonical": "鐘",
                                "to_canonical_candidate": "鐘",
                                "relation_category": "object_link",
                                "relation_label": "keeps_artifact",
                                "relation_summary": "証人が鐘を持つ。",
                                "evidence": ["鐘を携える。"],
                                "facts": ["証人が鐘を持つ。"],
                                "confidence": 0.77,
                                "needs_review": True,
                                "review_reason": "keeper relation inferred",
                            }
                        ],
                        "unresolved_mentions": [],
                    }
                ],
            },
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="第1話",
            chapter_text="鐘が鳴る。",
            work_title="Test",
            language="ja",
        )
        chapter = normalized["chapters"][0]
        self.assertEqual(chapter["chapter_extraction_schema_version"], "v2")
        self.assertEqual(chapter["objects"][0]["object_subkind"], "ritual_key")
        self.assertEqual(chapter["objects"][0]["retention_reason"], "event_trigger")
        self.assertEqual(chapter["events"][0]["event_importance"], "major")
        self.assertEqual(chapter["relations"][0]["relation_category"], "object_link")
        self.assertEqual(chapter["relations"][0]["relation_label"], "keeps_artifact")

    def test_normalizer_tolerates_legacy_without_objects(self):
        normalized = _normalize_chapter_payload(
            {
                "work": {"title": "Test", "language": "ja"},
                "chapters": [
                    {
                        "chapter_id": "ch_001",
                        "chapter_title_original": "第1話",
                        "chapter_title_canonical": "第1話",
                        "sequence_index": 1,
                        "chapter_label_type": "episode",
                        "chapter_number_in_label": 1,
                        "title_parse_signals": {},
                        "chapter_summary": "要約。",
                        "characters": [],
                        "places": [],
                        "concepts": [],
                        "events": [],
                        "relations": [],
                        "unresolved_mentions": [],
                    }
                ],
            },
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="第1話",
            chapter_text="短い本文。",
            work_title="Test",
            language="ja",
        )
        chapter = normalized["chapters"][0]
        self.assertEqual(chapter["chapter_extraction_schema_version"], "v1")
        self.assertEqual(chapter["objects"], [])


if __name__ == "__main__":
    unittest.main()
