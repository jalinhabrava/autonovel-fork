import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/viewer_graph_architecture/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-097_stable-graph-viewer-v2'
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
LAUNCHER = REPO / 'scripts/dev/textifai_viewer_dev_server.py'
PROJECT_READER = REPO / 'textifai/web_viewer/project_reader.py'

REPORTS = [
    'stable_viewer_server_diagnosis_after_sp096.json',
    'stable_viewer_server_workflow_after_sp096.json',
    'graph_api_contract_v2_after_sp096.json',
    'edge_rendering_fix_after_sp096.json',
    'native_graph_engine_v2_after_sp096.json',
    'graph_viewer_v2_ux_after_sp096.json',
    'quartz_obsidian_graph_pattern_adr_after_sp096.json',
    'stable_sp096_viewer_8872_after_sp096.json',
]


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIViewerGraphArchitectureTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_graph_contract_v2_report(self):
        payload = read_json('graph_api_contract_v2_after_sp096.json')
        self.assertEqual(payload['contract_version'], 2)
        self.assertTrue(payload['uses_sp096_runtime'])
        self.assertEqual(payload['bad_edges_count'], 0)
        self.assertEqual(payload['missing_source_count'], 0)
        self.assertEqual(payload['missing_target_count'], 0)
        self.assertEqual(payload['edges_with_id_count'], payload['edge_count'])
        self.assertEqual(payload['nodes_with_radius_count'], payload['node_count'])
        self.assertEqual(payload['nodes_with_color_count'], payload['node_count'])

    def test_static_app_uses_edge_ids_not_edge_indexes(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('data-edge-id', text)
        self.assertIn('state.current.visibleGraph', text)
        self.assertIn('normalizeGraphData', text)
        self.assertIn('buildVisibleGraph', text)
        self.assertIn('createGraphLayout', text)
        self.assertIn('tickGraph', text)
        self.assertIn('renderGraphDom', text)
        self.assertIn('updateGraphDom', text)
        self.assertIn('bindGraphInteractions', text)
        self.assertNotIn('data-edge="${index}"', text)
        self.assertNotIn('data-edge-group="${index}"', text)
        self.assertNotIn('updateGraphDom(svg, byId, (state.current.graph || {}).edges || [])', text)

    def test_project_reader_emits_contract_v2_metadata(self):
        text = PROJECT_READER.read_text(encoding='utf-8')
        self.assertIn('graph_contract_version', text)
        self.assertIn('edge_id', text)
        self.assertIn('radius', text)
        self.assertIn('color', text)
        self.assertIn('canonical_redirects', text)

    def test_stable_server_workflow_report(self):
        payload = read_json('stable_viewer_server_workflow_after_sp096.json')
        self.assertEqual(payload['default_port'], 8872)
        self.assertTrue(payload['writes_pid_file'])
        self.assertTrue(payload['writes_log_file'])
        self.assertTrue(payload['refuses_non_textifai_process'])
        self.assertTrue(payload['supports_kill_existing_textifai_viewer'])

    def test_launcher_contract(self):
        text = LAUNCHER.read_text(encoding='utf-8')
        self.assertIn('--kill-existing-textifai-viewer', text)
        self.assertIn('/tmp/textifai_viewer_8872.pid', text)
        self.assertIn('/tmp/textifai_viewer_8872.log', text)
        self.assertIn('textifai.web_viewer.server', text)
        self.assertIn('refusing to stop non-TextifAI process', text)
        self.assertNotIn('8873', text)

    def test_stable_sp096_viewer_report(self):
        payload = read_json('stable_sp096_viewer_8872_after_sp096.json')
        self.assertTrue(payload['8872_serves_sp096'])
        self.assertFalse(payload['8872_serves_sp095'])
        self.assertEqual(payload['port'], 8872)
        self.assertIn('sp096_vaerl_entity_quality_viewer_ux_patch', payload['root'])
        self.assertIn('__viewer_project', payload['project_id'])
        self.assertGreater(payload['graph_node_count'], 0)
        self.assertGreater(payload['graph_edge_count'], 0)
        self.assertEqual(payload['bad_edges_count'], 0)

    def test_no_package_dependency_change_required(self):
        status = subprocess.run(['git', 'status', '--short', 'package.json', 'package-lock.json'], cwd=REPO, check=False, capture_output=True, text=True)
        for line in status.stdout.splitlines():
            self.assertTrue(line.startswith('?? '), line)

    def test_no_provider_calls_reported(self):
        for name in REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)
        decision = read_json('stable_sp096_viewer_8872_after_sp096.json')
        self.assertFalse(decision['provider_calls'])
        self.assertFalse(decision['write_back'])

    def test_private_handoff_path_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
