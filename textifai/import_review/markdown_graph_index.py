from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")

CANONICAL_KIND_PRIORITY = {
    "character": 10,
    "place": 9,
    "object": 8,
    "event": 7,
    "concept": 6,
    "chapter": 5,
    "review": 4,
    "note": 3,
    "unknown": 2,
    "unresolved": 1
}

_EXCLUDED_PATH_PARTS = {

    "dev",
    "runs",
    "99_system",
    ".textifai_runs",
    "provider_outputs",
    "viewer_project",
    "markdown_vault",
}


def build_markdown_graph_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    scan_root = _resolve_markdown_scan_root(root)
    notes = []
    path_by_stem: dict[str, str] = {}
    for path in sorted(scan_root.rglob('*.md')):
        if _is_excluded_markdown_path(path, scan_root):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        frontmatter, body = _split_frontmatter(text)
        title = _title_from_body(body) or Path(rel).stem
        links = _extract_wikilinks(text)
        tags = sorted(set(_as_string_list(frontmatter.get('tags')) + TAG_RE.findall(body)))
        note = {
            'path': rel,
            'title': title,
            'frontmatter': frontmatter,
            'tags': tags,
            'outgoing_wikilinks': links,
        }
        notes.append(note)
        path_by_stem[_key(rel.removesuffix('.md'))] = rel
        path_by_stem[_key(Path(rel).stem)] = rel
        if frontmatter.get('canonical_label'):
            path_by_stem[_key(str(frontmatter['canonical_label']))] = rel

    backlinks: dict[str, list[str]] = defaultdict(list)
    unresolved: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    for note in notes:
        for link in note['outgoing_wikilinks']:
            target = _resolve_link(link['target'], path_by_stem)
            if target:
                backlinks[target].append(note['path'])
                edges.append({'source': note['path'], 'target': target, 'label': link.get('label') or 'wikilink'})
            else:
                unresolved.append({'source': note['path'], 'target': link['target']})

    degree = Counter()
    for edge in edges:
        degree[edge['source']] += 1
        degree[edge['target']] += 1
    indexed_notes = []
    for note in notes:
        incoming = sorted(set(backlinks.get(note['path'], [])))
        indexed_notes.append({**note, 'backlinks': incoming, 'degree': degree[note['path']]})
    nodes = [
        {
            'id': note['path'],
            'label': note['title'],
            'kind': str(note['frontmatter'].get('kind') or 'note'),
            'tags': note['tags'],
            'degree': note['degree'],
            'size': 1 + note['degree'],
        }
        for note in indexed_notes
    ]
    return {
        'schema_version': 'textifai.markdown_graph_index.v1',
        'root': str(root),
        'scan_root': str(scan_root),
        'notes': indexed_notes,
        'nodes': nodes,
        'edges': edges,
        'orphan_notes': [note['path'] for note in indexed_notes if note['degree'] == 0],
        'unresolved_links': unresolved,
        'tags': sorted({tag for note in indexed_notes for tag in note['tags']}),
        'note_count': len(indexed_notes),
        'edge_count': len(edges),
    }


