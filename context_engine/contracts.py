from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


NarrativeScope = Literal["project", "arc", "chapter", "scene", "fragment"]
RetrievalCategory = Literal["canon", "lore", "voice", "characters", "scenes", "chapters", "timeline", "outline"]
IntentName = Literal[
    "scene_write",
    "scene_rewrite",
    "chapter_context",
    "consistency_check",
    "canon_decision",
    "bootstrap_extract",
    "world_lookup",
    "context_search",
]
ArtifactKind = Literal["note", "root_artifact", "chapter"]
SectionName = Literal["hard_constraints", "narrative_context", "voice_context", "evidence"]
@dataclass(frozen=True)
class ContextRequest:
    intent: str
    target_id: str
    target_type: str
    narrative_scope: NarrativeScope | None = None
    retrieval_scope: tuple[RetrievalCategory, ...] = ()
    query_text: str | None = None
    chapter_refs: tuple[str, ...] = ()
    character_ids: tuple[str, ...] = ()
    policy_name: str = "default"
    token_budget: int = 4000
    interface_language: str | None = None
    user_command_language: str | None = None
    internal_system_language: str | None = None
    operation_language: str | None = None
    artifact_target_language: str | None = None
    mixed_language_allowed: bool | None = None


@dataclass(frozen=True)
class ResolvedIntent:
    name: IntentName
    narrative_scope: NarrativeScope
    retrieval_scope: tuple[RetrievalCategory, ...]
    target_type: str


@dataclass(frozen=True)
class ResolvedScope:
    narrative_scope: NarrativeScope
    retrieval_scope: tuple[RetrievalCategory, ...]
    target_id: str
    chapter_refs: tuple[str, ...] = ()
    scene_refs: tuple[str, ...] = ()
    character_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionBudgets:
    hard_constraints: int
    narrative_context: int
    voice_context: int
    evidence: int


@dataclass(frozen=True)
class ScopeRadiusConfig:
    scene_neighbors: int = 0
    chapter_neighbors: int = 0


@dataclass(frozen=True)
class ContextPolicy:
    name: str
    selection_weights: dict[str, float]
    status_priority: dict[str, float]
    section_budgets: SectionBudgets
    literality_by_artifact_type: dict[str, float]
    scope_radius: dict[str, ScopeRadiusConfig]


@dataclass(frozen=True)
class Candidate:
    id: str
    artifact_kind: ArtifactKind
    artifact_type: str
    category: RetrievalCategory
    title: str
    status: str
    content: str
    path: str
    chapter_ref: str | None = None
    character_ids: tuple[str, ...] = ()
    reason: str = ""
    source_refs: tuple[str, ...] = ()
    line_span: dict[str, int] | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    selection_weight: float
    status_weight: float
    scope_bonus: float
    query_bonus: float
    target_bonus: float
    reason: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    section: SectionName
    score: ScoreBreakdown
    literality: float


@dataclass(frozen=True)
class ContextEntry:
    id: str
    artifact_kind: ArtifactKind
    artifact_type: str
    title: str
    status: str
    reason: str
    content: str
    path: str
    score: float
    score_breakdown: dict[str, float | str]
    section_reason: str = ""
    selection_rank: int = 0
    effective_literality: float = 0.5
    content_mode_info: dict[str, float | int | str] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    line_span: dict[str, int] | None = None


@dataclass(frozen=True)
class ContextPack:
    type: Literal["context_pack"]
    intent: str
    scope: dict
    policy: dict
    hard_constraints: tuple[ContextEntry, ...]
    narrative_context: tuple[ContextEntry, ...]
    voice_context: dict[str, tuple[ContextEntry, ...]]
    evidence: tuple[ContextEntry, ...]
    meta: dict


@dataclass(frozen=True)
class ContextDebugResult:
    request: dict
    resolved_intent: dict
    resolved_scope: dict
    policy: dict
    candidates: tuple[dict, ...]
    context_pack: ContextPack
