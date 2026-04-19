from textifai.vaerl.contracts import (
    ARTIFACT_RELATION_CATALOG,
    ENTITY_KIND_CATALOG,
    ENTITY_HINT_KIND_CATALOG,
    ENTITY_HINT_SOURCE_CATALOG,
    MATCH_SOURCE_CATALOG,
    MENTION_SOURCE_CATALOG,
    EntityCandidate,
    EntityHint,
    EntityMention,
    EntityResolutionResult,
    RelatedArtifactSuggestion,
    VaultIndexEntry,
)
from textifai.vaerl.detection import detect_mentions
from textifai.vaerl.index import build_vault_index
from textifai.vaerl.matching import match_candidates
from textifai.vaerl.related import suggest_related_artifacts
from textifai.vaerl.resolver import resolve_text_against_vault

__all__ = [
    "ARTIFACT_RELATION_CATALOG",
    "ENTITY_KIND_CATALOG",
    "ENTITY_HINT_KIND_CATALOG",
    "ENTITY_HINT_SOURCE_CATALOG",
    "MATCH_SOURCE_CATALOG",
    "MENTION_SOURCE_CATALOG",
    "EntityCandidate",
    "EntityHint",
    "EntityMention",
    "EntityResolutionResult",
    "RelatedArtifactSuggestion",
    "VaultIndexEntry",
    "detect_mentions",
    "build_vault_index",
    "match_candidates",
    "suggest_related_artifacts",
    "resolve_text_against_vault",
]
