from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

KIND_FOLDERS = {
    'character': 'Characters',
    'place': 'Places',
    'event': 'Events',
    'object': 'Objects',
    'concept': 'Concepts',
    'chapter': 'Chapters',
    'review': 'Reviews',
}
REQUIRED_FOLDERS = ['Characters', 'Places', 'Events', 'Objects', 'Concepts', 'Chapters', 'Reviews', 'System']

KIND_PREFERENCE = {
    'character': 0,
    'place': 1,
    'object': 2,
    'event': 3,
    'concept': 4,
    'chapter': 5,
    'review': 6,
}


@dataclass(frozen=True)
class MaterializedNote:
    vaerl_id: str
    kind: str
    canonical_label: str
    path: str
    title: str
    tags: list[str]
    aliases: list[str]
    status: str
    review_state: str
    chapter_ids: list[str]
    source_refs: list[dict[str, Any]]
    wikilinks: list[str]

@dataclass(frozen=True)
class EntityNoteSpec:
    entity: Mapping[str, Any]
    kind: str
    label: str
    note_path: str


def materialize_vaerl_markdown(
    vaerl: Mapping[str, Any],
    output_root: Path,
    *,
    write_files: bool = True,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    notes: list[MaterializedNote] = []
    used_paths: Counter[str] = Counter()
    entities = [item for item in _as_list(vaerl.get('entities') or vaerl.get('nodes')) if isinstance(item, Mapping)]
    chapters = [item for item in _as_list(vaerl.get('chapters')) if isinstance(item, Mapping)]
    reviews = [item for item in _as_list(vaerl.get('reviews') or vaerl.get('review_items')) if isinstance(item, Mapping)]

    if write_files:
        for folder in REQUIRED_FOLDERS:
            _safe_join(output_root, folder).mkdir(parents=True, exist_ok=True)

    entity_specs: list[EntityNoteSpec] = []
    for entity in entities:
        kind = _normalize_kind(entity.get('kind') or entity.get('entity_kind'))
        label = _pick_label(entity)
        entity_specs.append(
            EntityNoteSpec(
                entity=entity,
                kind=kind,
                label=label,
                note_path=_note_path(kind, label, used_paths),
            )
        )

    label_to_path = _build_label_to_path(entity_specs)

    for spec in entity_specs:
        notes.append(_materialize_entity(spec, label_to_path=label_to_path))
    for chapter in chapters:
        notes.append(_materialize_chapter(chapter, label_to_path=label_to_path, used_paths=used_paths))
    if reviews:
        notes.append(_materialize_review_index(reviews, label_to_path=label_to_path))

    if write_files:
        for note in notes:
            path = _safe_join(output_root, note.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_note(note, vaerl), encoding='utf-8')
        manifest_path = _safe_join(output_root, 'System/materialization_manifest.json')
        manifest_path.write_text(json.dumps(_manifest(notes, output_root), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    return _manifest(notes, output_root)


def _materialize_entity(spec: EntityNoteSpec, *, label_to_path: Mapping[str, str]) -> MaterializedNote:
    entity = spec.entity
    kind = spec.kind
    label = spec.label
    note_path = spec.note_path
    relationships = [item for item in _as_list(entity.get('relationships')) if isinstance(item, Mapping)]
    wikilinks: list[str] = []
    for rel in relationships:
        target = str(rel.get('target_label') or rel.get('target') or rel.get('to') or '').strip()
        if target:
            wikilinks.append(_wikilink(target, label_to_path))
    tags = _tags(entity.get('tags'), kind, entity.get('status') or entity.get('review_state') or 'ready')
    return MaterializedNote(
        vaerl_id=str(entity.get('id') or f'{kind}:{_slug(label)}'),
        kind=kind,
        canonical_label=label,
        path=note_path,
        title=label,
        tags=tags,
        aliases=_string_list(entity.get('aliases')),
        status=str(entity.get('status') or 'ready'),
        review_state=str(entity.get('review_state') or entity.get('status') or 'ready'),
        chapter_ids=_string_list(entity.get('chapter_ids') or entity.get('chapters')),
        source_refs=_source_refs(entity.get('source_refs')),
        wikilinks=_dedupe(wikilinks),
    )

def _build_label_to_path(entity_specs: Sequence[EntityNoteSpec]) -> dict[str, str]:
    candidates: dict[str, list[tuple[tuple[int, int, int, int, str], str]]] = {}
    for spec in entity_specs:
        entity = spec.entity
        rel_count = len([item for item in _as_list(entity.get('relationships')) if isinstance(item, Mapping)])
        fact_count = len(_string_list(entity.get('facts') or entity.get('key_facts')))
        character_signals = _character_signal_score(entity, spec.kind)
        priority = KIND_PREFERENCE.get(spec.kind, 99)
        score = (priority, -character_signals, -rel_count, -fact_count, spec.note_path)
        for label_value in [spec.label, *_string_list(entity.get('aliases')), *_string_list(entity.get('surface_forms'))]:
            if not label_value:
                continue
            key = _link_key(label_value)
            candidates.setdefault(key, []).append((score, spec.note_path))
    label_to_path: dict[str, str] = {}
    for key, rows in candidates.items():
        rows.sort(key=lambda row: row[0])
        label_to_path[key] = rows[0][1]
    return label_to_path

def _character_signal_score(entity: Mapping[str, Any], kind: str) -> int:
    score = 0
    if kind == 'character':
        score += 4
    label = _pick_label(entity).casefold()
    if any(token in label for token in ('san', 'abuelo', 'narrador', 'princesa', 'hija', 'hijo')):
        score += 1
    rels = [item for item in _as_list(entity.get('relationships')) if isinstance(item, Mapping)]
    if rels:
        score += 1
    rel_text = ' '.join(str(item.get('type') or item.get('relation_type') or '') for item in rels).casefold()
    if any(token in rel_text for token in ('guardian', 'daughter', 'grand', 'abuelo', 'narrador', 'protagon')):
        score += 1
    if _string_list(entity.get('aliases')):
        score += 1
    return score


def _materialize_chapter(chapter: Mapping[str, Any], *, label_to_path: Mapping[str, str], used_paths: Counter[str]) -> MaterializedNote:
    chapter_id = str(chapter.get('chapter_id') or chapter.get('id') or 'chapter').strip()
    label = str(chapter.get('title') or chapter.get('chapter_title_canonical') or chapter_id).strip()
    path = _dedupe_path(f"Chapters/{_safe_filename(chapter_id)}.md", used_paths)
    wikilinks = [_wikilink(value, label_to_path) for value in _string_list(chapter.get('entity_mentions') or chapter.get('linked_entities'))]
    return MaterializedNote(
        vaerl_id=str(chapter.get('vaerl_id') or f'chapter:{chapter_id}'),
        kind='chapter',
        canonical_label=label,
        path=path,
        title=label,
        tags=_tags(chapter.get('tags'), 'chapter', chapter.get('status') or 'ready'),
        aliases=[],
        status=str(chapter.get('status') or 'ready'),
        review_state=str(chapter.get('review_state') or chapter.get('status') or 'ready'),
        chapter_ids=[chapter_id],
        source_refs=_source_refs(chapter.get('source_refs')),
        wikilinks=_dedupe(wikilinks),
    )


def _materialize_review_index(reviews: Sequence[Mapping[str, Any]], *, label_to_path: Mapping[str, str]) -> MaterializedNote:
    wikilinks = []
    for review in reviews:
        target = str(review.get('target_label') or review.get('target') or '').strip()
        if target:
            wikilinks.append(_wikilink(target, label_to_path))
    return MaterializedNote(
        vaerl_id='review:index',
        kind='review',
        canonical_label='Pending Reviews',
        path='Reviews/pending.md',
        title='Pending Reviews',
        tags=['review', 'needs_review'],
        aliases=[],
        status='needs_review',
        review_state='needs_review',
        chapter_ids=[],
        source_refs=[],
        wikilinks=_dedupe(wikilinks),
    )


def _render_note(note: MaterializedNote, vaerl: Mapping[str, Any]) -> str:
    frontmatter = {
        'vaerl_id': note.vaerl_id,
        'kind': note.kind,
        'canonical_label': note.canonical_label,
        'aliases': note.aliases,
        'tags': note.tags,
        'status': note.status,
        'review_state': note.review_state,
        'chapter_ids': note.chapter_ids,
        'source_refs': note.source_refs,
    }
    lines = ['---', *_yaml_lines(frontmatter), '---', '', f'# {note.title}', '']
    source = _find_source(vaerl, note.vaerl_id)
    summary = str((source or {}).get('summary') or '')
    facts = _string_list((source or {}).get('facts'))
    relationships = [item for item in _as_list((source or {}).get('relationships')) if isinstance(item, Mapping)]
    evidence_refs = _source_refs((source or {}).get('evidence_refs') or (source or {}).get('evidence'))
    if summary:
        lines += ['## Summary', '', summary, '']
    if facts:
        lines += ['## Facts', '', *[f'- {fact}' for fact in facts], '']
    if relationships:
        lines += ['## Relationships', '']
        for rel in relationships:
            target = str(rel.get('target_label') or rel.get('target') or rel.get('to') or '').strip()
            label = str(rel.get('label') or rel.get('relation_label') or rel.get('type') or 'related_to')
            link = next((item for item in note.wikilinks if _link_key(target) in _link_key(item)), _wikilink(target, {})) if target else ''
            lines.append(f'- {label}: {link}'.rstrip())
        lines.append('')
    if note.source_refs or evidence_refs:
        lines += ['## Evidence', '']
        for ref in [*note.source_refs, *evidence_refs]:
            lines.append(f"- {ref.get('chapter_id') or ref.get('chapter') or 'source'}:{ref.get('span_id') or ref.get('chunk_id') or ref.get('pointer') or 'ref'}")
        lines.append('')
    if note.wikilinks:
        lines += ['## Links', '', *[f'- {link}' for link in note.wikilinks], '']
    lines += ['## Review Notes', '', '<!-- Author notes here. Changes create VaERL patch proposals; they do not silently change canon. -->', '']
    return '\n'.join(lines)


def _manifest(notes: Sequence[MaterializedNote], output_root: Path) -> dict[str, Any]:
    return {
        'schema_version': 'textifai.vaerl_markdown_manifest.v1',
        'output_root': str(output_root),
        'folders': REQUIRED_FOLDERS,
        'notes': [note.__dict__ for note in notes],
        'note_count': len(notes),
        'editable_policy': 'Markdown edits create VaERL patch proposals; VaERL remains source of truth until author confirmation.',
    }


def _find_source(vaerl: Mapping[str, Any], vaerl_id: str) -> Mapping[str, Any] | None:
    for collection in ('entities', 'nodes', 'chapters', 'reviews', 'review_items'):
        for item in _as_list(vaerl.get(collection)):
            if isinstance(item, Mapping) and str(item.get('id') or item.get('vaerl_id') or f"chapter:{item.get('chapter_id') or ''}") == vaerl_id:
                return item
    return None


def _note_path(kind: str, label: str, used_paths: Counter[str]) -> str:
    folder = KIND_FOLDERS.get(kind, 'Concepts')
    return _dedupe_path(f'{folder}/{_safe_filename(label)}.md', used_paths)


def _dedupe_path(path: str, used_paths: Counter[str]) -> str:
    used_paths[path] += 1
    if used_paths[path] == 1:
        return path
    stem, suffix = path.rsplit('.', 1)
    return f'{stem}_{used_paths[path]}.{suffix}'


def _safe_join(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError('Path escapes materialization root')
    return candidate


def _pick_label(item: Mapping[str, Any]) -> str:
    for key in ('canonical_label', 'canonical_name', 'canonical', 'label', 'title', 'name'):
        value = str(item.get(key) or '').strip()
        if value:
            return value
    return 'Untitled'


def _normalize_kind(value: Any) -> str:
    kind = str(value or 'concept').strip().casefold()
    return kind if kind in KIND_FOLDERS else 'concept'


def _wikilink(label: str, label_to_path: Mapping[str, str]) -> str:
    target = label_to_path.get(_link_key(label)) or label
    return f'[[{target.removesuffix(".md")}]]'


def _safe_filename(value: str) -> str:
    return _slug(value).replace('_', ' ').title().replace(' ', '_') or 'Untitled'


def _slug(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or 'untitled')).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[-\s]+', '_', text).strip('_')
    return text or 'untitled'


def _link_key(value: str) -> str:
    return re.sub(r'[^\w]+', '', str(value or '').casefold())


def _tags(values: Any, *extra: Any) -> list[str]:
    tags = []
    for item in [*_as_list(values), *extra]:
        text = str(item or '').strip().replace(' ', '_').casefold()
        if text:
            tags.append(text.removeprefix('#'))
    return sorted(set(tags))


def _source_refs(value: Any) -> list[dict[str, Any]]:
    refs = []
    for item in _as_list(value):
        if isinstance(item, Mapping):
            refs.append({k: item.get(k) for k in ('source_id', 'chapter_id', 'chunk_id', 'span_id', 'char_start', 'char_end', 'pointer') if item.get(k) is not None})
    return refs


def _yaml_lines(value: Mapping[str, Any]) -> list[str]:
    lines = []
    for key, item in value.items():
        if isinstance(item, list):
            lines.append(f'{key}:')
            if not item:
                lines.append('  []')
            for entry in item:
                if isinstance(entry, Mapping):
                    lines.append('  - ' + json.dumps(dict(entry), ensure_ascii=False))
                else:
                    lines.append(f'  - {json.dumps(entry, ensure_ascii=False)}')
        else:
            lines.append(f'{key}: {json.dumps(item, ensure_ascii=False)}')
    return lines


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item or '').strip()]


def _dedupe(values: Sequence[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
