from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote
import unicodedata

_WIKILINK_RE = re.compile(r"(?<!\\)\[\[([^\]]+?)\]\]")
_ESCAPED_WIKILINK_RE = re.compile(r"\\\[\\\[([^\n]+?)\\\]\]", re.DOTALL)
_GRAPH_LINK_RE = re.compile(r"\[([^\]]+?)\]\(#graph_select=([^\)]+)\)")


@dataclass(frozen=True)
class WikilinkResolver:
    label_to_slug: dict[str, str]
    slug_to_label: dict[str, str]

    @staticmethod
    def _normalize(value: str) -> str:
        text = " ".join(str(value or "").strip().split()).casefold()
        return unicodedata.normalize('NFKC', text)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | list[Any] | None) -> "WikilinkResolver":
        label_to_slug: dict[str, str] = {}
        slug_to_label: dict[str, str] = {}
        items: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("nodes", "entities", "primaries"):
                value = payload.get(key)
                if isinstance(value, list):
                    items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(payload, list):
            items.extend(item for item in payload if isinstance(item, dict))

        def add(label: str | None, slug: str | None) -> None:
            if not label or not slug:
                return
            label_text = str(label).strip()
            slug_text = str(slug).strip()
            if not label_text or not slug_text:
                return
            normalized = cls._normalize(label_text)
            if normalized and normalized not in label_to_slug:
                label_to_slug[normalized] = slug_text
            label_to_slug.setdefault(slug_text.casefold(), slug_text)
            slug_to_label.setdefault(slug_text, label_text)

        for item in items:
            slug = str(item.get("canonical_id") or item.get("preferred_slug") or item.get("slug") or item.get("id") or "").strip()
            label = str(item.get("display_label") or item.get("label") or item.get("canonical_label") or item.get("canonical_name") or item.get("name") or slug).strip()
            add(label, slug)
            add(item.get("label"), slug)
            add(item.get("canonical_label"), slug)
            add(item.get("canonical_name"), slug)
            add(item.get("display_name"), slug)
            for alias in item.get("aliases") or []:
                if isinstance(alias, str):
                    add(alias, slug)
            for alias in item.get("names") or []:
                if isinstance(alias, str):
                    add(alias, slug)
        return cls(label_to_slug=label_to_slug, slug_to_label=slug_to_label)

    def resolve_label(self, label: str) -> str | None:
        return self.label_to_slug.get(self._normalize(label))

    def display_label_for_slug(self, slug: str, fallback: str | None = None) -> str:
        return self.slug_to_label.get(str(slug), fallback or str(slug))


def canonicalize_wikilinks(markdown: str) -> str:
    text = str(markdown or "")
    text = text.replace(r"\[\[", "[[").replace(r"\]\]", "]]")
    return _ESCAPED_WIKILINK_RE.sub(r"[[\1]]", text)


def render_known_wikilinks(markdown: str, resolver: WikilinkResolver | dict[str, Any] | list[Any] | None = None) -> str:
    text = canonicalize_wikilinks(markdown)
    resolver_obj = resolver if isinstance(resolver, WikilinkResolver) else WikilinkResolver.from_payload(resolver)

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        slug = resolver_obj.resolve_label(label)
        if not slug:
            return match.group(0)
        return f"[{label}](#graph_select={quote(slug, safe='')})"

    return _WIKILINK_RE.sub(replace, text)


def restore_known_display_links(markdown: str, resolver: WikilinkResolver | dict[str, Any] | list[Any] | None = None) -> str:
    text = str(markdown or "")
    resolver_obj = resolver if isinstance(resolver, WikilinkResolver) else WikilinkResolver.from_payload(resolver)

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        slug = unquote(match.group(2).strip())
        return f"[[{resolver_obj.display_label_for_slug(slug, label)}]]"

    return canonicalize_wikilinks(_GRAPH_LINK_RE.sub(replace, text))


# Backwards-compatible helpers

def canonicalize_sera_wikilink(markdown: str) -> str:
    return canonicalize_wikilinks(markdown)


def render_known_sera_wikilink(markdown: str) -> str:
    return render_known_wikilinks(markdown, {"entities": [{"label": "Sera", "canonical_id": "sera"}]})


def restore_known_sera_display_link(markdown: str) -> str:
    return restore_known_display_links(markdown, {"entities": [{"label": "Sera", "canonical_id": "sera"}]})
