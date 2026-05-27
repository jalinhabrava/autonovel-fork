from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path('tests/fixtures/textifai/spanish_20ch_e2e/expected')
PRIVATE = Path('docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight')
REPORTS = [
    'spanish_20ch_source_preflight_after_sp094.json',
    'spanish_20ch_execution_plan_after_sp094.json',
    'spanish_20ch_deepseek_execution_summary_after_sp094.json',
    'spanish_20ch_writer_outcome_after_sp094.json',
    'spanish_20ch_vaerl_projection_summary_after_sp094.json',
    'spanish_20ch_markdown_materialization_summary_after_sp094.json',
    'spanish_20ch_markdown_graph_index_summary_after_sp094.json',
    'spanish_20ch_viewer_project_summary_after_sp094.json',
    'spanish_20ch_viewer_manual_review_server_after_sp094.json',
    'spanish_20ch_viewer_api_validation_after_sp094.json',
    'spanish_20ch_graph_quality_summary_after_sp094.json',
    'spanish_20ch_ui_review_checklist_after_sp094.json',
    'spanish_20ch_product_decision_after_sp094.json',
]
FORBIDDEN_WRITER_TERMS = {
    'chunk', 'reduction', 'parseable', 'provider', 'source_ref', 'finish_reason',
    'json', 'continuation', 'patch', 'model', 'profile', 'token', 'api',
    'telemetry', 'run_id', 'failure_mode',
}
VALID_ASSESSMENTS = {
    'spanish_20ch_vaerl_markdown_viewer_ready_for_manual_review',
    'spanish_20ch_partial_needs_targeted_retry',
    'spanish_20ch_blocked_missing_source',
    'spanish_20ch_blocked_provider',
    'spanish_20ch_failed_needs_patch',
}


class TextifAISpanish20chE2ETests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = json.loads((ROOT / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('CHUNK_TEXT', text)
            self.assertNotIn('html-anything', text.casefold())
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)

    def test_execution_plan_has_no_artificial_call_cap_blocker(self):
        payload = json.loads((ROOT / 'spanish_20ch_execution_plan_after_sp094.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['no_artificial_call_cap'])
        self.assertTrue(payload['telemetry_only_estimates'])
        self.assertTrue(payload['emergency_loop_guard']['enabled'])

    def test_gitignore_and_private_handoff_path(self):
        gitignore = Path('.gitignore').read_text(encoding='utf-8')
        self.assertIn('docs/handoffs/private/', gitignore)
        private_path = PRIVATE / 'decision_handoff_private.md'
        self.assertTrue(str(private_path).startswith('docs/handoffs/private/'))

    def test_private_handoff_folder_is_gitignored(self):
        result = subprocess.run(
            ['git', 'check-ignore', '-v', 'docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/decision_handoff_private.md'],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertIn('docs/handoffs/private/', result.stdout)

    def test_writer_outcome_avoids_technical_terms(self):
        payload = json.loads((ROOT / 'spanish_20ch_writer_outcome_after_sp094.json').read_text(encoding='utf-8'))
        text = json.dumps(payload, ensure_ascii=False).casefold()
        for term in FORBIDDEN_WRITER_TERMS:
            self.assertNotIn(term, text)

    def test_product_decision_enum_valid(self):
        payload = json.loads((ROOT / 'spanish_20ch_product_decision_after_sp094.json').read_text(encoding='utf-8'))
        self.assertIn(payload['assessment'], VALID_ASSESSMENTS)

    def test_private_runtime_and_handoff_paths_referenced(self):
        decision = json.loads((ROOT / 'spanish_20ch_product_decision_after_sp094.json').read_text(encoding='utf-8'))
        self.assertIn('private_runtime_packet_root', decision)
        self.assertIn('private_handoff_root', decision)


if __name__ == '__main__':
    unittest.main()
