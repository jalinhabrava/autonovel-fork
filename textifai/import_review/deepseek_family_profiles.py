from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from textifai.import_review.provider_prompt_profiles import ProviderPromptProfile

DEEPSEEK_FAMILY_REQUIRED_SECTIONS = [
    "characters",
    "places",
    "concepts",
    "objects",
    "events",
    "relations",
    "unresolved_mentions",
]

FLASH_OER_FOCUS_OVERLAY = """Return exactly one valid JSON object. Do not use markdown.

Do not compress into summary only.

Focus especially on:
1. objects: include all tools, artifacts, catalysts, weapons, restraints, keys, props that trigger or explain events.
2. events: include all durable state changes, not only the final outcome.
3. relations: include all evidence-backed links involving protagonist, authority, places, objects, concepts, and events.
4. unresolved_mentions: do not drop important unknown references.

Also include characters, places, and concepts normally.
Keep facts concise.
Keep uncertainty in review/local_candidate.
Do not invent names."""

PRO_BALANCED_KB_OVERLAY = """Return exactly one valid JSON object. Do not use markdown.

Extract for a story knowledge base, not for a short summary.

Include evidence-supported:
- characters and important unnamed roles;
- places and subplaces;
- concepts and magic/system states;
- objects, tools, artifacts, catalysts, weapons, restraints, keys, and event-triggering props;
- durable events;
- relations between extracted items;
- unresolved important mentions.

Prefer coverage over brevity, but keep each fact concise.
Use review/local_candidate when identity or canonical merge is uncertain.
Use unresolved_mentions instead of dropping unclear but important references.
Do not invent names."""

DEEPSEEK_REASONER_STATUS = {
    "model_id": "deepseek-reasoner",
    "discovery_status": "not_visible_in_sp069",
    "profile_status": "not_packaged",
    "reason": "not available in current model discovery",
}

@dataclass(frozen=True)
class DeepSeekModelGuidance:
    model_id: str
    profile_id: str | None
    enabled: bool
    guidance: list[str]
    warnings: list[str]
    rerun_guidance: list[str]


def deepseek_family_profiles() -> tuple[ProviderPromptProfile, ...]:
    return (
        ProviderPromptProfile(
            profile_id="deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
            provider="deepseek",
            model_pattern="deepseek-v4-flash",
            task="bootstrap_chapter_extraction",
            json_mode=True,
            default_max_output_tokens=8192,
            json_reliability_policy="json_first_no_markdown_single_object",
            prompt_density_policy="oer_focus_high_recall",
            overlay_style="deepseek_family_oer_focus",
            schema_strategy="full_v2_objects_events_relations_boost",
            must_include_sections=list(DEEPSEEK_FAMILY_REQUIRED_SECTIONS),
            minimum_density_targets={
                "objects": "include tools, artifacts, catalysts, weapons, restraints, keys, and event-triggering props.",
                "events": "include durable state changes, not only final outcomes.",
                "relations": "include evidence-backed links involving protagonist, authority, places, objects, concepts, and events.",
                "unresolved_mentions": "include important unclear references instead of dropping them.",
                "review": "keep uncertain identities in review/local_candidate with review_reason.",
            },
            review_safety_policy="do_not_promote_uncertain_identities",
            validation_policy="strict_json_density_and_thin_output_warnings",
            fallback="same_model_rerun_with_alternate_deepseek_profile_if_available",
            prompt_overlay=FLASH_OER_FOCUS_OVERLAY,
        ),
        ProviderPromptProfile(
            profile_id="deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1",
            provider="deepseek",
            model_pattern="deepseek-v4-pro",
            task="bootstrap_chapter_extraction",
            json_mode=True,
            default_max_output_tokens=8192,
            json_reliability_policy="json_first_no_markdown_single_object",
            prompt_density_policy="balanced_story_kb_high_recall",
            overlay_style="deepseek_family_balanced_kb",
            schema_strategy="full_v2_balanced_story_knowledge_base",
            must_include_sections=list(DEEPSEEK_FAMILY_REQUIRED_SECTIONS),
            minimum_density_targets={
                "characters": "include named characters and important unnamed roles.",
                "places": "include places and subplaces.",
                "concepts": "include concepts and magic/system states.",
                "objects": "include objects, tools, artifacts, catalysts, weapons, restraints, keys, and event-triggering props.",
                "events": "include durable events.",
                "relations": "include relations between extracted items.",
                "unresolved_mentions": "include unresolved important mentions.",
                "review": "use review/local_candidate when identity or canonical merge is uncertain.",
            },
            review_safety_policy="do_not_promote_uncertain_identities",
            validation_policy="strict_json_density_and_thin_output_warnings",
            fallback="same_model_rerun_with_alternate_deepseek_profile_if_available",
            prompt_overlay=PRO_BALANCED_KB_OVERLAY,
        ),
    )


