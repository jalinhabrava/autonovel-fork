from __future__ import annotations

from typing import Any


PRIMARY_ENTITY_KINDS = (
    "character",
    "place",
    "faction",
    "concept",
    "object",
    "creature",
    "event",
)

ENTITY_SUBKINDS: dict[str, tuple[str, ...]] = {
    "character": ("protagonist", "supporting", "antagonist", "mentor", "nobility"),
    "place": ("local", "structural", "geopolitical"),
    "faction": ("state", "house", "order", "guild", "military", "religious", "informal"),
    "concept": ("system", "phenomenon", "role", "title", "doctrine", "law", "ritual"),
    "object": ("artifact", "weapon", "symbol", "document", "device"),
    "creature": ("species", "individual_nonhuman", "beast", "spirit"),
    "event": ("historical", "war", "disaster", "ritual_event", "political", "foundational"),
}

PRIMARY_DIRS = {
    "character": "03_Characters/Profiles",
    "place": "02_World/Places",
    "faction": "02_World/Factions",
    "concept": "02_World/Concepts",
    "object": "02_World/Objects",
    "creature": "02_World/Creatures",
    "event": "02_World/Events",
}

LEGACY_KIND_MAP = {
    "magic": ("concept", "system"),
    "lore": ("concept", None),
    "history": ("event", "historical"),
}


def normalize_taxonomy(
    *,
    entity_kind: str | None,
    entity_subkind: str | None = None,
    canonical_name: str | None = None,
    chapter_refs: list[str] | None = None,
    title_hit_count: int = 0,
) -> tuple[str, str | None]:
    kind = str(entity_kind or "").strip().casefold()
    subkind = _clean_subkind(entity_subkind)

    if kind in LEGACY_KIND_MAP:
        mapped_kind, mapped_subkind = LEGACY_KIND_MAP[kind]
        kind = mapped_kind
        subkind = subkind or mapped_subkind

    if kind not in PRIMARY_ENTITY_KINDS:
        kind = "concept"

    if subkind not in ENTITY_SUBKINDS.get(kind, ()):
        subkind = infer_entity_subkind(
            entity_kind=kind,
            canonical_name=canonical_name,
            chapter_refs=chapter_refs or [],
            title_hit_count=title_hit_count,
        )
    return kind, subkind


def infer_entity_subkind(
    *,
    entity_kind: str,
    canonical_name: str | None = None,
    chapter_refs: list[str] | None = None,
    title_hit_count: int = 0,
) -> str | None:
    refs = chapter_refs or []
    name = str(canonical_name or "").strip()
    lower_name = name.casefold()

    if entity_kind == "character":
        if title_hit_count >= 2 or len(refs) >= 4:
            return "protagonist"
        if any(token in lower_name for token in ("reina", "rey", "princesa", "príncipe", "regente", "lord", "lady")):
            return "nobility"
        return None
    if entity_kind == "place":
        if any(token in lower_name for token in ("reino", "kingdom", "imperio", "territorio")):
            return "geopolitical"
        if any(token in lower_name for token in ("castillo", "torre", "templo", "casa", "fortaleza")):
            return "structural"
        return "local" if refs else None
    if entity_kind == "faction":
        if any(token in lower_name for token in ("reino", "kingdom", "imperio", "corona")):
            return "state"
        if any(token in lower_name for token in ("orden", "order")):
            return "order"
        if any(token in lower_name for token in ("casa", "house")):
            return "house"
        return None
    if entity_kind == "concept":
        if any(token in lower_name for token in ("magia", "mana", "maná", "sistema", "vinculo", "vínculo")):
            return "system"
        if any(token in lower_name for token in ("ritual", "ceremonia")):
            return "ritual"
        if any(token in lower_name for token in ("titulo", "título", "princesa", "rey", "reina", "regente")):
            return "title"
        if any(token in lower_name for token in ("anomalia", "anomalía", "eco", "despertar")):
            return "phenomenon"
        return None
    if entity_kind == "object":
        if any(token in lower_name for token in ("báculo", "baculo", "artefacto", "reliquia")):
            return "artifact"
        if any(token in lower_name for token in ("espada", "lanza", "arco")):
            return "weapon"
        return None
    if entity_kind == "creature":
        if len(refs) >= 2:
            return "individual_nonhuman"
        return None
    if entity_kind == "event":
        if any(token in lower_name for token in ("guerra", "war")):
            return "war"
        if any(token in lower_name for token in ("caida", "caída", "desastre", "catástrofe", "ruina")):
            return "disaster"
        if any(token in lower_name for token in ("ritual", "ceremonia")):
            return "ritual_event"
        return "historical" if refs else None
    return None


def taxonomy_tags(*, note_role: str, entity_kind: str | None = None, entity_subkind: str | None = None) -> list[str]:
    role_tags = {
        "chapter": ["#chapter"],
        "chapter_summary": ["#summary"],
        "primary": ["#primary"],
        "review": ["#review"],
        "system": ["#system"],
    }.get(note_role, [])
    tags = list(role_tags)
    if note_role in {"primary", "review"}:
        kind, subkind = normalize_taxonomy(entity_kind=entity_kind, entity_subkind=entity_subkind)
        tags.append(f"#{kind}")
        if subkind:
            tags.append(f"#{subkind}")
    return tags


def _clean_subkind(value: str | None) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


def taxonomy_payload_for_entity(entity: dict[str, Any], *, title_hit_count: int = 0) -> dict[str, Any]:
    kind, subkind = normalize_taxonomy(
        entity_kind=entity.get("entity_kind"),
        entity_subkind=entity.get("entity_subkind"),
        canonical_name=entity.get("canonical_name"),
        chapter_refs=entity.get("chapter_refs") or [],
        title_hit_count=title_hit_count,
    )
    return {
        "entity_kind": kind,
        "entity_subkind": subkind,
        "semantic_class": f"{kind}:{subkind}" if subkind else kind,
    }
