from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from textifai.bootstrap.prose_language_validation import resolve_prose_language_validator
from textifai.obsidian.parser import extract_obsidian_links, parse_obsidian_frontmatter
from vault.schema import slugify


def evaluate_semantic_invariants(
    *,
    system_root: str | Path | None = None,
    obsidian_import_path: str | Path | None = None,
    vault_root: str | Path | None = None,
    required_primaries: list[str] | None = None,
    language: str | None = None,
    min_primary_count: int | None = None,
    max_primary_count: int | None = None,
    max_review_count: int | None = None,
    max_unlinked_primary_mentions: int | None = None,
    max_suspicious_orphan_primaries: int | None = None,
    language_validator: str | None = "heuristic",
) -> dict[str, Any]:
    system = Path(system_root) if system_root is not None else None
    import_path = Path(obsidian_import_path) if obsidian_import_path is not None else (
        system / "obsidian_import.json" if system is not None else None
    )
    checks: list[dict[str, Any]] = []
    if import_path is None or not import_path.exists():
        return _audit(checks=[_check("obsidian_import_exists", "fail", {"path": str(import_path)})], entities=[])

    payload = json.loads(import_path.read_text(encoding="utf-8"))
    entities = [item for item in payload.get("entities") or [] if isinstance(item, dict)]
    chapters = [item for item in payload.get("chapters") or [] if isinstance(item, dict)]
    work_language = str(language or (payload.get("work") or {}).get("language") or "").strip()
    primary_entities = [item for item in entities if str(item.get("review_state") or "").casefold() == "canonical"]
    review_entities = [item for item in entities if str(item.get("review_state") or "").casefold() != "canonical"]

    checks.append(_check("obsidian_import_exists", "pass", {"path": str(import_path)}))
    checks.append(_chapter_integrity_check(payload=payload, chapters=chapters))
    checks.append(_required_primary_check(entities=entities, required_primaries=required_primaries or []))
    checks.append(_primary_count_check(primary_count=len(primary_entities), minimum=min_primary_count, maximum=max_primary_count))
    checks.append(_review_count_check(review_count=len(review_entities), maximum=max_review_count))
    checks.append(_preferred_slug_check(entities=entities))
    checks.append(_ontological_collision_check(entities=entities))
    checks.append(_duplicate_canonical_check(entities=entities))
    checks.append(_near_duplicate_primary_check(primary_entities))
    checks.append(_relationship_target_resolution_check(primary_entities))
    checks.append(_unlinked_primary_mention_check(primary_entities, maximum=max_unlinked_primary_mentions))
    checks.append(_suspicious_orphan_primary_check(primary_entities, maximum=max_suspicious_orphan_primaries))
    checks.append(_canonical_name_strength_check(primary_entities))
    checks.append(_language_check(entities=entities, language=work_language, validator_name=language_validator))
    if system is not None:
        checks.append(_required_artifact_check(system))
        checks.append(_auxiliary_check(system))
    if vault_root is not None:
        checks.append(_vault_placeholder_check(Path(vault_root)))
        checks.append(_vault_wikilink_check(Path(vault_root)))

    return _audit(checks=checks, entities=entities)


