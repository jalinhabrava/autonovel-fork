from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION = "2.0"
SUPPORTED_OBSIDIAN_SNAPSHOT_SCHEMA_VERSIONS = ("1.0", "2.0")
DEFAULT_SNAPSHOT_STALE_AFTER_SECONDS = 60 * 30


@dataclass(frozen=True)
class ObsidianNote:
    note_id: str
    title: str
    path: str
    vault_relative_path: str
    artifact_type: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    project_confirmed_aliases: list[str] = field(default_factory=list)
    outgoing_links: list[str] = field(default_factory=list)
    incoming_links: list[str] = field(default_factory=list)
    raw_text: str = ""
    body_text: str = ""
    tags: list[str] = field(default_factory=list)
    headings: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    wikilinks: list[dict[str, Any]] = field(default_factory=list)
    embeds: list[dict[str, Any]] = field(default_factory=list)
    frontmatter_links: list[dict[str, Any]] = field(default_factory=list)
    resolved_links: dict[str, int] = field(default_factory=dict)
    unresolved_links: dict[str, int] = field(default_factory=dict)
    source_kind: str = "vault_markdown"


@dataclass(frozen=True)
class ObsidianContextBundle:
    primary: ObsidianNote | None
    related: list[ObsidianNote] = field(default_factory=list)
    source_status: "ObsidianSourceStatus | None" = None


@dataclass(frozen=True)
class ObsidianBridgeSnapshot:
    schema_version: str
    source: str
    generated_at: str | None
    vault_name: str | None
    plugin_version: str | None
    obsidian_app_version: str | None
    export_reason: str | None
    export_complete: bool = False
    note_count: int = 0
    vault_id: str | None = None
    installation_id: str | None = None
    vault_root_hint: str | None = None
    generated_unix_ms: int | None = None
    export_sequence: int | None = None
    bridge_capabilities: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[ObsidianNote] = field(default_factory=list)


@dataclass(frozen=True)
class ObsidianSourceStatus:
    reliability: str
    source_kind: str
    snapshot_path: str | None = None
    schema_version: str | None = None
    generated_at: str | None = None
    snapshot_age_seconds: float | None = None
    bridge_preferred: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    requires_caution: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidatedObsidianSnapshot:
    snapshot: ObsidianBridgeSnapshot | None
    status: ObsidianSourceStatus


@dataclass(frozen=True)
class OpenedObsidianSource:
    reader: Any
    status: ObsidianSourceStatus
