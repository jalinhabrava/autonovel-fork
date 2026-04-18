import unittest

from textifai.editorial.contracts import (
    BeatItem,
    EditorialStructuringResult,
    NarrationPrep,
    RevisionIntent,
    StoryFactItem,
    StoryFacts,
)
from textifai.vaerl.contracts import EntityCandidate, EntityMention, EntityResolutionResult, RelatedArtifactSuggestion


class TextifAIEditorialContractsTests(unittest.TestCase):
    def test_entity_resolution_distinguishes_candidates_and_related_artifacts(self):
        result = EntityResolutionResult(
            query_text="Sera no diría eso",
            mention=EntityMention(
                surface_text="Sera",
                normalized_text="sera",
                mention_kind_hint="character",
                source="raw_text",
                confidence=0.95,
            ),
            resolved=True,
            resolution_confidence=0.95,
            resolution_source="known_characters",
            resolved_entity_id="sera",
            resolved_entity_type="character",
            candidate_entities=[
                EntityCandidate(
                    artifact_id="sera",
                    artifact_type="character",
                    path="/tmp/sera.md",
                    match_source="known_name",
                    match_reason="known character name match",
                    confidence=0.95,
                )
            ],
            related_artifacts_suggested=[
                RelatedArtifactSuggestion(
                    artifact_id="sera",
                    artifact_type="character",
                    relation="direct_profile",
                    confidence=0.99,
                )
            ],
        )
        self.assertEqual(result.candidate_entities[0].match_source, "known_name")
        self.assertEqual(result.related_artifacts_suggested[0].relation, "direct_profile")

    def test_story_facts_keep_explicit_and_inferred_facts_separate(self):
        facts = StoryFacts(
            source_text="Sera llega tarde.",
            language="es",
            explicit_facts=[StoryFactItem(text="Sera llega tarde", fact_kind="event", source="explicit_input")],
            inferred_facts=[StoryFactItem(text="There is time pressure.", fact_kind="constraint", source="system_inference")],
            goals=["Sera wants to reach the port on time."],
        )
        self.assertEqual(facts.explicit_facts[0].source, "explicit_input")
        self.assertEqual(facts.inferred_facts[0].source, "system_inference")

    def test_beat_item_uses_controlled_tension_level(self):
        beat = BeatItem(index=1, summary="Sera arrives late.", purpose="advance_scene", characters=["sera"], tension_level="rising")
        self.assertEqual(beat.tension_level, "rising")
        with self.assertRaises(ValueError):
            BeatItem(index=1, summary="bad", purpose="advance_scene", tension_level="wild")

    def test_editorial_structuring_result_can_hold_narration_prep(self):
        result = EditorialStructuringResult(
            result_kind="narration_prep",
            ready_for_validation=True,
            narration_prep=NarrationPrep(
                source_kind="story_facts",
                target_language="ja",
                explanation_language="es",
            ),
            revision_intent=RevisionIntent(source_text="revise this"),
        )
        self.assertEqual(result.result_kind, "narration_prep")
        self.assertEqual(result.narration_prep.target_language, "ja")


if __name__ == "__main__":
    unittest.main()
