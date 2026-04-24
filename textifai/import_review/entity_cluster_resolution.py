from __future__ import annotations

from collections import defaultdict
import re
from typing import Any
import unicodedata


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

_GENDER_SIGNALS = {"masculine", "feminine", "unknown", "mixed"}
_REVIEW_REASON_CODES = {
    "type_conflict_stronger_identity",
    "descriptor_cluster_overlaps_named_character",
    "weak_or_descriptive_naming",
    "alias_contamination_rejected_named_aliases",
}
_REVIEW_REASON_I18N = {
    "type_conflict_stronger_identity": {
        "en": "Type conflict with stronger identity: {stronger_identity}.",
        "es": "Conflicto de tipo con una identidad más fuerte: {stronger_identity}.",
    },
    "descriptor_cluster_overlaps_named_character": {
        "en": "Descriptor cluster overlaps stronger named character: {stronger_identity}.",
        "es": "El clúster descriptivo se solapa con un personaje nombrado más fuerte: {stronger_identity}.",
    },
    "weak_or_descriptive_naming": {
        "en": "Cluster requires manual review due to weak or descriptive naming.",
        "es": "El clúster requiere revisión manual por naming débil o descriptivo.",
    },
    "alias_contamination_rejected_named_aliases": {
        "en": "Alias contamination guardrail rejected named aliases: {rejected_aliases}.",
        "es": "El guardrail de contaminación de aliases rechazó aliases nombrados: {rejected_aliases}.",
    },
}


def normalize_entity_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_entity_key(value: str) -> str:
    return normalize_entity_text(value).casefold()


def _expanded_identity_surface_forms(values: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_entity_text(value)
        if not normalized:
            continue
        candidates = [normalized]
        if "—" in normalized:
            parts = [normalize_entity_text(part) for part in normalized.split("—") if normalize_entity_text(part)]
            if not any(" no " in f" {part.casefold()} " for part in parts):
                candidates.extend(parts)
        for candidate in candidates:
            key = normalize_entity_key(candidate)
            if not key or key in seen:
                continue
            seen.add(key)
            expanded.append(candidate)
    return expanded


def _identity_bridge_names(observation: dict[str, Any]) -> list[str]:
    """Return names allowed to join observations into the same identity cluster.

    Pronoun-like surface forms are useful evidence once an extractor has already
    attached them to a canonical candidate, but they are unsafe as global merge
    bridges because they can connect unrelated POV characters across chapters.
    """
    quality = _normalize_naming_quality(observation.get("naming_quality"))
    canonical_names = [
        observation.get("canonical_candidate") or "",
        observation.get("canonical_name") or "",
    ]
    if quality == "pronoun_like":
        return _expanded_identity_surface_forms(canonical_names)
    return _expanded_identity_surface_forms(
        [
            *canonical_names,
            *(observation.get("surface_forms") or []),
        ]
    )


def _preferred_slug_for_name(value: str) -> str:
    normalized = normalize_entity_text(value)
    if not normalized:
        return ""
    normalized = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower()
    normalized = normalized.replace("’", "").replace("'", "")
    normalized = re.sub(r"[^\w\s-]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-\s]+", "_", normalized).strip("_")
    return normalized or "note"


def _normalize_review_reason_code(value: str | None) -> str:
    normalized = str(value or "").strip()
    if normalized in _REVIEW_REASON_CODES:
        return normalized
    return ""


def _normalize_review_reason_params(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = str(key or "").strip()
        normalized_value = normalize_entity_text(item or "")
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def _render_review_reason(*, code: str | None, params: dict[str, str] | None, language: str) -> str:
    normalized_code = _normalize_review_reason_code(code)
    normalized_params = _normalize_review_reason_params(params)
    if not normalized_code:
        return ""
    lang = str(language or "").strip().casefold()
    locale = "es" if lang.startswith("es") else "en"
    template_catalog = _REVIEW_REASON_I18N.get(normalized_code, {})
    template = template_catalog.get(locale) or template_catalog.get("en") or ""
    if not template:
        return ""
    safe_params = {
        "stronger_identity": normalized_params.get("stronger_identity", "another entity"),
        "rejected_aliases": normalized_params.get("rejected_aliases", "other aliases"),
    }
    safe_params.update(normalized_params)
    return template.format(**safe_params)


def _normalize_naming_quality(value: str | None) -> str:
    normalized = str(value or "unknown").strip().casefold()
    if normalized in _QUALITY_RANK:
        return normalized
    return "unknown"


def _normalize_gender_signal(value: str | None) -> str:
    normalized = str(value or "unknown").strip().casefold()
    if normalized in _GENDER_SIGNALS:
        return normalized
    return "unknown"


def _normalize_gender_signal_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return round(numeric, 4)


def _normalize_gender_signal_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        chapter_id = str(item.get("chapter_id") or "").strip()
        surface = normalize_entity_text(item.get("surface") or "")
        kind = str(item.get("kind") or "").strip() or "unknown"
        key = (chapter_id, surface, kind)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "chapter_id": chapter_id,
                "surface": surface,
                "kind": kind,
            }
        )
    return normalized[:5]


