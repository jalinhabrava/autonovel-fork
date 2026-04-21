from __future__ import annotations

import ast
from pathlib import Path

from textifai.obsidian.artifact_types import normalize_artifact_type
from textifai.obsidian.contracts import ObsidianNote
from textifai.obsidian.parser import (
    extract_heading_title,
    extract_obsidian_links,
    normalize_aliases,
    parse_obsidian_frontmatter,
    strip_obsidian_frontmatter,
)
from vault.schema import slugify


class ObsidianVaultReader:
    def __init__(self, vault_root: str | Path) -> None:
        self.vault_root = Path(vault_root).expanduser().resolve()

    def list_notes(self, *, include_system: bool = False) -> list[ObsidianNote]:
        raw_notes: list[ObsidianNote] = []
        for path in sorted(self.vault_root.rglob("*.md")):
            if not include_system and self._skip_path(path):
                continue
            raw_notes.append(self._read_note(path))
        incoming = _compute_incoming_links(raw_notes)
        return [
            ObsidianNote(
                note_id=note.note_id,
                title=note.title,
                path=note.path,
                vault_relative_path=note.vault_relative_path,
                artifact_type=note.artifact_type,
                frontmatter=note.frontmatter,
                aliases=note.aliases,
                project_confirmed_aliases=note.project_confirmed_aliases,
                outgoing_links=note.outgoing_links,
                incoming_links=incoming.get(note.note_id, []),
                raw_text=note.raw_text,
                body_text=note.body_text,
            )
            for note in raw_notes
        ]

    def get_note(self, note_id: str) -> ObsidianNote | None:
        for note in self.list_notes():
            if note.note_id == slugify(note_id):
                return note
        return None

    def related_notes(self, note_id: str, *, limit: int = 6) -> list[ObsidianNote]:
        primary = self.get_note(note_id)
        if primary is None:
            return []
        all_notes = {note.note_id: note for note in self.list_notes()}
        related_ids = [*primary.outgoing_links, *primary.incoming_links]
        related_scored: list[tuple[tuple[int, int, str], ObsidianNote]] = []
        seen: set[str] = set()
        for related_id in related_ids:
            if related_id in seen:
                continue
            candidate = all_notes.get(related_id)
            if candidate is None:
                continue
            seen.add(related_id)
            related_scored.append((_related_priority(candidate), candidate))
        related_scored.sort(key=lambda item: item[0])
        return [candidate for _, candidate in related_scored[:limit]]

    def _read_note(self, path: Path) -> ObsidianNote:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_obsidian_frontmatter(text)
        body = strip_obsidian_frontmatter(text)
        relative = path.relative_to(self.vault_root)
        note_id = slugify(str(frontmatter.get("slug") or relative.with_suffix("").as_posix()))
        title = str(
            frontmatter.get("title")
            or extract_heading_title(body)
            or path.stem.replace("_", " ").replace("-", " ").title()
        ).strip()
        return ObsidianNote(
            note_id=note_id,
            title=title,
            path=str(path),
            vault_relative_path=str(relative),
            artifact_type=normalize_artifact_type(
                vault_relative_path=relative,
                frontmatter_kind=frontmatter.get("kind"),
            ),
            frontmatter=dict(frontmatter),
            aliases=normalize_aliases(frontmatter.get("aliases")),
            project_confirmed_aliases=normalize_aliases(frontmatter.get("project_confirmed_aliases")),
            outgoing_links=extract_obsidian_links(text),
            incoming_links=[],
            raw_text=text,
            body_text=body,
            source_kind="vault_markdown",
        )

    def _skip_path(self, path: Path) -> bool:
        parts = set(path.relative_to(self.vault_root).parts)
        return ".obsidian" in parts or path.name.startswith(".") or "99_System" in parts
def _compute_incoming_links(notes: list[ObsidianNote]) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {note.note_id: [] for note in notes}
    for note in notes:
        for linked in note.outgoing_links:
            if linked in incoming:
                incoming[linked].append(note.note_id)
    return {key: sorted(set(value)) for key, value in incoming.items()}


def _related_priority(note: ObsidianNote) -> tuple[int, int, str]:
    role = str(note.frontmatter.get("note_role") or "").strip().casefold()
    stage = str(note.frontmatter.get("artifact_stage") or "").strip().casefold()
    tags = {
        str(tag).strip().casefold()
        for tag in _normalize_tags(note.frontmatter.get("tags"))
        if str(tag).strip()
    }
    path = note.vault_relative_path.replace("\\", "/").casefold()
    if role == "primary":
        role_rank = 0
    elif role == "chapter_summary" or note.artifact_type == "chapter_summary":
        role_rank = 1
    elif role == "chapter" or note.artifact_type == "chapter":
        role_rank = 2
    elif role in {"review", "supporting"} or "/90_review/" in path or tags & {"#review", "#system"}:
        role_rank = 6
    elif note.artifact_type == "chapter_summary":
        role_rank = 1
    elif note.artifact_type == "chapter":
        role_rank = 2
    elif "/99_import_staging/" in path:
        role_rank = 7
    else:
        role_rank = 4
    stage_rank = 0 if stage == "promoted_artifact" else 1
    return (role_rank, stage_rank, note.title.casefold())


def _normalize_tags(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        values = raw
    else:
        text = str(raw).strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
            values = parsed if isinstance(parsed, list) else [text]
        elif "," in text:
            values = text.split(",")
        else:
            values = [text]
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        while len(text) >= 2 and (
            (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'"))
        ):
            text = text[1:-1].strip()
        if text:
            normalized.append(text)
    return normalized
