import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / 'textifai/web_viewer/static/index.html'
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
STYLES = REPO / 'textifai/web_viewer/static/styles.css'
REACT_PACKAGE = REPO / 'textifai/web_viewer/react_shell/package.json'
REACT_APP = REPO / 'textifai/web_viewer/static/react-shell/app.js'
REACT_CSS = REPO / 'textifai/web_viewer/static/react-shell/app.css'
HANDOFF = REPO / 'docs/handoffs/safepoint-105b_react-ui-shell-migration.md'

class TextifAIReactShellMigrationTests(unittest.TestCase):
    def test_react_shell_files_exist(self):
        self.assertTrue(REACT_PACKAGE.exists())
        self.assertTrue(REACT_APP.exists())
        self.assertTrue(REACT_CSS.exists())

    def test_root_index_supports_react_and_legacy(self):
        text = INDEX.read_text(encoding='utf-8')
        self.assertIn('id="react-root"', text)
        self.assertIn('id="legacy-root"', text)
        self.assertIn("document.documentElement.dataset.ui = legacyMode ? 'legacy' : 'react';", text)
        self.assertIn("import('/react-shell/app.js')", text)
        self.assertIn('id="tab-graph"', text)

    def test_legacy_runtime_supports_embed_project_view_boot(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn("const BOOT_EMBED = BOOT_PARAMS.get('embed') === '1';", text)
        self.assertIn("const BOOT_PROJECT_ID = BOOT_PARAMS.get('project') || '';", text)
        self.assertIn("const BOOT_VIEW = BOOT_PARAMS.get('view') || '';", text)
        self.assertIn("if (document.documentElement.dataset.ui === 'legacy')", text)
        self.assertIn("if (BOOT_EMBED) document.body.classList.add('embedded-legacy');", text)

    def test_embedded_legacy_css_exists(self):
        css = STYLES.read_text(encoding='utf-8')
        self.assertIn('body.embedded-legacy .sidebar', css)
        self.assertIn('body.embedded-legacy .project-header', css)

    def test_root_package_files_unchanged(self):
        result = subprocess.run(['git', 'diff', '--exit-code', '--', 'package.json', 'package-lock.json'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_react_shell_package_has_minimal_stack(self):
        payload = json.loads(REACT_PACKAGE.read_text(encoding='utf-8'))
        self.assertEqual(payload['dependencies']['react'], '^18.3.1')
        self.assertEqual(payload['dependencies']['react-dom'], '^18.3.1')
        self.assertIn('tailwindcss', payload['devDependencies'])
        self.assertIn('typescript', payload['devDependencies'])
        self.assertIn('vite', payload['devDependencies'])

    def test_handoff_exists(self):
        self.assertTrue(HANDOFF.exists())

    def test_projecthub_and_ingestion_avoid_neutral_warm_regressions(self):
        targets = [
            REPO / 'textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx',
            REPO / 'textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx',
        ]
        forbidden = ('bg-white', 'bg-neutral-', 'border-neutral-', 'text-neutral-')
        for path in targets:
            text = path.read_text(encoding='utf-8')
            for token in forbidden:
                self.assertNotIn(token, text, f'{path.name} still contains {token}')

if __name__ == '__main__':
    unittest.main()