def _gender_signal_kind(observation: dict[str, Any]) -> str:
    if str(observation.get("source") or "") == "chapter":
        quality = _normalize_naming_quality(observation.get("naming_quality"))
        if quality in {"descriptor", "pronoun_like", "title_plus_name"}:
            return "local_descriptor"
        if observation.get("facts"):
            return "local_fact"
        return "local_surface"
    return "global_aggregate"


def _gender_signal_surface(observation: dict[str, Any]) -> str:
    for value in observation.get("source_mentions") or []:
        normalized = normalize_entity_text(value)
        if normalized:
            return normalized
    for value in observation.get("surface_forms") or []:
        normalized = normalize_entity_text(value)
        if normalized:
            return normalized
    return normalize_entity_text(observation.get("canonical_name") or "")


def _gender_signal_weight(observation: dict[str, Any]) -> float:
    confidence = _normalize_gender_signal_confidence(observation.get("gender_signal_confidence"))
    confidence_factor = 0.35 + (0.65 * confidence)
    if str(observation.get("source") or "") == "chapter":
        base = 1.0
        if observation.get("facts"):
            base += 0.25
        if _normalize_naming_quality(observation.get("naming_quality")) in {"descriptor", "title_plus_name"}:
            base += 0.2
        if observation.get("chapter_refs"):
            base += 0.05
    else:
        base = 0.2
        if observation.get("facts"):
            base += 0.05
        if observation.get("relationships"):
            base += 0.05
        if len(observation.get("chapter_refs") or []) >= 2:
            base += 0.05
    return round(base * confidence_factor, 4)


def _build_gender_signal_observation(observation: dict[str, Any]) -> dict[str, Any] | None:
    signal = _normalize_gender_signal(observation.get("gender_presentation_signal"))
    if signal == "unknown":
        return None
    gender_confidence = _normalize_gender_signal_confidence(observation.get("gender_signal_confidence"))
    chapter_refs = [str(item).strip() for item in (observation.get("chapter_refs") or []) if str(item).strip()]
    chapter_id = chapter_refs[0] if str(observation.get("source") or "") == "chapter" and chapter_refs else ""
    return {
        "signal": signal,
        "source": str(observation.get("source") or ""),
        "weight": _gender_signal_weight(observation),
        "has_explicit_gender_confidence": gender_confidence > 0.0,
        "chapter_id": chapter_id,
        "surface": _gender_signal_surface(observation),
        "kind": _gender_signal_kind(observation),
    }


