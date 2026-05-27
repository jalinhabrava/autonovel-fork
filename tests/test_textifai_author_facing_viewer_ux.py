import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/viewer_author_ux/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-098_author-facing-viewer-ux'
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
INDEX_HTML = REPO / 'textifai/web_viewer/static/index.html'
PROJECT_READER = REPO / 'textifai/web_viewer/project_reader.py'

REPORTS = [
    'viewer_i18n_string_dictionary_after_sp097.json',
    'viewer_project_selector_author_mode_after_sp097.json',
    'viewer_canonical_node_resolution_after_sp097.json',
    'viewer_node_detail_ia_after_sp097.json',
    'viewer_graph_layout_label_after_sp097.json',
    'viewer_broken_actions_after_sp097.json',
    'open_design_tooling_status_after_sp097.json',
    'author_facing_viewer_ux_decision_after_sp097.json',
]


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIAuthorFacingViewerUXTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload)

    def test_project_selector_defaults_to_viewer_project(self):
        payload = read_json('viewer_project_selector_author_mode_after_sp097.json')
        self.assertTrue(payload['defaults_to_viewer_project'])
        self.assertFalse(payload['defaults_to_markdown_vault'])
        self.assertFalse(payload['primary_copy_mentions_served_root'])
        self.assertFalse(payload['primary_copy_mentions_filesystem_browsing'])

    def test_i18n_dictionary(self):
        payload = read_json('viewer_i18n_string_dictionary_after_sp097.json')
        self.assertEqual(set(payload['locales']), {'en', 'es'})
        self.assertGreater(payload['key_count'], 20)
        self.assertEqual(payload['missing_keys'], [])
        self.assertIn(payload['default_locale_strategy'], {
            'project language -> navigator.language -> en',
            'work.language -> navigator.language -> en',
        })

    def test_source_has_i18n_hooks(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('const I18N = {', text)
        self.assertIn('state.locale', text)
        self.assertIn('function t(', text)
        self.assertIn('navigator.language', text)
        self.assertIn('document.documentElement.lang', text)

    def test_primary_copy_not_dev_facing(self):
        app_text = APP_JS.read_text(encoding='utf-8')
        index_text = INDEX_HTML.read_text(encoding='utf-8')
        for forbidden in [
            'Choose inspected project under served root',
            'No arbitrary filesystem browsing',
        ]:
            self.assertNotIn(forbidden, app_text)
            self.assertNotIn(forbidden, index_text)

    def test_canonical_redirects(self):
        payload = read_json('viewer_canonical_node_resolution_after_sp097.json')
        self.assertGreater(payload['redirects_count'], 0)
        self.assertEqual(payload['Sera_redirect']['from'], 'Concepts/Sera.md')
        self.assertEqual(payload['Sera_redirect']['to'], 'Characters/Sera.md')
        self.assertEqual(payload['Ren_redirect']['from'], 'Concepts/Ren.md')
        self.assertEqual(payload['Ren_redirect']['to'], 'Characters/Ren.md')
        self.assertTrue(payload['graph_click_resolves'])
        self.assertTrue(payload['search_resolves'])
        self.assertTrue(payload['backlinks_resolve'])
        self.assertTrue(payload['wiki_resolves'])
        self.assertTrue(payload['detail_resolves'])

    def test_source_has_canonical_resolution_hooks(self):
        app_text = APP_JS.read_text(encoding='utf-8')
        reader_text = PROJECT_READER.read_text(encoding='utf-8')
        self.assertIn('function resolveCanonicalNodeId(', app_text)
        self.assertIn('canonical_redirects', app_text)
        self.assertIn('canonical_node_id', reader_text)
        self.assertIn('canonical_note_path', reader_text)

    def test_node_detail_ia_report(self):
        payload = read_json('viewer_node_detail_ia_after_sp097.json')
        self.assertEqual(payload['section_order'][:5], [
            'summary', 'facts', 'story_relationships', 'appearances_evidence', 'markdown_links'
        ])
        self.assertTrue(payload['technical_details_collapsed'])
        self.assertTrue(payload['summary_precedes_technical'])
        self.assertTrue(payload['facts_precede_technical'])

    def test_graph_layout_and_labels_report(self):
        payload = read_json('viewer_graph_layout_label_after_sp097.json')
        self.assertTrue(payload['auto_fit_with_padding'])
        self.assertTrue(payload['edge_labels_hidden_by_default'])
        self.assertTrue(payload['selected_or_hover_reveals_labels'])
        self.assertTrue(payload['center_bias_for_characters_and_hubs'])

    def test_broken_actions_cleanup_report(self):
        payload = read_json('viewer_broken_actions_after_sp097.json')
        self.assertTrue(payload['open_review_context_conditioned'])
        self.assertTrue(payload['open_note_conditioned_or_renamed'])
        self.assertTrue(payload['no_placeholder_buttons_in_primary_detail'])

    def test_open_design_status_report(self):
        payload = read_json('open_design_tooling_status_after_sp097.json')
        self.assertIn('repo_exists', payload)
        self.assertFalse(payload['no_runtime_dependency'] is False)
        self.assertTrue(payload['install_required_for_actual_skills'])
        self.assertTrue(payload['user_approval_required_for_global_skill_install'])

    def test_no_provider_calls_or_package_changes(self):
        for name in REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)
        status = subprocess.run(['git', 'status', '--short', 'package.json', 'package-lock.json'], cwd=REPO, check=False, capture_output=True, text=True)
        for line in status.stdout.splitlines():
            self.assertTrue(line.startswith('?? '), line)

    def test_private_handoff_path_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
