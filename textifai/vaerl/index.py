from __future__ import annotations

from pathlib import Path

from textifai.obsidian import open_obsidian_source
from textifai.vaerl.contracts import VaultIndexEntry
from vault.schema import slugify


def build_vault_index(
    *,
    vault_path: Path,
    known_characters: list[dict[str, object]] | None = None,
) -> list[VaultIndexEntry]:
    reader = open_obsidian_source(vault_path)
    entries: list[VaultIndexEntry] = []
    for note in reader.list_notes():
        if note.artifact_type == "note":
            continue
        entries.append(
            VaultIndexEntry(
                artifact_id=note.note_id,
                artifact_type=note.artifact_type,
                title=note.title,
                slug=note.note_id,
                aliases=list(note.aliases),
                project_confirmed_aliases=list(note.project_confirmed_aliases),
                path=note.path,
                links=list(note.outgoing_links),
                backlinks=list(note.incoming_links),
                frontmatter=dict(note.frontmatter),
            )
        )
    entries = _merge_known_characters(entries, known_characters or [])
    return entries


def _merge_known_characters(
    entries: list[VaultIndexEntry],
    known_characters: list[dict[str, object]],
) -> list[VaultIndexEntry]:
    by_id = {entry.artifact_id: entry for entry in entries}
    for character in known_characters:
        character_id = slugify(str(character.get("id") or ""))
        if not character_id:
            continue
        names = [str(name).strip() for name in character.get("names", []) if str(name).strip()]
        if character_id in by_id:
            entry = by_id[character_id]
            aliases = sorted(set(entry.aliases + names))
            project_confirmed_aliases = sorted(set(entry.project_confirmed_aliases + names))
            by_id[character_id] = VaultIndexEntry(
                artifact_id=entry.artifact_id,
                artifact_type=entry.artifact_type,
                title=entry.title,
                slug=entry.slug,
                aliases=aliases,
                project_confirmed_aliases=project_confirmed_aliases,
                path=entry.path,
                links=entry.links,
                backlinks=entry.backlinks,
                frontmatter=entry.frontmatter,
            )
            continue
        title = names[0] if names else character_id.replace("_", " ").title()
        by_id[character_id] = VaultIndexEntry(
            artifact_id=character_id,
            artifact_type="character",
            title=title,
            slug=character_id,
            aliases=sorted(set(names)),
            project_confirmed_aliases=sorted(set(names)),
            path=None,
            links=[],
            backlinks=[],
            frontmatter={"synthetic": True},
        )
    return list(by_id.values())
