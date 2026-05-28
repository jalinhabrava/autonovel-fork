import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
API = REPO / 'textifai/web_viewer/react_shell/src/api.ts'
PKG = REPO / 'textifai/web_viewer/react_shell/package.json'
ROOT_PKG = REPO / 'package.json'
ROOT_LOCK = REPO / 'package-lock.json'
EXPECTED = REPO / 'tests/fixtures/textifai/react_ui_target_parity/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-105c_react-ui-target-parity'
HANDOFF = REPO / 'docs/handoffs/safepoint-105c_react-ui-target-parity.md'

REPORTS = [
    'react_ui_target_parity_audit_after_sp105b.json',
    'react_shell_design_system_after_sp105b.json',
    'react_screen_parity_after_sp105b.json',
    'legacy_embed_boundary_after_sp105b.json',
    'react_ui_build_validation_after_sp105b.json',
    'react_ui_target_parity_decision_after_sp105b.json',
]

def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class TextifAIReactUITargetParityTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_shell_uses_target_design_classes(self):
        text = APP.read_text(encoding='utf-8')
        for cls in [
            'min-h-screen h-screen bg-neutral-100 text-neutral-900 p-2 md:p-4 overflow-hidden',
            'mx-auto w-full max-w-none h-full rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200',
            'border-b border-neutral-200 px-5 py-4 bg-neutral-50',
            'grid grid-cols-12 h-[calc(100%-73px)] min-h-0',
            'col-span-12 md:col-span-2 border-r border-neutral-200 bg-neutral-50 p-3 flex min-h-0 flex-col',
            'col-span-12 md:col-span-10 bg-white min-h-0 overflow-y-auto',
        ]:
            self.assertIn(cls, text)

    def test_sidebar_nav_contains_target_screens(self):
        text = APP.read_text(encoding='utf-8')
        for label in ['Project Hub', 'Ingestion', 'Codex / VaERL', 'Graph', 'Review Queue', 'Editor', 'Story Bible', 'Ask Canon']:
            self.assertIn(label, text)

    def test_lucide_icons_imported_and_used(self):
        text = APP.read_text(encoding='utf-8')
        for icon in ['BookOpen', 'Upload', 'Network', 'GitBranch', 'Inbox', 'PenLine', 'FileText', 'MessageSquareText']:
            self.assertIn(icon, text)
        package = json.loads(PKG.read_text(encoding='utf-8'))
        self.assertIn('lucide-react', package['dependencies'])
        self.assertIn('framer-motion', package['dependencies'])

    def test_design_system_components_exist(self):
        text = APP.read_text(encoding='utf-8')
        for fn in ['function Shell', 'function TopBar', 'function Button', 'function Metric', 'function SidebarNav', 'function StatusChip', 'function ProjectRow', 'function DecisionCard', 'function EntityRecordTable', 'function InspectorCard']:
            self.assertIn(fn, text)

    def test_black_sidebar_not_primary_shell(self):
        text = APP.read_text(encoding='utf-8')
        shell_start = text.index('function Shell')
        shell_end = text.index('function SidebarNav')
        shell = text[shell_start:shell_end]
        self.assertIn('bg-neutral-50', shell)
        self.assertNotIn('bg-black text-white', shell)

    def test_legacy_embed_boundary_documented_and_used(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('function LegacyEmbed', text)
        self.assertIn("?embed=1", text)
        self.assertIn('Story Bible transitional legacy boundary', text)
        self.assertIn('Graph legacy dev fallback', text)
        report = read_json('legacy_embed_boundary_after_sp105b.json')
        self.assertTrue(report['legacy_not_primary_product_shell'])
        self.assertIn('Graph', report['remaining_legacy_embeds'])

    def test_api_adapters_preserve_existing_endpoints(self):
        text = API.read_text(encoding='utf-8')
        for endpoint in ['/api/projects', '/graph', '/note?path=', '/artifacts', '/api/ingestion/config', '/api/ingestion/jobs']:
            self.assertIn(endpoint, text)

    def test_no_provider_writeback_or_open_design_runtime_dependency(self):
        decision = read_json('react_ui_target_parity_decision_after_sp105b.json')
        self.assertFalse(decision['provider_calls'])
        self.assertFalse(decision['write_back'])
        package = json.loads(PKG.read_text(encoding='utf-8'))
        all_deps = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
        self.assertNotIn('open-design', all_deps)
        self.assertNotIn('deepseek', json.dumps(package).lower())
        root_diff = subprocess.run(['git', 'diff', '--exit-code', '--', str(ROOT_PKG.relative_to(REPO)), str(ROOT_LOCK.relative_to(REPO))], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(root_diff.returncode, 0, root_diff.stdout + root_diff.stderr)

    def test_node_modules_not_staged(self):
        result = subprocess.run(['git', 'status', '--short', 'node_modules', 'textifai/web_viewer/react_shell/node_modules'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), '')

    def test_handoff_and_private_path(self):
        self.assertTrue(HANDOFF.exists())
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)

if __name__ == '__main__':
    unittest.main()
