from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path('tests/fixtures/textifai/design_tooling/expected')


class TextifAIDesignToolingTests(unittest.TestCase):
    def test_open_design_audit_report_parses(self):
        payload = json.loads((ROOT / 'open_design_dev_tooling_audit_after_sp091.json').read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertTrue(payload['not_runtime_dependency'])
        self.assertTrue(payload['not_product_dependency'])

    def test_install_plan_is_dev_only_and_no_package_files_required(self):
        payload = json.loads((ROOT / 'open_design_dev_only_install_plan_after_sp091.json').read_text(encoding='utf-8'))
        self.assertFalse(payload['package_json_changes_required'])
        self.assertIn('/tmp/textifai_dev_tools/open-design', payload['recommended_install_path'])

    def test_design_docs_exist_and_no_html_anything(self):
        design_doc = Path('docs/textifai-design-direction.md').read_text(encoding='utf-8')
        checklist = Path('docs/textifai-ui-review-checklist.md').read_text(encoding='utf-8')
        self.assertIn('Dashboard', design_doc)
        self.assertIn('dashboard checklist', checklist.casefold())
        self.assertNotIn('html-anything', design_doc.casefold())
        self.assertNotIn('html-anything', checklist.casefold())

    def test_ui_checklist_covers_core_surfaces(self):
        checklist = Path('docs/textifai-ui-review-checklist.md').read_text(encoding='utf-8').casefold()
        for term in ['dashboard', 'graph', 'wiki', 'node detail', 'editor', 'debug secondary']:
            self.assertIn(term, checklist)
