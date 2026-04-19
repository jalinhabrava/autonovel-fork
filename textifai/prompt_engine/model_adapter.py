from __future__ import annotations

from textifai.prompt_engine.contracts import ModelPromptProfile, PromptTemplateDefinition


def ordered_sections(
    template: PromptTemplateDefinition,
    profile: ModelPromptProfile,
) -> list[tuple[str, object]]:
    sections = {
        "objective": template.objective,
        "stable_instructions": template.stable_instructions,
        "prudence_rules": template.prudence_rules,
        "author_style": template.author_style,
        "output_expectations": template.output_expectations,
        "insufficient_support_behavior": template.insufficient_support_behavior,
        "overlay_instructions": profile.overlay_instructions,
    }
    ordered: list[tuple[str, object]] = []
    seen: set[str] = set()
    for name in profile.instruction_order:
        if name in sections:
            ordered.append((name, sections[name]))
            seen.add(name)
    for name, value in sections.items():
        if name not in seen:
            ordered.append((name, value))
    return ordered
