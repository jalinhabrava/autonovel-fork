from __future__ import annotations

from textifai.conversation.contracts import ConversationRequest, RecognizedIntent
from textifai.conversation.state import ConversationState


class RuleBasedIntentRecognizer:
    kind = "rule_based"
    future_kind = "hybrid_llm"

    def recognize(
        self,
        request: ConversationRequest,
        state: ConversationState | None = None,
    ) -> RecognizedIntent:
        raw = request.raw_text.strip()
        lowered = raw.lower()
        if not lowered:
            return RecognizedIntent(
                intent_name="unknown",
                confidence=0.0,
                signals=["empty_input"],
                recognizer_kind="rule_based",
                metadata={
                    "next_recognizer": self.future_kind,
                    "classification_note": "No rule matched because the request was empty.",
                },
            )

        if lowered == "help":
            return self._intent("conversation_help", confidence=0.95, signals=["help_command"])
        if lowered == "world":
            return self._intent("lookup_world", confidence=0.95, signals=["world_command"])
        if lowered.startswith("find "):
            return self._intent("search_context", confidence=0.9, signals=["find_command"])
        if lowered.startswith("scene "):
            return self._intent(
                "inspect_scene",
                confidence=0.95,
                target_type="scene",
                target_id=raw.split(maxsplit=1)[1].strip(),
                requires_target=True,
                signals=["scene_command"],
            )
        if lowered.startswith("chapter "):
            return self._intent(
                "inspect_chapter",
                confidence=0.95,
                target_type="chapter",
                target_id=raw.split(maxsplit=1)[1].strip(),
                requires_target=True,
                signals=["chapter_command"],
            )
        if lowered.startswith("check "):
            return self._intent("consistency_check", confidence=0.9, requires_target=True, signals=["check_command"])
        if lowered == "decide" or lowered.startswith("decide "):
            return self._intent("persist_decision", confidence=0.9, persistent_hint=True, signals=["decide_command"])
        if lowered.startswith("validate "):
            return self._intent("validate_artifact", confidence=0.9, requires_target=True, persistent_hint=True, signals=["validate_command"])
        if lowered.startswith("reject "):
            return self._intent("reject_artifact", confidence=0.9, requires_target=True, persistent_hint=True, signals=["reject_command"])
        if lowered.startswith("bootstrap"):
            return self._intent("bootstrap_extract", confidence=0.9, persistent_hint=True, signals=["bootstrap_command"])

        fallback_target = request.target_hint or (state.last_target_id if state else None)
        return RecognizedIntent(
            intent_name="unknown",
            confidence=0.2,
            target_id=fallback_target,
            signals=["no_rule_match"],
            recognizer_kind="rule_based",
            metadata={
                "next_recognizer": self.future_kind,
                "classification_note": "Rules could not confidently classify the request.",
            },
        )

    def _intent(
        self,
        intent_name: str,
        *,
        confidence: float,
        target_type: str | None = None,
        target_id: str | None = None,
        requires_target: bool = False,
        ephemeral_hint: bool | None = None,
        persistent_hint: bool | None = None,
        signals: list[str] | None = None,
    ) -> RecognizedIntent:
        return RecognizedIntent(
            intent_name=intent_name,
            confidence=confidence,
            target_type=target_type,
            target_id=target_id,
            requires_target=requires_target,
            ephemeral_hint=ephemeral_hint,
            persistent_hint=persistent_hint,
            signals=signals or [],
            recognizer_kind="rule_based",
            metadata={
                "next_recognizer": self.future_kind,
                "classification_note": f"Recognized directly by rules as {intent_name}.",
            },
        )
