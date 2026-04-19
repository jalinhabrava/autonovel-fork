from __future__ import annotations

import json
from pathlib import Path

from vault.schema import IMPORT_STAGING_DIRS, ROOT_NOTES, TEMPLATE_ROOT, VAULT_DIRS
from vault.templates import render_template


def bootstrap_vault(
    destination: str | Path,
    title: str = "Untitled Novel Project",
    force: bool = False,
    allow_existing_content: bool = False,
) -> Path:
    root = Path(destination)
    if root.exists() and any(root.iterdir()) and not force and not allow_existing_content:
        raise FileExistsError(f"Vault destination is not empty: {root}")

    root.mkdir(parents=True, exist_ok=True)
    (root / ".obsidian").mkdir(exist_ok=True)

    for relative_dir in VAULT_DIRS.values():
        (root / relative_dir).mkdir(parents=True, exist_ok=True)
    for relative_dir in IMPORT_STAGING_DIRS.values():
        (root / relative_dir).mkdir(parents=True, exist_ok=True)

    template_files = {
        ROOT_NOTES["project"]: "project.md",
        ROOT_NOTES["seed"]: "seed.md",
        ROOT_NOTES["mystery"]: "mystery.md",
        ROOT_NOTES["voice"]: "voice.md",
        ROOT_NOTES["world"]: "world.md",
        ROOT_NOTES["characters"]: "characters.md",
        ROOT_NOTES["outline"]: "outline.md",
        ROOT_NOTES["canon"]: "canon.md",
        ROOT_NOTES["manuscript"]: "manuscript.md",
        ROOT_NOTES["arc_summary"]: "arc_summary.md",
        "_Templates/character.md": "_template_character.md",
        "_Templates/lore.md": "_template_lore.md",
        "_Templates/scene.md": "_template_scene.md",
        "_Templates/decision.md": "_template_decision.md",
        "_Templates/chapter.md": "_template_chapter.md",
        "_Templates/revision_brief.md": "_template_revision_brief.md",
    }

    for output_path, template_name in template_files.items():
        path = root / output_path
        if force or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_template(template_name, project_title=title))

    state_path = root / ROOT_NOTES["state"]
    if force or not state_path.exists():
        state_path.write_text(
            json.dumps(
                {
                    "phase": "foundation",
                    "current_focus": "planning",
                    "iteration": 0,
                    "foundation_score": 0.0,
                    "lore_score": 0.0,
                    "chapters_drafted": 0,
                    "chapters_total": 0,
                    "novel_score": 0.0,
                    "revision_cycle": 0,
                    "debts": [],
                },
                indent=2,
            )
        )

    results_path = root / ROOT_NOTES["results"]
    if force or not results_path.exists():
        results_path.write_text("commit\tphase\tscore\tword_count\tstatus\tdescription\n")

    return root


def validate_vault(destination: str | Path) -> list[str]:
    root = Path(destination)
    errors: list[str] = []

    if not root.exists():
        return [f"Vault root does not exist: {root}"]

    for relative_dir in VAULT_DIRS.values():
        path = root / relative_dir
        if not path.exists() or not path.is_dir():
            errors.append(f"Missing directory: {relative_dir}")

    for artifact_name, relative_path in ROOT_NOTES.items():
        path = root / relative_path
        if not path.exists():
            errors.append(f"Missing root artifact: {artifact_name} -> {relative_path}")

    return errors


def create_import_staging_structure(destination: str | Path) -> Path:
    root = Path(destination)
    for relative_dir in IMPORT_STAGING_DIRS.values():
        (root / relative_dir).mkdir(parents=True, exist_ok=True)
    return root / IMPORT_STAGING_DIRS["root"]
