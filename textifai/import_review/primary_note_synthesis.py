from __future__ import annotations

from typing import Any

from textifai.import_review.entity_cluster_resolution import normalize_entity_text
from textifai.obsidian.taxonomy import taxonomy_payload_for_entity


def synthesize_primary_note_summaries(
    *,
    entities: list[dict[str, Any]],
    language: str = "unknown",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compose readable primary summaries from reconciled facts.

    This is intentionally deterministic. It improves the note-facing summary
    after entity reconciliation without changing clustering or graph identity.
    """

    synthesized: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    updated_count = 0
    for entity in entities:
        item = dict(entity)
        if _is_primary(item):
            summary = _compose_primary_summary(item, language=language)
            previous = normalize_entity_text(item.get("summary") or "")
            if summary and summary != previous:
                item["summary"] = summary
                item["primary_note_summary_synthesized"] = True
                updated_count += 1
                decisions.append(
                    {
                        "canonical_name": item.get("canonical_name") or "",
                        "entity_kind": item.get("entity_kind") or "",
                        "entity_subkind": taxonomy_payload_for_entity(item).get("entity_subkind"),
                        "previous_summary": previous,
                        "new_summary": summary,
                        "reason": "primary_note_summary_from_reconciled_facts",
                    }
                )
            else:
                decisions.append(
                    {
                        "canonical_name": item.get("canonical_name") or "",
                        "entity_kind": item.get("entity_kind") or "",
                        "entity_subkind": taxonomy_payload_for_entity(item).get("entity_subkind"),
                        "previous_summary": previous,
                        "new_summary": previous,
                        "reason": "summary_unchanged",
                    }
                )
        synthesized.append(item)
    audit = {
        "schema_version": "textifai.primary_note_synthesis.v1",
        "input_entity_count": len(entities),
        "output_entity_count": len(synthesized),
        "primary_count": len([entity for entity in synthesized if _is_primary(entity)]),
        "updated_summary_count": updated_count,
        "strategy": "deterministic_reconciled_fact_summary",
        "decisions": decisions,
    }
    return synthesized, audit


def _is_primary(entity: dict[str, Any]) -> bool:
    return (
        str(entity.get("note_role") or "").strip().casefold() == "primary"
        or str(entity.get("review_state") or "").strip().casefold() == "canonical"
    )


def _compose_primary_summary(entity: dict[str, Any], *, language: str) -> str:
    name = normalize_entity_text(entity.get("canonical_name") or "")
    if not name:
        return ""
    taxonomy = taxonomy_payload_for_entity(entity)
    entity_kind = str(taxonomy.get("entity_kind") or entity.get("entity_kind") or "entity")
    entity_subkind = str(taxonomy.get("entity_subkind") or "")
    aliases = _meaningful_aliases(entity)
    facts = _fact_sentences(entity)
    relationships = _relationship_sentences(entity, language=language)
    evidence = [*relationships[:2], *facts[:3]]
    if str(language or "").casefold().startswith("es"):
        return _compose_spanish_summary(
            name=name,
            entity_kind=entity_kind,
            entity_subkind=entity_subkind,
            aliases=aliases,
            evidence=evidence,
        )
    return _compose_english_summary(
        name=name,
        entity_kind=entity_kind,
        entity_subkind=entity_subkind,
        aliases=aliases,
        evidence=evidence,
    )


def _meaningful_aliases(entity: dict[str, Any]) -> list[str]:
    name_key = normalize_entity_text(entity.get("canonical_name") or "").casefold()
    candidates: list[str] = []
    for alias in entity.get("aliases") or []:
        text = normalize_entity_text(alias)
        if not text or text.casefold() == name_key:
            continue
        if text.casefold() in {"yo", "él", "ella", "el", "la"}:
            continue
        if text not in candidates:
            candidates.append(text)
    out: list[str] = []
    for alias in sorted(candidates, key=lambda item: (-len(item.split()), -len(item))):
        alias_key = alias.casefold()
        if any(alias_key in kept.casefold() or kept.casefold() in alias_key for kept in out):
            continue
        out.append(alias)
    return out[:3]


def _fact_sentences(entity: dict[str, Any]) -> list[str]:
    return [normalize_entity_text(item).rstrip(".") for item in (entity.get("key_facts") or []) if normalize_entity_text(item)][:4]


def _relationship_sentences(entity: dict[str, Any], *, language: str) -> list[str]:
    out: list[str] = []
    for rel in sorted(entity.get("relationships") or [], key=_relationship_priority):
        if not isinstance(rel, dict):
            continue
        target = normalize_entity_text(rel.get("target") or "")
        rel_type = normalize_entity_text(rel.get("type") or "")
        if rel_type.casefold() == "related_to":
            continue
        facts = [normalize_entity_text(item).rstrip(".") for item in (rel.get("facts") or []) if normalize_entity_text(item)]
        if not target:
            continue
        label = _relationship_label(rel_type, language=language)
        if facts:
            out.append(f"{label} con {target}: {facts[0]}" if label else f"{target}: {facts[0]}")
        elif rel_type:
            out.append(f"{label} con {target}" if label else f"Mantiene una relación con {target}")
    return out[:3]


def _relationship_priority(rel: dict[str, Any]) -> int:
    rel_type = normalize_entity_text(rel.get("type") or "").casefold()
    return {
        "familial": 0,
        "conflict": 1,
        "authority": 2,
        "dependency": 3,
        "located_in": 4,
        "uses": 5,
        "member_of": 6,
        "related_to": 9,
    }.get(rel_type, 8)


def _relationship_label(rel_type: str, *, language: str) -> str:
    if str(language or "").casefold().startswith("es"):
        return {
            "familial": "mantiene una relación familiar",
            "conflict": "mantiene un conflicto",
            "authority": "mantiene una relación de autoridad",
            "dependency": "mantiene una dependencia",
            "located_in": "se vincula con el lugar",
            "uses": "usa o canaliza",
            "member_of": "pertenece o se vincula a",
        }.get(rel_type.casefold(), "")
    return {
        "familial": "has a familial relationship",
        "conflict": "has a conflict",
        "authority": "has an authority relationship",
        "dependency": "has a dependency",
        "located_in": "is tied to the place",
        "uses": "uses or channels",
        "member_of": "belongs or is linked to",
    }.get(rel_type.casefold(), "")


def _compose_spanish_summary(
    *,
    name: str,
    entity_kind: str,
    entity_subkind: str,
    aliases: list[str],
    evidence: list[str],
) -> str:
    role = _spanish_role(entity_kind=entity_kind, entity_subkind=entity_subkind)
    first = f"{name} es {role}"
    if aliases:
        first += f", también asociada con {', '.join(aliases[:2])}"
    first += "."
    if not evidence:
        return first
    second = _join_evidence_spanish(evidence[:2])
    summary = f"{first} {second}."
    if len(evidence) > 2:
        summary += f" Además, {_lower_initial_after_join(evidence[2].rstrip('.'))}."
    return summary


def _compose_english_summary(
    *,
    name: str,
    entity_kind: str,
    entity_subkind: str,
    aliases: list[str],
    evidence: list[str],
) -> str:
    role = _english_role(entity_kind=entity_kind, entity_subkind=entity_subkind)
    first = f"{name} is {role}"
    if aliases:
        first += f", also associated with {', '.join(aliases[:2])}"
    first += "."
    if not evidence:
        return first
    second = _join_evidence_english(evidence[:2])
    summary = f"{first} {second}."
    if len(evidence) > 2:
        summary += f" In addition, {_lower_initial_after_join(evidence[2].rstrip('.'))}."
    return summary


def _spanish_role(*, entity_kind: str, entity_subkind: str) -> str:
    if entity_kind == "character" and entity_subkind == "protagonist":
        return "una figura protagonista de la historia"
    if entity_kind == "character":
        return "un personaje relevante de la historia"
    if entity_kind == "place":
        return "un lugar relevante del mundo narrativo"
    if entity_kind == "object":
        return "un objeto relevante del mundo narrativo"
    if entity_kind == "faction":
        return "una facción relevante del mundo narrativo"
    if entity_kind == "event":
        return "un evento relevante de la historia"
    return "una entidad relevante del VaERL"


def _english_role(*, entity_kind: str, entity_subkind: str) -> str:
    if entity_kind == "character" and entity_subkind == "protagonist":
        return "a protagonist figure in the story"
    if entity_kind == "character":
        return "a relevant character in the story"
    if entity_kind == "place":
        return "a relevant place in the narrative world"
    if entity_kind == "object":
        return "a relevant object in the narrative world"
    if entity_kind == "faction":
        return "a relevant faction in the narrative world"
    if entity_kind == "event":
        return "a relevant event in the story"
    return "a relevant VaERL entity"


def _join_evidence_spanish(items: list[str]) -> str:
    cleaned = [_lower_initial_after_join(item.rstrip(".")) for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return _upper_initial(cleaned[0])
    return f"{_upper_initial(cleaned[0])} y {cleaned[1]}"


def _join_evidence_english(items: list[str]) -> str:
    cleaned = [_lower_initial_after_join(item.rstrip(".")) for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return _upper_initial(cleaned[0])
    return f"{_upper_initial(cleaned[0])} and {cleaned[1]}"


def _lower_initial_after_join(value: str) -> str:
    if not value:
        return ""
    return value[:1].lower() + value[1:]


def _upper_initial(value: str) -> str:
    if not value:
        return ""
    return value[:1].upper() + value[1:]
