from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textifai.obsidian.parser import extract_obsidian_links, parse_obsidian_frontmatter
from vault.schema import slugify
from textifai.import_review.markdown_graph_index import build_author_graph, build_markdown_graph_index, local_graph
from textifai.web_viewer.entity_card import build_entity_card
from textifai.import_review.viewer_graph_adapter import adapt_ingestion_graph_to_viewer_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PROJECT_REGISTRY = REPO_ROOT / '.textifai_runs' / 'registry.local.json'

CANONICAL_KIND_PRIORITY = {
    "character": 700,
    "place": 600,
    "object": 500,
    "event": 400,
    "concept": 300,
    "review": 200,
    "chapter": 100,
    "unresolved": 0,
}

KIND_VISUALS = {
    "character": {"color": "#247c7a", "label": "Character"},
    "place": {"color": "#4f8f4f", "label": "Place"},
    "event": {"color": "#d5793a", "label": "Event"},
    "object": {"color": "#a9782b", "label": "Object"},
    "concept": {"color": "#6c6f93", "label": "Concept"},
    "chapter": {"color": "#7f7a6a", "label": "Chapter"},
    "review": {"color": "#b45b35", "label": "Review"},
    "unresolved": {"color": "#a23b55", "label": "Needs attention"},
}

STATUS_VISUALS = {
    "ready": {"border": "#247c7a", "label": "Ready"},
    "needs_review": {"border": "#d59a2f", "label": "Needs review"},
    "needs_retry": {"border": "#a23b55", "label": "Needs retry"},
    "failed": {"border": "#7b1f2a", "label": "Failed"},
}


VISIBLE_ARTIFACTS = [
    "novel_index.json",
    "global_normalization.json",
    "canonical_entity_map.json",
    "resolved_entities.json",
    "cleaned_entities.json",
    "obsidian_import.json",
    "chapter_extraction_audit.json",
    "semantic_invariants_audit.json",
    "review_queue.json",
    "run_comparability_manifest.json",
    "semantic_replay_audit.json",
    "pre_vaerl_reconciliation_audit.json",
    "primary_note_synthesis_audit.json",
    "obsidian_relationship_reconciliation_audit.json",
    "ingestion_graph.json",
    "markdown_manifest.json",
    "markdown_graph_index.json",
]

HEALTH_EXPECTED_ARTIFACTS = [
    "obsidian_import.json",
    "review_queue.json",
    "semantic_invariants_audit.json",
    "canonical_entity_map.json",
    "resolved_entities.json",
    "cleaned_entities.json",
    "run_comparability_manifest.json",
    "chapter_outputs",
]


@dataclass(frozen=True)
class ProjectRef:
    project_id: str
    name: str
    root: Path
    system_root: Path | None
    kind: str
    manifest_path: Path | None = None
    manifest: dict[str, Any] | None = None


class ProjectCatalog:
    def __init__(self, roots: list[Path]):
        self.roots = [root.resolve() for root in roots]
        self._projects = self._discover()

    def list_projects(self) -> list[dict[str, Any]]:
        self._projects = self._discover()
        return [self._project_summary(project) for project in self._projects]

    def get_project(self, project_id: str) -> ProjectRef:
        self._projects = self._discover()
        for project in self._projects:
            if project.project_id == project_id:
                return project
        raise KeyError(project_id)

    def _discover(self) -> list[ProjectRef]:
        projects: dict[str, ProjectRef] = {}
        for root in self.roots:
            if not root.exists():
                continue
            candidates = [root, *[path for path in root.iterdir() if path.is_dir()]]
            for candidate in candidates:
                project = _project_from_candidate(candidate)
                if project is None:
                    continue
                projects.setdefault(project.project_id, project)
        for project in _discover_registry_projects():
            projects[project.project_id] = project
        return sorted(projects.values(), key=lambda item: item.name.casefold())

    def _project_summary(self, project: ProjectRef) -> dict[str, Any]:
        system = project.system_root
        obsidian_import = _read_project_json(project, 'vaerl') or (_read_json(system / "obsidian_import.json") if system else None)
        review_queue = _read_project_json(project, 'review_queue') or (_read_json(system / "review_queue.json") if system else None)
        invariants = _read_json(system / "semantic_invariants_audit.json") if system else None
        ingestion_graph = _read_json(system / "ingestion_graph.json") if system else None
        markdown_manifest = read_markdown_manifest(project)
        markdown_index = read_markdown_graph_index(project)
        entities = obsidian_import.get("entities") if isinstance(obsidian_import, dict) else []
        chapters = obsidian_import.get("chapters") if isinstance(obsidian_import, dict) else []
        primary_count = sum(1 for item in entities or [] if _is_primary(item))
        graph_summary = {}
        writer_outcome = _read_writer_outcome(project)
        if isinstance(ingestion_graph, dict):
            adapted = adapt_ingestion_graph_to_viewer_graph(ingestion_graph)
            metadata = adapted.get("metadata") if isinstance(adapted, dict) else {}
            if isinstance(metadata, dict):
                graph_summary = metadata.get("graph_summary") if isinstance(metadata.get("graph_summary"), dict) else {}
                if not writer_outcome:
                    writer_outcome = metadata.get("writer_outcome") if isinstance(metadata.get("writer_outcome"), dict) else {}
        if not graph_summary and isinstance(markdown_index, dict):
            graph_summary = {
                "node_count": len(markdown_index.get("nodes") or []),
                "edge_count": len(markdown_index.get("edges") or []),
                "node_counts_by_kind": _count_nodes_by_kind([node for node in markdown_index.get("nodes") or [] if isinstance(node, dict)]),
                "synthetic_label_count": 0,
            }
        markdown_chapter_count = sum(1 for note in (markdown_manifest or {}).get("notes", []) if isinstance(note, dict) and str(note.get("kind") or "") == "chapter")
        chapter_count = int(writer_outcome.get("total_chapters") or len(chapters or []) or len((ingestion_graph or {}).get("metadata", {}).get("chapters") or []) or markdown_chapter_count)
        synthetic_label_count = graph_summary.get("synthetic_label_count")
        recommended = bool(graph_summary) and synthetic_label_count == 0 and str(project.name).endswith("sp089")
        if project.kind == 'textifai_project' and chapter_count >= 20:
            recommended = True
        return {
            "project_id": project.project_id,
            "name": project.name,
            "kind": project.kind,
            "root": str(project.root),
            "system_root": str(system) if system else None,
            "mtime": project.root.stat().st_mtime if project.root.exists() else None,
            "work": _project_work(project, obsidian_import),
            "chapter_count": chapter_count,
            "entity_count": len(entities or []),
            "primary_count": primary_count,
            "review_count": max(len(entities or []) - primary_count, 0),
            "review_queue_count": review_queue.get("item_count") if isinstance(review_queue, dict) else None,
            "invariants_status": invariants.get("status") if isinstance(invariants, dict) else None,
            "has_ingestion_graph": isinstance(ingestion_graph, dict),
            "has_markdown_manifest": isinstance(markdown_manifest, dict),
            "has_markdown_graph_index": isinstance(markdown_index, dict),
            "markdown_note_count": markdown_manifest.get("note_count") if isinstance(markdown_manifest, dict) else None,
            "markdown_unresolved_link_count": len(markdown_index.get("unresolved_links") or []) if isinstance(markdown_index, dict) else None,
            "graph_summary": graph_summary,
            "writer_outcome": writer_outcome,
            "ingestion_policy": project.manifest.get("ingestion_policy") if isinstance(project.manifest, dict) else {},
            "workspace_status": _build_workspace_status_summary(writer_outcome, project.manifest if isinstance(project.manifest, dict) else {}),
            "recommended": recommended,
        }


def read_project(project: ProjectRef) -> dict[str, Any]:
    canon = read_canon(project)
    artifacts = list_artifacts(project)
    graph = build_graph(project, canon=canon)
    markdown_manifest = read_markdown_manifest(project) or {}
    markdown_graph_index = read_markdown_graph_index(project) or {}
    graph_metadata = graph.get("metadata") if isinstance(graph, dict) else {}
    writer_outcome = _read_writer_outcome(project)
    if not writer_outcome:
        writer_outcome = graph_metadata.get("writer_outcome") if isinstance(graph_metadata, dict) and isinstance(graph_metadata.get("writer_outcome"), dict) else {}
    graph_summary = graph_metadata.get("graph_summary") if isinstance(graph_metadata, dict) and isinstance(graph_metadata.get("graph_summary"), dict) else {}
    overview = {
        "chapters_processed": writer_outcome.get("total_chapters") or len(graph_metadata.get("chapters") or canon.get("chapters") or []) or sum(1 for note in markdown_manifest.get("notes", []) if isinstance(note, dict) and str(note.get("kind") or "") == "chapter"),
        "chapters_ready": writer_outcome.get("chapters_ready"),
        "chapters_ready_with_warnings": writer_outcome.get("chapters_ready_with_warnings"),
        "chapters_needing_retry": writer_outcome.get("chapters_needing_retry"),
        "chapters_needing_review": writer_outcome.get("chapters_needing_review"),
        "chapters_failed": writer_outcome.get("chapters_failed"),
        "primary_action": writer_outcome.get("primary_action"),
        "secondary_action": writer_outcome.get("secondary_action"),
        "user_summary": writer_outcome.get("user_summary"),
        "node_counts_by_kind": graph_summary.get("node_counts_by_kind") if isinstance(graph_summary, dict) else {},
        "relationship_count": graph_summary.get("edge_count") if isinstance(graph_summary, dict) else None,
        "warning_summary": (graph_metadata.get("warnings") or [])[:12] if isinstance(graph_metadata, dict) else [],
        "synthetic_label_count": graph_summary.get("synthetic_label_count") if isinstance(graph_summary, dict) else None,
        "markdown_note_count": markdown_manifest.get("note_count") or markdown_graph_index.get("note_count"),
        "markdown_graph_edge_count": markdown_graph_index.get("edge_count"),
        "markdown_tag_count": len(markdown_graph_index.get("tags") or []),
        "orphan_note_count": len(markdown_graph_index.get("orphan_notes") or []),
        "unresolved_link_count": len(markdown_graph_index.get("unresolved_links") or []),
        "next_action_cta": "Open Wiki to review notes, backlinks, tags, and local graph context.",
    }
    return {
        "project": {
            "project_id": project.project_id,
            "name": project.name,
            "kind": project.kind,
            "root": str(project.root),
            "system_root": str(project.system_root) if project.system_root else None,
            "work": canon.get("work") if isinstance(canon.get("work"), dict) else {},
        },
        "notes": list_notes(project.root, markdown_manifest=markdown_manifest, markdown_index=markdown_graph_index),
        "markdown_manifest": markdown_manifest,
        "markdown_graph_index": markdown_graph_index,
        "canon": canon,
        "artifacts": artifacts,
        "graph": graph,
        "overview": overview,
        "writer_outcome": writer_outcome if isinstance(writer_outcome, dict) else {},
        "ingestion_policy": project.manifest.get("ingestion_policy") if isinstance(project.manifest, dict) else {},
        "workspace_status": _build_workspace_status_summary(writer_outcome if isinstance(writer_outcome, dict) else {}, project.manifest if isinstance(project.manifest, dict) else {}),
        "health": build_semantic_health(project, canon=canon, artifacts=artifacts, graph=graph),
        "canonicalization": build_canonicalization_payload(project, canon=canon, artifacts=artifacts),
        "run_status": _read_json(project.root / 'reports' / 'run_status.json') or {},
    }

