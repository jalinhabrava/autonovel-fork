from __future__ import annotations

import re

from textifai.vaerl.contracts import EntityMention, VaultIndexEntry
from vault.schema import slugify


GENERIC_CONTEXT_PATTERNS = (
    (r"\besta nota\b", "note", "esta nota"),
    (r"\besta escena\b", "scene", "esta escena"),
    (r"\beste capítulo\b|\beste capitulo\b", "chapter", "este capítulo"),
    (r"\blo del ([^,.!?;]+)", None, "lo del"),
    (r"\bel ([^,.!?;]+)", None, "el"),
    (r"\bla ([^,.!?;]+)", None, "la"),
)


def detect_mentions(
    *,
    text: str,
    index_entries: list[VaultIndexEntry],
    entity_hints: list[str] | None = None,
) -> list[EntityMention]:
    mentions: list[EntityMention] = []
    lowered = text.casefold()
    for entry in index_entries:
        candidate_names = [entry.title, entry.slug.replace("_", " ").replace("-", " ")] + list(entry.aliases)
        for name in candidate_names:
            normalized = name.strip()
            if len(normalized) < 3:
                continue
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

    for pattern, kind_hint, context_hint in GENERIC_CONTEXT_PATTERNS:
        for match in re.finditer(pattern, lowered):
            raw_value = text[match.start():match.end()]
            mention_text = raw_value
            if "(" in raw_value:
                mention_text = raw_value.split("(", 1)[0].strip()
            mentions.append(
                EntityMention(
                    surface_text=mention_text,
                    normalized_text=slugify(_normalize_generic_match(match, raw_value)),
                    mention_kind_hint=kind_hint,
                    source="contextual_phrase",
                    confidence=0.45 if kind_hint is None else 0.58,
                    context_hint=context_hint,
                    span_start=match.start(),
                    span_end=match.end(),
                )
            )

    for hint in entity_hints or []:
        normalized_hint = slugify(hint)
        if not normalized_hint:
            continue
        mentions.append(
            EntityMention(
                surface_text=hint,
                normalized_text=normalized_hint,
                source="narrative_signals",
                confidence=0.4,
                context_hint="narrative_signal_hint",
            )
        )

    return _dedupe_mentions(mentions)


def _normalize_generic_match(match: re.Match[str], raw_value: str) -> str:
    if match.lastindex:
        captured = match.group(match.lastindex) or ""
        if captured.strip():
            return captured.strip()
    return raw_value.strip()


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
