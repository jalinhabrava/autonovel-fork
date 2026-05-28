import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
GRAPH_CANVAS = REPO / 'textifai/web_viewer/react_shell/src/components/graph/GraphCanvas.tsx'
PKG = REPO / 'textifai/web_viewer/react_shell/package.json'


class TextifAIReactForceGraphWorkspaceContracts(unittest.TestCase):
    def test_graph_canvas_uses_react_force_graph_2d(self):
        self.assertTrue(GRAPH_CANVAS.exists(), f'Missing graph canvas contract file: {GRAPH_CANVAS}')
        text = GRAPH_CANVAS.read_text(encoding='utf-8')
        self.assertIn("from 'react-force-graph-2d'", text)
        self.assertIn('ForceGraph2D', text)

    def test_graph_block_not_legacy_primary(self):
        text = APP.read_text(encoding='utf-8')
        graph_start = text.index("if (active === 'graph')")
        graph_end = text.index("if (active === 'review')")
        graph_block = text[graph_start:graph_end]
        self.assertIn('GraphCanvas', graph_block)
        self.assertNotIn('LegacyEmbed title="Graph legacy dev fallback"', graph_block)
        self.assertNotIn('LegacyEmbed title="Graph module', graph_block)

    def test_graph_toolbar_and_search_labels_exist(self):
        text = APP.read_text(encoding='utf-8')
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
            'Buscar nodo',
        ]:
            self.assertIn(label, text)

    def test_inspector_and_modal_strings_exist(self):
        text = APP.read_text(encoding='utf-8')
        for label in ['Ficha del nodo', 'Editar', 'SP-106', 'No write-back']:
            self.assertIn(label, text)

    def test_shell_package_declares_force_graph_dependency(self):
        package = json.loads(PKG.read_text(encoding='utf-8'))
        deps = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
        self.assertIn('react-force-graph-2d', deps)


if __name__ == '__main__':
    unittest.main()
