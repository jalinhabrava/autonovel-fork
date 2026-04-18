from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ENTITY_KIND_CATALOG = (
    "character",
    "scene",
    "chapter",
    "lore",
    "decision",
    "location",
    "object",
    "note",
)

MENTION_SOURCE_CATALOG = (
    "raw_text",
    "contextual_phrase",
    "narrative_signals",
    "request_hint",
)

ARTIFACT_RELATION_CATALOG = (
    "direct_profile",
    "direct_note",
    "linked_canon",
    "linked_lore",
    "linked_scene",
    "linked_chapter",
    "backlinked_context",
    "voice_context",
    "relationship_context",
)

MATCH_SOURCE_CATALOG = (
    "title",
    "slug",
    "alias",
    "known_name",
    "metadata",
)


@dataclass(frozen=True)
class EntityMention:
    surface_text: str
    normalized_text: str
    mention_kind_hint: str | None = None
    source: str = "raw_text"
    confidence: float = 0.0
    context_hint: str | None = None
    span_start: int | None = None
    span_end: int | None = None

    def __post_init__(self) -> None:
        if self.mention_kind_hint is not None:
            _ensure_catalog_value("mention_kind_hint", self.mention_kind_hint, ENTITY_KIND_CATALOG)
        _ensure_catalog_value("source", self.source, MENTION_SOURCE_CATALOG)


@dataclass(frozen=True)
class EntityCandidate:
    artifact_id: str
    artifact_type: str
    title: str | None = None
    path: str | None = None
    match_source: str = "title"
    match_reason: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        _ensure_catalog_value("artifact_type", self.artifact_type, ENTITY_KIND_CATALOG)
        _ensure_catalog_value("match_source", self.match_source, MATCH_SOURCE_CATALOG)


@dataclass(frozen=True)
class RelatedArtifactSuggestion:
    artifact_id: str
    artifact_type: str
    relation: str
    confidence: float = 0.0
    path: str | None = None

    def __post_init__(self) -> None:
        _ensure_catalog_value("artifact_type", self.artifact_type, ENTITY_KIND_CATALOG)
        _ensure_catalog_value("relation", self.relation, ARTIFACT_RELATION_CATALOG)


@dataclass(frozen=True)
class EntityResolutionResult:
    query_text: str
    mention: EntityMention
    candidate_entities: list[EntityCandidate] = field(default_factory=list)
    resolved: bool = False
    resolution_confidence: float = 0.0
    resolution_source: str | None = None
    resolved_entity_id: str | None = None
    resolved_entity_type: str | None = None
    related_artifacts_suggested: list[RelatedArtifactSuggestion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.resolved_entity_type is not None:
            _ensure_catalog_value("resolved_entity_type", self.resolved_entity_type, ENTITY_KIND_CATALOG)


@dataclass(frozen=True)
class VaultIndexEntry:
    artifact_id: str
    artifact_type: str
    title: str
    slug: str
    aliases: list[str] = field(default_factory=list)
    path: str | None = None
    links: list[str] = field(default_factory=list)
    backlinks: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_catalog_value("artifact_type", self.artifact_type, ENTITY_KIND_CATALOG)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
