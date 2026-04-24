from __future__ import annotations

import json
import re
import shutil
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from textifai.obsidian.parser import extract_obsidian_links, parse_obsidian_frontmatter
from textifai.obsidian.taxonomy import PRIMARY_DIRS, normalize_taxonomy, taxonomy_payload_for_entity, taxonomy_tags

_SECTION_LABELS = {
    "es": {
        "overview": "Resumen",
        "key_facts": "Datos Clave",
        "relationships": "Relaciones",
        "source_chapters": "Capítulos Fuente",
        "summary": "Resumen",
        "chapter_text": "Texto del Capítulo",
        "characters": "Personajes",
        "places": "Lugares",
        "concepts": "Conceptos",
        "events": "Eventos",
        "relations": "Relaciones",
        "linked_primaries": "Primarias Enlazadas",
        "chapter_summary_suffix": "Resumen",
        "import_manifest": "Manifiesto de Importación",
        "unknown_language": "desconocido",
        "no_summary": "Sin resumen.",
    }
}

_GENERIC_TITLES = {
    "castillo",
    "claro",
    "confrontacion",
    "confrontación",
    "ceremonia",
    "explosion",
    "explosión",
    "campo",
    "bosque",
}


def _labels_for_language(language: str | None) -> dict[str, str]:
    normalized = str(language or "").strip().casefold()
    return _SECTION_LABELS.get(normalized, {
        "overview": "Overview",
        "key_facts": "Key Facts",
        "relationships": "Relationships",
        "source_chapters": "Source Chapters",
        "summary": "Summary",
        "chapter_text": "Chapter Text",
        "characters": "Characters",
        "places": "Places",
        "concepts": "Concepts",
        "events": "Events",
        "relations": "Relations",
        "linked_primaries": "Linked Primaries",
        "chapter_summary_suffix": "Summary",
        "import_manifest": "Import Manifest",
        "unknown_language": "unknown",
        "no_summary": "No summary.",
    })


