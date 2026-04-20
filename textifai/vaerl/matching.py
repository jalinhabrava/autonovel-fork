from __future__ import annotations

from textifai.vaerl.contracts import EntityCandidate, EntityHint, EntityMention, VaultIndexEntry
from vault.schema import slugify


def match_candidates(
    *,
    mention: EntityMention,
    index_entries: list[VaultIndexEntry],
    entity_hints: list[EntityHint] | None = None,
) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    for entry in index_entries:
        score, match_source, match_reason, supporting_hints = _match_entry(
            mention,
            entry,
            entity_hints or [],
        )
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
                supporting_hints=supporting_hints,
            )
        )
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    return candidates[:5]


def _match_entry(
    mention: EntityMention,
    entry: VaultIndexEntry,
    entity_hints: list[EntityHint],
) -> tuple[float, str, str, list[EntityHint]]:
    normalized = mention.normalized_text
    title_norm = slugify(entry.title)
    slug_norm = slugify(entry.slug)
    alias_norms = [slugify(alias) for alias in entry.aliases]
    project_alias_norms = [slugify(alias) for alias in entry.project_confirmed_aliases]
    frontmatter = entry.frontmatter

    if mention.mention_kind_hint and mention.mention_kind_hint != entry.artifact_type:
        kind_penalty = 0.12
    else:
        kind_penalty = 0.0

    supporting_hints = _supporting_hints_for_entry(entry, normalized, entity_hints)
    hint_bonus = min(0.2, sum(hint.confidence for hint in supporting_hints) * 0.12)

    if normalized == slug_norm:
        return (
            _apply_entry_priority(max(0.94 - kind_penalty, 0.0), entry),
            "slug",
            "exact slug match",
            supporting_hints,
        )
    if normalized == title_norm:
        return (
            _apply_entry_priority(max(0.92 - kind_penalty, 0.0), entry),
            "title",
            "exact title match",
            supporting_hints,
        )
    if normalized in alias_norms:
        return (
            _apply_entry_priority(max(0.9 - kind_penalty, 0.0), entry),
            "alias",
            "exact alias match",
            supporting_hints,
        )
    if normalized in project_alias_norms:
        return (
            _apply_entry_priority(max(0.95 - kind_penalty, 0.0), entry),
            "project_confirmed_alias",
            "exact project-confirmed alias match",
            supporting_hints,
        )
    if entry.artifact_type == "character" and normalized in alias_norms + [title_norm]:
        return (
            _apply_entry_priority(max(0.93 - kind_penalty, 0.0), entry),
            "known_name",
            "known character name match",
            supporting_hints,
        )

    metadata_values = []
    for key in ("entity_id", "character_id", "artifact_id"):
        value = frontmatter.get(key)
        if value:
            metadata_values.append(slugify(str(value)))
    if normalized in metadata_values:
        return (
            _apply_entry_priority(max(0.86 - kind_penalty, 0.0), entry),
            "metadata",
            "simple metadata id match",
            supporting_hints,
        )

    title_tokens = {token for token in re_split_tokens(entry.title)}
    slug_tokens = {token for token in re_split_tokens(entry.slug)}
    alias_tokens = {token for alias in [*entry.aliases, *entry.project_confirmed_aliases] for token in re_split_tokens(alias)}
    if len(normalized) >= 5 and normalized in title_tokens | slug_tokens | alias_tokens:
        return (
            _apply_entry_priority(max(0.74 - kind_penalty + hint_bonus, 0.0), entry),
            "metadata",
            "primary title token match",
            supporting_hints,
        )

    if supporting_hints:
        return (
            _apply_entry_priority(max(0.3 - kind_penalty + hint_bonus, 0.0), entry),
            "metadata",
            "hint-supported candidate",
            supporting_hints,
        )
    return (0.0, "title", "", [])


def _apply_entry_priority(score: float, entry: VaultIndexEntry) -> float:
    frontmatter = entry.frontmatter or {}
    role = str(frontmatter.get("note_role") or "").strip().casefold()
    artifact_stage = str(frontmatter.get("artifact_stage") or "").strip().casefold()
    import_state = str(frontmatter.get("import_review_state") or "").strip().casefold()
    path = str(entry.path or "").replace("\\", "/").casefold()
    boost = 0.0
    if role == "primary":
        boost += 0.08
    elif role == "supporting":
        boost += 0.03
    if artifact_stage == "promoted_artifact":
        boost += 0.05
    elif artifact_stage == "candidate_artifact":
        boost -= 0.04
    if import_state == "promoted":
        boost += 0.03
    if "/99_import_staging/" in path:
        boost -= 0.08
    return max(0.0, min(1.0, score + boost))


def _supporting_hints_for_entry(
    entry: VaultIndexEntry,
    normalized_mention: str,
    entity_hints: list[EntityHint],
) -> list[EntityHint]:
    supporting: list[EntityHint] = []
    alias_norms = {slugify(alias) for alias in entry.aliases}
    project_alias_norms = {slugify(alias) for alias in entry.project_confirmed_aliases}
    title_norm = slugify(entry.title)
    slug_norm = slugify(entry.slug)
    for hint in entity_hints:
        candidate_target_match = bool(
            hint.candidate_target_id
            and slugify(hint.candidate_target_id) == slugify(entry.artifact_id)
            and (hint.candidate_target_type is None or hint.candidate_target_type == entry.artifact_type)
        )
        normalized_hint = slugify(hint.normalized_hint or hint.hint_text)
        if not normalized_hint:
            continue
        if normalized_hint in {title_norm, slug_norm} | alias_norms | project_alias_norms:
            supporting.append(hint)
            continue
        if candidate_target_match and (
            hint.supported_by_author_understanding
            or hint.supported_by_document_analysis
            or hint.hint_source == "project_alias"
        ):
            supporting.append(hint)
    return supporting


def re_split_tokens(value: str) -> list[str]:
    return [slugify(token) for token in str(value).replace("_", " ").replace("-", " ").split() if len(slugify(token)) >= 5]
