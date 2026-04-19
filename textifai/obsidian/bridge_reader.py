from __future__ import annotations

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
        return [note for note in notes if ".obsidian/" not in note.vault_relative_path and not note.vault_relative_path.startswith(".obsidian")]

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
        related: list[ObsidianNote] = []
        seen: set[str] = set()
        for related_id in related_ids:
            if related_id in seen:
                continue
            candidate = by_id.get(slugify(related_id))
            if candidate is None:
                continue
            seen.add(candidate.note_id)
            related.append(candidate)
            if len(related) >= limit:
                break
        return related

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
