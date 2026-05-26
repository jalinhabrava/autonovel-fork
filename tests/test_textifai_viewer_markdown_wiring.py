from __future__ import annotations

import json
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, read_note, read_project

ROOT = Path('tests/fixtures/textifai/viewer_wiring')
INPUT = ROOT / 'input'
EXPECTED = ROOT / 'expected'
REPORTS = [
    'current_viewer_wiring_inventory_after_sp092.json',
    'markdown_manifest_project_reader_patch_after_sp092.json',
    'wiki_browser_mvp_after_sp092.json',
    'node_detail_markdown_backlink_patch_after_sp092.json',
    'graph_readability_v1_after_sp092.json',
    'dashboard_overview_markdown_index_patch_after_sp092.json',
    'sample_markdown_viewer_project_validation_after_sp092.json',
    'viewer_markdown_wiki_manual_server_after_sp092.json',
    'markdown_wiki_viewer_wiring_decision_after_sp092.json',
]

class TextifAIViewerMarkdownWiringTests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = json.loads((EXPECTED / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('王者の杖', text)
            self.assertLess(len(text), 30000)

    def test_project_reader_loads_markdown_manifest_and_index(self):
        project = self._sample_project()
        payload = read_project(project)
        self.assertTrue(payload['markdown_manifest'])
        self.assertTrue(payload['markdown_graph_index'])
        self.assertEqual(payload['overview']['markdown_note_count'], 8)
        self.assertEqual(payload['overview']['markdown_graph_edge_count'], 11)

    def test_wiki_browser_data_available(self):
        payload = read_project(self._sample_project())
        notes = payload['notes']
        self.assertGreaterEqual(len(notes), 8)
        ada = next(note for note in notes if note['path'] == 'Characters/Ada_Bright_2.md')
        self.assertIn('character', ada['tags'])
        self.assertIn('backlinks', ada)
        self.assertIn('outgoing_wikilinks', ada)
        self.assertIn('degree', ada)

    def test_note_detail_includes_frontmatter_tags_backlinks_outgoing(self):
        note = read_note(self._sample_project(), 'Characters/Ada_Bright_2.md')
        self.assertEqual(note['frontmatter']['canonical_label'], 'Ada Bright')
        self.assertIn('character', note['tags'])
        self.assertTrue(note['backlinks'])
        self.assertTrue(note['outgoing_wikilinks'])
        self.assertTrue(note['local_graph']['nodes'])

    def test_graph_nodes_edges_degree_and_local_graph(self):
        payload = read_project(self._sample_project())
        graph = payload['graph']
        self.assertEqual(graph['metadata']['source'], 'markdown_graph_index')
        self.assertGreater(len(graph['nodes']), 0)
        self.assertGreater(len(graph['edges']), 0)
        self.assertTrue(all('degree' in node for node in graph['nodes']))
        self.assertTrue(all(edge.get('label') for edge in graph['edges']))

    def test_filters_metadata_and_dashboard_counts_available(self):
        payload = read_project(self._sample_project())
        tags = payload['markdown_graph_index']['tags']
        kinds = {node['kind'] for node in payload['graph']['nodes']}
        overview = payload['overview']
        self.assertIn('character', kinds)
        self.assertIn('ready', tags)
        self.assertIn('orphan_note_count', overview)
        self.assertIn('unresolved_link_count', overview)
        self.assertIn('next_action_cta', overview)

    def test_artifacts_debug_secondary_in_report(self):
        payload = json.loads((EXPECTED / 'dashboard_overview_markdown_index_patch_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['artifacts_debug_secondary'])
        self.assertFalse(payload['raw_json_primary_surface'])

    def test_sample_viewer_project_parsea(self):
        report = json.loads((EXPECTED / 'sample_markdown_viewer_project_validation_after_sp092.json').read_text(encoding='utf-8'))
        self.assertTrue(report['project_discovered'])
        self.assertEqual(report['note_count'], 8)
        self.assertEqual(report['graph_edge_count'], 11)

    def _sample_project(self):
        catalog = ProjectCatalog([INPUT.resolve()])
        projects = catalog.list_projects()
        self.assertEqual(len(projects), 1)
        return catalog.get_project(projects[0]['project_id'])

if __name__ == '__main__':
    unittest.main()
