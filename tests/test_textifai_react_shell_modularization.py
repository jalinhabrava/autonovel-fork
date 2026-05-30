import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
NAV = REPO / 'textifai/web_viewer/react_shell/src/shell/navigation.ts'
REQUIRED_MODULES = [
    REPO / 'textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/review/ReviewQueueView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/graph/GraphView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/editor/EditorView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx',
]
MODULE_MAP_REPORT = REPO / 'tests/fixtures/textifai/react_shell_modularization/expected/react_shell_module_map_after_sp117.json'
APP_ROLE_REPORT = REPO / 'tests/fixtures/textifai/react_shell_modularization/expected/app_tsx_decomposition_after_sp117.json'

class TestTextifAIReactShellModularization(unittest.TestCase):
    def test_required_modules_exist(self):
        for path in REQUIRED_MODULES:
            self.assertTrue(path.exists(), str(path))

    def test_navigation_exists(self):
        text = NAV.read_text(encoding='utf-8')
        self.assertIn('export const screens', text)
        self.assertIn("id: 'hub'", text)
        self.assertIn("id: 'graph'", text)
        self.assertIn("id: 'editor'", text)

    def test_app_is_composer_like(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('./shell/AppShell', text)
        self.assertIn('./modules/project/ProjectHubView', text)
        self.assertIn('./modules/ingestion/IngestionView', text)
        self.assertIn('./modules/review/ReviewQueueView', text)
        self.assertIn('./modules/graph/GraphView', text)
        self.assertIn('./modules/canon/CanonVaerlView', text)
        self.assertIn('./modules/editor/EditorView', text)
        self.assertIn('./modules/ai/AIStudioView', text)

    def test_reports_exist(self):
        for report_path in [MODULE_MAP_REPORT, APP_ROLE_REPORT]:
            payload = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)
            self.assertTrue(payload.get('no_source_prose'))

if __name__ == '__main__':
    unittest.main()
