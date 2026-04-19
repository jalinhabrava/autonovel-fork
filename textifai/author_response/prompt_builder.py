from __future__ import annotations

from typing import Any

from textifai.author_response.contracts import AnchoredAuthorPrompt
from textifai.conversation.contracts import ConversationRequest, PlannedTask
from textifai.editorial.contracts import EditorialStructuringResult
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.followthrough.contracts import FollowThroughResult
from textifai.prompt_engine import (
    build_semantic_prompt_context,
    load_prompt_base,
    load_model_profile,
    load_prompt_template,
    render_prompt_payload,
)


def build_anchored_author_prompt(
    *,
    request: ConversationRequest,
    task: PlannedTask,
    semantic_response_kind: str,
    response_generation_ready: bool,
    author_understanding: dict | None,
    editorial_intent: EditorialIntent | None,
    entity_results: list[dict[str, Any]],
    vault_context_snippets: list[dict[str, str]],
    supporting_canon: list[dict[str, str]],
    structuring_result: EditorialStructuringResult | None = None,
    followthrough_result: FollowThroughResult | None = None,
    consistency_report: dict[str, Any] | None = None,
    clarification_payload: dict[str, Any] | None = None,
    exact_artifact_resolution: bool = False,
    semantic_working_sufficiency: bool = False,
    general_editorial_sufficiency: bool = False,
    anchored_editorial_sufficiency: bool = False,
) -> AnchoredAuthorPrompt:
    semantic_flow_name = _semantic_flow_name(semantic_response_kind)
    model_profile_id = _resolve_model_profile_id(request=request, task=task)
    context = build_semantic_prompt_context(
        request=request,
        task=task,
        semantic_flow_name=semantic_flow_name,
        semantic_response_kind=semantic_response_kind,
        response_generation_ready=response_generation_ready,
        exact_artifact_resolution=exact_artifact_resolution,
        semantic_working_sufficiency=semantic_working_sufficiency,
        general_editorial_sufficiency=general_editorial_sufficiency,
        anchored_editorial_sufficiency=anchored_editorial_sufficiency,
        author_understanding=author_understanding,
        editorial_intent=editorial_intent,
        entity_results=entity_results,
        vault_context_snippets=vault_context_snippets,
        supporting_canon=supporting_canon,
        structuring_result=structuring_result,
        followthrough_result=followthrough_result,
        consistency_report=consistency_report,
        clarification_payload=clarification_payload,
    )
    prompt_base = load_prompt_base()
    template = load_prompt_template(semantic_flow_name)
    profile = load_model_profile(model_profile_id)
    rendered = render_prompt_payload(prompt_base=prompt_base, template=template, profile=profile, context=context)

    return AnchoredAuthorPrompt(
        prompt_base_id=rendered.prompt_base_id,
        prompt_base_version=rendered.prompt_base_version,
        prompt_template_id=rendered.prompt_template_id,
        prompt_template_version=rendered.prompt_template_version,
        semantic_flow_name=rendered.semantic_flow_name,
        semantic_response_kind=semantic_response_kind,
        model_profile_used=rendered.model_profile_used,
        base_template_sections=rendered.base_template_sections,
        dynamic_context_payload=rendered.dynamic_context_payload,
        trace_rendered_prompt_payload=rendered.trace_rendered_prompt_payload,
        llm_rendered_prompt_payload=rendered.llm_rendered_prompt_payload,
        anchored_evidence_used=rendered.anchored_evidence_used,
        response_support_summary=rendered.response_support_summary,
        response_generation_ready=response_generation_ready,
    )


def _semantic_flow_name(semantic_response_kind: str) -> str:
    mapping = {
        "structuring_suggestion": "structuring_request",
        "revision_guidance": "editorial_revision",
        "canon_answer": "consistency_check",
        "narration_handoff": "prepare_narration",
        "contextual_followup_response": "contextual_followup",
        "clarification_with_candidates": "clarification_with_candidates",
    }
    return mapping.get(semantic_response_kind, "clarification_with_candidates")


def _resolve_model_profile_id(*, request: ConversationRequest, task: PlannedTask) -> str:
    explicit = request.metadata.get("model_profile")
    if isinstance(explicit, str) and explicit:
        return explicit
    metadata_profile = task.metadata.get("model_profile_used")
    if isinstance(metadata_profile, str) and metadata_profile:
        return metadata_profile
    return "openai_chatgpt"
