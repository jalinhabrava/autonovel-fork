from __future__ import annotations

import json
from pathlib import Path

from textifai.prompt_engine.contracts import ModelPromptProfile, PromptBaseDefinition, PromptTemplateDefinition


_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = _ROOT / "prompt_templates"
_MODEL_PROFILE_DIR = _ROOT / "model_profiles"


def load_prompt_base() -> PromptBaseDefinition:
    path = _TEMPLATE_DIR / "_author_facing_base.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return PromptBaseDefinition(
        prompt_base_id=data["prompt_base_id"],
        prompt_base_version=data["prompt_base_version"],
        system_role=data["system_role"],
        stable_instructions=list(data.get("stable_instructions", [])),
        authoring_priorities=list(data.get("authoring_priorities", [])),
        transversal_rules=list(data.get("transversal_rules", [])),
    )


def load_prompt_template(semantic_flow_name: str) -> PromptTemplateDefinition:
    path = _TEMPLATE_DIR / f"{semantic_flow_name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return PromptTemplateDefinition(
        prompt_template_id=data["prompt_template_id"],
        prompt_template_version=data["prompt_template_version"],
        semantic_flow_name=data["semantic_flow_name"],
        semantic_response_kind=data["semantic_response_kind"],
        objective=data["objective"],
        stable_instructions=list(data.get("stable_instructions", [])),
        prudence_rules=list(data.get("prudence_rules", [])),
        author_style=list(data.get("author_style", [])),
        output_expectations=list(data.get("output_expectations", [])),
        insufficient_support_behavior=list(data.get("insufficient_support_behavior", [])),
        context_keys=list(data.get("context_keys", [])),
    )


def load_model_profile(model_profile_id: str) -> ModelPromptProfile:
    path = _MODEL_PROFILE_DIR / f"{model_profile_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ModelPromptProfile(
        model_profile_id=data["model_profile_id"],
        instruction_order=list(data.get("instruction_order", [])),
        explicitness=data.get("explicitness", "balanced"),
        output_wrapper=data.get("output_wrapper", "json_payload"),
        overlay_instructions=list(data.get("overlay_instructions", [])),
    )
