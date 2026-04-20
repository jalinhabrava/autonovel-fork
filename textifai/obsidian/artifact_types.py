from __future__ import annotations

from pathlib import Path


def normalize_artifact_type(
    *,
    vault_relative_path: str | Path | None,
    frontmatter_kind: object = None,
    snapshot_artifact_type: object = None,
) -> str:
    normalized = _normalize_path(vault_relative_path)
    if normalized.startswith("_templates/"):
        return "note"

    hinted = _normalize_hint(frontmatter_kind)
    if hinted is not None:
        return hinted

    hinted = _normalize_hint(snapshot_artifact_type)
    if hinted is not None:
        return hinted

    if normalized.startswith("03_characters/profiles/"):
        return "character"
    if normalized.startswith("02_world/lore/"):
        return "lore"
    if normalized.startswith("02_world/places/"):
        return "location"
    if normalized.startswith("02_world/magic/"):
        return "lore"
    if normalized.startswith("02_world/creatures/"):
        return "lore"
    if normalized.startswith("02_world/factions/"):
        return "lore"
    if normalized.startswith("02_world/objects/"):
        return "lore"
    if normalized.startswith("02_world/history/"):
        return "lore"
    if normalized.startswith("04_story/chapter_summaries/"):
        return "chapter_summary"
    if normalized.startswith("04_story/chapters/"):
        return "chapter"
    if normalized.startswith("04_outline/scenes/"):
        return "scene"
    if normalized.startswith("06_canon/decisions/"):
        return "decision"
    if normalized.startswith("99_import_staging/99_import_staging/characters/") or normalized.startswith("99_import_staging/characters/"):
        return "character"
    if normalized.startswith("99_import_staging/99_import_staging/lore/") or normalized.startswith("99_import_staging/lore/"):
        return "lore"
    if normalized.startswith("99_import_staging/99_import_staging/scenes/") or normalized.startswith("99_import_staging/scenes/"):
        return "scene"
    if normalized.startswith("99_import_staging/99_import_staging/chapters/") or normalized.startswith("99_import_staging/chapters/"):
        return "chapter"
    if normalized.startswith("99_import_staging/99_import_staging/mixed/") or normalized.startswith("99_import_staging/mixed/"):
        return "mixed_note"
    return "note"


def _normalize_hint(value: object) -> str | None:
    raw = str(value or "").strip().casefold()
    if not raw:
        return None
    mappings = {
        "character": "character",
        "lore": "lore",
        "place": "location",
        "scene": "scene",
        "chapter": "chapter",
        "chapter_summary": "chapter_summary",
        "decision": "decision",
        "location": "location",
        "object": "object",
        "canon_decision": "decision",
        "mixed_note": "note",
        "project_note": "note",
        "revision_brief": "note",
        "mystery": "note",
        "world": "note",
        "voice": "note",
        "seed": "note",
        "outline": "note",
        "canon": "note",
        "manuscript": "note",
        "arc_summary": "note",
        "note": None,
    }
    return mappings.get(raw, "note")


def _normalize_path(value: str | Path | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "/").casefold().replace(" ", "_")
