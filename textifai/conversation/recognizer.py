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
        if lowered == "decide" or lowered.startswith("decide "):
            return self._intent("persist_decision", confidence=0.9, persistent_hint=True, signals=["decide_command"])
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
        if lowered in {
            "valido esta estructura",
            "valida esta estructura",
            "validate this structure",
            "valida la estructura",
        }:
            return self._intent(
                "validate_structure",
                confidence=0.96,
                signals=["validation_command"],
            )
        if lowered in {
            "déjalo listo para narrar",
            "dejalo listo para narrar",
            "prepáralo para narrar",
            "preparalo para narrar",
            "lista para narrar",
        }:
            return self._intent(
                "prepare_narration",
                confidence=0.95,
                signals=["narration_handoff_command"],
            )
        if lowered in {
            "déjalo listo para revisión",
            "dejalo listo para revision",
            "prepáralo para revisión",
            "preparalo para revision",
            "lista para revisión",
            "lista para revision",
        }:
            return self._intent(
                "prepare_review",
                confidence=0.95,
                signals=["review_handoff_command"],
            )
        if lowered in {
            "sí, esa",
            "si, esa",
            "usa la anterior",
            "prepáralo con esa estructura",
            "preparalo con esa estructura",
        }:
            return self._intent(
                "structured_followup",
                confidence=0.9,
                signals=["structured_followup_command"],
            )
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

        natural_intent = _classify_natural_request(request, state, narrative_signals)
        if natural_intent is not None:
            return natural_intent

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