def build_author_graph(
    *,
    markdown_index: Mapping[str, Any],
    review_queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    notes = [row for row in markdown_index.get('notes', []) if isinstance(row, Mapping)]
    raw_nodes = [row for row in markdown_index.get('nodes', []) if isinstance(row, Mapping)]
    raw_edges = [row for row in markdown_index.get('edges', []) if isinstance(row, Mapping)]
    notes_by_path = {str(row.get('path') or ''): row for row in notes}

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    excluded = {
        'internal_candidates': 0,
        'pronouns': 0,
        'dev_nodes': 0,
        'duplicate_alias_nodes': 0,
    }

    for node in raw_nodes:
        node_id = str(node.get('id') or '')
        note = notes_by_path.get(node_id, {})
        frontmatter = note.get('frontmatter') if isinstance(note.get('frontmatter'), Mapping) else {}
        kind = str(node.get('kind') or frontmatter.get('kind') or 'note').lower()
        label = str(frontmatter.get('canonical_label') or node.get('label') or '').strip()
        path_text = str(node_id).lower()
        label_key = _key(label)

        if '/dev/' in path_text or '/runs/' in path_text or '/99_system/' in path_text:
            excluded['dev_nodes'] += 1
            continue
        if 'reviewlocal_candidate' in path_text or 'local_candidate' in path_text:
            excluded['internal_candidates'] += 1
            continue
        if kind == 'review' or str(frontmatter.get('review_state') or '').lower() == 'needs_review':
            excluded['internal_candidates'] += 1
            continue
        if label_key in {'yo', 'ella', 'el', 'él', 'la', 'tu', 'tú', 'nosotros', 'vosotros', 'ellos', 'ellas'}:
            excluded['pronouns'] += 1
            continue
        if not label:
            continue
        grouped[label_key].append(node)

    canonical_nodes: list[dict[str, Any]] = []
    node_redirect: dict[str, str] = {}
    for key, entries in grouped.items():
        entries_sorted = sorted(
            entries,
            key=lambda row: (
                -CANONICAL_KIND_PRIORITY.get(str(row.get('kind') or '').lower(), 0),
                str(row.get('id') or '').count('/'),
                -int(row.get('degree') or 0),
            ),
        )
        canonical = entries_sorted[0]
        canonical_id = str(canonical.get('id') or '')
        note = notes_by_path.get(canonical_id, {})
        frontmatter = note.get('frontmatter') if isinstance(note.get('frontmatter'), Mapping) else {}
        label = str(frontmatter.get('canonical_label') or canonical.get('label') or canonical_id)
        aliases = []
        for row in entries_sorted[1:]:
            excluded['duplicate_alias_nodes'] += 1
            alias_note = notes_by_path.get(str(row.get('id') or ''), {})
            alias_frontmatter = alias_note.get('frontmatter') if isinstance(alias_note.get('frontmatter'), Mapping) else {}
            alias_label = str(alias_frontmatter.get('canonical_label') or row.get('label') or '').strip()
            if alias_label and alias_label.casefold() != label.casefold():
                aliases.append(alias_label)
            node_redirect[str(row.get('id') or '')] = canonical_id
        node_redirect[canonical_id] = canonical_id
        canonical_nodes.append(
            {
                'id': canonical_id,
                'canonical_id': key,
                'label': label,
                'kind': str(canonical.get('kind') or 'note').lower(),
                'status': str(frontmatter.get('status') or frontmatter.get('review_state') or 'ready'),
                'summary': str(frontmatter.get('summary') or ''),
                'aliases': sorted(set(aliases)),
                'note_path': canonical_id,
                'degree': int(canonical.get('degree') or 0),
                'review_count': 0,
                'evidence_count': 0,
                'tags': canonical.get('tags') or [],
            }
        )

    allowed_ids = {row['id'] for row in canonical_nodes}
    author_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for edge in raw_edges:
        source_raw = str(edge.get('source') or '')
        target_raw = str(edge.get('target') or '')
        source = node_redirect.get(source_raw, source_raw)
        target = node_redirect.get(target_raw, target_raw)
        label = str(edge.get('label') or edge.get('type') or 'wikilink')
        if source not in allowed_ids or target not in allowed_ids:
            continue
        fingerprint = (source, target, label)
        if fingerprint in seen_edges:
            continue
        seen_edges.add(fingerprint)
        author_edges.append(
            {
                'source': source,
                'target': target,
                'relation_label': label,
                'kind': label,
                'evidence_count': 0,
                'review_state': 'ready',
                'chapters': [],
            }
        )

    decision_items = [row for row in ((review_queue or {}).get('decision_items') or []) if isinstance(row, Mapping)]
    return {
        'schema': 'textifai.author_graph',
        'schema_version': 1,
        'source': 'canonical_projection',
        'nodes': canonical_nodes,
        'edges': author_edges,
        'excluded': excluded,
        'stats': {
            'node_count': len(canonical_nodes),
            'edge_count': len(author_edges),
            'review_decision_count': len(decision_items),
            'raw_node_count': len(raw_nodes),
            'raw_edge_count': len(raw_edges),
        },
    }


def local_graph(index: Mapping[str, Any], note_path: str, *, depth: int = 1) -> dict[str, Any]:
    max_depth = max(1, int(depth))
    edges = [edge for edge in index.get('edges', []) if isinstance(edge, Mapping)]
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge.get('source') or '')
        target = str(edge.get('target') or '')
        adjacency[source].add(target)
        adjacency[target].add(source)
    seen = {note_path}
    frontier = {note_path}
    for _ in range(max_depth):
        next_frontier = set()
        for node in frontier:
            for neighbor in adjacency.get(node, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
    nodes = [node for node in index.get('nodes', []) if node.get('id') in seen]
    local_edges = [edge for edge in edges if edge.get('source') in seen and edge.get('target') in seen]
    return {'center': note_path, 'nodes': nodes, 'edges': local_edges, 'depth': max_depth}


def _extract_wikilinks(text: str) -> list[dict[str, str]]:
    links = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        label = (match.group(2) or target).strip()
        if target:
            links.append({'target': target, 'label': label})
    return links


def _resolve_link(target: str, path_by_stem: Mapping[str, str]) -> str | None:
    key = _key(target.removesuffix('.md'))
    if key in path_by_stem:
        return path_by_stem[key]
    key_file = _key(Path(target).stem)
    return path_by_stem.get(key_file)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith('---\n'):
        return {}, text
    try:
        _, raw, body = text.split('---\n', 2)
    except ValueError:
        return {}, text
    return _parse_simple_yaml(raw), body


def _parse_simple_yaml(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith('  - ') and current_key:
            value = line[4:].strip()
            if value == '[]':
                continue
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = value.strip('"')
            data.setdefault(current_key, []).append(parsed)
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            current_key = key.strip()
            value = value.strip()
            if value == '':
                data[current_key] = []
            else:
                try:
                    data[current_key] = json.loads(value)
                except json.JSONDecodeError:
                    data[current_key] = value.strip('"')
    return data


def _title_from_body(body: str) -> str:
    for line in body.splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return ''


def _key(value: str) -> str:
    return re.sub(r'[^\w]+', '', value.casefold())


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().removeprefix('#') for item in value if str(item).strip()]
    return [str(value).strip().removeprefix('#')]


def _resolve_markdown_scan_root(root: Path) -> Path:
    markdown_root = root / 'markdown'
    if markdown_root.exists() and markdown_root.is_dir():
        return markdown_root
    return root


def _is_excluded_markdown_path(path: Path, scan_root: Path) -> bool:
    try:
        parts = [part.casefold() for part in path.relative_to(scan_root).parts]
    except Exception:
        parts = [part.casefold() for part in path.parts]
    for part in parts:
        if part.startswith('.'):
            return True
        if part in _EXCLUDED_PATH_PARTS:
            return True
    joined = '/'.join(parts)
    if 'provider_outputs' in joined or 'reviewlocal_candidate' in joined:
        return True
    return False
