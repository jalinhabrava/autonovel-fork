import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from textifai.import_review.markdown_graph_index import build_markdown_graph_index, build_author_graph
from textifai.web_viewer.project_reader import ProjectCatalog, read_project

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/canonical_projection_regression/expected'
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
AUTHOR_GRAPH = PROJECT_ROOT / 'graph/author_graph.json'
RUN_STATUS = PROJECT_ROOT / 'reports/run_status.json'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-108b_canonical-projection-review-progress/decision_handoff_private.md'


def read_report(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class CanonicalProjectionRegressionTests(unittest.TestCase):
    def test_markdown_graph_index_excludes_internal_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'markdown/Characters').mkdir(parents=True)
            (root / 'dev/provider_outputs/viewer_project/Characters').mkdir(parents=True)
            (root / 'runs/x/markdown_vault/Characters').mkdir(parents=True)
            (root / '99_System').mkdir()
            (root / 'markdown/Characters/Ren.md').write_text('---\nkind: character\ncanonical_label: Ren\n---\n# Ren\n', encoding='utf-8')
            (root / 'dev/provider_outputs/viewer_project/Characters/Ren.md').write_text('# Ren dev\n', encoding='utf-8')
            (root / 'runs/x/markdown_vault/Characters/Yo.md').write_text('# Yo\n', encoding='utf-8')
            (root / '99_System/Internal.md').write_text('# Internal\n', encoding='utf-8')
            index = build_markdown_graph_index(root)
            paths = {note['path'] for note in index['notes']}
            self.assertEqual(paths, {'markdown/Characters/Ren.md'})

    def test_author_graph_contract_exists_and_filters(self):
        self.assertTrue(AUTHOR_GRAPH.exists())
        payload = json.loads(AUTHOR_GRAPH.read_text(encoding='utf-8'))
        self.assertEqual(payload['schema'], 'textifai.author_graph')
        self.assertEqual(payload['schema_version'], 1)
        text = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in ['dev/provider_outputs', 'runs/sp107', 'reviewlocal_candidate', 'provider_response_raw']:
            self.assertNotIn(forbidden, text)
        labels = {str(node.get('label', '')).casefold() for node in payload['nodes']}
        for pronoun in ['yo', 'ella', 'él', 'el', 'la']:
            self.assertNotIn(pronoun, labels)
        self.assertGreaterEqual(payload['excluded']['dev_nodes'], 0)
        self.assertGreater(payload['excluded']['pronouns'], 0)

    def test_project_reader_prioritizes_author_graph(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        graph = detail['graph']
        self.assertEqual(graph['metadata']['graph_mode'], 'author_graph')
        self.assertTrue(graph['metadata']['author_graph_ready'])
        self.assertLess(len(graph['nodes']), 700)

    def test_duplicate_pronoun_and_candidate_reports_exist(self):
        duplicate = read_report('entity_duplicate_pronoun_audit_after_sp107.json')
        leak = read_report('internal_candidate_leak_audit_after_sp107.json')
        self.assertGreater(duplicate['before']['ren_visible_nodes'], duplicate['after']['ren_visible_nodes'])
        self.assertEqual(duplicate['after']['pronoun_visible_nodes'], 0)
        self.assertGreater(leak['before']['internal_candidate_nodes'], 0)
        self.assertEqual(leak['after']['internal_candidate_nodes'], 0)

    def test_review_decisions_are_hydrated(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        review = detail['canon']['review_queue']
        items = review.get('decision_items') or []
        self.assertEqual(len(items), review.get('item_count'))
        self.assertTrue(items)
        first = items[0]
        for key in ['id', 'type', 'severity', 'title', 'subtitle', 'human_reason', 'evidence_refs', 'local_state', 'suggested_action']:
            self.assertIn(key, first)
        titles = [item['title'] for item in items]
        self.assertFalse(any(title in {'Entidad origen / Entidad relacionada', 'Entidad origen'} for title in titles))
        summary = review.get('decision_summary') or {}
        grouped_total = sum(summary.get(key, 0) for key in ['possible_merges', 'probable_aliases', 'uncertain_relationships', 'insufficient_evidence', 'pronoun_pov', 'unconfirmed_local_candidates'])
        self.assertEqual(grouped_total, summary['total_pending'])

    def test_graph_filters_and_ingestion_progress_contracts(self):
        adapter = (REPO / 'textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts').read_text(encoding='utf-8')
        toolbar = (REPO / 'textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx').read_text(encoding='utf-8')
        app = (REPO / 'textifai/web_viewer/react_shell/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('selectedKinds', adapter)
        self.assertIn('toggleKind', toolbar)
        self.assertIn('Restablecer filtros', app)
        self.assertNotIn('Mostrar todo', app)
        self.assertTrue(RUN_STATUS.exists())
        status = json.loads(RUN_STATUS.read_text(encoding='utf-8'))
        self.assertEqual(status['schema'], 'textifai.run_status')
        self.assertTrue(status['safe_to_open_workspace'])
        self.assertEqual(status['status'], 'completed_with_editorial_review')
        self.assertGreaterEqual(len(status['steps']), 10)

    def test_reports_commit_safe_and_private_handoff_ignored(self):
        for path in EXPECTED.glob('*.json'):
            payload = json.loads(path.read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload, path.name)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('Me llamaron muchas cosas', text)
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, capture_output=True, text=True, check=False)
        self.assertIn('docs/handoffs/private/', ignore.stdout)
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=REPO, capture_output=True, text=True, check=False).stdout
        self.assertNotIn('/home/david/TextifAIProjects', staged)
        self.assertNotIn('.textifai_runs/registry.local.json', staged)


if __name__ == '__main__':
    unittest.main()
