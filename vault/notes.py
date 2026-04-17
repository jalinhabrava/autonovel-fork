from __future__ import annotations

from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from vault.schema import NOTE_STATUSES, ROOT_NOTES, note_frontmatter, slugify


NOTE_TYPE_DIRS = {
    "character": "character_profiles",
    "lore": "world_lore",
    "scene": "outline_scenes",
    "decision": "canon_decisions",
    "chapter": "chapters",
    "revision_brief": "editorial_briefs",
    "review": "editorial_reviews",
    "reader_panel": "editorial_reader_panel",
}


NOTE_KIND_MAP = {
    "character": "character",
    "lore": "lore",
    "scene": "scene",
    "decision": "canon_decision",
    "chapter": "chapter",
    "revision_brief": "revision_brief",
    "review": "review",
    "reader_panel": "reader_panel",
}


ROOT_ARTIFACT_KINDS = {
    "project": "project",
    "seed": "seed",
    "mystery": "mystery",
    "voice": "voice",
    "world": "world",
    "characters": "characters",
    "outline": "outline",
    "canon": "canon",
    "manuscript": "manuscript",
    "arc_summary": "arc_summary",
}


def write_or_update_note(
    vault_root: str | Path,
    *,
    note_type: str,
    slug: str,
    title: str,
    body: str,
    status: str = "proposed",
    metadata: dict[str, str | int | None] | None = None,
) -> Path:
    if status not in NOTE_STATUSES:
        raise ValueError(f"Invalid note status {status!r}. Expected one of {NOTE_STATUSES}.")
    if note_type not in NOTE_TYPE_DIRS:
        raise ValueError(f"Unsupported note type: {note_type}")

    adapter = VaultProjectAdapter(vault_root)
    note_path = adapter.note_path(note_type, slugify(slug))
    note_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = note_frontmatter(
        NOTE_KIND_MAP[note_type],
        title,
        status=status,
        slug=slugify(slug),
        **(metadata or {}),
    )
    note_path.write_text(f"{frontmatter}\n\n# {title}\n\n{body.strip()}\n")
    return note_path


def write_root_artifact_note(
    vault_root: str | Path,
    *,
    artifact: str,
    title: str,
    body: str,
    status: str = "proposed",
    metadata: dict[str, str | int | None] | None = None,
) -> Path:
    if status not in NOTE_STATUSES:
        raise ValueError(f"Invalid note status {status!r}. Expected one of {NOTE_STATUSES}.")
    if artifact not in ROOT_ARTIFACT_KINDS or artifact not in ROOT_NOTES:
        raise ValueError(f"Unsupported root artifact: {artifact}")

    adapter = VaultProjectAdapter(vault_root)
    note_path = adapter.artifact_path(artifact)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = note_frontmatter(
        ROOT_ARTIFACT_KINDS[artifact],
        title,
        status=status,
        slug=slugify(artifact),
        **(metadata or {}),
    )
    note_path.write_text(f"{frontmatter}\n\n# {title}\n\n{body.strip()}\n")
    return note_path


def update_note_status(
    vault_root: str | Path,
    *,
    note_type: str,
    slug: str,
    status: str,
) -> Path:
    if status not in NOTE_STATUSES:
        raise ValueError(f"Invalid note status {status!r}. Expected one of {NOTE_STATUSES}.")
    if note_type not in NOTE_TYPE_DIRS:
        raise ValueError(f"Unsupported note type: {note_type}")

    adapter = VaultProjectAdapter(vault_root)
    note_path = adapter.note_path(note_type, slugify(slug))
    if not note_path.exists():
        raise FileNotFoundError(f"Vault note does not exist: {note_path}")

    text = note_path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"Vault note is missing frontmatter: {note_path}")

    lines = text.splitlines()
    try:
        closing = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError(f"Vault note has invalid frontmatter: {note_path}") from exc

    updated = False
    for index in range(1, closing):
        if lines[index].startswith("status:"):
            lines[index] = f"status: {status}"
            updated = True
            break
    if not updated:
        lines.insert(closing, f"status: {status}")

    note_path.write_text("\n".join(lines) + "\n")
    return note_path


def artifact_path_for(
    vault_root: str | Path,
    *,
    artifact_kind: str,
    artifact_type: str,
    entity_id: str,
) -> Path:
    adapter = VaultProjectAdapter(vault_root)
    if artifact_kind == "note":
        if artifact_type not in NOTE_TYPE_DIRS:
            raise ValueError(f"Unsupported note type: {artifact_type}")
        return adapter.note_path(artifact_type, slugify(entity_id))
    if artifact_kind == "root_artifact":
        if artifact_type not in ROOT_ARTIFACT_KINDS:
            raise ValueError(f"Unsupported root artifact type: {artifact_type}")
        return adapter.artifact_path(artifact_type)
    raise ValueError(f"Unsupported artifact kind: {artifact_kind}")


def write_artifact_payload(
    vault_root: str | Path,
    *,
    artifact_kind: str,
    artifact_type: str,
    entity_id: str,
    title: str,
    body: str,
    status: str,
    metadata: dict[str, str | int | None] | None = None,
) -> Path:
    if artifact_kind == "note":
        return write_or_update_note(
            vault_root,
            note_type=artifact_type,
            slug=entity_id,
            title=title,
            body=body,
            status=status,
            metadata=metadata,
        )
    if artifact_kind == "root_artifact":
        return write_root_artifact_note(
            vault_root,
            artifact=artifact_type,
            title=title,
            body=body,
            status=status,
            metadata=metadata,
        )
    raise ValueError(f"Unsupported artifact kind: {artifact_kind}")


def export_context(vault_root: str | Path, artifact: str) -> str:
    adapter = VaultProjectAdapter(vault_root)
    if artifact == "all":
        names = ["voice", "world", "characters", "outline", "canon"]
        parts = [f"# {name.upper()}\n\n{adapter.read_artifact(name)}" for name in names]
        return "\n\n".join(parts)
    return adapter.read_artifact(artifact)
