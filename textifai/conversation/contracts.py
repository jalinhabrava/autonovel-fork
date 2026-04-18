from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from textifai.editorial_intent.contracts import EditorialIntent

INTENT_CATALOG = (
    "unknown",
    "editorial_structuring",
    "confirm_pending",
    "cancel_pending",
    "conversation_help",
    "lookup_world",
    "search_context",
    "inspect_scene",
    "inspect_chapter",
    "consistency_check",
    "persist_decision",
    "validate_artifact",
    "reject_artifact",
    "bootstrap_extract",
)

ISSUE_TYPE_CATALOG = (
    "character_voice_mismatch",
    "canon_issue",
    "continuity_issue",
    "tone_issue",
    "motivation_issue",
    "clarity_issue",
)

CONSTRAINT_HINT_CATALOG = (
    "check_character_voice",
    "check_validated_canon",
    "check_recent_continuity",
    "check_tone_alignment",
    "check_character_motivation",
    "check_clarity",
)

TASK_TYPE_CATALOG = (
    "noop",
    "respond",
    "conversation_control",
    "context_lookup",
    "consistency_validation",
    "artifact_persistence",
    "bootstrap_operation",
    "editorial_structuring",
)

FLOW_NAME_CATALOG = (
    "noop_flow",
    "editorial_structuring_flow",
    "confirm_pending_flow",
    "cancel_pending_flow",
    "help_flow",
    "world_lookup_flow",
    "context_search_flow",
    "scene_context_flow",
    "chapter_context_flow",
    "consistency_check_flow",
    "decision_persistence_flow",
    "validate_artifact_flow",
    "reject_artifact_flow",
    "bootstrap_extract_flow",
)

STEP_KIND_CATALOG = (
    "recognize_intent",
    "resolve_target",
    "resolve_entities",
    "confirm_operation",
    "cancel_operation",
    "build_context",
    "structure_editorial",
    "prepare_narration_context",
    "call_llm",
    "run_consistency_check",
    "persist_artifact",
    "return_response",
)


@dataclass(frozen=True)
class ConversationRequest:
    raw_text: str
    source: Literal["user", "system"]
    mode: Literal["normal", "advanced"]
    interface_language: str
    user_command_language: str
    internal_system_language: str
    project_default_language: str
    mixed_language_allowed: bool
    artifact_target_language: str | None = None
    explanation_language: str | None = None
    target_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NarrativeSignals:
    mentioned_entities: list[str] = field(default_factory=list)
    mentioned_character_ids: list[str] = field(default_factory=list)
    target_hint: str | None = None
    target_inference_source: str | None = None
    issue_types: list[str] = field(default_factory=list)
    constraint_hints: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        for issue_type in self.issue_types:
            _ensure_catalog_value("issue_type", issue_type, ISSUE_TYPE_CATALOG)
        for constraint_hint in self.constraint_hints:
            _ensure_catalog_value("constraint_hint", constraint_hint, CONSTRAINT_HINT_CATALOG)


@dataclass(frozen=True)
class RecognizedIntent:
    intent_name: str
    confidence: float
    target_type: str | None = None
    target_id: str | None = None
    requires_target: bool = False
    ephemeral_hint: bool | None = None
    persistent_hint: bool | None = None
    signals: list[str] = field(default_factory=list)
    narrative_signals: NarrativeSignals | None = None
    editorial_intent: EditorialIntent | None = None
    recognizer_kind: Literal["rule_based", "hybrid_stub", "hybrid_llm"] = "rule_based"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("intent_name", self.intent_name, INTENT_CATALOG)


@dataclass(frozen=True)
class PlannedTask:
    task_type: str
    flow_name: str
    target_type: str | None
    target_id: str | None
    ephemeral: bool
    persistent: bool
    operation_language: str
    artifact_target_language: str | None
    explanation_language: str
    requires_context: bool
    requires_llm: bool
    requires_persistence: bool
    step_kinds: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("task_type", self.task_type, TASK_TYPE_CATALOG)
        _ensure_catalog_value("flow_name", self.flow_name, FLOW_NAME_CATALOG)
        for step_kind in self.step_kinds:
            _ensure_catalog_value("step_kind", step_kind, STEP_KIND_CATALOG)


@dataclass(frozen=True)
class ConversationTurn:
    turn_index: int
    request: ConversationRequest
    recognized_intent: RecognizedIntent | None
    planned_task: PlannedTask | None
    result_type: str | None = None
    result_summary: str | None = None
    artifacts_touched: list[str] = field(default_factory=list)
    context_used: bool = False
    persisted: bool = False


@dataclass(frozen=True)
class PendingConversationOperation:
    operation_id: str
    operation_kind: str
    task_type: str
    flow_name: str
    target_type: str | None
    target_id: str | None
    artifact_target_language: str | None
    explanation_language: str
    payload: dict[str, Any]
    summary: str
    executable: bool
    missing_fields: list[str] = field(default_factory=list)
    created_from_turn: int = 0


@dataclass(frozen=True)
class ExecutionResult:
    type: str
    flow_name: str
    success: bool
    result_summary: str
    result: Any | None = None
    context_request: dict | None = None
    context_pack: dict | None = None
    artifacts_touched: list[str] = field(default_factory=list)
    persisted: bool = False
    missing_target: bool = False
    pending_operation: PendingConversationOperation | None = None
    clear_pending_operation: bool = False


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
