import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
API = REPO / 'textifai/web_viewer/react_shell/src/api.ts'
PKG = REPO / 'textifai/web_viewer/react_shell/package.json'
EXPECTED = REPO / 'tests/fixtures/textifai/react_workspace_real_project/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-105d_react-workspace-real-project-native-graph'
HANDOFF = REPO / 'docs/handoffs/safepoint-105d_react-workspace-real-project-native-graph.md'

REPORTS = [
    'real_20ch_project_loading_audit_after_sp105c.json',
    'react_project_selection_after_sp105c.json',
    'fullscreen_workspace_layout_after_sp105c.json',
    'user_settings_flow_after_sp105c.json',
    'editor_chapter_only_fullscreen_after_sp105c.json',
    'native_react_graph_surface_after_sp105c.json',
    'node_note_edit_affordance_after_sp105c.json',
    'story_bible_legacy_boundary_after_sp105c.json',
    'react_i18n_consistency_after_sp105c.json',
    'react_workspace_real_project_decision_after_sp105c.json',
]

def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class TextifAIReactWorkspaceRealProjectTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            self.assertIn('assessment', read_json(name), name)

    def test_project_loading_audit_expects_20_or_blocks(self):
        audit = read_json('real_20ch_project_loading_audit_after_sp105c.json')
        self.assertEqual(audit['expected_chapters'], 20)
        if audit['loaded_chapters'] < 20:
            self.assertTrue(audit['blocked_if_missing'])
            self.assertFalse(audit['real_runtime_found'])
            self.assertIn('Restaurar runtime privado SP-095', ' '.join(audit['remediation_plan']))

    def test_ui_does_not_silently_prefer_2ch_when_20ch_exists(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('function choosePreferredProject', text)
        self.assertIn('chapters >= 20 ? 10000 : 0', text)
        self.assertIn('Proyecto reducido detectado', text)
        report = read_json('react_project_selection_after_sp105c.json')
        self.assertFalse(report['auto_select_wrong_minimal_when_real_exists'])

    def test_fullscreen_workspace_layout(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('min-h-screen h-screen bg-neutral-100 text-neutral-900 p-2 md:p-4 overflow-hidden', text)
        self.assertIn('mx-auto w-full max-w-none h-full rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200', text)
        self.assertIn('grid grid-cols-12 h-[calc(100%-73px)] min-h-0', text)
        self.assertIn('overflow-y-auto', text)
        self.assertNotIn('mx-auto max-w-7xl rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200', text)

    def test_user_card_and_settings_modal_exist(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('Autor local', text)
        self.assertIn('function SettingsModal', text)
        self.assertIn('Ajustes', text)
        self.assertIn('Apariencia', text)
        self.assertIn('Idioma', text)
        self.assertIn('Proyecto', text)
        self.assertIn('Dev/debug', text)
        shell = text[text.index('function Shell'):text.index('function SettingsModal')]
        self.assertNotIn('Settings size={', shell)
        report = read_json('user_settings_flow_after_sp105c.json')
        self.assertFalse(report['top_right_settings_primary'])

    def test_editor_chapter_only_fullscreen_context(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('function isChapterNote', text)
        self.assertIn('const chapterNotes = useMemo(() => (projectDetail?.notes || []).filter(isChapterNote)', text)
        self.assertIn('const [editorChapterRailCollapsed, setEditorChapterRailCollapsed] = useState(false);', text)
        self.assertIn('Añadir capítulo', text)
        self.assertIn('Pantalla completa', text)
        self.assertIn("editorChapterRailCollapsed ? 'Mostrar' : 'Ocultar'", text)
        self.assertIn("editorFullscreen && editorChapterRailCollapsed ? 'col-span-12 lg:col-span-1", text)
        self.assertIn("editorFullscreen && editorChapterRailCollapsed ? 'col-span-12 lg:col-span-8'", text)
        self.assertIn('Panel derecho retenido también en fullscreen', text)
        self.assertIn('No write-back en SP-105D', text)
        editor_start = text.index("if (active === 'editor')")
        editor_end = text.index("if (active === 'story')")
        editor_block = text[editor_start:editor_end]
        self.assertNotIn('TopBar title="Editor" subtitle="Solo capítulos/manuscrito. Fichas primarias viven en Codex, Graph o Story Bible." actions={<><Button onClick={() => setEditDraft', editor_block)
        self.assertIn('flex items-center justify-between gap-3', editor_block)
        report = read_json('editor_chapter_only_fullscreen_after_sp105c.json')
        self.assertTrue(report['editor_items_are_chapters_only'])
        self.assertFalse(report['write_back'])

    def test_graph_native_not_legacy_primary(self):
        text = APP.read_text(encoding='utf-8')
        graph_start = text.index("if (active === 'graph')")
        graph_end = text.index("if (active === 'review')")
        graph_block = text[graph_start:graph_end]
        self.assertIn('GraphCanvas', graph_block)
        self.assertIn('Exploración visual author-facing con física viva e inspector editorial.', graph_block)
        self.assertIn('setSelectedGraphNodeId', text)
        self.assertIn('Ficha del nodo', text)
        self.assertIn('Editar', text)
        self.assertNotIn('LegacyEmbed', graph_block)
        self.assertNotIn('Graph module (legacy runtime boundary)', graph_block)
        report = read_json('native_react_graph_surface_after_sp105c.json')
        self.assertTrue(report['legacy_embed_removed_from_primary_graph'])
        self.assertTrue(report['graph_fetches_real_payload'])

    def test_node_edit_affordance_no_writeback(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn('Draft local/read-only', text)
        self.assertIn('Guardar cambios llega con drafts/patch queue', text)
        report = read_json('node_note_edit_affordance_after_sp105c.json')
        self.assertFalse(report['write_back'])

    def test_api_graph_payload_types_and_endpoints_preserved(self):
        text = API.read_text(encoding='utf-8')
        self.assertIn('export type GraphNode', text)
        self.assertIn('export type GraphPayload', text)
        for endpoint in ['/api/projects', '/graph', '/note?path=', '/artifacts']:
            self.assertIn(endpoint, text)

    def test_no_provider_calls_writeback_or_open_design_runtime_dependency(self):
        decision = read_json('react_workspace_real_project_decision_after_sp105c.json')
        self.assertFalse(decision['provider_calls'])
        self.assertFalse(decision['write_back'])
        package = json.loads(PKG.read_text(encoding='utf-8'))
        deps = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
        self.assertNotIn('open-design', deps)
        self.assertNotIn('deepseek', json.dumps(package).lower())

    def test_node_modules_not_staged_and_private_gitignored(self):
        result = subprocess.run(['git', 'status', '--short', 'node_modules', 'textifai/web_viewer/react_shell/node_modules'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), '')
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', ignore.stdout)
        self.assertTrue(HANDOFF.exists())

if __name__ == '__main__':
    unittest.main()
