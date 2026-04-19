from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    resolved_links: dict[str, int] = field(default_factory=dict)
    unresolved_links: dict[str, int] = field(default_factory=dict)
    source_kind: str = "vault_markdown"


@dataclass(frozen=True)
class ObsidianContextBundle:
    primary: ObsidianNote | None
    related: list[ObsidianNote] = field(default_factory=list)


@dataclass(frozen=True)
class ObsidianBridgeSnapshot:
    schema_version: str
    source: str
    generated_at: str | None
    vault_name: str | None
    plugin_version: str | None
    obsidian_app_version: str | None
    export_reason: str | None
    notes: list[ObsidianNote] = field(default_factory=list)
