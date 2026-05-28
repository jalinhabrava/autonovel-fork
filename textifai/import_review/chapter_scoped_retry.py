from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChapterSubchunk:
    chapter_id: str
    subchunk_id: str
    local_index: int
    char_start: int
    char_end: int
    text_hash: str
    source_ref: dict[str, Any]


def build_chapter_subchunks(chapter_id: str, markdown_text: str, *, max_chunks: int = 3) -> list[dict[str, Any]]:
    text = str(markdown_text or '')
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    if not paragraphs:
        return []
    target_chunks = min(max_chunks, max(1, len(paragraphs) // 4 + (1 if len(paragraphs) % 4 else 0)))
    target_chunks = max(1, target_chunks)
    per_chunk = max(1, len(paragraphs) // target_chunks)
    chunks: list[dict[str, Any]] = []
    cursor = 0
    index = 0
    for chunk_no in range(target_chunks):
        start_i = index
        end_i = len(paragraphs) if chunk_no == target_chunks - 1 else min(len(paragraphs), start_i + per_chunk)
        selected = paragraphs[start_i:end_i]
        if not selected:
            continue
        joined = '\n\n'.join(selected)
        start_pos = text.find(selected[0], cursor)
        if start_pos < 0:
            start_pos = cursor
        end_pos = start_pos + len(joined)
        cursor = end_pos
        payload = ChapterSubchunk(
            chapter_id=chapter_id,
            subchunk_id=f'{chapter_id}_subchunk_{chunk_no+1:02d}',
            local_index=chunk_no,
            char_start=start_pos,
            char_end=end_pos,
            text_hash=hashlib.sha256(joined.encode('utf-8', errors='replace')).hexdigest(),
            source_ref={'chapter_id': chapter_id, 'char_start': start_pos, 'char_end': end_pos},
        )
        chunks.append(payload.__dict__)
        index = end_i
    return chunks


def first_chapter(parsed: dict[str, Any]) -> dict[str, Any] | None:
    chapters = parsed.get('chapters') if isinstance(parsed, dict) else None
    if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
        return chapters[0]
    return None


def build_chapter_vaerl_patch(parsed: dict[str, Any]) -> dict[str, Any]:
    chapter = first_chapter(parsed) or {}
    return {
        'schema': 'textifai.chapter_vaerl_patch',
        'schema_version': 1,
        'chapter_id': chapter.get('chapter_id'),
        'chapter_summary': chapter.get('chapter_summary'),
        'entities': {
            'characters': chapter.get('characters') or [],
            'places': chapter.get('places') or [],
            'concepts': chapter.get('concepts') or [],
            'objects': chapter.get('objects') or [],
            'events': chapter.get('events') or [],
        },
        'relationships': chapter.get('relations') or [],
        'unresolved_mentions': chapter.get('unresolved_mentions') or [],
    }


def build_chapter_graph_patch(vaerl_patch: dict[str, Any]) -> dict[str, Any]:
    chapter_id = vaerl_patch.get('chapter_id')
    nodes = [{'id': chapter_id, 'kind': 'chapter', 'label': chapter_id}]
    edges = []
    for kind, items in (vaerl_patch.get('entities') or {}).items():
        entity_kind = kind[:-1] if kind.endswith('s') else kind
        for item in items or []:
            canonical = item.get('canonical') or item.get('canonical_name') or item.get('surface')
            if not canonical:
                continue
            node_id = f'{entity_kind}:{canonical}'
            nodes.append({'id': node_id, 'kind': entity_kind, 'label': canonical})
            edges.append({'source': chapter_id, 'target': node_id, 'kind': 'mentions'})
    for rel in vaerl_patch.get('relationships') or []:
        src = rel.get('source') or rel.get('source_entity') or rel.get('from')
        tgt = rel.get('target') or rel.get('target_entity') or rel.get('to')
        if src and tgt:
            edges.append({'source': src, 'target': tgt, 'kind': rel.get('type') or rel.get('relation_type') or 'related'})
    return {
        'schema': 'textifai.chapter_graph_patch',
        'schema_version': 1,
        'chapter_id': chapter_id,
        'nodes': nodes,
        'edges': edges,
    }


def build_chapter_review_patch(vaerl_patch: dict[str, Any]) -> dict[str, Any]:
    unresolved = vaerl_patch.get('unresolved_mentions') or []
    items = []
    for item in unresolved:
        items.append({
            'chapter_id': vaerl_patch.get('chapter_id'),
            'severity': 'medium',
            'review_type': 'unresolved_mention',
            'source_entity': item.get('surface') or item.get('canonical') or 'unknown',
            'recommendation': 'Resolver mención ambigua antes de consolidar canon.',
        })
    return {
        'schema': 'textifai.chapter_review_patch',
        'schema_version': 1,
        'chapter_id': vaerl_patch.get('chapter_id'),
        'items': items,
    }


def build_chapter_retry_result(*, chapter_id: str, pre_retry_score: int | None, post_retry_score: int | None, subchunks: list[dict[str, Any]], vaerl_patch_path: str, graph_patch_path: str, review_patch_path: str, integration_report_path: str, integration_applied: bool, status: str) -> dict[str, Any]:
    return {
        'schema': 'textifai.chapter_retry_result',
        'schema_version': 1,
        'chapter_id': chapter_id,
        'status': status,
        'pre_retry_score': pre_retry_score,
        'post_retry_score': post_retry_score,
        'subchunks': subchunks,
        'vaerl_patch_path': vaerl_patch_path,
        'graph_patch_path': graph_patch_path,
        'review_patch_path': review_patch_path,
        'integration_report_path': integration_report_path,
        'integration_applied': integration_applied,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
