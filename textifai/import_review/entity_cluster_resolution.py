from __future__ import annotations

from collections import defaultdict
from typing import Any


_QUALITY_RANK = {
    "proper_name": 4,
    "title_plus_name": 3,
    "descriptor": 2,
    "pronoun_like": 1,
    "unknown": 0,
}

_SECTION_KIND = {
    "characters": "character",
    "places": "place",
    "concepts": "concept",
    "events": "event",
}


def normalize_entity_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_entity_key(value: str) -> str:
    return normalize_entity_text(value).casefold()


def _normalize_naming_quality(value: str | None) -> str:
    normalized = str(value or "unknown").strip().casefold()
    if normalized in _QUALITY_RANK:
        return normalized
    return "unknown"


def _candidate_key(entity_kind: str, names: list[str]) -> str:
    for name in names:
        normalized = normalize_entity_text(name)
        if normalized:
            return f"{entity_kind}::{normalize_entity_key(normalized)}"
    return f"{entity_kind}::"


def _collect_global_observations(global_data: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for entity in global_data.get("entities", []) or []:
        if not isinstance(entity, dict):
            continue
        canonical_name = normalize_entity_text(entity.get("canonical_name") or entity.get("canonical_candidate") or "")
        canonical_candidate = normalize_entity_text(entity.get("canonical_candidate") or canonical_name)
        aliases = [normalize_entity_text(item) for item in (entity.get("aliases") or []) if normalize_entity_text(item)]
        source_mentions = [normalize_entity_text(item) for item in (entity.get("source_mentions") or []) if normalize_entity_text(item)]
        observations.append(
            {
                "source": "global",
                "entity_kind": str(entity.get("entity_kind") or "lore").strip().casefold() or "lore",
                "canonical_name": canonical_name,
                "canonical_candidate": canonical_candidate,
                "surface_forms": [item for item in [canonical_name, canonical_candidate, *aliases, *source_mentions] if item],
                "aliases_candidates": aliases,
                "rejected_aliases_candidates": [],
                "naming_quality": _normalize_naming_quality(entity.get("naming_quality")),
                "is_stable_entity": bool(entity.get("is_stable_entity", True)),
                "needs_review": bool(entity.get("needs_review", str(entity.get("review_state") or "").casefold() == "review")),
                "review_reason": normalize_entity_text(entity.get("review_reason") or ""),
                "summary": normalize_entity_text(entity.get("summary") or ""),
                "facts": [normalize_entity_text(item) for item in (entity.get("key_facts") or []) if normalize_entity_text(item)],
                "relationships": [item for item in (entity.get("relationships") or []) if isinstance(item, dict)],
                "chapter_refs": [str(item).strip() for item in (entity.get("chapter_refs") or []) if str(item).strip()],
                "source_mentions": source_mentions,
                "confidence": float(entity.get("confidence") or 0.0),
            }
        )
    return observations


def _collect_chapter_observations(chapter_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for chapter in chapter_outputs:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        for section, entity_kind in _SECTION_KIND.items():
            for item in chapter.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                surface = normalize_entity_text(item.get("surface") or "")
                canonical = normalize_entity_text(item.get("canonical") or surface)
                canonical_candidate = normalize_entity_text(item.get("canonical_candidate") or canonical or surface)
                observations.append(
                    {
                        "source": "chapter",
                        "entity_kind": entity_kind,
                        "canonical_name": canonical,
                        "canonical_candidate": canonical_candidate,
                        "surface_forms": [value for value in [surface, canonical, canonical_candidate] if value],
                        "aliases_candidates": [],
                        "rejected_aliases_candidates": [],
                        "naming_quality": _normalize_naming_quality(item.get("naming_quality")),
                        "is_stable_entity": bool(item.get("is_stable_entity", False)),
                        "needs_review": bool(item.get("needs_review", False)),
                        "review_reason": normalize_entity_text(item.get("review_reason") or ""),
                        "summary": "",
                        "facts": [normalize_entity_text(fact) for fact in (item.get("facts") or []) if normalize_entity_text(fact)],
                        "relationships": [],
                        "chapter_refs": [chapter_id] if chapter_id else [],
                        "source_mentions": [surface] if surface else [],
                        "confidence": float(item.get("confidence") or 0.0),
                    }
                )
    return observations


def _merge_relationships(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        target = normalize_entity_text(item.get("target") or "")
        rel_type = str(item.get("type") or "").strip()
        facts = [normalize_entity_text(fact) for fact in (item.get("facts") or []) if normalize_entity_text(fact)]
        if not target or not rel_type:
            continue
        key = (normalize_entity_key(target), rel_type.casefold())
        if key not in bucket:
            bucket[key] = {"target": target, "type": rel_type, "facts": []}
        existing = bucket[key]
        for fact in facts:
            if fact and fact not in existing["facts"]:
                existing["facts"].append(fact)
    return sorted(bucket.values(), key=lambda rel: (str(rel.get("type") or ""), str(rel.get("target") or "").lower()))


def _pick_best_name(variants: list[dict[str, Any]]) -> tuple[str, str]:
    ranked = sorted(
        variants,
        key=lambda item: (
            _QUALITY_RANK.get(str(item.get("naming_quality") or "unknown"), 0),
            int(item.get("chapter_coverage") or 0),
            int(item.get("support_count") or 0),
            float(item.get("avg_confidence") or 0.0),
            -len(str(item.get("name") or "")),
        ),
        reverse=True,
    )
    if not ranked:
        return "", "unknown"
    return str(ranked[0]["name"]), str(ranked[0]["naming_quality"])


def resolve_entity_clusters(
    *,
    global_data: dict[str, Any],
    chapter_outputs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    observations = _collect_global_observations(global_data) + _collect_chapter_observations(chapter_outputs)
    cluster_map: dict[str, list[dict[str, Any]]] = {}
    alias_index: dict[str, str] = {}
    for observation in observations:
        names = [
            normalize_entity_text(value)
            for value in [
                observation.get("canonical_candidate") or "",
                observation.get("canonical_name") or "",
                *(observation.get("surface_forms") or []),
            ]
            if normalize_entity_text(value)
        ]
        existing_keys = {
            alias_index[f"{observation['entity_kind']}::{normalize_entity_key(name)}"]
            for name in names
            if f"{observation['entity_kind']}::{normalize_entity_key(name)}" in alias_index
        }
        if existing_keys:
            key = sorted(existing_keys)[0]
            if len(existing_keys) > 1:
                merged_items: list[dict[str, Any]] = []
                for existing_key in sorted(existing_keys):
                    merged_items.extend(cluster_map.pop(existing_key, []))
                cluster_map[key] = merged_items
                for alias_key, alias_cluster in list(alias_index.items()):
                    if alias_cluster in existing_keys:
                        alias_index[alias_key] = key
        else:
            key = _candidate_key(observation["entity_kind"], names)
        if key.endswith("::") or not names:
            continue
        cluster_map.setdefault(key, [])
        cluster_map[key].append(observation)
        for name in names:
            alias_index[f"{observation['entity_kind']}::{normalize_entity_key(name)}"] = key

    resolved_entities: list[dict[str, Any]] = []
    clusters_audit: list[dict[str, Any]] = []
    resolution_audit: list[dict[str, Any]] = []

    for cluster_key, cluster_items in sorted(cluster_map.items()):
        entity_kind = str(cluster_items[0].get("entity_kind") or "lore").strip().casefold() or "lore"
        chapter_refs: list[str] = []
        source_mentions: list[str] = []
        facts: list[str] = []
        summaries: list[str] = []
        relationships: list[dict[str, Any]] = []
        variant_bucket: dict[str, dict[str, Any]] = {}
        accepted_aliases: list[str] = []
        rejected_aliases: list[str] = []
        review_reasons: list[str] = []
        confidence_values: list[float] = []
        stable_votes = 0
        review_votes = 0

        for item in cluster_items:
            names = [value for value in [item.get("canonical_name"), item.get("canonical_candidate"), *(item.get("surface_forms") or [])] if normalize_entity_text(value)]
            quality = _normalize_naming_quality(item.get("naming_quality"))
            confidence = float(item.get("confidence") or 0.0)
            confidence_values.append(confidence)
            stable_votes += 1 if item.get("is_stable_entity") else 0
            review_votes += 1 if item.get("needs_review") else 0
            if item.get("review_reason"):
                review_reasons.append(str(item["review_reason"]))
            for name in names:
                normalized_name = normalize_entity_text(name)
                if not normalized_name:
                    continue
                bucket = variant_bucket.setdefault(
                    normalized_name,
                    {
                        "name": normalized_name,
                        "naming_quality": quality,
                        "support_count": 0,
                        "chapter_refs": set(),
                        "confidence_total": 0.0,
                    },
                )
                if _QUALITY_RANK.get(quality, 0) > _QUALITY_RANK.get(str(bucket["naming_quality"]), 0):
                    bucket["naming_quality"] = quality
                bucket["support_count"] += 1
                bucket["confidence_total"] += confidence
                for chapter_ref in item.get("chapter_refs") or []:
                    bucket["chapter_refs"].add(str(chapter_ref).strip())
            for chapter_ref in item.get("chapter_refs") or []:
                normalized_ref = str(chapter_ref).strip()
                if normalized_ref and normalized_ref not in chapter_refs:
                    chapter_refs.append(normalized_ref)
            for mention in item.get("source_mentions") or []:
                normalized_mention = normalize_entity_text(mention)
                if normalized_mention and normalized_mention not in source_mentions:
                    source_mentions.append(normalized_mention)
            for fact in item.get("facts") or []:
                normalized_fact = normalize_entity_text(fact)
                if normalized_fact and normalized_fact not in facts:
                    facts.append(normalized_fact)
            summary = normalize_entity_text(item.get("summary") or "")
            if summary and summary not in summaries:
                summaries.append(summary)
            for alias in item.get("aliases_candidates") or []:
                normalized_alias = normalize_entity_text(alias)
                if normalized_alias and normalized_alias not in accepted_aliases:
                    accepted_aliases.append(normalized_alias)
            for alias in item.get("rejected_aliases_candidates") or []:
                normalized_alias = normalize_entity_text(alias)
                if normalized_alias and normalized_alias not in rejected_aliases:
                    rejected_aliases.append(normalized_alias)
            relationships.extend(item.get("relationships") or [])

        ranked_variants = [
            {
                "name": data["name"],
                "naming_quality": data["naming_quality"],
                "support_count": data["support_count"],
                "chapter_coverage": len(data["chapter_refs"]),
                "avg_confidence": data["confidence_total"] / max(data["support_count"], 1),
            }
            for data in variant_bucket.values()
        ]
        final_canonical_name, final_quality = _pick_best_name(ranked_variants)
        if not final_canonical_name:
            continue

        for variant in ranked_variants:
            name = str(variant["name"])
            quality = str(variant["naming_quality"])
            if name == final_canonical_name:
                continue
            if quality in {"pronoun_like", "unknown"}:
                if name not in rejected_aliases:
                    rejected_aliases.append(name)
            elif name not in accepted_aliases:
                accepted_aliases.append(name)

        merged_relationships = _merge_relationships(relationships)
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        is_stable_entity = stable_votes > 0 or len(chapter_refs) >= 2 or len(merged_relationships) >= 1 or len(facts) >= 2
        needs_review = review_votes > 0 or final_quality in {"descriptor", "pronoun_like", "unknown"}
        review_reason = ""
        if needs_review:
            review_reason = review_reasons[0] if review_reasons else "Cluster requires manual review due to weak or descriptive naming."

        resolved_entities.append(
            {
                "canonical_name": final_canonical_name,
                "canonical_candidate": final_canonical_name,
                "entity_kind": entity_kind,
                "preferred_slug": "",
                "aliases": accepted_aliases,
                "rejected_aliases": rejected_aliases,
                "summary": summaries[0] if summaries else "",
                "key_facts": facts[:5],
                "relationships": merged_relationships[:5],
                "chapter_refs": chapter_refs,
                "source_mentions": source_mentions,
                "confidence": round(confidence, 4),
                "review_state": "review" if needs_review else "canonical",
                "naming_quality": final_quality,
                "is_stable_entity": is_stable_entity,
                "needs_review": needs_review,
                "review_reason": review_reason,
            }
        )
        clusters_audit.append(
            {
                "cluster_key": cluster_key,
                "entity_kind": entity_kind,
                "observation_count": len(cluster_items),
                "chapter_coverage": len(chapter_refs),
                "variants": sorted(ranked_variants, key=lambda item: item["name"].lower()),
            }
        )
        resolution_audit.append(
            {
                "cluster_key": cluster_key,
                "final_canonical_name": final_canonical_name,
                "entity_kind": entity_kind,
                "naming_quality": final_quality,
                "accepted_aliases": accepted_aliases,
                "rejected_aliases": rejected_aliases,
                "needs_review": needs_review,
                "review_reason": review_reason,
                "confidence": round(confidence, 4),
            }
        )

    resolved_entities.sort(key=lambda item: (str(item.get("entity_kind") or ""), str(item.get("canonical_name") or "").lower()))
    return (
        resolved_entities,
        {"cluster_count": len(clusters_audit), "clusters": clusters_audit},
        {"resolved_entity_count": len(resolved_entities), "resolutions": resolution_audit},
    )
