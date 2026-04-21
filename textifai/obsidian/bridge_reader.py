from __future__ import annotations

import ast
from pathlib import Path

from textifai.obsidian.contracts import ObsidianBridgeSnapshot, ObsidianNote, ValidatedObsidianSnapshot
from textifai.obsidian.snapshot_validation import validate_obsidian_snapshot
from vault.schema import slugify


DEFAULT_SNAPSHOT_CANDIDATES = (
    ".textifai/obsidian-bridge-snapshot.json",
    "99_System/obsidian_bridge_snapshot.json",
)


class ObsidianBridgeSnapshotReader:
    def __init__(self, snapshot_path: str | Path) -> None:
        self.snapshot_path = Path(snapshot_path).expanduser().resolve()
        self.validation = validate_obsidian_snapshot(self.snapshot_path)
        if self.validation.snapshot is None:
            raise ValueError(
                f"Invalid Obsidian bridge snapshot at {self.snapshot_path}: {', '.join(self.validation.status.issues)}"
            )
        self.snapshot = self.validation.snapshot

    def list_notes(self, *, include_system: bool = False) -> list[ObsidianNote]:
        notes = list(self.snapshot.notes)
        if include_system:
            return notes
        return [
            note
            for note in notes
            if ".obsidian/" not in note.vault_relative_path
            and not note.vault_relative_path.startswith(".obsidian")
            and "99_System/" not in note.vault_relative_path
            and not note.vault_relative_path.startswith("99_System")
        ]

    def get_note(self, note_id: str) -> ObsidianNote | None:
        normalized = slugify(note_id)
        for note in self.snapshot.notes:
            if note.note_id == normalized:
                return note
        return None

    def related_notes(self, note_id: str, *, limit: int = 6) -> list[ObsidianNote]:
        primary = self.get_note(note_id)
        if primary is None:
            return []
        by_id = {note.note_id: note for note in self.snapshot.notes}
        related_ids = [*primary.outgoing_links, *primary.incoming_links]
        related_scored: list[tuple[tuple[int, int, str], ObsidianNote]] = []
        seen: set[str] = set()
        for related_id in related_ids:
            if related_id in seen:
                continue
            candidate = by_id.get(slugify(related_id))
            if candidate is None:
                continue
            seen.add(candidate.note_id)
            related_scored.append((_related_priority(candidate), candidate))
        related_scored.sort(key=lambda item: item[0])
        return [candidate for _, candidate in related_scored[:limit]]

    @property
    def snapshot_status(self) -> ValidatedObsidianSnapshot:
        return self.validation


def resolve_obsidian_snapshot_path(
    vault_root: str | Path,
    *,
    snapshot_path: str | Path | None = None,
) -> Path | None:
    if snapshot_path is not None:
        path = Path(snapshot_path).expanduser().resolve()
        return path if path.exists() else None
    root = Path(vault_root).expanduser().resolve()
    for candidate in DEFAULT_SNAPSHOT_CANDIDATES:
        path = root / candidate
        if path.exists():
            return path
    return None


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
