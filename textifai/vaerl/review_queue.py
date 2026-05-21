from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vault.schema import slugify


def build_review_queue(
    *,
    obsidian_import: dict[str, Any],
    semantic_invariants_audit: dict[str, Any] | None = None,
    retention_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entities = [item for item in obsidian_import.get("entities") or [] if isinstance(item, dict)]
    primaries = [item for item in entities if _is_primary(item)]
    reviews = [item for item in entities if not _is_primary(item)]
    primary_index = _reference_index(primaries)
    review_index = _reference_index(reviews)

    items: list[dict[str, Any]] = []
    items.extend(_review_entity_items(reviews=reviews, primaries=primaries))
    items.extend(_absorbed_semantic_surface_items(primaries=primaries, retention_context=retention_context or {}))
    items.extend(_unresolved_relationship_items(primaries=primaries, primary_index=primary_index, review_index=review_index))
    items.extend(_ontological_collision_items(primaries=primaries))
    items.extend(_weak_canonical_items(primaries=primaries))
    items.extend(_orphan_primary_items(primaries=primaries))
    items.extend(_retention_signal_items(primaries=primaries, retention_context=retention_context or {}))
    items.extend(_invariant_items(semantic_invariants_audit or {}))

    deduped = _dedupe_items(items)
    for item in deduped:
        item["review_item_id"] = _review_item_id(item)
    deduped.sort(key=lambda item: (_severity_rank(item.get("severity")), str(item.get("review_type") or ""), str(item.get("review_item_id") or "")))
    counts_by_type: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for item in deduped:
        counts_by_type[str(item.get("review_type") or "unknown")] = counts_by_type.get(str(item.get("review_type") or "unknown"), 0) + 1
        counts_by_severity[str(item.get("severity") or "unknown")] = counts_by_severity.get(str(item.get("severity") or "unknown"), 0) + 1
    return {
        "schema_version": "textifai.review_queue.v1",
        "status": "ready_for_author_review" if deduped else "empty",
        "item_count": len(deduped),
        "counts_by_type": counts_by_type,
        "counts_by_severity": counts_by_severity,
        "items": deduped,
        "policy": {
            "pending_reviews_are_expected": True,
            "can_auto_apply_default": False,
            "notes": [
                "The goal is not zero pending reviews.",
                "Each item should carry enough metadata for author-assisted merge, rejection, promotion, or confirmation.",
            ],
        },
    }


def write_review_queue(
    *,
    output_path: str | Path,
    obsidian_import: dict[str, Any] | None = None,
    obsidian_import_path: str | Path | None = None,
    semantic_invariants_audit: dict[str, Any] | None = None,
    semantic_invariants_audit_path: str | Path | None = None,
    retention_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if obsidian_import is None:
        if obsidian_import_path is None:
            raise ValueError("obsidian_import or obsidian_import_path is required")
        obsidian_import = json.loads(Path(obsidian_import_path).read_text(encoding="utf-8"))
    if semantic_invariants_audit is None and semantic_invariants_audit_path is not None:
        path = Path(semantic_invariants_audit_path)
        if path.exists():
            semantic_invariants_audit = json.loads(path.read_text(encoding="utf-8"))
    queue = build_review_queue(
        obsidian_import=obsidian_import,
        semantic_invariants_audit=semantic_invariants_audit,
        retention_context=retention_context,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return queue


def _review_entity_items(*, reviews: list[dict[str, Any]], primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for review in reviews:
        candidates = _candidate_entities_for_review(review, primaries)
        confidence = _safe_float(review.get("confidence"))
        naming_quality = str(review.get("naming_quality") or "unknown").strip().casefold()
        normalized_object_retention = _normalized_object_retention_item(
            review=review,
            candidate_entities=candidates,
            confidence=confidence,
        )
        if normalized_object_retention is not None:
            items.append(normalized_object_retention)
            continue
        severity = "medium" if candidates or confidence >= 0.65 else "low"
        items.append(
            _item(
                review_type="review_entity",
                severity=severity,
                suggested_action="merge_into_primary_or_keep_review",
                source_entity=review.get("canonical_name") or "",
                target_text=review.get("canonical_name") or "",
                candidate_entities=candidates,
                evidence=[
                    *_evidence("key_fact", review.get("key_facts") or [], limit=3),
                    *_evidence("source_mention", review.get("source_mentions") or [], limit=3),
                ],
                confidence=confidence,
                metadata={
                    "entity_kind": review.get("entity_kind") or "",
                    "preferred_slug": review.get("preferred_slug") or "",
                    "naming_quality": naming_quality,
                    "review_reason": review.get("review_reason") or "",
                    "review_reason_code": review.get("review_reason_code") or "",
                    "relationship_count": len([rel for rel in review.get("relationships") or [] if isinstance(rel, dict)]),
                },
            )
        )
    return items

def _normalized_object_retention_item(
    *,
    review: dict[str, Any],
    candidate_entities: list[dict[str, Any]],
    confidence: float,
) -> dict[str, Any] | None:
    entity_kind = str(review.get("entity_kind") or "").strip().casefold()
    if entity_kind != "object":
        return None
    if _is_forbidden_ephemeral_retention_candidate(review):
        return None
    if not _has_retention_weight(review):
        return None
    top_score = _safe_float(candidate_entities[0].get("score")) if candidate_entities else 0.0
    if top_score >= 0.85:
        return None
    recommended_action = "review_create_primary" if not candidate_entities else "review_keep_secondary"
    candidate_status = _candidate_status(discarded_entity=review, candidate_entities=candidate_entities)
    return _item(
        review_type="entity_retention_review",
        severity="medium",
        suggested_action=recommended_action,
        source_entity=review.get("canonical_name") or "",
        target_text=review.get("canonical_name") or "",
        candidate_entities=candidate_entities,
        evidence=[
            *_evidence("key_fact", review.get("key_facts") or [], limit=3),
            *_evidence("source_mention", review.get("source_mentions") or [], limit=3),
        ],
        confidence=confidence,
        metadata={
            "entity_kind": review.get("entity_kind") or "",
            "preferred_slug": review.get("preferred_slug") or "",
            "naming_quality": str(review.get("naming_quality") or "unknown").strip().casefold(),
            "review_reason": review.get("review_reason") or "",
            "review_reason_code": review.get("review_reason_code") or "",
            "relationship_count": len([rel for rel in review.get("relationships") or [] if isinstance(rel, dict)]),
            "chapter_refs": list(review.get("chapter_refs") or []),
            "decision_reason": review.get("review_reason") or review.get("review_reason_code") or "durable_object_review_entity_normalized",
            "recommended_action": recommended_action,
            "signal_tier": "medium",
            "candidate_status": candidate_status,
            "do_not_auto_merge": True,
            "no_clear_existing_primary": not bool(candidate_entities),
            "retention_review_required": True,
            "language_hint": review.get("language_hint") or "",
            "surface_type": _surface_type(review),
            "semantic_value": _semantic_value(review),
            "future_viewer_actions": ["promote", "keep_secondary", "reject_noise"],
        },
    )


def _unresolved_relationship_items(
    *,
    primaries: list[dict[str, Any]],
    primary_index: dict[str, Any],
    review_index: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for primary in primaries:
        for rel in primary.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            target = str(rel.get("target") or "").strip()
            if not target or _resolve_key(target, primary_index):
                continue
            candidate_reviews = _candidate_entities_for_target(target, review_index)
            items.append(
                _item(
                    review_type="unresolved_relationship_target",
                    severity="medium" if candidate_reviews else "low",
                    suggested_action="resolve_target_or_keep_unmaterialized",
                    source_entity=primary.get("canonical_name") or "",
                    target_text=target,
                    candidate_entities=candidate_reviews,
                    evidence=_evidence("relationship_fact", rel.get("facts") or [], limit=3),
                    confidence=0.0,
                    metadata={
                        "relationship_type": rel.get("type") or rel.get("relation_type") or "",
                        "source_entity_kind": primary.get("entity_kind") or "",
                        "candidate_count": len(candidate_reviews),
                    },
                )
            )
    return items


def _ontological_collision_items(*, primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for primary in primaries:
        slug = str(primary.get("preferred_slug") or "").strip()
        if slug:
            by_slug.setdefault(slug, []).append(primary)
    items: list[dict[str, Any]] = []
    for slug, group in by_slug.items():
        kinds = sorted({str(item.get("entity_kind") or "").strip().casefold() for item in group if item.get("entity_kind")})
        if len(group) <= 1 or len(kinds) <= 1:
            continue
        items.append(
            _item(
                review_type="ontological_collision",
                severity="medium",
                suggested_action="confirm_separate_facets_or_disambiguate_slug",
                source_entity=group[0].get("canonical_name") or "",
                target_text=slug,
                candidate_entities=[_candidate(item, reason="same_slug_cross_kind", score=0.8) for item in group],
                evidence=[],
                confidence=0.8,
                metadata={"preferred_slug": slug, "entity_kinds": kinds},
            )
        )
    return items


def _weak_canonical_items(*, primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for primary in primaries:
        quality = str(primary.get("naming_quality") or "").strip().casefold()
        if quality not in {"descriptor", "pronoun_like", "unknown"}:
            continue
        stronger = [value for value in [*(primary.get("aliases") or []), *(primary.get("source_mentions") or [])] if _looks_specific(value)]
        if not stronger:
            continue
        items.append(
            _item(
                review_type="weak_canonical_name",
                severity="medium",
                suggested_action="rename_canonical_or_confirm_descriptor",
                source_entity=primary.get("canonical_name") or "",
                target_text=primary.get("canonical_name") or "",
                candidate_entities=[{"canonical_name": value, "reason": "specific_alias_or_source_mention", "score": 0.75} for value in sorted(set(stronger))[:5]],
                evidence=_evidence("alias_or_source_mention", stronger, limit=5),
                confidence=0.75,
                metadata={"naming_quality": quality, "preferred_slug": primary.get("preferred_slug") or ""},
            )
        )
    return items


def _orphan_primary_items(*, primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for primary in primaries:
        relationships = [rel for rel in primary.get("relationships") or [] if isinstance(rel, dict)]
        facts = [fact for fact in primary.get("key_facts") or [] if str(fact or "").strip()]
        source_refs = primary.get("source_refs") or []
        chapter_refs = primary.get("chapter_refs") or []
        if relationships or facts or source_refs or chapter_refs:
            continue
        items.append(
            _item(
                review_type="orphan_primary",
                severity="high",
                suggested_action="demote_or_add_evidence",
                source_entity=primary.get("canonical_name") or "",
                target_text=primary.get("canonical_name") or "",
                candidate_entities=[],
                evidence=[],
                confidence=0.0,
                metadata={"entity_kind": primary.get("entity_kind") or "", "preferred_slug": primary.get("preferred_slug") or ""},
                blocking_phase1_gate=True,
            )
        )
    return items


def _invariant_items(audit: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for check in audit.get("checks") or []:
        if not isinstance(check, dict) or check.get("status") not in {"fail", "warn"}:
            continue
        name = str(check.get("name") or "")
        if name in {
            "ontological_name_collisions",
            "relationship_targets_resolve_to_primary",
            "unlinked_primary_mentions",
            "suspicious_orphan_primaries",
            "canonical_name_not_weaker_than_available_alias",
        }:
            continue
        items.append(
            _item(
                review_type=f"invariant_{name}",
                severity="high" if check.get("status") == "fail" else "medium",
                suggested_action="inspect_invariant_failure",
                source_entity="",
                target_text=name,
                candidate_entities=[],
                evidence=[],
                confidence=0.0,
                metadata={"check_name": name, "check_status": check.get("status"), "details": check.get("details") or {}},
                blocking_phase1_gate=check.get("status") == "fail",
            )
        )
    return items


def _retention_signal_items(*, primaries: list[dict[str, Any]], retention_context: dict[str, Any]) -> list[dict[str, Any]]:
    discarded = _collect_discarded_entities(retention_context=retention_context)
    if not discarded:
        return []
    primary_index = _reference_index(primaries)
    items: list[dict[str, Any]] = []
    for discarded_entity in discarded:
        if _is_forbidden_ephemeral_retention_candidate(discarded_entity):
            continue
        if _resolve_key(str(discarded_entity.get("canonical_name") or ""), primary_index):
            continue
        candidate_entities = _retention_candidates_for_entity(discarded_entity=discarded_entity, primaries=primaries)
        signal_tier = _retention_signal_tier(
            discarded_entity=discarded_entity,
            candidate_entities=candidate_entities,
        )
        recommended_action = _recommended_retention_action(
            discarded_entity=discarded_entity,
            candidate_entities=candidate_entities,
        )
        if not recommended_action or signal_tier == "suppressed":
            continue
        candidate_status = _candidate_status(
            discarded_entity=discarded_entity,
            candidate_entities=candidate_entities,
        )
        items.append(
            _item(
                review_type="entity_retention_review",
                severity=_tier_to_severity(signal_tier),
                suggested_action=recommended_action,
                source_entity=discarded_entity.get("canonical_name") or "",
                target_text=discarded_entity.get("canonical_name") or "",
                candidate_entities=candidate_entities,
                evidence=[
                    *_evidence("key_fact", discarded_entity.get("key_facts") or [], limit=3),
                    *_evidence("source_mention", discarded_entity.get("source_mentions") or [], limit=3),
                ],
                confidence=_safe_float(discarded_entity.get("confidence")),
                metadata={
                    "entity_kind": discarded_entity.get("entity_kind") or "",
                    "naming_quality": discarded_entity.get("naming_quality") or "",
                    "chapter_refs": list(discarded_entity.get("chapter_refs") or []),
                    "decision_reason": discarded_entity.get("_retention_decision_reason") or "",
                    "recommended_action": recommended_action,
                    "signal_tier": signal_tier,
                    "candidate_status": candidate_status,
                    "do_not_auto_merge": True,
                    "no_clear_existing_primary": not bool(candidate_entities),
                    "retention_review_required": True,
                    "language_hint": discarded_entity.get("language_hint") or "",
                    "surface_type": _surface_type(discarded_entity),
                    "semantic_value": _semantic_value(discarded_entity),
                    "future_viewer_actions": _future_viewer_actions(recommended_action),
                },
            )
        )
    return items

def _absorbed_semantic_surface_items(*, primaries: list[dict[str, Any]], retention_context: dict[str, Any]) -> list[dict[str, Any]]:
    primary_index = _reference_index(primaries)
    items: list[dict[str, Any]] = []
    for entity in _semantic_surface_review_candidates(retention_context=retention_context):
        if _is_forbidden_ephemeral_retention_candidate(entity):
            continue
        if _surface_type(entity) == "pronoun_like":
            continue
        if not _resolve_key(str(entity.get("canonical_name") or ""), primary_index):
            continue
        candidate_entities = _retention_candidates_for_entity(discarded_entity=entity, primaries=primaries)
        if not candidate_entities:
            continue
        item = _normalized_absorbed_semantic_surface_item(
            entity=entity,
            candidate_entities=candidate_entities,
        )
        if item is not None:
            items.append(item)
    return items


def _retention_candidates_for_entity(*, discarded_entity: dict[str, Any], primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _is_pronoun_like_entity(discarded_entity):
        return []
    candidates = _candidate_entities_for_review(discarded_entity, primaries)
    for candidate in candidates:
        candidate["confidence_bucket"] = _confidence_bucket(_safe_float(candidate.get("score")))
    return candidates[:4]


def _recommended_retention_action(*, discarded_entity: dict[str, Any], candidate_entities: list[dict[str, Any]]) -> str:
    naming_quality = str(discarded_entity.get("naming_quality") or "").strip().casefold()
    entity_kind = str(discarded_entity.get("entity_kind") or "").strip().casefold()
    surface_type = _surface_type(discarded_entity)
    if surface_type == "pronoun_like":
        return ""
    if candidate_entities:
        if surface_type in {"descriptor_like", "title_like", "role_like"} or naming_quality in {"descriptor", "title_like", "role_like"}:
            return "review_attach_role_or_title"
        return "review_merge_or_alias"
    if entity_kind in _durable_entity_kinds() and _has_retention_weight(discarded_entity):
        return "review_create_primary"
    if _has_retention_weight(discarded_entity):
        return "review_keep_secondary"
    return ""

def _semantic_surface_review_candidates(*, retention_context: dict[str, Any]) -> list[dict[str, Any]]:
    resolved_entities = [item for item in (retention_context.get("resolved_entities") or []) if isinstance(item, dict)]
    global_entities = [item for item in (retention_context.get("global_entities") or []) if isinstance(item, dict)]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entity in [*resolved_entities, *global_entities]:
        surface_type = _surface_type(entity)
        if surface_type not in {"title_like", "role_like", "descriptor_like"}:
            continue
        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not canonical_name:
            continue
        key = _key(canonical_name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(entity)
    return out

def _normalized_absorbed_semantic_surface_item(
    *,
    entity: dict[str, Any],
    candidate_entities: list[dict[str, Any]],
) -> dict[str, Any] | None:
    recommended_action = _recommended_absorbed_surface_action(
        entity=entity,
        candidate_entities=candidate_entities,
    )
    if not recommended_action:
        return None
    candidate_status = _candidate_status(discarded_entity=entity, candidate_entities=candidate_entities)
    signal_tier = _absorbed_surface_signal_tier(entity=entity, candidate_entities=candidate_entities)
    return _item(
        review_type="entity_retention_review",
        severity=_tier_to_severity(signal_tier),
        suggested_action=recommended_action,
        source_entity=entity.get("canonical_name") or "",
        target_text=entity.get("canonical_name") or "",
        candidate_entities=candidate_entities,
        evidence=[
            *_evidence("key_fact", entity.get("key_facts") or [], limit=3),
            *_evidence("source_mention", entity.get("source_mentions") or [], limit=3),
            *_evidence("chapter_ref", entity.get("chapter_refs") or [], limit=3),
        ],
        confidence=_safe_float(entity.get("confidence")),
        metadata={
            "entity_kind": entity.get("entity_kind") or "",
            "preferred_slug": entity.get("preferred_slug") or "",
            "naming_quality": str(entity.get("naming_quality") or "unknown").strip().casefold(),
            "review_reason": entity.get("review_reason") or "",
            "review_reason_code": entity.get("review_reason_code") or "",
            "relationship_count": len([rel for rel in entity.get("relationships") or [] if isinstance(rel, dict)]),
            "chapter_refs": list(entity.get("chapter_refs") or []),
            "decision_reason": _absorbed_surface_decision_reason(entity=entity, recommended_action=recommended_action),
            "recommended_action": recommended_action,
            "signal_tier": signal_tier,
            "candidate_status": candidate_status,
            "do_not_auto_merge": True,
            "no_clear_existing_primary": False,
            "retention_review_required": True,
            "language_hint": entity.get("language_hint") or "",
            "surface_type": _surface_type(entity),
            "semantic_value": _semantic_value(entity),
            "future_viewer_actions": _future_viewer_actions(recommended_action),
        },
    )

def _recommended_absorbed_surface_action(*, entity: dict[str, Any], candidate_entities: list[dict[str, Any]]) -> str:
    if not candidate_entities:
        return ""
    if _safe_float(candidate_entities[0].get("score")) < 0.6:
        return ""
    surface_type = _surface_type(entity)
    if surface_type in {"title_like", "role_like"}:
        return "review_attach_role_or_title" if _has_min_semantic_surface_evidence(entity) else ""
    if surface_type == "descriptor_like":
        return "review_enrich_existing_entity" if _has_descriptor_enrichment_signal_value(entity) else ""
    return ""

def _has_min_semantic_surface_evidence(entity: dict[str, Any]) -> bool:
    return bool((entity.get("source_mentions") or []) or (entity.get("key_facts") or []) or (entity.get("chapter_refs") or []))

def _has_descriptor_enrichment_signal_value(entity: dict[str, Any]) -> bool:
    if not _has_min_semantic_surface_evidence(entity):
        return False
    metrics = entity.get("_metrics") or {}
    fact_count = max(len(entity.get("key_facts") or []), int(metrics.get("fact_count") or 0))
    chapter_ref_count = max(len(entity.get("chapter_refs") or []), int(metrics.get("chapter_ref_count") or 0))
    confidence = _safe_float(entity.get("confidence"))
    return fact_count >= 2 or chapter_ref_count >= 2 or confidence >= 0.74

def _absorbed_surface_signal_tier(*, entity: dict[str, Any], candidate_entities: list[dict[str, Any]]) -> str:
    if not candidate_entities:
        return "suppressed"
    top_score = _safe_float(candidate_entities[0].get("score"))
    if top_score >= 0.85 and _surface_type(entity) in {"title_like", "role_like"}:
        return "high"
    return "medium"

def _absorbed_surface_decision_reason(*, entity: dict[str, Any], recommended_action: str) -> str:
    if recommended_action == "review_attach_role_or_title":
        return "absorbed_title_or_role_surface_requires_editorial_attachment"
    if recommended_action == "review_enrich_existing_entity":
        return "absorbed_descriptor_surface_contains_non_trivial_enrichment_evidence"
    return str(entity.get("review_reason") or entity.get("review_reason_code") or "absorbed_semantic_surface_requires_review")


def _collect_discarded_entities(*, retention_context: dict[str, Any]) -> list[dict[str, Any]]:
    promotion_decisions = [item for item in (retention_context.get("promotion_decisions") or []) if isinstance(item, dict)]
    resolved_entities = [item for item in (retention_context.get("resolved_entities") or []) if isinstance(item, dict)]
    global_entities = [item for item in (retention_context.get("global_entities") or []) if isinstance(item, dict)]
    by_key: dict[str, dict[str, Any]] = {}
    for source_entity in [*resolved_entities, *global_entities]:
        key = _key(source_entity.get("canonical_name"))
        if key and key not in by_key:
            by_key[key] = source_entity

    discarded: list[dict[str, Any]] = []
    for decision in promotion_decisions:
        if str(decision.get("decision") or "").strip().casefold() != "discard":
            continue
        canonical_name = str(decision.get("canonical_name") or "")
        base = by_key.get(_key(canonical_name)) or {}
        metrics = decision.get("metrics") or {}
        discarded.append(
            {
                "canonical_name": canonical_name,
                "entity_kind": decision.get("entity_kind") or base.get("entity_kind") or "",
                "preferred_slug": base.get("preferred_slug") or _key(canonical_name),
                "aliases": list(base.get("aliases") or []),
                "source_mentions": list(base.get("source_mentions") or []),
                "key_facts": list(base.get("key_facts") or []),
                "chapter_refs": list(base.get("chapter_refs") or []),
                "relationships": list(base.get("relationships") or []),
                "review_state": base.get("review_state") or "review",
                "confidence": base.get("confidence") if base.get("confidence") is not None else 0.0,
                "naming_quality": decision.get("naming_quality") or base.get("naming_quality") or "",
                "surface_type": decision.get("surface_type") or base.get("surface_type") or "",
                "language_hint": decision.get("language_hint") or base.get("language_hint") or "",
                "_retention_decision_reason": decision.get("reason") or "",
                "_metrics": metrics,
            }
        )
    return discarded


def _candidate_entities_for_review(review: dict[str, Any], primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review_terms = _entity_terms(review)
    review_keys = {_key(term) for term in review_terms if _key(term)}
    review_kind = str(review.get("entity_kind") or "").strip().casefold()
    candidates: list[dict[str, Any]] = []
    for primary in primaries:
        score = 0.0
        reasons: list[str] = []
        primary_terms = _entity_terms(primary)
        primary_keys = {_key(term) for term in primary_terms if _key(term)}
        overlap = sorted(review_keys & primary_keys)
        if overlap:
            score += 0.7
            reasons.append("exact_alias_or_source_overlap")
        if review_kind and review_kind == str(primary.get("entity_kind") or "").strip().casefold():
            score += 0.1
        similarity = _name_similarity(review.get("canonical_name") or "", primary.get("canonical_name") or "")
        if similarity >= 0.85:
            score += 0.4
            reasons.append("similar_canonical_name")
        elif similarity >= 0.72:
            score += 0.2
            reasons.append("weak_name_similarity")
        if score > 0.19:
            candidates.append(_candidate(primary, reason=",".join(reasons) or "same_kind_low_signal", score=min(score, 1.0)))
    candidates.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("canonical_name") or "")))
    return candidates[:5]


def _candidate_entities_for_target(target: str, index: dict[str, Any]) -> list[dict[str, Any]]:
    target_key = _key(target)
    candidates_by_key: dict[str, dict[str, Any]] = {}
    exact_key = index["term_to_entity_key"].get(target_key)
    if exact_key:
        entity = index["entities_by_key"][exact_key]
        candidates_by_key[exact_key] = _candidate(entity, reason="exact_target_matches_review_entity", score=1.0)
    target_tokens = _significant_tokens(target_key)
    if target_tokens:
        for entity_key, entity in index["entities_by_key"].items():
            if exact_key == entity_key:
                continue
            best = max((_token_overlap(target_tokens, _significant_tokens(_key(term))) for term in _entity_terms(entity)), default=0.0)
            if best >= 0.5:
                candidate = _candidate(entity, reason="partial_target_overlap", score=round(min(best, 0.79), 3))
                current = candidates_by_key.get(entity_key)
                if current is None or float(candidate["score"]) > float(current["score"]):
                    candidates_by_key[entity_key] = candidate
    candidates = list(candidates_by_key.values())
    candidates.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("canonical_name") or "")))
    return candidates[:5]


def _reference_index(entities: list[dict[str, Any]]) -> dict[str, Any]:
    entities_by_key: dict[str, dict[str, Any]] = {}
    term_to_entity_key: dict[str, str] = {}
    for entity in entities:
        entity_key = _key(entity.get("preferred_slug") or entity.get("canonical_name") or "")
        if not entity_key:
            continue
        entities_by_key[entity_key] = entity
        for term in _entity_terms(entity):
            term_key = _key(term)
            if term_key:
                term_to_entity_key.setdefault(term_key, entity_key)
    return {"entities_by_key": entities_by_key, "term_to_entity_key": term_to_entity_key}


def _resolve_key(value: str, index: dict[str, Any]) -> str:
    key = _key(value)
    return key if key in index["entities_by_key"] else index["term_to_entity_key"].get(key, "")


def _entity_terms(entity: dict[str, Any]) -> list[str]:
    values = [entity.get("canonical_name") or "", entity.get("preferred_slug") or "", *(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _candidate(entity: dict[str, Any], *, reason: str, score: float) -> dict[str, Any]:
    return {
        "canonical_name": entity.get("canonical_name") or "",
        "preferred_slug": entity.get("preferred_slug") or "",
        "entity_kind": entity.get("entity_kind") or "",
        "review_state": entity.get("review_state") or "",
        "reason": reason,
        "score": round(float(score), 3),
    }


def _item(
    *,
    review_type: str,
    severity: str,
    suggested_action: str,
    source_entity: str,
    target_text: str,
    candidate_entities: list[dict[str, Any]],
    evidence: list[dict[str, str]],
    confidence: float,
    metadata: dict[str, Any],
    blocking_phase1_gate: bool = False,
) -> dict[str, Any]:
    return {
        "review_type": review_type,
        "severity": severity,
        "suggested_action": suggested_action,
        "source_entity": str(source_entity or ""),
        "target_text": str(target_text or ""),
        "candidate_entities": candidate_entities,
        "evidence": evidence,
        "confidence": round(float(confidence or 0.0), 3),
        "blocking_phase1_gate": bool(blocking_phase1_gate),
        "can_auto_apply": False,
        "metadata": metadata,
    }


def _evidence(kind: str, values: Any, *, limit: int) -> list[dict[str, str]]:
    if not isinstance(values, list):
        values = [values]
    out: list[dict[str, str]] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            out.append({"kind": kind, "text": text[:500]})
        if len(out) >= limit:
            break
    return out


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(
            {
                "review_type": item.get("review_type"),
                "source_entity": item.get("source_entity"),
                "target_text": item.get("target_text"),
                "suggested_action": item.get("suggested_action"),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _review_item_id(item: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "review_type": item.get("review_type"),
            "source_entity": item.get("source_entity"),
            "target_text": item.get("target_text"),
            "suggested_action": item.get("suggested_action"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"rq_{digest}"


def _severity_rank(value: Any) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(value or "").casefold(), 3)


def _is_primary(entity: dict[str, Any]) -> bool:
    return str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary"


def _key(value: Any) -> str:
    return slugify(str(value or "")).strip("_")


def _looks_specific(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or "_" in text:
        return False
    return any(token[:1].isupper() and any(char.islower() for char in token[1:]) for token in text.split())


def _has_retention_weight(entity: dict[str, Any]) -> bool:
    metrics = entity.get("_metrics") or {}
    chapter_ref_count = max(len(entity.get("chapter_refs") or []), int(metrics.get("chapter_ref_count") or 0))
    fact_count = max(len(entity.get("key_facts") or []), int(metrics.get("fact_count") or 0))
    relationship_count = max(len(entity.get("relationships") or []), int(metrics.get("relationship_count") or 0))
    source_mention_count = max(len(entity.get("source_mentions") or []), int(metrics.get("source_mention_count") or 0))
    return chapter_ref_count >= 2 or fact_count >= 2 or relationship_count >= 1 or source_mention_count >= 2


def _is_forbidden_ephemeral_retention_candidate(entity: dict[str, Any]) -> bool:
    if _is_pronoun_like_entity(entity):
        return True
    if _has_retention_weight(entity):
        return False
    entity_kind = str(entity.get("entity_kind") or "").strip().casefold()
    surface_type = _surface_type(entity)
    if entity_kind == "object":
        return False
    return surface_type in {"descriptor_like", "title_like", "role_like", "pronoun_like"} or entity_kind in {"character", "creature"}


def _durable_entity_kinds() -> set[str]:
    return {"object", "place", "character", "faction", "magic", "concept", "event"}


def _is_pronoun_like(value: Any) -> bool:
    key = _key(value)
    return key in {
        "el",
        "ella",
        "ellas",
        "ellos",
        "lo",
        "la",
        "le",
        "les",
        "he",
        "she",
        "they",
        "them",
        "him",
        "her",
    }


def _is_pronoun_like_entity(entity: dict[str, Any]) -> bool:
    if _surface_type(entity) == "pronoun_like":
        return True
    return _is_pronoun_like(entity.get("canonical_name"))


def _surface_type(entity: dict[str, Any]) -> str:
    explicit = str(entity.get("surface_type") or "").strip().casefold()
    if explicit:
        return explicit
    naming_quality = str(entity.get("naming_quality") or "").strip().casefold()
    if naming_quality == "pronoun_like":
        return "pronoun_like"
    if naming_quality == "descriptor":
        return "descriptor_like"
    if naming_quality in {"title_like", "role_like"}:
        return naming_quality
    entity_kind = str(entity.get("entity_kind") or "").strip().casefold()
    if entity_kind == "object":
        return "object_like"
    if _looks_specific(entity.get("canonical_name")):
        return "named_entity_like"
    return "mention_like"


def _semantic_value(entity: dict[str, Any]) -> str:
    surface_type = _surface_type(entity)
    if surface_type == "object_like":
        return "persistent_object"
    if surface_type in {"descriptor_like", "title_like", "role_like"}:
        return surface_type.removesuffix("_like")
    if surface_type == "pronoun_like":
        return "noise"
    entity_kind = str(entity.get("entity_kind") or "").strip().casefold()
    if entity_kind in _durable_entity_kinds():
        return "durable_entity"
    return "secondary_mention"


def _candidate_status(*, discarded_entity: dict[str, Any], candidate_entities: list[dict[str, Any]]) -> str:
    if _surface_type(discarded_entity) == "pronoun_like":
        return "insufficient_evidence"
    if not candidate_entities:
        return "no_clear_existing_primary" if _has_retention_weight(discarded_entity) else "insufficient_evidence"
    top_score = _safe_float(candidate_entities[0].get("score"))
    return "strong_candidate" if top_score >= 0.85 else "weak_candidate"


def _retention_signal_tier(*, discarded_entity: dict[str, Any], candidate_entities: list[dict[str, Any]]) -> str:
    surface_type = _surface_type(discarded_entity)
    entity_kind = str(discarded_entity.get("entity_kind") or "").strip().casefold()
    if surface_type == "pronoun_like":
        return "suppressed"
    if candidate_entities:
        top_score = _safe_float(candidate_entities[0].get("score"))
        if surface_type in {"descriptor_like", "title_like", "role_like"} and _has_retention_weight(discarded_entity):
            return "high" if top_score >= 0.85 else "medium"
        return "medium" if top_score >= 0.6 else "low"
    if entity_kind in _durable_entity_kinds() and _has_retention_weight(discarded_entity):
        return "medium"
    return "low" if _has_retention_weight(discarded_entity) else "suppressed"


def _tier_to_severity(signal_tier: str) -> str:
    return {"high": "high", "medium": "medium", "low": "low", "suppressed": "low"}.get(signal_tier, "medium")


def _future_viewer_actions(recommended_action: str) -> list[str]:
    if recommended_action == "review_merge_or_alias":
        return ["merge", "mark_alias", "keep_secondary", "reject_noise"]
    if recommended_action == "review_attach_role_or_title":
        return ["attach_role_or_title", "merge", "mark_alias", "keep_secondary", "reject_noise"]
    if recommended_action == "review_create_primary":
        return ["promote", "keep_secondary", "reject_noise"]
    if recommended_action == "review_enrich_existing_entity":
        return ["enrich_existing_entity", "merge", "keep_secondary", "reject_noise"]
    return ["keep_secondary", "reject_noise"]


def _confidence_bucket(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _name_similarity(left: str, right: str) -> float:
    left_key = _key(left)
    right_key = _key(right)
    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0
    left_tokens = set(left_key.split("_"))
    right_tokens = set(right_key.split("_"))
    return _token_overlap(left_tokens, right_tokens)


def _token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


def _significant_tokens(value: str) -> set[str]:
    return {token for token in str(value or "").split("_") if len(token) >= 4}
