from __future__ import annotations

from pathlib import Path

from textifai.obsidian.contracts import ObsidianContextBundle
from textifai.obsidian.source import open_obsidian_source


def build_obsidian_context_bundle(
    vault_root: str | Path,
    *,
    note_id: str,
    related_limit: int = 6,
    snapshot_path: str | Path | None = None,
) -> ObsidianContextBundle:
    reader = open_obsidian_source(vault_root, snapshot_path=snapshot_path)
    primary = reader.get_note(note_id)
    if primary is None:
        return ObsidianContextBundle(primary=None, related=[])
    return ObsidianContextBundle(
        primary=primary,
        related=reader.related_notes(primary.note_id, limit=related_limit),
    )
