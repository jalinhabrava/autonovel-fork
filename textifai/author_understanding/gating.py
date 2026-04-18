from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from textifai.author_understanding.contracts import AUTHOR_UNDERSTANDING_ROUTE_CATALOG

if TYPE_CHECKING:
    from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
    from textifai.conversation.state import ConversationState


@dataclass(frozen=True)
class AuthorUnderstandingRoute:
    route_type: str
    reason: str
    should_use_llm: bool
    token_count: int = 0
    has_recent_context: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.route_type not in AUTHOR_UNDERSTANDING_ROUTE_CATALOG:
            raise ValueError(f"Unsupported route_type: {self.route_type}")


def classify_author_understanding_route(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    state: ConversationState | None,
    narrative_signals: NarrativeSignals | None = None,
) -> AuthorUnderstandingRoute:
    token_count = _token_count(request.raw_text)
    has_recent_context = bool(state and state.last_target_id)
    if _is_expert_bypass(request=request, rule_intent=rule_intent, state=state):
        return AuthorUnderstandingRoute(
            route_type="expert_bypass",
            reason="closed_form_or_direct_operation",
            should_use_llm=False,
            token_count=token_count,
            has_recent_context=has_recent_context,
            metadata={
                "intent_name": rule_intent.intent_name,
                "target_id": rule_intent.target_id,
                "target_type": rule_intent.target_type,
            },
        )

    if _is_trivial_contextual_case(
        request=request,
        rule_intent=rule_intent,
        state=state,
        narrative_signals=narrative_signals,
        token_count=token_count,
    ):
        return AuthorUnderstandingRoute(
            route_type="trivial_contextual_case",
            reason="short_recent_contextual_followup",
            should_use_llm=False,
            token_count=token_count,
            has_recent_context=has_recent_context,
            metadata={
                "intent_name": rule_intent.intent_name,
                "target_id": rule_intent.target_id or request.target_hint or (state.last_target_id if state else None),
                "target_type": rule_intent.target_type or (state.last_target_type if state else None),
            },
        )

    return AuthorUnderstandingRoute(
        route_type="freeform_author_request",
        reason="freeform_author_request_requires_interpretation",
        should_use_llm=True,
        token_count=token_count,
        has_recent_context=has_recent_context,
        metadata={
            "intent_name": rule_intent.intent_name,
            "target_id": rule_intent.target_id or request.target_hint or (state.last_target_id if state else None),
            "target_type": rule_intent.target_type or (state.last_target_type if state else None),
        },
    )


def _is_expert_bypass(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    state: ConversationState | None,
) -> bool:
    if rule_intent.metadata.get("unsupported_capability"):
        return True
    if request.raw_text.strip().startswith("/"):
        return True
    if rule_intent.intent_name in {"confirm_pending", "cancel_pending", "conversation_help", "validate_structure", "prepare_narration", "prepare_review", "structured_followup"}:
        return True
    if rule_intent.intent_name in {"persist_decision", "validate_artifact", "reject_artifact", "consistency_check"}:
        return bool(rule_intent.target_id or request.target_hint or (state is not None and state.last_target_id))
    return False


def _is_trivial_contextual_case(
    *,
    request: ConversationRequest,
    rule_intent: RecognizedIntent,
    state: ConversationState | None,
    narrative_signals: NarrativeSignals | None,
    token_count: int,
) -> bool:
    if state is None or state.last_target_id is None:
        return False
    if rule_intent.intent_name != "unknown" and rule_intent.intent_name not in {"structured_followup"}:
        return False
    if request.target_hint or rule_intent.target_id or (narrative_signals is not None and narrative_signals.target_hint):
        return True
    if token_count <= 2:
        return True
    return False


def _token_count(raw_text: str) -> int:
    return len([token for token in raw_text.strip().split() if token])
