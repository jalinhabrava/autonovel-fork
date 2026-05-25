from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from typing import Any


@dataclass(frozen=True)
class ProviderPromptProfile:
    profile_id: str
    provider: str
    model_pattern: str
    task: str
    json_mode: bool
    default_max_output_tokens: int
    json_reliability_policy: str
    prompt_density_policy: str
    overlay_style: str
    schema_strategy: str
    must_include_sections: list[str]
    minimum_density_targets: dict[str, str]
    review_safety_policy: str
    validation_policy: str
    fallback: str
    prompt_overlay: str


_DEEPSEEK_V4_FLASH_BOOTSTRAP_CHAPTER_EXTRACTION_OVERLAY = """DeepSeek V4 Flash JSON reliability and extraction density:

Return exactly one valid JSON object. Do not use markdown.

Keep every required schema key:
work, chapters, characters, places, concepts, objects, events, relations, unresolved_mentions.

Do not compress the extraction into only the summary.

Include structurally relevant:
- objects/tools/artifacts/catalysts/weapons;
- durable events;
- evidence-backed relations;
- important unresolved mentions.

Keep facts concise.
Keep uncertain identities in review/local candidate.
Do not invent names."""


_PROFILES: tuple[ProviderPromptProfile, ...] = (
    ProviderPromptProfile(
        profile_id="deepseek-v4-flash:bootstrap_chapter_extraction:v1",
        provider="deepseek",
        model_pattern="deepseek-v4-flash",
        task="bootstrap_chapter_extraction",
        json_mode=True,
        default_max_output_tokens=8192,
        json_reliability_policy="json_first_no_markdown_single_object",
        prompt_density_policy="compact_high_recall",
        overlay_style="compact_json_first",
        schema_strategy="full_v2_with_density_reminder",
        must_include_sections=[
            "characters",
            "places",
            "concepts",
            "objects",
            "events",
            "relations",
            "unresolved_mentions",
        ],
        minimum_density_targets={
            "objects": "include all structurally relevant artifacts, tools, catalysts, weapons, keys, persistent props, and event-triggering props.",
            "events": "include all durable structural events, not only the final scene outcome.",
            "relations": "include protagonist-object, protagonist-place, protagonist-concept, object-event, authority/political, and magic/system relations when supported.",
            "unresolved_mentions": "include important unresolved actors, objects, concepts, or pronouns rather than silently dropping them.",
            "review": "keep uncertain identities in review or local candidate instead of promoting them.",
        },
        review_safety_policy="do_not_promote_uncertain_identities",
        validation_policy="strict_json_and_density_check",
        fallback="retry_with_density_boost_or_larger_model",
        prompt_overlay=_DEEPSEEK_V4_FLASH_BOOTSTRAP_CHAPTER_EXTRACTION_OVERLAY,
    ),
)


def _all_profiles() -> tuple[ProviderPromptProfile, ...]:
    from textifai.import_review.deepseek_family_profiles import deepseek_family_profiles

    return (*deepseek_family_profiles(), *_PROFILES)


def list_provider_prompt_profiles() -> list[ProviderPromptProfile]:
    return list(_all_profiles())


def get_provider_prompt_profile(provider: str, model: str, task: str) -> ProviderPromptProfile | None:
    normalized_provider = provider.strip().casefold()
    normalized_task = task.strip()
    normalized_model = model.strip().casefold()
    for profile in _all_profiles():
        if profile.provider.casefold() != normalized_provider:
            continue
        if profile.task != normalized_task:
            continue
        pattern = profile.model_pattern.casefold()
        if _model_matches(normalized_model, pattern):
            return profile
    return None


def apply_provider_prompt_profile(system_prompt: str, user_prompt: str, profile: ProviderPromptProfile) -> tuple[str, str]:
    overlay_header = "## Provider Profile Overlay"
    if overlay_header in system_prompt:
        return system_prompt, user_prompt
    separator = "\n\n" if system_prompt.strip() else ""
    updated_system = f"{system_prompt.rstrip()}{separator}{overlay_header}\n\n{profile.prompt_overlay}".strip()
    return updated_system, user_prompt

