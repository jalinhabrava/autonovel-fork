from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

ROOT = Path('tests/fixtures/textifai/platform_architecture/expected')
INPUT = Path('tests/fixtures/textifai/platform_architecture/input')
REPORTS = [
    'readme_product_doctrine_after_sp090.json',
    'current_repo_vs_readme_gap_after_sp090.json',
    'quartz_architecture_audit_after_sp090.json',
    'existing_obsidian_like_path_reuse_after_sp090.json',
    'first_party_vaerl_platform_architecture_after_sp090.json',
    'vaerl_markdown_materialization_contract_after_sp090.json',
    'first_party_viewer_surfaces_after_sp090.json',
    'quartz_obsidian_adaptation_strategy_after_sp090.json',
    'lean_legacy_cleanup_plan_after_sp090.json',
    'sample_markdown_materialization_index_after_sp090.json',
    'sample_graph_index_from_markdown_after_sp090.json',
    'first_party_vaerl_platform_decision_after_sp090.json',
]


class TextifAIPlatformArchitectureTests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = json.loads((ROOT / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('王者の杖', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)

    def test_readme_doctrine_includes_vaerl_source_of_truth(self):
        payload = json.loads((ROOT / 'readme_product_doctrine_after_sp090.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['vaerl_as_source_of_truth'])
        self.assertTrue(payload['markdown_first_class_output'])
        self.assertIn('Obsidian importer', payload['what_textifai_is_not'])

    def test_architecture_report_defines_layers(self):
        payload = json.loads((ROOT / 'first_party_vaerl_platform_architecture_after_sp090.json').read_text(encoding='utf-8'))
        layer_names = [layer['name'] for layer in payload['layers']]
        for required in ['Ingestion/ECC', 'VaERL core', 'Markdown materialization layer', 'Graph/index/backlink layer', 'Viewer/KB manager', 'Wiki view', 'AI authoring suite', 'Review/retry/canon governance']:
            self.assertIn(required, layer_names)

    def test_materialization_contract_includes_markdown_frontmatter_tags_wikilinks_backlinks(self):
        payload = json.loads((ROOT / 'vaerl_markdown_materialization_contract_after_sp090.json').read_text(encoding='utf-8'))
        self.assertIn('frontmatter_required', payload)
        self.assertIn('tags', payload)
        self.assertIn('wikilinks', payload)
        self.assertIn('backlinks', payload)
        self.assertIn('editability_rules', payload)

    def test_viewer_surfaces_include_dashboard_graph_wiki_node_detail_ai_authoring(self):
        payload = json.loads((ROOT / 'first_party_viewer_surfaces_after_sp090.json').read_text(encoding='utf-8'))
        for required in ['dashboard', 'graph', 'wiki', 'node_detail', 'ai_authoring']:
            self.assertIn(required, payload)

    def test_quartz_strategy_does_not_require_external_obsidian_primary_workflow(self):
        payload = json.loads((ROOT / 'quartz_obsidian_adaptation_strategy_after_sp090.json').read_text(encoding='utf-8'))
        avoid = ' '.join(payload['avoid'])
        self.assertIn('external Obsidian as primary workflow', avoid)
        self.assertEqual(payload['embed_generated_quartz'], 'temporary spike only, not product architecture')

    def test_legacy_cleanup_rejects_indefinite_fallback(self):
        payload = json.loads((ROOT / 'lean_legacy_cleanup_plan_after_sp090.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['rejects_indefinite_fallback'])

    def test_optional_spike_files_parse(self):
        source = json.loads((INPUT / 'sample_vaerl_for_markdown_materialization.json').read_text(encoding='utf-8'))
        materialized = json.loads((ROOT / 'sample_markdown_materialization_index_after_sp090.json').read_text(encoding='utf-8'))
        graph = json.loads((ROOT / 'sample_graph_index_from_markdown_after_sp090.json').read_text(encoding='utf-8'))
        self.assertIn('entities', source)
        self.assertGreater(len(materialized['generated_files']), 0)
        self.assertGreater(len(graph['nodes']), 0)
        self.assertGreater(len(graph['edges']), 0)


if __name__ == '__main__':
    unittest.main()
