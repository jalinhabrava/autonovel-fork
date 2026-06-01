from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSPECTOR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx'
FICHE = REPO / 'textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx'
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
ENTITY_CARD = REPO / 'textifai/web_viewer/entity_card.py'
FIX = REPO / 'tests/fixtures/textifai/graph_fiche/expected'

REPORTS = [
    'graph_fiche_surface_after_sp120.json',
    'entity_fiche_source_priority_after_sp120.json',
    'entity_fiche_visual_editor_contract_after_sp120.json',
    'entity_fiche_technical_details_policy_after_sp120.json',
    'entity_fiche_i18n_after_sp120.json',
    'entity_fiche_wikilinks_after_sp121c.json',
    'entity_fiche_semantic_contract_after_sp122a.json',
    'entity_fiche_generated_body_policy_after_sp122a.json',
    'entity_fiche_visual_editor_contract_after_sp120.json',
    'entity_fiche_i18n_after_sp120.json',
    'graph_fiche_surface_after_sp120.json',
]

class TextifaiGraphFicheEditorSurfaceTests(unittest.TestCase):
    def test_reports_exist(self):
        for name in REPORTS:
            payload = json.loads((FIX / name).read_text(encoding='utf-8'))
            self.assertTrue(payload['visual_editor_surface'])
            self.assertTrue(payload['raw_markdown_hidden'])
            self.assertTrue(payload['technical_details_collapsed'])
            self.assertTrue(payload['local_edit_only'])
            self.assertTrue(payload['writeback_enabled'])
            self.assertTrue(payload['i18n_keys_present'])
            self.assertTrue(payload['no_source_prose'])
            self.assertTrue(payload.get('visual_mdx_editor', True))
            self.assertFalse(payload.get('textarea_raw_editor', False))
            self.assertTrue(payload.get('visual_only', True))
            self.assertTrue(payload.get('markdown_pill_removed', True))
            self.assertTrue(payload.get('wikilink_relationships', True))

    def test_graph_inspector_uses_reusable_fiche_surface(self):
        text = INSPECTOR.read_text(encoding='utf-8')
        fiche = FICHE.read_text(encoding='utf-8')
        self.assertIn('EntityFicheView', text)
        self.assertIn('stripFrontmatter', text)
        self.assertIn('details', text)
        self.assertIn("t('graph.technical_details')", text)
        self.assertIn("t('graph.fiche_local_dirty')", fiche)
        self.assertIn('MDXEditor', fiche)
        self.assertIn('EditorBoundary', fiche)
        self.assertIn('fallback={<textarea', fiche)
        self.assertNotIn('>Markdown<', fiche)
        self.assertIn('buildFicheMarkdown', text)
        self.assertIn('[[' , text)

    def test_fiche_body_preserves_authored_text_without_forced_structure(self):
        text = INSPECTOR.read_text(encoding='utf-8')
        self.assertIn('if (cleanBody) return cleanBody;', text)
        self.assertIn("`## ${t('graph.fiche_notes')}`", text)
        self.assertNotIn('const hasStructure = /(^|\\n)##\\s+/.test(cleanBody);', text)

    def test_generated_entity_body_does_not_duplicate_structured_cards(self):
        text = ENTITY_CARD.read_text(encoding='utf-8')
        self.assertNotIn('## Aliases', text)
        self.assertNotIn('## Relaciones', text)
        self.assertNotIn('## Backlinks', text)
        self.assertNotIn('## Enlaces salientes', text)

    def test_source_priority_documented(self):
        payload = json.loads((FIX / 'entity_fiche_source_priority_after_sp120.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['source_priority'][0], 'entity_card.author_markdown')
        self.assertEqual(payload['source_priority'][1], 'entity_markdown_note_body')
        self.assertEqual(payload['source_priority'][2], 'generated_author_markdown')
        self.assertEqual(payload['source_priority'][3], 'empty_author_placeholder')

    def test_graph_select_query_param_visual_test_hook(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn("get('graph_select')", text)
        self.assertIn('selectedFromUrl', text)
        self.assertIn('setSelectedGraphNodeId(firstNode.id)', text)

    def test_fiche_internal_links_are_intercepted_without_root_navigation(self):
        fiche = FICHE.read_text(encoding='utf-8')
        app = APP.read_text(encoding='utf-8')
        entity_card = ENTITY_CARD.read_text(encoding='utf-8')
        self.assertIn("closest?.('a')", fiche)
        self.assertIn('preventDefault()', fiche)
        self.assertIn('onInternalLinkClick?.(href)', fiche)
        self.assertIn('handleGraphInternalEntityLinkClick', app)
        self.assertIn("window.history.replaceState", app)
        self.assertIn("searchParams.set('graph_select'", app)
        self.assertIn('selectGraphEntityBySelectToken', app)
        self.assertIn('return f"#graph_select=', entity_card)
        self.assertNotIn('return f"/?graph_select=', entity_card)

    def test_fiche_editor_has_rich_content_classes(self):
        fiche = FICHE.read_text(encoding='utf-8')
        styles = (REPO / 'textifai/web_viewer/react_shell/src/styles.css').read_text(encoding='utf-8')
        self.assertIn('entity-fiche-editor-content', fiche)
        self.assertIn('.entity-fiche-editor-content h1', styles)
        self.assertIn('.entity-fiche-editor-content h2', styles)
        self.assertIn('.entity-fiche-editor-content ul', styles)
        self.assertIn('.entity-fiche-editor-content a', styles)
        self.assertIn('cursor: pointer', styles)
        self.assertIn('.entity-fiche-editor-content a:hover', styles)

if __name__ == '__main__':
    unittest.main()