def _build_workspace_status_summary(writer_outcome: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    status = manifest.get("status") if isinstance(manifest.get("status"), dict) else {}
    total = int(writer_outcome.get("total_chapters") or status.get("chapters_total") or 0)
    ready = int(writer_outcome.get("chapters_ready") or status.get("chapters_ready") or 0)
    retry_required = int(writer_outcome.get("chapters_needing_retry") or status.get("chapters_retry_required") or status.get("retry_required") or 0)
    retried = int(writer_outcome.get("chapters_retried") or status.get("chapters_retried") or 0)
    still_failed = int(writer_outcome.get("chapters_still_failed") or status.get("chapters_still_failed") or retry_required)
    semantic_reviews = int(writer_outcome.get("chapters_needing_review") or status.get("semantic_reviews") or 0)
    if status.get("chapters_still_failed") is not None:
        still_failed = int(status.get("chapters_still_failed") or 0)
    if status.get("chapters_retried") is not None:
        retried = int(status.get("chapters_retried") or 0)
    return {
        "chapters_detected_label": f"{total} capítulos detectados",
        "chapters_ready_label": f"{ready} listos",
        "chapters_retried_label": f"{retried} reintentados",
        "chapters_still_failed_label": f"{still_failed} siguen necesitando reintento",
        "semantic_review_label": f"{semantic_reviews} decisiones editoriales pendientes",
        "retry_cta": "Reintentar capítulos fallidos" if still_failed else "Abrir workspace",
        "review_cta": "Ver decisiones" if semantic_reviews else "Sin decisiones pendientes",
        "product_language": "author_facing_no_provider_jargon",
    }


def list_notes(
    root: Path,
    *,
    markdown_manifest: dict[str, Any] | None = None,
    markdown_index: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    manifest_by_path = {
        str(note.get("path") or ""): note
        for note in (markdown_manifest or {}).get("notes", [])
        if isinstance(note, dict)
    }
    index_by_path = {
        str(note.get("path") or ""): note
        for note in (markdown_index or {}).get("notes", [])
        if isinstance(note, dict)
    }
    manifest_paths = [root / rel for rel in manifest_by_path.keys() if rel]
    if manifest_paths:
        candidate_paths = [path for path in manifest_paths if path.exists() and path.suffix == '.md']
    else:
        candidate_paths = sorted(root.rglob("*.md"))
    for path in sorted(candidate_paths):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_obsidian_frontmatter(text)
        tags = _tags_from_frontmatter(frontmatter)
        manifest_note = manifest_by_path.get(rel, {})
        index_note = index_by_path.get(rel, {})
        merged_tags = sorted(set([*tags, *(manifest_note.get("tags") or []), *(index_note.get("tags") or [])]))
        notes.append(
            {
                "path": rel,
                "name": manifest_note.get("title") or frontmatter.get("canonical_label") or path.stem,
                "folder": path.parent.relative_to(root).as_posix() if path.parent != root else "",
                "frontmatter": frontmatter,
                "tags": merged_tags,
                "role": _note_role(path, frontmatter),
                "mtime": path.stat().st_mtime,
                "kind": frontmatter.get("kind") or manifest_note.get("kind") or "note",
                "status": frontmatter.get("status") or manifest_note.get("status"),
                "review_state": frontmatter.get("review_state") or manifest_note.get("review_state"),
                "aliases": frontmatter.get("aliases") or manifest_note.get("aliases") or [],
                "backlinks": index_note.get("backlinks") or [],
                "outgoing_wikilinks": index_note.get("outgoing_wikilinks") or [],
                "degree": index_note.get("degree") or 0,
            }
        )
    return notes



def read_entity_card(
    project: ProjectRef,
    node_id: str | None = None,
    note_path: str | None = None,
    canonical_label: str | None = None,
) -> dict[str, Any]:
    """Build EntityCardViewModel combining author_graph, VaERL, Markdown, backlinks, review."""
    root = project.root
    if not root or not root.exists():
        return {"error": "project_root_not_found"}
    return build_entity_card(
        project_root=root,
        node_id=node_id,
        note_path=note_path,
        canonical_label=canonical_label,
    )
def read_note(project: ProjectRef, note_path: str) -> dict[str, Any]:
    path = _safe_child(project.root, note_path)
    if path.suffix != ".md" or not path.exists():
        raise FileNotFoundError(note_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(project.root).as_posix()
    frontmatter = parse_obsidian_frontmatter(text)
    markdown_index = read_markdown_graph_index(project) or {}
    indexed_note = _markdown_index_note(markdown_index, rel)
    return {
        "path": rel,
        "markdown": text,
        "frontmatter": frontmatter,
        "content_hydration": _markdown_content_hydration(text),
        "links": extract_obsidian_links(text),
        "tags": indexed_note.get("tags") or _tags_from_frontmatter(frontmatter),
        "backlinks": indexed_note.get("backlinks") or [],
        "outgoing_wikilinks": indexed_note.get("outgoing_wikilinks") or [],
        "degree": indexed_note.get("degree") or 0,
        "local_graph": local_graph(markdown_index, rel, depth=1) if isinstance(markdown_index, dict) and markdown_index.get("nodes") else {},
    }



def _markdown_content_hydration(markdown_text: str) -> dict[str, Any]:
    sections: dict[str, Any] = {"summary": "", "facts": [], "relationships": [], "evidence": []}
    current = ""
    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            heading = _key(line[3:])
            if "summary" in heading:
                current = "summary"
            elif "fact" in heading:
                current = "facts"
            elif "relationship" in heading or "relacion" in heading:
                current = "relationships"
            elif "evidence" in heading or "evidencia" in heading:
                current = "evidence"
            else:
                current = ""
            continue
        if not current or not line or line.startswith("<!--") or line == "---":
            continue
        cleaned = re.sub(r"^[-*]\s+", "", line).strip()
        cleaned = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", cleaned)
        if not cleaned:
            continue
        if current == "summary":
            sections["summary"] = " ".join(part for part in [sections["summary"], cleaned] if part)
        else:
            sections[current].append(cleaned)
    summary = str(sections["summary"] or "").strip()
    facts = [str(item) for item in sections["facts"][:8]]
    return {
        "summary_excerpt": summary[:420],
        "key_facts_count": len(sections["facts"]),
        "key_facts_preview": facts,
        "relationship_count": len(sections["relationships"]),
        "evidence_count": len(sections["evidence"]),
    }

def read_canon(project: ProjectRef) -> dict[str, Any]:
    system = project.system_root
    obsidian_import = _read_project_json(project, 'vaerl') or (_read_json(system / "obsidian_import.json") if system else {})
    review_queue = _read_project_json(project, 'review_queue') or (_read_json(system / "review_queue.json") if system else {})
    entities = obsidian_import.get("entities") if isinstance(obsidian_import, dict) else []
    chapters = obsidian_import.get("chapters") if isinstance(obsidian_import, dict) else []
    hydrated_queue = _hydrate_review_queue(review_queue if isinstance(review_queue, dict) else {}, entities if isinstance(entities, list) else [], chapters if isinstance(chapters, list) else [], project.root)
    return {
        "work": _project_work(project, obsidian_import),
        "chapters": chapters or [],
        "primaries": [item for item in entities or [] if _is_primary(item)],
        "review_entities": [item for item in entities or [] if not _is_primary(item)],
        "review_queue": hydrated_queue,
    }


def list_artifacts(project: ProjectRef) -> list[dict[str, Any]]:
    if project.kind == 'textifai_project':
        artifacts: list[dict[str, Any]] = []
        for key in ['vaerl', 'entities', 'relationships', 'review_queue', 'graph', 'backlinks', 'markdown_graph_index', 'markdown_manifest']:
            path = _project_path(project, key)
            if path and path.exists():
                artifacts.append(_artifact_meta(project.root, path))
        return artifacts
    system = project.system_root
    if system is None or not system.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for name in VISIBLE_ARTIFACTS:
        path = system / name
        if path.exists():
            artifacts.append(_artifact_meta(system, path))
    for path in sorted(system.glob("*.json")):
        if path.name not in VISIBLE_ARTIFACTS:
            artifacts.append(_artifact_meta(system, path))
    if (system / "chapter_outputs").exists():
        artifacts.append(_artifact_meta(system, system / "chapter_outputs"))
    return artifacts


def read_artifact(project: ProjectRef, artifact_path: str) -> dict[str, Any]:
    if project.kind == 'textifai_project':
        path = _safe_child(project.root, artifact_path)
        if path.is_dir():
            return {
                "path": path.relative_to(project.root).as_posix(),
                "kind": "directory",
                "children": [_artifact_meta(project.root, child) for child in sorted(path.iterdir()) if child.is_file()],
            }
        if not path.exists():
            raise FileNotFoundError(artifact_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        return {"path": path.relative_to(project.root).as_posix(), "kind": "json" if payload is not None else "text", "json": payload, "text": text if payload is None else ""}
    if project.system_root is None:
        raise FileNotFoundError(artifact_path)
    path = _safe_child(project.system_root, artifact_path)
    if path.is_dir():
        return {
            "path": path.relative_to(project.system_root).as_posix(),
            "kind": "directory",
            "children": [_artifact_meta(project.system_root, child) for child in sorted(path.iterdir()) if child.is_file()],
        }
    if not path.exists():
        raise FileNotFoundError(artifact_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    payload: Any
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    return {
        "path": path.relative_to(project.system_root).as_posix(),
        "kind": "json" if payload is not None else "text",
        "json": payload,
        "text": text if payload is None else "",
    }


def build_graph(project: ProjectRef, canon: dict[str, Any] | None = None) -> dict[str, Any]:
    author_graph_path = project.root / 'graph' / 'author_graph.json'
    if author_graph_path.exists():
        payload = _read_json(author_graph_path)
        if isinstance(payload, dict) and isinstance(payload.get('nodes'), list):
            payload = _hydrate_author_graph_payload(project, payload)
            return {
                'nodes': payload.get('nodes') or [],
                'edges': payload.get('edges') or [],
                'metadata': {
                    'graph_mode': 'author_graph',
                    'author_graph_ready': True,
                    'excluded_counts': payload.get('excluded') or {},
                    'graph_summary': {
                        'node_count': len(payload.get('nodes') or []),
                        'edge_count': len(payload.get('edges') or []),
                        'node_counts_by_kind': _count_nodes_by_kind([row for row in payload.get('nodes') or [] if isinstance(row, dict)]),
                        'synthetic_label_count': 0,
                    },
                    'source_path': 'graph/author_graph.json',
                },
            }
    markdown_graph = _build_graph_from_markdown_index(project)
    if markdown_graph is not None:
        metadata = markdown_graph.setdefault('metadata', {})
        if isinstance(metadata, dict):
            metadata.setdefault('graph_mode', 'legacy_markdown_index')
            metadata.setdefault('author_graph_ready', False)
        return markdown_graph

    ingestion_graph = _build_graph_from_ingestion_artifact(project)
    if ingestion_graph is not None:
        return ingestion_graph

    canon = canon or read_canon(project)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    slug_to_id: dict[str, str] = {}
    for entity in [*canon["primaries"], *canon["review_entities"]]:
        slug = str(entity.get("preferred_slug") or entity.get("canonical_name") or "").strip()
        node_id = f"entity:{slug or entity.get('canonical_name')}"
        role = "primary" if _is_primary(entity) else "review"
        tags = _graph_entity_tags(entity, role)
        nodes[node_id] = {
            "id": node_id,
            "label": entity.get("canonical_name") or slug,
            "kind": entity.get("entity_kind") or "entity",
            "role": role,
            "tags": tags,
            "note_path": _guess_note_path(project.root, entity),
            "entity": _graph_entity_payload(entity),
        }
        for value in [slug, entity.get("canonical_name"), *(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]:
            key = _key(value)
            if key:
                slug_to_id[key] = node_id
    for entity in [*canon["primaries"], *canon["review_entities"]]:
        source_key = _key(entity.get("preferred_slug") or entity.get("canonical_name"))
        source_id = slug_to_id.get(source_key)
        if not source_id:
            continue
        for rel in entity.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            target_id = slug_to_id.get(_key(rel.get("target")))
            if not target_id:
                target_id = f"unresolved:{_key(rel.get('target'))}"
                nodes.setdefault(
                    target_id,
                    {
                        "id": target_id,
                        "label": rel.get("target") or "unresolved",
                        "kind": "unresolved",
                        "role": "review",
                        "tags": ["#review", "#unresolved"],
                        "note_path": None,
                    },
                )
            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "type": rel.get("type") or rel.get("relation_type") or "related_to",
                }
            )
    for chapter in canon["chapters"]:
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        if not chapter_id:
            continue
        node_id = f"chapter:{chapter_id}"
        nodes[node_id] = {
            "id": node_id,
            "label": chapter.get("chapter_title_original") or chapter_id,
            "kind": "chapter",
            "role": "chapter",
            "tags": _graph_chapter_tags(chapter),
            "note_path": _guess_chapter_note_path(project.root, chapter),
            "chapter": _graph_chapter_payload(chapter),
        }
    return {"nodes": list(nodes.values()), "edges": edges}


def _hydrate_author_graph_payload(project: ProjectRef, payload: dict[str, Any]) -> dict[str, Any]:
    markdown_index = read_markdown_graph_index(project) or {}
    notes_by_path = {
        str(note.get('path') or ''): note
        for note in markdown_index.get('notes') or []
        if isinstance(note, dict)
    }
    hydrated_nodes: list[dict[str, Any]] = []
    for node in payload.get('nodes') or []:
        if not isinstance(node, dict):
            continue
        note_path = str(node.get('note_path') or node.get('id') or '')
        indexed_note = notes_by_path.get(note_path, {})
        markdown_text = ''
        if note_path:
            note_file = project.root / note_path
            if note_file.exists() and note_file.suffix == '.md':
                markdown_text = note_file.read_text(encoding='utf-8', errors='replace')
        content = _markdown_content_hydration(markdown_text) if markdown_text else {}
        next_node = dict(node)
        next_node.setdefault('summary_excerpt', content.get('summary_excerpt') or str(node.get('summary') or ''))
        next_node.setdefault('key_facts_count', content.get('key_facts_count') or 0)
        next_node.setdefault('key_facts_preview', content.get('key_facts_preview') or [])
        next_node.setdefault('relationship_count', content.get('relationship_count') or int(node.get('degree') or 0))
        next_node.setdefault('evidence_count', content.get('evidence_count') or int(node.get('evidence_count') or 0))
        next_node.setdefault('backlinks', indexed_note.get('backlinks') or [])
        next_node.setdefault('outgoing_wikilinks', indexed_note.get('outgoing_wikilinks') or [])
        next_node.setdefault('display_label', format_author_facing_label(str(node.get('label') or '')))
        next_node.setdefault('display_kind', str(node.get('kind') or 'note'))
        hydrated_nodes.append(next_node)
    next_payload = dict(payload)
    next_payload['nodes'] = hydrated_nodes
    return next_payload


def build_semantic_health(
    project: ProjectRef,
    *,
    canon: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canon = canon or read_canon(project)
    artifacts = artifacts or list_artifacts(project)
    graph = graph or build_graph(project, canon=canon)
    invariants = _read_json(project.system_root / "semantic_invariants_audit.json") if project.system_root else {}
    invariant_checks = invariants.get("checks") if isinstance(invariants, dict) else []
    if not isinstance(invariant_checks, list):
        invariant_checks = []
    artifact_paths = {item.get("path") for item in artifacts if isinstance(item, dict)}
    unresolved_nodes = [node for node in graph.get("nodes", []) if node.get("kind") == "unresolved"]
    unresolved_edges = [edge for edge in graph.get("edges", []) if str(edge.get("target") or "").startswith("unresolved:")]
    primary_nodes = [node for node in graph.get("nodes", []) if node.get("role") == "primary"]
    review_nodes = [
        node
        for node in graph.get("nodes", [])
        if node.get("role") == "review" and node.get("kind") != "unresolved"
    ]
    chapter_nodes = [node for node in graph.get("nodes", []) if node.get("role") == "chapter"]
    review_queue = canon.get("review_queue") if isinstance(canon, dict) else {}
    review_items = review_queue.get("items") if isinstance(review_queue, dict) else []
    missing_expected_artifacts = [name for name in HEALTH_EXPECTED_ARTIFACTS if name not in artifact_paths]
    collision_count = _count_check_items(invariant_checks, "ontological_name_collisions", "collisions")
    duplicate_name_count = _count_check_items(invariant_checks, "duplicate_exact_canonical_names", "duplicates")
    near_duplicate_count = _count_check_items(invariant_checks, "near_duplicate_primary_names", "suspicious")
    unresolved_from_invariants = _check_detail_int(invariant_checks, "unresolved_relationship_targets", "count")
    failing_checks = [_health_check_summary(check) for check in invariant_checks if _check_status(check) in {"fail", "warn"}]
    high_severity_items = _review_severity_count(review_queue, review_items, "high")
    medium_severity_items = _review_severity_count(review_queue, review_items, "medium")
    canonical_ambiguity_items = sum(1 for item in review_items or [] if _looks_like_canonical_ambiguity(item))

    canon_stability = {
        "canonical_primary_count": len(canon.get("primaries", [])),
        "review_entity_count": len(canon.get("review_entities", [])),
        "canonical_collision_count": collision_count,
        "duplicate_exact_canonical_name_count": duplicate_name_count,
        "near_duplicate_primary_name_count": near_duplicate_count,
        "canonical_ambiguity_items": canonical_ambiguity_items,
    }
    relationship_integrity = {
        "relationship_edge_count": len(
            [edge for edge in graph.get("edges", []) if not str(edge.get("source") or "").startswith("chapter:")]
        ),
        "unresolved_relationship_targets": max(len(unresolved_nodes), unresolved_from_invariants or 0),
        "dangling_relationship_edges": len(unresolved_edges),
        "sample_unresolved_targets": [node.get("label") for node in unresolved_nodes[:8]],
    }
    review_pressure = {
        "review_queue_size": review_queue.get("item_count") if isinstance(review_queue, dict) else len(review_items or []),
        "high_severity_items": high_severity_items,
        "medium_severity_items": medium_severity_items,
        "review_type_count": len((review_queue.get("counts_by_type") or {})) if isinstance(review_queue, dict) else 0,
        "canonical_ambiguity_items": canonical_ambiguity_items,
    }
    materialization_integrity = {
        "missing_expected_artifacts": missing_expected_artifacts,
        "missing_expected_artifacts_count": len(missing_expected_artifacts),
        "missing_primary_notes": sum(1 for node in primary_nodes if not node.get("note_path")),
        "missing_review_notes": sum(1 for node in review_nodes if not node.get("note_path")),
        "missing_chapter_notes": sum(1 for node in chapter_nodes if not node.get("note_path")),
        "broken_wikilinks": None,
    }
    semantic_invariants = {
        "status": invariants.get("status") if isinstance(invariants, dict) else "not_available",
        "passed": invariants.get("passed") if isinstance(invariants, dict) else None,
        "failure_count": invariants.get("failure_count") if isinstance(invariants, dict) else None,
        "warning_count": invariants.get("warning_count") if isinstance(invariants, dict) else None,
        "total_count": len(invariant_checks),
        "pass_count": sum(1 for check in invariant_checks if _check_status(check) == "pass"),
        "skip_count": sum(1 for check in invariant_checks if _check_status(check) == "skip"),
        "checks": [_health_check_summary(check) for check in invariant_checks],
        "failing_checks": failing_checks,
        "raw_artifact_path": "semantic_invariants_audit.json" if "semantic_invariants_audit.json" in artifact_paths else None,
    }
    highlights = _health_highlights(
        canon_stability=canon_stability,
        relationship_integrity=relationship_integrity,
        review_pressure=review_pressure,
        materialization_integrity=materialization_integrity,
        semantic_invariants=semantic_invariants,
    )
    return {
        "overall_status": _overall_health_status(
            semantic_invariants=semantic_invariants,
            review_pressure=review_pressure,
            relationship_integrity=relationship_integrity,
            materialization_integrity=materialization_integrity,
        ),
        "canon_stability": canon_stability,
        "relationship_integrity": relationship_integrity,
        "review_pressure": review_pressure,
        "materialization_integrity": materialization_integrity,
        "semantic_invariants": semantic_invariants,
        "highlights": highlights,
    }


def build_canonicalization_payload(
    project: ProjectRef,
    *,
    canon: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canon = canon or read_canon(project)
    artifacts = artifacts or list_artifacts(project)
    system = project.system_root
    artifact_names = {item.get("path") for item in artifacts if isinstance(item, dict)}
    if system is None:
        return {"by_entity": {}, "available_artifacts": []}

    payloads = {
        "canonical_entity_map.json": _read_json(system / "canonical_entity_map.json"),
        "resolved_entities.json": _read_json(system / "resolved_entities.json"),
        "cleaned_entities.json": _read_json(system / "cleaned_entities.json"),
        "entity_clusters_audit.json": _read_json(system / "entity_clusters_audit.json"),
        "entity_resolution_audit.json": _read_json(system / "entity_resolution_audit.json"),
        "entity_cleanup_audit.json": _read_json(system / "entity_cleanup_audit.json"),
        "promotion_decisions_audit.json": _read_json(system / "promotion_decisions_audit.json"),
        "pre_vaerl_reconciliation_audit.json": _read_json(system / "pre_vaerl_reconciliation_audit.json"),
        "obsidian_relationship_reconciliation_audit.json": _read_json(system / "obsidian_relationship_reconciliation_audit.json"),
        "review_queue.json": _read_json(system / "review_queue.json"),
        "semantic_invariants_audit.json": _read_json(system / "semantic_invariants_audit.json"),
    }

    by_entity: dict[str, dict[str, Any]] = {}
    review_items = (canon.get("review_queue") or {}).get("items") or []
    invariant_checks = (payloads["semantic_invariants_audit.json"] or {}).get("checks") or []
    unresolved_targets = []
    for check in invariant_checks:
        if str(check.get("name") or "") != "relationship_targets_resolve_to_primary":
            continue
        unresolved_targets = (check.get("details") or {}).get("unresolved") or []
        break

    for entity in [*(canon.get("primaries") or []), *(canon.get("review_entities") or [])]:
        key = _key(entity.get("preferred_slug") or entity.get("canonical_name"))
        if not key:
            continue
        terms = _entity_terms(entity)
        resolved_match = _find_matching_object(payloads["resolved_entities.json"], terms, ("canonical_name", "preferred_slug", "aliases", "source_mentions"))
        cleaned_match = _find_matching_object(payloads["cleaned_entities.json"], terms, ("canonical_name", "preferred_slug", "aliases", "source_mentions"))
        resolution_match = _find_matching_object(
            (payloads["entity_resolution_audit.json"] or {}).get("resolutions") or [],
            terms,
            ("final_canonical_name", "accepted_aliases", "rejected_aliases"),
        )
        cluster_match = _find_cluster_match((payloads["entity_clusters_audit.json"] or {}).get("clusters") or [], terms)
        promotion_match = _find_matching_object(
            (payloads["promotion_decisions_audit.json"] or {}).get("decisions") or [],
            terms,
            ("canonical_name",),
        )
        related_reviews = _find_related_review_items(review_items, terms)
        nearby_reviews = _find_nearby_review_entities(canon.get("review_entities") or [], entity, terms)
        pre_vaerl = _extract_pre_vaerl_matches(payloads["pre_vaerl_reconciliation_audit.json"] or {}, terms)
        relationship_reconciliation = _extract_relationship_reconciliation_matches(
            payloads["obsidian_relationship_reconciliation_audit.json"] or {},
            terms,
        )
        unresolved_matches = [
            item for item in unresolved_targets
            if _term_matches_terms(item.get("source"), terms) or _term_matches_terms(item.get("target"), terms)
        ][:8]

        confidence = (
            resolved_match.get("confidence") if isinstance(resolved_match, dict) and resolved_match.get("confidence") is not None
            else cleaned_match.get("confidence") if isinstance(cleaned_match, dict) and cleaned_match.get("confidence") is not None
            else entity.get("confidence")
        )
        alias_count = len(entity.get("aliases") or [])
        mention_count = len(entity.get("source_mentions") or [])
        relationship_count = len([rel for rel in entity.get("relationships") or [] if isinstance(rel, dict)])
        fact_count = len(entity.get("key_facts") or [])
        chapter_refs = entity.get("chapter_refs") or []
        confidence_value = float(confidence) if isinstance(confidence, (int, float)) else None

        risk_signals = []
        if alias_count >= 6:
            risk_signals.append({"level": "warning", "label": "many aliases", "value": alias_count})
        if mention_count >= 8:
            risk_signals.append({"level": "warning", "label": "many source mentions", "value": mention_count})
        if confidence_value is not None and confidence_value < 0.75:
            risk_signals.append({"level": "warning", "label": "low confidence", "value": round(confidence_value, 3)})
        if str(entity.get("review_state") or "").casefold() != "canonical":
            risk_signals.append({"level": "warning", "label": "review_state not canonical", "value": entity.get("review_state") or "review"})
        if nearby_reviews:
            risk_signals.append({"level": "warning", "label": "nearby review entities", "value": len(nearby_reviews)})
        if related_reviews:
            risk_signals.append({"level": "warning", "label": "review pressure", "value": len(related_reviews)})
        if unresolved_matches:
            risk_signals.append({"level": "warning", "label": "unresolved relationship hints", "value": len(unresolved_matches)})

        artifact_refs = [
            name for name in (
                "canonical_entity_map.json",
                "resolved_entities.json",
                "cleaned_entities.json",
                "entity_clusters_audit.json",
                "entity_resolution_audit.json",
                "entity_cleanup_audit.json",
                "promotion_decisions_audit.json",
                "pre_vaerl_reconciliation_audit.json",
                "obsidian_relationship_reconciliation_audit.json",
                "review_queue.json",
            )
            if name in artifact_names
        ]

        by_entity[key] = {
            "canonical_name": entity.get("canonical_name"),
            "preferred_slug": entity.get("preferred_slug"),
            "entity_kind": entity.get("entity_kind"),
            "entity_subkind": entity.get("entity_subkind"),
            "review_state": entity.get("review_state") or entity.get("note_role"),
            "confidence": confidence,
            "aliases": entity.get("aliases") or [],
            "source_mentions": entity.get("source_mentions") or [],
            "chapter_refs": chapter_refs,
            "relationship_count": relationship_count,
            "key_fact_count": fact_count,
            "review_pressure_count": len(related_reviews),
            "nearby_review_entity_count": len(nearby_reviews),
            "resolved_entity": _limit_mapping(resolved_match, 12),
            "cleaned_entity": _limit_mapping(cleaned_match, 12),
            "cluster_match": _limit_mapping(cluster_match, 10),
            "resolution_match": _limit_mapping(resolution_match, 12),
            "promotion_match": _limit_mapping(promotion_match, 12),
            "cleanup_summary": _cleanup_summary(payloads["entity_cleanup_audit.json"] or {}),
            "related_review_items": related_reviews[:8],
            "nearby_review_entities": nearby_reviews[:8],
            "pre_vaerl_matches": pre_vaerl,
            "relationship_reconciliation": relationship_reconciliation,
            "unresolved_relationship_hints": unresolved_matches,
            "risk_signals": risk_signals,
            "artifact_refs": artifact_refs,
        }

    return {
        "by_entity": by_entity,
        "available_artifacts": sorted(name for name in artifact_names if isinstance(name, str)),
    }


def _graph_entity_tags(entity: dict[str, Any], role: str) -> list[str]:
    tags = _normalize_graph_tags(entity.get("tags") or [])
    tags.extend([f"#{role}", f"#{entity.get('entity_kind') or 'entity'}"])
    if entity.get("entity_subkind"):
        tags.append(f"#{entity['entity_subkind']}")
    return sorted(set(_normalize_graph_tags(tags)))


def _graph_chapter_tags(chapter: dict[str, Any]) -> list[str]:
    tags = ["#chapter"]
    if chapter.get("chapter_label_type"):
        tags.append(f"#{chapter['chapter_label_type']}")
    return sorted(set(_normalize_graph_tags(tags)))


def _normalize_graph_tags(tags: list[Any]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        value = str(tag or "").strip()
        if not value:
            continue
        if not value.startswith("#"):
            value = f"#{value}"
        normalized.append(value.replace(" ", "_").casefold())
    return normalized


def _graph_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "canonical_name",
        "preferred_slug",
        "entity_kind",
        "entity_subkind",
        "review_state",
        "note_role",
        "summary",
        "aliases",
        "key_facts",
        "relationships",
        "source_mentions",
        "source_refs",
        "tags",
        "confidence",
    ]
    return {field: entity.get(field) for field in fields if field in entity}


def _graph_chapter_payload(chapter: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "chapter_id",
        "sequence_index",
        "chapter_title_original",
        "chapter_title_canonical",
        "chapter_label_type",
        "chapter_number_in_label",
        "chapter_summary",
        "summary",
        "title_parse_signals",
    ]
    return {field: chapter.get(field) for field in fields if field in chapter}


def _project_from_candidate(path: Path) -> ProjectRef | None:
    manifest_path = path / 'textifai.project.json'
    manifest = _read_json(manifest_path)
    if isinstance(manifest, dict) and manifest.get('schema') == 'textifai.project':
        title = str(manifest.get('title') or path.name)
        return ProjectRef(project_id=_project_id(path), name=title, root=path, system_root=None, kind='textifai_project', manifest_path=manifest_path, manifest=manifest)
    system = path / "99_System"
    has_system_artifacts = lambda root: any((root / name).exists() for name in ("obsidian_import.json", "review_queue.json", "ingestion_graph.json", "markdown_manifest.json", "markdown_graph_index.json"))
    has_markdown_manifest = lambda root: any((root / name).exists() for name in ("System/materialization_manifest.json", "System/markdown_manifest.json", "99_System/markdown_manifest.json"))
    if system.exists() and has_system_artifacts(system):
        return ProjectRef(project_id=_project_id(path), name=path.name, root=path, system_root=system, kind="vault_or_run")
    if path.name == "99_System" and has_system_artifacts(path):
        root = path.parent
        return ProjectRef(project_id=_project_id(root), name=root.name, root=root, system_root=path, kind="system_run")
    if has_markdown_manifest(path):
        return ProjectRef(project_id=_project_id(path), name=path.name, root=path, system_root=system if system.exists() else path / "System", kind="markdown_vault")
    return None

def _markdown_manifest_candidates(project: ProjectRef) -> list[Path]:
    candidates: list[Path] = []
    manifest_path = _project_path(project, 'markdown_manifest')
    if manifest_path:
        candidates.append(manifest_path)
    if project.system_root:
        candidates.extend([
            project.system_root / "markdown_manifest.json",
            project.system_root / "materialization_manifest.json",
        ])
    candidates.extend([
        project.root / "99_System" / "markdown_manifest.json",
        project.root / "System" / "materialization_manifest.json",
        project.root / "System" / "markdown_manifest.json",
    ])
    return candidates

def _markdown_index_candidates(project: ProjectRef) -> list[Path]:
    candidates: list[Path] = []
    manifest_path = _project_path(project, 'markdown_graph_index')
    if manifest_path:
        candidates.append(manifest_path)
    if project.system_root:
        candidates.append(project.system_root / "markdown_graph_index.json")
    candidates.extend([
        project.root / "99_System" / "markdown_graph_index.json",
        project.root / "System" / "markdown_graph_index.json",
    ])
    return candidates

def read_markdown_manifest(project: ProjectRef) -> dict[str, Any] | None:
    for path in _markdown_manifest_candidates(project):
        payload = _read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("notes"), list):
            return payload
    return None

def read_markdown_graph_index(project: ProjectRef) -> dict[str, Any] | None:
    for path in _markdown_index_candidates(project):
        payload = _read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
            return payload
    if read_markdown_manifest(project):
        try:
            return build_markdown_graph_index(project.root)
        except OSError:
            return None
    return None

def _markdown_index_note(markdown_index: dict[str, Any], note_path: str) -> dict[str, Any]:
    for note in markdown_index.get("notes") or []:
        if isinstance(note, dict) and note.get("path") == note_path:
            return note
    return {}

def _build_graph_from_markdown_index(project: ProjectRef) -> dict[str, Any] | None:
    markdown_index = read_markdown_graph_index(project)
    if not isinstance(markdown_index, dict) or not markdown_index.get("nodes"):
        return None
    notes_by_path = {
        str(note.get("path") or ""): note
        for note in markdown_index.get("notes") or []
        if isinstance(note, dict)
    }
    hydration_cache: dict[str, dict[str, Any]] = {}
    nodes: list[dict[str, Any]] = []
    for node in markdown_index.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        note_path = str(node.get("id") or "")
        note = notes_by_path.get(note_path, {})
        frontmatter = note.get("frontmatter") if isinstance(note.get("frontmatter"), dict) else {}
        kind = str(node.get("kind") or frontmatter.get("kind") or "note")
        role = "chapter" if kind == "chapter" else "review" if kind == "review" or frontmatter.get("review_state") == "needs_review" else "primary"
        status = str(frontmatter.get("review_state") or frontmatter.get("status") or role or "ready")
        degree = int(node.get("degree") or note.get("degree") or 0)
        visual = _node_visual(kind, frontmatter, degree=degree, role=role)
        nodes.append({
            "id": note_path,
            "label": node.get("label") or frontmatter.get("canonical_label") or Path(note_path).stem,
            "kind": kind,
            "role": role,
            "tags": node.get("tags") or note.get("tags") or [],
            "note_path": note_path,
            "status": status,
            "review_state": status,
            "degree": degree,
            "size": node.get("size") or 1 + degree,
            "radius": visual["radius"],
            "color": visual["kind_color"],
            "frontmatter": frontmatter,
            "backlinks": note.get("backlinks") or [],
            "outgoing_wikilinks": note.get("outgoing_wikilinks") or [],
            "visual": visual,
        })
    canonical_redirects, canonical_note_redirects = _build_canonical_redirect_maps(nodes)
    nodes_by_id = {str(node.get("id") or ""): node for node in nodes}
    for node in nodes:
        node_id = str(node.get("id") or "")
        canonical_node_id = canonical_redirects.get(node_id, node_id)
        canonical_node = nodes_by_id.get(canonical_node_id) or node
        canonical_note_path = str(canonical_node.get("note_path") or canonical_node.get("id") or "")
        node["canonical_node_id"] = canonical_node_id
        node["canonical_note_path"] = canonical_note_path
        node["canonical_kind"] = str(canonical_node.get("kind") or node.get("kind") or "note")
        node["display_kind"] = str(canonical_node.get("kind") or node.get("kind") or "note")
        node["canonical_degree"] = int(canonical_node.get("degree") or node.get("degree") or 0)
        if canonical_note_path not in hydration_cache:
            canonical_note = notes_by_path.get(canonical_note_path, {}) if canonical_note_path else {}
            markdown_text = str(canonical_note.get("markdown") or "")
            if not markdown_text and canonical_note_path:
                note_file = project.root / canonical_note_path
                if note_file.exists():
                    markdown_text = note_file.read_text(encoding="utf-8", errors="replace")
            hydration_cache[canonical_note_path] = _markdown_content_hydration(markdown_text) if markdown_text else {
                "summary_excerpt": "",
                "key_facts_count": 0,
                "key_facts_preview": [],
                "relationship_count": 0,
                "evidence_count": 0,
            }
        node.update(hydration_cache.get(canonical_note_path, {}))
        if canonical_node_id != node_id:
            node["canonical_redirected"] = True
            node["canonical_redirect_reason"] = "exact_label_cross_kind"
    node_ids = {str(node.get("id") or "") for node in nodes}
    edges: list[dict[str, Any]] = []
    seen_edge_ids: dict[str, int] = {}
    for edge in markdown_index.get("edges") or []:
        if not isinstance(edge, dict) or edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            continue
        label = edge.get("label") or "wikilink"
        base_edge_id = _edge_id(edge.get("source"), edge.get("target"), label)
        seen_edge_ids[base_edge_id] = seen_edge_ids.get(base_edge_id, 0) + 1
        edge_id = base_edge_id if seen_edge_ids[base_edge_id] == 1 else f"{base_edge_id}_{seen_edge_ids[base_edge_id]}"
        edges.append({
            "id": edge_id,
            "source": edge.get("source"),
            "target": edge.get("target"),
            "source_note_path": edge.get("source"),
            "target_note_path": edge.get("target"),
            "type": label,
            "kind": label,
            "label": label,
        })
    return {
        "nodes": nodes,
        "edges": edges,
        "graph_contract_version": 2,
        "canonical_redirects": canonical_redirects,
        "canonical_note_redirects": canonical_note_redirects,
        "metadata": {
            "graph_contract_version": 2,
            "source": "markdown_graph_index",
            "graph_mode": "legacy_markdown_index",
            "author_graph_ready": False,
            "canonical_redirects": canonical_redirects,
            "canonical_note_redirects": canonical_note_redirects,
            "local_graph": {
                "endpoint_contract": "edge.source and edge.target are node.id values",
                "preserve_valid_endpoints": True,
            },
            "graph_summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "node_counts_by_kind": _count_nodes_by_kind(nodes),
                "synthetic_label_count": 0,
            },
            "markdown_summary": {
                "note_count": markdown_index.get("note_count"),
                "orphan_note_count": len(markdown_index.get("orphan_notes") or []),
                "unresolved_link_count": len(markdown_index.get("unresolved_links") or []),
                "tags": markdown_index.get("tags") or [],
            },
            "visuals": {
                "kind_colors": KIND_VISUALS,
                "status_borders": STATUS_VISUALS,
            },
        },
    }

def _read_writer_outcome(project: ProjectRef) -> dict[str, Any]:
    candidates: list[Path] = []
    manifest_path = _project_path(project, 'writer_outcome')
    if manifest_path:
        candidates.append(manifest_path)
    if project.system_root:
        candidates.append(project.system_root / "writer_outcome.json")
    candidates.extend([
        project.root / "99_System" / "writer_outcome.json",
        project.root / "System" / "writer_outcome.json",
    ])
    for path in candidates:
        payload = _read_json(path)
        if isinstance(payload, dict) and payload:
            return payload
    return {}

def _node_visual(kind: str, frontmatter: dict[str, Any], *, degree: int = 0, role: str = "primary") -> dict[str, Any]:
    status = str(frontmatter.get("review_state") or frontmatter.get("status") or "ready")
    base = 13 if kind == "character" else 8 if role == "chapter" else 10 if role == "review" else 11
    radius = max(base, min(base + int(degree or 0) * 1.45, 26))
    return {
        "kind_color": KIND_VISUALS.get(kind, KIND_VISUALS["concept"])["color"],
        "status_border": STATUS_VISUALS.get(status, STATUS_VISUALS["ready"])["border"],
        "status": status,
        "radius": radius,
    }


def _edge_id(source: Any, target: Any, label: Any) -> str:
    raw = f"{source or ''}::{label or 'edge'}::{target or ''}"
    return "edge:" + slugify(raw).strip("_")


def _build_canonical_redirect_maps(nodes: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        key = _key(node.get("label") or node.get("id") or "")
        if not key:
            continue
        groups.setdefault(key, []).append(node)

    canonical_redirects: dict[str, str] = {}
    canonical_note_redirects: dict[str, str] = {}
    for entries in groups.values():
        if len(entries) < 2:
            continue
        kinds = {str(item.get("kind") or "") for item in entries}
        if "chapter" in kinds:
            continue
        target = sorted(
            entries,
            key=lambda item: (
                CANONICAL_KIND_PRIORITY.get(str(item.get("kind") or ""), 0),
                1 if str(item.get("id") or "").startswith("Characters/") else 0,
                int(item.get("degree") or 0),
            ),
            reverse=True,
        )[0]
        target_id = str(target.get("id") or "")
        target_kind = str(target.get("kind") or "")
        target_path = str(target.get("note_path") or target_id)
        for node in entries:
            node_id = str(node.get("id") or "")
            node_kind = str(node.get("kind") or "")
            node_path = str(node.get("note_path") or node_id)
            if not node_id or node_id == target_id:
                continue
            if node_kind == target_kind:
                continue
            canonical_redirects[node_id] = target_id
            if node_path and target_path and node_path != target_path:
                canonical_note_redirects[node_path] = target_path
    return canonical_redirects, canonical_note_redirects


def _build_graph_from_ingestion_artifact(project: ProjectRef) -> dict[str, Any] | None:
    manifest_graph = _read_project_json(project, 'graph')
    if isinstance(manifest_graph, dict) and isinstance(manifest_graph.get('nodes'), list):
        return manifest_graph
    system = project.system_root
    if system is None:
        return None
    ingestion = _read_json(system / "ingestion_graph.json")
    if not isinstance(ingestion, dict):
        return None
    if not any(key in ingestion for key in ("nodes", "characters", "places", "concepts", "objects", "events")):
        return None
    payload = adapt_ingestion_graph_to_viewer_graph(ingestion)
    if isinstance(payload, dict):
        metadata = payload.setdefault('metadata', {})
        if isinstance(metadata, dict):
            metadata.setdefault('graph_mode', 'legacy_ingestion')
            metadata.setdefault('author_graph_ready', False)
    return payload


def _hydrate_review_queue(raw_review_queue: dict[str, Any], entities: list[dict[str, Any]], chapters: list[dict[str, Any]], project_root: Path) -> dict[str, Any]:
    items = [row for row in (raw_review_queue.get('items') or []) if isinstance(row, dict)]
    decision_items: list[dict[str, Any]] = []
    summary_counts = {
        'total_pending': 0,
        'possible_merges': 0,
        'probable_aliases': 0,
        'uncertain_relationships': 0,
        'insufficient_evidence': 0,
        'pronoun_pov': 0,
        'unconfirmed_local_candidates': 0,
        'deferred': 0,
        'local_unapplied': 0,
    }
    entity_map: dict[str, dict[str, Any]] = {
        _key(str(row.get('canonical_name') or '')): row
        for row in entities if isinstance(row, dict) and row.get('canonical_name')
    }
    chapter_titles = {}
    # Build from chapters list first
    for row in (chapters or []):
        if not isinstance(row, dict):
            continue
        cid = str(row.get('chapter_id') or '')
        if not cid:
            continue
        title = str(row.get('chapter_title_original') or row.get('chapter_title_canonical') or '').strip()
        if not title:
            # Fallback: try to read the chapter markdown canonical_label from frontmatter or first H1
            ch_filename = f'Ch_{cid.split("_", 1)[1] if cid.lower().startswith("ch_") else cid}.md'
            ch_path = project_root / 'markdown' / 'Chapters' / ch_filename
            if not ch_path.exists():
                ch_path = project_root / 'markdown' / 'Chapters' / f'{cid}.md'
            if ch_path.exists():
                try:
                    raw = ch_path.read_text(encoding='utf-8', errors='replace')
                    # Try to parse canonical_label from frontmatter
                    in_fm = False
                    fm_lines = []
                    body_started = False
                    for line in raw.splitlines():
                        stripped = line.strip()
                        if stripped == '---' and not body_started:
                            if in_fm:
                                body_started = True
                                continue
                            else:
                                in_fm = True
                                continue
                        if in_fm:
                            fm_lines.append(stripped)
                            if stripped.startswith('canonical_label:'):
                                val = stripped.split(':', 1)[1].strip().strip('"').strip("'")
                                if val and len(val) < 200:
                                    title = val
                                    break
                            elif stripped.startswith('chapter_title:') or stripped.startswith('title:'):
                                val = stripped.split(':', 1)[1].strip().strip('"').strip("'")
                                if val and len(val) < 200:
                                    title = val
                                    break
                        elif body_started:
                            if stripped.startswith('# ') and not stripped.startswith('## '):
                                val = stripped.lstrip('# ').strip('*').strip()
                                if val and len(val) < 200:
                                    title = val
                                    break
                except OSError:
                    pass
        chapter_titles[cid] = title or cid
    chapter_paths = _build_chapter_path_map(chapters, project_root) if hasattr(chapters, '__iter__') else {}
    for item in items:
        target_label = format_author_facing_label(str(item.get('target_label') or '').strip())
        summary = str(item.get('summary') or '').strip()
        source_refs = [row for row in (item.get('source_refs') or []) if isinstance(row, dict)]
        chapter_id = str(item.get('chapter_id') or '')
        chapter_label = chapter_titles.get(chapter_id) or chapter_id or ''
        normalized_target = _key(target_label)
        matched_entity = entity_map.get(normalized_target)
        matched_label = format_author_facing_label(str(matched_entity.get('canonical_name') or target_label)) if matched_entity else target_label

        if not target_label or normalized_target in {'yo', 'ella', 'el', 'él', 'la', 'tu', 'tú'}:
            review_type = 'pronoun_pov'
            summary_key = 'pronoun_pov'
            severity = 'medium'
            title = f'{target_label or "Pronombre"} · sin entidad sugerida'
            source_entity = {'label': target_label or 'pronoun'}
            target_entity = None
            suggested_action = 'review'
            human_reason = 'Pronombre de POV detectado; necesita resolución explícita antes de entrar al canon.'
        elif normalized_target in entity_map:
            review_type = 'possible_merge'
            summary_key = 'possible_merges'
            severity = 'low'
            title = f'{target_label} → {matched_label}'
            source_entity = {'label': target_label}
            target_entity = {'label': matched_label, 'canonical_name': matched_label}
            suggested_action = 'merge'
            human_reason = summary or f'{target_label} podría ser la misma entidad que {matched_label}.'
        elif 'local_candidate' in target_label.casefold() or 'local candidate' in target_label.casefold():
            review_type = 'unconfirmed_local_candidate'
            summary_key = 'unconfirmed_local_candidates'
            severity = 'medium'
            title = f'{target_label} · sin entidad sugerida'
            source_entity = None
            target_entity = {'label': target_label}
            suggested_action = 'review'
            human_reason = summary or 'Candidato local detectado; necesita confirmación antes de ser proyección canónica.'
        elif any(token in (summary or '').casefold() for token in ['no nombrad', 'identidad no especificada', 'no se describe', 'ambiguo', 'sin identificar']):
            review_type = 'insufficient_evidence'
            summary_key = 'insufficient_evidence'
            severity = 'medium'
            title = f'{target_label} · sin entidad sugerida'
            source_entity = None
            target_entity = {'label': target_label} if target_label else None
            suggested_action = 'review'
            human_reason = summary or f'Referencia ambigua: {target_label}. No hay suficiente evidencia para resolverla automáticamente.'
        else:
            review_type = 'uncertain_relationships'
            summary_key = 'uncertain_relationships'
            severity = 'low'
            title = f'{target_label} · sin entidad sugerida' if not matched_entity else f'{target_label} → {matched_label}'
            source_entity = None
            target_entity = {'label': target_label}
            suggested_action = 'review'
            human_reason = summary or f'Referencia ambigua: {target_label}. El modelo no la resolvió a una entidad canónica con suficiente confianza.'

        subtitle = human_reason or summary or 'Necesita decisión editorial.'
        if subtitle.strip().casefold() == 'review':
            subtitle = 'Necesita decisión editorial basada en evidencia narrativa.'
        # Build chapter label from chapter_id
        chapter_label = chapter_titles.get(chapter_id) or chapter_id or ''
        # Get chapter note name from markdown manifest if available
        chapter_note = None
        if chapter_paths and chapter_id:
            for p_ch, v_ch in chapter_paths.items():
                if chapter_id in str(p_ch) or p_ch.replace('.md','').replace('Ch_','ch_') == chapter_id.replace('Ch_','ch_'):
                    chapter_note = v_ch.name if hasattr(v_ch, 'name') else str(p_ch)
                    break
        evidence_refs = []
        for ref in source_refs:
            ev_ch_id = str(ref.get('chapter_id') or chapter_id or '')
            ev_ch_label = chapter_titles.get(ev_ch_id) or chapter_note or ev_ch_id or ''
            ev_chunk_id = str(ref.get('chunk_id') or '')
            ev_has_excerpt = False
            ev_excerpt = _resolve_evidence_excerpt(chapter_paths, ev_ch_id, ref)
            if ev_excerpt:
                ev_has_excerpt = True
            # pointer as technical detail, not main evidence
            ev_pointer_parts = [p for p in ev_chunk_id.split('_') if p and p not in ('source','chunk','')]
            ev_pointer_short = ' → '.join(ev_pointer_parts[-2:]) if len(ev_pointer_parts) > 2 else ev_chunk_id
            ev = {
                'chapter_id': ev_ch_id,
                'chapter_label': ev_ch_label,
                'pointer': ev_chunk_id,
                'pointer_short': ev_pointer_short,
                'char_start': ref.get('char_start'),
                'char_end': ref.get('char_end'),
                'has_text': ev_has_excerpt,
                'excerpt': ev_excerpt,
            }
            evidence_refs.append(ev)
        decision_items.append(
            {
                'id': str(item.get('id') or f'review:{len(decision_items)+1}'),
                'type': review_type,
                'severity': severity,
                'title': title,
                'subtitle': subtitle,
                'source_entity': source_entity,
                'target_entity': target_entity,
                'suggested_action': suggested_action,
                'human_reason': human_reason,
                'evidence_summary': f'{len(evidence_refs)} referencias' if evidence_refs else 'Sin evidencia textual',
                'evidence_refs': evidence_refs,
                'local_state': 'pending',
                'impact_if_accept': 'Refina la proyección canónica y reduce ambigüedad visible.',
                'impact_if_reject': 'Mantiene la referencia fuera del canon visible hasta nueva evidencia.',
                'technical_details': {'chapter_id': chapter_id, 'status': item.get('status'), 'raw_target_label': target_label, 'matched_entity': matched_label if matched_entity else None},
            }
        )
        summary_counts['total_pending'] += 1
        summary_counts[summary_key] = summary_counts.get(summary_key, 0) + 1

    hydrated = dict(raw_review_queue)
    hydrated['decision_items'] = decision_items
    hydrated['decision_summary'] = summary_counts
    return hydrated


def _build_chapter_path_map(chapters: list[dict[str, Any]], project_root: Path) -> dict[str, Path]:
    """Map chapter_id to markdown path for evidence excerpt resolution."""
    from pathlib import Path as _Path
    result: dict[str, _Path] = {}
    for ch in (chapters or []):
        cid = str(ch.get('chapter_id') or '')
        if not cid:
            continue
        candidate = project_root / 'markdown' / 'Chapters' / f'{cid}.md'
        if not candidate.exists() and cid.lower().startswith('ch_'):
            candidate = project_root / 'markdown' / 'Chapters' / f'Ch_{cid.split("_", 1)[1]}.md'
        if candidate.exists():
            result[cid] = candidate
    return result


def _is_meaningful_excerpt(text_snippet: str) -> bool:
    """Return True if the snippet looks like narrative content, not frontmatter/metadata."""
    if not text_snippet:
        return False
    # Skip if mostly frontmatter-like patterns
    lower = text_snippet.lower()
    frontmatter_indicators = [
        'schema:', 'created_at:', 'updated_at:', 'source_refs:',
        'chapter_id:', 'canonical_id:', 'vaerl_id:', 'kind:', 'tags:',
        'review_state:', 'status:', 'aliases:', 'relationships:',
        'character_count:', 'word_count:', 'chunk_id:',
    ]
    indicator_count = sum(1 for ind in frontmatter_indicators if ind in lower)
    # If more than 30% of words look like frontmatter, discard
    words = text_snippet.split()
    if len(words) < 5:
        return False
    if indicator_count >= 2:
        return False
    # Must have some content words (length > 3, not all numbers/symbols)
    content_words = [w for w in words if len(w) > 3 and not all(c in '0123456789-:[]{}' for c in w)]
    return len(content_words) >= 3


def _resolve_evidence_excerpt(chapter_paths: dict[str, Path], chapter_id: str, ref: dict[str, Any]) -> str | None:
    import math
    char_start = ref.get('char_start')
    char_end = ref.get('char_end')
    if not chapter_id or not chapter_paths:
        return None
    ch_path = chapter_paths.get(chapter_id)
    if not ch_path:
        return None
    try:
        text = ch_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    if isinstance(char_start, (int, float)) and char_start >= 0:
        start = int(char_start)
        end = min(len(text), int(char_end) + 120) if isinstance(char_end, (int, float)) and char_end >= 0 else min(start + 240, len(text))
        if start < len(text):
            pad = max(0, start - 40)
            snippet = text[pad:min(end, len(text)):360].replace('\r','\n')
            lines = [l.strip() for l in snippet.split('\n') if l.strip()]
            candidate = ' '.join(lines[:8]) if lines else ''
            if _is_meaningful_excerpt(candidate):
                return candidate
            return None
    return None


def _project_id(path: Path) -> str:
    return path.resolve().as_posix().replace("/", "__").strip("_")

def _discover_registry_projects() -> list[ProjectRef]:
    payload = _read_json(LOCAL_PROJECT_REGISTRY)
    if not isinstance(payload, dict):
        return []
    projects: list[ProjectRef] = []
    for row in payload.get('projects') or []:
        if not isinstance(row, dict):
            continue
        manifest_path = Path(str(row.get('manifest_path') or '')).resolve()
        manifest = _read_json(manifest_path)
        if not manifest_path.exists() or not isinstance(manifest, dict) or manifest.get('schema') != 'textifai.project':
            continue
        root = manifest_path.parent
        projects.append(ProjectRef(project_id=_project_id(root), name=str(manifest.get('title') or root.name), root=root, system_root=None, kind='textifai_project', manifest_path=manifest_path, manifest=manifest))
    return projects

def _project_path(project: ProjectRef, key: str) -> Path | None:
    manifest = project.manifest or {}
    paths = manifest.get('paths') if isinstance(manifest.get('paths'), dict) else {}
    value = paths.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = _safe_child(project.root, value)
    return candidate

def _read_project_json(project: ProjectRef, key: str) -> Any:
    path = _project_path(project, key)
    return _read_json(path) if path else None

def _project_work(project: ProjectRef, obsidian_import: Any) -> dict[str, Any]:
    if isinstance(obsidian_import, dict) and isinstance(obsidian_import.get('work'), dict):
        return obsidian_import.get('work') or {}
    manifest = project.manifest or {}
    return {
        'title': manifest.get('title'),
        'language': manifest.get('language'),
    }


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError("Path escapes project root")
    return candidate


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _artifact_meta(system_root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(system_root).as_posix()
    return {
        "path": rel,
        "name": path.name,
        "kind": "directory" if path.is_dir() else "json" if path.suffix == ".json" else "file",
        "size": path.stat().st_size if path.is_file() else None,
        "mtime": path.stat().st_mtime,
    }


def _is_primary(entity: Any) -> bool:
    return isinstance(entity, dict) and (
        str(entity.get("review_state") or "").casefold() == "canonical"
        or str(entity.get("note_role") or "").casefold() == "primary"
    )


def _tags_from_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    tags = frontmatter.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return [str(tag) for tag in tags if str(tag).strip()]


def _note_role(path: Path, frontmatter: dict[str, Any]) -> str:
    parts = set(path.parts)
    tags = {tag.strip("#").casefold() for tag in _tags_from_frontmatter(frontmatter)}
    if "99_System" in parts or "system" in tags:
        return "system"
    if "90_Review" in parts or "review" in tags:
        return "review"
    if "Chapters" in parts or "chapter" in tags:
        return "chapter"
    if "Chapter_Summaries" in parts or "summary" in tags:
        return "summary"
    if "Profiles" in parts or "primary" in tags:
        return "primary"
    return "note"


def _guess_note_path(root: Path, entity: dict[str, Any]) -> str | None:
    candidates = [
        str(entity.get("preferred_slug") or "").strip(),
        slugify(str(entity.get("canonical_name") or "")),
    ]
    candidates.extend(slugify(str(alias or "")) for alias in entity.get("aliases") or [])
    for slug in [item for item in candidates if item]:
        matches = list(root.rglob(f"{slug}.md"))
        if matches:
            return matches[0].relative_to(root).as_posix()
    return None


def _guess_chapter_note_path(root: Path, chapter: dict[str, Any]) -> str | None:
    chapter_id = str(chapter.get("chapter_id") or "").strip()
    if not chapter_id:
        return None
    matches = list(root.rglob(f"{chapter_id}.md"))
    if matches:
        return matches[0].relative_to(root).as_posix()
    return None


def _key(value: Any) -> str:
    return slugify(str(value or "")).strip("_")


def format_author_facing_label(label: str) -> str:
    text = str(label or '').strip()
    if not text:
        return text
    replacements = {
        'unnamed_girl': 'chica sin identificar',
        'unnamed girl': 'chica sin identificar',
        'hombremisterioso': 'hombre misterioso',
        'hombre_misterioso': 'hombre misterioso',
    }
    key = _key(text)
    if key in replacements:
        text = replacements[key]
        return text[:1].upper() + text[1:] if text else text
    text = re.sub(r'([a-záéíóúñ])([A-ZÁÉÍÓÚÑ])', r'\1 \2', text)
    text = text.replace('_', ' ')
    text = re.sub(r'^él\s*\(([^)]*)\)$', r'\1', text, flags=re.I).strip()
    text = re.sub(r'\s*\((protagonist|narrator|protagonista|narrador)[^)]*\)', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^\((.*)\)$', r'\1', text).strip()
    if text.startswith('él ') and 'padre de' in text.casefold():
        text = re.sub(r'^él\s*', '', text, flags=re.I).strip()
    return text[:1].upper() + text[1:] if text else text

def _count_nodes_by_kind(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        kind = str(node.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _check_status(check: Any) -> str:
    return str((check or {}).get("status") or "").casefold()


def _count_check_items(checks: Any, name: str, detail_key: str) -> int:
    for check in checks or []:
        if str(check.get("name") or "") != name:
            continue
        values = (check.get("details") or {}).get(detail_key) or []
        return len(values) if isinstance(values, list) else 0
    return 0


def _review_severity_count(review_queue: Any, items: Any, severity: str) -> int:
    if isinstance(review_queue, dict):
        counts = review_queue.get("counts_by_severity") or {}
        if severity in counts:
            return int(counts.get(severity) or 0)
    return sum(1 for item in items or [] if str(item.get("severity") or "").casefold() == severity)


def _check_detail_int(checks: Any, name: str, detail_key: str) -> int | None:
    for check in checks or []:
        if str(check.get("name") or "") != name:
            continue
        value = (check.get("details") or {}).get(detail_key)
        if isinstance(value, int):
            return value
    return None


def _looks_like_canonical_ambiguity(item: Any) -> bool:
    review_type = str((item or {}).get("review_type") or "").casefold()
    return any(token in review_type for token in ("merge", "canonical", "alias", "identity", "duplicate"))


def _entity_terms(entity: dict[str, Any]) -> set[str]:
    values = [
        entity.get("canonical_name") or "",
        entity.get("preferred_slug") or "",
        *(entity.get("aliases") or []),
        *(entity.get("source_mentions") or []),
    ]
    terms: set[str] = set()
    for value in values:
        key = _key(value)
        if key:
            terms.add(key)
    return terms


def _term_matches_terms(value: Any, terms: set[str]) -> bool:
    return _key(value) in terms if terms else False


def _extract_term_values(item: Any, field: str) -> list[str]:
    if not isinstance(item, dict):
        return []
    value = item.get(field)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(entry or "") for entry in value]
    return [str(value)]


def _find_matching_object(rows: Any, terms: set[str], fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            for value in _extract_term_values(row, field):
                if _term_matches_terms(value, terms):
                    return row
    return {}


def _find_cluster_match(clusters: Any, terms: set[str]) -> dict[str, Any]:
    if not isinstance(clusters, list):
        return {}
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        variants = cluster.get("variants") or []
        for variant in variants if isinstance(variants, list) else []:
            if _term_matches_terms((variant or {}).get("name"), terms):
                return cluster
    return {}


def _find_related_review_items(review_items: list[dict[str, Any]], terms: set[str]) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for item in review_items or []:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidate_entities") or []
        candidate_hit = any(
            _term_matches_terms((candidate or {}).get("canonical_name"), terms)
            or _term_matches_terms((candidate or {}).get("preferred_slug"), terms)
            for candidate in candidates
            if isinstance(candidate, dict)
        )
        source_hit = _term_matches_terms(item.get("source_entity"), terms)
        target_hit = _term_matches_terms(item.get("target_text"), terms)
        if not (candidate_hit or source_hit or target_hit):
            continue
        related.append(
            {
                "review_item_id": item.get("review_item_id"),
                "review_type": item.get("review_type"),
                "severity": item.get("severity"),
                "source_entity": item.get("source_entity"),
                "target_text": item.get("target_text"),
                "candidate_count": len(candidates if isinstance(candidates, list) else []),
                "evidence_count": len((item.get("evidence") or []) if isinstance(item.get("evidence"), list) else []),
            }
        )
    return related


def _find_nearby_review_entities(review_entities: list[dict[str, Any]], entity: dict[str, Any], terms: set[str]) -> list[dict[str, Any]]:
    nearby: list[dict[str, Any]] = []
    entity_key = _key(entity.get("preferred_slug") or entity.get("canonical_name"))
    for review in review_entities or []:
        if not isinstance(review, dict):
            continue
        review_key = _key(review.get("preferred_slug") or review.get("canonical_name"))
        if not review_key or review_key == entity_key:
            continue
        review_terms = _entity_terms(review)
        if terms.isdisjoint(review_terms):
            continue
        nearby.append(
            {
                "canonical_name": review.get("canonical_name"),
                "preferred_slug": review.get("preferred_slug"),
                "entity_kind": review.get("entity_kind"),
                "review_state": review.get("review_state"),
                "confidence": review.get("confidence"),
                "shared_terms": sorted(list(terms.intersection(review_terms)))[:6],
            }
        )
    return nearby


def _extract_pre_vaerl_matches(payload: dict[str, Any], terms: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"counts": {}, "samples": {}}

    def filter_rows(rows: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        if not isinstance(rows, list):
            return selected
        for row in rows:
            if not isinstance(row, dict):
                continue
            if any(_term_matches_terms(row.get(field), terms) for field in fields):
                selected.append(_limit_mapping(row, 10))
        return selected[:8]

    auto_merged = filter_rows(payload.get("auto_merged_entities"), ("source_entity", "target_entity"))
    candidates = filter_rows(payload.get("candidate_reviews"), ("source_entity", "candidate_target"))
    rejected = filter_rows(payload.get("rejected_candidates"), ("source_entity", "candidate_target"))
    return {
        "counts": {
            "auto_merged_count": payload.get("auto_merged_count"),
            "candidate_review_count": payload.get("candidate_review_count"),
        },
        "samples": {
            "auto_merged_entities": auto_merged,
            "candidate_reviews": candidates,
            "rejected_candidates": rejected,
        },
    }


def _extract_relationship_reconciliation_matches(payload: dict[str, Any], terms: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"counts": {}, "samples": {}}

    def filter_rows(rows: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        if not isinstance(rows, list):
            return selected
        for row in rows:
            if not isinstance(row, dict):
                continue
            if any(_term_matches_terms(row.get(field), terms) for field in fields):
                selected.append(_limit_mapping(row, 10))
        return selected[:8]

    rewrites = filter_rows(payload.get("relationship_rewrites"), ("source_entity", "from_target", "to_target"))
    fact_adds = filter_rows(payload.get("fact_relationships_added"), ("source_entity", "target"))
    return {
        "counts": {
            "relationship_rewrite_count": payload.get("relationship_rewrite_count"),
            "fact_relationship_added_count": payload.get("fact_relationship_added_count"),
        },
        "samples": {
            "relationship_rewrites": rewrites,
            "fact_relationships_added": fact_adds,
        },
    }


def _cleanup_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    keys = (
        "input_entity_count",
        "output_entity_count",
        "primary_count",
        "review_count",
        "discarded_count",
        "alias_noise_rate",
        "descriptor_primary_rate",
        "named_primary_rate",
        "single_chapter_primary_rate",
        "review_to_primary_ratio",
    )
    return {key: payload.get(key) for key in keys if key in payload}


def _limit_mapping(value: Any, max_keys: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    limited: dict[str, Any] = {}
    for key in sorted(value.keys())[:max_keys]:
        item = value.get(key)
        if isinstance(item, list):
            limited[key] = item[:6]
        elif isinstance(item, dict):
            limited[key] = {nested_key: item[nested_key] for nested_key in sorted(item.keys())[:6]}
        else:
            limited[key] = item
    return limited


def _health_check_summary(check: dict[str, Any]) -> dict[str, Any]:
    name = str(check.get("name") or "")
    details = check.get("details") or {}
    summary_parts: list[str] = []
    for key in ("missing", "duplicates", "collisions", "suspicious", "errors", "warnings"):
        values = details.get(key)
        if isinstance(values, list) and values:
            summary_parts.append(f"{key}: {len(values)}")
    for key in ("count", "failed", "actual_chapter_count", "generated", "expected"):
        if key in details and isinstance(details.get(key), int):
            summary_parts.append(f"{key}: {details[key]}")
    entities = _collect_check_entities(details, check_name=name)
    chapters = _collect_check_chapters(details)
    targets = _collect_check_targets(details)
    artifacts = _collect_check_artifacts(details, check_name=name)
    review_terms = _collect_check_review_terms(details)
    message = _health_check_message(details)
    raw_context = _health_check_raw_context(details)
    return {
        "name": check.get("name"),
        "status": check.get("status"),
        "severity": _health_check_severity(check.get("status")),
        "summary": ", ".join(summary_parts) if summary_parts else "details available",
        "message": message,
        "affected_entities": entities,
        "affected_chapters": chapters,
        "affected_targets": targets,
        "related_artifacts": artifacts,
        "review_terms": review_terms,
        "raw_context": raw_context,
    }


def _health_check_severity(status: Any) -> str:
    value = str(status or "").casefold()
    if value == "fail":
        return "critical"
    if value == "warn":
        return "warning"
    if value == "pass":
        return "healthy"
    return "unknown"


def _health_check_message(details: dict[str, Any]) -> str | None:
    for key in ("recommended_review_action", "policy", "reason"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _health_check_raw_context(details: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "missing",
        "duplicates",
        "collisions",
        "suspicious",
        "unresolved",
        "findings",
        "errors",
        "warnings",
        "broken",
        "broken_count",
        "actual_chapter_count",
        "expected",
        "generated",
        "failed",
        "count",
        "unresolved_count",
        "finding_count",
        "path",
        "language",
    )
    return {key: details[key] for key in allowed if key in details}


def _collect_check_entities(details: dict[str, Any], *, check_name: str) -> list[str]:
    values: list[str] = []
    if check_name == "required_primaries_present":
        values.extend(_strings(details.get("missing")))
    values.extend(_collect_strings_from_objects(details.get("duplicates"), "canonical_names"))
    collisions = details.get("collisions") or []
    for collision in collisions if isinstance(collisions, list) else []:
        values.extend(_collect_strings_from_objects((collision or {}).get("entities"), "canonical_name"))
    values.extend(_collect_strings_from_objects(details.get("suspicious"), "canonical_name"))
    values.extend(_collect_strings_from_objects(details.get("unresolved"), "source"))
    values.extend(_collect_strings_from_objects(details.get("findings"), "canonical_name"))
    values.extend(_collect_strings_from_objects(details.get("errors"), "canonical_name"))
    values.extend(_collect_strings_from_objects(details.get("warnings"), "canonical_name"))
    return _dedupe_strings(values)


def _collect_check_chapters(details: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_collect_strings_from_objects(details.get("findings"), "chapter_id"))
    values.extend(_collect_strings_from_objects(details.get("errors"), "chapter_id"))
    values.extend(_collect_strings_from_objects(details.get("warnings"), "chapter_id"))
    return _dedupe_strings(values)


def _collect_check_targets(details: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_collect_strings_from_objects(details.get("unresolved"), "target"))
    values.extend(_collect_strings_from_objects(details.get("broken"), "target"))
    values.extend(_collect_strings_from_objects(details.get("findings"), "target"))
    return _dedupe_strings(values)


def _collect_check_artifacts(details: dict[str, Any], *, check_name: str) -> list[str]:
    values: list[str] = []
    path = details.get("path")
    if isinstance(path, str) and path.strip():
        values.append(Path(path).name)
    if check_name == "required_phase1_artifacts_exist":
        values.extend(_strings(details.get("missing")))
    values.extend(_collect_strings_from_objects(details.get("broken"), "path"))
    values.extend(_collect_strings_from_objects(details.get("suspicious_paths"),))
    return _dedupe_strings(values)


def _collect_check_review_terms(details: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_collect_strings_from_objects(details.get("unresolved"), "source"))
    values.extend(_collect_strings_from_objects(details.get("unresolved"), "target"))
    values.extend(_collect_strings_from_objects(details.get("findings"), "canonical_name"))
    values.extend(_collect_strings_from_objects(details.get("findings"), "mention"))
    values.extend(_collect_strings_from_objects(details.get("duplicates"), "preferred_slug"))
    return _dedupe_strings(values)


def _collect_strings_from_objects(values: Any, *path: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    out: list[str] = []
    for item in values:
        current = item
        if path:
            for key in path:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    current = None
                    break
        if isinstance(current, list):
            out.extend(_strings(current))
        elif isinstance(current, dict):
            out.extend(_strings(current.get("canonical_name")))
        else:
            out.extend(_strings(current))
    return out


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out[:12]


def _overall_health_status(
    *,
    semantic_invariants: dict[str, Any],
    review_pressure: dict[str, Any],
    relationship_integrity: dict[str, Any],
    materialization_integrity: dict[str, Any],
) -> str:
    if semantic_invariants.get("passed") is False or (semantic_invariants.get("failure_count") or 0) > 0:
        return "critical"
    if (
        (semantic_invariants.get("warning_count") or 0) > 0
        or (review_pressure.get("high_severity_items") or 0) > 0
        or (relationship_integrity.get("unresolved_relationship_targets") or 0) > 0
        or (materialization_integrity.get("missing_expected_artifacts_count") or 0) > 0
    ):
        return "warning"
    return "healthy"


def _health_highlights(
    *,
    canon_stability: dict[str, Any],
    relationship_integrity: dict[str, Any],
    review_pressure: dict[str, Any],
    materialization_integrity: dict[str, Any],
    semantic_invariants: dict[str, Any],
) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    if (semantic_invariants.get("failure_count") or 0) > 0:
        highlights.append({"level": "critical", "message": f"{semantic_invariants['failure_count']} invariant failures"})
    elif (semantic_invariants.get("warning_count") or 0) > 0:
        highlights.append({"level": "warning", "message": f"{semantic_invariants['warning_count']} invariant warnings"})
    if (review_pressure.get("high_severity_items") or 0) > 0:
        highlights.append({"level": "warning", "message": f"{review_pressure['high_severity_items']} high-severity review items"})
    if (relationship_integrity.get("unresolved_relationship_targets") or 0) > 0:
        highlights.append(
            {
                "level": "warning",
                "message": f"{relationship_integrity['unresolved_relationship_targets']} unresolved relationship targets",
            }
        )
    if (materialization_integrity.get("missing_expected_artifacts_count") or 0) > 0:
        highlights.append(
            {
                "level": "warning",
                "message": f"{materialization_integrity['missing_expected_artifacts_count']} expected artifacts missing",
            }
        )
    if (canon_stability.get("canonical_collision_count") or 0) > 0:
        highlights.append(
            {
                "level": "warning",
                "message": f"{canon_stability['canonical_collision_count']} canonical collision signals",
            }
        )
    return highlights[:6]
