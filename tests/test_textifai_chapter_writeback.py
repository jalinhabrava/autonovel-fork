from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from io import BytesIO

from textifai.project_store import open_project
from textifai.project_store.store import _hash_text
from textifai.web_viewer.server import _make_handler


EXPECTED = Path(__file__).resolve().parent / 'fixtures/textifai/chapter_writeback/expected'


class TextifaiChapterWritebackTests(unittest.TestCase):
    def test_save_method_exists_and_contract_reports_are_commit_safe(self):
        self.assertTrue(hasattr(open_project(Path('/tmp/example.textifai')), 'save_chapter_markdown'))
        names = [
            'projectstore_save_chapter_contract_after_sp115a.json',
            'chapter_backup_versioning_after_sp115a.json',
            'chapter_hash_conflict_after_sp115a.json',
            'editor_save_runtime_after_sp115a.json',
            'chapter_semantic_dirty_state_after_sp115a.json',
            'chapter_writeback_decision_after_sp115a.json',
            'chapter_title_writeback_contract_after_sp116.json',
            'chapter_heading_sync_after_sp116.json',
            'chapter_manifest_snapshot_update_after_sp116.json',
            'chapter_print_export_title_contract_after_sp116.json',
        ]
        for name in names:
            data = json.loads((EXPECTED / name).read_text(encoding='utf-8'))
            self.assertTrue(data['no_vaerl_writeback'])
            self.assertTrue(data['no_graph_regeneration'])
            self.assertTrue(data['no_review_regeneration'])
            self.assertTrue(data['no_source_prose'])
            self.assertNotIn('chapter_markdown', data)

    def test_correct_hash_writes_markdown_backup_and_dirty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            before = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            expected_hash = _hash_text(before)
            new_markdown = '---\ntitle: Uno\n---\n\nTexto nuevo con acento ñ y emoji 🌙\n'

            result = store.save_chapter_markdown('ch_001', new_markdown, expected_hash, actor='test')

            self.assertTrue(result['ok'])
            saved = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            self.assertIn('# Uno', saved)
            self.assertIn('Texto nuevo con acento ñ y emoji 🌙', saved)
            self.assertEqual(result['old_hash'], expected_hash)
            self.assertEqual(result['new_hash'], _hash_text(saved))
            self.assertEqual(result['semantic_state'], 'needs_reanalysis')
            self.assertTrue(result['dirty_state'])
            backup = project / result['backup_path']
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding='utf-8'), before)
            with sqlite3.connect(project / '.textifai/db/textifai.sqlite') as conn:
                chapter = conn.execute('select content_hash, char_count, status, dirty from chapters where chapter_id = ?', ('ch_001',)).fetchone()
                self.assertEqual(chapter, (_hash_text(saved), len(saved), 'needs_reanalysis', 1))
                dirty = conn.execute('select dirty_reason from dirty_states where resource_type = ? and resource_id = ?', ('chapter', 'ch_001')).fetchone()
                self.assertEqual(dirty[0], 'chapter_markdown_edited')

    def test_stale_expected_hash_returns_conflict_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            path = project / 'markdown/Chapters/Ch_001.md'
            before = path.read_text(encoding='utf-8')

            result = store.save_chapter_markdown('ch_001', 'changed', 'stale_hash')

            self.assertFalse(result['ok'])
            self.assertEqual(result['error'], 'hash_mismatch')
            self.assertEqual(result['current_hash'], _hash_text(before))
            self.assertEqual(path.read_text(encoding='utf-8'), before)

    def test_save_path_cannot_escape_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            with sqlite3.connect(project / '.textifai/db/textifai.sqlite') as conn:
                conn.execute('update chapters set markdown_path = ? where chapter_id = ?', ('../escape.md', 'ch_001'))
                conn.commit()

            with self.assertRaises(ValueError):
                store.save_chapter_markdown('ch_001', 'changed', 'anything')

    def test_vaerl_graph_review_artifacts_are_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            vaerl = project / 'artifacts/vaerl.json'
            graph = project / 'artifacts/graph.json'
            review = project / 'artifacts/review.json'
            for path in [vaerl, graph, review]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"unchanged": true}', encoding='utf-8')
            before = {path: path.stat().st_mtime_ns for path in [vaerl, graph, review]}
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            old = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')

            store.save_chapter_markdown('ch_001', old + '\nextra', _hash_text(old))

            after = {path: path.stat().st_mtime_ns for path in [vaerl, graph, review]}
            self.assertEqual(after, before)


    def test_http_save_endpoint_returns_json_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            captured: list[tuple[int, dict]] = []

            case = self

            class Catalog:
                def get_project(self, project_id: str):
                    case.assertEqual(project_id, 'fixture')
                    return type('Project', (), {'kind': 'textifai_project', 'root': project})()

            handler_cls = _make_handler(Catalog(), type('Registry', (), {})())
            handler = handler_cls.__new__(handler_cls)
            handler.path = f'/api/projects/fixture/chapters/ch_001/save'
            handler.headers = {'Content-Length': '0'}
            handler.rfile = BytesIO()
            handler._json_body = lambda: {'markdown': store.get_chapter('ch_001')['markdown'] + '\nHTTP save', 'expected_hash': store.get_chapter('ch_001')['content_hash']}
            handler._json = lambda payload, status=200: captured.append((status, payload))

            handler._handle_post()
            self.assertEqual(captured[0][0], 200)
            self.assertTrue(captured[0][1]['ok'])
            self.assertEqual(captured[0][1]['semantic_state'], 'needs_reanalysis')

            captured.clear()
            handler._json_body = lambda: {'markdown': 'stale', 'expected_hash': 'bad'}
            handler._handle_post()
            self.assertEqual(captured[0][0], 409)
            self.assertEqual(captured[0][1]['error'], 'hash_mismatch')

    def test_title_edit_updates_h1_sqlite_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            before = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            result = store.save_chapter_markdown('ch_001', before, _hash_text(before), display_title='Nuevo Título')
            self.assertTrue(result['ok'])
            text = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            self.assertIn('# Nuevo Título', text)
            self.assertTrue(result['manifest_updated'])
            with sqlite3.connect(project / '.textifai/db/textifai.sqlite') as conn:
                row = conn.execute('select title, display_title, status from chapters where chapter_id = ?', ('ch_001',)).fetchone()
                self.assertEqual(row, ('Nuevo Título', 'Nuevo Título', 'needs_reanalysis'))
            manifest = json.loads((project / 'chapters/chapter_manifest.json').read_text(encoding='utf-8'))
            entry = manifest['chapters'][0]
            self.assertEqual(entry['display_title'], 'Nuevo Título')
            self.assertEqual(entry['status'], 'needs_reanalysis')

    def test_insert_h1_after_frontmatter_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp), chapter='---\ntitle: Uno\n---\n\nSin heading inicial.\n')
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            before = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            store.save_chapter_markdown('ch_001', before, _hash_text(before), display_title='Título Insertado')
            text = (project / 'markdown/Chapters/Ch_001.md').read_text(encoding='utf-8')
            self.assertIn('---\ntitle: Uno\n---\n# Título Insertado\n', text)

    def test_conflict_does_not_write_markdown_or_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            md_path = project / 'markdown/Chapters/Ch_001.md'
            mf_path = project / 'chapters/chapter_manifest.json'
            before_md = md_path.read_text(encoding='utf-8')
            before_mf = mf_path.read_text(encoding='utf-8')
            result = store.save_chapter_markdown('ch_001', before_md, 'stale_hash', display_title='No Debe Guardar')
            self.assertFalse(result['ok'])
            self.assertEqual(md_path.read_text(encoding='utf-8'), before_md)
            self.assertEqual(mf_path.read_text(encoding='utf-8'), before_mf)

    def _make_project(self, parent: Path, chapter: str | None = None) -> Path:
        project = parent / 'fixture.textifai'
        (project / 'chapters').mkdir(parents=True)
        (project / 'markdown/Chapters').mkdir(parents=True)
        (project / 'textifai.project.json').write_text(json.dumps({'project_id': 'fixture', 'title': 'Fixture', 'language': 'es', 'schema_version': 1}), encoding='utf-8')
        markdown = chapter if chapter is not None else '---\ntitle: Uno\n---\n\n# Uno\n\nTexto inicial.\n'
        (project / 'markdown/Chapters/Ch_001.md').write_text(markdown, encoding='utf-8')
        manifest = {'chapters': [{'chapter_id': 'ch_001', 'order': 1, 'title': 'Uno', 'display_title': 'Uno', 'unit_type': 'chapter', 'markdown_path': 'markdown/Chapters/Ch_001.md'}]}
        (project / 'chapters/chapter_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return project


if __name__ == '__main__':
    unittest.main()