def write_semantic_invariants_audit(
    *,
    output_path: str | Path,
    system_root: str | Path | None = None,
    obsidian_import_path: str | Path | None = None,
    vault_root: str | Path | None = None,
    required_primaries: list[str] | None = None,
    language: str | None = None,
    min_primary_count: int | None = None,
    max_primary_count: int | None = None,
    max_review_count: int | None = None,
    max_unlinked_primary_mentions: int | None = None,
    max_suspicious_orphan_primaries: int | None = None,
    language_validator: str | None = "heuristic",
) -> dict[str, Any]:
    audit = evaluate_semantic_invariants(
        system_root=system_root,
        obsidian_import_path=obsidian_import_path,
        vault_root=vault_root,
        required_primaries=required_primaries,
        language=language,
        min_primary_count=min_primary_count,
        max_primary_count=max_primary_count,
        max_review_count=max_review_count,
        max_unlinked_primary_mentions=max_unlinked_primary_mentions,
        max_suspicious_orphan_primaries=max_suspicious_orphan_primaries,
        language_validator=language_validator,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def _audit(*, checks: list[dict[str, Any]], entities: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [item for item in checks if item.get("status") == "fail"]
    warnings = [item for item in checks if item.get("status") == "warn"]
    primary_count = sum(1 for item in entities if str(item.get("review_state") or "").casefold() == "canonical")
    return {
        "schema_version": "textifai.semantic_invariants.v1",
        "status": "fail" if failures else "pass_with_warnings" if warnings else "pass",
        "passed": not failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "entity_count": len(entities),
        "primary_count": primary_count,
        "review_count": len(entities) - primary_count,
        "checks": checks,
    }


def _check(name: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "details": details or {}}


def _chapter_integrity_check(*, payload: dict[str, Any], chapters: list[dict[str, Any]]) -> dict[str, Any]:
    run_status = payload.get("run_status") or {}
    expected = int(run_status.get("expected_chapter_count") or len(chapters))
    generated = int(run_status.get("generated_chapter_count") or len(chapters))
    failed = int(run_status.get("failed_chapter_count") or 0)
    ok = bool(run_status.get("semantic_integrity") == "complete" and expected == generated == len(chapters) and failed == 0)
    return _check(
        "chapter_integrity_complete",
        "pass" if ok else "fail",
        {"expected": expected, "generated": generated, "actual_chapter_count": len(chapters), "failed": failed},
    )


def _required_primary_check(*, entities: list[dict[str, Any]], required_primaries: list[str]) -> dict[str, Any]:
    if not required_primaries:
        return _check("required_primaries_present", "skip", {"required_primaries": []})
    primary_keys: set[str] = set()
    for entity in entities:
        if str(entity.get("review_state") or "").casefold() != "canonical":
            continue
        for value in [entity.get("canonical_name") or "", *(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]:
            key = _entity_key(value)
            if key:
                primary_keys.add(key)
    missing = [name for name in required_primaries if _entity_key(name) not in primary_keys]
    return _check(
        "required_primaries_present",
        "pass" if not missing else "fail",
        {"required_primaries": required_primaries, "missing": missing},
    )


def _primary_count_check(*, primary_count: int, minimum: int | None, maximum: int | None) -> dict[str, Any]:
    if minimum is None and maximum is None:
        return _check("primary_count_range", "skip", {"primary_count": primary_count})
    ok = (minimum is None or primary_count >= minimum) and (maximum is None or primary_count <= maximum)
    return _check("primary_count_range", "pass" if ok else "fail", {"primary_count": primary_count, "min": minimum, "max": maximum})


def _review_count_check(*, review_count: int, maximum: int | None) -> dict[str, Any]:
    if maximum is None:
        return _check("review_count_range", "skip", {"review_count": review_count})
    return _check("review_count_range", "pass" if review_count <= maximum else "warn", {"review_count": review_count, "max": maximum})


def _preferred_slug_check(*, entities: list[dict[str, Any]]) -> dict[str, Any]:
    materialized = [
        item for item in entities
        if str(item.get("review_state") or "").casefold() == "canonical"
    ]
    missing = [item.get("canonical_name") or "" for item in materialized if not str(item.get("preferred_slug") or "").strip()]
    duplicate_slugs: dict[tuple[str, str], list[str]] = {}
    for item in materialized:
        slug = str(item.get("preferred_slug") or "").strip()
        kind = str(item.get("entity_kind") or "").strip().casefold()
        if slug:
            duplicate_slugs.setdefault((kind, slug), []).append(str(item.get("canonical_name") or ""))
    duplicates = [
        {"entity_kind": kind, "preferred_slug": slug, "canonical_names": names}
        for (kind, slug), names in duplicate_slugs.items()
        if len(names) > 1
    ]
    return _check(
        "preferred_slug_present_and_unique_within_kind",
        "pass" if not missing and not duplicates else "fail",
        {"missing": missing, "duplicates": duplicates},
    )


def _ontological_collision_check(*, entities: list[dict[str, Any]]) -> dict[str, Any]:
    materialized = [
        item for item in entities
        if str(item.get("review_state") or "").casefold() == "canonical"
    ]
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for item in materialized:
        slug = str(item.get("preferred_slug") or "").strip()
        if slug:
            by_slug.setdefault(slug, []).append(item)

    collisions: list[dict[str, Any]] = []
    for slug, items in by_slug.items():
        kinds = sorted({str(item.get("entity_kind") or "").strip().casefold() for item in items if item.get("entity_kind")})
        if len(items) <= 1 or len(kinds) <= 1:
            continue
        collisions.append(
            {
                "collision_type": "same_slug_cross_kind",
                "preferred_slug": slug,
                "entity_kinds": kinds,
                "entities": [
                    {
                        "canonical_name": item.get("canonical_name") or "",
                        "entity_kind": item.get("entity_kind") or "",
                        "entity_subkind": item.get("entity_subkind") or "",
                        "review_state": item.get("review_state") or "",
                        "note_role": item.get("note_role") or "",
                    }
                    for item in items
                ],
                "recommended_review_action": "confirm separate facets, assign disambiguated slugs, or merge into the true bearer if the label is only an alias/title",
            }
        )
    return _check(
        "ontological_name_collisions",
        "pass" if not collisions else "warn",
        {
            "collisions": collisions,
            "policy": "same slug within the same entity_kind is a hard duplicate; same slug across different entity_kinds is an ontological collision requiring review, not an automatic merge",
        },
    )


def _duplicate_canonical_check(*, entities: list[dict[str, Any]]) -> dict[str, Any]:
    bucket: dict[tuple[str, str], list[str]] = {}
    for item in entities:
        kind = str(item.get("entity_kind") or "").casefold()
        name = str(item.get("canonical_name") or "").casefold()
        if not kind or not name:
            continue
        bucket.setdefault((kind, name), []).append(str(item.get("preferred_slug") or ""))
    duplicates = [{"entity_kind": kind, "canonical_name": name, "slugs": slugs} for (kind, name), slugs in bucket.items() if len(slugs) > 1]
    return _check("duplicate_exact_canonical_names", "pass" if not duplicates else "fail", {"duplicates": duplicates})


def _near_duplicate_primary_check(entities: list[dict[str, Any]]) -> dict[str, Any]:
    names = [
        (str(item.get("entity_kind") or "").casefold(), str(item.get("canonical_name") or "").strip(), str(item.get("preferred_slug") or ""))
        for item in entities
        if str(item.get("canonical_name") or "").strip()
    ]
    suspicious: list[dict[str, Any]] = []
    for idx, (kind_a, name_a, slug_a) in enumerate(names):
        key_a = _entity_key(name_a)
        if len(key_a) < 5:
            continue
        for kind_b, name_b, slug_b in names[idx + 1 :]:
            if kind_a != kind_b:
                continue
            key_b = _entity_key(name_b)
            if key_a == key_b or len(key_b) < 5:
                continue
            ratio = SequenceMatcher(None, key_a, key_b).ratio()
            if ratio >= 0.9:
                suspicious.append({"left": name_a, "right": name_b, "entity_kind": kind_a, "similarity": round(ratio, 3), "slugs": [slug_a, slug_b]})
    return _check("near_duplicate_primary_names", "pass" if not suspicious else "warn", {"suspicious": suspicious[:25]})


def _relationship_target_resolution_check(entities: list[dict[str, Any]]) -> dict[str, Any]:
    index = _primary_reference_index(entities)
    unresolved: list[dict[str, str]] = []
    for entity in entities:
        for rel in entity.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            target = str(rel.get("target") or "").strip()
            if not target:
                continue
            if _resolve_primary_key(target, index=index):
                continue
            unresolved.append(
                {
                    "source": str(entity.get("canonical_name") or ""),
                    "target": target,
                    "relationship_type": str(rel.get("type") or ""),
                }
            )
    return _check(
        "relationship_targets_resolve_to_primary",
        "pass" if not unresolved else "warn",
        {
            "unresolved": unresolved[:50],
            "unresolved_count": len(unresolved),
            "policy": "relationship targets should resolve through canonical_name, preferred_slug, aliases, or source_mentions of a primary entity",
        },
    )


def _unlinked_primary_mention_check(entities: list[dict[str, Any]], *, maximum: int | None) -> dict[str, Any]:
    index = _primary_reference_index(entities)
    findings: list[dict[str, Any]] = []
    for entity in entities:
        source_key = _primary_entity_key(entity)
        related_keys = _related_primary_keys(entity, index=index)
        texts = _entity_semantic_texts(entity)
        for text_item in texts:
            mentioned = _mentioned_primary_keys(text_item["text"], index=index)
            for target_key in sorted(mentioned - {source_key} - related_keys):
                target = index["entities_by_key"].get(target_key, {})
                findings.append(
                    {
                        "source": str(entity.get("canonical_name") or ""),
                        "mentioned_primary": str(target.get("canonical_name") or target_key),
                        "field": text_item["field"],
                        "text": text_item["text"][:240],
                    }
                )
    status = "pass"
    if findings and maximum is None:
        status = "warn"
    elif maximum is not None and len(findings) > maximum:
        status = "fail"
    return _check(
        "unlinked_primary_mentions",
        status,
        {
            "maximum": maximum,
            "finding_count": len(findings),
            "findings": findings[:50],
            "policy": "if a primary fact/summary names another primary, the graph should usually expose a relationship or leave an explicit review signal",
        },
    )


def _suspicious_orphan_primary_check(entities: list[dict[str, Any]], *, maximum: int | None) -> dict[str, Any]:
    suspicious: list[dict[str, Any]] = []
    for entity in entities:
        relationships = [rel for rel in entity.get("relationships") or [] if isinstance(rel, dict)]
        facts = _strings(entity.get("key_facts") or [])
        source_refs = entity.get("source_refs") or []
        chapter_refs = entity.get("chapter_refs") or []
        if relationships or facts or source_refs or chapter_refs:
            continue
        suspicious.append(
            {
                "canonical_name": str(entity.get("canonical_name") or ""),
                "entity_kind": str(entity.get("entity_kind") or ""),
                "preferred_slug": str(entity.get("preferred_slug") or ""),
                "reason": "primary_without_relationships_refs_or_enough_facts",
            }
        )
    status = "pass"
    if suspicious and maximum is None:
        status = "warn"
    elif maximum is not None and len(suspicious) > maximum:
        status = "fail"
    return _check(
        "suspicious_orphan_primaries",
        status,
        {
            "maximum": maximum,
            "suspicious_count": len(suspicious),
            "suspicious": suspicious[:50],
            "policy": "auxiliary-only primaries are allowed, but materialized primaries should carry enough facts, refs, or relationships to be useful",
        },
    )


def _canonical_name_strength_check(entities: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    weak_qualities = {"descriptor", "pronoun_like", "unknown"}
    for entity in entities:
        naming_quality = str(entity.get("naming_quality") or "").strip().casefold()
        if naming_quality not in weak_qualities:
            continue
        candidates = [
            str(value).strip()
            for value in [*(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]
            if str(value or "").strip()
        ]
        stronger = [value for value in candidates if _looks_like_specific_name(value)]
        if not stronger:
            continue
        findings.append(
            {
                "canonical_name": str(entity.get("canonical_name") or ""),
                "entity_kind": str(entity.get("entity_kind") or ""),
                "naming_quality": naming_quality,
                "stronger_name_candidates": sorted(set(stronger))[:10],
            }
        )
    return _check(
        "canonical_name_not_weaker_than_available_alias",
        "pass" if not findings else "warn",
        {
            "findings": findings[:50],
            "policy": "if a cluster has an explicit specific name, a descriptor/pronoun canonical is suspicious and should be reviewed",
        },
    )


def _language_check(*, entities: list[dict[str, Any]], language: str, validator_name: str | None) -> dict[str, Any]:
    if not language:
        return _check("semantic_prose_language", "skip", {"reason": "language_missing"})
    validator = resolve_prose_language_validator(validator_name)
    if validator is None:
        return _check("semantic_prose_language", "warn", {"reason": "validator_unavailable", "validator": validator_name})
    texts: list[str] = []
    for entity in entities:
        texts.extend(_strings([entity.get("summary"), entity.get("review_reason")]))
        texts.extend(_strings(entity.get("key_facts") or []))
        for rel in entity.get("relationships") or []:
            if isinstance(rel, dict):
                texts.extend(_strings(rel.get("facts") or []))
    result = validator.validate_texts(texts=texts, expected_language=language, context="semantic_invariants")
    errors = [
        item.message for item in result.messages
        if item.severity == "error" and "detected=unknown" not in item.message
    ]
    warnings = [
        item.message for item in result.messages
        if item.severity != "error" or "detected=unknown" in item.message
    ]
    return _check("semantic_prose_language", "pass" if not errors else "fail", {"language": language, "errors": errors, "warnings": warnings})


def _required_artifact_check(system: Path) -> dict[str, Any]:
    required = [
        "global_normalization.json",
        "chapter_outputs",
        "resolved_entities.json",
        "cleaned_entities.json",
        "obsidian_import.json",
        "chapter_extraction_audit.json",
        "run_comparability_manifest.json",
        "run_limits_audit.json",
        "obsidian_relationship_reconciliation_audit.json",
    ]
    missing = [name for name in required if not (system / name).exists()]
    return _check("required_phase1_artifacts_exist", "pass" if not missing else "fail", {"missing": missing})


def _auxiliary_check(system: Path) -> dict[str, Any]:
    audit_path = system / "auxiliary_enrichment_audit.json"
    if not audit_path.exists():
        return _check("auxiliary_ingestion_integrity", "skip", {"reason": "auxiliary_not_present"})
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    errors = int(audit.get("extraction_error_count") or 0)
    return _check(
        "auxiliary_ingestion_integrity",
        "pass" if errors == 0 else "fail",
        {
            "chunk_count": audit.get("chunk_count"),
            "extraction_count": audit.get("extraction_count"),
            "extraction_error_count": errors,
            "created_entity_count": audit.get("created_entity_count"),
            "enriched_entity_count": audit.get("enriched_entity_count"),
        },
    )


def _vault_placeholder_check(vault: Path) -> dict[str, Any]:
    if not vault.exists():
        return _check("vault_no_empty_placeholders", "skip", {"reason": "vault_missing", "vault_root": str(vault)})
    suspicious: list[str] = []
    for path in vault.rglob("*.md"):
        if any(part in {"99_System", "_Templates"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        frontmatter = parse_obsidian_frontmatter(text)
        body = text
        if text.startswith("---\n"):
            parts = text.split("---", 2)
            body = parts[2].strip() if len(parts) == 3 else text
        if len(body) < 12 and not frontmatter:
            suspicious.append(str(path))
    return _check("vault_no_empty_placeholders", "pass" if not suspicious else "fail", {"suspicious_paths": suspicious[:50]})


def _vault_wikilink_check(vault: Path) -> dict[str, Any]:
    if not vault.exists():
        return _check("vault_wikilinks_resolve", "skip", {"reason": "vault_missing", "vault_root": str(vault)})
    note_targets: set[str] = set()
    for path in vault.rglob("*.md"):
        note_targets.add(path.stem)
        note_targets.add(slugify(path.stem))
        try:
            relative = path.relative_to(vault).with_suffix("").as_posix()
        except ValueError:
            relative = path.with_suffix("").as_posix()
        note_targets.add(relative)
        note_targets.add(slugify(relative))
        parts = Path(relative).parts
        for start in range(len(parts)):
            suffix = "/".join(parts[start:])
            note_targets.add(suffix)
            note_targets.add(slugify(suffix))
    broken: list[dict[str, str]] = []
    for path in vault.rglob("*.md"):
        if any(part in {"99_System", "_Templates"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in extract_obsidian_links(text):
            if target not in note_targets:
                broken.append({"path": str(path), "target": target})
    return _check("vault_wikilinks_resolve", "pass" if not broken else "fail", {"broken": broken[:100], "broken_count": len(broken)})


def _strings(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    return [str(item).strip() for item in values if str(item or "").strip()]


def _entity_key(value: Any) -> str:
    return slugify(str(value or "")).replace("_", "")


def _primary_entity_key(entity: dict[str, Any]) -> str:
    return _entity_key(entity.get("preferred_slug") or entity.get("canonical_name") or "")


def _primary_reference_index(entities: list[dict[str, Any]]) -> dict[str, Any]:
    entities_by_key: dict[str, dict[str, Any]] = {}
    term_to_key: dict[str, str] = {}
    terms: list[tuple[str, str, str]] = []
    for entity in entities:
        primary_key = _primary_entity_key(entity)
        if not primary_key:
            continue
        entities_by_key[primary_key] = entity
        raw_terms = [
            entity.get("canonical_name") or "",
            entity.get("preferred_slug") or "",
            *(entity.get("aliases") or []),
            *(entity.get("source_mentions") or []),
        ]
        for raw in raw_terms:
            label = str(raw or "").strip()
            key = _entity_key(label)
            if len(key) < 4:
                continue
            term_to_key.setdefault(key, primary_key)
            terms.append((key, primary_key, label))
    terms.sort(key=lambda item: len(item[0]), reverse=True)
    return {"entities_by_key": entities_by_key, "term_to_key": term_to_key, "terms": terms}


def _resolve_primary_key(value: Any, *, index: dict[str, Any]) -> str:
    key = _entity_key(value)
    if not key:
        return ""
    entities_by_key: dict[str, dict[str, Any]] = index["entities_by_key"]
    term_to_key: dict[str, str] = index["term_to_key"]
    return key if key in entities_by_key else term_to_key.get(key, "")


def _related_primary_keys(entity: dict[str, Any], *, index: dict[str, Any]) -> set[str]:
    related: set[str] = set()
    for rel in entity.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        key = _resolve_primary_key(rel.get("target"), index=index)
        if key:
            related.add(key)
    return related


def _entity_semantic_texts(entity: dict[str, Any]) -> list[dict[str, str]]:
    texts: list[dict[str, str]] = []
    for field in ("summary", "review_reason"):
        value = str(entity.get(field) or "").strip()
        if value:
            texts.append({"field": field, "text": value})
    for idx, fact in enumerate(_strings(entity.get("key_facts") or [])):
        texts.append({"field": f"key_facts[{idx}]", "text": fact})
    for rel_idx, rel in enumerate(entity.get("relationships") or []):
        if not isinstance(rel, dict):
            continue
        for fact_idx, fact in enumerate(_strings(rel.get("facts") or [])):
            texts.append({"field": f"relationships[{rel_idx}].facts[{fact_idx}]", "text": fact})
    return texts


def _mentioned_primary_keys(text: str, *, index: dict[str, Any]) -> set[str]:
    normalized_text = _entity_key(text)
    mentioned: set[str] = set()
    for term_key, primary_key, _label in index["terms"]:
        if len(term_key) < 4:
            continue
        if term_key in normalized_text:
            mentioned.add(primary_key)
    return mentioned


def _looks_like_specific_name(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned or len(_entity_key(cleaned)) < 4:
        return False
    if "_" in cleaned:
        return False
    tokens = [token for token in re.split(r"\s+", cleaned) if token]
    if not tokens or len(tokens) > 5:
        return False
    return any(token[:1].isupper() and any(char.islower() for char in token[1:]) for token in tokens)
