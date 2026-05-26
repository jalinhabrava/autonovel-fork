from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

VIEWER_NODE_KINDS = {"character", "place", "concept", "object", "event", "unresolved", "chapter"}
SYNTHETIC_LABEL_PATTERN = ("character ", "place ", "concept ", "object ", "event ")


def adapt_ingestion_graph_to_viewer_graph(ingestion_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a normalized ingestion graph into the current web viewer graph shape.

    Runtime policy:
    - Prefer real canonical/surface labels.
    - Preserve aliases, facts, source refs and evidence pointers.
    - Emit explicit warnings when a real label is missing.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    chapter_ids = _chapter_ids(ingestion_graph)

    for node in _iter_nodes(ingestion_graph):
        adapted = _adapt_node(node, warnings=warnings)
        if not adapted["source_refs"]:
            warnings.append(f"node_without_source_refs:{adapted['id']}")
        nodes.append(adapted)

    known_ids = {node["id"] for node in nodes}
    for edge in _iter_edges(ingestion_graph):
        adapted = _adapt_edge(edge, warnings=warnings)
        if adapted["source"] not in known_ids or adapted["target"] not in known_ids:
            warnings.append(f"edge_with_missing_endpoint:{adapted['id']}")
        if not adapted["source_refs"]:
            warnings.append(f"edge_without_source_refs:{adapted['id']}")
        edges.append(adapted)

    for mention in _as_list(ingestion_graph.get("unresolved_mentions")):
        if not isinstance(mention, Mapping):
            continue
        node_id = str(mention.get("id") or f"unresolved:{_safe_id(_pick_label(mention))}")
        if node_id in known_ids:
            continue
        label = _pick_label(mention)
        if not label:
            label = "label_missing_runtime_warning"
            warnings.append(f"label_missing_runtime_warning:{node_id}")
        nodes.append(
            {
                "id": node_id,
                "canonical_label": label,
                "label": label,
                "kind": "unresolved",
                "role": "review",
                "tags": ["#review", "#unresolved"],
                "chapter_ids": _string_list(mention.get("chapter_ids")),
                "source_refs": _normalize_source_refs(mention.get("source_refs")),
                "evidence_refs": _normalize_evidence_refs(mention.get("evidence_refs") or mention.get("evidence")),
                "status": str(mention.get("status") or "needs_review"),
                "note_path": mention.get("note_path"),
                "entity": {
                    "canonical_name": label,
                    "surface_forms": _merge_unique(_string_list(mention.get("surface_forms")), _string_list(mention.get("source_mentions"))),
                    "aliases": _string_list(mention.get("aliases")),
                    "summary": str(mention.get("summary") or ""),
                    "facts": _string_list(mention.get("facts") or mention.get("key_facts")),
                    "source_refs": _normalize_source_refs(mention.get("source_refs")),
                    "evidence_refs": _normalize_evidence_refs(mention.get("evidence_refs") or mention.get("evidence")),
                    "review_state": str(mention.get("status") or "needs_review"),
                    "relationships_out": [],
                    "relationships_in": [],
                    "backlinks": _string_list(mention.get("backlinks")),
                },
            }
        )
        known_ids.add(node_id)

    _link_relationship_views(nodes=nodes, edges=edges)
    metadata = _build_metadata(ingestion_graph=ingestion_graph, nodes=nodes, edges=edges, warnings=warnings, chapters=chapter_ids)
    return {"nodes": nodes, "edges": edges, "metadata": metadata}


def build_runtime_ingestion_graph(
    *,
    chapter_payloads: Sequence[Mapping[str, Any]],
    chapter_status_map: Mapping[str, str] | None = None,
    source: str = "runtime_projection",
) -> dict[str, Any]:
    """Build a real-label ingestion graph from chapter payloads (provider-free)."""

    chapter_status_map = dict(chapter_status_map or {})
    node_map: dict[tuple[str, str], dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def ensure_node(kind: str, label: str, *, chapter_id: str, raw: Mapping[str, Any] | None = None) -> str:
        norm = _safe_id(label)
        key = (kind, norm)
        status = chapter_status_map.get(chapter_id, "ready")
        if key not in node_map:
            raw = raw or {}
            node_map[key] = {
                "id": f"{kind}:{norm}",
                "canonical_label": label,
                "label": label,
                "kind": kind,
                "status": status,
                "chapter_ids": [chapter_id],
                "source_refs": _normalize_source_refs(raw.get("source_refs")),
                "evidence_refs": _normalize_evidence_refs(raw.get("evidence_refs") or raw.get("evidence")),
                "surface_forms": _merge_unique(_string_list(raw.get("surface_forms")), _string_list(raw.get("source_mentions"))),
                "aliases": _string_list(raw.get("aliases") or raw.get("accepted_aliases")),
                "facts": _string_list(raw.get("facts") or raw.get("key_facts")),
                "summary": str(raw.get("summary") or raw.get("description") or ""),
                "tags": _normalize_tags(_string_list(raw.get("tags")) + [kind, status]),
            }
        else:
            entry = node_map[key]
            entry["chapter_ids"] = _merge_unique(_string_list(entry.get("chapter_ids")), [chapter_id])
            entry["source_refs"] = _merge_source_refs(entry.get("source_refs"), _normalize_source_refs((raw or {}).get("source_refs")))
            entry["evidence_refs"] = _merge_evidence_refs(entry.get("evidence_refs"), _normalize_evidence_refs((raw or {}).get("evidence_refs") or (raw or {}).get("evidence")))
            entry["surface_forms"] = _merge_unique(entry.get("surface_forms"), _merge_unique(_string_list((raw or {}).get("surface_forms")), _string_list((raw or {}).get("source_mentions"))))
            entry["aliases"] = _merge_unique(entry.get("aliases"), _string_list((raw or {}).get("aliases") or (raw or {}).get("accepted_aliases")))
            entry["facts"] = _merge_unique(entry.get("facts"), _string_list((raw or {}).get("facts") or (raw or {}).get("key_facts")))
        return node_map[key]["id"]

    for chapter in chapter_payloads:
        chapter_id = str(chapter.get("chapter_id") or chapter.get("id") or "")
        if not chapter_id:
            continue

        kind_to_section = {
            "character": chapter.get("characters") or [],
            "place": chapter.get("places") or [],
            "concept": chapter.get("concepts") or [],
            "object": chapter.get("objects") or [],
            "event": chapter.get("events") or [],
        }
        chapter_node_ids: dict[str, str] = {}
        for kind, section in kind_to_section.items():
            for raw_item in section:
                if not isinstance(raw_item, Mapping):
                    continue
                label = _pick_label(raw_item)
                if not label:
                    continue
                node_id = ensure_node(kind, label, chapter_id=chapter_id, raw=raw_item)
                chapter_node_ids[f"{kind}:{_safe_id(label)}"] = node_id

        for relation in _as_list(chapter.get("relations") or chapter.get("relationships")):
            if not isinstance(relation, Mapping):
                continue
            source_label = _pick_relation_endpoint(relation, "source")
            target_label = _pick_relation_endpoint(relation, "target")
            if not source_label or not target_label:
                continue
            source_kind = str(relation.get("source_kind") or relation.get("from_kind") or "character").casefold()
            target_kind = str(relation.get("target_kind") or relation.get("to_kind") or "character").casefold()
            source_id = ensure_node(source_kind if source_kind in VIEWER_NODE_KINDS else "character", source_label, chapter_id=chapter_id)
            target_id = ensure_node(target_kind if target_kind in VIEWER_NODE_KINDS else "character", target_label, chapter_id=chapter_id)
            relation_label = _pick_relation_label(relation)
            edge_id = f"edge:{_safe_id(source_id)}:{_safe_id(relation_label)}:{_safe_id(target_id)}:{chapter_id}"
            edges.append(
                {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "label": relation_label,
                    "kind": str(relation.get("relation_category") or relation.get("kind") or "relation"),
                    "summary": str(relation.get("relation_summary") or relation.get("summary") or ""),
                    "facts": _string_list(relation.get("facts") or relation.get("relation_facts")),
                    "chapter_ids": [chapter_id],
                    "source_refs": _normalize_source_refs(relation.get("source_refs")),
                    "evidence_refs": _normalize_evidence_refs(relation.get("evidence_refs") or relation.get("evidence")),
                    "confidence": relation.get("confidence"),
                    "status": relation.get("status") or relation.get("review_status"),
                }
            )

    graph = {
        "source": source,
        "nodes": list(node_map.values()),
        "edges": edges,
        "chapters": [
            {
                "chapter_id": chapter_id,
                "status": chapter_status_map.get(chapter_id, "ready"),
            }
            for chapter_id in sorted(set(chapter_status_map) | {str(item.get("chapter_id") or item.get("id") or "") for item in chapter_payloads if isinstance(item, Mapping)})
            if chapter_id
        ],
    }
    return adapt_ingestion_graph_to_viewer_graph(graph)


def _iter_nodes(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(graph.get("nodes"), list):
        return [item for item in graph["nodes"] if isinstance(item, Mapping)]
    items: list[Mapping[str, Any]] = []
    for key in ("characters", "places", "concepts", "objects", "events"):
        items.extend(item for item in _as_list(graph.get(key)) if isinstance(item, Mapping))
    return items


def _iter_edges(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(graph.get("edges"), list):
        return [item for item in graph["edges"] if isinstance(item, Mapping)]
    items: list[Mapping[str, Any]] = []
    for key in ("relations", "relationships", "event_links", "object_links"):
        items.extend(item for item in _as_list(graph.get(key)) if isinstance(item, Mapping))
    return items


def _adapt_node(node: Mapping[str, Any], *, warnings: list[str]) -> dict[str, Any]:
    kind = str(node.get("kind") or node.get("entity_kind") or "concept").casefold()
    if kind not in VIEWER_NODE_KINDS:
        kind = "concept"
    status = str(node.get("status") or node.get("review_state") or "ready")
    role = str(node.get("role") or ("review" if status in {"needs_review", "needs_retry", "failed"} else "primary"))

    canonical_label = _pick_label(node)
    node_id = str(node.get("id") or f"{kind}:{_safe_id(canonical_label or kind)}")
    if not canonical_label:
        canonical_label = "label_missing_runtime_warning"
        warnings.append(f"label_missing_runtime_warning:{node_id}")

    surface_forms = _merge_unique(_string_list(node.get("surface_forms")), _string_list(node.get("source_mentions")))
    aliases = _merge_unique(_string_list(node.get("aliases")), _string_list(node.get("accepted_aliases")))
    facts = _merge_unique(_string_list(node.get("facts")), _string_list(node.get("key_facts")))
    summary = str(node.get("summary") or node.get("description") or "")
    source_refs = _normalize_source_refs(node.get("source_refs"))
    evidence_refs = _normalize_evidence_refs(node.get("evidence_refs") or node.get("evidence"))
    chapter_ids = _string_list(node.get("chapter_ids") or node.get("chapters"))

    tags = _normalize_tags([*_string_list(node.get("tags")), kind, role, status])
    relationships = [item for item in _as_list(node.get("relationships")) if isinstance(item, Mapping)]

    return {
        "id": node_id,
        "canonical_label": canonical_label,
        "label": canonical_label,
        "kind": kind,
        "role": role,
        "tags": tags,
        "chapter_ids": chapter_ids,
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "status": status,
        "note_path": node.get("note_path"),
        "surface_forms": surface_forms,
        "aliases": aliases,
        "facts": facts,
        "summary": summary,
        "entity": {
            "canonical_name": canonical_label,
            "entity_kind": kind,
            "surface_forms": surface_forms,
            "aliases": aliases,
            "summary": summary,
            "facts": facts,
            "key_facts": facts,
            "source_mentions": surface_forms,
            "source_refs": source_refs,
            "evidence_refs": evidence_refs,
            "review_state": str(node.get("review_state") or status),
            "note_role": str(node.get("note_role") or role),
            "relationships": relationships,
            "relationships_out": [],
            "relationships_in": [],
            "backlinks": _string_list(node.get("backlinks")),
        },
    }


def _adapt_edge(edge: Mapping[str, Any], *, warnings: list[str]) -> dict[str, Any]:
    source = str(edge.get("source") or edge.get("from") or "")
    target = str(edge.get("target") or edge.get("to") or "")
    label = _pick_relation_label(edge)
    kind = str(edge.get("kind") or edge.get("relation_category") or edge.get("type") or "relation")
    if not label:
        label = "label_missing_runtime_warning"
        warnings.append(f"relation_label_missing_runtime_warning:{source}:{target}")
    edge_id = str(edge.get("id") or f"edge:{_safe_id(source)}:{_safe_id(label)}:{_safe_id(target)}")
    chapter_ids = _string_list(edge.get("chapter_ids") or edge.get("chapters"))
    source_refs = _normalize_source_refs(edge.get("source_refs"))
    evidence_refs = _normalize_evidence_refs(edge.get("evidence_refs") or edge.get("evidence"))
    facts = _string_list(edge.get("facts") or edge.get("relation_facts"))
    summary = str(edge.get("summary") or edge.get("relation_summary") or "")

    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "label": label,
        "type": label,
        "kind": kind,
        "summary": summary,
        "facts": facts,
        "chapter_ids": chapter_ids,
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "confidence": edge.get("confidence"),
        "status": edge.get("status") or edge.get("review_status"),
    }


def _build_metadata(*, ingestion_graph: Mapping[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], warnings: list[str], chapters: list[str]) -> dict[str, Any]:
    source = str(ingestion_graph.get("source") or ingestion_graph.get("metadata", {}).get("source") or "ingestion_output")
    metadata_in = ingestion_graph.get("metadata") if isinstance(ingestion_graph.get("metadata"), Mapping) else {}
    kind_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        kind_counts[str(node.get("kind") or "unknown")] += 1

    synthetic_label_count = sum(1 for node in nodes if _is_synthetic_label(str(node.get("label") or "")))
    writer_outcome = metadata_in.get("writer_outcome") if isinstance(metadata_in.get("writer_outcome"), Mapping) else {}

    return {
        "source": source,
        "chapters": chapters,
        "warnings": sorted(set(warnings)),
        "writer_outcome": writer_outcome,
        "graph_summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_counts_by_kind": dict(sorted(kind_counts.items())),
            "synthetic_label_count": synthetic_label_count,
        },
    }


def _link_relationship_views(*, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    node_map = {str(node.get("id")): node for node in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        row = {
            "edge_id": edge.get("id"),
            "label": edge.get("label"),
            "kind": edge.get("kind"),
            "target": target,
            "source": source,
            "summary": edge.get("summary"),
            "chapter_ids": edge.get("chapter_ids") or [],
        }
        outgoing[source].append(row)
        incoming[target].append(row)

    for node_id, node in node_map.items():
        entity = node.get("entity") if isinstance(node.get("entity"), dict) else {}
        entity["relationships_out"] = outgoing.get(node_id, [])
        entity["relationships_in"] = incoming.get(node_id, [])
        node["entity"] = entity


def _pick_label(value: Mapping[str, Any]) -> str:
    for key in (
        "canonical_label",
        "canonical_name",
        "canonical",
        "label",
        "surface",
        "surface_form",
        "name",
        "title",
        "target",
        "text",
    ):
        raw = str(value.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _pick_relation_label(value: Mapping[str, Any]) -> str:
    for key in (
        "relation_label",
        "label",
        "relation_type",
        "type",
        "relation_category",
    ):
        raw = str(value.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _pick_relation_endpoint(value: Mapping[str, Any], side: str) -> str:
    keys = {
        "source": (
            "source",
            "source_entity",
            "subject",
            "from",
            "from_entity",
            "from_canonical",
            "from_surface",
            "character",
            "entity",
        ),
        "target": (
            "target",
            "target_entity",
            "object",
            "to",
            "to_entity",
            "to_canonical",
            "to_surface",
        ),
    }
    for key in keys[side]:
        raw = str(value.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _chapter_ids(graph: Mapping[str, Any]) -> list[str]:
    chapters = graph.get("chapters") or graph.get("metadata", {}).get("chapters")
    ids: list[str] = []
    for chapter in _as_list(chapters):
        if isinstance(chapter, Mapping):
            value = chapter.get("chapter_id") or chapter.get("id")
        else:
            value = chapter
        if value:
            ids.append(str(value))
    return ids


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if item is not None and str(item).strip()]


def _normalize_tags(tags: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        value = str(tag or "").strip().replace(" ", "_").casefold()
        if not value:
            continue
        normalized.append(value if value.startswith("#") else f"#{value}")
    return sorted(set(normalized))


def _normalize_source_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in _as_list(value):
        if not isinstance(item, Mapping):
            continue
        ref = {
            "source_id": item.get("source_id"),
            "chapter_id": item.get("chapter_id") or item.get("chapter"),
            "chunk_id": item.get("chunk_id"),
            "char_start": item.get("char_start"),
            "char_end": item.get("char_end"),
            "span_id": item.get("span_id"),
            "source_span": item.get("source_span"),
        }
        key = tuple(ref.values())
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _normalize_evidence_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in _as_list(value):
        if isinstance(item, Mapping):
            ref = {
                "evidence_id": item.get("evidence_id") or item.get("id"),
                "chapter_id": item.get("chapter_id") or item.get("chapter"),
                "pointer": item.get("pointer") or item.get("span_id") or item.get("source_span"),
            }
        else:
            text = str(item).strip()
            if not text:
                continue
            ref = {"evidence_id": None, "chapter_id": None, "pointer": text}
        key = tuple(ref.values())
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _merge_unique(first: Sequence[Any] | None, second: Sequence[Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in [*(first or []), *(second or [])]:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _merge_source_refs(first: Any, second: Any) -> list[dict[str, Any]]:
    return _normalize_source_refs([*_as_list(first), *_as_list(second)])


def _merge_evidence_refs(first: Any, second: Any) -> list[dict[str, Any]]:
    return _normalize_evidence_refs([*_as_list(first), *_as_list(second)])


def _safe_id(value: Any) -> str:
    text = str(value or "item").strip().casefold()
    safe = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return safe or "item"


def _is_synthetic_label(label: str) -> bool:
    candidate = label.strip().casefold()
    if not candidate:
        return False
    if not any(candidate.startswith(prefix) for prefix in SYNTHETIC_LABEL_PATTERN):
        return False
    suffix = candidate.split(" ")[-1]
    return suffix.isdigit()
