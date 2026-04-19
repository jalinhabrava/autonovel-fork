from __future__ import annotations

from textifai.prompt_engine.contracts import ModelPromptProfile, PromptBaseDefinition, PromptTemplateDefinition, RenderedPromptPayload, SemanticPromptContext
from textifai.prompt_engine.model_adapter import ordered_sections


def render_prompt_payload(
    *,
    prompt_base: PromptBaseDefinition,
    template: PromptTemplateDefinition,
    profile: ModelPromptProfile,
    context: SemanticPromptContext,
) -> RenderedPromptPayload:
    sections = ordered_sections(template, profile)
    system_lines = [
        prompt_base.system_role,
        f"Semantic flow: {context.semantic_flow_name}.",
        f"Response kind: {context.semantic_response_kind}.",
        f"Model profile: {profile.model_profile_id}.",
        "Base doctrine:",
    ]
    system_lines.extend(f"- {item}" for item in prompt_base.stable_instructions)
    system_lines.append("Always optimize for:")
    system_lines.extend(f"{index}. {item}" for index, item in enumerate(prompt_base.authoring_priorities, start=1))
    system_lines.append("Cross-flow rules:")
    system_lines.extend(f"- {item}" for item in prompt_base.transversal_rules)
    for name, value in sections:
        if isinstance(value, list):
            if not value:
                continue
            system_lines.append(f"{name}:")
            system_lines.extend(f"- {item}" for item in value)
        else:
            system_lines.append(f"{name}: {value}")

    trace_rendered_prompt = {
        "system_prompt": "\n".join(system_lines),
        "user_payload": context.context_payload,
        "prompt_sections": [
            {"name": name, "value": value}
            for name, value in sections
        ],
        "output_wrapper": profile.output_wrapper,
        "explicitness": profile.explicitness,
    }
    llm_rendered_prompt = {
        "system_prompt": "\n".join(system_lines),
        "user_payload": context.llm_context_payload,
        "output_wrapper": profile.output_wrapper,
        "explicitness": profile.explicitness,
    }

    return RenderedPromptPayload(
        prompt_base_id=prompt_base.prompt_base_id,
        prompt_base_version=prompt_base.prompt_base_version,
        prompt_template_id=template.prompt_template_id,
        prompt_template_version=template.prompt_template_version,
        semantic_flow_name=template.semantic_flow_name,
        semantic_response_kind=template.semantic_response_kind,
        model_profile_used=profile.model_profile_id,
        base_template_sections={
            "prompt_base": {
                "system_role": prompt_base.system_role,
                "stable_instructions": prompt_base.stable_instructions,
                "authoring_priorities": prompt_base.authoring_priorities,
                "transversal_rules": prompt_base.transversal_rules,
            },
            "objective": template.objective,
            "stable_instructions": template.stable_instructions,
            "prudence_rules": template.prudence_rules,
            "author_style": template.author_style,
            "output_expectations": template.output_expectations,
            "insufficient_support_behavior": template.insufficient_support_behavior,
        },
        dynamic_context_payload=context.context_payload,
        anchored_evidence_used=context.anchored_evidence_used,
        response_support_summary=context.response_support_summary,
        trace_rendered_prompt_payload=trace_rendered_prompt,
        llm_rendered_prompt_payload=llm_rendered_prompt,
    )
