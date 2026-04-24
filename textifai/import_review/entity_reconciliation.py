from __future__ import annotations

from typing import Any

from textifai.import_review.entity_cluster_resolution import normalize_entity_key, normalize_entity_text


def reconcile_entities_for_vaerl(
    *,
    entities: list[dict[str, Any]],
    language: str = "unknown",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reconcile post-cleanup entities before VaERL materialization.

    This pass is deterministic and conservative: it uses existing primary
    aliases, titles, facts, and relationship targets to fold orphan review
    entities into already-promoted primaries when evidence is strong enough.
    """

    del language  # Reserved for future audit localization; matching stays language-agnostic.
    primaries = [_clone_entity(entity) for entity in entities if _is_primary(entity)]
    reviews = [_clone_entity(entity) for entity in entities if not _is_primary(entity)]
    primary_by_key = {
        normalize_entity_key(primary.get("canonical_name") or ""): primary
        for primary in primaries
        if normalize_entity_key(primary.get("canonical_name") or "")
    }
    primary_profiles = {id(primary): _identity_profile(primary) for primary in primaries}

    relationship_rewrites: list[dict[str, Any]] = []
    fact_relationships_added: list[dict[str, Any]] = []
    for entity in [*primaries, *reviews]:
        rewrites = _canonicalize_relationship_targets(entity, primaries, primary_profiles)
        relationship_rewrites.extend(rewrites)
        additions = _add_fact_based_primary_relationships(entity, primaries, primary_profiles)
        fact_relationships_added.extend(additions)

    auto_merged: list[dict[str, Any]] = []
    retained_reviews: list[dict[str, Any]] = []
    candidate_reviews: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []

    for review in reviews:
        candidate = _best_primary_candidate(review, primaries, primary_profiles)
        if candidate is None:
            retained_reviews.append(review)
            continue
        primary, score, evidence = candidate
        if score >= 3:
            _merge_review_into_primary(primary, review, evidence=evidence)
            auto_merged.append(
                {
                    "source_entity": review.get("canonical_name") or "",
                    "target_entity": primary.get("canonical_name") or "",
                    "entity_kind": review.get("entity_kind") or "",
                    "score": score,
                    "evidence": evidence,
                    "policy": "strong_positive_evidence_only",
                }
            )
            continue
        if score > 0:
            candidate_reviews.append(
                {
                    "source_entity": review.get("canonical_name") or "",
                    "candidate_target": primary.get("canonical_name") or "",
                    "entity_kind": review.get("entity_kind") or "",
                    "score": score,
                    "evidence": evidence,
                    "reason": "insufficient_positive_evidence",
                }
            )
        else:
            rejected_candidates.append(
                {
                    "source_entity": review.get("canonical_name") or "",
                    "candidate_target": primary.get("canonical_name") or "",
                    "entity_kind": review.get("entity_kind") or "",
                    "score": score,
                    "reason": "no_positive_identity_overlap",
                }
            )
        retained_reviews.append(review)

    reconciled = [*primaries, *retained_reviews]
    _canonicalize_all_relationship_targets(reconciled)
    reconciled.sort(key=lambda item: (str(item.get("entity_kind") or ""), str(item.get("canonical_name") or "").casefold()))
    audit = {
        "schema_version": "textifai.pre_vaerl_reconciliation.v1",
        "input_entity_count": len(entities),
        "output_entity_count": len(reconciled),
        "primary_count": len([entity for entity in reconciled if _is_primary(entity)]),
        "review_count": len([entity for entity in reconciled if not _is_primary(entity)]),
        "auto_merged_count": len(auto_merged),
        "candidate_review_count": len(candidate_reviews),
        "relationship_rewrite_count": len(relationship_rewrites),
        "fact_relationship_added_count": len(fact_relationships_added),
        "auto_merged_entities": auto_merged,
        "candidate_reviews": candidate_reviews,
        "rejected_candidates": rejected_candidates,
        "relationship_rewrites": relationship_rewrites,
        "fact_relationships_added": fact_relationships_added,
        "policy": {
            "temporal_presence_conflicts_are_not_hard_blocks": True,
            "required_auto_merge_score": 3,
            "notes": [
                "Flashbacks, memories, records, and retrospective scenes can mention absent or dead characters as present.",
                "Automatic merges require positive identity evidence such as alias/title overlap or relationship target convergence.",
            ],
        },
    }
    return reconciled, audit


def _clone_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        **entity,
        "aliases": list(entity.get("aliases") or []),
        "key_facts": list(entity.get("key_facts") or []),
        "chapter_refs": list(entity.get("chapter_refs") or []),
        "source_mentions": list(entity.get("source_mentions") or []),
        "relationships": [dict(rel) for rel in (entity.get("relationships") or []) if isinstance(rel, dict)],
        "reconciled_from": list(entity.get("reconciled_from") or []),
    }


def _is_primary(entity: dict[str, Any]) -> bool:
    return (
        str(entity.get("note_role") or "").strip().casefold() == "primary"
        or str(entity.get("review_state") or "").strip().casefold() == "canonical"
    )


def _identity_profile(entity: dict[str, Any]) -> dict[str, Any]:
    phrases = _entity_identity_phrases(entity)
    alias_phrases = [normalize_entity_text(item) for item in (entity.get("aliases") or []) if normalize_entity_text(item)]
    return {
        "phrases": phrases,
        "alias_phrases": alias_phrases,
        "keys": {normalize_entity_key(phrase) for phrase in phrases if normalize_entity_key(phrase)},
        "token_sets": [_token_set(phrase) for phrase in phrases if _token_set(phrase)],
        "alias_token_sets": [_token_set(phrase) for phrase in alias_phrases if _token_set(phrase)],
    }


def _entity_identity_phrases(entity: dict[str, Any]) -> list[str]:
    phrases: list[str] = []
    for value in [
        entity.get("canonical_name") or "",
        entity.get("canonical_candidate") or "",
        *(entity.get("aliases") or []),
        *(entity.get("source_mentions") or []),
    ]:
        text = normalize_entity_text(value)
        if text and text not in phrases:
            phrases.append(text)
    return phrases


def _token_set(value: str) -> set[str]:
    return {token for token in normalize_entity_key(value).split() if token}


def _text_blob(entity: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("canonical_name", "canonical_candidate", "summary", "review_reason"):
        parts.append(str(entity.get(key) or ""))
    parts.extend(str(item) for item in (entity.get("aliases") or []))
    parts.extend(str(item) for item in (entity.get("source_mentions") or []))
    parts.extend(str(item) for item in (entity.get("key_facts") or []))
    return normalize_entity_key(" ".join(parts))


def _best_primary_candidate(
    review: dict[str, Any],
    primaries: list[dict[str, Any]],
    primary_profiles: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], int, list[dict[str, Any]]] | None:
    if str(review.get("entity_kind") or "") != "character":
        return None
    best: tuple[dict[str, Any], int, list[dict[str, Any]]] | None = None
    for primary in primaries:
        if str(primary.get("entity_kind") or "") != str(review.get("entity_kind") or ""):
            continue
        score, evidence = _reconciliation_score(review, primary, primary_profiles[id(primary)])
        if best is None or score > best[1]:
            best = (primary, score, evidence)
    return best


def _reconciliation_score(
    review: dict[str, Any],
    primary: dict[str, Any],
    primary_profile: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]]:
    score = 0
    evidence: list[dict[str, Any]] = []
    review_phrases = _entity_identity_phrases(review)
    review_keys = {normalize_entity_key(phrase) for phrase in review_phrases if normalize_entity_key(phrase)}
    review_token_sets = [_token_set(phrase) for phrase in review_phrases if _token_set(phrase)]
    relationship_target_keys = _relationship_target_keys(review)
    naming_quality = str(review.get("naming_quality") or "").strip().casefold()

    exact_overlap = sorted(review_keys & set(primary_profile["keys"]))
    if exact_overlap:
        score += 3
        evidence.append({"kind": "exact_identity_overlap", "values": exact_overlap[:5]})

    subset_matches = []
    for review_tokens in review_token_sets:
        for primary_tokens in primary_profile["token_sets"]:
            if not review_tokens or not primary_tokens:
                continue
            if review_tokens == primary_tokens:
                continue
            if review_tokens.issubset(primary_tokens) or primary_tokens.issubset(review_tokens):
                subset_matches.append(" ".join(sorted(review_tokens & primary_tokens)))
    if subset_matches:
        score += 2
        evidence.append({"kind": "title_or_descriptor_token_overlap", "values": sorted(set(subset_matches))[:5]})

    related_not_identity = sorted(relationship_target_keys & set(primary_profile["keys"]))
    if related_not_identity:
        score -= 3
        evidence.append({"kind": "relationship_target_mentions_primary_not_identity", "values": related_not_identity[:5]})

    blob = _text_blob(review)
    alias_token_matches = []
    blob_tokens = set(blob.split())
    if naming_quality in {"descriptor", "pronoun_like", "unknown"} and not related_not_identity:
        for tokens in primary_profile["alias_token_sets"]:
            significant_tokens = {token for token in tokens if len(token) >= 5}
            matched = significant_tokens & blob_tokens
            if matched:
                alias_token_matches.extend(sorted(matched))
    if alias_token_matches:
        score += 2
        evidence.append({"kind": "source_text_mentions_primary_alias_tokens", "values": sorted(set(alias_token_matches))[:5]})

    primary_quality = str(primary.get("naming_quality") or "").strip().casefold()
    if naming_quality in {"descriptor", "pronoun_like", "unknown"} and primary_quality in {"proper_name", "title_plus_name"}:
        score += 1
        evidence.append({"kind": "weak_named_review_against_strong_primary"})

    return score, evidence


def _relationship_target_keys(entity: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for rel in entity.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        key = normalize_entity_key(rel.get("target") or "")
        if key:
            keys.add(key)
    return keys


def _canonicalize_relationship_targets(
    entity: dict[str, Any],
    primaries: list[dict[str, Any]],
    primary_profiles: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rewrites: list[dict[str, Any]] = []
    relationships = []
    for rel in entity.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        current_target = normalize_entity_text(rel.get("target") or "")
        canonical_target = _resolve_primary_target(current_target, primaries, primary_profiles)
        if canonical_target and normalize_entity_key(canonical_target) != normalize_entity_key(current_target):
            rewritten = {**rel, "target": canonical_target}
            relationships.append(rewritten)
            rewrites.append(
                {
                    "source_entity": entity.get("canonical_name") or "",
                    "from_target": current_target,
                    "to_target": canonical_target,
                    "reason": "target_matches_primary_alias_or_title",
                }
            )
        else:
            relationships.append(rel)
    entity["relationships"] = _merge_relationships(relationships)
    return rewrites


def _canonicalize_all_relationship_targets(entities: list[dict[str, Any]]) -> None:
    primaries = [entity for entity in entities if _is_primary(entity)]
    profiles = {id(primary): _identity_profile(primary) for primary in primaries}
    for entity in entities:
        _canonicalize_relationship_targets(entity, primaries, profiles)
        _add_fact_based_primary_relationships(entity, primaries, profiles)


def _resolve_primary_target(
    target: str,
    primaries: list[dict[str, Any]],
    primary_profiles: dict[int, dict[str, Any]],
) -> str:
    target_key = normalize_entity_key(target)
    if not target_key:
        return ""
    exact = [
        primary
        for primary in primaries
        if target_key in primary_profiles[id(primary)]["keys"]
    ]
    if len(exact) == 1:
        return str(exact[0].get("canonical_name") or "")

    target_tokens = _token_set(target)
    subset = []
    for primary in primaries:
        for tokens in primary_profiles[id(primary)]["token_sets"]:
            if target_tokens and tokens and target_tokens.issubset(tokens):
                subset.append(primary)
                break
    unique_subset = {normalize_entity_key(primary.get("canonical_name") or ""): primary for primary in subset}
    if len(unique_subset) == 1:
        return str(next(iter(unique_subset.values())).get("canonical_name") or "")
    return ""


def _add_fact_based_primary_relationships(
    entity: dict[str, Any],
    primaries: list[dict[str, Any]],
    primary_profiles: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_targets = {normalize_entity_key(rel.get("target") or "") for rel in entity.get("relationships") or [] if isinstance(rel, dict)}
    source_key = normalize_entity_key(entity.get("canonical_name") or "")
    added: list[dict[str, Any]] = []
    relationships = list(entity.get("relationships") or [])
    for fact in entity.get("key_facts") or []:
        fact_text = normalize_entity_text(fact)
        target = _resolve_unique_primary_mention_in_text(
            fact_text,
            primaries=primaries,
            primary_profiles=primary_profiles,
            source_key=source_key,
        )
        target_key = normalize_entity_key(target)
        if not target or target_key in existing_targets:
            continue
        relationships.append({"target": target, "type": "related_to", "facts": [fact_text]})
        existing_targets.add(target_key)
        added.append(
            {
                "source_entity": entity.get("canonical_name") or "",
                "target": target,
                "reason": "key_fact_mentions_unique_primary_alias_or_source_mention",
                "fact": fact_text,
            }
        )
    if added:
        entity["relationships"] = _merge_relationships(relationships)
    return added


def _resolve_unique_primary_mention_in_text(
    text: str,
    *,
    primaries: list[dict[str, Any]],
    primary_profiles: dict[int, dict[str, Any]],
    source_key: str,
) -> str:
    text_tokens = {token.strip(".,;:!?()[]{}\"'") for token in normalize_entity_key(text).split()}
    text_tokens = {token for token in text_tokens if token}
    if not text_tokens:
        return ""
    matches: dict[str, str] = {}
    for primary in primaries:
        primary_name = str(primary.get("canonical_name") or "")
        primary_key = normalize_entity_key(primary_name)
        if not primary_key or primary_key == source_key:
            continue
        for tokens in primary_profiles[id(primary)]["token_sets"]:
            if tokens and tokens.issubset(text_tokens):
                matches[primary_key] = primary_name
                break
    if len(matches) == 1:
        return next(iter(matches.values()))
    return ""


def _merge_review_into_primary(primary: dict[str, Any], review: dict[str, Any], *, evidence: list[dict[str, Any]]) -> None:
    primary["aliases"] = _unique_texts(
        [
            *(primary.get("aliases") or []),
            review.get("canonical_name") or "",
            *(review.get("aliases") or []),
            *(review.get("source_mentions") or []),
        ]
    )
    primary["key_facts"] = _unique_texts([*(primary.get("key_facts") or []), *(review.get("key_facts") or [])])
    primary["chapter_refs"] = _unique_texts([*(primary.get("chapter_refs") or []), *(review.get("chapter_refs") or [])])
    primary["source_mentions"] = _unique_texts(
        [*(primary.get("source_mentions") or []), review.get("canonical_name") or "", *(review.get("source_mentions") or [])]
    )
    primary["relationships"] = _merge_relationships([*(primary.get("relationships") or []), *(review.get("relationships") or [])])
    primary["reconciled_from"] = [
        *(primary.get("reconciled_from") or []),
        {
            "canonical_name": review.get("canonical_name") or "",
            "entity_kind": review.get("entity_kind") or "",
            "evidence": evidence,
        },
    ]
    primary["pre_vaerl_reconciled"] = True


def _unique_texts(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_entity_text(value)
        key = normalize_entity_key(text)
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _merge_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        target = normalize_entity_text(rel.get("target") or "")
        rel_type = normalize_entity_text(rel.get("type") or rel.get("relation_type") or "")
        if not target or not rel_type:
            continue
        key = (normalize_entity_key(target), rel_type.casefold())
        facts = _unique_texts(list(rel.get("facts") or []))
        if key not in bucket:
            bucket[key] = {"target": target, "type": rel_type, "facts": facts}
        else:
            bucket[key]["facts"] = _unique_texts([*bucket[key]["facts"], *facts])
    return sorted(bucket.values(), key=lambda item: (str(item.get("type") or ""), str(item.get("target") or "").casefold()))