def normalize_title(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("[[", " ").replace("]]", " ")
    text = text.replace("[", " ").replace("]", " ")
    text = text.replace("*", " ").replace("·", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[\s\.,:;!?\-_/]+", "", text)
    text = re.sub(r"[\s\.,:;!?\-_/]+$", "", text)
    return text.strip()


def slugify(text: str) -> str:
    normalized = normalize_title(text)
    normalized = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower()
    normalized = normalized.replace("’", "").replace("'", "")
    normalized = re.sub(r"[^\w\s-]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-\s]+", "_", normalized).strip("_")
    return normalized or "note"


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_title(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalize_entity_kind(value: str | None) -> str:
    normalized, _ = normalize_taxonomy(entity_kind=value)
    return normalized


def _normalize_entity_subkind(entity_kind: str | None, value: str | None, *, canonical_name: str = "", chapter_refs: list[str] | None = None) -> str | None:
    _, subkind = normalize_taxonomy(
        entity_kind=entity_kind,
        entity_subkind=value,
        canonical_name=canonical_name,
        chapter_refs=chapter_refs or [],
    )
    return subkind


def _title_key(value: str) -> str:
    return normalize_title(value).casefold()


def _token_set(value: str) -> set[str]:
    return {token for token in slugify(value).split("_") if token}


def _normalize_aliases(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        raw_values = values
    else:
        text = str(values).strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                raw_values = parsed if isinstance(parsed, list) else str(values).split(",")
            except json.JSONDecodeError:
                raw_values = str(values).split(",")
        else:
            raw_values = str(values).split(",")
    return dedupe([str(item).strip() for item in raw_values if str(item).strip()])


def _normalize_relationships(relationships: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for rel in relationships or []:
        if not isinstance(rel, dict):
            continue
        target = normalize_title(str(rel.get("target") or ""))
        rel_type = str(rel.get("type") or "").strip()
        facts = dedupe([str(item).strip() for item in (rel.get("facts") or []) if str(item).strip()])
        if not target or not rel_type:
            continue
        key = (target.casefold(), rel_type.casefold())
        existing = bucket.get(key)
        if existing is None:
            bucket[key] = {"target": target, "type": rel_type, "facts": facts[:5]}
        else:
            existing["facts"] = dedupe(existing["facts"] + facts)[:5]
    return list(bucket.values())


def should_promote_entity(entity: dict[str, Any]) -> bool:
    explicit_status = str(entity.get("promotion_status") or "").strip().casefold()
    if explicit_status == "promoted_canonical":
        return True
    if explicit_status == "pending_review":
        return False
    title = normalize_title(str(entity.get("canonical_name") or entity.get("canonical_subject") or ""))
    key_facts = dedupe([str(fact).strip() for fact in (entity.get("key_facts") or []) if str(fact).strip()])
    relationships = _normalize_relationships(entity.get("relationships") or [])
    chapter_refs = dedupe([str(ref).strip() for ref in (entity.get("chapter_refs") or []) if str(ref).strip()])
    summary = str(entity.get("summary") or "").strip()
    entity_kind = _normalize_entity_kind(entity.get("entity_kind"))
    if not title or len(slugify(title)) < 3:
        return False
    if len(key_facts) < 2:
        return False
    if title.casefold() in _GENERIC_TITLES:
        return False
    if len(chapter_refs) < 2 and not relationships:
        return False
    if not summary and not relationships:
        return False
    if entity_kind == "event" and len(chapter_refs) < 2 and len(relationships) < 2:
        return False
    return True


def _should_materialize_review_entity(entity: dict[str, Any]) -> bool:
    title = normalize_title(str(entity.get("canonical_name") or entity.get("canonical_subject") or ""))
    key_facts = dedupe([str(fact).strip() for fact in (entity.get("key_facts") or []) if str(fact).strip()])
    relationships = _normalize_relationships(entity.get("relationships") or [])
    aliases = _normalize_aliases(entity.get("aliases"))
    summary = str(entity.get("summary") or "").strip()
    if not title or len(slugify(title)) < 3:
        return False
    if title.casefold() in _GENERIC_TITLES:
        return False
    return bool(summary or key_facts or relationships or aliases)


def _specificity_score(entity: dict[str, Any]) -> tuple[int, int, int, int]:
    title = normalize_title(str(entity.get("canonical_name") or ""))
    return (
        len(_token_set(title)),
        len(title),
        len(dedupe(entity.get("key_facts") or [])),
        len(dedupe(entity.get("chapter_refs") or [])),
    )


def _merge_entities(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    preferred = base if _specificity_score(base) >= _specificity_score(extra) else extra
    secondary = extra if preferred is base else base
    merged = dict(preferred)
    merged["canonical_name"] = normalize_title(str(preferred.get("canonical_name") or secondary.get("canonical_name") or ""))
    merged["preferred_slug"] = str(preferred.get("preferred_slug") or secondary.get("preferred_slug") or "").strip()
    merged["entity_kind"] = _normalize_entity_kind(preferred.get("entity_kind") or secondary.get("entity_kind"))
    merged["aliases"] = dedupe(
        _normalize_aliases(preferred.get("aliases")) +
        _normalize_aliases(secondary.get("aliases")) +
        [str(secondary.get("canonical_name") or "").strip()]
    )
    merged["summary"] = str(preferred.get("summary") or secondary.get("summary") or "").strip()
    merged["key_facts"] = dedupe((preferred.get("key_facts") or []) + (secondary.get("key_facts") or []))[:5]
    merged["chapter_refs"] = dedupe((preferred.get("chapter_refs") or []) + (secondary.get("chapter_refs") or []))
    merged["source_mentions"] = dedupe((preferred.get("source_mentions") or []) + (secondary.get("source_mentions") or []))
    merged["relationships"] = _normalize_relationships((preferred.get("relationships") or []) + (secondary.get("relationships") or []))
    merged["confidence"] = max(float(preferred.get("confidence") or 0.0), float(secondary.get("confidence") or 0.0))
    preferred_status = str(preferred.get("promotion_status") or "").strip().casefold()
    secondary_status = str(secondary.get("promotion_status") or "").strip().casefold()
    if "promoted_canonical" in {preferred_status, secondary_status}:
        merged["promotion_status"] = "promoted_canonical"
        merged["review_state"] = "canonical"
        merged["note_role"] = "primary"
    elif "pending_review" in {preferred_status, secondary_status}:
        merged["promotion_status"] = "pending_review"
        merged["review_state"] = "review"
        merged["note_role"] = "review"
    else:
        merged["review_state"] = "canonical" if (
            str(preferred.get("review_state") or "").casefold() == "canonical"
            or str(secondary.get("review_state") or "").casefold() == "canonical"
        ) else "review"
        merged["promotion_status"] = "promoted_canonical" if merged["review_state"] == "canonical" else "pending_review"
        merged["note_role"] = "primary" if merged["review_state"] == "canonical" else "review"
    merged["naming_quality"] = str(preferred.get("naming_quality") or secondary.get("naming_quality") or "unknown")
    merged["needs_review"] = bool(preferred.get("needs_review", False) or secondary.get("needs_review", False))
    merged["review_reason_code"] = str(preferred.get("review_reason_code") or secondary.get("review_reason_code") or "").strip()
    merged["review_reason_params"] = dict(preferred.get("review_reason_params") or secondary.get("review_reason_params") or {})
    merged["review_reason"] = str(preferred.get("review_reason") or secondary.get("review_reason") or "").strip()
    return merged


def _dedupe_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exact_bucket: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for raw in entities:
        if not isinstance(raw, dict):
            continue
        entity = dict(raw)
        entity["canonical_name"] = normalize_title(str(entity.get("canonical_name") or ""))
        entity["entity_kind"] = _normalize_entity_kind(entity.get("entity_kind"))
        if not entity["canonical_name"]:
            continue
        key = f"{entity['entity_kind']}::{_title_key(entity['canonical_name'])}"
        existing = exact_bucket.get(key)
        exact_bucket[key] = _merge_entities(existing, entity) if existing else entity

    ordered = list(exact_bucket.values())
    consumed: set[int] = set()
    merged_entities: list[dict[str, Any]] = []
    for index, entity in enumerate(ordered):
        if index in consumed:
            continue
        current = entity
        for other_index in range(index + 1, len(ordered)):
            if other_index in consumed:
                continue
            other = ordered[other_index]
            if _normalize_entity_kind(current.get("entity_kind")) != _normalize_entity_kind(other.get("entity_kind")):
                continue
            current_aliases = {_title_key(item) for item in _normalize_aliases(current.get("aliases"))}
            other_aliases = {_title_key(item) for item in _normalize_aliases(other.get("aliases"))}
            current_title = _title_key(str(current.get("canonical_name") or ""))
            other_title = _title_key(str(other.get("canonical_name") or ""))
            current_tokens = _token_set(str(current.get("canonical_name") or ""))
            other_tokens = _token_set(str(other.get("canonical_name") or ""))
            chapter_overlap = bool(set(current.get("chapter_refs") or []) & set(other.get("chapter_refs") or []))
            alias_overlap = bool(current_aliases & other_aliases) or current_title in other_aliases or other_title in current_aliases
            token_subset = bool(current_tokens and other_tokens) and (current_tokens <= other_tokens or other_tokens <= current_tokens)
            if alias_overlap or (token_subset and chapter_overlap):
                current = _merge_entities(current, other)
                consumed.add(other_index)
        merged_entities.append(current)
    merged_entities.sort(key=lambda item: (item.get("entity_kind", ""), str(item.get("canonical_name") or "").lower()))
    return merged_entities


def _canonical_primary_index(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entity in entities:
        normalized_title = normalize_title(str(entity.get("canonical_name") or ""))
        if not normalized_title:
            continue
        explicit_status = str(entity.get("promotion_status") or "").strip().casefold()
        if explicit_status:
            if explicit_status != "promoted_canonical":
                continue
        elif str(entity.get("review_state") or "canonical").casefold() != "canonical":
            continue
        if explicit_status != "promoted_canonical" and not should_promote_entity(entity):
            continue
        index[normalized_title] = {
            **entity,
            "canonical_name": normalized_title,
            "entity_kind": _normalize_entity_kind(entity.get("entity_kind")),
        }
    return index


def _review_entity_index(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entity in entities:
        normalized_title = normalize_title(str(entity.get("canonical_name") or ""))
        if not normalized_title:
            continue
        explicit_status = str(entity.get("promotion_status") or "").strip().casefold()
        if explicit_status:
            if explicit_status != "pending_review":
                continue
        elif str(entity.get("review_state") or "canonical").casefold() != "review":
            continue
        if explicit_status != "pending_review" and not _should_materialize_review_entity(entity):
            continue
        index[normalized_title] = {
            **entity,
            "canonical_name": normalized_title,
            "entity_kind": _normalize_entity_kind(entity.get("entity_kind")),
        }
    return index


def write_note(path: Path, *, frontmatter: dict[str, Any], body_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in frontmatter.items():
        if key == "tags":
            lines.append("tags:")
            for tag in value:
                lines.append(f"  - {json.dumps(str(tag), ensure_ascii=False)}")
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += ["---", ""] + body_lines
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _preferred_link_target(entity: dict[str, Any]) -> str:
    title = normalize_title(str(entity.get("canonical_name") or entity.get("canonical_subject") or ""))
    preferred_slug = str(entity.get("preferred_slug") or "").strip()
    return preferred_slug or slugify(title)


def _link_markup(entity: dict[str, Any], *, display_text: str | None = None) -> str:
    target = _preferred_link_target(entity)
    display = normalize_title(display_text or str(entity.get("canonical_name") or entity.get("canonical_subject") or ""))
    if display and slugify(display) != slugify(target):
        return f"[[{target}|{display}]]"
    return f"[[{target}]]"


def resolve_wikilinks(text: str, canonical_index: dict[str, dict[str, Any]]) -> str:
    if not text:
        return text
    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        raw = match.group(1)
        target = normalize_title(raw.split("|", 1)[0].split("#", 1)[0])
        token = f"__WIKILINK_{len(protected)}__"
        matched = _resolve_canonical_entity(target, canonical_index)
        if matched is not None:
            display = normalize_title(raw.split("|", 1)[1]) if "|" in raw else normalize_title(target)
            protected[token] = _link_markup(matched, display_text=display)
        else:
            protected[token] = normalize_title(raw.split("|", 1)[-1]) or normalize_title(raw)
        return token

    working = re.sub(r"\[\[([^\]]+)\]\]", protect, text)
    titles = sorted(
        {
            normalize_title(str(entity.get("canonical_name") or key))
            for key, entity in canonical_index.items()
            if normalize_title(str(entity.get("canonical_name") or key))
        },
        key=len,
        reverse=True,
    )
    for title in titles:
        entity = _resolve_canonical_entity(title, canonical_index)
        if entity is None:
            continue
        pattern = re.compile(rf"(?<!\[\[)(?<![\w]){re.escape(title)}(?![\w])(?!\]\])")
        working = pattern.sub(_link_markup(entity, display_text=title), working)
    for token, original in protected.items():
        working = working.replace(token, original)
    return working


def _normalize_frontmatter_entity(entity: dict[str, Any], *, role: str) -> dict[str, Any]:
    normalized_title = normalize_title(str(entity.get("canonical_name") or entity.get("canonical_subject") or ""))
    explicit_note_role = str(entity.get("note_role") or "").strip()
    explicit_promotion = str(entity.get("promotion_status") or "").strip().casefold()
    review_state = "review" if str(entity.get("review_state") or "").strip().casefold() == "review" else "canonical"
    if explicit_promotion == "pending_review":
        review_state = "review"
    elif explicit_promotion == "promoted_canonical":
        review_state = "canonical"
    note_role = explicit_note_role or ("review" if review_state == "review" else role)
    if note_role == "review":
        promotion_status = "pending_review"
        review_state = "review"
    else:
        promotion_status = "promoted_canonical"
        if review_state != "review":
            review_state = "canonical"
    entity_kind = _normalize_entity_kind(entity.get("entity_kind"))
    entity_subkind = _normalize_entity_subkind(
        entity_kind,
        entity.get("entity_subkind"),
        canonical_name=normalized_title,
        chapter_refs=entity.get("chapter_refs") or [],
    )
    return {
        "canonical_subject": normalized_title,
        "display_title": normalized_title,
        "review_state": review_state,
        "note_role": note_role,
        "promotion_status": promotion_status,
        "graph_exclude": review_state == "review",
        "retrieval_exclude": review_state == "review",
        "entity_kind": entity_kind,
        "entity_subkind": entity_subkind,
        "tags": taxonomy_tags(note_role=note_role, entity_kind=entity_kind, entity_subkind=entity_subkind),
    }


def _safe_primary_link(name: str, canonical_index: dict[str, dict[str, Any]]) -> str:
    matched = _resolve_canonical_entity(name, canonical_index)
    return _link_markup(matched, display_text=name) if matched else normalize_title(name)


def _resolve_canonical_entity(name: str, canonical_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    normalized = normalize_title(name)
    if not normalized:
        return None
    if normalized in canonical_index:
        return canonical_index[normalized]
    lookup_key = _title_key(normalized)
    for key, entity in canonical_index.items():
        if _title_key(key) == lookup_key:
            return entity
    return None


def validate_vault(vault_root: Path) -> None:
    errors: list[str] = []
    canonical_targets: set[str] = set()
    all_notes = sorted(vault_root.rglob("*.md"))

    for note_path in all_notes:
        text = note_path.read_text(encoding="utf-8")
        frontmatter = parse_obsidian_frontmatter(text)
        note_role = str(frontmatter.get("note_role") or "").strip()
        promotion_status = str(frontmatter.get("promotion_status") or "").strip()
        review_state = str(frontmatter.get("review_state") or "").strip()
        canonical_subject = str(frontmatter.get("canonical_subject") or "").strip()
        if review_state == "review" and promotion_status == "promoted_canonical":
            errors.append(f"review promoted as canonical: {note_path}")
        if review_state == "review" and note_role == "primary":
            errors.append(f"review stored as primary: {note_path}")
        if re.search(r"[\*\[\]·]", canonical_subject):
            errors.append(f"canonical_subject contains forbidden chars: {note_path}")
        if review_state == "review" and "/90_Review/" not in note_path.as_posix():
            errors.append(f"review note outside review folder: {note_path}")
        if review_state != "review" and "/90_Review/" in note_path.as_posix():
            errors.append(f"canonical note inside review folder: {note_path}")
        if note_role == "primary" and promotion_status == "promoted_canonical":
            slug = slugify(str(frontmatter.get("slug") or note_path.stem))
            canonical_targets.add(slug)

        raw_frontmatter = text.split("---\n", 2)[1] if text.startswith("---\n") and text.count("---\n") >= 2 else ""
        tag_lines = raw_frontmatter.splitlines()
        try:
            tag_index = tag_lines.index("tags:")
        except ValueError:
            tag_index = -1
        expected_tags = taxonomy_tags(
            note_role=note_role,
            entity_kind=str(frontmatter.get("entity_kind") or ""),
            entity_subkind=str(frontmatter.get("entity_subkind") or ""),
        )
        actual_tag_lines: list[str] = []
        if tag_index >= 0:
            for line in tag_lines[tag_index + 1 :]:
                if not line.startswith("  - "):
                    break
                actual_tag_lines.append(line)
        if not expected_tags or not actual_tag_lines:
            errors.append(f"tags missing or empty: {note_path}")
        else:
            expected_lines = [f"  - {json.dumps(tag, ensure_ascii=False)}" for tag in expected_tags]
            if actual_tag_lines != expected_lines:
                errors.append(f"tags invalid for role {note_role}: {note_path}")

    for note_path in all_notes:
        text = note_path.read_text(encoding="utf-8")
        frontmatter = parse_obsidian_frontmatter(text)
        linked_primary_subjects = frontmatter.get("linked_primary_subjects") or []
        normalized_subjects = [slugify(item) for item in _normalize_aliases(linked_primary_subjects) if normalize_title(item)]
        if any(item not in canonical_targets for item in normalized_subjects):
            errors.append(f"linked_primary_subjects contains non-canonical targets: {note_path}")
        for link in extract_obsidian_links(text):
            resolved = slugify(link)
            if resolved not in canonical_targets:
                errors.append(f"wikilink points to non-canonical target: {note_path} -> {link}")

    if errors:
        raise ValueError("Vault validation failed:\n" + "\n".join(f"- {item}" for item in errors))


def import_json_to_vault(*, source_json: Path, vault_root: Path) -> dict[str, Any]:
    payload = json.loads(source_json.read_text(encoding="utf-8"))
    work = payload.get("work") or {}
    labels = _labels_for_language(work.get("language"))
    chapters = payload.get("chapters") or []
    raw_entities = payload.get("entities") or []
    preserved_system_dir: Path | None = None

    if vault_root.exists():
        existing_system_dir = vault_root / "99_System"
        if existing_system_dir.exists():
            preserved_system_dir = Path(tempfile.mkdtemp(prefix="textifai_preserve_system_")) / "99_System"
            shutil.copytree(existing_system_dir, preserved_system_dir, dirs_exist_ok=True)
        shutil.rmtree(vault_root)

    for rel in [
        "01_Project",
        "02_World/Places",
        "02_World/Concepts",
        "02_World/Creatures",
        "02_World/Factions",
        "02_World/Objects",
        "02_World/Events",
        "03_Characters/Profiles",
        "04_Story/Chapters",
        "04_Story/Chapter_Summaries",
        "90_Review",
        "99_System",
    ]:
        (vault_root / rel).mkdir(parents=True, exist_ok=True)

    entities = _dedupe_entities(raw_entities)
    canonical_index = _canonical_primary_index(entities)
    review_index = _review_entity_index(entities)
    wikify = lambda text: resolve_wikilinks(text, canonical_index)
    chapter_title_by_id = {
        str(item.get("chapter_id") or "").strip(): normalize_title(
            str(item.get("chapter_title_original") or item.get("chapter_title_canonical") or "")
        )
        for item in chapters
    }

    created_primary_paths: list[str] = []
    skipped_primaries: list[dict[str, str]] = []
    review_primary_paths: list[str] = []
    for entity in entities:
        title = normalize_title(str(entity.get("canonical_name") or ""))
        if not title:
            skipped_primaries.append({"title": "", "reason": "missing_title"})
            continue
        review_state = str(entity.get("review_state") or "canonical").casefold()
        if title in canonical_index:
            canonical_entity = canonical_index[title]
            taxonomy = taxonomy_payload_for_entity(canonical_entity)
            entity_kind = taxonomy["entity_kind"]
            entity_subkind = taxonomy["entity_subkind"]
            target_dir = PRIMARY_DIRS.get(entity_kind, "02_World/Concepts")
            state = _normalize_frontmatter_entity(canonical_entity, role="primary")
        elif title in review_index:
            canonical_entity = review_index[title]
            taxonomy = taxonomy_payload_for_entity(canonical_entity)
            entity_kind = taxonomy["entity_kind"]
            entity_subkind = taxonomy["entity_subkind"]
            target_dir = "90_Review"
            state = _normalize_frontmatter_entity(canonical_entity, role="primary")
        else:
            reason = "failed_should_promote" if review_state != "review" else "failed_review_materialization"
            skipped_primaries.append({"title": title, "reason": reason})
            continue

        rel_dir = PRIMARY_DIRS.get(entity_kind, "02_World/Concepts")
        slug = str(canonical_entity.get("preferred_slug") or "").strip() or slugify(title)
        aliases = _normalize_aliases(canonical_entity.get("aliases"))
        chapter_titles = dedupe([
            chapter_title_by_id.get(str(ref).strip(), normalize_title(str(ref).strip()))
            for ref in (canonical_entity.get("chapter_refs") or [])
            if str(ref).strip()
        ])
        relationships = _normalize_relationships(canonical_entity.get("relationships") or [])
        key_facts = dedupe([str(fact).strip() for fact in (canonical_entity.get("key_facts") or []) if str(fact).strip()])
        summary = wikify(str(canonical_entity.get("summary") or "").strip())

        body_lines = [f"# {title}", ""]
        if summary:
            body_lines += [f"## {labels['overview']}", "", summary, ""]
        if key_facts:
            body_lines += [f"## {labels['key_facts']}", ""]
            body_lines += [f"- {wikify(fact)}" for fact in key_facts[:12]]
            body_lines += [""]
        if relationships:
            body_lines += [f"## {labels['relationships']}", ""]
            for rel in relationships[:12]:
                target = normalize_title(str(rel.get("target") or ""))
                rel_type = str(rel.get("type") or "").strip()
                facts = [str(fact).strip() for fact in (rel.get("facts") or []) if str(fact).strip()]
                line = f"- {_safe_primary_link(target, canonical_index)}" if target else "- Related entity"
                if rel_type:
                    line += f" ({rel_type})"
                if facts:
                    line += f": {wikify(facts[0])}"
                body_lines.append(line)
            body_lines += [""]
        if chapter_titles:
            body_lines += [f"## {labels['source_chapters']}", ""]
            body_lines += [f"- {title_ref}" for title_ref in chapter_titles[:20]]
            body_lines += [""]

        frontmatter = {
            "kind": "location" if entity_kind == "place" else entity_kind,
            "title": title,
            "display_title": state["display_title"],
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": slug,
            "artifact_stage": "promoted_artifact",
            "promotion_status": state["promotion_status"],
            "note_role": state["note_role"],
            "entity_kind": entity_kind,
            "entity_subkind": entity_subkind,
            "canonical_subject": state["canonical_subject"],
            "aliases": aliases,
            "semantic_class": taxonomy["semantic_class"],
            "evidence_sources": chapter_titles,
            "confidence": float(canonical_entity.get("confidence") or 0.0),
            "review_state": state["review_state"],
            "graph_exclude": state["graph_exclude"],
            "retrieval_exclude": state["retrieval_exclude"],
            "tags": state["tags"],
            "linked_primary_subjects": [],
        }
        note_path = vault_root / (target_dir if title in review_index else rel_dir) / f"{slug}.md"
        write_note(note_path, frontmatter=frontmatter, body_lines=body_lines)
        if title in review_index:
            review_primary_paths.append(str(note_path))
        else:
            created_primary_paths.append(str(note_path))

    chapter_paths: list[str] = []
    summary_paths: list[str] = []

    for chapter in chapters:
        original_title = str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "").strip()
        title = normalize_title(original_title)
        if not title:
            continue
        slug = slugify(str(chapter.get("chapter_title_canonical") or title))
        seq = int(chapter.get("sequence_index") or 0)
        summary = wikify(str(chapter.get("chapter_summary") or "").strip())
        text = wikify(str(chapter.get("chapter_text_markdown") or "").strip())

        linked_primaries: list[str] = []
        chapter_body = [f"# {original_title}", ""]
        if summary:
            chapter_body += [f"## {labels['summary']}", "", summary, ""]
        if text:
            chapter_body += [f"## {labels['chapter_text']}", "", text, ""]

        for heading, key in [
            (labels["characters"], "characters"),
            (labels["places"], "places"),
            (labels["concepts"], "concepts"),
            (labels["events"], "events"),
        ]:
            items = chapter.get(key) or []
            if not items:
                continue
            chapter_body += [f"## {heading}", ""]
            for item in items[:20]:
                if not isinstance(item, dict):
                    continue
                canonical = normalize_title(str(item.get("canonical") or item.get("surface") or ""))
                facts = [str(fact).strip() for fact in (item.get("facts") or []) if str(fact).strip()]
                matched_canonical = _resolve_canonical_entity(canonical, canonical_index)
                if matched_canonical:
                    linked_primaries.append(_preferred_link_target(matched_canonical))
                label = _safe_primary_link(canonical, canonical_index) if canonical else normalize_title(str(item.get("surface") or ""))
                line = f"- {label}" if label else "- Item"
                if facts:
                    line += f": {wikify(facts[0])}"
                chapter_body.append(line)
            chapter_body += [""]

        relations = chapter.get("relations") or []
        if relations:
            chapter_body += [f"## {labels['relations']}", ""]
            for rel in relations[:20]:
                if not isinstance(rel, dict):
                    continue
                source = normalize_title(str(rel.get("from_canonical") or rel.get("from_surface") or rel.get("from") or ""))
                target = normalize_title(str(rel.get("to_canonical") or rel.get("to_surface") or rel.get("to") or ""))
                rel_type = str(rel.get("relation_type") or rel.get("type") or "").strip()
                facts = [str(fact).strip() for fact in (rel.get("facts") or []) if str(fact).strip()]
                left = _safe_primary_link(source, canonical_index) if source else "Relation"
                right = _safe_primary_link(target, canonical_index) if target else "Relation"
                line = f"- {left} -> {right}"
                if rel_type:
                    line += f" ({rel_type})"
                if facts:
                    line += f": {wikify(facts[0])}"
                chapter_body.append(line)
            chapter_body += [""]

        linked_primaries = dedupe(linked_primaries)
        chapter_frontmatter = {
            "kind": "chapter",
            "title": title,
            "display_title": title,
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": slug,
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "chapter",
            "entity_kind": "chapter",
            "entity_subkind": "",
            "canonical_subject": title,
            "source_title": title,
            "source_sequence_index": seq,
            "semantic_class": "chapter_structured_json",
            "source_path": str(source_json),
            "linked_primary_subjects": linked_primaries,
            "evidence_sources": [str(source_json)],
            "confidence": 0.8,
            "review_state": "canonical",
            "graph_exclude": True,
            "retrieval_exclude": True,
            "tags": taxonomy_tags(note_role="chapter"),
        }
        chapter_path = vault_root / "04_Story/Chapters" / f"{slug}.md"
        write_note(chapter_path, frontmatter=chapter_frontmatter, body_lines=chapter_body)
        chapter_paths.append(str(chapter_path))

        summary_frontmatter = dict(chapter_frontmatter)
        summary_frontmatter.update(
            {
                "kind": "chapter_summary",
                "title": f"{title} {labels['chapter_summary_suffix']}",
                "display_title": f"{title} {labels['chapter_summary_suffix']}",
                "slug": f"{slug}_summary",
                "note_role": "chapter_summary",
                "entity_kind": "chapter_summary",
                "entity_subkind": "",
                "semantic_class": "chapter_summary",
                "summary_for_chapter": chapter_path.name,
                "tags": taxonomy_tags(note_role="chapter_summary"),
            }
        )
        summary_body = [f"# {original_title} {labels['chapter_summary_suffix']}", "", summary or labels["no_summary"], ""]
        if linked_primaries:
            summary_body += [f"## {labels['linked_primaries']}", ""]
            summary_body += [f"- {_safe_primary_link(name, canonical_index)}" for name in linked_primaries[:20]]
            summary_body += [""]
        summary_path = vault_root / "04_Story/Chapter_Summaries" / f"{slug}_summary.md"
        write_note(summary_path, frontmatter=summary_frontmatter, body_lines=summary_body)
        summary_paths.append(str(summary_path))

    audit = {
        "source_json": str(source_json),
        "work": work,
        "vault_root": str(vault_root),
        "chapter_count": len(chapters),
        "summary_count": len(summary_paths),
        "primary_count": len(created_primary_paths),
        "review_primary_count": len(review_primary_paths),
        "skipped_primary_count": len(skipped_primaries),
        "primary_paths": created_primary_paths,
        "review_primary_paths": review_primary_paths,
        "skipped_primaries": skipped_primaries,
        "chapter_paths": chapter_paths,
        "summary_paths": summary_paths,
        "sample_primary_paths": created_primary_paths[:20],
        "sample_chapter_paths": chapter_paths[:10],
    }
    write_note(
        vault_root / "01_Project" / "import_manifest.md",
        frontmatter={
            "kind": "project_note",
            "title": labels["import_manifest"],
            "display_title": labels["import_manifest"],
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": "import_manifest",
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "system",
            "entity_kind": "system",
            "entity_subkind": "",
            "canonical_subject": labels["import_manifest"],
            "aliases": [],
            "semantic_class": "import_manifest",
            "evidence_sources": [str(source_json)],
            "confidence": 1.0,
            "review_state": "canonical",
            "graph_exclude": True,
            "retrieval_exclude": True,
            "tags": taxonomy_tags(note_role="system"),
            "linked_primary_subjects": [],
        },
        body_lines=[
            f"# {labels['import_manifest']}",
            "",
            f"- Source JSON: `{source_json}`",
            f"- Title: {work.get('title', 'Unknown')}",
            f"- Language: {work.get('language', labels['unknown_language'])}",
            f"- Chapters: {len(chapters)}",
            f"- Primaries: {len(created_primary_paths)}",
            "",
        ],
    )
    (vault_root / "99_System" / "json_import_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if preserved_system_dir is not None and preserved_system_dir.exists():
        for item in preserved_system_dir.iterdir():
            target = vault_root / "99_System" / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        shutil.rmtree(preserved_system_dir.parent, ignore_errors=True)
    validate_vault(vault_root)
    return audit
