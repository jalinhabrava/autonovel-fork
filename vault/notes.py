from __future__ import annotations

from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from textifai.obsidian.taxonomy import taxonomy_tags
from vault.schema import NOTE_STATUSES, ROOT_NOTES, note_frontmatter, slugify


NOTE_TYPE_DIRS = {
    "character": "character_profiles",
    "concept": "world_concepts",
    "place": "world_places",
    "creature": "world_creatures",
    "faction": "world_factions",
    "object": "world_objects",
    "event": "world_events",
    "scene": "outline_scenes",
    "decision": "canon_decisions",
    "chapter": "chapters",
    "chapter_summary": "story_chapter_summaries",
    "revision_brief": "editorial_briefs",
    "review": "review_hidden",
    "reader_panel": "editorial_reader_panel",
}


NOTE_KIND_MAP = {
    "character": "character",
    "concept": "concept",
    "place": "place",
    "creature": "creature",
    "faction": "faction",
    "object": "object",
    "event": "event",
    "scene": "scene",
    "decision": "canon_decision",
    "chapter": "chapter",
    "chapter_summary": "chapter_summary",
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
    note_type = normalize_note_type(note_type)
    if status not in NOTE_STATUSES:
        raise ValueError(f"Invalid note status {status!r}. Expected one of {NOTE_STATUSES}.")
    if note_type not in NOTE_TYPE_DIRS:
        raise ValueError(f"Unsupported note type: {note_type}")

    adapter = VaultProjectAdapter(vault_root)
    note_path = adapter.note_path(note_type, slugify(slug))
    note_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = _merge_note_metadata(note_type=note_type, metadata=metadata)
    frontmatter = note_frontmatter(
        NOTE_KIND_MAP[note_type],
        title,
        status=status,
        slug=slugify(slug),
        **metadata,
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
    metadata = _merge_root_metadata(artifact=artifact, metadata=metadata)
    frontmatter = note_frontmatter(
        ROOT_ARTIFACT_KINDS[artifact],
        title,
        status=status,
        slug=slugify(artifact),
        **metadata,
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
    note_type = normalize_note_type(note_type)
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
        artifact_type = normalize_note_type(artifact_type)
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
        artifact_type = normalize_note_type(artifact_type)
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


def _merge_note_metadata(
    *,
    note_type: str,
    metadata: dict[str, str | int | None] | None,
) -> dict[str, str | int | list[str]]:
    note_type = normalize_note_type(note_type)
    merged: dict[str, str | int | list[str]] = dict(metadata or {})
    role = str(merged.get("note_role") or "").strip().casefold()
    tags = _coerce_tags(merged.get("tags"))

    if note_type in {"chapter", "chapter_summary"} or role in {"chapter", "chapter_summary"}:
        tags.extend(["#chapters"])
        merged.setdefault("graph_exclude", True)
        merged.setdefault("retrieval_exclude", True)
    elif note_type == "review" or role in {"review", "supporting"}:
        tags.extend(["#review"])
        merged.setdefault("graph_exclude", True)
        merged.setdefault("retrieval_exclude", True)
    else:
        merged.setdefault("graph_exclude", False)
        merged.setdefault("retrieval_exclude", False)

    if role == "primary":
        tags.extend(["#primary"])
    if note_type in {"character", "concept", "place", "faction", "object", "creature", "event"}:
        subkind = str(merged.get("entity_subkind") or "").strip().casefold() or None
        tags.extend(taxonomy_tags(note_role="primary" if role == "primary" else "review" if role == "review" else "system", entity_kind=note_type, entity_subkind=subkind)[1:] if role in {"primary", "review"} else [f"#{note_type}"])
        if subkind:
            tags.append(f"#{subkind}")
    merged["tags"] = _dedupe_tags(tags)
    return merged


def _merge_root_metadata(
    *,
    artifact: str,
    metadata: dict[str, str | int | None] | None,
) -> dict[str, str | int | list[str]]:
    merged: dict[str, str | int | list[str]] = dict(metadata or {})
    tags = _coerce_tags(merged.get("tags"))
    if artifact in {"state", "results"}:
        tags.extend(["#system"])
        merged.setdefault("graph_exclude", True)
        merged.setdefault("retrieval_exclude", True)
    merged["tags"] = _dedupe_tags(tags)
    return merged


def _coerce_tags(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw).split(",")
    return [value.strip() for value in values if str(value).strip()]


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        normalized = tag.strip()
        if not normalized:
            continue
        if not normalized.startswith("#"):
            normalized = f"#{normalized}"
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def normalize_note_type(note_type: str) -> str:
    normalized = str(note_type or "").strip().casefold()
    return {
        "lore": "concept",
        "magic": "concept",
        "history": "event",
        "location": "place",
    }.get(normalized, normalized)
