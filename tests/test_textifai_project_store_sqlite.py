from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from textifai.project_store import open_project
from textifai.web_viewer.project_reader import _project_from_candidate, read_editor_chapters


PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')


class TextifaiProjectStoreSQLiteTests(unittest.TestCase):
    def test_bootstrap_project_store_from_real_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_copy = Path(tmp) / 'OnT_Spanish_20ch.textifai'
            self._copy_project(project_copy)

            store = open_project(project_copy)
            store.validate_project()
            store.ensure_sqlite()
            store.bootstrap_from_project_files()

            chapters = store.get_chapters()
            self.assertEqual(len(chapters), 20)
            self.assertEqual(chapters[0]['chapter_id'], 'ch_001')
            self.assertEqual(chapters[0]['source_used'], 'project_store')
            self.assertEqual(chapters[0]['dirty_state'], False)
            self.assertEqual(chapters[0]['semantic_state'], 'ready')
            self.assertTrue(chapters[0]['markdown_path'].startswith('markdown/Chapters/'))

            chapter = store.get_chapter('ch_001')
            self.assertEqual(chapter['chapter_id'], 'ch_001')
            self.assertIn('markdown', chapter)
            self.assertGreater(len(chapter['markdown']), 0)
            self.assertEqual(chapter['dirty_state'], False)

            dirty = store.get_dirty_state('chapter', 'ch_001')
            self.assertEqual(dirty['dirty'], False)

            db_path = project_copy / '.textifai' / 'db' / 'textifai.sqlite'
            self.assertTrue(db_path.exists())
            with sqlite3.connect(db_path) as conn:
                count = conn.execute('select count(*) from chapters').fetchone()[0]
                self.assertEqual(count, 20)

            project_ref = _project_from_candidate(project_copy)
            editor_chapters = read_editor_chapters(project_ref)
            self.assertEqual(editor_chapters['source_used'], 'project_store')
            self.assertEqual(len(editor_chapters['chapters']), 20)
            self.assertEqual(editor_chapters['chapters'][0]['chapter_id'], 'ch_001')

    def test_mark_dirty_persists_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_copy = Path(tmp) / 'OnT_Spanish_20ch.textifai'
            self._copy_project(project_copy)

            store = open_project(project_copy)
            store.ensure_sqlite()
            store.bootstrap_from_project_files()
            store.mark_dirty('chapter', 'ch_001', 'test-change')

            dirty = store.get_dirty_state('chapter', 'ch_001')
            self.assertTrue(dirty['dirty'])
            self.assertEqual(dirty['reason'], 'test-change')

    def _copy_project(self, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for relative in ['textifai.project.json', 'chapters/chapter_manifest.json']:
            source = PROJECT_ROOT / relative
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
        chapters_dir = dest / 'markdown' / 'Chapters'
        chapters_dir.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((PROJECT_ROOT / 'chapters/chapter_manifest.json').read_text(encoding='utf-8'))
        for chapter in manifest['chapters']:
            source = PROJECT_ROOT / chapter['markdown_path']
            target = dest / chapter['markdown_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
