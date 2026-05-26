from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path('tests/fixtures/textifai/design_tooling/expected')
REPORTS = [
    'open_design_install_and_skill_setup_after_sp092.json',
    'open_design_codex_mcp_setup_after_sp092.json',
    'textifai_open_design_first_review_after_sp092.json',
    'open_design_tooling_decision_after_sp092.json',
]

class TextifAIOpenDesignSetupTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = json.loads((ROOT / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False).casefold()
            self.assertIn('assessment', payload)
            self.assertNotIn('html-anything', text)
            self.assertNotIn('provider_response_raw', text)

    def test_install_report_dev_only_outside_repo(self):
        payload = json.loads((ROOT / 'open_design_install_and_skill_setup_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['not_runtime_dependency'])
        self.assertTrue(payload['not_product_dependency'])
        self.assertTrue(payload['clone_path'].startswith('/tmp/textifai_dev_tools/open-design'))
        self.assertFalse(payload['textifai_package_changes'])
        self.assertGreaterEqual(payload['skills_found_count'], 1)
        self.assertGreaterEqual(payload['design_systems_found_count'], 1)

    def test_codex_mcp_setup_doc_exists(self):
        doc = Path('docs/textifai-open-design-codex-setup.md')
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8')
        self.assertIn('mcpServers', text)
        self.assertIn('/tmp/textifai_dev_tools/open-design', text)
        self.assertIn('Dev-only', text)

    def test_skills_and_design_systems_selected_or_blocked_reason_present(self):
        payload = json.loads((ROOT / 'open_design_install_and_skill_setup_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['selected_recommended_skills'])
        self.assertTrue(payload['selected_recommended_design_system'])
        self.assertTrue(payload['blocked_reason'])

    def test_generated_outputs_not_committed(self):
        payload = json.loads((ROOT / 'textifai_open_design_first_review_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['output_path_private'].startswith('/tmp/textifai_private_provider_runs/'))
        self.assertFalse(Path(payload['output_path_private']).is_relative_to(Path.cwd()))

    def test_no_package_file_dependency(self):
        payload = json.loads((ROOT / 'open_design_install_and_skill_setup_after_sp092.json').read_text(encoding='utf-8'))
        self.assertFalse(payload['textifai_package_changes'])
        text = Path('docs/textifai-open-design-codex-setup.md').read_text(encoding='utf-8')
        self.assertIn('No modificar `package.json`/`package-lock.json`', text)

if __name__ == '__main__':
    unittest.main()
