import json
import subprocess
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, read_project

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/targeted_retry_policy/expected'
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
MANIFEST = PROJECT_ROOT / 'textifai.project.json'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-106b_targeted-retry-policy/decision_handoff_private.md'
HANDOFF = REPO / 'docs/handoffs/safepoint-106b_targeted-retry-policy.md'
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
API = REPO / 'textifai/web_viewer/react_shell/src/api.ts'

REPORTS = [
    'persistent_workspace_8872_verification_after_sp106.json',
    'retry_classification_after_sp106.json',
    'ingestion_retry_policy_after_sp106.json',
    'targeted_retry_execution_after_sp106.json',
    'workspace_ingestion_status_after_sp106.json',
    'persistent_workspace_views_after_sp106.json',
    'targeted_retry_policy_decision_after_sp106.json',
]

def read_report(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class TextifAITargetedRetryPolicyTests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = read_report(name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload, name)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text, name)
            self.assertNotIn('Me llamaron muchas cosas', text, name)

    def test_manifest_has_retry_policy_fields(self):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        policy = manifest.get('ingestion_policy') or {}
        self.assertTrue(policy.get('allow_auto_retries'))
        self.assertEqual(policy.get('max_retries_per_chapter'), 2)
        self.assertTrue(policy.get('retry_only_technical_failures'))
        self.assertTrue(policy.get('ask_before_extra_costly_retry'))
        status = manifest.get('status') or {}
        for key in ['chapters_total', 'chapters_ready', 'chapters_retry_required', 'chapters_retried', 'chapters_still_failed', 'technical_failures', 'semantic_reviews']:
            self.assertIn(key, status)

    def test_retry_classification_distinguishes_retry_from_review(self):
        report = read_report('retry_classification_after_sp106.json')
        self.assertTrue(report['retry_only_technical_failures'])
        self.assertEqual(report['technical_retry_items'], report['retry_required_chapters'])
        self.assertGreater(report['technical_retry_items'], 0)
        self.assertEqual(report['semantic_review_items'], 0)

    def test_only_retry_required_chapters_selected(self):
        writer = json.loads((PROJECT_ROOT / '99_System/writer_outcome.json').read_text(encoding='utf-8'))
        retry_ids = [row['chapter_id'] for row in writer.get('affected_chapters', []) if row.get('status') == 'needs_retry']
        self.assertEqual(len(retry_ids), writer.get('chapters_needing_retry'))
        report = read_report('targeted_retry_execution_after_sp106.json')
        self.assertEqual(report['chapters_skipped_ready'], 5)
        self.assertTrue(report['provider_calls_made'])
        self.assertFalse(report['full_rerun'])

    def test_product_ui_status_avoids_internal_jargon(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('chapters_detected_label', text)
        self.assertIn('chapters_still_failed_label', text)
        report = read_report('workspace_ingestion_status_after_sp106.json')
        self.assertTrue(report['no_chunk_language_in_product_ui'])
        product_text = '\n'.join(report['author_summary_strings']).lower()
        for forbidden in ['chunk', 'reduction', 'provider', 'token']:
            self.assertNotIn(forbidden, product_text)

    def test_8872_project_report_prefers_persistent_project(self):
        report = read_report('persistent_workspace_8872_verification_after_sp106.json')
        self.assertTrue(report['persistent_project_listed'])
        self.assertTrue(report['persistent_project_selected_by_default'])
        self.assertTrue(report['mini_fixture_listed_as_dev_only'])
        self.assertEqual(report['chapter_count'], 20)

    def test_editor_graph_review_use_persistent_project(self):
        report = read_report('persistent_workspace_views_after_sp106.json')
        self.assertTrue(report['uses_persistent_project'])
        self.assertEqual(report['editor_chapter_count'], 20)
        self.assertTrue(report['editor_primaries_excluded'])
        self.assertGreater(report['graph_node_count'], 11)
        self.assertGreater(report['review_decision_count'], 0)

    def test_loader_exposes_retry_policy_and_workspace_status(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        project_ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        payload = read_project(project_ref)
        self.assertTrue(payload['ingestion_policy']['retry_only_technical_failures'])
        self.assertIn('capítulos detectados', payload['workspace_status']['chapters_detected_label'])
        self.assertIn('decisiones editoriales', payload['workspace_status']['semantic_review_label'])

    def test_private_handoff_gitignored_and_package_not_staged(self):
        self.assertTrue(HANDOFF.exists())
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', ignore.stdout)
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertNotIn('/home/david/TextifAIProjects', staged.stdout)
        self.assertNotIn('.textifai_runs/registry.local.json', staged.stdout)

if __name__ == '__main__':
    unittest.main()
