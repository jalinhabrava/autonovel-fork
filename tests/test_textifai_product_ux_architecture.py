import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
INDEX_HTML = REPO / 'textifai/web_viewer/static/index.html'
STYLES = REPO / 'textifai/web_viewer/static/styles.css'
EXPECTED = REPO / 'tests/fixtures/textifai/product_ux_architecture/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-104_product-dev-mode-overview-canon'
PACKAGE_JSON = REPO / 'package.json'
PACKAGE_LOCK = REPO / 'package-lock.json'

REPORTS = [
    'product_vs_dev_mode_audit_after_sp102.json',
    'overview_redesign_after_sp102.json',
    'dev_debug_surface_after_sp102.json',
    'canon_entities_redesign_after_sp102.json',
    'view_in_graph_contract_after_sp102.json',
    'canon_rows_selection_after_sp102.json',
    'review_queue_product_tone_after_sp102.json',
    'merge_canonicalization_workflow_after_sp102.json',
    'editable_markdown_workflow_after_sp102.json',
    'product_ux_architecture_decision_after_sp102.json',
]

FORBIDDEN_OVERVIEW_TERMS = [
    'renderSemanticHealth(state.current.health || {})',
    'renderIngestionWizard()',
    'renderCompareRunsPanel()',
    'renderEntityTriagePanel()',
]


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIProductUXArchitectureTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_overview_product_mode_excludes_debug_renderers(self):
        text = APP_JS.read_text(encoding='utf-8')
        start = text.index('function renderOverview()')
        end = text.index('function overviewPrimaryAction')
        overview = text[start:end]
        for term in FORBIDDEN_OVERVIEW_TERMS:
            self.assertNotIn(term, overview)
        self.assertIn("t('storyStatus')", overview)
        self.assertIn("t('pendingDecisions')", overview)
        self.assertIn("t('mainEntities')", overview)
        self.assertIn("t('graphReadyNatural', { nodes: fmtCount(visibleGraph.nodes.length) })", overview)

    def test_dev_surface_contains_technical_diagnostics(self):
        text = APP_JS.read_text(encoding='utf-8')
        start = text.index('function renderArtifacts()')
        end = text.index('async function openArtifact')
        dev = text[start:end]
        self.assertIn("t('devMode')", dev)
        self.assertIn("renderSemanticHealth(state.current.health || {})", dev)
        self.assertIn('renderIngestionWizard()', dev)
        self.assertIn('renderCompareRunsPanel()', dev)
        self.assertIn('renderEntityTriagePanel()', dev)

    def test_canon_entities_rows_are_clickable_and_detail_updates(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn("canonEntities: \"Canon / Entidades\"", text)
        self.assertIn('class="canon-workspace"', text)
        self.assertIn('class="panel canon-side-detail"', text)
        self.assertIn('data-canon-select="${escapeHtml(key)}"', text)
        self.assertIn('function renderCanonEntityDetail(entity) {', text)
        self.assertIn('state.selectedCanonEntityKey = normalizeKey(key);', text)
        self.assertIn('data-canon-graph="${escapeHtml(key)}"', text)
        self.assertIn('data-canon-note="${escapeHtml(key)}"', text)
        self.assertIn('disabled title="${escapeHtml(t(\'futurePhaseDisabled\'))}"', text)

    def test_view_in_graph_contract_helper(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('function navigateToGraphNode(nodeOrPathOrId, { from = "Viewer" } = {}) {', text)
        self.assertIn('const canonicalNodeId = resolveCanonicalNodeId(node.canonical_node_id || node.id || node.note_path || node.label);', text)
        self.assertIn('const revealNotice = ensureGraphNodeVisible(canonicalNode);', text)
        self.assertIn('setView("graph");', text)
        self.assertIn('renderGraph();', text)
        self.assertIn('focusGraphNode(canonicalNode.id);', text)
        self.assertIn('selectGraphNode(canonicalNode.id, { pushHistory: true, renderDetail: true });', text)
        self.assertIn("t('graphNodeMissing')", text)
        self.assertIn('function ensureGraphNodeVisible(node) {', text)
        self.assertIn('$("show-all-nodes").checked = true;', text)
        self.assertIn('function focusGraphNode(nodeId) {', text)

    def test_review_queue_product_tone(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn("decisionQueueTitle: \"Cola de decisiones\"", text)
        self.assertIn("decisionQueueSubtitle: \"Items agrupados por decisión narrativa, evidencia e impacto.\"", text)
        self.assertIn("t('suggestedMerges')", text)
        self.assertIn("t('ambiguousEntities')", text)
        self.assertIn("t('uncertainRelationships')", text)

    def test_styles_support_product_layouts(self):
        css = STYLES.read_text(encoding='utf-8')
        self.assertIn('.overview-grid', css)
        self.assertIn('.canon-workspace', css)
        self.assertIn('.canon-side-detail', css)
        self.assertIn('.canon-row', css)

    def test_reports_capture_contracts(self):
        product = read_json('product_vs_dev_mode_audit_after_sp102.json')
        self.assertTrue(product['no_technical_garbage_in_author_overview'])
        self.assertEqual(product['dev_access_path'], 'tab-dev')
        graph = read_json('view_in_graph_contract_after_sp102.json')
        self.assertTrue(graph['helper_exists'])
        self.assertTrue(graph['canonical_resolution'])
        self.assertTrue(graph['switches_to_graph'])
        self.assertTrue(graph['selects_node'])
        self.assertTrue(graph['handles_hidden_by_scope'])
        merge = read_json('merge_canonicalization_workflow_after_sp102.json')
        self.assertIn('abuelo', ' '.join(merge['sp105_required_cases']['grandfather_variants']))
        self.assertIn('Sera', merge['sp105_required_cases']['sera_variants'])
        markdown = read_json('editable_markdown_workflow_after_sp102.json')
        self.assertFalse(markdown['write_back'])

    def test_no_provider_package_changes_private_leaks(self):
        package_status = subprocess.run(['git', 'status', '--short', 'package.json', 'package-lock.json'], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertEqual(package_status.stdout.strip(), '')
        for name in REPORTS:
            text = (EXPECTED / name).read_text(encoding='utf-8')
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('final_prompt_sent', text)
            self.assertNotIn('write_back_performed: true', text)
            secret = os.environ.get('DEEPSEEK_API_KEY')
            if secret:
                self.assertNotIn(secret, text)
        self.assertTrue(PACKAGE_JSON.exists())
        self.assertTrue(PACKAGE_LOCK.exists())

    def test_private_handoff_path_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
