import unittest

from textifai.author_understanding.contracts import LLMAuthorUnderstandingPayload, MixedRequestPart
from textifai.author_understanding.gating import classify_author_understanding_route
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer, HybridAuthorUnderstandingConfig
from textifai.author_understanding.prompt_builder import build_author_understanding_prompt
from textifai.conversation.contracts import ConversationRequest, RecognizedIntent
from textifai.conversation.state import create_conversation_state
from textifai.vaerl.contracts import EntityCandidate, EntityMention, EntityResolutionResult


class TextifAIAuthorUnderstandingGatingTests(unittest.TestCase):
    def test_expert_bypass_skips_llm_for_closed_command(self):
        called = {"value": False}
        analyzer = HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_StubLLM(called),
            config=HybridAuthorUnderstandingConfig(),
        )
        request = _request("validate this structure", interface_language="en", command_language="en")
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_recognized("validate_structure", confidence=0.96),
            narrative_signals=None,
            entity_results=[],
            state=create_conversation_state(explanation_language="en", artifact_target_language="en"),
        )
        self.assertFalse(called["value"])
        self.assertEqual(interpretation.source, "rule_based")
        self.assertEqual(interpretation.metadata["author_understanding_route"], "expert_bypass")

    def test_trivial_contextual_case_skips_llm_for_short_recent_followup(self):
        called = {"value": False}
        analyzer = HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_StubLLM(called),
            config=HybridAuthorUnderstandingConfig(),
        )
        state = create_conversation_state(explanation_language="es", artifact_target_language="es")
        state = state.__class__(
            **{
                **state.__dict__,
                "last_target_type": "lore",
                "last_target_id": "magic_limits",
            }
        )
        request = _request("esta nota", interface_language="es", command_language="es")
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_recognized("unknown", confidence=0.24),
            narrative_signals=None,
            entity_results=[],
            state=state,
        )
        self.assertFalse(called["value"])
        self.assertEqual(interpretation.primary_intent_type, "contextual_followup")
        self.assertEqual(interpretation.followup_reference_text, "esta nota")
        self.assertEqual(interpretation.metadata["author_understanding_route"], "trivial_contextual_case")

    def test_freeform_author_request_uses_llm_for_narration_prep_without_trigger_words(self):
        payload = LLMAuthorUnderstandingPayload(
            raw_text="I want this prepared for later narration, but do not finalize it yet.",
            provider_name="stub",
            model="stub-model",
            primary_intent_type="narration_preparation",
            secondary_intent_types=[],
            confidence=0.9,
            has_mixed_request=False,
            author_goal_signals=["prepare_for_narration"],
            preserve_signals=[],
            change_signals=["prepare_for_narration"],
            followup_reference_text=None,
            narrative_content_text=None,
            meta_instruction_text="I want this prepared for later narration, but do not finalize it yet.",
            needs_clarification=False,
            clarification_reason=None,
            parts=[
                MixedRequestPart(
                    part_type="narration_prep",
                    text="I want this prepared for later narration, but do not finalize it yet.",
                    confidence=0.91,
                )
            ],
            candidate_targets=[],
            preferred_target=None,
            disambiguation_reason=None,
            raw_payload={"primary_intent_type": "narration_preparation"},
        )
        called = {"value": False}
        analyzer = HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_StubLLM(called, payload),
            config=HybridAuthorUnderstandingConfig(),
        )
        request = _request(
            "I want this prepared for later narration, but do not finalize it yet.",
            interface_language="en",
            command_language="en",
            project_language="en",
        )
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_recognized("unknown", confidence=0.31),
            narrative_signals=None,
            entity_results=[],
            state=create_conversation_state(explanation_language="en", artifact_target_language="en"),
        )
        self.assertTrue(called["value"])
        self.assertEqual(interpretation.source, "hybrid")
        self.assertEqual(interpretation.primary_intent_type, "narration_preparation")
        self.assertEqual(interpretation.metadata["author_understanding_route"], "freeform_author_request")

    def test_same_freeform_intent_in_spanish_and_english_routes_to_llm_path(self):
        route_es = classify_author_understanding_route(
            request=_request("prepáralo para escribir", interface_language="es", command_language="es"),
            rule_intent=_recognized("unknown", confidence=0.28),
            state=create_conversation_state(explanation_language="es", artifact_target_language="es"),
        )
        route_en = classify_author_understanding_route(
            request=_request("prepare it for writing", interface_language="en", command_language="en"),
            rule_intent=_recognized("unknown", confidence=0.28),
            state=create_conversation_state(explanation_language="en", artifact_target_language="en"),
        )
        self.assertEqual(route_es.route_type, "freeform_author_request")
        self.assertEqual(route_en.route_type, "freeform_author_request")

    def test_prompt_builder_includes_context_and_schema(self):
        state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        state = state.__class__(
            **{
                **state.__dict__,
                "last_target_type": "scene",
                "last_target_id": "scene_054_b",
                "last_result_summary": "Prepared editorial structure: narration prep",
            }
        )
        prompt = build_author_understanding_prompt(
            request=_request("prepáralo para escribir", interface_language="es", command_language="es"),
            rule_intent=_recognized("unknown", confidence=0.2),
            narrative_signals=None,
            entity_results=[
                EntityResolutionResult(
                    query_text="prepáralo para escribir",
                    mention=EntityMention(surface_text="scene_054_b", normalized_text="scene_054_b"),
                    resolved=True,
                    resolved_entity_type="scene",
                    resolved_entity_id="scene_054_b",
                    resolution_confidence=0.94,
                    candidate_entities=[
                        EntityCandidate(
                            artifact_id="scene_054_b",
                            artifact_type="scene",
                            confidence=0.94,
                        )
                    ],
                    metadata={},
                )
            ],
            state=state,
        )
        self.assertIn("request_text", prompt.user_payload)
        self.assertIn("rule_based_intent", prompt.user_payload)
        self.assertIn("vaerl_candidate_hints", prompt.user_payload)
        self.assertIn("primary_intent_type", prompt.required_output_schema)
        self.assertIn("narrative_content_text", prompt.required_output_schema)
        self.assertEqual(prompt.user_payload["conversation_state"]["last_target_id"], "scene_054_b")
        self.assertEqual(prompt.user_payload["vaerl_candidate_hints"][0]["target_id"], "scene_054_b")


class _StubLLM:
    def __init__(self, called: dict[str, bool], payload: LLMAuthorUnderstandingPayload | None = None) -> None:
        self.called = called
        self.payload = payload

    def interpret(self, **kwargs):  # type: ignore[no-untyped-def]
        self.called["value"] = True
        return self.payload


def _request(raw_text: str, *, interface_language: str, command_language: str, project_language: str | None = None):
    return ConversationRequest(
        raw_text=raw_text,
        source="user",
        mode="normal",
        interface_language=interface_language,
        user_command_language=command_language,
        internal_system_language="en",
        project_default_language=project_language or interface_language,
        mixed_language_allowed=True,
        explanation_language=interface_language,
    )


def _recognized(intent_name: str, *, confidence: float) -> RecognizedIntent:
    return RecognizedIntent(intent_name=intent_name, confidence=confidence)


if __name__ == "__main__":
    unittest.main()
