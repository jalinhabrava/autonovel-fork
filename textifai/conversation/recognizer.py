from __future__ import annotations

import re

from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
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
        narrative_signals = _extract_narrative_signals(request, state)
        if not lowered:
            return RecognizedIntent(
                intent_name="unknown",
                confidence=0.0,
                signals=["empty_input"],
                narrative_signals=narrative_signals,
                recognizer_kind="rule_based",
                metadata={
                    "next_recognizer": self.future_kind,
                    "classification_note": "No rule matched because the request was empty.",
                },
            )

        if lowered == "confirm":
            return self._intent("confirm_pending", confidence=0.99, signals=["confirm_control"])
        if lowered == "cancel":
            return self._intent("cancel_pending", confidence=0.99, signals=["cancel_control"])
        if _matches_pending_confirm(raw, state):
            return self._intent("confirm_pending", confidence=0.99, signals=["confirm_control"])
        if _matches_pending_cancel(raw, state):
            return self._intent("cancel_pending", confidence=0.99, signals=["cancel_control"])
        if lowered in {"ok", "vale", "sí", "si", "yes"}:
            return RecognizedIntent(
                intent_name="unknown",
                confidence=0.15,
                signals=["ack_without_pending"],
                narrative_signals=narrative_signals,
                recognizer_kind="rule_based",
                metadata={
                    "next_recognizer": self.future_kind,
                    "skip_llm_escalation": True,
                    "classification_note": "Short acknowledgement without a pending operation was kept conservative.",
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
            target_type, target_id = _parse_target_reference(raw.split(maxsplit=1)[1].strip())
            return self._intent(
                "consistency_check",
                confidence=0.9,
                target_type=target_type,
                target_id=target_id,
                requires_target=True,
                signals=["check_command"],
            )
        if lowered == "decide":
            return self._intent("persist_decision", confidence=0.9, persistent_hint=True, signals=["decide_command"])
        if lowered.startswith("decide "):
            target_type, target_id = _parse_target_reference(raw.split(maxsplit=1)[1].strip())
            return self._intent(
                "persist_decision",
                confidence=0.9,
                target_type=target_type,
                target_id=target_id,
                requires_target=bool(target_id),
                persistent_hint=True,
                signals=["decide_command"],
            )
        if lowered.startswith("validate "):
            target_type, target_id = _parse_target_reference(raw.split(maxsplit=1)[1].strip())
            return self._intent(
                "validate_artifact",
                confidence=0.9,
                target_type=target_type,
                target_id=target_id,
                requires_target=True,
                persistent_hint=True,
                signals=["validate_command"],
            )
        if lowered.startswith("reject "):
            target_type, target_id = _parse_target_reference(raw.split(maxsplit=1)[1].strip())
            return self._intent(
                "reject_artifact",
                confidence=0.9,
                target_type=target_type,
                target_id=target_id,
                requires_target=True,
                persistent_hint=True,
                signals=["reject_command"],
            )
        if lowered == "validate_structure":
            return self._intent("validate_structure", confidence=0.96, signals=["validation_command"])
        if lowered == "prepare_narration":
            return self._intent("prepare_narration", confidence=0.96, signals=["narration_handoff_command"])
        if lowered == "prepare_review":
            return self._intent("prepare_review", confidence=0.96, signals=["review_handoff_command"])
        if lowered == "structured_followup":
            return self._intent("structured_followup", confidence=0.9, signals=["structured_followup_command"])
        if lowered.startswith("bootstrap"):
            return self._intent("bootstrap_extract", confidence=0.9, persistent_hint=True, signals=["bootstrap_command"])
        if "bootstrap" in lowered:
            return RecognizedIntent(
                intent_name="unknown",
                confidence=0.35,
                signals=["unsupported_bootstrap_request"],
                narrative_signals=narrative_signals,
                recognizer_kind="rule_based",
                metadata={
                    "next_recognizer": self.future_kind,
                    "unsupported_capability": "bootstrap_extract",
                    "classification_note": "The request refers to bootstrap, which is not supported yet through natural conversation.",
                },
            )

        fallback_target = request.target_hint or (state.last_target_id if state else None)
        return RecognizedIntent(
            intent_name="unknown",
            confidence=0.2,
            target_id=fallback_target,
            signals=["no_rule_match"],
            narrative_signals=narrative_signals,
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
            narrative_signals=None,
            recognizer_kind="rule_based",
            metadata={
                "next_recognizer": self.future_kind,
                "classification_note": f"Recognized directly by rules as {intent_name}.",
            },
        )



def _parse_target_reference(raw: str) -> tuple[str | None, str | None]:
    if ":" not in raw or raw.endswith(".md"):
        return (None, raw or None)
    target_type, target_id = raw.split(":", 1)
    return (target_type.strip().lower() or None, target_id.strip() or None)


def _extract_narrative_signals(
    request: ConversationRequest,
    state: ConversationState | None,
) -> NarrativeSignals | None:
    raw = request.raw_text.strip()
    if not raw:
        return None

    known_characters = request.metadata.get("known_characters", [])
    matched_names, matched_ids = _match_known_characters(raw, known_characters)
    mentioned_entities = list(matched_names)
    target_hint, target_source = _infer_target_hint(request, state, raw.lower())
    if not mentioned_entities and request.metadata.get("entity_hint"):
        mentioned_entities.append(str(request.metadata["entity_hint"]))

    if not any((mentioned_entities, matched_ids, target_hint)):
        return None

    return NarrativeSignals(
        mentioned_entities=_dedupe_preserve(mentioned_entities),
        mentioned_character_ids=_dedupe_preserve(matched_ids),
        target_hint=target_hint,
        target_inference_source=target_source,
        issue_types=[],
        constraint_hints=[],
        confidence=_signal_confidence(matched_ids, [], target_hint),
    )


def _infer_target_hint(
    request: ConversationRequest,
    state: ConversationState | None,
    lowered: str,
) -> tuple[str | None, str | None]:
    if request.target_hint:
        return request.target_hint, "request_hint"
    return None, None


def _match_known_characters(raw: str, known_characters: list[dict]) -> tuple[list[str], list[str]]:
    lowered = raw.lower()
    matched_names: list[str] = []
    matched_ids: list[str] = []
    for entry in known_characters:
        character_id = str(entry.get("id") or "").strip()
        names = [str(name).strip() for name in entry.get("names", []) if str(name).strip()]
        for name in names:
            if len(name) < 3:
                continue
            if re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", lowered):
                matched_names.append(name)
                if character_id:
                    matched_ids.append(character_id)
                break
    return matched_names, matched_ids


def _signal_confidence(character_ids: list[str], issue_types: list[str], target_hint: str | None) -> float:
    confidence = 0.45
    if character_ids:
        confidence += 0.2
    if issue_types:
        confidence += 0.2
    if target_hint:
        confidence += 0.1
    return min(confidence, 0.95)


def _dedupe_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _matches_pending_confirm(raw: str, state: ConversationState | None) -> bool:
    if state is None or state.pending_operation is None:
        return False
    normalized = " ".join(raw.strip().lower().split())
    if not normalized or len(normalized.split()) > 2:
        return False
    return normalized in {
        "confirm",
        "sí",
        "si",
        "yes",
        "ok",
        "vale",
        "adelante",
        "confirma",
        "hazlo",
    }


def _matches_pending_cancel(raw: str, state: ConversationState | None) -> bool:
    if state is None or state.pending_operation is None:
        return False
    normalized = " ".join(raw.strip().lower().split())
    return normalized in {
        "cancel",
        "cancel it",
        "cancela",
        "cancelalo",
        "cancélalo",
        "mejor no",
        "mejor no, cancélalo",
        "mejor no, cancelalo",
        "no lo guardes",
        "olvídalo",
        "olvidalo",
    }