def _derive_gender_signal(cluster_items: list[dict[str, Any]]) -> dict[str, Any]:
    raw_evidence = [
        built
        for built in (_build_gender_signal_observation(item) for item in cluster_items)
        if built is not None
    ]
    if not raw_evidence:
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": [],
            "gender_signal_conflict": False,
            "gender_signal_downgraded": False,
        }
    if not any(bool(item.get("has_explicit_gender_confidence")) for item in raw_evidence):
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": _normalize_gender_signal_evidence(raw_evidence),
            "gender_signal_conflict": False,
            "gender_signal_downgraded": True,
        }

    local_evidence = [item for item in raw_evidence if item["source"] == "chapter"]
    if local_evidence:
        weighted = list(local_evidence)
        weighted.extend(
            {
                **item,
                "weight": round(item["weight"] * 0.25, 4),
            }
            for item in raw_evidence
            if item["source"] != "chapter"
        )
    else:
        weighted = list(raw_evidence)

    score_by_signal = defaultdict(float)
    local_score_by_signal = defaultdict(float)
    for item in weighted:
        signal = str(item["signal"])
        score_by_signal[signal] += float(item["weight"])
        if item["source"] == "chapter":
            local_score_by_signal[signal] += float(item["weight"])

    resolved_scores = {
        signal: score
        for signal, score in score_by_signal.items()
        if signal in {"masculine", "feminine"} and score > 0.0
    }
    if not resolved_scores:
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": [],
            "gender_signal_conflict": False,
            "gender_signal_downgraded": False,
        }

    ranked = sorted(resolved_scores.items(), key=lambda item: item[1], reverse=True)
    top_signal, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    has_conflict = len(ranked) > 1
    has_local_conflict = sum(1 for score in local_score_by_signal.values() if score > 0.0) > 1

    if local_evidence and max(local_score_by_signal.values(), default=0.0) < 0.45:
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": _normalize_gender_signal_evidence(weighted),
            "gender_signal_conflict": has_conflict,
            "gender_signal_downgraded": True,
        }

    if not local_evidence and top_score < 0.35:
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": _normalize_gender_signal_evidence(weighted),
            "gender_signal_conflict": has_conflict,
            "gender_signal_downgraded": True,
        }

    if has_conflict and (has_local_conflict or second_score >= max(0.55, top_score * 0.55)):
        return {
            "gender_presentation_signal": "mixed",
            "gender_signal_confidence": round(min(0.45, top_score / max(top_score + second_score, 1.0)), 4),
            "gender_signal_evidence": _normalize_gender_signal_evidence(weighted),
            "gender_signal_conflict": True,
            "gender_signal_downgraded": True,
        }

    confidence = top_score / (2.0 if local_evidence else 3.0)
    if has_conflict:
        confidence = min(confidence, 0.6)
    confidence = round(min(1.0, confidence), 4)
    if confidence < 0.35:
        return {
            "gender_presentation_signal": "unknown",
            "gender_signal_confidence": 0.0,
            "gender_signal_evidence": _normalize_gender_signal_evidence(weighted),
            "gender_signal_conflict": has_conflict,
            "gender_signal_downgraded": True,
        }

    return {
        "gender_presentation_signal": top_signal,
        "gender_signal_confidence": confidence,
        "gender_signal_evidence": _normalize_gender_signal_evidence(weighted),
        "gender_signal_conflict": has_conflict,
        "gender_signal_downgraded": has_conflict,
    }


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
                "surface_forms": _expanded_identity_surface_forms([canonical_name, canonical_candidate, *aliases, *source_mentions]),
                "aliases_candidates": aliases,
                "rejected_aliases_candidates": [],
                "naming_quality": _normalize_naming_quality(entity.get("naming_quality")),
                "is_stable_entity": bool(entity.get("is_stable_entity", True)),
                "needs_review": bool(entity.get("needs_review", str(entity.get("review_state") or "").casefold() == "review")),
                "review_reason": normalize_entity_text(entity.get("review_reason") or ""),
                "review_reason_code": _normalize_review_reason_code(entity.get("review_reason_code")),
                "review_reason_params": _normalize_review_reason_params(entity.get("review_reason_params")),
                "summary": normalize_entity_text(entity.get("summary") or ""),
                "facts": [normalize_entity_text(item) for item in (entity.get("key_facts") or []) if normalize_entity_text(item)],
                "relationships": [item for item in (entity.get("relationships") or []) if isinstance(item, dict)],
                "chapter_refs": [str(item).strip() for item in (entity.get("chapter_refs") or []) if str(item).strip()],
                "source_mentions": source_mentions,
                "confidence": float(entity.get("confidence") or 0.0),
                "preferred_slug": str(entity.get("preferred_slug") or "").strip(),
                "gender_presentation_signal": _normalize_gender_signal(entity.get("gender_presentation_signal")),
                "gender_signal_confidence": _normalize_gender_signal_confidence(entity.get("gender_signal_confidence")),
                "gender_signal_evidence": _normalize_gender_signal_evidence(entity.get("gender_signal_evidence")),
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
                        "review_reason_code": _normalize_review_reason_code(item.get("review_reason_code")),
                        "review_reason_params": _normalize_review_reason_params(item.get("review_reason_params")),
                        "summary": "",
                        "facts": [normalize_entity_text(fact) for fact in (item.get("facts") or []) if normalize_entity_text(fact)],
                        "relationships": [],
                        "chapter_refs": [chapter_id] if chapter_id else [],
                        "source_mentions": [surface] if surface else [],
                        "confidence": float(item.get("confidence") or 0.0),
                        "gender_presentation_signal": _normalize_gender_signal(item.get("gender_presentation_signal")),
                        "gender_signal_confidence": _normalize_gender_signal_confidence(item.get("gender_signal_confidence")),
                        "gender_signal_evidence": _normalize_gender_signal_evidence(item.get("gender_signal_evidence")),
                    }
                )
    return observations


