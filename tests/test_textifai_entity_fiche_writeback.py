from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from textifai.project_store import open_project
from textifai.project_store.store import _hash_text
from textifai.web_viewer.server import _make_handler
EXPECTED = Path(__file__).resolve().parent / 'fixtures/textifai/entity_fiche_writeback/expected'


class TextifaiEntityFicheWritebackTests(unittest.TestCase):
    def test_save_method_and_reports_exist(self):
        self.assertTrue(hasattr(open_project(Path('/tmp/example.textifai')), 'save_entity_fiche_markdown'))
        names = [
            'entity_fiche_save_contract_after_sp122a.json',
            'entity_fiche_backup_versioning_after_sp122a.json',
            'entity_fiche_hash_conflict_after_sp122a.json',
            'entity_fiche_wikilink_preservation_after_sp122a.json',
            'entity_fiche_semantic_dirty_state_after_sp122a.json',
            'entity_fiche_writeback_decision_after_sp122a.json',
        ]
        for name in names:
            data = json.loads((EXPECTED / name).read_text(encoding='utf-8'))
            self.assertTrue(data['save_api_exists'])
            self.assertTrue(data['endpoint_exists'])
            self.assertTrue(data['no_silent_semantic_mutation'])
            self.assertTrue(data['no_vaerl_writeback'])
            self.assertTrue(data['no_graph_regeneration'])
            self.assertTrue(data['no_review_regeneration'])
            self.assertTrue(data['no_source_prose'])

    def test_correct_hash_writes_fiche_backup_frontmatter_wikilinks_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            self._seed_entity_row(store, project)
            path = project / 'markdown/Entities/Sera.md'
            before = path.read_text(encoding='utf-8')
            expected_hash = _hash_text(before)

            body_only = 'Ren es el interés romántico de [[Sera]].\n\nTexto con ñ y 🌙.'
            result = store.save_entity_fiche_markdown('sera', body_only, expected_hash, actor='test', canonical_label='Sera')

            self.assertTrue(result['ok'])
            self.assertEqual(result['semantic_state'], 'needs_reanalysis')
            self.assertTrue(result['dirty_state'])
            after = path.read_text(encoding='utf-8')
            self.assertTrue(after.startswith('---\nentity_id: sera\nkind: character\n---\n'))
            self.assertIn('[[Sera]]', after)
            self.assertIn('ñ y 🌙', after)
            self.assertNotIn('## Relaciones', after)
            self.assertEqual(result['new_hash'], _hash_text(after))
            backup = project / result['backup_path']
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding='utf-8'), before)
            with sqlite3.connect(project / '.textifai/db/textifai.sqlite') as conn:
                dirty = conn.execute('select dirty_reason from dirty_states where resource_type = ? and resource_id = ?', ('entity', 'sera')).fetchone()
                self.assertEqual(dirty[0], 'entity_fiche_markdown_edited')

    def test_save_works_even_when_entity_row_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            path = project / 'markdown/Entities/Sera.md'
            before = path.read_text(encoding='utf-8')

            result = store.save_entity_fiche_markdown(
                'sera',
                'Sera conoce a Ren.\n\nCambio local.',
                _hash_text(before),
                canonical_label='Sera',
            )

            self.assertTrue(result['ok'])
            after = path.read_text(encoding='utf-8')
            self.assertIn('Cambio local.', after)
            self.assertEqual(result['semantic_state'], 'needs_reanalysis')
            with sqlite3.connect(store.sqlite_path) as conn:
                row = conn.execute('select entity_id, canonical_name, ficha_markdown_path from entities where entity_id = ?', ('sera',)).fetchone()
                self.assertEqual(row[0], 'sera')
                self.assertEqual(row[1], 'Sera')
                self.assertEqual(row[2], 'markdown/Entities/Sera.md')

    def test_entity_card_contract_includes_content_hash_field(self):
        text = (Path(__file__).resolve().parents[1] / 'textifai/web_viewer/entity_card.py').read_text(encoding='utf-8')
        self.assertIn('"content_hash": markdown_content_hash', text)

    def test_stale_hash_returns_conflict_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            self._seed_entity_row(store, project)
            path = project / 'markdown/Entities/Sera.md'
            before = path.read_text(encoding='utf-8')

            result = store.save_entity_fiche_markdown('sera', 'changed [[Sera]]', 'stale_hash')

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
            self._seed_entity_row(store, project)
            with sqlite3.connect(project / '.textifai/db/textifai.sqlite') as conn:
                conn.execute('update entities set ficha_markdown_path = ? where entity_id = ?', ('../escape.md', 'sera'))
                conn.commit()
            with self.assertRaises(ValueError):
                store.save_entity_fiche_markdown('sera', 'x', 'y')

    def test_no_vaerl_graph_review_artifacts_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            vaerl = project / 'vaerl'
            graph = project / 'graph'
            vaerl.mkdir(parents=True)
            graph.mkdir(parents=True)
            for rel in ['vaerl/entities.json', 'vaerl/relationships.json', 'vaerl/review_queue.json', 'graph/author_graph.json']:
                p = project / rel
                p.write_text('{}', encoding='utf-8')
            before = {rel: (project / rel).read_text(encoding='utf-8') for rel in ['vaerl/entities.json', 'vaerl/relationships.json', 'vaerl/review_queue.json', 'graph/author_graph.json']}
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            self._seed_entity_row(store, project)
            md = (project / 'markdown/Entities/Sera.md').read_text(encoding='utf-8')
            store.save_entity_fiche_markdown('sera', '[[Sera]] body', _hash_text(md))
            after = {rel: (project / rel).read_text(encoding='utf-8') for rel in before}
            self.assertEqual(before, after)

    def test_http_endpoint_success_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            store = open_project(project)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            self._seed_entity_row(store, project)
            captured: list[tuple[int, dict]] = []

            class Catalog:
                def get_project(self, _project_id: str):
                    return type('Project', (), {'kind': 'textifai_project', 'root': project})()

            handler_cls = _make_handler(Catalog(), type('Registry', (), {})())
            handler = handler_cls.__new__(handler_cls)
            handler.path = '/api/projects/fixture/entities/sera/save'
            handler.headers = {'Content-Length': '0'}
            handler.rfile = BytesIO()
            current = (project / 'markdown/Entities/Sera.md').read_text(encoding='utf-8')
            handler._json_body = lambda: {'markdown': 'Ren ama a [[Sera]].', 'expected_hash': _hash_text(current), 'canonical_label': 'Sera'}
            handler._json = lambda payload, status=200: captured.append((status, payload))

            handler._handle_post()
            self.assertEqual(captured[0][0], 200)
            self.assertTrue(captured[0][1]['ok'])

            captured.clear()
            handler._json_body = lambda: {'markdown': 'stale', 'expected_hash': 'bad', 'canonical_label': 'Sera'}
            handler._handle_post()
            self.assertEqual(captured[0][0], 409)
            self.assertEqual(captured[0][1]['error'], 'hash_mismatch')

    def _make_project(self, parent: Path) -> Path:
        project = parent / 'fixture.textifai'
        (project / 'chapters').mkdir(parents=True)
        (project / 'markdown/Chapters').mkdir(parents=True)
        (project / 'markdown/Entities').mkdir(parents=True)
        (project / 'textifai.project.json').write_text(json.dumps({'project_id': 'fixture', 'title': 'Fixture', 'language': 'es', 'schema_version': 1}), encoding='utf-8')
        (project / 'markdown/Chapters/Ch_001.md').write_text('---\ntitle: Uno\n---\n\n# Uno\n', encoding='utf-8')
        (project / 'markdown/Entities/Sera.md').write_text('---\nentity_id: sera\nkind: character\n---\n\nSera conoce a Ren.\n', encoding='utf-8')
        manifest = {'chapters': [{'chapter_id': 'ch_001', 'order': 1, 'title': 'Uno', 'display_title': 'Uno', 'unit_type': 'chapter', 'markdown_path': 'markdown/Chapters/Ch_001.md'}]}
        (project / 'chapters/chapter_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return project

    def _seed_entity_row(self, store, project: Path) -> None:
        rel = 'markdown/Entities/Sera.md'
        body = (project / rel).read_text(encoding='utf-8')
        checksum = _hash_text(body)
        now = '2026-05-31T00:00:00Z'
        with sqlite3.connect(store.sqlite_path) as conn:
            conn.execute(
                'insert or replace into files(path, kind, checksum, char_count, last_seen_at) values (?, ?, ?, ?, ?)',
                (rel, 'entity_fiche_markdown', checksum, len(body), now),
            )
            conn.execute(
                'insert or replace into entities(entity_id, canonical_name, kind, ficha_markdown_path, summary) values (?, ?, ?, ?, ?)',
                ('sera', 'Sera', 'character', rel, ''),
            )
            conn.commit()

if __name__ == '__main__':
    unittest.main()
