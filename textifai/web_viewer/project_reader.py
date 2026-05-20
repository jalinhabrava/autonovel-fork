from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textifai.obsidian.parser import extract_obsidian_links, parse_obsidian_frontmatter
from vault.schema import slugify


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


class ProjectCatalog:
    def __init__(self, roots: list[Path]):
        self.roots = [root.resolve() for root in roots]
        self._projects = self._discover()

    def list_projects(self) -> list[dict[str, Any]]:
        return [self._project_summary(project) for project in self._projects]

    def get_project(self, project_id: str) -> ProjectRef:
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
                projects[project.project_id] = project
        return sorted(projects.values(), key=lambda item: item.name.casefold())

    def _project_summary(self, project: ProjectRef) -> dict[str, Any]:
        system = project.system_root
        obsidian_import = _read_json(system / "obsidian_import.json") if system else None
        review_queue = _read_json(system / "review_queue.json") if system else None
        invariants = _read_json(system / "semantic_invariants_audit.json") if system else None
        entities = obsidian_import.get("entities") if isinstance(obsidian_import, dict) else []
        chapters = obsidian_import.get("chapters") if isinstance(obsidian_import, dict) else []
        primary_count = sum(1 for item in entities or [] if _is_primary(item))
        return {
            "project_id": project.project_id,
            "name": project.name,
            "kind": project.kind,
            "root": str(project.root),
            "system_root": str(system) if system else None,
            "mtime": project.root.stat().st_mtime if project.root.exists() else None,
            "work": obsidian_import.get("work") if isinstance(obsidian_import, dict) else {},
            "chapter_count": len(chapters or []),
            "entity_count": len(entities or []),
            "primary_count": primary_count,
            "review_count": max(len(entities or []) - primary_count, 0),
            "review_queue_count": review_queue.get("item_count") if isinstance(review_queue, dict) else None,
            "invariants_status": invariants.get("status") if isinstance(invariants, dict) else None,
        }


def read_project(project: ProjectRef) -> dict[str, Any]:
    canon = read_canon(project)
    artifacts = list_artifacts(project)
    graph = build_graph(project, canon=canon)
    return {
        "project": {
            "project_id": project.project_id,
            "name": project.name,
            "kind": project.kind,
            "root": str(project.root),
            "system_root": str(project.system_root) if project.system_root else None,
        },
        "notes": list_notes(project.root),
        "canon": canon,
        "artifacts": artifacts,
        "graph": graph,
        "health": build_semantic_health(project, canon=canon, artifacts=artifacts, graph=graph),
    }


def list_notes(root: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_obsidian_frontmatter(text)
        tags = _tags_from_frontmatter(frontmatter)
        notes.append(
            {
                "path": rel,
                "name": path.stem,
                "folder": path.parent.relative_to(root).as_posix() if path.parent != root else "",
                "frontmatter": frontmatter,
                "tags": tags,
                "role": _note_role(path, frontmatter),
                "mtime": path.stat().st_mtime,
            }
        )
    return notes


def read_note(project: ProjectRef, note_path: str) -> dict[str, Any]:
    path = _safe_child(project.root, note_path)
    if path.suffix != ".md" or not path.exists():
        raise FileNotFoundError(note_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": path.relative_to(project.root).as_posix(),
        "markdown": text,
        "frontmatter": parse_obsidian_frontmatter(text),
        "links": extract_obsidian_links(text),
    }


def read_canon(project: ProjectRef) -> dict[str, Any]:
    system = project.system_root
    obsidian_import = _read_json(system / "obsidian_import.json") if system else {}
    review_queue = _read_json(system / "review_queue.json") if system else {}
    entities = obsidian_import.get("entities") if isinstance(obsidian_import, dict) else []
    chapters = obsidian_import.get("chapters") if isinstance(obsidian_import, dict) else []
    return {
        "work": obsidian_import.get("work") if isinstance(obsidian_import, dict) else {},
        "chapters": chapters or [],
        "primaries": [item for item in entities or [] if _is_primary(item)],
        "review_entities": [item for item in entities or [] if not _is_primary(item)],
        "review_queue": review_queue if isinstance(review_queue, dict) else {},
    }


def list_artifacts(project: ProjectRef) -> list[dict[str, Any]]:
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
    system = path / "99_System"
    if system.exists() and ((system / "obsidian_import.json").exists() or (system / "review_queue.json").exists()):
        return ProjectRef(project_id=_project_id(path), name=path.name, root=path, system_root=system, kind="vault_or_run")
    if path.name == "99_System" and ((path / "obsidian_import.json").exists() or (path / "review_queue.json").exists()):
        root = path.parent
        return ProjectRef(project_id=_project_id(root), name=root.name, root=root, system_root=path, kind="system_run")
    return None


def _project_id(path: Path) -> str:
    return path.resolve().as_posix().replace("/", "__").strip("_")


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


def _health_check_summary(check: dict[str, Any]) -> dict[str, Any]:
    details = check.get("details") or {}
    summary_parts: list[str] = []
    for key in ("missing", "duplicates", "collisions", "suspicious", "errors", "warnings"):
        values = details.get(key)
        if isinstance(values, list) and values:
            summary_parts.append(f"{key}: {len(values)}")
    for key in ("count", "failed", "actual_chapter_count", "generated", "expected"):
        if key in details and isinstance(details.get(key), int):
            summary_parts.append(f"{key}: {details[key]}")
    return {
        "name": check.get("name"),
        "status": check.get("status"),
        "summary": ", ".join(summary_parts) if summary_parts else "details available",
    }


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