def _title_contains_name(title: str, name: str) -> bool:
    normalized_title = normalize_entity_text(title)
    normalized_name = normalize_entity_text(name)
    if len(normalized_name) < 3:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", normalized_title, flags=re.IGNORECASE) is not None


def _apply_title_hint_identity_bridges(
    observations: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    chapter_titles = {
        str(chapter.get("chapter_id") or "").strip(): str(
            chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or ""
        ).strip()
        for chapter in chapter_outputs
        if isinstance(chapter, dict)
    }
    known_character_names = sorted(
        {
            normalize_entity_text(value)
            for observation in observations
            if str(observation.get("entity_kind") or "") == "character"
            and _normalize_naming_quality(observation.get("naming_quality")) in {"proper_name", "title_plus_name"}
            for value in [observation.get("canonical_name"), observation.get("canonical_candidate")]
            if normalize_entity_text(value)
        },
        key=lambda value: (-len(value), value.casefold()),
    )
    if not known_character_names:
        return observations

    bridged: list[dict[str, Any]] = []
    for observation in observations:
        if (
            str(observation.get("source") or "") != "chapter"
            or str(observation.get("entity_kind") or "") != "character"
            or _normalize_naming_quality(observation.get("naming_quality")) != "pronoun_like"
        ):
            bridged.append(observation)
            continue
        chapter_refs = [str(item).strip() for item in (observation.get("chapter_refs") or []) if str(item).strip()]
        title = chapter_titles.get(chapter_refs[0], "") if chapter_refs else ""
        matches = [name for name in known_character_names if _title_contains_name(title, name)]
        match_keys = {normalize_entity_key(name) for name in matches}
        if len(match_keys) != 1:
            bridged.append(observation)
            continue
        hint_name = matches[0]
        bridged.append(
            {
                **observation,
                "canonical_name": hint_name,
                "canonical_candidate": hint_name,
                "title_identity_bridge": {
                    "chapter_id": chapter_refs[0] if chapter_refs else "",
                    "chapter_title": title,
                    "hint_name": hint_name,
                    "original_canonical_name": observation.get("canonical_name") or "",
                },
            }
        )
    return bridged


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
            int(item.get("global_canonical_support_count") or 0),
            int(item.get("canonical_support_count") or 0),
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


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = normalize_entity_text(item)
            key = normalize_entity_key(normalized)
            if not normalized or key in seen:
                continue
            seen.add(key)
            out.append(normalized)
    return out


def _gender_signals_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_signal = _normalize_gender_signal(left.get("gender_presentation_signal"))
    right_signal = _normalize_gender_signal(right.get("gender_presentation_signal"))
    left_confidence = _normalize_gender_signal_confidence(left.get("gender_signal_confidence"))
    right_confidence = _normalize_gender_signal_confidence(right.get("gender_signal_confidence"))
    if "unknown" in {left_signal, right_signal}:
        return True
    if "mixed" in {left_signal, right_signal}:
        return True
    if min(left_confidence, right_confidence) < 0.7:
        return True
    return left_signal == right_signal


def _has_strong_named_identity(entity: dict[str, Any]) -> bool:
    return _normalize_naming_quality(entity.get("naming_quality")) == "proper_name" and bool(
        normalize_entity_text(entity.get("canonical_name") or "")
    )


def _overlap_is_descriptor_only(overlap: set[str], left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not overlap:
        return False
    left_name = normalize_entity_key(left.get("canonical_name") or "")
    right_name = normalize_entity_key(right.get("canonical_name") or "")
    return all(item not in {left_name, right_name} for item in overlap)


def _entity_strength(entity: dict[str, Any]) -> tuple[int, int, int, float]:
    quality = _QUALITY_RANK.get(str(entity.get("naming_quality") or "unknown"), 0)
    chapter_count = len(entity.get("chapter_refs") or [])
    relation_count = len(entity.get("relationships") or [])
    confidence = float(entity.get("confidence") or 0.0)
    return (quality, chapter_count, relation_count, confidence)


def _merge_resolved_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    preferred = left if _entity_strength(left) >= _entity_strength(right) else right
    secondary = right if preferred is left else left
    variants = [
        {
            "name": preferred.get("canonical_name") or "",
            "naming_quality": preferred.get("naming_quality") or "unknown",
            "support_count": max(1, len(preferred.get("source_mentions") or [])),
            "chapter_coverage": len(preferred.get("chapter_refs") or []),
            "avg_confidence": float(preferred.get("confidence") or 0.0),
        },
        {
            "name": secondary.get("canonical_name") or "",
            "naming_quality": secondary.get("naming_quality") or "unknown",
            "support_count": max(1, len(secondary.get("source_mentions") or [])),
            "chapter_coverage": len(secondary.get("chapter_refs") or []),
            "avg_confidence": float(secondary.get("confidence") or 0.0),
        },
    ]
    canonical_name, naming_quality = _pick_best_name(variants)
    merged_gender = _derive_gender_signal(
        [
            {
                "source": (
                    "chapter"
                    if any(str(evidence.get("kind") or "").startswith("local_") for evidence in (item.get("gender_signal_evidence") or []))
                    else "global"
                ),
                "gender_presentation_signal": item.get("gender_presentation_signal"),
                "gender_signal_confidence": item.get("gender_signal_confidence"),
                "gender_signal_evidence": item.get("gender_signal_evidence"),
                "chapter_refs": item.get("chapter_refs") or [],
                "source_mentions": item.get("source_mentions") or [],
                "surface_forms": [item.get("canonical_name") or "", *(item.get("aliases") or [])],
                "naming_quality": item.get("naming_quality"),
                "facts": item.get("key_facts") or [],
                "relationships": item.get("relationships") or [],
                "confidence": item.get("confidence") or 0.0,
            }
            for item in (preferred, secondary)
        ]
    )
    return {
        **preferred,
        "canonical_name": canonical_name,
        "canonical_candidate": canonical_name,
        "naming_quality": naming_quality,
        "aliases": _merge_unique_strings(
            preferred.get("aliases") or [],
            secondary.get("aliases") or [],
            [secondary.get("canonical_name") or ""],
        ),
        "rejected_aliases": _merge_unique_strings(
            preferred.get("rejected_aliases") or [],
            secondary.get("rejected_aliases") or [],
        ),
        "summary": str(preferred.get("summary") or secondary.get("summary") or "").strip(),
        "key_facts": _merge_unique_strings(preferred.get("key_facts") or [], secondary.get("key_facts") or [])[:5],
        "relationships": _merge_relationships((preferred.get("relationships") or []) + (secondary.get("relationships") or []))[:5],
        "chapter_refs": _merge_unique_strings(preferred.get("chapter_refs") or [], secondary.get("chapter_refs") or []),
        "source_mentions": _merge_unique_strings(preferred.get("source_mentions") or [], secondary.get("source_mentions") or []),
        "confidence": max(float(preferred.get("confidence") or 0.0), float(secondary.get("confidence") or 0.0)),
        "gender_presentation_signal": merged_gender["gender_presentation_signal"],
        "gender_signal_confidence": merged_gender["gender_signal_confidence"],
        "gender_signal_evidence": merged_gender["gender_signal_evidence"],
        "gender_signal_conflict": merged_gender["gender_signal_conflict"],
        "gender_signal_downgraded": merged_gender["gender_signal_downgraded"],
        "anti_contamination_guardrail": _merge_unique_strings(
            preferred.get("anti_contamination_guardrail") or [],
            secondary.get("anti_contamination_guardrail") or [],
        ),
        "is_stable_entity": bool(preferred.get("is_stable_entity")) or bool(secondary.get("is_stable_entity")),
        "needs_review": bool(preferred.get("needs_review")) or bool(secondary.get("needs_review")),
        "review_reason": str(preferred.get("review_reason") or secondary.get("review_reason") or "").strip(),
        "review_reason_code": str(preferred.get("review_reason_code") or secondary.get("review_reason_code") or "").strip(),
        "review_reason_params": {
            **_normalize_review_reason_params(secondary.get("review_reason_params")),
            **_normalize_review_reason_params(preferred.get("review_reason_params")),
        },
        "review_state": "review"
        if bool(preferred.get("needs_review")) or bool(secondary.get("needs_review"))
        else "canonical",
    }


def _merge_gender_signal(left: str | None, right: str | None) -> str:
    left_signal = _normalize_gender_signal(left)
    right_signal = _normalize_gender_signal(right)
    if left_signal == right_signal:
        return left_signal
    if left_signal == "unknown":
        return right_signal
    if right_signal == "unknown":
        return left_signal
    return "mixed"


def _names_for_overlap(entity: dict[str, Any]) -> set[str]:
    rejected = {normalize_entity_key(name) for name in (entity.get("rejected_aliases") or []) if normalize_entity_text(name)}
    names = [entity.get("canonical_name") or ""]
    if _normalize_naming_quality(entity.get("naming_quality")) != "pronoun_like":
        names.extend(entity.get("aliases") or [])
        names.extend(entity.get("source_mentions") or [])
    return {
        normalize_entity_key(name)
        for name in names
        if normalize_entity_text(name) and normalize_entity_key(name) not in rejected
    }


def _coalesce_same_kind_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = list(entities)
    consumed: set[int] = set()
    merged: list[dict[str, Any]] = []
    for index, entity in enumerate(ordered):
        if index in consumed:
            continue
        current = entity
        current_names = _names_for_overlap(current)
        for other_index in range(index + 1, len(ordered)):
            if other_index in consumed:
                continue
            other = ordered[other_index]
            if str(current.get("entity_kind") or "") != str(other.get("entity_kind") or ""):
                continue
            other_names = _names_for_overlap(other)
            overlap = current_names & other_names
            if not overlap:
                continue
            if (
                _has_strong_named_identity(current)
                and _has_strong_named_identity(other)
                and normalize_entity_key(current.get("canonical_name") or "") != normalize_entity_key(other.get("canonical_name") or "")
                and _overlap_is_descriptor_only(overlap, current, other)
            ):
                continue
            if (
                not _gender_signals_compatible(current, other)
                and _overlap_is_descriptor_only(overlap, current, other)
            ):
                continue
            if any(
                _QUALITY_RANK.get(str(candidate.get("naming_quality") or "unknown"), 0) >= _QUALITY_RANK["proper_name"]
                for candidate in (current, other)
            ) or overlap:
                current = _merge_resolved_pair(current, other)
                current_names = _names_for_overlap(current)
                consumed.add(other_index)
        merged.append(current)
    return merged


def _enforce_cross_kind_priority(entities: list[dict[str, Any]], *, language: str) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for entity in entities:
        names = _names_for_overlap(entity)
        entity_kind = str(entity.get("entity_kind") or "")
        naming_quality = str(entity.get("naming_quality") or "unknown")
        stronger_character = None
        for candidate in entities:
            if candidate is entity:
                continue
            if str(candidate.get("entity_kind") or "") != "character":
                continue
            if str(candidate.get("naming_quality") or "unknown") not in {"proper_name", "title_plus_name"}:
                continue
            if names & _names_for_overlap(candidate):
                if stronger_character is None or _entity_strength(candidate) > _entity_strength(stronger_character):
                    stronger_character = candidate
        if stronger_character and entity_kind != "character":
            review_reason_code = "type_conflict_stronger_identity"
            review_reason_params = {
                "stronger_identity": normalize_entity_text(stronger_character.get("canonical_name") or ""),
            }
            adjusted.append(
                {
                    **entity,
                    "needs_review": True,
                    "review_state": "review",
                    "review_reason_code": review_reason_code,
                    "review_reason_params": review_reason_params,
                    "review_reason": _render_review_reason(
                        code=review_reason_code,
                        params=review_reason_params,
                        language=language,
                    ),
                }
            )
            continue
        if stronger_character and entity_kind == "character" and naming_quality == "descriptor":
            review_reason_code = "descriptor_cluster_overlaps_named_character"
            review_reason_params = {
                "stronger_identity": normalize_entity_text(stronger_character.get("canonical_name") or ""),
            }
            adjusted.append(
                {
                    **entity,
                    "needs_review": True,
                    "review_state": "review",
                    "review_reason_code": review_reason_code,
                    "review_reason_params": review_reason_params,
                    "review_reason": _render_review_reason(
                        code=review_reason_code,
                        params=review_reason_params,
                        language=language,
                    ),
                }
            )
            continue
        adjusted.append(entity)
    return adjusted


def resolve_entity_clusters(
    *,
    global_data: dict[str, Any],
    chapter_outputs: list[dict[str, Any]],
    language: str = "unknown",
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    observations = _collect_global_observations(global_data) + _collect_chapter_observations(chapter_outputs)
    observations = _apply_title_hint_identity_bridges(observations, chapter_outputs)
    cluster_map: dict[str, list[dict[str, Any]]] = {}
    alias_index: dict[str, str] = {}
    for observation in observations:
        names = _identity_bridge_names(observation)
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
        review_reason_codes: list[str] = []
        review_reason_params_list: list[dict[str, str]] = []
        confidence_values: list[float] = []
        stable_votes = 0
        review_votes = 0
        preferred_slug = ""
        preferred_slug_by_name: dict[str, str] = {}

        for item in cluster_items:
            canonical_names = [
                normalize_entity_text(value)
                for value in [item.get("canonical_name"), item.get("canonical_candidate")]
                if normalize_entity_text(value)
            ]
            surface_names = [
                normalize_entity_text(value)
                for value in (item.get("surface_forms") or [])
                if normalize_entity_text(value)
            ]
            quality = _normalize_naming_quality(item.get("naming_quality"))
            confidence = float(item.get("confidence") or 0.0)
            confidence_values.append(confidence)
            if not preferred_slug:
                preferred_slug = str(item.get("preferred_slug") or "").strip()
            stable_votes += 1 if item.get("is_stable_entity") else 0
            review_votes += 1 if item.get("needs_review") else 0
            if item.get("review_reason"):
                review_reasons.append(str(item["review_reason"]))
            code = _normalize_review_reason_code(item.get("review_reason_code"))
            if code:
                review_reason_codes.append(code)
            params = _normalize_review_reason_params(item.get("review_reason_params"))
            if params:
                review_reason_params_list.append(params)
            names_with_role = [(name, True) for name in canonical_names] + [(name, False) for name in surface_names]
            for name, is_canonical_role in names_with_role:
                normalized_name = normalize_entity_text(name)
                if not normalized_name:
                    continue
                bucket = variant_bucket.setdefault(
                    normalized_name,
                    {
                        "name": normalized_name,
                        "naming_quality": quality,
                        "support_count": 0,
                        "canonical_support_count": 0,
                        "global_canonical_support_count": 0,
                        "chapter_canonical_support_count": 0,
                        "chapter_refs": set(),
                        "confidence_total": 0.0,
                        "preferred_slug": "",
                    },
                )
                if _QUALITY_RANK.get(quality, 0) > _QUALITY_RANK.get(str(bucket["naming_quality"]), 0):
                    bucket["naming_quality"] = quality
                bucket["support_count"] += 1
                bucket["confidence_total"] += confidence
                if is_canonical_role:
                    bucket["canonical_support_count"] += 1
                    if str(item.get("source") or "") == "global":
                        bucket["global_canonical_support_count"] += 1
                    if str(item.get("source") or "") == "chapter":
                        bucket["chapter_canonical_support_count"] += 1
                    item_preferred_slug = str(item.get("preferred_slug") or "").strip()
                    if item_preferred_slug and not bucket["preferred_slug"]:
                        bucket["preferred_slug"] = item_preferred_slug
                        preferred_slug_by_name[normalized_name] = item_preferred_slug
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
                "canonical_support_count": data["canonical_support_count"],
                "global_canonical_support_count": data["global_canonical_support_count"],
                "chapter_canonical_support_count": data["chapter_canonical_support_count"],
                "chapter_coverage": len(data["chapter_refs"]),
                "avg_confidence": data["confidence_total"] / max(data["support_count"], 1),
                "preferred_slug": data.get("preferred_slug") or "",
            }
            for data in variant_bucket.values()
        ]
        final_canonical_name, final_quality = _pick_best_name(ranked_variants)
        if not final_canonical_name:
            continue
        final_preferred_slug = preferred_slug_by_name.get(final_canonical_name) or next(
            (str(item.get("preferred_slug") or "").strip() for item in ranked_variants if item.get("name") == final_canonical_name),
            "",
        )

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
        gender_summary = _derive_gender_signal(cluster_items)
        is_stable_entity = stable_votes > 0 or len(chapter_refs) >= 2 or len(merged_relationships) >= 1 or len(facts) >= 2
        needs_review = review_votes > 0 or final_quality in {"descriptor", "pronoun_like", "unknown"}
        strong_primary_candidate = (
            final_quality == "proper_name"
            and len(chapter_refs) >= 3
            and len(set(chapter_refs)) >= 3
            and bool(final_canonical_name)
        )
        review_reason = ""
        review_reason_code = ""
        review_reason_params: dict[str, str] = {}
        if needs_review:
            if review_reason_codes:
                review_reason_code = review_reason_codes[0]
                review_reason_params = review_reason_params_list[0] if review_reason_params_list else {}
                review_reason = _render_review_reason(
                    code=review_reason_code,
                    params=review_reason_params,
                    language=language,
                )
            elif review_reasons:
                review_reason = review_reasons[0]
            else:
                review_reason_code = "weak_or_descriptive_naming"
                review_reason = _render_review_reason(
                    code=review_reason_code,
                    params={},
                    language=language,
                )

        resolved_entities.append(
            {
                "canonical_name": final_canonical_name,
                "canonical_candidate": final_canonical_name,
                "entity_kind": entity_kind,
                "preferred_slug": final_preferred_slug or preferred_slug or _preferred_slug_for_name(final_canonical_name),
                "aliases": accepted_aliases,
                "rejected_aliases": rejected_aliases,
                "summary": summaries[0] if summaries else "",
                "key_facts": facts[:5],
                "relationships": merged_relationships[:5],
                "chapter_refs": chapter_refs,
                "source_mentions": source_mentions,
                "confidence": round(confidence, 4),
                "gender_presentation_signal": gender_summary["gender_presentation_signal"],
                "gender_signal_confidence": gender_summary["gender_signal_confidence"],
                "gender_signal_evidence": gender_summary["gender_signal_evidence"],
                "gender_signal_conflict": gender_summary["gender_signal_conflict"],
                "gender_signal_downgraded": gender_summary["gender_signal_downgraded"],
                "strong_primary_candidate": strong_primary_candidate,
                "review_state": "review" if needs_review else "canonical",
                "naming_quality": final_quality,
                "is_stable_entity": is_stable_entity,
                "needs_review": needs_review,
                "review_reason_code": review_reason_code,
                "review_reason_params": review_reason_params,
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
                "review_reason_code": review_reason_code,
                "review_reason_params": review_reason_params,
                "review_reason": review_reason,
                "confidence": round(confidence, 4),
                "gender_presentation_signal": gender_summary["gender_presentation_signal"],
                "gender_signal_confidence": gender_summary["gender_signal_confidence"],
                "gender_signal_evidence": gender_summary["gender_signal_evidence"],
                "gender_signal_conflict": gender_summary["gender_signal_conflict"],
                "gender_signal_downgraded": gender_summary["gender_signal_downgraded"],
                "strong_primary_candidate": strong_primary_candidate,
            }
        )

    resolved_entities = _coalesce_same_kind_entities(resolved_entities)
    resolved_entities = _enforce_cross_kind_priority(resolved_entities, language=language)
    resolved_entities.sort(key=lambda item: (str(item.get("entity_kind") or ""), str(item.get("canonical_name") or "").lower()))
    return (
        resolved_entities,
        {"cluster_count": len(clusters_audit), "clusters": clusters_audit},
        {"resolved_entity_count": len(resolved_entities), "resolutions": resolution_audit},
    )
