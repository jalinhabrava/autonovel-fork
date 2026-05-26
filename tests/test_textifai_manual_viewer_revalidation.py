from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, ProjectRef, read_artifact, read_project

ROOT = Path('tests/fixtures/textifai/viewer_revalidation/expected')
REPORTS = [
    'sp089_private_graph_presence_after_sp089.json',
    'open_project_discovery_after_sp089.json',
    'open_project_ui_patch_after_sp089.json',
    'manual_viewer_server_after_sp089.json',
    'sp089_viewer_endpoint_validation_after_sp089.json',
    'sp089_viewer_data_quality_after_sp089.json',
    'manual_viewer_revalidation_decision_after_sp089.json',
]


def _sample_graph(label: str, synthetic: bool = False) -> dict:
    node_label = 'Object 010' if synthetic else label
    return {
        'nodes': [
            {
                'id': 'object:item',
                'label': node_label,
                'canonical_label': node_label,
                'kind': 'object',
                'facts': ['kept in cellar'],
                'source_refs': [{'source_id': 'synthetic', 'chapter_id': 'ch_001', 'chunk_id': 'c1', 'char_start': 1, 'char_end': 9}],
            },
            {
                'id': 'character:ada',
                'label': 'Ada',
                'canonical_label': 'Ada',
                'kind': 'character',
                'aliases': ['Archivist'],
                'facts': ['guards the records'],
                'source_refs': [{'source_id': 'synthetic', 'chapter_id': 'ch_001', 'chunk_id': 'c1', 'char_start': 10, 'char_end': 20}],
            },
        ],
        'edges': [
            {'id': 'e1', 'source': 'character:ada', 'target': 'object:item', 'label': 'finds', 'kind': 'object_link', 'source_refs': [{'source_id': 'synthetic', 'chapter_id': 'ch_001', 'chunk_id': 'c1', 'char_start': 10, 'char_end': 20}]},
        ],
        'metadata': {
            'source': 'synthetic',
            'chapters': ['ch_001'],
            'writer_outcome': {
                'total_chapters': 1,
                'chapters_ready': 1,
                'chapters_ready_with_warnings': 0,
                'chapters_needing_retry': 0,
                'chapters_needing_review': 0,
                'chapters_failed': 0,
                'primary_action': {'label': 'Review results'},
                'secondary_action': {'label': 'Later'},
                'user_summary': '1 capítulo procesado.',
            },
            'graph_summary': {
                'node_count': 2,
                'edge_count': 1,
                'node_counts_by_kind': {'character': 1, 'object': 1},
                'synthetic_label_count': 1 if synthetic else 0,
            },
        },
    }


class TextifAIManualViewerRevalidationTests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = json.loads((ROOT / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('王者の杖', text)
            self.assertLess(len(text), 30000)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)

    def test_private_packet_path_is_referenced_in_commit_safe_outputs(self):
        graph_report = json.loads((ROOT / 'sp089_private_graph_presence_after_sp089.json').read_text(encoding='utf-8'))
        server_report = json.loads((ROOT / 'manual_viewer_server_after_sp089.json').read_text(encoding='utf-8'))
        self.assertIn('/tmp/textifai_private_provider_runs/', graph_report['private_path'])
        self.assertIn('/tmp/textifai_private_provider_runs/', server_report['log_path'])

    def test_project_discovery_lists_multiple_projects_under_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, synthetic in [('viewer_project', True), ('viewer_project_sp089', False)]:
                system = root / name / '99_System'
                system.mkdir(parents=True)
                (system / 'ingestion_graph.json').write_text(json.dumps(_sample_graph(name, synthetic=synthetic)), encoding='utf-8')
            catalog = ProjectCatalog([root])
            projects = catalog.list_projects()
            self.assertEqual(len(projects), 2)
            self.assertTrue(any(project['name'] == 'viewer_project_sp089' for project in projects))
            self.assertTrue(any(project['name'] == 'viewer_project' for project in projects))

    def test_selected_project_graph_returns_nodes_edges_and_real_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'viewer_project_sp089'
            system = root / '99_System'
            system.mkdir(parents=True)
            (system / 'ingestion_graph.json').write_text(json.dumps(_sample_graph('Copper Key', synthetic=False)), encoding='utf-8')
            project = read_project(ProjectRef(project_id='p', name='viewer_project_sp089', kind='vault_or_run', root=root, system_root=system))
            self.assertGreater(len(project['graph']['nodes']), 0)
            self.assertGreater(len(project['graph']['edges']), 0)
            self.assertEqual(project['overview']['chapters_processed'], 1)
            self.assertEqual(project['graph']['metadata']['graph_summary']['synthetic_label_count'], 0)
            self.assertTrue(any(node['label'] == 'Copper Key' for node in project['graph']['nodes']))

    def test_no_arbitrary_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'viewer_project_sp089'
            system = root / '99_System'
            system.mkdir(parents=True)
            (system / 'ingestion_graph.json').write_text(json.dumps(_sample_graph('Copper Key', synthetic=False)), encoding='utf-8')
            project = ProjectRef(project_id='p', name='viewer_project_sp089', kind='vault_or_run', root=root, system_root=system)
            with self.assertRaises(ValueError):
                read_artifact(project, '../outside.txt')

    def test_decision_enum_and_synthetic_label_guard(self):
        decision = json.loads((ROOT / 'manual_viewer_revalidation_decision_after_sp089.json').read_text(encoding='utf-8'))
        self.assertIn(decision['assessment'], {
            'viewer_manual_revalidation_passed_ready_for_user_review',
            'viewer_manual_revalidation_passed_with_minor_warnings',
            'viewer_manual_revalidation_needs_data_projection_patch',
            'viewer_manual_revalidation_needs_open_project_patch',
            'viewer_manual_revalidation_blocked',
        })
        endpoint = json.loads((ROOT / 'sp089_viewer_endpoint_validation_after_sp089.json').read_text(encoding='utf-8'))
        self.assertEqual(endpoint['synthetic_labels_count'], 0)
        self.assertTrue(endpoint['real_labels_present'])


if __name__ == '__main__':
    unittest.main()