def get_deepseek_family_profile(model_id: str, task: str = "bootstrap_chapter_extraction") -> ProviderPromptProfile | None:
    normalized_model = model_id.strip().casefold()
    normalized_task = task.strip()
    for profile in deepseek_family_profiles():
        if profile.task == normalized_task and profile.model_pattern.casefold() == normalized_model:
            return profile
    return None


def build_deepseek_byok_guidance(enabled_models: list[str]) -> dict[str, Any]:
    enabled = {model.strip() for model in enabled_models}
    known = {profile.model_pattern: profile for profile in deepseek_family_profiles()}
    model_guidance: list[DeepSeekModelGuidance] = []
    for model_id, profile in known.items():
        is_enabled = model_id in enabled
        if not is_enabled:
            continue
        model_guidance.append(
            DeepSeekModelGuidance(
                model_id=model_id,
                profile_id=profile.profile_id,
                enabled=True,
                guidance=[
                    f"Use profile {profile.profile_id} for bootstrap_chapter_extraction.",
                    "Validate JSON and density before accepting output.",
                    "Keep user-selected provider/model explicit.",
                ],
                warnings=[
                    "model_profile_experimental",
                    "valid_json_may_still_be_thin",
                ],
                rerun_guidance=[
                    "If output is thin, rerun with same enabled model when alternate same-model profile exists.",
                    "Do not auto-switch to another model without user action.",
                ],
            )
        )

    unavailable = []
    if "deepseek-reasoner" not in enabled:
        unavailable.append(dict(DEEPSEEK_REASONER_STATUS))

    return {
        "provider": "deepseek",
        "byok_policy": "user_enabled_models_only",
        "enabled_models": sorted(enabled),
        "model_guidance": [asdict(item) for item in model_guidance],
        "unavailable_models": unavailable,
        "auto_switching": False,
        "global_routing": False,
        "informational_comparison_allowed": len(model_guidance) > 1,
    }


def build_thin_output_warnings(metrics: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    score = _number(metrics.get("density_score"), metrics.get("score"))
    response_text_chars = _number(metrics.get("response_text_chars"))
    objects = _count(metrics, "objects")
    events = _count(metrics, "events")
    relations = _count(metrics, "relations")
    unresolved = _count(metrics, "unresolved_mentions")
    parseable = bool(metrics.get("response_parseable_json", True))
    validation_ok = bool(metrics.get("validation_ok", True))

    if parseable and validation_ok and score is not None and score < 20:
        warnings.append("valid_json_but_thin")
    if score is not None and score < 20:
        warnings.append("low_density_score")
    if objects <= 1:
        warnings.append("low_objects_count")
    if events <= 1:
        warnings.append("low_events_count")
    if relations <= 2:
        warnings.append("low_relations_count")
    if unresolved == 0 and metrics.get("ambiguous_context", True):
        warnings.append("zero_unresolved_mentions_in_ambiguous_context")
    if response_text_chars is not None and response_text_chars < 2500:
        warnings.append("valid_json_but_thin")
    warnings.append("model_profile_experimental")

    ordered = list(dict.fromkeys(warnings))
    return {
        "warnings": ordered,
        "warning_count": len(ordered),
        "rerun_guidance": "same_provider_same_model_rerun_if_alternate_profile_available",
        "auto_switching": False,
    }


def build_deepseek_e2e_readiness_gate() -> dict[str, Any]:
    return {
        "assessment": "deepseek_family_profiles_packaged_for_e2e_preflight",
        "deepseek_family_usable_for_low_cost_e2e_preflight": True,
        "production_quality_claim": False,
        "requires_review_warnings": True,
        "requires_output_validation": True,
        "reasoner_profile_available": False,
        "common_family_profile_viable": False,
        "per_model_profiles_required": True,
        "provider_calls_required_for_packaging": False,
        "write_back_allowed": False,
    }


def _count(metrics: dict[str, Any], section: str) -> int:
    counts = metrics.get("counts")
    if isinstance(counts, dict):
        return int(counts.get(section, 0) or 0)
    return int(metrics.get(f"{section}_count", 0) or 0)


def _number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
