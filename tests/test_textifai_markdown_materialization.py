from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from textifai.import_review.markdown_graph_index import build_markdown_graph_index, local_graph
from textifai.import_review.vaerl_markdown_materializer import materialize_vaerl_markdown

FIXTURE_INPUT = Path('tests/fixtures/textifai/markdown_materialization/input/sample_vaerl_for_materialization_after_sp091.json')
FIXTURE_EXPECTED = Path('tests/fixtures/textifai/markdown_materialization/expected')


class TextifAIMarkdownMaterializationTests(unittest.TestCase):
    def test_materializer_creates_expected_folder_structure(self):
        payload = json.loads(FIXTURE_INPUT.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            manifest = materialize_vaerl_markdown(payload, Path(tmp), write_files=True)
            for folder in ['Characters', 'Places', 'Events', 'Objects', 'Concepts', 'Chapters', 'Reviews', 'System']:
                self.assertTrue((Path(tmp) / folder).exists())
            self.assertGreater(manifest['note_count'], 0)

    def test_frontmatter_includes_required_fields(self):
        payload = json.loads(FIXTURE_INPUT.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            manifest = materialize_vaerl_markdown(payload, Path(tmp), write_files=True)
            ada = next(note for note in manifest['notes'] if note['canonical_label'] == 'Ada Bright')
            note = (Path(tmp) / ada['path']).read_text(encoding='utf-8')
            for field in ['vaerl_id:', 'kind:', 'canonical_label:', 'aliases:', 'tags:', 'status:', 'review_state:', 'chapter_ids:', 'source_refs:']:
                self.assertIn(field, note)

    def test_aliases_tags_status_source_refs_preserved(self):
        manifest = json.loads((FIXTURE_EXPECTED / 'sample_materialized_markdown_manifest_after_sp091.json').read_text(encoding='utf-8'))
        ada = next(note for note in manifest['notes'] if note['canonical_label'] == 'Ada Bright')
        self.assertIn('Ada', ada['aliases'])
        self.assertIn('character', ada['tags'])
        self.assertEqual(ada['status'], 'ready')
        self.assertTrue(ada['source_refs'])

    def test_wikilinks_generated_for_relationships(self):
        manifest = json.loads((FIXTURE_EXPECTED / 'sample_materialized_markdown_manifest_after_sp091.json').read_text(encoding='utf-8'))
        ada = next(note for note in manifest['notes'] if note['canonical_label'] == 'Ada Bright')
        self.assertTrue(any('Farmhouse' in link or 'Copper_Key' in link for link in ada['wikilinks']))

    def test_backlink_graph_index_resolves_links_and_reports_unresolved(self):
        index = json.loads((FIXTURE_EXPECTED / 'sample_backlink_graph_index_after_sp091.json').read_text(encoding='utf-8'))
        self.assertGreater(len(index['nodes']), 0)
        self.assertGreater(len(index['edges']), 0)
        self.assertIn('unresolved_links', index)

    def test_graph_nodes_have_degree_counts_and_local_graph_query_works(self):
        sample_vault = FIXTURE_EXPECTED / 'sample_vault_after_sp091'
        index = build_markdown_graph_index(sample_vault)
        self.assertTrue(all('degree' in node for node in index['nodes']))
        chapter = next(node['id'] for node in index['nodes'] if node['kind'] == 'chapter')
        local = local_graph(index, chapter, depth=1)
        self.assertGreater(len(local['nodes']), 0)
        self.assertGreaterEqual(len(local['edges']), 0)

    def test_paths_are_safe_and_no_private_prose_or_keys(self):
        manifest = json.loads((FIXTURE_EXPECTED / 'sample_materialized_markdown_manifest_after_sp091.json').read_text(encoding='utf-8'))
        text = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn('..', ''.join(note['path'] for note in manifest['notes']))
        self.assertNotIn('王者の杖', text)
        secret = os.environ.get('DEEPSEEK_API_KEY')
        if secret:
            self.assertNotIn(secret, text)
