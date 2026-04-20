import unittest

from textifai.author_understanding.contracts import (
    AuthorIntentInterpretation,
    DisambiguationResult,
    LLMAuthorUnderstandingPayload,
    LLMInterpretationResult,
    MixedRequestAnalysis,
    MixedRequestPart,
)
from textifai.author_understanding.normalization import normalize_candidate_target
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityHint


class TextifAIAuthorUnderstandingContractTests(unittest.TestCase):
    def test_author_intent_interpretation_enforces_closed_catalogs(self):
        interpretation = AuthorIntentInterpretation(
            primary_intent_type="mixed_request",
            secondary_intent_types=["narration_preparation"],
            confidence=0.8,
            has_mixed_request=True,
            author_goal_signals=["structure_scene", "prepare_for_narration"],
            preserve_signals=["preserve_scene_conflict"],
            change_signals=["structure_scene"],
            entity_hints=[
                EntityHint(
                    hint_text="Memory Ritual",
                    normalized_hint="memory_ritual",
                    hint_kind="semantic_target",
                    hint_source="author_understanding",
                    confidence=0.9,
                    supported_by_author_understanding=True,
                    candidate_target_id="memory_ritual",
                    candidate_target_type="lore",
                )
            ],
            followup_reference_text="de lo anterior",
            narrative_content_text="Sera llega tarde al puerto.",
            meta_instruction_text="ordena la escena",
            needs_clarification=False,
            clarification_reason=None,
            mixed_request_analysis=MixedRequestAnalysis(
                source_text="Sera llega tarde al puerto, ordénalo y luego déjamelo preparado para narrar",
                parts=[
                    MixedRequestPart(part_type="narrative_content", text="Sera llega tarde al puerto.", confidence=0.9),
                    MixedRequestPart(part_type="meta_instruction", text="ordénalo", confidence=0.8),
                ],
            ),
            disambiguation=DisambiguationResult(
                candidate_targets=[],
                preferred_target=None,
                confidence=0.0,
                reason="",
                requires_user_confirmation=False,
            ),
            source="hybrid",
        )
        self.assertEqual(interpretation.primary_intent_type, "mixed_request")
        self.assertTrue(interpretation.entity_hints)
        with self.assertRaises(ValueError):
            AuthorIntentInterpretation(
                primary_intent_type="invented_intent",
                secondary_intent_types=[],
            )

    def test_llm_interpretation_result_enforces_catalogs(self):
        result = LLMInterpretationResult(
            raw_text="quiero que aquí Sera suene más contenida",
            provider_name="stub",
            model="stub-model",
            primary_intent_type="editorial_revision",
            secondary_intent_types=["structuring_request"],
            confidence=0.88,
            has_mixed_request=False,
            author_goal_signals=["align_tone"],
            preserve_signals=["preserve_scene_conflict"],
            change_signals=["align_tone"],
            followup_reference_text=None,
            narrative_content_text=None,
            meta_instruction_text="quiero que",
            needs_clarification=False,
            clarification_reason=None,
            parts=[MixedRequestPart(part_type="revision", text="quiero que aquí Sera suene más contenida", confidence=0.9)],
            candidate_targets=[CandidateTarget(target_id="sera", target_type="character", confidence=0.9)],
            preferred_target=CandidateTarget(target_id="sera", target_type="character", confidence=0.9),
            disambiguation_reason="clear character anchor",
            raw_payload={"primary_intent_type": "editorial_revision"},
        )
        self.assertEqual(result.primary_intent_type, "editorial_revision")
        self.assertIs(LLMInterpretationResult, LLMAuthorUnderstandingPayload)
        with self.assertRaises(ValueError):
            LLMInterpretationResult(
                raw_text="x",
                provider_name=None,
                model=None,
                primary_intent_type="not_allowed",
            )

    def test_mixed_request_part_enforces_closed_catalog(self):
        part = MixedRequestPart(part_type="narrative_content", text="Sera llega tarde al puerto.", confidence=0.8)
        self.assertEqual(part.part_type, "narrative_content")
        with self.assertRaises(ValueError):
            MixedRequestPart(part_type="invented_part", text="x", confidence=0.5)

    def test_candidate_target_normalization_coerces_character_voice_to_character(self):
        target = normalize_candidate_target(
            {
                "target_id": "Sera",
                "target_type": "character_voice",
                "confidence": 0.56,
            }
        )
        self.assertIsNotNone(target)
        self.assertEqual(target.target_type, "character")


if __name__ == "__main__":
    unittest.main()
