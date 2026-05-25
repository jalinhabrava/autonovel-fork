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

def build_deepseek_budget_bridge(task: str = "bootstrap_chapter_extraction") -> dict[str, Any]:
    profiles = [profile for profile in deepseek_family_profiles() if profile.task == task]
    models: list[dict[str, Any]] = []
    for profile in profiles:
        models.append(
            {
                "model_id": profile.model_pattern,
                "profile_id": profile.profile_id,
                "task": profile.task,
                "output_budget_tokens": profile.default_max_output_tokens,
                "prompt_overhead_policy": "use_task_prompt_overhead_plus_profile_overlay_margin",
                "source_budget_policy": "usable_input_budget_after_output_reserve_and_safety_margin",
                "safety_margin_policy": "model_capabilities_or_profile_bridge_margin",
            }
        )
    return {
        "provider": "deepseek",
        "task": task,
        "models": models,
        "remaining_gaps": [
            "TokenBudget does not yet infer profile-specific prompt overhead automatically without explicit bridge input.",
            "Reasoner remains unavailable and unbridged.",
        ],
    }

def build_response_control_contract() -> dict[str, Any]:
    return {
        "response_control": {
            "completion_status": "complete|partial",
            "part_index": 1,
            "part_count_estimate": 1,
            "continuation_required": False,
            "continuation_cursor": None,
            "omitted_sections": [],
        },
        "legacy_outputs_without_response_control": "allowed_but_unknown",
        "compatible_with": ["partial_extraction", "reduction", "continuation_output"],
    }

def build_pro_compact_reduction_policy() -> dict[str, Any]:
    caps = {
        "max_facts_per_item": 2,
        "max_evidence_entries_per_item": 1,
        "max_candidate_summary_points": 0,
        "max_unresolved_mention_note_chars": 120,
        "max_relation_summary_chars": 140,
        "max_event_summary_chars": 160,
    }
    return {
        "mode_id": "pro_compact_reduction_v1",
        "model_family": "deepseek-v4-pro",
        "use_cases": ["chapter_reduction", "length_recovery_retry", "high_reasoning_budget_risk"],
        "caps": caps,
        "affected_sections": [
            "characters",
            "places",
            "concepts",
            "objects",
            "events",
            "relations",
            "unresolved_mentions",
        ],
        "prompt_guidance": [
            "Return exactly one valid JSON object.",
            "Use compact reduction mode.",
            "Prioritize item-level source_refs and canonical structure.",
            "Do not produce long prose.",
            "Do not expand candidate_summary_points.",
            "Prefer compact complete JSON over verbose details when budget is tight.",
        ],
        "rationale": [
            "DeepSeek Pro reduction can exhaust output budget before JSON closes.",
            "Compact caps trade verbosity for parseability and source-ref preservation.",
        ],
        "privacy_safety_notes": {
            "byok": True,
            "no_auto_switch": True,
            "no_openai": True,
            "write_back": False,
        },
    }

def build_patch_based_continuation_contract() -> dict[str, Any]:
    return {
        "request_shape": {
            "top_level_key": "continuation_patch",
            "sections": [
                "characters",
                "places",
                "concepts",
                "objects",
                "events",
                "relations",
                "unresolved_mentions",
            ],
            "patch_metadata": {
                "continues_from": "chunk_or_reduction_run_id",
                "completion_status": "complete|partial|unknown",
                "do_not_repeat_previous_items": True,
            },
        },
        "rules": [
            "Patch only missing or incomplete items.",
            "Do not repeat previous items unless source_refs need completion.",
            "Preserve source_refs.",
            "Return empty patch with structured warning if missing scope is unknown.",
            "Do not reconstruct full JSON object.",
        ],
        "merge_rules": [
            "dedupe_by_canonical_name_or_surface",
            "merge_source_refs_without_duplicates",
            "preserve_review_state_and_local_candidate",
            "do_not_auto_promote_uncertain_items",
        ],
        "safety_rules": {
            "same_provider_model_profile_required": True,
            "no_auto_switch": True,
            "private_packet_trace_required": True,
        },
    }

def build_finish_reason_length_strategy() -> dict[str, Any]:
    return {
        "trigger": "finish_reason=length",
        "budget_exhausted_threshold": 0.95,
        "primary_strategy": "retry_same_model_profile_in_compact_reduction_mode",
        "secondary_strategy": "patch_based_continuation_if_compact_retry_still_incomplete",
        "forbidden": ["open_continuation_full_reconstruction", "auto_switch_model", "openai_fallback"],
        "signals": [
            "finish_reason_length",
            "output_budget_exhausted",
            "reasoning_budget_exhaustion_optional",
            "parseability",
            "raw_tail_shape",
        ],
    }

def build_response_control_runtime_policy() -> dict[str, Any]:
    return {
        "response_control_requested": True,
        "response_control_required_for_success": False,
        "primary_runtime_truth_sources": [
            "finish_reason",
            "usage",
            "parseability",
            "raw_tail_shape",
            "output_token_ratio",
        ],
        "response_control_role": "advisory_only",
        "missing_response_control_policy": "allowed_but_logged",
    }

def build_continuation_repair_contract() -> dict[str, Any]:
    return {
        "triggers": [
            "response_control.partial",
            "invalid_json_truncated",
            "finish_reason_length",
            "output_near_max_tokens",
        ],
        "continuation_request_shape": {
            "same_provider_model_profile_required": True,
            "continuation_cursor_required": True,
            "prior_partial_reference_required": True,
        },
        "continuation_output_shape": {
            "must_return_valid_json": True,
            "must_include_response_control": True,
            "must_preserve_source_refs": True,
        },
        "merge_rules": [
            "do_not_duplicate_previous_items",
            "merge_source_refs_without_duplicates",
            "preserve_review_state_and_local_candidate",
        ],
        "safety_rules": {
            "same_provider_model_profile_unless_user_allows_other": True,
            "no_auto_switch_invisible": True,
            "private_packet_trace_required": True,
        },
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
