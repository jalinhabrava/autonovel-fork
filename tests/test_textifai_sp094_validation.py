from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

VAL = Path('tests/fixtures/textifai/validation/expected')
VIEW = Path('tests/fixtures/textifai/viewer_wiring/expected')
DESIGN = Path('tests/fixtures/textifai/design_tooling/expected')

class TextifAISP094ValidationTests(unittest.TestCase):
    def test_validation_report_parses(self):
        payload = json.loads((VAL / 'sp093_full_validation_results_after_sp093.json').read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertIn('results', payload)
        self.assertEqual(len(payload['results']), 16)
        self.assertTrue(all('command' in row for row in payload['results']))

    def test_decision_reports_parse(self):
        for path in [
            VAL / 'sp094_validation_decision_after_sp093.json',
            VIEW / 'viewer_manual_review_decision_after_sp093.json',
            DESIGN / 'open_design_node24_decision_after_sp093.json',
        ]:
            payload = json.loads(path.read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)

    def test_viewer_manual_review_reports_parse(self):
        manual = json.loads((VIEW / 'viewer_markdown_wiki_manual_review_after_sp093.json').read_text(encoding='utf-8'))
        quality = json.loads((VIEW / 'viewer_markdown_wiki_data_quality_after_sp093.json').read_text(encoding='utf-8'))
        self.assertTrue(manual['manual_review_required'])
        self.assertTrue(quality['overview_ok'])
        self.assertTrue(quality['wiki_ok'])
        self.assertTrue(quality['graph_ok'])
        self.assertTrue(quality['node_detail_ok'])

    def test_reports_have_no_private_outputs_or_api_keys(self):
        for root in [VAL, VIEW, DESIGN]:
            for path in root.glob('*.json'):
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('provider_response_raw', text)
                self.assertNotIn('final_prompt_sent', text)
                self.assertNotIn('html-anything', text.casefold())
                secret = os.environ.get('DEEPSEEK_API_KEY')
                if secret:
                    self.assertNotIn(secret, text)

if __name__ == '__main__':
    unittest.main()
