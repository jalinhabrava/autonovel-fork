from __future__ import annotations

import re

from textifai.vaerl.contracts import EntityHint, EntityMention, VaultIndexEntry
from vault.schema import slugify


def detect_mentions(
    *,
    text: str,
    index_entries: list[VaultIndexEntry],
    entity_hints: list[EntityHint | str] | None = None,
) -> list[EntityMention]:
    mentions: list[EntityMention] = []
    lowered = text.casefold()
    for entry in index_entries:
        token_fallback: EntityMention | None = None
        candidate_names = (
            [entry.title, entry.slug.replace("_", " ").replace("-", " ")]
            + list(entry.aliases)
            + list(entry.project_confirmed_aliases)
        )
        for name in candidate_names:
            normalized = name.strip()
            if len(normalized) < 3:
                continue
            if token_fallback is None:
                token_fallback = _token_level_primary_match(text=text, lowered=lowered, entry=entry, name=normalized)
            match = re.search(r"(?<!\w)" + re.escape(normalized.casefold()) + r"(?!\w)", lowered)
            if match is None:
                continue
            mentions.append(
                EntityMention(
                    surface_text=text[match.start():match.end()],
                    normalized_text=slugify(normalized),
                    mention_kind_hint=entry.artifact_type,
                    source="raw_text",
                    confidence=0.92 if normalized.casefold() == entry.title.casefold() else 0.88,
                    span_start=match.start(),
                    span_end=match.end(),
                )
            )
            break
        else:
            if token_fallback is not None:
                mentions.append(token_fallback)

    for hint in _normalize_entity_hints(entity_hints or []):
        if not hint.normalized_hint:
            continue
        mentions.append(
            EntityMention(
                surface_text=hint.hint_text,
                normalized_text=hint.normalized_hint,
                mention_kind_hint=hint.candidate_target_type,
                source="request_hint" if hint.hint_source == "conversation" else "narrative_signals",
                confidence=max(hint.confidence, 0.4),
                context_hint=hint.hint_kind,
            )
        )

    return _dedupe_mentions(mentions)


def _token_level_primary_match(*, text: str, lowered: str, entry: VaultIndexEntry, name: str) -> EntityMention | None:
    if str((entry.frontmatter or {}).get("note_role") or "").strip().casefold() != "primary":
        return None
    tokens = [token for token in re.split(r"[\s_\-]+", name.strip()) if len(token) >= 5]
    for token in tokens:
        match = re.search(r"(?<!\w)" + re.escape(token.casefold()) + r"(?!\w)", lowered)
        if match is None:
            continue
        return EntityMention(
            surface_text=text[match.start():match.end()],
            normalized_text=slugify(token),
            mention_kind_hint=entry.artifact_type,
            source="raw_text",
            confidence=0.68,
            span_start=match.start(),
            span_end=match.end(),
        )
    return None


def _dedupe_mentions(mentions: list[EntityMention]) -> list[EntityMention]:
    deduped: list[EntityMention] = []
    seen: set[tuple[str, str | None]] = set()
    for mention in mentions:
        key = (mention.normalized_text, mention.context_hint)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mention)
    return deduped


def _normalize_entity_hints(entity_hints: list[EntityHint | str]) -> list[EntityHint]:
    normalized: list[EntityHint] = []
    for item in entity_hints:
        if isinstance(item, EntityHint):
            normalized.append(item)
            continue
        hint_text = str(item).strip()
        if not hint_text:
            continue
        normalized.append(
            EntityHint(
                hint_text=hint_text,
                normalized_hint=slugify(hint_text),
                hint_kind="narrative_signal",
                hint_source="conversation",
                confidence=0.4,
            )
        )
    return normalized
