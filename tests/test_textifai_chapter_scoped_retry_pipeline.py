import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/chapter_scoped_retry_pipeline/expected'
SCRIPT = REPO / 'scripts/dev/spanish_20ch_vaerl_markdown_viewer.py'
PIPE = REPO / 'scripts/dev/chapter_scoped_retry_pipeline.py'
MODULE = REPO / 'textifai/import_review/chapter_scoped_retry.py'
HANDOFF = REPO / 'docs/handoffs/safepoint-106e_chapter-scoped-retry-pipeline.md'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-106e_chapter-scoped-retry-pipeline/decision_handoff_private.md'

REPORTS = [
    'chapter_ids_pipeline_support_after_sp106d.json',
    'chapter_subchunking_strategy_after_sp106d.json',
    'chapter_retry_output_contract_after_sp106d.json',
    'chapter_patch_generation_after_sp106d.json',
    'chapter_patch_integration_after_sp106d.json',
    'provider_pilot_result_after_sp106d.json',
    'workspace_status_after_chapter_retry_after_sp106d.json',
    'chapter_scoped_retry_pipeline_decision_after_sp106d.json',
]

def read(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class TextifAIChapterScopedRetryPipelineTests(unittest.TestCase):
    def test_reports_commit_safe(self):
        for name in REPORTS:
            payload = read(name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('Me llamaron muchas cosas', text)

    def test_high_level_parser_accepts_chapter_ids(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('--chapter-ids', text)
        self.assertIn('parse_chapter_ids', text)
        report = read('chapter_ids_pipeline_support_after_sp106d.json')
        self.assertTrue(report['argparse_accepts_chapter_ids'])
        self.assertTrue(report['invalid_ids_rejected'])
        self.assertTrue(report['full_run_without_chapter_ids_supported'])

    def test_invalid_chapter_ids_rejected(self):
        result = subprocess.run(['uv', 'run', 'python', str(SCRIPT), '--help'], cwd=REPO, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--chapter-ids', result.stdout)

    def test_subchunking_preserves_source_refs(self):
        text = MODULE.read_text(encoding='utf-8')
        self.assertIn('def build_chapter_subchunks', text)
        self.assertIn('source_ref', text)
        report = read('chapter_subchunking_strategy_after_sp106d.json')
        self.assertTrue(report['preserves_chapter_id'])
        self.assertTrue(report['preserves_source_refs'])

    def test_retry_result_and_patch_schemas_exist(self):
        module = MODULE.read_text(encoding='utf-8')
        for token in ['textifai.chapter_retry_result', 'textifai.chapter_vaerl_patch', 'textifai.chapter_graph_patch', 'textifai.chapter_review_patch']:
            self.assertIn(token, module)

    def test_integration_does_not_overwrite_unrelated(self):
        report = read('chapter_patch_integration_after_sp106d.json')
        self.assertFalse(report['integration_applied'])
        self.assertFalse(report['overwrites_unrelated_chapters'])

    def test_ready_and_semantic_review_not_retried(self):
        report = read('provider_pilot_result_after_sp106d.json')
        self.assertEqual(report['chapters_attempted'], ['ch_005', 'ch_010'])
        self.assertFalse(report['full_rerun'])
        status = read('workspace_status_after_chapter_retry_after_sp106d.json')
        self.assertTrue(status['no_product_jargon'])

    def test_workspace_strings_avoid_jargon(self):
        text = json.dumps(read('workspace_status_after_chapter_retry_after_sp106d.json'), ensure_ascii=False).lower()
        for forbidden in ['chunk', 'reduction', 'provider', 'score']:
            self.assertNotIn(forbidden, text)

    def test_project_package_not_staged_and_private_gitignored(self):
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=REPO, capture_output=True, text=True, check=False).stdout
        self.assertNotIn('/home/david/TextifAIProjects', staged)
        self.assertNotIn('.textifai_runs/registry.local.json', staged)
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, capture_output=True, text=True, check=False)
        self.assertIn('docs/handoffs/private/', ignore.stdout)
        self.assertTrue(HANDOFF.exists())

if __name__ == '__main__':
    unittest.main()
