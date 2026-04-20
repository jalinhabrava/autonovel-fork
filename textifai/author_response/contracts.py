from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SEMANTIC_RESPONSE_KIND_CATALOG = (
    "structuring_suggestion",
    "revision_guidance",
    "canon_answer",
    "narration_handoff",
    "contextual_followup_response",
    "clarification_with_candidates",
)

PROVIDER_MODE_CATALOG = (
    "disabled",
    "simulated",
    "simulated_preview",
    "live_provider",
    "live_openai",
)


@dataclass(frozen=True)
class AnchoredAuthorPrompt:
    prompt_base_id: str
    prompt_base_version: str
    prompt_template_id: str
    prompt_template_version: str
    semantic_flow_name: str
    semantic_response_kind: str
    model_profile_used: str
    base_template_sections: dict[str, Any]
    dynamic_context_payload: dict[str, Any]
    trace_rendered_prompt_payload: dict[str, Any]
    llm_rendered_prompt_payload: dict[str, Any]
    anchored_evidence_used: dict[str, Any]
    response_support_summary: dict[str, Any]
    response_generation_ready: bool

    def __post_init__(self) -> None:
        if self.semantic_response_kind not in SEMANTIC_RESPONSE_KIND_CATALOG:
            raise ValueError(f"Unsupported semantic_response_kind: {self.semantic_response_kind}")

    @property
    def prompt_version(self) -> str:
        return self.prompt_template_version

    @property
    def system_prompt(self) -> str:
        return str(self.llm_rendered_prompt_payload.get("system_prompt", ""))

    @property
    def user_payload(self) -> dict[str, Any]:
        payload = self.llm_rendered_prompt_payload.get("user_payload")
        if isinstance(payload, dict):
            return payload
        return self.dynamic_context_payload

    @property
    def rendered_prompt_payload(self) -> dict[str, Any]:
        return self.trace_rendered_prompt_payload

    def trace_payload(self) -> dict[str, Any]:
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


@dataclass(frozen=True)
class AnchoredAuthorResponse:
    semantic_response_kind: str
    author_facing_response: str | None
    response_generation_ready: bool
    anchored_prompt_payload: dict[str, Any]
    response_support_summary: dict[str, Any] = field(default_factory=dict)
    llm_used: bool = False
    provider_mode: str = "disabled"
    response_generation_mode: str = "disabled"
    response_generation_reason: str | None = None
    provider_execution_enabled: bool = False
    provider_execution_mode: str = "disabled"
    provider_model_used: str | None = None
    live_model_response: str | None = None
    simulated_preview_enabled: bool = False
    simulated_preview_output: str | None = None

    def __post_init__(self) -> None:
        if self.semantic_response_kind not in SEMANTIC_RESPONSE_KIND_CATALOG:
            raise ValueError(f"Unsupported semantic_response_kind: {self.semantic_response_kind}")
        if self.provider_mode not in PROVIDER_MODE_CATALOG:
            raise ValueError(f"Unsupported provider_mode: {self.provider_mode}")
