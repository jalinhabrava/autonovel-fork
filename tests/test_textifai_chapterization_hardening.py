import json
import re
import unittest
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / 'tests/fixtures/textifai/chapterization_hardening/expected'
PROJECT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
MANIFEST_PATH = PROJECT / 'chapters/chapter_manifest.json'
PROJECT_ID = 'home__david__TextifAIProjects__OnT_Spanish_20ch.textifai'


class ChapterizationHardeningTests(unittest.TestCase):
    def test_reports_exist_and_parse(self):
        names = [
            'source_heading_taxonomy_after_sp112a.json',
            'chapter_manifest_quality_audit_after_sp112a.json',
            'chapter_splitter_ranges_after_sp112a.json',
            'chapter_title_cleanup_after_sp112a.json',
            'editor_chapter_manifest_runtime_after_sp112a.json',
            'chapterization_hardening_decision_after_sp112a.json',
        ]
        for name in names:
            data = json.loads((REPORTS / name).read_text(encoding='utf-8'))
            self.assertIn('assessment', data)

    def test_h1_candidates_classified_not_blind(self):
        data = json.loads((REPORTS / 'source_heading_taxonomy_after_sp112a.json').read_text(encoding='utf-8'))
        self.assertEqual(data['h1_candidates_detected'], 64)
        self.assertEqual(data['classified']['true_chapter'], 20)

    def test_manifest_quality(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        chapters = manifest['chapters']
        self.assertEqual(manifest['total_chapters'], 20)
        self.assertEqual(len(chapters), 20)
        ids = [ch['chapter_id'] for ch in chapters]
        paths = [ch['markdown_path'] for ch in chapters]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(paths), len(set(paths)))
        starts = [int(ch['source_start']) for ch in chapters]
        ends = [int(ch['source_end']) for ch in chapters]
        self.assertTrue(all(a < b for a, b in zip(starts, ends)))
        self.assertTrue(all(ends[i] <= starts[i+1] for i in range(len(chapters)-1)))
        for chapter in chapters:
            self.assertTrue(str(chapter.get('display_title') or '').strip())
            self.assertTrue(str(chapter.get('unit_type') or '').strip())
            self.assertFalse(re.search(r'https?://', chapter.get('display_title') or '', re.IGNORECASE))
            self.assertFalse(re.match(r'^Chapter\s+0*(4|10|11|14|17)$', chapter.get('display_title') or '', re.IGNORECASE))

    def test_editor_payload_uses_manifest(self):
        payload = json.loads(urlopen(f'http://127.0.0.1:8872/api/projects/{PROJECT_ID}', timeout=5).read().decode('utf-8'))
        editor = payload.get('editor_chapters') or {}
        self.assertEqual(editor.get('source_used'), 'project_store')
        self.assertTrue(editor.get('manifest_used'))
        chapters = editor.get('chapters') or []
        self.assertEqual(len(chapters), 20)

    def test_reports_no_prose_or_provider_or_writeback(self):
        for report in REPORTS.glob('*.json'):
            text = report.read_text(encoding='utf-8')
            self.assertNotIn('Me llamaron muchas cosas', text)
            data = json.loads(text)
            self.assertFalse(bool(data.get('provider_calls', False)))
            self.assertFalse(bool(data.get('write_back', False)))


if __name__ == '__main__':
    unittest.main()
