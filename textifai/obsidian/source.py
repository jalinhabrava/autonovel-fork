from __future__ import annotations

from pathlib import Path
from typing import Protocol

from textifai.obsidian.bridge_reader import ObsidianBridgeSnapshotReader, resolve_obsidian_snapshot_path
from textifai.obsidian.reader import ObsidianVaultReader


class ObsidianContextSource(Protocol):
    def list_notes(self, *, include_system: bool = False): ...
    def get_note(self, note_id: str): ...
    def related_notes(self, note_id: str, *, limit: int = 6): ...


def open_obsidian_source(
    vault_root: str | Path,
    *,
    snapshot_path: str | Path | None = None,
) -> ObsidianContextSource:
    resolved_snapshot = resolve_obsidian_snapshot_path(vault_root, snapshot_path=snapshot_path)
    if resolved_snapshot is not None:
        return ObsidianBridgeSnapshotReader(resolved_snapshot)
    return ObsidianVaultReader(vault_root)
