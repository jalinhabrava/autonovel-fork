from __future__ import annotations

import json
from pathlib import Path

from textifai.obsidian.contracts import ObsidianBridgeSnapshot, ObsidianNote
from vault.schema import slugify


DEFAULT_SNAPSHOT_CANDIDATES = (
    ".textifai/obsidian-bridge-snapshot.json",
    "99_System/obsidian_bridge_snapshot.json",
)


class ObsidianBridgeSnapshotReader:
    def __init__(self, snapshot_path: str | Path) -> None:
        self.snapshot_path = Path(snapshot_path).expanduser().resolve()
        self.snapshot = self._load_snapshot()

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

    def _load_snapshot(self) -> ObsidianBridgeSnapshot:
        payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        notes = [_note_from_snapshot(item) for item in payload.get("notes", []) if isinstance(item, dict)]
        return ObsidianBridgeSnapshot(
            schema_version=str(payload.get("schema_version") or "1.0"),
            source=str(payload.get("source") or "obsidian_bridge_snapshot"),
            generated_at=payload.get("generated_at"),
            vault_name=payload.get("vault_name"),
            plugin_version=payload.get("plugin_version"),
            obsidian_app_version=payload.get("obsidian_app_version"),
            export_reason=payload.get("export_reason"),
            notes=notes,
        )


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


def _note_from_snapshot(value: dict) -> ObsidianNote:
    relative_path = str(value.get("vault_relative_path") or value.get("path") or "")
    title = str(value.get("title") or Path(relative_path).stem or "Note").strip()
    note_id = slugify(str(value.get("note_id") or value.get("slug") or Path(relative_path).with_suffix("").as_posix()))
    return ObsidianNote(
        note_id=note_id,
        title=title,
        path=str(value.get("path") or relative_path),
        vault_relative_path=relative_path,
        artifact_type=str(value.get("artifact_type") or "note"),
        frontmatter=dict(value.get("frontmatter") or {}),
        aliases=[str(item).strip() for item in value.get("aliases", []) if str(item).strip()],
        project_confirmed_aliases=[str(item).strip() for item in value.get("project_confirmed_aliases", []) if str(item).strip()],
        outgoing_links=[slugify(str(item)) for item in value.get("outgoing_links", []) if str(item).strip()],
        incoming_links=[slugify(str(item)) for item in value.get("incoming_links", []) if str(item).strip()],
        raw_text=str(value.get("raw_text") or ""),
        body_text=str(value.get("body_text") or ""),
        tags=[str(item).strip() for item in value.get("tags", []) if str(item).strip()],
        headings=[dict(item) for item in value.get("headings", []) if isinstance(item, dict)],
        resolved_links={slugify(str(key)): int(count) for key, count in (value.get("resolved_links") or {}).items()},
        unresolved_links={str(key): int(count) for key, count in (value.get("unresolved_links") or {}).items()},
        source_kind="obsidian_bridge_snapshot",
    )
