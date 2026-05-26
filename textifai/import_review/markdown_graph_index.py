from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")


def build_markdown_graph_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    notes = []
    path_by_stem: dict[str, str] = {}
    for path in sorted(root.rglob('*.md')):
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
        'notes': indexed_notes,
        'nodes': nodes,
        'edges': edges,
        'orphan_notes': [note['path'] for note in indexed_notes if note['degree'] == 0],
        'unresolved_links': unresolved,
        'tags': sorted({tag for note in indexed_notes for tag in note['tags']}),
        'note_count': len(indexed_notes),
        'edge_count': len(edges),
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
