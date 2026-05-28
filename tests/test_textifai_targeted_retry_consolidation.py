import json
import subprocess
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, read_project

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/targeted_retry_consolidation/expected'
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
MANIFEST = PROJECT_ROOT / 'textifai.project.json'
HANDOFF = REPO / 'docs/handoffs/safepoint-106c_targeted-retry-consolidation.md'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-106c_targeted-retry-consolidation/decision_handoff_private.md'
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'

REPORTS = [
    'chapter_retry_result_classification_after_sp106b.json',
    'retry_artifact_integration_after_sp106b.json',
    'manifest_status_after_retry_consolidation_after_sp106b.json',
    'workspace_status_after_retry_consolidation_after_sp106b.json',
    'persistent_workspace_8872_after_retry_consolidation_after_sp106b.json',
    'editor_graph_review_after_retry_consolidation_after_sp106b.json',
    'retry_cta_state_after_sp106b.json',
    'targeted_retry_consolidation_decision_after_sp106b.json',
]

def report(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class TextifAITargetedRetryConsolidationTests(unittest.TestCase):
    def test_reports_exist_and_are_commit_safe(self):
        for name in REPORTS:
            payload = report(name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertTrue(payload, name)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text, name)
            self.assertNotIn('Me llamaron muchas cosas', text, name)
            self.assertNotIn('provider_response', text, name)

    def test_retry_classification_distinguishes_technical_and_review(self):
        payload = report('chapter_retry_result_classification_after_sp106b.json')
        chapters = payload['chapters']
        self.assertEqual(len(chapters), 20)
        attempted = [row for row in chapters if row['retry_attempted']]
        still_failed = [row for row in chapters if row['after_retry_status'] == 'still_failed']
        self.assertEqual(len(attempted), 15)
        self.assertEqual(len(still_failed), 13)
        self.assertTrue(all(row['semantic_review_count'] == 0 for row in chapters))

    def test_integration_report_is_honest(self):
        payload = report('retry_artifact_integration_after_sp106b.json')
        self.assertFalse(payload['integration_supported'])
        self.assertFalse(payload['graph_updated'])
        self.assertFalse(payload['vaerl_updated'])
        self.assertEqual(payload['chapters_integrated'], [])

    def test_manifest_status_includes_retry_summary(self):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.assertIn('retry_summary', manifest)
        retry = manifest['retry_summary']
        self.assertEqual(retry['provider'], 'deepseek')
        self.assertIn(retry['model'], ['deepseek-v4-flash', 'deepseek-v4-pro'])
        status = manifest['status']
        self.assertEqual(status['chapters_total'], 20)
        if manifest.get('active_run_id'):
            self.assertIn('chapters_still_failed', status)
        else:
            self.assertEqual(status['chapters_retried'], 15)
            self.assertEqual(status['chapters_still_failed'], 13)

    def test_workspace_status_uses_author_facing_language(self):
        payload = report('workspace_status_after_retry_consolidation_after_sp106b.json')
        strings = ' '.join(str(v) for v in payload.values()).lower()
        for expected in ['20 capítulos detectados', '15 reintentados', '13 siguen necesitando reintento']:
            self.assertIn(expected, strings)
        for forbidden in ['chunk', 'reduction', 'provider raw', 'stack trace']:
            self.assertNotIn(forbidden, strings)

    def test_8872_and_views_use_persistent_project(self):
        payload = report('persistent_workspace_8872_after_retry_consolidation_after_sp106b.json')
        self.assertTrue(payload['persistent_project_selected'])
        self.assertTrue(payload['mini_fixture_not_selected_by_default'])
        self.assertEqual(payload['chapter_count'], 20)
        self.assertGreater(payload['graph_node_count'], 11)
        view = report('editor_graph_review_after_retry_consolidation_after_sp106b.json')
        self.assertEqual(view['editor_chapter_count'], 20)
        self.assertTrue(view['editor_primaries_excluded'])
        self.assertGreater(view['review_decision_count'], 0)

    def test_loader_exposes_consolidated_status(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        project_ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        payload = read_project(project_ref)
        self.assertIn('capítulos detectados', payload['workspace_status']['chapters_detected_label'])
        self.assertIn(payload['workspace_status']['retry_cta'], ['Reintentar capítulos fallidos', 'Abrir workspace'])

    def test_retry_cta_state_is_honest(self):
        payload = report('retry_cta_state_after_sp106b.json')
        self.assertTrue(payload['retry_available'])
        self.assertEqual(payload['retry_label'], 'Reintentar capítulos fallidos')
        self.assertTrue(payload['open_workspace_available'])
        text = APP.read_text(encoding='utf-8')
        self.assertIn('chapters_still_failed_label', text)

    def test_project_package_registry_provider_outputs_not_staged(self):
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=REPO, capture_output=True, text=True, check=False).stdout
        self.assertNotIn('/home/david/TextifAIProjects', staged)
        self.assertNotIn('.textifai_runs/registry.local.json', staged)
        self.assertNotIn('dev/provider_outputs', staged)
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, capture_output=True, text=True, check=False)
        self.assertIn('docs/handoffs/private/', ignore.stdout)

if __name__ == '__main__':
    unittest.main()
