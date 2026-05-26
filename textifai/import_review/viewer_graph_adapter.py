from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


VIEWER_NODE_KINDS = {"character", "place", "concept", "object", "event", "unresolved", "chapter"}


def adapt_ingestion_graph_to_viewer_graph(ingestion_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a normalized ingestion graph into the current web viewer graph shape."""

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    chapter_ids = _chapter_ids(ingestion_graph)

    for node in _iter_nodes(ingestion_graph):
        adapted = _adapt_node(node)
        if not adapted["source_refs"]:
            warnings.append(f"node_without_source_refs:{adapted['id']}")
        nodes.append(adapted)

    known_ids = {node["id"] for node in nodes}
    for edge in _iter_edges(ingestion_graph):
        adapted = _adapt_edge(edge)
        if adapted["source"] not in known_ids or adapted["target"] not in known_ids:
            warnings.append(f"edge_with_missing_endpoint:{adapted['id']}")
        if not adapted["source_refs"]:
            warnings.append(f"edge_without_source_refs:{adapted['id']}")
        edges.append(adapted)

    for mention in _as_list(ingestion_graph.get("unresolved_mentions")):
        if not isinstance(mention, Mapping):
            continue
        node_id = str(mention.get("id") or f"unresolved:{_safe_id(mention.get('label') or mention.get('text') or 'mention')}")
        if node_id in known_ids:
            continue
        nodes.append(
            {
                "id": node_id,
                "label": str(mention.get("label") or mention.get("text") or "Unresolved"),
                "kind": "unresolved",
                "role": "review",
                "tags": ["#review", "#unresolved"],
                "chapter_ids": _string_list(mention.get("chapter_ids")),
                "source_refs": _as_list(mention.get("source_refs")),
                "status": str(mention.get("status") or "needs_review"),
                "note_path": None,
            }
        )
        known_ids.add(node_id)

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "source": str(ingestion_graph.get("source") or ingestion_graph.get("metadata", {}).get("source") or "ingestion_output"),
            "chapters": chapter_ids,
            "warnings": sorted(set(warnings)),
        },
    }


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


def _adapt_node(node: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(node.get("kind") or node.get("entity_kind") or "concept").casefold()
    if kind not in VIEWER_NODE_KINDS:
        kind = "concept"
    status = str(node.get("status") or node.get("review_state") or "ready")
    role = str(node.get("role") or ("review" if status in {"needs_review", "needs_retry", "failed"} else "primary"))
    node_id = str(node.get("id") or f"{kind}:{_safe_id(node.get('label') or node.get('canonical_name') or kind)}")
    label = str(node.get("label") or node.get("canonical_name") or node_id)
    tags = _normalize_tags([*_string_list(node.get("tags")), kind, role, status])
    return {
        "id": node_id,
        "label": label,
        "kind": kind,
        "role": role,
        "tags": tags,
        "chapter_ids": _string_list(node.get("chapter_ids") or node.get("chapters")),
        "source_refs": _as_list(node.get("source_refs")),
        "status": status,
        "note_path": node.get("note_path"),
        "entity": {
            "canonical_name": label,
            "entity_kind": kind,
            "review_state": status,
            "source_refs": _as_list(node.get("source_refs")),
        },
    }


def _adapt_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    source = str(edge.get("source") or edge.get("from") or "")
    target = str(edge.get("target") or edge.get("to") or "")
    label = str(edge.get("label") or edge.get("type") or edge.get("relation_type") or "related_to")
    kind = str(edge.get("kind") or "relation")
    edge_id = str(edge.get("id") or f"edge:{_safe_id(source)}:{_safe_id(label)}:{_safe_id(target)}")
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "label": label,
        "type": label,
        "kind": kind,
        "chapter_ids": _string_list(edge.get("chapter_ids") or edge.get("chapters")),
        "source_refs": _as_list(edge.get("source_refs")),
    }


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
    return [str(item) for item in _as_list(value) if item is not None and str(item)]


def _normalize_tags(tags: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        value = str(tag or "").strip().replace(" ", "_").casefold()
        if not value:
            continue
        normalized.append(value if value.startswith("#") else f"#{value}")
    return sorted(set(normalized))


def _safe_id(value: Any) -> str:
    text = str(value or "item").strip().casefold()
    safe = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return safe or "item"
