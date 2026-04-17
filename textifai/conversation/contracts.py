from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


INTENT_CATALOG = (
    "unknown",
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

TASK_TYPE_CATALOG = (
    "noop",
    "respond",
    "context_lookup",
    "consistency_validation",
    "artifact_persistence",
    "bootstrap_operation",
)

FLOW_NAME_CATALOG = (
    "noop_flow",
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
    "build_context",
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
class RecognizedIntent:
    intent_name: str
    confidence: float
    target_type: str | None = None
    target_id: str | None = None
    requires_target: bool = False
    ephemeral_hint: bool | None = None
    persistent_hint: bool | None = None
    signals: list[str] = field(default_factory=list)
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


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
