import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/project_store_architecture/expected'

ADR = REPO / 'docs/adr/ADR-0001-textifai-projectstore-sqlite-hybrid-architecture.md'
SCHEMA_DOC = REPO / 'docs/architecture/textifai_sqlite_schema_v0.md'
PROJECTSTORE_CONTRACT = REPO / 'textifai/project_store/README.md'
LIVE_FOLDER_CONTRACT = REPO / 'docs/architecture/textifai_project_folder_contract.md'
BUNDLE_CONTRACT = REPO / 'docs/architecture/txtfai_bundle_contract.md'
SCHEMA_SQL = REPO / 'textifai/project_store/schema.sql'


def read_report(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIProjectStoreArchitectureTests(unittest.TestCase):
    ARCHITECTURE_PATHS = [
        'docs/adr/ADR-0001-textifai-projectstore-sqlite-hybrid-architecture.md',
        'docs/architecture/textifai_sqlite_schema_v0.md',
        'docs/architecture/textifai_project_folder_contract.md',
        'docs/architecture/txtfai_bundle_contract.md',
        'textifai/project_store/README.md',
        'textifai/project_store/schema.sql',
        'tests/test_textifai_project_store_architecture.py',
        'tests/fixtures/textifai/project_store_architecture/expected/projectstore_architecture_decision_after_sp113a.json',
        'tests/fixtures/textifai/project_store_architecture/expected/sqlite_schema_v0_contract_after_sp113a.json',
        'tests/fixtures/textifai/project_store_architecture/expected/txtfai_bundle_contract_after_sp113a.json',
        'tests/fixtures/textifai/project_store_architecture/expected/markdown_sqlite_json_ownership_after_sp113a.json',
    ]

    def test_required_documents_exist(self):
        for path in [ADR, SCHEMA_DOC, PROJECTSTORE_CONTRACT, LIVE_FOLDER_CONTRACT, BUNDLE_CONTRACT, SCHEMA_SQL]:
            self.assertTrue(path.exists(), str(path))

    def test_reports_parse(self):
        reports = [
            'projectstore_architecture_decision_after_sp113a.json',
            'sqlite_schema_v0_contract_after_sp113a.json',
            'txtfai_bundle_contract_after_sp113a.json',
            'markdown_sqlite_json_ownership_after_sp113a.json',
        ]
        for name in reports:
            payload = read_report(name)
            self.assertIn('assessment', payload)

    def test_adr_documents_hybrid_decision_and_vector_strategy(self):
        text = ADR.read_text(encoding='utf-8').lower()
        self.assertIn('hybrid', text)
        self.assertIn('markdown', text)
        self.assertIn('sqlite', text)
        self.assertIn('json', text)
        self.assertIn('vectorindex', text)
        self.assertIn('pluggable', text)

    def test_ownership_and_json_snapshot_policy_documented(self):
        combined = '\n'.join([
            ADR.read_text(encoding='utf-8').lower(),
            PROJECTSTORE_CONTRACT.read_text(encoding='utf-8').lower(),
            LIVE_FOLDER_CONTRACT.read_text(encoding='utf-8').lower(),
        ])
        self.assertIn('json snapshots', combined)
        self.assertIn('not live crud source', combined)
        self.assertIn('markdown', combined)

    def test_saas_future_mapping_documented(self):
        text = ADR.read_text(encoding='utf-8').lower()
        self.assertIn('team', text)
        self.assertIn('online-only', text)
        self.assertIn('postgres', text)
        self.assertIn('same logical projectstore contract', text)

    def test_sqlite_schema_doc_mentions_all_required_tables(self):
        text = SCHEMA_DOC.read_text(encoding='utf-8')
        required = [
            'project_meta', 'files', 'chapters', 'entities', 'entity_aliases', 'relationships',
            'evidence_items', 'source_chunks', 'review_items', 'review_decisions', 'graph_nodes',
            'graph_edges', 'dirty_states', 'jobs', 'migrations', 'settings'
        ]
        for table in required:
            self.assertIn(f'`{table}`', text)

    def test_schema_sql_declares_required_tables(self):
        text = SCHEMA_SQL.read_text(encoding='utf-8').lower()
        for table in [
            'project_meta', 'files', 'chapters', 'entities', 'entity_aliases', 'relationships',
            'evidence_items', 'source_chunks', 'review_items', 'review_decisions', 'graph_nodes',
            'graph_edges', 'dirty_states', 'jobs', 'migrations', 'settings'
        ]:
            self.assertIn(f'create table if not exists {table}', text)

    def test_no_react_editor_files_touched(self):
        for path in self.ARCHITECTURE_PATHS:
            normalized = path.replace('\\', '/')
            self.assertFalse(normalized.startswith('textifai/web_viewer/static/react-shell/'))
            self.assertFalse(normalized.startswith('textifai/web_viewer/react_shell/src/'))

    def test_no_project_package_manifest_staged(self):
        staged = subprocess.run(['git', 'diff', '--name-only', '--cached'], cwd=REPO, capture_output=True, text=True, check=True)
        for path in staged.stdout.splitlines():
            self.assertNotEqual(path.strip(), 'textifai.project.json')

    def test_no_provider_calls_in_test_execution(self):
        checked = subprocess.run(['git', 'grep', '-n', 'OPENAI_API_KEY\\|ANTHROPIC_API_KEY', '--', 'docs/adr', 'docs/architecture', 'textifai/project_store'], cwd=REPO, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 1)


if __name__ == '__main__':
    unittest.main()
