from __future__ import annotations

from typing import Any

from textifai.import_review.entity_cluster_resolution import normalize_entity_key, normalize_entity_text


def _extract_title_entity_hints(chapter_title: str) -> list[str]:
    title = normalize_entity_text(chapter_title)
    if not title:
        return []
    if ":" in title:
        title = title.split(":", 1)[1].strip()
    hints: list[str] = []
    for marker in (" de ", " del ", " about ", " of "):
        if marker in title.casefold():
            for fragment in title.split(marker):
                candidate = normalize_entity_text(fragment)
                tokens = candidate.split()
                if tokens and tokens[-1][:1].isupper():
                    last = normalize_entity_text(tokens[-1].rstrip("."))
                    if last and last not in hints:
                        hints.append(last)
    trailing = title.split()
    if trailing and trailing[-1][:1].isupper():
        candidate = normalize_entity_text(trailing[-1].rstrip("."))
        if candidate and candidate not in hints:
            hints.append(candidate)
    return hints


def _title_hit_count(entity_name: str, chapter_outputs: list[dict[str, Any]]) -> int:
    key = normalize_entity_key(entity_name)
    count = 0
    for chapter in chapter_outputs:
        title = str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "")
        hints = _extract_title_entity_hints(title)
        if any(normalize_entity_key(hint) == key for hint in hints):
            count += 1
    return count


def _count_descriptor_aliases(aliases: list[str], canonical_name: str) -> int:
    canonical_tokens = set(normalize_entity_key(canonical_name).split())
    noisy = 0
    for alias in aliases:
        alias_tokens = set(normalize_entity_key(alias).split())
        if not alias_tokens:
            continue
        overlap = len(alias_tokens & canonical_tokens)
        if overlap == 0 and len(alias_tokens) >= 3:
            noisy += 1
    return noisy


