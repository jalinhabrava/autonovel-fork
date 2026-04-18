from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from textifai.conversation.contracts import (
    CONSTRAINT_HINT_CATALOG,
    ConversationRequest,
    INTENT_CATALOG,
    ISSUE_TYPE_CATALOG,
    NarrativeSignals,
    RecognizedIntent,
)
from textifai.conversation.recognizer import RuleBasedIntentRecognizer
from textifai.conversation.state import ConversationState


DEFAULT_LLM_ESCALATION_THRESHOLD = 0.6


class IntentLLMClassifier(Protocol):
    def classify_intent(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        state: ConversationState | None,
    ) -> dict | None: ...


@dataclass(frozen=True)
class HybridRecognizerConfig:
    llm_escalation_threshold: float = DEFAULT_LLM_ESCALATION_THRESHOLD


class HybridIntentRecognizer:
    kind = "hybrid_llm"

    def __init__(
        self,
        *,
        rule_recognizer: RuleBasedIntentRecognizer | None = None,
        llm_classifier: IntentLLMClassifier | None = None,
        config: HybridRecognizerConfig | None = None,
    ) -> None:
        self.rule_recognizer = rule_recognizer or RuleBasedIntentRecognizer()
        self.llm_classifier = llm_classifier
        self.config = config or HybridRecognizerConfig()

    def recognize(
        self,
        request: ConversationRequest,
        state: ConversationState | None = None,
    ) -> RecognizedIntent:
        rule_intent = self.rule_recognizer.recognize(request, state)
        if not self._should_escalate(request, rule_intent):
            return self._with_rule_metadata(rule_intent)

        if self.llm_classifier is None:
            return self._fallback_without_llm(rule_intent)

        llm_result = self.llm_classifier.classify_intent(
            request=request,
            rule_intent=rule_intent,
            state=state,
        )
        return self._normalize_llm_result(request, rule_intent, llm_result)

    def _should_escalate(self, request: ConversationRequest, rule_intent: RecognizedIntent) -> bool:
        if rule_intent.metadata.get("unsupported_capability"):
            return False
        if rule_intent.metadata.get("skip_llm_escalation"):
            return False
        if _is_direct_command_result(rule_intent) and rule_intent.confidence >= self.config.llm_escalation_threshold:
            return False
        if rule_intent.intent_name == "unknown":
            return True
        if rule_intent.confidence < self.config.llm_escalation_threshold:
            return True
        if self._looks_less_structured(request):
            return True
        return False

    def _looks_less_structured(self, request: ConversationRequest) -> bool:
        lowered = request.raw_text.strip().lower()
        if not lowered:
            return False
        known_prefixes = (
            "confirm",
            "cancel",
            "help",
            "world",
            "find ",
            "scene ",
            "chapter ",
            "check ",
            "decide",
            "validate ",
            "reject ",
            "bootstrap",
        )
        if lowered.startswith(known_prefixes):
            return False
        if request.user_command_language != request.interface_language:
            return True
        if request.mixed_language_allowed and request.artifact_target_language:
            return True
        return len(lowered.split()) >= 4

    def _with_rule_metadata(self, intent: RecognizedIntent) -> RecognizedIntent:
        metadata = dict(intent.metadata)
        metadata.update(
            {
                "recognition_source": "rule_based",
                "escalated_to_llm": False,
                "rule_based_candidate": intent.intent_name,
                "rule_based_confidence": intent.confidence,
                "llm_used": False,
                "llm_reason": None,
                "llm_raw_intent": None,
                "catalog_validated": True,
                "classification_note": metadata.get("classification_note") or f"Rule-based recognizer selected {intent.intent_name}.",
            }
        )
        return RecognizedIntent(
            intent_name=intent.intent_name,
            confidence=intent.confidence,
            target_type=intent.target_type,
            target_id=intent.target_id,
            requires_target=intent.requires_target,
            ephemeral_hint=intent.ephemeral_hint,
            persistent_hint=intent.persistent_hint,
            signals=list(intent.signals),
            narrative_signals=intent.narrative_signals,
            recognizer_kind="rule_based",
            metadata=metadata,
        )

    def _fallback_without_llm(self, rule_intent: RecognizedIntent) -> RecognizedIntent:
        metadata = dict(rule_intent.metadata)
        metadata.update(
            {
                "recognition_source": "rule_based",
                "escalated_to_llm": True,
                "rule_based_candidate": rule_intent.intent_name,
                "rule_based_confidence": rule_intent.confidence,
                "llm_used": False,
                "llm_reason": "llm_classifier_unavailable",
                "llm_raw_intent": None,
                "catalog_validated": rule_intent.intent_name in INTENT_CATALOG,
                "classification_note": "Escalation was requested but no LLM classifier was configured, so the rule-based result was kept.",
            }
        )
        return RecognizedIntent(
            intent_name=rule_intent.intent_name,
            confidence=rule_intent.confidence,
            target_type=rule_intent.target_type,
            target_id=rule_intent.target_id,
            requires_target=rule_intent.requires_target,
            ephemeral_hint=rule_intent.ephemeral_hint,
            persistent_hint=rule_intent.persistent_hint,
            signals=list(rule_intent.signals),
            narrative_signals=rule_intent.narrative_signals,
            recognizer_kind="rule_based",
            metadata=metadata,
        )

    def _normalize_llm_result(
        self,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        llm_result: dict | None,
    ) -> RecognizedIntent:
        result = llm_result or {}
        proposed_intent = str(result.get("intent_name") or "unknown")
        catalog_validated = proposed_intent in INTENT_CATALOG
        final_intent = proposed_intent if catalog_validated else "unknown"
        confidence = _coerce_confidence(result.get("confidence"), default=max(rule_intent.confidence, 0.51))
        target_type = result.get("target_type") or rule_intent.target_type
        target_id = result.get("target_id") or rule_intent.target_id or request.target_hint
        signals = list(dict.fromkeys(list(rule_intent.signals) + _coerce_signals(result.get("signals")) + ["llm_classification"]))
        narrative_signals = _normalize_narrative_signals(
            result.get("narrative_signals"),
            rule_intent.narrative_signals,
            request=request,
        )

        metadata = {
            "recognition_source": "hybrid_llm",
            "escalated_to_llm": True,
            "rule_based_candidate": rule_intent.intent_name,
            "rule_based_confidence": rule_intent.confidence,
            "llm_used": True,
            "llm_reason": result.get("reason") or result.get("classification_note") or "llm_disambiguation",
            "llm_raw_intent": proposed_intent,
            "catalog_validated": catalog_validated,
            "classification_note": result.get("classification_note")
            or result.get("reason")
            or f"LLM classified the request as {final_intent}.",
            "target_suggested": bool(result.get("target_type") or result.get("target_id")),
            "target_resolution_status": "suggested" if (result.get("target_type") or result.get("target_id")) else "unresolved",
            "language_context": {
                "user_command_language": request.user_command_language,
                "interface_language": request.interface_language,
                "artifact_target_language": request.artifact_target_language,
                "mixed_language_allowed": request.mixed_language_allowed,
            },
        }
        return RecognizedIntent(
            intent_name=final_intent,
            confidence=confidence,
            target_type=target_type,
            target_id=target_id,
            requires_target=bool(result.get("requires_target", rule_intent.requires_target)),
            ephemeral_hint=result.get("ephemeral_hint", rule_intent.ephemeral_hint),
            persistent_hint=result.get("persistent_hint", rule_intent.persistent_hint),
            signals=signals,
            narrative_signals=narrative_signals,
            recognizer_kind="hybrid_llm",
            metadata=metadata,
        )


