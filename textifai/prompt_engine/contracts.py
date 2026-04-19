from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PromptBaseDefinition:
    prompt_base_id: str
    prompt_base_version: str
    system_role: str
    stable_instructions: list[str] = field(default_factory=list)
    authoring_priorities: list[str] = field(default_factory=list)
    transversal_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PromptTemplateDefinition:
    prompt_template_id: str
    prompt_template_version: str
    semantic_flow_name: str
    semantic_response_kind: str
    objective: str
    stable_instructions: list[str] = field(default_factory=list)
    prudence_rules: list[str] = field(default_factory=list)
    author_style: list[str] = field(default_factory=list)
    output_expectations: list[str] = field(default_factory=list)
    insufficient_support_behavior: list[str] = field(default_factory=list)
    context_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticPromptContext:
    semantic_flow_name: str
    semantic_response_kind: str
    request_text: str
    operation_language: str
    response_language: str
    artifact_target_language: str | None
    context_payload: dict[str, Any] = field(default_factory=dict)
    llm_context_payload: dict[str, Any] = field(default_factory=dict)
    anchored_evidence_used: dict[str, Any] = field(default_factory=dict)
    response_support_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelPromptProfile:
    model_profile_id: str
    instruction_order: list[str] = field(default_factory=list)
    explicitness: str = "balanced"
    output_wrapper: str = "json_payload"
    overlay_instructions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderedPromptPayload:
    prompt_base_id: str
    prompt_base_version: str
    prompt_template_id: str
    prompt_template_version: str
    semantic_flow_name: str
    semantic_response_kind: str
    model_profile_used: str
    base_template_sections: dict[str, Any]
    dynamic_context_payload: dict[str, Any]
    anchored_evidence_used: dict[str, Any]
    response_support_summary: dict[str, Any]
    trace_rendered_prompt_payload: dict[str, Any]
    llm_rendered_prompt_payload: dict[str, Any]

    @property
    def rendered_prompt_payload(self) -> dict[str, Any]:
        return self.trace_rendered_prompt_payload

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_base_id": self.prompt_base_id,
            "prompt_base_version": self.prompt_base_version,
            "prompt_template_id": self.prompt_template_id,
            "prompt_template_version": self.prompt_template_version,
            "semantic_flow_name": self.semantic_flow_name,
            "semantic_response_kind": self.semantic_response_kind,
            "model_profile_used": self.model_profile_used,
            "base_template_sections": self.base_template_sections,
            "dynamic_context_payload": self.dynamic_context_payload,
            "anchored_evidence_used": self.anchored_evidence_used,
            "response_support_summary": self.response_support_summary,
            "trace_rendered_prompt_payload": self.trace_rendered_prompt_payload,
            "llm_rendered_prompt_payload": self.llm_rendered_prompt_payload,
        }
