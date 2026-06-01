from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name('schema.sql')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def extract_first_h1(markdown: str) -> str | None:
    for line in StringIO(markdown).read().splitlines():
        if line.startswith('# '):
            return line[2:].strip() or None
    return None


def _split_frontmatter(markdown: str) -> tuple[str, str]:
    if markdown.startswith('---\n'):
        closing = markdown.find('\n---\n', 4)
        if closing != -1:
            return markdown[:closing + 5], markdown[closing + 5:]
    return '', markdown


def replace_or_insert_first_h1(markdown: str, new_title: str) -> str:
    frontmatter, body = _split_frontmatter(markdown)
    lines = body.splitlines(keepends=True)
    title_line = f'# {new_title.strip()}\n'
    for index, line in enumerate(lines):
        if line.startswith('# '):
            lines[index] = title_line
            return frontmatter + ''.join(lines)
    if lines and lines[0].startswith('\n'):
        return frontmatter + title_line + ''.join(lines)
    prefix = '\n' if body and not body.startswith('\n') else ''
    return frontmatter + title_line + prefix + body.lstrip('\n')


def normalize_chapter_title_for_manifest(title: str) -> str:
    return ' '.join(str(title or '').strip().split())


def normalize_entity_canonical_label(label: str) -> str:
    return ' '.join(str(label or '').strip().split())


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else None

def _resolve_entity_fiche_record(project_root: Path, conn: sqlite3.Connection, entity_id: str, canonical_label: str | None = None, note_path: str | None = None) -> dict[str, str] | None:
    row = conn.execute('select entity_id, canonical_name, ficha_markdown_path, summary from entities where entity_id = ?', (entity_id,)).fetchone()
    if row is not None:
        return {
            'entity_id': str(row['entity_id'] or entity_id),
            'canonical_name': str(row['canonical_name'] or canonical_label or entity_id),
            'ficha_markdown_path': str(row['ficha_markdown_path'] or '').strip(),
            'summary': str(row['summary'] or ''),
        }

    targets = [str(canonical_label or '').strip(), str(entity_id or '').strip(), str(note_path or '').strip()]
    markdown_root = project_root / 'markdown'
    for path in markdown_root.rglob('*.md'):
        rel_path = path.relative_to(project_root).as_posix()
        if '/Chapters/' in rel_path or rel_path.startswith('markdown/Chapters/'):
            continue
        if note_path and rel_path != note_path:
            continue
        text = path.read_text(encoding='utf-8')
        frontmatter, body = _split_frontmatter(text)
        canonical_name = normalize_entity_canonical_label(canonical_label or extract_first_h1(body) or path.stem or entity_id)
        frontmatter_entity_id = ''
        frontmatter_kind = ''
        if frontmatter:
            for line in frontmatter.splitlines():
                if line.startswith('entity_id:'):
                    frontmatter_entity_id = str(line.split(':', 1)[1]).strip()
                elif line.startswith('kind:'):
                    frontmatter_kind = str(line.split(':', 1)[1]).strip()
        normalized_candidates = {value.casefold() for value in [frontmatter_entity_id, canonical_name, path.stem] if value}
        if any(target and target.casefold() in normalized_candidates for target in targets):
            return {
                'entity_id': frontmatter_entity_id or entity_id,
                'canonical_name': canonical_name,
                'ficha_markdown_path': rel_path,
                'summary': '',
                'kind': frontmatter_kind,
            }
    return None


def open_project(project_path: Path) -> 'ProjectStore':
    return ProjectStore(project_path)


