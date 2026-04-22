from __future__ import annotations

import json
import re
import shutil
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


PRIMARY_DIRS = {
    "character": "03_Characters/Profiles",
    "place": "02_World/Places",
    "concept": "02_World/Lore",
    "magic": "02_World/Magic",
    "creature": "02_World/Creatures",
    "faction": "02_World/Factions",
    "object": "02_World/Objects",
    "lore": "02_World/Lore",
    "event": "02_World/History",
    "history": "02_World/History",
}

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


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = text.replace("·", " ").replace("’", "").replace("'", "")
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "_", text).strip("_")
    return text or "note"


def _is_numeric_note_title(text: str) -> bool:
    compact = re.sub(r"[\s._-]+", "", str(text).strip())
    return bool(compact) and compact.isdigit()


def _has_meaningful_primary_content(entity: dict[str, Any]) -> bool:
    summary = str(entity.get("summary") or "").strip()
    key_facts = [str(fact).strip() for fact in (entity.get("key_facts") or []) if str(fact).strip()]
    relationships = [item for item in (entity.get("relationships") or []) if isinstance(item, dict)]
    aliases = [str(alias).strip() for alias in (entity.get("aliases") or []) if str(alias).strip()]
    return bool(summary or key_facts or relationships or aliases)


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def write_note(path: Path, *, frontmatter: dict[str, Any], body_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in frontmatter.items():
        if key == "tags":
            lines.append("tags:")
            for tag in value:
                lines.append(f"  - {tag}")
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += ["---", ""] + body_lines
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_wikifier(primary_titles: list[str]):
    ordered = sorted({title.strip() for title in primary_titles if title.strip()}, key=len, reverse=True)

    def wikify(text: str) -> str:
        if not text:
            return text
        protected: dict[str, str] = {}

        def protect(match: re.Match[str]) -> str:
            token = f"__WIKILINK_{len(protected)}__"
            protected[token] = match.group(0)
            return token

        working = re.sub(r"\[\[[^\]]+\]\]", protect, text)
        for title in ordered:
            pattern = re.compile(rf"(?<!\[\[)(?<![\w]){re.escape(title)}(?![\w])(?!\]\])")
            working = pattern.sub(f"[[{title}]]", working)
        for token, original in protected.items():
            working = working.replace(token, original)
        return working

    return wikify


def import_json_to_vault(*, source_json: Path, vault_root: Path) -> dict[str, Any]:
    payload = json.loads(source_json.read_text(encoding="utf-8"))
    work = payload.get("work") or {}
    labels = _labels_for_language(work.get("language"))
    chapters = payload.get("chapters") or []
    entities = payload.get("entities") or []
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
        "02_World/Lore",
        "02_World/Magic",
        "02_World/Creatures",
        "02_World/Factions",
        "02_World/Objects",
        "02_World/History",
        "03_Characters/Profiles",
        "04_Story/Chapters",
        "04_Story/Chapter_Summaries",
        "90_Review",
        "99_System",
    ]:
        (vault_root / rel).mkdir(parents=True, exist_ok=True)

    chapter_title_by_id = {
        str(item.get("chapter_id") or "").strip(): str(item.get("chapter_title_original") or item.get("chapter_title_canonical") or "").strip()
        for item in chapters
    }
    primary_titles = [str(item.get("canonical_name") or "").strip() for item in entities]
    wikify = build_wikifier(primary_titles)

    created_primary_paths: list[str] = []
    skipped_primaries: list[dict[str, str]] = []
    review_primary_paths: list[str] = []
    for entity in entities:
        title = str(entity.get("canonical_name") or "").strip()
        if not title:
            skipped_primaries.append({"title": "", "reason": "missing_title"})
            continue
        if _is_numeric_note_title(title):
            skipped_primaries.append({"title": title, "reason": "numeric_title"})
            continue
        if not _has_meaningful_primary_content(entity):
            skipped_primaries.append({"title": title, "reason": "insufficient_content"})
            continue
        entity_kind = str(entity.get("entity_kind") or "lore").strip().casefold()
        rel_dir = PRIMARY_DIRS.get(entity_kind, "02_World/Lore")
        slug = str(entity.get("preferred_slug") or "").strip() or slugify(title)
        if _is_numeric_note_title(slug):
            skipped_primaries.append({"title": title, "reason": "numeric_slug"})
            continue
        aliases = dedupe([str(alias).strip() for alias in (entity.get("aliases") or []) if str(alias).strip()])
        chapter_titles = [
            chapter_title_by_id.get(str(ref).strip(), str(ref).strip())
            for ref in (entity.get("chapter_refs") or [])
            if str(ref).strip()
        ]
        chapter_titles = dedupe(chapter_titles)
        relationships = entity.get("relationships") or []
        key_facts = dedupe([str(fact).strip() for fact in (entity.get("key_facts") or []) if str(fact).strip()])
        summary = wikify(str(entity.get("summary") or "").strip())
        review_state = str(entity.get("review_state") or "canonical").strip().casefold() or "canonical"
        is_review = review_state != "canonical"
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
                if not isinstance(rel, dict):
                    continue
                target = str(rel.get("target") or "").strip()
                rel_type = str(rel.get("type") or "").strip()
                facts = [str(fact).strip() for fact in (rel.get("facts") or []) if str(fact).strip()]
                line = f"- [[{target}]]" if target else "- Related entity"
                if rel_type:
                    line += f" ({rel_type})"
                if facts:
                    line += f": {wikify(facts[0])}"
                body_lines.append(line)
            body_lines += [""]
        if chapter_titles:
            body_lines += [f"## {labels['source_chapters']}", ""]
            body_lines += [f"- [[{title_ref}]]" for title_ref in chapter_titles[:20]]
            body_lines += [""]

        frontmatter = {
            "kind": "location" if entity_kind == "place" else entity_kind,
            "title": title,
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": slug,
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "primary",
            "entity_kind": entity_kind,
            "canonical_subject": title,
            "aliases": ", ".join(aliases),
            "semantic_class": entity_kind,
            "evidence_sources": ", ".join(chapter_titles),
            "confidence": float(entity.get("confidence") or 0.0),
            "review_state": review_state,
            "graph_exclude": is_review,
            "retrieval_exclude": is_review,
            "tags": ["#review"] if is_review else ["#primary"],
        }
        note_path = vault_root / ("90_Review" if is_review else rel_dir) / f"{slug}.md"
        write_note(note_path, frontmatter=frontmatter, body_lines=body_lines)
        if is_review:
            review_primary_paths.append(str(note_path))
        else:
            created_primary_paths.append(str(note_path))

    chapter_paths: list[str] = []
    summary_paths: list[str] = []
    chapter_refs_by_title: dict[str, list[str]] = defaultdict(list)

    for chapter in chapters:
        title = str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "").strip()
        if not title:
            continue
        slug = slugify(str(chapter.get("chapter_title_canonical") or title))
        seq = int(chapter.get("sequence_index") or 0)
        summary = wikify(str(chapter.get("chapter_summary") or "").strip())
        text = wikify(str(chapter.get("chapter_text_markdown") or "").strip())

        linked_primaries: list[str] = []
        chapter_body = [f"# {title}", ""]
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
                canonical = str(item.get("canonical") or item.get("surface") or "").strip()
                if canonical:
                    linked_primaries.append(canonical)
                facts = [str(fact).strip() for fact in (item.get("facts") or []) if str(fact).strip()]
                line = f"- [[{canonical}]]" if canonical else f"- {str(item.get('surface') or '').strip()}"
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
                source = str(rel.get("from_canonical") or rel.get("from_surface") or rel.get("from") or "").strip()
                target = str(rel.get("to_canonical") or rel.get("to_surface") or rel.get("to") or "").strip()
                rel_type = str(rel.get("relation_type") or rel.get("type") or "").strip()
                facts = [str(fact).strip() for fact in (rel.get("facts") or []) if str(fact).strip()]
                line = f"- [[{source}]] -> [[{target}]]" if source and target else "- Relation"
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
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": slug,
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "chapter",
            "entity_kind": "chapter",
            "canonical_subject": title,
            "source_title": title,
            "source_sequence_index": seq,
            "semantic_class": "chapter_structured_json",
            "source_path": str(source_json),
            "linked_primary_subjects": ", ".join(linked_primaries),
            "evidence_sources": str(source_json),
            "confidence": 0.8,
            "review_state": "canonical",
            "graph_exclude": True,
            "retrieval_exclude": True,
            "tags": ["#chapter", "#chapters"],
        }
        chapter_path = vault_root / "04_Story/Chapters" / f"{slug}.md"
        write_note(chapter_path, frontmatter=chapter_frontmatter, body_lines=chapter_body)
        chapter_paths.append(str(chapter_path))

        summary_frontmatter = dict(chapter_frontmatter)
        summary_frontmatter.update(
            {
                "kind": "chapter_summary",
                "title": f"{title} {labels['chapter_summary_suffix']}",
                "slug": f"{slug}_summary",
                "note_role": "chapter_summary",
                "entity_kind": "chapter_summary",
                "semantic_class": "chapter_summary",
                "summary_for_chapter": chapter_path.name,
            }
        )
        summary_body = [f"# {title} {labels['chapter_summary_suffix']}", "", summary or labels["no_summary"], ""]
        if linked_primaries:
            summary_body += [f"## {labels['linked_primaries']}", ""]
            summary_body += [f"- [[{name}]]" for name in linked_primaries[:20]]
            summary_body += [""]
        summary_path = vault_root / "04_Story/Chapter_Summaries" / f"{slug}_summary.md"
        write_note(summary_path, frontmatter=summary_frontmatter, body_lines=summary_body)
        summary_paths.append(str(summary_path))
        chapter_refs_by_title[title] = linked_primaries

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
            "status": "pending_revision",
            "schema_version": "1.0",
            "slug": "import_manifest",
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "system",
            "entity_kind": "system",
            "canonical_subject": labels["import_manifest"],
            "aliases": "",
            "semantic_class": "import_manifest",
            "evidence_sources": str(source_json),
            "confidence": 1.0,
            "review_state": "canonical",
            "graph_exclude": True,
            "retrieval_exclude": True,
            "tags": ["#system"],
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
    return audit
