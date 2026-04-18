import tempfile
import unittest
from pathlib import Path

from textifai.author_understanding.contracts import LLMInterpretationResult, MixedRequestPart
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer, HybridAuthorUnderstandingConfig
from textifai.author_understanding.llm_interpreter import AuthorUnderstandingLLMInterpreter
from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.manager import ConversationManager
from textifai.conversation.state import create_conversation_state
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class TextifAIAuthorUnderstandingHybridAnalysisTests(unittest.TestCase):
    def test_rule_based_analysis_keeps_simple_followup_contextual(self):
        analyzer = HybridAuthorUnderstandingAnalyzer(config=HybridAuthorUnderstandingConfig(llm_enabled=False))
        request = ConversationRequest(
            raw_text="esta nota",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_rule_intent("unknown", confidence=0.25),
            narrative_signals=None,
            entity_results=[],
            state=state,
        )
        self.assertEqual(interpretation.primary_intent_type, "contextual_followup")
        self.assertEqual(interpretation.source, "rule_based")
        self.assertEqual(interpretation.followup_reference_text, "esta nota")
        self.assertFalse(interpretation.has_mixed_request)

    def test_llm_assisted_analysis_separates_revision_and_preservation(self):
        llm = _StubLLMInterpreter(
            LLMInterpretationResult(
                raw_text="quiero que aquí Sera suene más contenida, pero sin perder la tensión con Ren",
                provider_name="stub",
                model="stub-model",
                primary_intent_type="editorial_revision",
                secondary_intent_types=[],
                confidence=0.91,
                has_mixed_request=False,
                author_goal_signals=["align_tone"],
                preserve_signals=["preserve_scene_conflict"],
                change_signals=["align_tone"],
                followup_reference_text=None,
                narrative_content_text=None,
                meta_instruction_text="quiero que aquí Sera suene más contenida, pero sin perder la tensión con Ren",
                needs_clarification=False,
                clarification_reason=None,
                parts=[
                    MixedRequestPart(part_type="revision", text="quiero que aquí Sera suene más contenida", confidence=0.92),
                    MixedRequestPart(part_type="preserve", text="sin perder la tensión con Ren", confidence=0.9),
                ],
                candidate_targets=[],
                preferred_target=None,
                disambiguation_reason=None,
                raw_payload={"primary_intent_type": "editorial_revision"},
            )
        )
        analyzer = HybridAuthorUnderstandingAnalyzer(llm_interpreter=llm, config=HybridAuthorUnderstandingConfig())
        request = ConversationRequest(
            raw_text="quiero que aquí Sera suene más contenida, pero sin perder la tensión con Ren",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_rule_intent("editorial_structuring", confidence=0.72),
            narrative_signals=None,
            entity_results=[],
            state=create_conversation_state(explanation_language="es", artifact_target_language="ja"),
        )
        self.assertEqual(interpretation.source, "hybrid")
        self.assertEqual(interpretation.primary_intent_type, "editorial_revision")
        self.assertIn("align_tone", interpretation.change_signals)
        self.assertIn("preserve_scene_conflict", interpretation.preserve_signals)
        self.assertFalse(interpretation.needs_clarification)

    def test_llm_assisted_analysis_identifies_mixed_structuring_and_narration_prep(self):
        llm = _StubLLMInterpreter(
            LLMInterpretationResult(
                raw_text="Sera llega tarde al puerto, ordénalo y luego déjamelo preparado para narrar",
                provider_name="stub",
                model="stub-model",
                primary_intent_type="mixed_request",
                secondary_intent_types=["narration_preparation"],
                confidence=0.9,
                has_mixed_request=True,
                author_goal_signals=["structure_scene", "prepare_for_narration"],
                preserve_signals=[],
                change_signals=["structure_scene", "prepare_for_narration"],
                followup_reference_text=None,
                narrative_content_text="Sera llega tarde al puerto",
                meta_instruction_text="ordénalo y luego déjamelo preparado para narrar",
                needs_clarification=False,
                clarification_reason=None,
                parts=[
                    MixedRequestPart(part_type="narrative_content", text="Sera llega tarde al puerto", confidence=0.92),
                    MixedRequestPart(part_type="meta_instruction", text="ordénalo", confidence=0.85),
                    MixedRequestPart(part_type="narration_prep", text="déjamelo preparado para narrar", confidence=0.84),
                ],
                candidate_targets=[],
                preferred_target=None,
                disambiguation_reason=None,
                raw_payload={"primary_intent_type": "mixed_request"},
            )
        )
        analyzer = HybridAuthorUnderstandingAnalyzer(llm_interpreter=llm)
        request = ConversationRequest(
            raw_text="Sera llega tarde al puerto, ordénalo y luego déjamelo preparado para narrar",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_rule_intent("editorial_structuring", confidence=0.71),
            narrative_signals=None,
            entity_results=[],
            state=create_conversation_state(explanation_language="es", artifact_target_language="ja"),
        )
        self.assertEqual(interpretation.source, "hybrid")
        self.assertTrue(interpretation.has_mixed_request)
        self.assertEqual(interpretation.narrative_content_text, "Sera llega tarde al puerto")
        self.assertIn("prepare_for_narration", interpretation.change_signals)

    def test_rule_based_analysis_is_domain_agnostic_for_nonfantasy_scene(self):
        analyzer = HybridAuthorUnderstandingAnalyzer(config=HybridAuthorUnderstandingConfig(llm_enabled=False))
        request = ConversationRequest(
            raw_text="Ana llega tarde a la reunión, Marcos cubre el brief y no pueden improvisar",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="es",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=_rule_intent("editorial_structuring", confidence=0.73),
            narrative_signals=None,
            entity_results=[],
            state=create_conversation_state(explanation_language="es", artifact_target_language="es"),
        )
        self.assertEqual(interpretation.source, "rule_based")
        self.assertEqual(interpretation.primary_intent_type, "narrative_facts")
        self.assertIsNotNone(interpretation.narrative_content_text)

    def test_manager_uses_author_understanding_to_build_narration_prep_from_mixed_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                body="Courier.",
                status="validated",
            )
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="toma",
                title="Toma",
                body="Gatekeeper.",
                status="validated",
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(
                session=session,
                executor=MinimalExecutionLayer(session=session),
                author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
                    llm_interpreter=_StubLLMInterpreter(
                        LLMInterpretationResult(
                            raw_text="Sera llega tarde al puerto, ordénalo y luego déjamelo preparado para narrar",
                            provider_name="stub",
                            model="stub-model",
                            primary_intent_type="mixed_request",
                            secondary_intent_types=["narration_preparation"],
                            confidence=0.92,
                            has_mixed_request=True,
                            author_goal_signals=["structure_scene", "prepare_for_narration"],
                            preserve_signals=[],
                            change_signals=["structure_scene", "prepare_for_narration"],
                            followup_reference_text=None,
                            narrative_content_text="Sera llega tarde al puerto, Toma la acusa de mentir y ella revela que perdió el mapa",
                            meta_instruction_text="ordénalo y luego déjamelo preparado para narrar",
                            needs_clarification=False,
                            clarification_reason=None,
                            parts=[
                                MixedRequestPart(part_type="narrative_content", text="Sera llega tarde al puerto, Toma la acusa de mentir y ella revela que perdió el mapa", confidence=0.95),
                                MixedRequestPart(part_type="meta_instruction", text="ordénalo", confidence=0.9),
                                MixedRequestPart(part_type="narration_prep", text="déjamelo preparado para narrar", confidence=0.91),
                            ],
                            candidate_targets=[],
                            preferred_target=None,
                            disambiguation_reason=None,
                            raw_payload={"primary_intent_type": "mixed_request"},
                        )
                    )
                ),
            )
            turn = manager.handle_request(
                ConversationRequest(
                    raw_text="Sera llega tarde al puerto, ordénalo y luego déjamelo preparado para narrar",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                    metadata={
                        "known_characters": [
                            {"id": "sera", "names": ["Sera"]},
                            {"id": "toma", "names": ["Toma"]},
                        ]
                    },
                )
            )
            self.assertEqual(turn.result_type, "editorial_structuring")
            remembered = session.last_result["data"]
            self.assertIsNotNone(remembered["narration_prep"])
            self.assertGreaterEqual(len(remembered["story_facts"]["explicit_facts"]), 1)
            self.assertEqual(remembered["narration_prep"]["source_kind"], "beat_outline")


class _StubLLMInterpreter:
    def __init__(self, result):
        self.result = result

    def interpret(self, **kwargs):
        return self.result


def _rule_intent(intent_name: str, confidence: float):
    from textifai.conversation.contracts import RecognizedIntent

    return RecognizedIntent(intent_name=intent_name, confidence=confidence)


if __name__ == "__main__":
    unittest.main()
