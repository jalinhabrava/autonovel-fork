from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path('tests/fixtures/textifai/design_tooling/expected')

class TextifAIOpenDesignNode24Tests(unittest.TestCase):
    def test_node24_report_parses(self):
        payload = json.loads((ROOT / 'node24_dev_environment_after_sp093.json').read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertEqual(payload['version_manager_found'], 'nvm')
        self.assertTrue(payload['node24_available'])
        self.assertFalse(payload['global_environment_changed'])

    def test_open_design_runtime_report_parses(self):
        payload = json.loads((ROOT / 'open_design_runtime_validation_after_sp093.json').read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertTrue(payload['no_textifai_package_changes'])
        self.assertIn('mcp', payload['mcp_status'])
        if not payload['web_started']:
            self.assertTrue(payload['blocked_reason'])

    def test_mcp_validation_report_parses(self):
        payload = json.loads((ROOT / 'open_design_codex_mcp_validation_after_sp093.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['config_snippet_present'])
        self.assertFalse(payload['global_config_modified'])

    def test_live_review_report_parses(self):
        payload = json.loads((ROOT / 'open_design_live_textifai_review_after_sp093.json').read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertIn('reviewed_surfaces', payload)
        if not payload['used_open_design']:
            self.assertTrue(payload['reason_if_false'])

    def test_dev_only_and_no_package_changes(self):
        install = json.loads((ROOT / 'open_design_install_and_skill_setup_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(install['not_runtime_dependency'])
        self.assertFalse(install['textifai_package_changes'])

if __name__ == '__main__':
    unittest.main()
