import unittest

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer, HybridRecognizerConfig
from textifai.conversation.contracts import PendingConversationOperation
from textifai.conversation.state import create_conversation_state


class TextifAIHybridRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.state = create_conversation_state(explanation_language="es", artifact_target_language="ja")

    def test_does_not_escalate_when_rules_are_clear(self):
        recognizer = HybridIntentRecognizer(llm_classifier=_FailingClassifier())
        request = ConversationRequest(
            raw_text="scene scene_054_b",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            artifact_target_language="ja",
            explanation_language="es",
        )
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.intent_name, "inspect_scene")
        self.assertEqual(intent.recognizer_kind, "rule_based")
        self.assertFalse(intent.metadata["escalated_to_llm"])

    def test_escalates_unknown_request_to_llm_and_keeps_catalog_controlled(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier(
                {
                    "intent_name": "inspect_scene",
                    "confidence": 0.87,
                    "target_type": "scene",
                    "target_id": "scene_054_b",
                    "classification_note": "The user asked to review a specific scene in Spanish.",
                    "signals": ["spanish_freeform"],
                    "narrative_signals": {
                        "mentioned_entities": ["Sera"],
                        "mentioned_character_ids": ["sera"],
                        "target_hint": "scene_054_b",
                        "target_inference_source": "conversation_state",
                        "issue_types": ["character_voice_mismatch"],
                        "constraint_hints": ["check_character_voice"],
                        "confidence": 0.82,
                    },
                }
            )
        )
        request = ConversationRequest(
            raw_text="quiero revisar esta escena",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            artifact_target_language="ja",
            explanation_language="es",
            metadata={
                "known_characters": [
                    {"id": "sera", "names": ["Sera"]},
                ]
            },
        )
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.intent_name, "inspect_scene")
        self.assertEqual(intent.recognizer_kind, "hybrid_llm")
        self.assertTrue(intent.metadata["catalog_validated"])
        self.assertEqual(intent.metadata["target_resolution_status"], "suggested")
        self.assertEqual(intent.metadata["language_context"]["user_command_language"], "es")
        self.assertEqual(intent.narrative_signals.issue_types, ["character_voice_mismatch"])
        self.assertEqual(intent.narrative_signals.constraint_hints, ["check_character_voice"])
        self.assertEqual(intent.narrative_signals.mentioned_character_ids, ["sera"])

    def test_invalid_llm_intent_is_normalized_to_unknown(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier(
                {
                    "intent_name": "invented_magic_intent",
                    "confidence": 0.91,
                    "classification_note": "The model guessed a made-up intent.",
                }
            )
        )
        request = ConversationRequest(
            raw_text="haz algo raro con esto",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.intent_name, "unknown")
        self.assertEqual(intent.recognizer_kind, "hybrid_llm")
        self.assertFalse(intent.metadata["catalog_validated"])
        self.assertEqual(intent.metadata["llm_raw_intent"], "invented_magic_intent")

    def test_visible_threshold_config_controls_escalation(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier({"intent_name": "unknown", "confidence": 0.7}),
            config=HybridRecognizerConfig(llm_escalation_threshold=0.96),
        )
        request = ConversationRequest(
            raw_text="find hidden door",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=False,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, self.state)
        self.assertTrue(intent.metadata["escalated_to_llm"])

    def test_ok_confirms_only_when_pending_operation_exists(self):
        state = self.state.__class__(
            **{
                **self.state.__dict__,
                "pending_operation": PendingConversationOperation(
                    operation_id="op-1",
                    operation_kind="validate_artifact",
                    task_type="artifact_persistence",
                    flow_name="validate_artifact_flow",
                    target_type="lore",
                    target_id="magic_limits",
                    artifact_target_language="ja",
                    explanation_language="es",
                    payload={"type": "artifact_state_change"},
                    summary="validate lore:magic_limits",
                    executable=True,
                ),
            }
        )
        recognizer = HybridIntentRecognizer(llm_classifier=_FailingClassifier())
        request = ConversationRequest(
            raw_text="ok",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, state)
        self.assertEqual(intent.intent_name, "confirm_pending")
        no_pending_intent = recognizer.recognize(request, self.state)
        self.assertEqual(no_pending_intent.intent_name, "unknown")

    def test_natural_cancel_maps_only_with_pending_operation(self):
        state = self.state.__class__(
            **{
                **self.state.__dict__,
                "pending_operation": PendingConversationOperation(
                    operation_id="op-2",
                    operation_kind="reject_artifact",
                    task_type="artifact_persistence",
                    flow_name="reject_artifact_flow",
                    target_type="lore",
                    target_id="ritual_notes",
                    artifact_target_language="ja",
                    explanation_language="es",
                    payload={"type": "artifact_state_change"},
                    summary="reject lore:ritual_notes",
                    executable=True,
                ),
            }
        )
        recognizer = HybridIntentRecognizer(llm_classifier=_FailingClassifier())
        request = ConversationRequest(
            raw_text="mejor no, cancélalo",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, state)
        self.assertEqual(intent.intent_name, "cancel_pending")

    def test_bootstrap_natural_request_is_marked_unsupported(self):
        recognizer = HybridIntentRecognizer(llm_classifier=_FailingClassifier())
        request = ConversationRequest(
            raw_text="haz bootstrap del canon de los capítulos 1 a 3",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.intent_name, "unknown")
        self.assertEqual(intent.metadata["unsupported_capability"], "bootstrap_extract")

    def test_natural_canon_decision_phrase_maps_to_persist_decision(self):
        recognizer = HybridIntentRecognizer(llm_classifier=_FailingClassifier())
        request = ConversationRequest(
            raw_text="guarda esto como decisión de canon",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            explanation_language="es",
        )
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.intent_name, "persist_decision")

    def test_escalates_mixed_editorial_nuance_requests_to_llm(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier(
                {
                    "intent_name": "editorial_structuring",
                    "confidence": 0.84,
                    "classification_note": "LLM refined a mixed editorial request.",
                }
            )
        )
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
        intent = recognizer.recognize(request, self.state)
        self.assertEqual(intent.recognizer_kind, "hybrid_llm")
        self.assertTrue(intent.metadata["escalated_to_llm"])
        self.assertEqual(intent.metadata["llm_raw_intent"], "editorial_structuring")


class _StubClassifier:
    def __init__(self, result):
        self.result = result

    def classify_intent(self, *, request, rule_intent, state):
        return dict(self.result)


class _FailingClassifier:
    def classify_intent(self, *, request, rule_intent, state):
        raise AssertionError("LLM classifier should not have been called")


if __name__ == "__main__":
    unittest.main()
