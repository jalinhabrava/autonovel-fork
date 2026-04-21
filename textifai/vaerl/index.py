from __future__ import annotations

from pathlib import Path

from textifai.obsidian.artifact_types import normalize_artifact_type
from textifai.obsidian import open_obsidian_source
from textifai.vaerl.contracts import VaultIndexEntry
from vault.schema import slugify


def build_vault_index(
    *,
    vault_path: Path,
    known_characters: list[dict[str, object]] | None = None,
) -> list[VaultIndexEntry]:
    source = open_obsidian_source(vault_path)
    reader = source.reader
    entries: list[VaultIndexEntry] = []
    for note in reader.list_notes():
        note_path = str(note.vault_relative_path).replace("\\", "/")
        note_role = str((note.frontmatter or {}).get("note_role") or "").strip().casefold()
        if "99_Import_Staging/" in note_path or note_path.startswith("99_Import_Staging/"):
            continue
        if "90_Review/" in note_path or note_path.startswith("90_Review/"):
            continue
        if note_role == "review":
            continue
        normalized_artifact_type = normalize_artifact_type(
            vault_relative_path=note.vault_relative_path,
            frontmatter_kind=note.frontmatter.get("kind"),
            snapshot_artifact_type=note.artifact_type,
        )
        frontmatter = dict(note.frontmatter)
        frontmatter.setdefault("_context_source_reliability", source.status.reliability)
        frontmatter.setdefault("_context_source_kind", source.status.source_kind)
        metadata_aliases = _metadata_aliases(frontmatter)
        aliases = _dedupe_strings([*note.aliases, *metadata_aliases.get("aliases", [])])
        project_confirmed_aliases = _dedupe_strings(
            [*note.project_confirmed_aliases, *metadata_aliases.get("project_confirmed_aliases", [])]
        )
        entries.append(
            VaultIndexEntry(
                artifact_id=note.note_id,
                artifact_type=normalized_artifact_type,
                title=note.title,
                slug=note.note_id,
                aliases=aliases,
                project_confirmed_aliases=project_confirmed_aliases,
                path=note.path,
                links=list(note.outgoing_links),
                backlinks=list(note.incoming_links),
                frontmatter=frontmatter,
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


def _metadata_aliases(frontmatter: dict[str, object]) -> dict[str, list[str]]:
    aliases = _frontmatter_values(frontmatter, "aliases")
    confirmed = _frontmatter_values(frontmatter, "canonical_subject")
    return {
        "aliases": _dedupe_strings(aliases),
        "project_confirmed_aliases": _dedupe_strings(confirmed),
    }


def _frontmatter_values(frontmatter: dict[str, object], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = frontmatter.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            candidates = raw
        else:
            candidates = str(raw).split(",")
        for item in candidates:
            text = str(item).strip()
            if len(slugify(text)) < 3:
                continue
            values.append(text)
    return values


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped
