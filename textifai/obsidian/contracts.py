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


@dataclass(frozen=True)
class ObsidianContextBundle:
    primary: ObsidianNote | None
    related: list[ObsidianNote] = field(default_factory=list)

