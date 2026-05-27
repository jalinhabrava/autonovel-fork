import json
import os
import re
import subprocess
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, read_note, read_project

REPO = Path(__file__).resolve().parents[1]
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
INDEX_HTML = REPO / 'textifai/web_viewer/static/index.html'
PROJECT_READER = REPO / 'textifai/web_viewer/project_reader.py'
PACKAGE_JSON = REPO / 'package.json'
PACKAGE_LOCK = REPO / 'package-lock.json'
EXPECTED = REPO / 'tests/fixtures/textifai/author_workspace_stabilization/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-101_author-workspace-stabilization'
PRIVATE_SP102 = REPO / 'docs/handoffs/private/safepoint-102_node-selection-inspector-hydration'
RUNTIME_ROOT = Path('/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z')
PROJECT_ID = 'tmp__textifai_private_provider_runs__sp096_vaerl_entity_quality_viewer_ux_patch__20260527T124326Z__viewer_project'

REPORTS = [
    'sidebar_project_load_audit_after_sp100.json',
    'spanish_i18n_runtime_audit_after_sp100.json',
    'canonical_graph_kind_filter_audit_after_sp100.json',
    'default_author_graph_scope_after_sp100.json',
    'graph_v3_density_layout_audit_after_sp100.json',
    'node_content_hydration_audit_after_sp100.json',
    'author_workspace_stabilization_decision_after_sp100.json',
]

SP102_REPORTS = [
    'node_selection_click_drag_audit_after_sp101.json',
    'inspector_hydration_fallback_after_sp101.json',
    'sera_ren_node_selection_after_sp101.json',
    'node_selection_inspector_decision_after_sp101.json',
]

def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

def viewer_project():
    catalog = ProjectCatalog([RUNTIME_ROOT])
    return catalog.get_project(PROJECT_ID)

