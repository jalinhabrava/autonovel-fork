from __future__ import annotations

import json
import re
from pathlib import Path


VAULT_SCHEMA_VERSION = "1.0"
NOTE_STATUSES = ("proposed", "pending_revision", "validated", "rejected", "superseded")
IMPORT_STAGING_ROOT = "99_Import_Staging"
IMPORT_STAGING_DIRS = {
    "root": IMPORT_STAGING_ROOT,
    "manifests": f"{IMPORT_STAGING_ROOT}/_manifests",
    "characters": f"{IMPORT_STAGING_ROOT}/characters",
    "lore": f"{IMPORT_STAGING_ROOT}/lore",
    "scenes": f"{IMPORT_STAGING_ROOT}/scenes",
    "chapters": f"{IMPORT_STAGING_ROOT}/chapters",
    "mixed": f"{IMPORT_STAGING_ROOT}/mixed",
}

VAULT_DIRS = {
    "project": "00_Project",
    "voice": "01_Voice",
    "world": "02_World",
    "world_lore": "02_World/Lore",
    "world_places": "02_World/Places",
    "world_magic": "02_World/Magic",
    "world_creatures": "02_World/Creatures",
    "world_factions": "02_World/Factions",
    "world_objects": "02_World/Objects",
    "world_history": "02_World/History",
    "characters": "03_Characters",
    "character_profiles": "03_Characters/Profiles",
    "story": "04_Story",
    "story_chapters": "04_Story/Chapters",
    "story_chapter_summaries": "04_Story/Chapter_Summaries",
    "outline": "04_Outline",
    "outline_scenes": "04_Outline/Scenes",
    "draft": "05_Draft",
    "chapters": "04_Story/Chapters",
    "canon": "06_Canon",
    "canon_decisions": "06_Canon/Decisions",
    "editorial": "07_Editorial",
    "editorial_briefs": "07_Editorial/Revision_Briefs",
    "editorial_reviews": "07_Editorial/Reviews",
    "editorial_reader_panel": "07_Editorial/Reader_Panel",
    "editorial_logs": "07_Editorial/Logs",
    "editorial_eval": "07_Editorial/Evaluations",
    "review_hidden": "90_Review",
    "templates": "_Templates",
    "system": "99_System",
}

ROOT_NOTES = {
    "project": "00_Project/Project.md",
    "seed": "00_Project/Seed.md",
    "mystery": "00_Project/Mystery.md",
    "voice": "01_Voice/Voice.md",
    "world": "02_World/World.md",
    "characters": "03_Characters/Characters.md",
    "outline": "04_Story/Story.md",
    "canon": "06_Canon/Canon.md",
    "manuscript": "05_Draft/Manuscript.md",
    "arc_summary": "07_Editorial/Reader_Panel/Arc_Summary.md",
    "state": "99_System/state.json",
    "results": "99_System/results.tsv",
}

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates" / "vault"


def note_frontmatter(kind: str, title: str, status: str = "proposed", **extra) -> str:
    lines = [
        "---",
        f"kind: {_yaml_scalar(kind)}",
        f"title: {_yaml_scalar(title)}",
        f"status: {_yaml_scalar(status)}",
        f"schema_version: {_yaml_scalar(VAULT_SCHEMA_VERSION)}",
    ]
    for key, value in extra.items():
        if value is None:
            continue
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip("_") or "note"


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = "" if value is None else str(value)
    if re.fullmatch(r"[A-Za-z0-9._/\-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)
