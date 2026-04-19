from __future__ import annotations

from pathlib import Path
from typing import Protocol

from textifai.obsidian.contracts import OpenedObsidianSource, ObsidianSourceStatus
from textifai.obsidian.bridge_reader import ObsidianBridgeSnapshotReader, resolve_obsidian_snapshot_path
from textifai.obsidian.reader import ObsidianVaultReader
from textifai.obsidian.snapshot_validation import validate_obsidian_snapshot


class ObsidianContextSource(Protocol):
    def list_notes(self, *, include_system: bool = False): ...
    def get_note(self, note_id: str): ...
    def related_notes(self, note_id: str, *, limit: int = 6): ...


def open_obsidian_source(
    vault_root: str | Path,
    *,
    snapshot_path: str | Path | None = None,
) -> OpenedObsidianSource:
    resolved_snapshot = resolve_obsidian_snapshot_path(vault_root, snapshot_path=snapshot_path)
    if resolved_snapshot is not None:
        validation = validate_obsidian_snapshot(resolved_snapshot)
        if validation.snapshot is not None:
            return OpenedObsidianSource(
                reader=ObsidianBridgeSnapshotReader(resolved_snapshot),
                status=validation.status,
            )
        return OpenedObsidianSource(
            reader=ObsidianVaultReader(vault_root),
            status=ObsidianSourceStatus(
                reliability="vault_reader_only",
                source_kind="vault_markdown",
                snapshot_path=str(resolved_snapshot),
                bridge_preferred=True,
                fallback_used=True,
                fallback_reason="invalid_snapshot_fallback_to_vault_reader",
                requires_caution=True,
                issues=list(validation.status.issues),
            ),
        )
    return OpenedObsidianSource(
        reader=ObsidianVaultReader(vault_root),
        status=ObsidianSourceStatus(
            reliability="vault_reader_only",
            source_kind="vault_markdown",
            bridge_preferred=False,
            fallback_used=False,
            fallback_reason="bridge_snapshot_absent",
            requires_caution=True,
            issues=["bridge_snapshot_absent"],
        ),
    )