class TextifAIAuthorWorkspaceStabilizationTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_no_project_title_missing_helper(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('function projectTitle', text)
        self.assertNotIn('projectTitle is not defined', text)

    def test_project_loading_exposes_work_language(self):
        payload = read_project(viewer_project())
        self.assertEqual(payload['project']['work']['language'], 'es')
        self.assertEqual(payload['canon']['work']['language'], 'es')

    def test_runtime_spanish_defaults_to_es(self):
        report = read_json('spanish_i18n_runtime_audit_after_sp100.json')
        self.assertEqual(report['detected_locale_for_runtime'], 'es')
        self.assertTrue(report['primary_labels_spanish'])

    def test_primary_nav_core_labels_spanish(self):
        html = INDEX_HTML.read_text(encoding='utf-8')
        js = APP_JS.read_text(encoding='utf-8')
        self.assertIn('Resumen', html)
        self.assertIn('Grafo', html)
        self.assertIn('showAllNodes: "Mostrar todo"', js)
        self.assertIn('openInCanon: "Abrir en canon"', js)

    def test_canonical_graph_kind_for_sera_ren(self):
        graph = read_project(viewer_project())['graph']
        by_id = {node['id']: node for node in graph['nodes']}
        self.assertEqual(by_id['Characters/Sera.md']['display_kind'], 'character')
        self.assertEqual(by_id['Concepts/Sera.md']['display_kind'], 'character')
        self.assertEqual(by_id['Characters/Ren.md']['display_kind'], 'character')
        self.assertEqual(by_id['Concepts/Ren.md']['display_kind'], 'character')
        self.assertEqual(graph['canonical_redirects']['Concepts/Sera.md'], 'Characters/Sera.md')
        self.assertEqual(graph['canonical_redirects']['Concepts/Ren.md'], 'Characters/Ren.md')

    def test_hiding_concepts_keeps_canonical_sera_ren(self):
        report = read_json('canonical_graph_kind_filter_audit_after_sp100.json')
        self.assertTrue(report['sera_visible_when_concepts_hidden'])
        self.assertTrue(report['ren_visible_when_concepts_hidden'])
        self.assertTrue(report['filters_use_canonical_kind'])
        self.assertTrue(report['redirected_duplicates_collapsed_by_default'])

    def test_default_graph_scope(self):
        report = read_json('default_author_graph_scope_after_sp100.json')
        self.assertEqual(report['full_node_count'], 446)
        self.assertEqual(report['full_edge_count'], 582)
        self.assertLess(report['default_node_count'], report['full_node_count'])
        self.assertGreaterEqual(report['default_node_count'], 40)
        self.assertLessEqual(report['default_node_count'], 80)
        self.assertTrue(report['show_all_toggle_present'])
        self.assertTrue(report['redirected_duplicates_collapsed'])

    def test_show_all_toggle_exists(self):
        html = INDEX_HTML.read_text(encoding='utf-8')
        js = APP_JS.read_text(encoding='utf-8')
        self.assertIn('id="show-all-nodes"', html)
        self.assertIn('label-show-all-nodes', html)
        self.assertIn('showAllNodes', js)

    def test_d3_force_still_active_no_package_change(self):
        text = APP_JS.read_text(encoding='utf-8')
        for token in ['forceSimulation', 'forceCenter', 'forceManyBody', 'forceLink', 'forceCollide']:
            self.assertIn(token, text)
        package = json.loads(PACKAGE_JSON.read_text(encoding='utf-8'))
        self.assertEqual(set(package.get('dependencies', {}).keys()), {'d3-force'})
        self.assertIn('d3-force', PACKAGE_LOCK.read_text(encoding='utf-8'))

    def test_summary_facts_hydration_for_sera_ren(self):
        graph = read_project(viewer_project())['graph']
        by_id = {node['id']: node for node in graph['nodes']}
        self.assertTrue(by_id['Characters/Sera.md']['summary_excerpt'])
        self.assertGreaterEqual(by_id['Characters/Sera.md']['key_facts_count'], 4)
        self.assertTrue(by_id['Characters/Ren.md']['summary_excerpt'])
        self.assertGreaterEqual(by_id['Characters/Ren.md']['key_facts_count'], 4)
        note = read_note(viewer_project(), 'Characters/Sera.md')
        self.assertTrue(note['content_hydration']['summary_excerpt'])


    def test_sp102_reports_parse(self):
        for name in SP102_REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_graph_click_drag_threshold_and_loading_state_present(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('const GRAPH_CLICK_DRAG_THRESHOLD_PX = 5;', text)
        self.assertIn('startX: event.clientX', text)
        self.assertIn('startY: event.clientY', text)
        self.assertIn('Math.hypot(deltaX, deltaY)', text)
        self.assertIn('state.graphDidDragNode = distance >= GRAPH_CLICK_DRAG_THRESHOLD_PX', text)
        self.assertIn("$(\"graph-detail\").innerHTML = `<p class=\"muted\">${escapeHtml(t('loadingNodeDetail'))}</p>`;", text)

    def test_canonical_selection_and_note_path_priority_present(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('const canonicalNodeId = resolveCanonicalNodeId(nodeId) || nodeId;', text)
        self.assertIn('const canonicalNotePath = resolveCanonicalNotePath(node.canonical_note_path || node.note_path || "");', text)
        self.assertIn('const canonicalPath = resolveCanonicalNotePath(path);', text)
        self.assertIn('const summaryNode = (state.current?.graph?.nodes || []).find((item) => item.id === state.selectedGraphNodeId) || {};', text)

    def test_inspector_hydration_fallback_strings_present(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('loadingNodeDetail: "Cargando ficha..."', text)
        self.assertIn('loadingNodeDetail: "Loading node card..."', text)
        self.assertIn('noteLoadFallback: "No se pudo cargar la nota completa. Mostrando resumen disponible."', text)
        self.assertIn('noteLoadFallback: "Could not load full note. Showing available summary instead."', text)
        self.assertIn("renderGraphNodeHydrationFallback(node, { warning: t('noteLoadFallback') })", text)

    def test_hydration_fallback_uses_summary_and_facts(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('function renderGraphNodeHydrationFallback(node, { warning = "" } = {}) {', text)
        self.assertIn("node.summary_excerpt || t('noSummary')", text)
        self.assertIn('const facts = (node.key_facts_preview || []).slice(0, 8);', text)
        self.assertIn('node.relationship_count', text)
        self.assertIn('node.evidence_count', text)

    def test_sera_ren_reports_confirm_canonical_selection(self):
        report = read_json('sera_ren_node_selection_after_sp101.json')
        self.assertEqual(report['sera_expected_note_path'], 'Characters/Sera.md')
        self.assertEqual(report['ren_expected_note_path'], 'Characters/Ren.md')
        self.assertTrue(report['canonical_note_path_preferred'])
        self.assertTrue(report['inspector_leaves_empty_state'])

    def test_no_provider_writeback_private_leaks(self):
        for name in REPORTS + SP102_REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('write_back_performed: true', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)

    def test_private_handoff_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)
        result_sp102 = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_SP102 / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result_sp102.stdout)

if __name__ == '__main__':
    unittest.main()
