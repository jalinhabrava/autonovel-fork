from __future__ import annotations

from pathlib import Path
import ast
import re

from adapters.vault_adapter import VaultProjectAdapter
from interactive.query import parse_frontmatter
from textifai.vaerl.contracts import VaultIndexEntry
from vault.schema import slugify


def build_vault_index(
    *,
    vault_path: Path,
    known_characters: list[dict[str, object]] | None = None,
) -> list[VaultIndexEntry]:
    adapter = VaultProjectAdapter(vault_path)
    entries: list[VaultIndexEntry] = []
    catalog = (
        ("character", adapter.character_profiles_dir),
        ("scene", adapter.outline_scenes_dir),
        ("chapter", adapter.chapters_dir),
        ("lore", adapter.world_lore_dir),
        ("decision", adapter.canon_decisions_dir),
    )
    for artifact_type, directory in catalog:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text()
            frontmatter = parse_frontmatter(text)
            title = str(frontmatter.get("title") or path.stem.replace("_", " ").replace("-", " ").title()).strip()
            slug = slugify(str(frontmatter.get("slug") or path.stem))
            aliases = _normalize_aliases(frontmatter.get("aliases"))
            project_confirmed_aliases = _normalize_aliases(frontmatter.get("project_confirmed_aliases"))
            links = _extract_links(text)
            entries.append(
                VaultIndexEntry(
                    artifact_id=slug,
                    artifact_type=artifact_type,
                    title=title,
                    slug=slug,
                    aliases=aliases,
                    project_confirmed_aliases=project_confirmed_aliases,
                    path=str(path),
                    links=links,
                    backlinks=[],
                    frontmatter=dict(frontmatter),
                )
            )
    entries = _merge_known_characters(entries, known_characters or [])
    backlinks = _compute_backlinks(entries)
    return [
        VaultIndexEntry(
            artifact_id=entry.artifact_id,
            artifact_type=entry.artifact_type,
            title=entry.title,
            slug=entry.slug,
            aliases=entry.aliases,
            project_confirmed_aliases=entry.project_confirmed_aliases,
            path=entry.path,
            links=entry.links,
            backlinks=backlinks.get(entry.artifact_id, []),
            frontmatter=entry.frontmatter,
        )
        for entry in entries
    ]


def _normalize_aliases(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [stripped] if stripped else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _extract_links(text: str) -> list[str]:
    links = re.findall(r"\[\[([^\]|#]+)", text)
    return [slugify(link) for link in links if link.strip()]


def _compute_backlinks(entries: list[VaultIndexEntry]) -> dict[str, list[str]]:
    backlinks: dict[str, list[str]] = {entry.artifact_id: [] for entry in entries}
    for entry in entries:
        for linked in entry.links:
            if linked in backlinks:
                backlinks[linked].append(entry.artifact_id)
    return {key: sorted(set(value)) for key, value in backlinks.items()}


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
