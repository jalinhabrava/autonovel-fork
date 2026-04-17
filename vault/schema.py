from __future__ import annotations

from pathlib import Path


VAULT_SCHEMA_VERSION = "1.0"
NOTE_STATUSES = ("proposed", "pending_revision", "validated", "rejected", "superseded")

VAULT_DIRS = {
    "project": "00_Project",
    "voice": "01_Voice",
    "world": "02_World",
    "world_lore": "02_World/Lore",
    "characters": "03_Characters",
    "character_profiles": "03_Characters/Profiles",
    "outline": "04_Outline",
    "outline_scenes": "04_Outline/Scenes",
    "draft": "05_Draft",
    "chapters": "05_Draft/Chapters",
    "canon": "06_Canon",
    "canon_decisions": "06_Canon/Decisions",
    "editorial": "07_Editorial",
    "editorial_briefs": "07_Editorial/Revision_Briefs",
    "editorial_reviews": "07_Editorial/Reviews",
    "editorial_reader_panel": "07_Editorial/Reader_Panel",
    "editorial_logs": "07_Editorial/Logs",
    "editorial_eval": "07_Editorial/Evaluations",
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
    "outline": "04_Outline/Outline.md",
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
        f"kind: {kind}",
        f"title: {title}",
        f"status: {status}",
        f"schema_version: {VAULT_SCHEMA_VERSION}",
    ]
    for key, value in extra.items():
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip("_") or "note"
