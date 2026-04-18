from __future__ import annotations

from textifai.vaerl.contracts import EntityCandidate, EntityMention, VaultIndexEntry
from vault.schema import slugify


def match_candidates(
    *,
    mention: EntityMention,
    index_entries: list[VaultIndexEntry],
) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    for entry in index_entries:
        score, match_source, match_reason = _match_entry(mention, entry)
        if score <= 0.0:
            continue
        candidates.append(
            EntityCandidate(
                artifact_id=entry.artifact_id,
                artifact_type=entry.artifact_type,
                title=entry.title,
                path=entry.path,
                match_source=match_source,
                match_reason=match_reason,
                confidence=score,
            )
        )
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    return candidates[:5]


def _match_entry(mention: EntityMention, entry: VaultIndexEntry) -> tuple[float, str, str]:
    normalized = mention.normalized_text
    title_norm = slugify(entry.title)
    slug_norm = slugify(entry.slug)
    alias_norms = [slugify(alias) for alias in entry.aliases]
    frontmatter = entry.frontmatter

    if mention.mention_kind_hint and mention.mention_kind_hint != entry.artifact_type:
        kind_penalty = 0.12
    else:
        kind_penalty = 0.0

    if normalized == slug_norm:
        return (max(0.94 - kind_penalty, 0.0), "slug", "exact slug match")
    if normalized == title_norm:
        return (max(0.92 - kind_penalty, 0.0), "title", "exact title match")
    if normalized in alias_norms:
        return (max(0.9 - kind_penalty, 0.0), "alias", "exact alias match")
    if entry.artifact_type == "character" and normalized in alias_norms + [title_norm]:
        return (max(0.93 - kind_penalty, 0.0), "known_name", "known character name match")

    metadata_values = []
    for key in ("entity_id", "character_id", "artifact_id"):
        value = frontmatter.get(key)
        if value:
            metadata_values.append(slugify(str(value)))
    if normalized in metadata_values:
        return (max(0.86 - kind_penalty, 0.0), "metadata", "simple metadata id match")

    if mention.context_hint == "esta nota" and entry.artifact_type in {"lore", "decision"}:
        return (max(0.42 - kind_penalty, 0.0), "metadata", "generic note context hint")
    if mention.context_hint == "esta escena" and entry.artifact_type == "scene":
        return (max(0.45 - kind_penalty, 0.0), "metadata", "generic scene context hint")
    if mention.context_hint == "este capítulo" and entry.artifact_type == "chapter":
        return (max(0.45 - kind_penalty, 0.0), "metadata", "generic chapter context hint")
    return (0.0, "title", "")