def inject_output_budget_control(system_prompt: str, *, effective_max_output_tokens: int) -> str:
    header = "## Output Budget Control"
    if header in system_prompt:
        return system_prompt
    block = f"""{header}

You have a maximum output budget of {effective_max_output_tokens} tokens for this response.

If you cannot complete the extraction within this budget:
- return valid JSON anyway;
- set response_control.completion_status = "partial";
- set response_control.continuation_required = true;
- set response_control.continuation_cursor;
- list response_control.omitted_sections;
- do not end mid-string or mid-object."""
    separator = "\n\n" if system_prompt.strip() else ""
    return f"{system_prompt.rstrip()}{separator}{block}".strip()

def inject_compact_reduction_control(system_prompt: str, *, mode_label: str = "compact_reduction_v1") -> str:
    header = "## Compact Reduction Control"
    if header in system_prompt:
        return system_prompt
    block = f"""{header}

Use compact reduction mode: {mode_label}.

Prioritize:
- valid JSON;
- item-level source_refs;
- canonical/entity structure;
- objects/events/relations/unresolved_mentions;
- short evidence only.

Do not produce long prose.
Do not repeat full source text.
Do not expand candidate_summary_points.
Limit each item to short facts/evidence.
Prefer compact complete JSON over verbose details when budget is tight."""
    separator = "\n\n" if system_prompt.strip() else ""
    return f"{system_prompt.rstrip()}{separator}{block}".strip()


def summarize_provider_prompt_profile(profile: ProviderPromptProfile) -> dict[str, Any]:
    data = asdict(profile)
    data["prompt_overlay_preview"] = profile.prompt_overlay.splitlines()[0]
    data.pop("prompt_overlay")
    return data


def validate_extraction_density(payload: dict[str, Any], profile: ProviderPromptProfile) -> dict[str, Any]:
    warnings: list[str] = []
    missing_sections: list[str] = []
    chapter = _first_chapter(payload)
    if chapter is None:
        return {
            "ok": False,
            "warnings": ["missing_chapter_payload"],
            "missing_sections": list(profile.must_include_sections),
            "counts": {},
            "required_sections_present": False,
        }

    counts: dict[str, int] = {}
    for section in profile.must_include_sections:
        value = chapter.get(section)
        if section not in chapter:
            missing_sections.append(section)
            counts[section] = 0
            continue
        counts[section] = len(value) if isinstance(value, list) else 0

    events = chapter.get("events") if isinstance(chapter.get("events"), list) else []
    relations = chapter.get("relations") if isinstance(chapter.get("relations"), list) else []
    if events and not any(isinstance(item, dict) and item.get("event_importance") for item in events):
        warnings.append("events_missing_event_importance")
    if relations and not any(isinstance(item, dict) and item.get("relation_category") for item in relations):
        warnings.append("relations_missing_relation_category")
    if counts.get("relations", 0) <= 1 and sum(counts.get(key, 0) for key in ("characters", "objects", "events")) >= 2:
        warnings.append("low_relation_count")
    if counts.get("objects", 0) == 0:
        warnings.append("low_object_count")
    if counts.get("unresolved_mentions", 0) == 0:
        warnings.append("empty_unresolved_mentions")

    return {
        "ok": not missing_sections,
        "warnings": warnings,
        "missing_sections": missing_sections,
        "counts": counts,
        "required_sections_present": not missing_sections,
    }


def _first_chapter(payload: dict[str, Any]) -> dict[str, Any] | None:
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return None
    first = chapters[0]
    return first if isinstance(first, dict) else None


def _model_matches(model: str, pattern: str) -> bool:
    if pattern == model:
        return True
    if "*" in pattern or "?" in pattern:
        return fnmatchcase(model, pattern)
    return pattern in model or model.startswith(pattern) or model.endswith(pattern)