def _coerce_confidence(value, *, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))


def _coerce_signals(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _is_direct_command_result(intent: RecognizedIntent) -> bool:
    return any(signal.endswith("_command") or signal.endswith("_control") for signal in intent.signals)


def _normalize_narrative_signals(
    value,
    existing: NarrativeSignals | None,
    *,
    request: ConversationRequest,
) -> NarrativeSignals | None:
    if not isinstance(value, dict):
        return existing

    known_character_ids = {
        str(entry.get("id"))
        for entry in request.metadata.get("known_characters", [])
        if str(entry.get("id") or "").strip()
    }
    issue_types = [
        str(item)
        for item in value.get("issue_types", [])
        if str(item) in ISSUE_TYPE_CATALOG
    ]
    constraint_hints = [
        str(item)
        for item in value.get("constraint_hints", [])
        if str(item) in CONSTRAINT_HINT_CATALOG
    ]
    mentioned_entities = [str(item) for item in value.get("mentioned_entities", []) if str(item)]
    mentioned_character_ids = [
        str(item)
        for item in value.get("mentioned_character_ids", [])
        if str(item) and str(item) in known_character_ids
    ]
    target_hint = value.get("target_hint") or (existing.target_hint if existing else request.target_hint)
    target_inference_source = value.get("target_inference_source") or (existing.target_inference_source if existing else None)
    confidence = _coerce_confidence(value.get("confidence"), default=existing.confidence if existing else 0.55)

    return NarrativeSignals(
        mentioned_entities=list(dict.fromkeys((existing.mentioned_entities if existing else []) + mentioned_entities)),
        mentioned_character_ids=list(dict.fromkeys((existing.mentioned_character_ids if existing else []) + mentioned_character_ids)),
        target_hint=target_hint,
        target_inference_source=target_inference_source,
        issue_types=list(dict.fromkeys((existing.issue_types if existing else []) + issue_types)),
        constraint_hints=list(dict.fromkeys((existing.constraint_hints if existing else []) + constraint_hints)),
        confidence=confidence,
    )
