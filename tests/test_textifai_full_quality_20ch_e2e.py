import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/full_quality_20ch_e2e/expected'
HANDOFF = REPO / 'docs/handoffs/safepoint-107_full-quality-20ch-e2e.md'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-107_full-quality-20ch-e2e/decision_handoff_private.md'
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')

class TextifAIFullQuality20chE2ETests(unittest.TestCase):
    def test_provider_model_routing_report_exists(self):
        report = read('provider_model_routing_after_sp106e.json')
        self.assertTrue(report['strong_model_available'])
        self.assertEqual(report['strong_model_name'], 'deepseek-v4-pro')
        self.assertTrue(report['semantic_tasks_use_strong_model'])
        self.assertTrue(report['low_quality_retries_escalate_to_strong_model'])
        self.assertTrue(report['no_secrets_logged'])

    def test_full_quality_manifest_status_has_active_run(self):
        report = read('full_quality_manifest_status_after_sp106e.json')
        self.assertTrue(report['active_run_id'])
        self.assertTrue(report['model_routing_summary']['strong_model_used'])
        self.assertIn(report['assessment'], [
            'full_quality_20ch_e2e_ready_for_manual_review',
            'full_quality_20ch_e2e_ready_with_review_warnings',
            'full_quality_20ch_e2e_partial_needs_targeted_followup',
            'full_quality_20ch_e2e_blocked_provider_or_model_missing',
            'full_quality_20ch_e2e_failed_needs_pipeline_fix',
        ])

    def test_chapter_quality_summary_exists(self):
        report = read('chapter_quality_summary_after_sp106e.json')
        self.assertEqual(report['chapters_detected'], 20)
        self.assertGreaterEqual(report['ready_chapters'], 0)
        self.assertGreaterEqual(report['review_chapters'], 0)
        self.assertGreaterEqual(report['retry_required_chapters'], 0)
        self.assertEqual(report['ready_chapters'] + report['review_chapters'] + report['retry_required_chapters'], 20)

    def test_persistent_workspace_8872_report_selects_project(self):
        report = read('persistent_workspace_8872_full_quality_after_sp106e.json')
        self.assertTrue(report['persistent_project_selected'])
        self.assertFalse(report['mini_fixture_selected_by_default'])
        self.assertEqual(report['chapter_count'], 20)
        self.assertGreater(report['note_count'], 20)
        self.assertGreater(report['graph_node_count'], 20)

    def test_workspace_views_full_quality(self):
        report = read('workspace_views_full_quality_after_sp106e.json')
        self.assertEqual(report['editor_chapter_count'], 20)
        self.assertTrue(report['editor_primaries_excluded'])
        self.assertTrue(report['graph_node_count'] > 0)
        self.assertTrue(report['review_decision_count'] >= 0)
        self.assertTrue(report['uses_persistent_project'])

    def test_e2e_quality_comparison_report(self):
        report = read('e2e_quality_comparison_after_sp106e.json')
        self.assertIn('sp095_baseline', report)
        self.assertIn('sp106_previous', report)
        self.assertIn('sp107_current', report)
        # no hard equality, but can note improvements

    def test_reports_commit_safe_and_private(self):
        for name in [
            'provider_model_routing_after_sp106e.json',
            'full_quality_run_summary_after_sp106e.json',
            'chapter_quality_summary_after_sp106e.json',
            'full_quality_manifest_status_after_sp106e.json',
            'persistent_workspace_8872_full_quality_after_sp106e.json',
            'workspace_views_full_quality_after_sp106e.json',
            'e2e_quality_comparison_after_sp106e.json',
            'full_quality_20ch_e2e_decision_after_sp106e.json',
        ]:
            payload = read(name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('source_prose', text)
        self.assertTrue(HANDOFF.exists())
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, capture_output=True, text=True, check=False)
        self.assertIn('docs/handoffs/private/', ignore.stdout)

def read(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()
