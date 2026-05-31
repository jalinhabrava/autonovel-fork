"""EntityCardViewModel: canonical entity card combining author_graph, VaERL, Markdown, backlinks, review."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from textifai.obsidian.parser import parse_obsidian_frontmatter


CANONICAL_KIND_PRIORITY = {
    "character": 700,
    "place": 600,
    "object": 500,
    "event": 400,
    "concept": 300,
    "review": 200,
    "chapter": 100,
    "resolved": 100,
    "unresolved": 0,
}


def canonical_kind_sort_key(entity: dict[str, Any]) -> int:
    """Higher priority kind wins."""
    k = entity.get("kind", "unresolved")
    return CANONICAL_KIND_PRIORITY.get(k, 0)


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def depluralize_aliases(aliases: list[str]) -> list[str]:
    """Normalize common plural/singular variants."""
    seen: set[str] = set()
    result: list[str] = []
    for a in aliases:
        a_clean = a.strip()
        if not a_clean or a_clean in seen:
            continue
        seen.add(a_clean)
        result.append(a_clean)
    return result


def classify_alias(alias: str, entity_kind: str) -> str:
    """Return alias category: canonical, contextual, needs_review, suppressed."""
    a = alias.lower().strip()
    # POV pronouns
    if a in ("yo", "yo (narrador)", "yo (narrador en primera persona)", "ella", "él", "ellos", "ellas", "nosotros"):
        return "contextual"
    # Generic descriptors that need review
    generic_descriptors = ("una chica", "un chico", "la chica", "el chico", "una mujer", "un hombre",
                          "un anciano", "una anciana", "el hombre", "la mujer", "un desconocido",
                          "protagonista", "narrador", "narradora", "el protagonista", "la protagonista",
                          "chico", "chica", "niño", "niña", "mujer", "hombre")
    if a in generic_descriptors:
        return "needs_review"
    # Suppressed: empty, trivial
    if len(a) < 2 or a in ("", " ", "un", "una", "el", "la", "los", "las"):
        return "suppressed"
    # Check if alias equals canonical name (same entity)
    return "canonical"


def build_entity_card(
    project_root: Path,
    node_id: str | None = None,
    note_path: str | None = None,
    canonical_label: str | None = None,
) -> dict[str, Any]:
    """Build EntityCardViewModel from all data sources in the project."""

    graph_path = project_root / "graph" / "author_graph.json"
    entities_path = project_root / "vaerl" / "entities.json"
    relationships_path = project_root / "vaerl" / "relationships.json"
    review_path = project_root / "vaerl" / "review_queue.json"
    backlinks_path = project_root / "graph" / "backlinks.json"
    markdown_index_path = project_root / "graph" / "markdown_graph_index.json"

    graph = load_json(graph_path) if isinstance(load_json(graph_path), dict) else {}
    entities_data = load_json(entities_path) if isinstance(load_json(entities_path), dict) else {}
    relationships_data = load_json(relationships_path) if isinstance(load_json(relationships_path), dict) else {}
    review_data = load_json(review_path) if isinstance(load_json(review_path), dict) else {}
    backlinks_data = load_json(backlinks_path) if isinstance(load_json(backlinks_path), dict) else {}
    markdown_index = load_json(markdown_index_path) if isinstance(load_json(markdown_index_path), dict) else {}

    # Collect all entities from vaerl
    entities: list[dict[str, Any]] = []
    if isinstance(entities_data, dict):
        entities = entities_data.get("entities", entities_data.get("primaries", []))
    if isinstance(entities_data, list):
        entities = entities_data

    # Build label -> entity map with kind priority dedup
    label_entity_map: dict[str, dict[str, Any]] = {}
    for e in entities:
        label = e.get("canonical_name", e.get("label", e.get("id", "")))
        if not label:
            continue
        existing = label_entity_map.get(label)
        if existing and canonical_kind_sort_key(e) <= canonical_kind_sort_key(existing):
            continue
        label_entity_map[label] = e

    # Find the node in author_graph
    all_nodes = graph.get("nodes", [])
    all_edges = graph.get("edges", [])

    def match_node(n: dict[str, Any]) -> bool:
        if node_id and (n.get("id") == node_id or n.get("canonical_id") == node_id):
            return True
        if note_path and (n.get("note_path") == note_path or n.get(
                "notePath") == note_path):
            return True
        if canonical_label and n.get("label", "").lower() == canonical_label.lower():
            return True
        return False

    target_node = None
    for n in all_nodes:
        if match_node(n):
            target_node = n
            break

    if not target_node and canonical_label:
        # fallback: find first node with similar label
        for n in all_nodes:
            if n.get("label", "").lower().find(canonical_label.lower()) >= 0:
                target_node = n
                break

    if not target_node and node_id:
        # fallback by id prefix
        for n in all_nodes:
            if n.get("id", "").lower().find(node_id.lower()) >= 0:
                target_node = n
                break

    if not target_node:
        return {"error": "entity_not_found", "node_id": node_id, "note_path": note_path}

    label: str = target_node.get("label", target_node.get("id", ""))
    kind: str = target_node.get("kind", target_node.get("display_kind", "unresolved"))

    # VaERL entity data
    vaerl_entity = label_entity_map.get(label, {})
    if not vaerl_entity:
        # Try case-insensitive
        for k, v in label_entity_map.items():
            if k.lower() == label.lower():
                vaerl_entity = v
                break

    # Incident edges from graph
    incident_edges = [
        e for e in all_edges
        if e.get("source", "").endswith(label) or e.get("target", "").endswith(label)
    ]
    relation_count = len(incident_edges)

    # Build relationship list from VaERL relationships + incident edges
    all_vaerl_rels: list[dict[str, Any]] = []
    if isinstance(relationships_data, dict):
        all_vaerl_rels = relationships_data.get("relationships", relationships_data.get("edges", []))
    elif isinstance(relationships_data, list):
        all_vaerl_rels = relationships_data

    relationships: list[dict[str, Any]] = []
    seen_rel: set[str] = set()
    for e in incident_edges:
        s = e.get("source", "")
        t = e.get("target", "")
        rel_label = e.get("relation_label", "")
        # Convert paths to labels
        s_label = _path_to_label(s)
        t_label = _path_to_label(t)
        key = f"{s_label}|{t_label}|{rel_label}"
        if key not in seen_rel:
            seen_rel.add(key)
            relationships.append({
                "source": s_label,
                "predicate": rel_label,
                "target": t_label,
                "kind": e.get("kind", ""),
                "evidence_count": e.get("evidence_count", 0),
                "review_state": e.get("review_state", "ready"),
            })
    # Also add VaERL relationships
    for r in all_vaerl_rels:
        source = r.get("source", r.get("subject", ""))
        target = r.get("target", r.get("object", ""))
        predicate = r.get("predicate", r.get("relation_type", r.get("type", "")))
        if source.lower() == label.lower() or target.lower() == label.lower() or source.lower() in label.lower() or label.lower() in source.lower():
            key = f"{source}|{predicate}|{target}"
            if key not in seen_rel:
                seen_rel.add(key)
                relationships.append({
                    "source": source,
                    "predicate": predicate,
                    "target": target,
                    "kind": r.get("kind", ""),
                    "evidence_count": r.get("evidence_count", 0),
                    "review_state": "ready",
                })
                relation_count = len(relationships)

    # Backlinks
    backlinks: list[str] = []
    bl_by_note = {}
    if isinstance(backlinks_data, dict):
        bl_by_note = backlinks_data.get("backlinks_by_note", backlinks_data)
    note_p = target_node.get("note_path", target_node.get("notePath", ""))
    if note_p and isinstance(bl_by_note, dict):
        bl_list = bl_by_note.get(note_p, [])
        if isinstance(bl_list, list):
            backlinks = [_path_to_label(b) if isinstance(b, str) else b.get("source", str(b)) for b in bl_list]

    # Outgoing links from markdown index
    outgoing: list[dict[str, str]] = []
    if isinstance(markdown_index, dict) and note_p:
        md_notes = markdown_index.get("notes", markdown_index.get("nodes", []))
        md_target = _markdown_index_note(markdown_index, note_p)
        if md_target:
            links = md_target.get("links", [])
            outgoing = [{"label": _path_to_label(l) if isinstance(l, str) else l} for l in links[:30]]

    # Evidence refs
    evidence_refs: list[dict[str, Any]] = vaerl_entity.get("evidence_refs", [])
    evidence_count = len(evidence_refs)
    if evidence_count == 0:
        evidence_count = vaerl_entity.get("evidence_count", 0)
    if evidence_count == 0:
        evidence_count = target_node.get("evidence_count", 0)
    if evidence_count == 0:
        # Count from relationships
        evidence_count = sum(r.get("evidence_count", 0) for r in relationships)

    # Aliases from VaERL entity + graph node
    raw_aliases: list[str] = []
    if vaerl_entity:
        raw_aliases = list(vaerl_entity.get("aliases", []))
    for a in target_node.get("aliases", []):
        if a not in raw_aliases:
            raw_aliases.append(a)

    # Alias classification
    canonical_aliases: list[str] = []
    contextual_refs: list[str] = []
    needs_review: list[str] = []
    suppressed: list[str] = []
    for a in depluralize_aliases(raw_aliases):
        cat = classify_alias(a, kind)
        if cat == "canonical":
            canonical_aliases.append(a)
        elif cat == "contextual":
            contextual_refs.append(a)
        elif cat == "needs_review":
            needs_review.append(a)
        else:
            suppressed.append(a)

    # Summary
    summary = vaerl_entity.get("summary", vaerl_entity.get("description", ""))
    if not summary:
        summary = target_node.get("summary_excerpt", target_node.get("summaryExcerpt", ""))

    # Markdown note content
    markdown_sections: list[dict[str, Any]] = []
    author_markdown = ""
    technical_markdown = ""
    frontmatter: dict[str, Any] = {}
    note_path_final = note_p or ""

    note_full_path = project_root / note_path_final if note_path_final else None
    if note_full_path and note_full_path.exists():
        raw_md = note_full_path.read_text(encoding="utf-8")
        parsed = parse_obsidian_frontmatter(raw_md)
        if isinstance(parsed, tuple):
            fm, body = parsed
        elif isinstance(parsed, dict):
            fm = parsed.get("frontmatter", {}) or {}
            body = parsed.get("body", parsed.get("content", raw_md)) or raw_md
        else:
            fm = {}
            body = raw_md
        frontmatter = fm if fm else {}
        # Build sections from body
        sections = _parse_markdown_sections(str(body))
        markdown_sections = [{"title": s[0], "body": s[1]} for s in sections]
        # Author-facing: hide frontmatter, show sections
        author_markdown = _build_author_markdown(label, kind, canonical_aliases, contextual_refs,
                                                  needs_review, summary, relationships,
                                                  backlinks, outgoing, evidence_count)
        # Technical: frontmatter + raw IDs
        technical_markdown = f"Ruta: {note_path_final}\nFrontmatter:\n" + json.dumps(frontmatter, indent=2)
    else:
        # Build synthesised markdown from entity data
        author_markdown = _build_author_markdown(label, kind, canonical_aliases, contextual_refs,
                                                  needs_review, summary, relationships,
                                                  backlinks, outgoing, evidence_count)
        technical_markdown = f"Nota no encontrada: {note_path_final}"

    # Review items for this entity
    review_items: list[dict[str, Any]] = []
    review_queue_items = review_data.get("items", review_data.get("review_queue",
                                        review_data.get("queue", [])))
    if isinstance(review_queue_items, list):
        for item in review_queue_items:
            src = item.get("source_refs", item.get("source", ""))
            src_label = str(src)
            tgt_label = item.get("target_label", "")
            if label.lower() in src_label.lower() or (tgt_label and label.lower() in tgt_label.lower()):
                review_items.append(item)

    # Degree from graph
    degree = target_node.get("degree", 0)
    if degree == 0:
        degree = relation_count

    # Local graph
    local_graph_nodes = []
    local_graph_edges = []
    try:
        from textifai.import_review.markdown_graph_index import local_graph as lg_fn
        if note_path_final:
            lg_result = lg_fn(project_root, note_path_final)
            if isinstance(lg_result, dict):
                local_graph_nodes = lg_result.get("nodes", [])
                local_graph_edges = lg_result.get("edges", [])
    except Exception:
        pass

    return {
        "schema": "textifai.entity_card",
        "schema_version": 1,
        "id": target_node.get("id", label),
        "canonical_label": label,
        "display_label": label,
        "kind": kind,
        "status": target_node.get("review_state", "ready"),
        "summary": summary,
        "degree": degree,
        "relation_count": relation_count,
        "evidence_count": evidence_count,
        "aliases": {
            "canonical": canonical_aliases,
            "contextual": contextual_refs,
            "needs_review": needs_review,
            "suppressed": suppressed,
        },
        "relationships": relationships[:30],
        "backlinks": backlinks[:20],
        "outgoing_links": outgoing[:20],
        "local_graph": {
            "node_count": len(local_graph_nodes),
            "edge_count": len(local_graph_edges),
        },
        "review": {
            "count": len(review_items),
            "items": review_items[:10],
        },
        "markdown": {
            "note_path": note_path_final,
            "sections": markdown_sections,
            "author_markdown": author_markdown,
            "technical_markdown": technical_markdown,
        },
        "evidence_refs": evidence_refs[:20],
        "technical": {
            "node_id": target_node.get("id"),
            "canonical_id": target_node.get("canonical_id"),
            "note_path_resolved": note_path_final,
            "vaerl_entity_found": bool(vaerl_entity),
        },
    }


def _path_to_label(path: str) -> str:
    """Convert a file path to a display label."""
    name = path.split("/")[-1]
    name = name.replace(".md", "")
    name = name.replace("_", " ")
    return name


def _markdown_index_note(index: dict[str, Any], note_path: str) -> dict[str, Any] | None:
    notes = index.get("notes", index.get("nodes", []))
    for n in notes:
        if isinstance(n, dict) and n.get("path") == note_path:
            return n
    return None


def _parse_markdown_sections(body: str) -> list[tuple[str, str]]:
    lines = body.split("\n")
    sections: list[tuple[str, str]] = [("", "")]
    for line in lines:
        if line.startswith("## ") or line.startswith("# "):
            sections.append((line.strip("# ") + ("" if not line.startswith("## ") else ""), ""))
        else:
            sections[-1] = (sections[-1][0], sections[-1][1] + line + "\n")
    return [(s[0].strip(), s[1].strip()) for s in sections if s[1].strip()]


def _build_author_markdown(
    label: str,
    kind: str,
    canonical_aliases: list[str],
    contextual_refs: list[str],
    needs_review: list[str],
    summary: str,
    relationships: list[dict[str, Any]],
    backlinks: list[str],
    outgoing: list[dict[str, str]],
    evidence_count: int,
) -> str:
    lines = [f"# {label}", f"_{kind}_", ""]
    if summary:
        lines.append(summary)
        lines.append("")
    del canonical_aliases, contextual_refs, needs_review, relationships, backlinks, outgoing, evidence_count
    lines.append("---")
    lines.append("_Cuerpo editorial inicial. Los alias, relaciones, evidencias y enlaces calculados viven en tarjetas fuera del editor. Sin write-back automático._")
    return "\n".join(lines)


def entity_card_endpoint(project_reader: Any, project_id: str, node_id: str = "",
                         note_path: str = "", canonical_label: str = "") -> dict[str, Any]:
    """Handler for /api/projects/<id>/entity-card."""
    from textifai.web_viewer.project_reader import _project_path
    project = project_reader.get_project(project_id)
    if not project:
        return {"error": "project_not_found"}
    root = _project_path(project, "root")
    if not root:
        return {"error": "project_root_not_found"}
    return build_entity_card(
        project_root=root,
        node_id=node_id or None,
        note_path=note_path or None,
        canonical_label=canonical_label or None,
    )