def _entity_score(entity: dict[str, Any], chapter_outputs: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    canonical_name = normalize_entity_text(entity.get("canonical_name") or "")
    naming_quality = str(entity.get("naming_quality") or "unknown").strip().casefold()
    chapter_refs = [str(item).strip() for item in (entity.get("chapter_refs") or []) if str(item).strip()]
    relationships = [item for item in (entity.get("relationships") or []) if isinstance(item, dict)]
    key_facts = [normalize_entity_text(item) for item in (entity.get("key_facts") or []) if normalize_entity_text(item)]
    aliases = [normalize_entity_text(item) for item in (entity.get("aliases") or []) if normalize_entity_text(item)]
    source_mentions = [normalize_entity_text(item) for item in (entity.get("source_mentions") or []) if normalize_entity_text(item)]
    title_hit_count = _title_hit_count(canonical_name, chapter_outputs)

    score = 0
    if naming_quality == "proper_name":
        score += 4
    elif naming_quality == "title_plus_name":
        score += 3
    elif naming_quality == "descriptor":
        score += 0
    elif naming_quality == "pronoun_like":
        score -= 4
    else:
        score -= 2

    if len(chapter_refs) >= 3:
        score += 2
    elif len(chapter_refs) == 2:
        score += 1
    elif len(chapter_refs) == 1:
        score -= 1

    if len(relationships) >= 2:
        score += 2
    elif len(relationships) == 1:
        score += 1
    else:
        score -= 1

    if len(key_facts) >= 3:
        score += 2
    elif len(key_facts) == 2:
        score += 1
    else:
        score -= 2

    if title_hit_count >= 1:
        score += 2
    if len(source_mentions) >= 3:
        score += 1
    if bool(entity.get("is_stable_entity")):
        score += 2

    metrics = {
        "chapter_ref_count": len(chapter_refs),
        "relationship_count": len(relationships),
        "fact_count": len(key_facts),
        "alias_count": len(aliases),
        "source_mention_count": len(source_mentions),
        "title_hit_count": title_hit_count,
        "naming_quality": naming_quality,
        "descriptor_alias_count": _count_descriptor_aliases(aliases, canonical_name),
    }
    return score, metrics


def cleanup_resolved_entities(
    *,
    entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    promotion_decisions: list[dict[str, Any]] = []
    discarded_count = 0
    proper_like_primaries = 0
    descriptor_primaries = 0
    alias_noise_total = 0
    total_aliases = 0
    single_chapter_primaries = 0
    primary_count = 0
    review_count = 0

    for entity in entities:
        score, metrics = _entity_score(entity, chapter_outputs)
        naming_quality = metrics["naming_quality"]
        canonical_name = normalize_entity_text(entity.get("canonical_name") or "")
        chapter_refs = [str(item).strip() for item in (entity.get("chapter_refs") or []) if str(item).strip()]
        relationships = [item for item in (entity.get("relationships") or []) if isinstance(item, dict)]
        key_facts = [normalize_entity_text(item) for item in (entity.get("key_facts") or []) if normalize_entity_text(item)]

        decision = "discard"
        decision_reason = "insufficient_structural_evidence"
        if naming_quality in {"proper_name", "title_plus_name"} and score >= 4 and (
            len(chapter_refs) >= 2 or len(relationships) >= 2 or metrics["title_hit_count"] >= 1
        ):
            decision = "primary"
            decision_reason = "stable_named_entity_with_cross_chapter_evidence"
        elif score >= 2 and canonical_name:
            decision = "review"
            decision_reason = "retained_for_manual_review"

        if len(key_facts) < 2 and len(relationships) == 0 and metrics["title_hit_count"] == 0:
            if decision == "primary":
                decision = "review"
                decision_reason = "demoted_due_to_thin_entity_payload"
            elif decision == "review":
                decision = "discard"
                decision_reason = "discarded_due_to_thin_entity_payload"

        if naming_quality in {"pronoun_like", "unknown"}:
            if decision == "primary":
                decision = "review"
                decision_reason = "demoted_due_to_weak_naming_quality"
            elif decision == "review" and score < 4:
                decision = "discard"
                decision_reason = "discarded_due_to_weak_naming_quality"

        if bool(entity.get("needs_review")) and decision == "primary":
            decision = "review"
            decision_reason = "demoted_due_to_needs_review"

        final_entity = {
            **entity,
            "review_state": "canonical" if decision == "primary" else "review",
            "promotion_status": "promoted_canonical" if decision == "primary" else "pending_review",
            "note_role": "primary" if decision == "primary" else "review",
            "graph_exclude": decision != "primary",
            "retrieval_exclude": decision != "primary",
            "cleanup_decision": decision,
            "cleanup_score": score,
        }

        if decision == "discard":
            discarded_count += 1
        else:
            cleaned.append(final_entity)
            if decision == "primary":
                primary_count += 1
                if naming_quality in {"proper_name", "title_plus_name"}:
                    proper_like_primaries += 1
                if naming_quality == "descriptor":
                    descriptor_primaries += 1
                if len(chapter_refs) == 1:
                    single_chapter_primaries += 1
            else:
                review_count += 1

        alias_noise_total += int(metrics["descriptor_alias_count"])
        total_aliases += int(metrics["alias_count"])
        promotion_decisions.append(
            {
                "canonical_name": canonical_name,
                "entity_kind": str(entity.get("entity_kind") or ""),
                "naming_quality": naming_quality,
                "cleanup_score": score,
                "decision": decision,
                "reason": decision_reason,
                "metrics": metrics,
            }
        )

    alias_noise_rate = alias_noise_total / total_aliases if total_aliases else 0.0
    named_primary_rate = proper_like_primaries / primary_count if primary_count else 0.0
    descriptor_primary_rate = descriptor_primaries / primary_count if primary_count else 0.0
    single_chapter_primary_rate = single_chapter_primaries / primary_count if primary_count else 0.0
    review_to_primary_ratio = review_count / primary_count if primary_count else float(review_count > 0)

    cleanup_audit = {
        "input_entity_count": len(entities),
        "output_entity_count": len(cleaned),
        "primary_count": primary_count,
        "review_count": review_count,
        "discarded_count": discarded_count,
        "named_primary_rate": round(named_primary_rate, 4),
        "descriptor_primary_rate": round(descriptor_primary_rate, 4),
        "alias_noise_rate": round(alias_noise_rate, 4),
        "single_chapter_primary_rate": round(single_chapter_primary_rate, 4),
        "review_to_primary_ratio": round(review_to_primary_ratio, 4),
    }
    promotion_audit = {
        "decisions": promotion_decisions,
    }
    return cleaned, cleanup_audit, promotion_audit