def _classify_natural_request(
    request: ConversationRequest,
    state: ConversationState | None,
    narrative_signals: NarrativeSignals | None,
) -> RecognizedIntent | None:
    lowered = request.raw_text.strip().lower()
    target_hint = (narrative_signals.target_hint if narrative_signals else None) or request.target_hint
    state_target_type = state.last_target_type if state else None
    state_target_id = state.last_target_id if state else None

    if any(phrase in lowered for phrase in ("ayuda", "qué puedo hacer", "que puedo hacer", "what can i do", "how can i")):
        return _natural_intent(
            "conversation_help",
            confidence=0.78,
            signals=["natural_help_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("contexto del mundo", "world context", "estado del mundo", "global context")):
        return _natural_intent(
            "lookup_world",
            confidence=0.74,
            signals=["natural_world_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("busca", "search", "find", "sácame el contexto", "sacame el contexto")):
        intent_name = "search_context"
        target_type = None
        target_id = None
        requires_target = False
        if "escena" in lowered:
            intent_name = "inspect_scene"
            target_type = "scene"
            target_id = target_hint or (state_target_id if state_target_type == "scene" else None)
            requires_target = True
        elif "capítulo" in lowered or "capitulo" in lowered or "chapter" in lowered:
            intent_name = "inspect_chapter"
            target_type = "chapter"
            target_id = target_hint or (state_target_id if state_target_type == "chapter" else None)
            requires_target = True
        return _natural_intent(
            intent_name,
            confidence=0.72,
            target_type=target_type,
            target_id=target_id,
            requires_target=requires_target,
            signals=["natural_context_request"],
            narrative_signals=narrative_signals,
        )

    if "escena" in lowered:
        return _natural_intent(
            "inspect_scene",
            confidence=0.74,
            target_type="scene",
            target_id=target_hint or (state_target_id if state_target_type == "scene" else None),
            requires_target=True,
            signals=["natural_scene_request"],
            narrative_signals=narrative_signals,
        )

    if "capítulo" in lowered or "capitulo" in lowered or "chapter" in lowered:
        return _natural_intent(
            "inspect_chapter",
            confidence=0.74,
            target_type="chapter",
            target_id=target_hint or (state_target_id if state_target_type == "chapter" else None),
            requires_target=True,
            signals=["natural_chapter_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("guarda esto como decisión", "guarda esto como decision", "decisión de canon", "decision de canon", "haz una decisión de canon", "haz una decision de canon", "registra esto como decisión", "registra esto como decision")):
        return _natural_intent(
            "persist_decision",
            confidence=0.79,
            target_type=state_target_type,
            target_id=target_hint or state_target_id,
            persistent_hint=True,
            signals=["natural_decision_request"],
            narrative_signals=narrative_signals,
            skip_llm_escalation=True,
        )

    if any(phrase in lowered for phrase in ("contradice", "canon", "continuidad", "continuity", "consistencia")):
        conservative_target = _conservative_consistency_target(state, narrative_signals)
        return _natural_intent(
            "consistency_check",
            confidence=0.76,
            target_type=conservative_target[0],
            target_id=conservative_target[1],
            requires_target=True,
            signals=["natural_consistency_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("valida", "validate")):
        return _natural_intent(
            "validate_artifact",
            confidence=0.72,
            target_type=state_target_type,
            target_id=target_hint or state_target_id,
            requires_target=True,
            persistent_hint=True,
            signals=["natural_validate_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("rechaza", "reject", "descarta")):
        return _natural_intent(
            "reject_artifact",
            confidence=0.72,
            target_type=state_target_type,
            target_id=target_hint or state_target_id,
            requires_target=True,
            persistent_hint=True,
            signals=["natural_reject_request"],
            narrative_signals=narrative_signals,
        )

    if any(phrase in lowered for phrase in ("guarda esta decisión", "guarda esta decision", "create a decision", "haz una decisión", "haz una decision")):
        return _natural_intent(
            "persist_decision",
            confidence=0.72,
            persistent_hint=True,
            signals=["natural_decision_request"],
            narrative_signals=narrative_signals,
            skip_llm_escalation=True,
        )

    if _looks_like_editorial_structuring_request(lowered, narrative_signals):
        return _natural_intent(
            "editorial_structuring",
            confidence=0.71,
            target_type=state_target_type,
            target_id=target_hint or state_target_id,
            signals=["editorial_structuring_request"],
            narrative_signals=narrative_signals,
            skip_llm_escalation=True,
        )

    return None


def _natural_intent(
    intent_name: str,
    *,
    confidence: float,
    target_type: str | None = None,
    target_id: str | None = None,
    requires_target: bool = False,
    persistent_hint: bool | None = None,
    signals: list[str] | None = None,
    narrative_signals: NarrativeSignals | None = None,
    skip_llm_escalation: bool = False,
) -> RecognizedIntent:
    return RecognizedIntent(
        intent_name=intent_name,
        confidence=confidence,
        target_type=target_type,
        target_id=target_id,
        requires_target=requires_target,
        persistent_hint=persistent_hint,
        signals=signals or [],
        narrative_signals=narrative_signals,
        recognizer_kind="rule_based",
        metadata={
            "next_recognizer": RuleBasedIntentRecognizer.future_kind,
            "skip_llm_escalation": skip_llm_escalation,
            "classification_note": f"Natural-language request matched {intent_name}.",
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
    lowered = raw.lower()
    if not raw:
        return None

    known_characters = request.metadata.get("known_characters", [])
    matched_names, matched_ids = _match_known_characters(raw, known_characters)
    issue_types: list[str] = []
    constraint_hints: list[str] = []
    mentioned_entities = list(matched_names)

    if any(phrase in lowered for phrase in ("no diría", "no diria", "would never say", "out of character", "no suena a")):
        issue_types.append("character_voice_mismatch")
        constraint_hints.append("check_character_voice")
        if not mentioned_entities:
            hinted = _extract_phrase_hint(raw, ("porque ", "because "))
            if hinted:
                mentioned_entities.append(hinted)

    if any(phrase in lowered for phrase in ("contradice", "canon", "lore", "hard rule")):
        issue_types.append("canon_issue")
        constraint_hints.append("check_validated_canon")
        canon_hint = _extract_after_keyword(raw, ("canon del ", "canon de ", "canon of ", "lore de ", "lore of "))
        if canon_hint and canon_hint not in mentioned_entities:
            mentioned_entities.append(canon_hint)

    if any(phrase in lowered for phrase in ("no encaja", "no cuadra", "chapter anterior", "capítulo anterior", "capitulo anterior", "continuity")):
        issue_types.append("continuity_issue")
        constraint_hints.append("check_recent_continuity")

    if "tono" in lowered or "tone" in lowered:
        issue_types.append("tone_issue")
        constraint_hints.append("check_tone_alignment")

    if any(phrase in lowered for phrase in ("motivation", "motivación", "motivacion", "por qué hace", "por que hace", "why would")):
        issue_types.append("motivation_issue")
        constraint_hints.append("check_character_motivation")

    if any(phrase in lowered for phrase in ("no entiendo", "confuso", "confusing", "not clear", "poco claro")):
        issue_types.append("clarity_issue")
        constraint_hints.append("check_clarity")

    target_hint, target_source = _infer_target_hint(request, state, lowered)
    if not mentioned_entities and request.metadata.get("entity_hint"):
        mentioned_entities.append(str(request.metadata["entity_hint"]))

    if not any((mentioned_entities, matched_ids, target_hint, issue_types, constraint_hints)):
        return None

    return NarrativeSignals(
        mentioned_entities=_dedupe_preserve(mentioned_entities),
        mentioned_character_ids=_dedupe_preserve(matched_ids),
        target_hint=target_hint,
        target_inference_source=target_source,
        issue_types=_dedupe_preserve(issue_types),
        constraint_hints=_dedupe_preserve(constraint_hints),
        confidence=_signal_confidence(matched_ids, issue_types, target_hint),
    )


def _infer_target_hint(
    request: ConversationRequest,
    state: ConversationState | None,
    lowered: str,
) -> tuple[str | None, str | None]:
    if request.target_hint:
        return request.target_hint, "request_hint"
    if state is None or not state.last_target_id:
        return None, None
    if any(word in lowered for word in ("esta escena", "this scene")) and state.last_target_type == "scene":
        return state.last_target_id, "conversation_state"
    if any(word in lowered for word in ("este capítulo", "este capitulo", "this chapter")) and state.last_target_type == "chapter":
        return state.last_target_id, "conversation_state"
    if any(word in lowered for word in ("esta nota", "this note", "esto")):
        return state.last_target_id, "conversation_state"
    return None, None


def _conservative_consistency_target(
    state: ConversationState | None,
    narrative_signals: NarrativeSignals | None,
) -> tuple[str | None, str | None]:
    if narrative_signals is None:
        return (state.last_target_type, state.last_target_id) if state else (None, None)
    if narrative_signals.target_hint and narrative_signals.target_inference_source in {"request_hint", "explicit_input"}:
        return (state.last_target_type if state else None, narrative_signals.target_hint)
    if narrative_signals.mentioned_entities:
        return (None, None)
    return (state.last_target_type, state.last_target_id) if state else (None, None)


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


def _extract_phrase_hint(raw: str, prefixes: tuple[str, ...]) -> str | None:
    lowered = raw.lower()
    for prefix in prefixes:
        index = lowered.find(prefix)
        if index == -1:
            continue
        fragment = raw[index + len(prefix):].strip()
        if not fragment:
            continue
        token = re.split(r"[,.!?]| no | would | diría | diria ", fragment, maxsplit=1)[0].strip()
        return token or None
    return None


def _extract_after_keyword(raw: str, keywords: tuple[str, ...]) -> str | None:
    lowered = raw.lower()
    for keyword in keywords:
        index = lowered.find(keyword)
        if index == -1:
            continue
        fragment = raw[index + len(keyword):].strip()
        if not fragment:
            continue
        return re.split(r"[,.!?]", fragment, maxsplit=1)[0].strip() or None
    return None


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


def _looks_like_editorial_structuring_request(
    lowered: str,
    narrative_signals: NarrativeSignals | None,
) -> bool:
    if any(
        phrase in lowered
        for phrase in (
            "beat by beat",
            "beat a beat",
            "beats",
            "estructura",
            "outline",
            "quiero que",
            "la escena funciona hasta",
            "prepara la narración",
            "prepara la narracion",
        )
    ):
        return True
    if narrative_signals is None:
        return False
    if narrative_signals.issue_types and any(
        phrase in lowered
        for phrase in (
            "no me gusta",
            "debería",
            "deberia",
            "acepta demasiado rápido",
            "acepta demasiado rapido",
            "cede demasiado",
            "quiero que",
        )
    ):
        return True
    if narrative_signals.mentioned_entities and (lowered.count(",") >= 1 or len(narrative_signals.mentioned_entities) >= 2):
        return True
    return False
