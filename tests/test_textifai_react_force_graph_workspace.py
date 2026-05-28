import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
GRAPH_CANVAS = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx'
GRAPH_TOOLBAR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx'
GRAPH_INSPECTOR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx'
GRAPH_MODAL = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx'
PKG = REPO / 'textifai/web_viewer/react_shell/package.json'


class TextifAIReactForceGraphWorkspaceTests(unittest.TestCase):
    def test_graph_uses_force_graph_library(self):
        self.assertTrue(GRAPH_CANVAS.exists())
        text = GRAPH_CANVAS.read_text(encoding='utf-8')
        self.assertIn("from 'react-force-graph-2d'", text)
        self.assertIn('ForceGraph2D', text)

    def test_graph_no_legacy_embed_primary(self):
        text = APP.read_text(encoding='utf-8')
        graph_start = text.index("if (active === 'graph')")
        graph_end = text.index("if (active === 'review')")
        graph_block = text[graph_start:graph_end]
        self.assertNotIn('LegacyEmbed', graph_block)

    def test_toolbar_filters_and_search_exist(self):
        text = GRAPH_TOOLBAR.read_text(encoding='utf-8')
        for label in [
            'Todo',
            'Capítulos',
            'Personajes',
            'Lugares',
            'Objetos',
            'Eventos',
            'Conceptos',
            'Revisión',
            'Solo relacionados',
        ]:
            self.assertIn(label, text)
        self.assertIn('Buscar nodo', text)

    def test_inspector_and_edit_draft_modal_exist(self):
        inspector = GRAPH_INSPECTOR.read_text(encoding='utf-8')
        modal = GRAPH_MODAL.read_text(encoding='utf-8')
        self.assertIn('Ficha del nodo', inspector)
        self.assertIn('Editar', inspector)
        self.assertIn('SP-106', modal)
        self.assertIn('No write-back', modal)

    def test_dependency_scope_shell_only(self):
        package = json.loads(PKG.read_text(encoding='utf-8'))
        self.assertIn('react-force-graph-2d', package['dependencies'])


if __name__ == '__main__':
    unittest.main()
