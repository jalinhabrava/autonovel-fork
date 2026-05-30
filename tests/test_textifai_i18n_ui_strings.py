import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
UI = REPO / 'textifai/web_viewer/react_shell/src/i18n/ui.ts'
REPORT = REPO / 'tests/fixtures/textifai/i18n/expected/ui_i18n_audit_after_sp117.json'
MODULES = [
    REPO / 'textifai/web_viewer/react_shell/src/shell/AppShell.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/shell/navigation.ts',
    REPO / 'textifai/web_viewer/react_shell/src/common/ui.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/review/ReviewQueueView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/graph/GraphView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/canon/StoryAliasView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/editor/EditorView.tsx',
    REPO / 'textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx',
]

REQUIRED_KEYS = [
    'nav.hub','nav.ingest','nav.review','nav.graph','nav.codex','nav.editor','nav.ask',
    'editor.mode.markdown','editor.mode.visual','editor.save.chapter','editor.save.dirty','editor.save.saving','editor.save.saved',
    'editor.save.conflict','editor.save.error','editor.canon_risks','editor.reanalysis.pending','editor.reanalysis.notice','editor.reanalysis.action',
    'review.open_evidence','review.accept','review.reject',
]

class TestTextifAII18nUiStrings(unittest.TestCase):
    def test_i18n_module_exists(self):
        text = UI.read_text(encoding='utf-8')
        self.assertIn("export const uiI18n", text)
        self.assertIn("fallbackLocale", text)
        self.assertIn("export function t", text)

    def test_required_keys_exist(self):
        text = UI.read_text(encoding='utf-8')
        for key in REQUIRED_KEYS:
            self.assertIn(f"'{key}'", text)

    def test_modular_shell_files_exist(self):
        for path in MODULES:
            self.assertTrue(path.exists(), str(path))

    def test_app_uses_modules(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn("./i18n/ui", text)
        self.assertIn("./shell/AppShell", text)
        self.assertIn("./modules/project/ProjectHubView", text)
        self.assertIn("./modules/ingestion/IngestionView", text)
        self.assertIn("./modules/ai/AIStudioView", text)
        self.assertIn("./modules/canon/StoryAliasView", text)

    def test_report_exists(self):
        payload = json.loads(REPORT.read_text(encoding='utf-8'))
        self.assertIn('assessment', payload)
        self.assertTrue(payload.get('no_source_prose'))

if __name__ == '__main__':
    unittest.main()
