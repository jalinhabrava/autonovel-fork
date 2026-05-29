import json
import unittest
from pathlib import Path

ROOT = Path('/home/david/projects/autonovel-fork')
PROJECT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
EXPECTED = ROOT / 'tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected'
REPORT = EXPECTED / 'evidence_coverage_backfill_after_sp112a.json'
DECISION = EXPECTED / 'source_map_chunks_decision_after_sp111.json'


class TestSourceMapChunksEvidenceResolution(unittest.TestCase):
    def test_source_map_chunks_contract_exists(self):
        sm = json.loads((PROJECT / 'evidence/source_map.json').read_text(encoding='utf-8'))
        self.assertIn('chunks', sm)
        self.assertIsInstance(sm['chunks'], dict)
        for _, row in list(sm['chunks'].items())[:5]:
            self.assertIn('chunk_id', row)
            self.assertIn('chapter_id', row)
            self.assertIn('chapter_path', row)
            self.assertIn('char_start', row)
            self.assertIn('char_end', row)
            self.assertIn('text_hash', row)

    def test_evidence_index_links_chunks(self):
        ei = json.loads((PROJECT / 'evidence/evidence_index.json').read_text(encoding='utf-8'))
        items = [row for row in ei.get('items', []) if isinstance(row, dict)]
        self.assertGreater(len(items), 0)
        self.assertTrue(any(str(row.get('chunk_id') or '').strip() for row in items))
        self.assertTrue(any(str(row.get('evidence_id') or '').startswith('ev_') for row in items))

    def test_expected_reports_exist_and_commit_safe(self):
        names = [
            'source_map_chunks_contract_after_sp111.json',
            'evidence_resolution_contract_after_sp111.json',
            'review_evidence_runtime_after_sp111.json',
            'evidence_modal_ui_contract_after_sp111.json',
            'source_map_chunks_decision_after_sp111.json',
            'evidence_coverage_backfill_after_sp112a.json',
        ]
        for name in names:
            data = json.loads((EXPECTED / name).read_text(encoding='utf-8'))
            self.assertIn('assessment', data)
            raw = json.dumps(data, ensure_ascii=False)
            self.assertNotIn('Me llamaron muchas cosas', raw)

    def test_evidence_coverage_backfill_report(self):
        data = json.loads(REPORT.read_text(encoding='utf-8'))
        self.assertGreaterEqual(data['evidence_total'], 1)
        self.assertIn('backfilled_count', data)
        self.assertIn('unresolved_count', data)
        self.assertIn('blocker_counts', data)
        self.assertFalse(data.get('provider_calls', True))
        self.assertFalse(data.get('write_back', True))
        self.assertFalse(data.get('project_package_staged', True))
        self.assertTrue(data.get('no_source_prose'))

    def test_unresolved_refs_have_blocker_classification(self):
        blockers = json.loads(REPORT.read_text(encoding='utf-8')).get('blocker_counts', {})
        for key in [
            'missing_chunk',
            'missing_offsets',
            'offsets_out_of_range',
            'chunk_relative_offsets_without_chunk_text',
            'missing_chapter_mapping',
            'malformed_source_ref',
            'resolvable_from_chapter_markdown',
            'already_resolved',
        ]:
            self.assertIn(key, blockers)

    def test_no_fake_excerpts_and_requirements(self):
        data = json.loads(REPORT.read_text(encoding='utf-8'))
        self.assertEqual(data['excerpt_after'], data['excerpt_before'] + data['backfilled_count'])
        req = data.get('next_ingestion_requirements') or {}
        self.assertIn('source_map_chunks', req)
        self.assertIn('source_ref_contract', req)
        self.assertIn('source_ref_key_stable', req.get('source_ref_contract', []))

    def test_decision_consistency(self):
        decision = json.loads(DECISION.read_text(encoding='utf-8'))
        data = json.loads(REPORT.read_text(encoding='utf-8'))
        self.assertEqual(decision.get('assessment'), data.get('assessment'))
        self.assertEqual(decision.get('provider_calls'), data.get('provider_calls'))
        self.assertEqual(decision.get('write_back'), data.get('write_back'))


if __name__ == '__main__':
    unittest.main()
