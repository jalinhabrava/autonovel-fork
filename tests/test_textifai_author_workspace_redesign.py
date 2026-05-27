import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/author_workspace_redesign/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-100_author-workspace-redesign'
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
INDEX_HTML = REPO / 'textifai/web_viewer/static/index.html'
PROJECT_READER = REPO / 'textifai/web_viewer/project_reader.py'
PACKAGE_JSON = REPO / 'package.json'

REPORTS = [
    'open_design_mcp_verification_after_sp099.json',
    'package_impact_after_sp099.json',
    'author_workspace_shell_after_sp099.json',
    'd3_force_graph_engine_v3_after_sp099.json',
    'graph_v3_ux_after_sp099.json',
    'node_inspector_author_card_after_sp099.json',
    'dashboard_author_home_after_sp099.json',
    'wiki_kb_redesign_after_sp099.json',
    'review_queue_author_decisions_after_sp099.json',
    'i18n_primary_ux_coverage_after_sp099.json',
    'stable_author_workspace_8872_after_sp099.json',
    'author_workspace_redesign_decision_after_sp099.json',
]


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIAuthorWorkspaceRedesignTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_d3_dependency_present(self):
        package = json.loads(PACKAGE_JSON.read_text(encoding='utf-8'))
        deps = package.get('dependencies', {})
        self.assertIn('d3-force', deps)

    def test_unused_map_dependency_removed(self):
        package = json.loads(PACKAGE_JSON.read_text(encoding='utf-8'))
        deps = package.get('dependencies', {})
        self.assertNotIn('map', deps)

    def test_node_modules_not_staged(self):
        status = subprocess.run(['git', 'status', '--short', 'node_modules'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), '')

    def test_graphengine_uses_d3_force_apis(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('forceSimulation', text)
        self.assertIn('forceCenter', text)
        self.assertIn('forceManyBody', text)
        self.assertIn('forceLink', text)
        self.assertIn('forceCollide', text)

    def test_edges_by_id_and_no_index_line_updates(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('data-edge-id', text)
        self.assertNotIn('data-edge="${index}"', text)
        self.assertNotIn('data-edge-group="${index}"', text)

    def test_edge_labels_hidden_by_default(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('edge-label hidden', text)

    def test_local_graph_mode_explicit(self):
        payload = read_json('graph_v3_ux_after_sp099.json')
        self.assertTrue(payload['local_graph_mode_explicit'])

    def test_project_selector_not_dev_facing(self):
        text = INDEX_HTML.read_text(encoding='utf-8') + APP_JS.read_text(encoding='utf-8')
        self.assertNotIn('served root', text)
        self.assertNotIn('filesystem browsing', text)

    def test_markdown_vault_dev_artifact_not_default(self):
        payload = read_json('author_workspace_shell_after_sp099.json')
        self.assertTrue(payload['viewer_project_default'])
        self.assertTrue(payload['markdown_vault_dev_artifact'])

    def test_artifacts_moved_out_of_primary_nav(self):
        html = INDEX_HTML.read_text(encoding='utf-8')
        self.assertNotIn('id="tab-artifacts"', html)
        self.assertIn('id="tab-dev"', html)

    def test_node_detail_summary_facts_before_technical(self):
        payload = read_json('node_inspector_author_card_after_sp099.json')
        self.assertEqual(payload['section_order'][:3], ['summary', 'facts', 'story_relationships'])
        self.assertTrue(payload['technical_details_collapsed'])

    def test_sera_ren_canonical_character(self):
        payload = read_json('node_inspector_author_card_after_sp099.json')
        self.assertEqual(payload['sera']['resolved_kind'], 'character')
        self.assertEqual(payload['ren']['resolved_kind'], 'character')
        self.assertTrue(payload['sera']['summary_present'])
        self.assertTrue(payload['ren']['summary_present'])

    def test_i18n_coverage(self):
        payload = read_json('i18n_primary_ux_coverage_after_sp099.json')
        self.assertEqual(set(payload['locales']), {'en', 'es'})
        self.assertEqual(payload['missing_primary_keys'], [])
        self.assertEqual(payload['runtime_default_for_spanish'], 'es')

    def test_open_design_report(self):
        payload = read_json('open_design_mcp_verification_after_sp099.json')
        self.assertTrue(payload['mcp_registered'])
        self.assertTrue(payload['daemon_healthy'])
        self.assertTrue(payload['no_runtime_dependency'])

    def test_stable_8872_report(self):
        payload = read_json('stable_author_workspace_8872_after_sp099.json')
        self.assertTrue(payload['8872_serves_sp096'])
        self.assertTrue(payload['d3_graph_engine_active'])
        self.assertTrue(payload['package_dependency_present'])

    def test_no_provider_calls(self):
        for name in REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)

    def test_private_handoff_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
