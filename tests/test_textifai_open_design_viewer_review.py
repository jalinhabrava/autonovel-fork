import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/open_design_viewer_review/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-099_open-design-viewer-redesign'

REPORTS = [
    'open_design_tooling_verification_after_sp098.json',
    'viewer_design_review_after_sp098.json',
    'viewer_redesign_brief_after_sp098.json',
    'graph_engine_recommendation_after_sp098.json',
    'open_design_viewer_review_decision_after_sp098.json',
]

VALID_DECISIONS = {
    'open_design_viewer_redesign_review_ready_for_sp100_planning',
    'open_design_viewer_review_partial_needs_followup',
    'open_design_viewer_review_blocked',
}


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIOpenDesignViewerReviewTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_open_design_verification_report(self):
        payload = read_json('open_design_tooling_verification_after_sp098.json')
        self.assertTrue(payload['repo_exists'])
        self.assertEqual(payload['repo_path'], '/tmp/textifai_dev_tools/open-design')
        self.assertEqual(payload['repo_commit'], '279da4f3')
        self.assertTrue(payload['codex_mcp_registered'])
        self.assertEqual(payload['codex_mcp_name'], 'open-design')
        self.assertFalse(payload['textifai_runtime_dependency'])
        self.assertFalse(payload['package_change_required'])

    def test_design_review_report(self):
        payload = read_json('viewer_design_review_after_sp098.json')
        for key in [
            'dashboard_overview',
            'project_selector',
            'global_graph',
            'local_graph',
            'wiki_browser',
            'node_detail_panel',
            'review_queue',
            'technical_details_dev_mode',
            'i18n_copy',
            'future_markdown_editor',
        ]:
            self.assertIn('current_issue', payload[key])
            self.assertIn('recommendation', payload[key])

    def test_redesign_brief_report(self):
        payload = read_json('viewer_redesign_brief_after_sp098.json')
        self.assertIn('Author-facing narrative knowledge workspace', payload['north_star'])
        self.assertEqual(payload['project_selection']['default'], 'viewer_project if present')
        self.assertIn('Sera/Ren open character canonical cards with bio/facts.', payload['acceptance_criteria'])
        self.assertIn('markdown_vault is not presented as a normal project in author mode.', payload['acceptance_criteria'])

    def test_graph_engine_recommendation_report(self):
        payload = read_json('graph_engine_recommendation_after_sp098.json')
        self.assertEqual(payload['assessment'], 'recommend_d3_force_ack_for_sp100')
        self.assertEqual(payload['options']['d3_force_svg']['recommendation'], 'preferred')
        self.assertTrue(payload['ack_required_before_dependency'])
        self.assertIn('d3-force', payload['package_change_needed'])
        self.assertFalse(payload['textifai_runtime_dependency_on_open_design'])

    def test_decision_enum_valid(self):
        payload = read_json('open_design_viewer_review_decision_after_sp098.json')
        self.assertIn(payload['assessment'], VALID_DECISIONS)
        self.assertFalse(payload['provider_calls'])
        self.assertFalse(payload['write_back'])
        self.assertFalse(payload['package_changes'])
        self.assertFalse(payload['runtime_dependency_added'])

    def test_no_provider_calls_or_package_changes(self):
        for name in REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)
        status = subprocess.run(['git', 'status', '--short', 'package.json', 'package-lock.json'], cwd=REPO, check=False, capture_output=True, text=True)
        for line in status.stdout.splitlines():
            self.assertTrue(line.startswith('?? '), line)

    def test_no_runtime_dependency_on_open_design(self):
        payload = read_json('open_design_tooling_verification_after_sp098.json')
        self.assertFalse(payload['textifai_runtime_dependency'])
        self.assertFalse(payload['package_change_required'])
        decision = read_json('open_design_viewer_review_decision_after_sp098.json')
        self.assertFalse(decision['runtime_dependency_added'])

    def test_private_handoff_path_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