@dataclass
class ProjectStore:
    project_path: Path

    @property
    def project_root(self) -> Path:
        return self.project_path

    @property
    def live_root(self) -> Path:
        return self.project_path / '.textifai'

    @property
    def sqlite_path(self) -> Path:
        return self.live_root / 'db' / 'textifai.sqlite'

    def validate_project(self) -> None:
        if not (self.project_root / 'textifai.project.json').exists():
            raise FileNotFoundError('textifai.project.json')
        if not (self.project_root / 'chapters' / 'chapter_manifest.json').exists():
            raise FileNotFoundError('chapters/chapter_manifest.json')

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    def ensure_sqlite(self) -> Path:
        self.live_root.mkdir(parents=True, exist_ok=True)
        (self.live_root / 'db').mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))
            conn.execute(
                'insert or replace into settings(key, value, updated_at) values (?, ?, ?)',
                ('schema_version', '0', _now()),
            )
            conn.commit()
        return self.sqlite_path

    def _ensure_bootstrap_defaults(self) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        manifest = _read_json(self.project_root / 'textifai.project.json') or {}
        chapter_manifest = _read_json(self.project_root / 'chapters' / 'chapter_manifest.json') or {}
        chapters = chapter_manifest.get('chapters') if isinstance(chapter_manifest.get('chapters'), list) else []
        return manifest, chapter_manifest, chapters

    def bootstrap_from_project_files(self) -> None:
        manifest, _, chapters = self._ensure_bootstrap_defaults()
        self.ensure_sqlite()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('delete from project_meta')
            conn.execute('delete from files')
            conn.execute('delete from chapters')
            conn.execute('delete from dirty_states')

            conn.execute(
                'insert into project_meta(project_id, title, language, schema_version, created_at, updated_at) values (?, ?, ?, ?, ?, ?)',
                (
                    str(manifest.get('project_id') or self.project_root.name),
                    str(manifest.get('title') or self.project_root.name),
                    str(manifest.get('language') or ''),
                    int(manifest.get('schema_version') or 1),
                    str(manifest.get('created_at') or _now()),
                    str(manifest.get('updated_at') or _now()),
                ),
            )

            for chapter in chapters:
                if not isinstance(chapter, dict):
                    continue
                chapter_id = str(chapter.get('chapter_id') or '').strip()
                rel = str(chapter.get('markdown_path') or '').strip()
                if not chapter_id or not rel:
                    continue
                path = self.project_root / rel
                body = path.read_text(encoding='utf-8') if path.exists() else ''
                content_hash = _hash_text(body)
                order = int(chapter.get('order') or chapter.get('sequence_index') or 0)
                unit_type = str(chapter.get('unit_type') or '').strip() or None
                display_title = str(chapter.get('display_title') or chapter.get('title') or chapter_id)
                title = str(chapter.get('title') or display_title)
                char_count = int(chapter.get('char_count') or len(body) or 0)
                source_start = chapter.get('source_start')
                source_end = chapter.get('source_end')

                conn.execute(
                    'insert or replace into files(path, kind, checksum, char_count, last_seen_at) values (?, ?, ?, ?, ?)',
                    (rel, 'chapter_markdown', content_hash, int(char_count), _now()),
                )
                conn.execute(
                    'insert or replace into chapters(chapter_id, ordinal, unit_type, title, display_title, markdown_path, content_hash, char_count, source_start, source_end, status, dirty) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        chapter_id,
                        order,
                        unit_type,
                        title,
                        display_title,
                        rel,
                        content_hash,
                        int(char_count),
                        int(source_start) if isinstance(source_start, int) else None,
                        int(source_end) if isinstance(source_end, int) else None,
                        'ready',
                        0,
                    ),
                )
                conn.execute(
                    'insert or replace into dirty_states(resource_type, resource_id, dirty_reason, updated_at) values (?, ?, ?, ?)',
                    ('chapter', chapter_id, '', _now()),
                )
            conn.commit()

    def get_chapters(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('select * from chapters order by ordinal asc, chapter_id asc').fetchall()
        chapters = []
        for row in rows:
            path = self.project_root / row['markdown_path']
            markdown_path = str(row['markdown_path'])
            if path.exists():
                body = path.read_text(encoding='utf-8')
                content_hash = row['content_hash'] or _hash_text(body)
            else:
                body = ''
                content_hash = str(row['content_hash'] or '')
            dirty_state = self.get_dirty_state('chapter', row['chapter_id'])
            chapters.append(
                {
                    'chapter_id': row['chapter_id'],
                    'order': row['ordinal'],
                    'unit_type': row['unit_type'],
                    'title': row['title'],
                    'display_title': row['display_title'] or row['title'],
                    'path': markdown_path,
                    'markdown_path': markdown_path,
                    'content_hash': content_hash,
                    'char_count': row['char_count'],
                    'source_start': row['source_start'],
                    'source_end': row['source_end'],
                    'semantic_state': row['status'] or 'clean',
                    'source_used': 'project_store',
                    'dirty_state': bool(dirty_state['dirty']),
                }
            )
        return chapters

    def get_chapter(self, chapter_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('select * from chapters where chapter_id = ?', (chapter_id,)).fetchone()
        if row is None:
            raise KeyError(chapter_id)
        path = self.project_root / row['markdown_path']
        markdown = path.read_text(encoding='utf-8') if path.exists() else ''
        dirty_state = self.get_dirty_state('chapter', chapter_id)
        return {
            'chapter_id': row['chapter_id'],
            'order': row['ordinal'],
            'unit_type': row['unit_type'],
            'title': row['title'],
            'display_title': row['display_title'] or row['title'],
            'markdown_path': row['markdown_path'],
            'content_hash': row['content_hash'] or _hash_text(markdown),
            'char_count': row['char_count'],
            'source_start': row['source_start'],
            'source_end': row['source_end'],
            'semantic_state': row['status'] or 'clean',
            'dirty_state': bool(dirty_state['dirty']),
            'dirty_reason': dirty_state.get('reason'),
            'markdown': markdown,
        }

    def get_dirty_state(self, scope: str, object_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'select * from dirty_states where resource_type = ? and resource_id = ?',
                (scope, object_id),
            ).fetchone()
        if row is None:
            return {'dirty': False, 'reason': None}
        reason = row['dirty_reason'] if row['dirty_reason'] is not None else ''
        return {'dirty': bool(reason), 'reason': reason or None}

    def mark_dirty(self, scope: str, object_id: str, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'insert or replace into dirty_states(resource_type, resource_id, dirty_reason, updated_at) values (?, ?, ?, ?)',
                (scope, object_id, reason, _now()),
            )
            if scope == 'chapter':
                conn.execute(
                    'update chapters set dirty = 1, status = ? where chapter_id = ?',
                    ('dirty', object_id),
                )
            conn.commit()

    def update_chapter_manifest_snapshot(self, chapter_id: str, metadata: dict[str, Any]) -> bool:
        manifest_path = self.project_root / 'chapters' / 'chapter_manifest.json'
        payload = _read_json(manifest_path) or {}
        chapters = payload.get('chapters') if isinstance(payload.get('chapters'), list) else []
        updated = False
        for chapter in chapters:
            if not isinstance(chapter, dict) or str(chapter.get('chapter_id') or '') != chapter_id:
                continue
            chapter['title'] = metadata['title']
            chapter['display_title'] = metadata['display_title']
            chapter['clean_title'] = normalize_chapter_title_for_manifest(metadata['display_title'])
            chapter['content_hash'] = metadata['content_hash']
            chapter['char_count'] = metadata['char_count']
            chapter['updated_at'] = metadata['updated_at']
            chapter['semantic_state'] = metadata['semantic_state']
            chapter['status'] = metadata['semantic_state']
            updated = True
            break
        if updated:
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return updated

    def save_chapter_markdown(self, chapter_id: str, new_markdown: str, expected_hash: str, actor: str = 'local_user', display_title: str | None = None) -> dict[str, Any]:
        del actor
        now = _now()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('select * from chapters where chapter_id = ?', (chapter_id,)).fetchone()
            if row is None:
                raise KeyError(chapter_id)
            rel_path = str(row['markdown_path'] or '').strip()
            if not rel_path:
                raise ValueError('chapter markdown_path is empty')
            chapter_path = (self.project_root / rel_path).resolve()
            root = self.project_root.resolve()
            if root not in chapter_path.parents:
                raise ValueError('chapter markdown_path escapes project root')
            if not chapter_path.exists():
                raise FileNotFoundError(rel_path)
            current_markdown = chapter_path.read_text(encoding='utf-8')
            old_hash = _hash_text(current_markdown)
            if old_hash != expected_hash:
                return {
                    'ok': False,
                    'error': 'hash_mismatch',
                    'chapter_id': chapter_id,
                    'current_hash': old_hash,
                    'expected_hash': expected_hash,
                    'message': 'El capítulo cambió en disco. Recarga antes de guardar.',
                }

            resolved_title = normalize_chapter_title_for_manifest(display_title or extract_first_h1(new_markdown) or str(row['display_title'] or row['title'] or chapter_id))
            new_markdown = replace_or_insert_first_h1(new_markdown, resolved_title)

            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup_rel = Path('.textifai') / 'history' / 'chapters' / chapter_id / f'{stamp}_{old_hash[:12]}.md'
            backup_abs = self.project_root / backup_rel
            backup_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(chapter_path, backup_abs)

            chapter_path.write_text(new_markdown, encoding='utf-8')
            new_hash = _hash_text(new_markdown)
            char_count = len(new_markdown)
            conn.execute(
                'update files set checksum = ?, char_count = ?, last_seen_at = ? where path = ?',
                (new_hash, char_count, now, rel_path),
            )
            conn.execute(
                'update chapters set title = ?, display_title = ?, content_hash = ?, char_count = ?, status = ?, dirty = 1 where chapter_id = ?',
                (resolved_title, resolved_title, new_hash, char_count, 'needs_reanalysis', chapter_id),
            )
            conn.execute(
                'insert or replace into dirty_states(resource_type, resource_id, dirty_reason, updated_at) values (?, ?, ?, ?)',
                ('chapter', chapter_id, 'chapter_title_edited' if display_title else 'chapter_markdown_edited', now),
            )
            conn.commit()
        manifest_updated = self.update_chapter_manifest_snapshot(
            chapter_id,
            {
                'title': resolved_title,
                'display_title': resolved_title,
                'content_hash': new_hash,
                'char_count': char_count,
                'updated_at': now,
                'semantic_state': 'needs_reanalysis',
            },
        )
        return {
            'ok': True,
            'chapter_id': chapter_id,
            'old_hash': old_hash,
            'new_hash': new_hash,
            'display_title': resolved_title,
            'backup_path': str(backup_rel),
            'semantic_state': 'needs_reanalysis',
            'dirty_state': True,
            'manifest_updated': manifest_updated,
            'saved_at': now,
            'warning': 'VaERL, Graph y Review no han sido reanalizados todavía.',
            'message': 'Capítulo guardado. VaERL/Graph/Review pendientes de reanálisis.',
        }

    def save_entity_fiche_markdown(self, entity_id: str, new_markdown: str, expected_hash: str, actor: str = 'local_user', canonical_label: str | None = None, note_path: str | None = None) -> dict[str, Any]:
        del actor
        now = _now()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            record = _resolve_entity_fiche_record(self.project_root, conn, entity_id, canonical_label, note_path)
            if record is None:
                raise KeyError(entity_id)
            rel_path = str(record['ficha_markdown_path'] or '').strip()
            if not rel_path:
                raise ValueError('entity ficha_markdown_path is empty')
            fiche_path = (self.project_root / rel_path).resolve()
            root = self.project_root.resolve()
            if root not in fiche_path.parents:
                raise ValueError('entity ficha_markdown_path escapes project root')
            if not fiche_path.exists():
                raise FileNotFoundError(rel_path)

            current_markdown = fiche_path.read_text(encoding='utf-8')
            current_frontmatter, _ = _split_frontmatter(current_markdown)
            old_hash = _hash_text(current_markdown)
            if old_hash != expected_hash:
                return {
                    'ok': False,
                    'error': 'hash_mismatch',
                    'entity_id': entity_id,
                    'current_hash': old_hash,
                    'expected_hash': expected_hash,
                    'message': 'La ficha cambió en disco. Recarga antes de guardar.',
                }

            if new_markdown.startswith('---\n'):
                next_markdown = new_markdown
            elif current_frontmatter:
                sep = '' if current_frontmatter.endswith('\n') else '\n'
                next_markdown = f"{current_frontmatter}{sep}{new_markdown}"
            else:
                next_markdown = new_markdown

            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup_rel = Path('.textifai') / 'history' / 'entities' / entity_id / f'{stamp}_{old_hash[:12]}.md'
            backup_abs = self.project_root / backup_rel
            backup_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fiche_path, backup_abs)

            fiche_path.write_text(next_markdown, encoding='utf-8')
            new_hash = _hash_text(next_markdown)
            char_count = len(next_markdown)
            conn.execute(
                'insert or replace into files(path, kind, checksum, char_count, last_seen_at) values (?, ?, ?, ?, ?)',
                (rel_path, 'entity_fiche_markdown', new_hash, char_count, now),
            )
            conn.execute(
                'insert or replace into entities(entity_id, canonical_name, kind, ficha_markdown_path, summary) values (?, ?, ?, ?, ?)',
                (entity_id, str(record['canonical_name'] or canonical_label or entity_id), str(record.get('kind') or ''), rel_path, str(record['summary'] or '')),
            )
            conn.execute(
                'insert or replace into dirty_states(resource_type, resource_id, dirty_reason, updated_at) values (?, ?, ?, ?)',
                ('entity', entity_id, 'entity_fiche_markdown_edited', now),
            )
            conn.commit()

        return {
            'ok': True,
            'entity_id': entity_id,
            'canonical_label': str(record['canonical_name'] or canonical_label or entity_id),
            'old_hash': old_hash,
            'new_hash': new_hash,
            'backup_path': str(backup_rel),
            'semantic_state': 'needs_reanalysis',
            'dirty_state': True,
            'saved_at': now,
            'warning': 'VaERL, Graph y Review no han sido reanalizados todavía.',
            'message': 'Ficha guardada. VaERL/Graph/Review pendientes de reanálisis.',
        }

    def export_chapter_snapshot(self) -> dict[str, Any]:
        return {'chapters': self.get_chapters()}
