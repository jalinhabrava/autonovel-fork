import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP_JS = REPO / 'textifai/web_viewer/static/app.js'
INDEX_HTML = REPO / 'textifai/web_viewer/static/index.html'
EXPECTED = REPO / 'tests/fixtures/textifai/review_workspace_cleanup/expected'
PRIVATE = REPO / 'docs/handoffs/private/safepoint-105a_review-workspace-cleanup'
PACKAGE_JSON = REPO / 'package.json'
PACKAGE_LOCK = REPO / 'package-lock.json'

REPORTS = [
    'open_design_status_after_sp104.json',
    'review_queue_author_facing_after_sp104.json',
    'review_decision_item_contract_after_sp104.json',
    'review_actions_contract_after_sp104.json',
    'review_product_vs_dev_details_after_sp104.json',
    'product_naming_cleanup_after_sp104.json',
    'open_project_workspace_flow_after_sp104.json',
    'layer_boundaries_saas_plan_after_sp104.json',
    'review_workspace_cleanup_decision_after_sp104.json',
]

FORBIDDEN_PRIMARY_REVIEW_TERMS = [
    'Source → graph',
    'Target → graph',
    'Source → canon',
    'Target → canon',
    'Open canon',
    'Future viewer actions',
    'inspect evidence only',
    'Showing ${countRenderedReviewItems',
    'visible grouped entries',
    'Candidates: not available',
    'Evidence: not available',
]

RAW_DEBUG_TERMS = [
    'review_insufficient_evidence',
    'relationship_gap',
    'signalTier',
    'candidateStatus',
    'semanticValue',
    'surfaceType',
    'languageHint',
]


def read_json(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIReviewWorkspaceCleanupTests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = read_json(name)
            self.assertIn('assessment', payload, name)

    def test_review_decision_item_contract_exists(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('function buildReviewDecisionItems(rawReviewItems, context = {}) {', text)
        self.assertIn('function buildReviewDecisionItem(item, index, _context = {}) {', text)
        self.assertIn('plain_language_issue', text)
        self.assertIn('why_it_matters', text)
        self.assertIn('evidence_summary', text)
        self.assertIn('affected_entities', text)
        self.assertIn('technical_details', text)
        contract = read_json('review_decision_item_contract_after_sp104.json')
        self.assertEqual(contract['contract_name'], 'ReviewDecisionItem')
        self.assertTrue(contract['maps_raw_review_items'])

    def test_review_product_mode_uses_author_facing_labels(self):
        text = APP_JS.read_text(encoding='utf-8')
        start = text.index('function renderReview()')
        end = text.index('function applyReviewDecisionQuickFilter')
        render_review = text[start:end]
        self.assertIn("t('decisionQueueTitle')", render_review)
        self.assertIn("t('visibleDecisions'", render_review)
        self.assertIn('renderReviewDecisionCard(decision, index)', render_review)
        self.assertNotIn('renderReviewPresentationGroups', render_review)
        self.assertNotIn('renderReviewCandidateDrilldown', render_review)
        for term in FORBIDDEN_PRIMARY_REVIEW_TERMS:
            self.assertNotIn(term, render_review)

    def test_raw_internal_names_are_not_primary_review_content(self):
        text = APP_JS.read_text(encoding='utf-8')
        start = text.index('function renderReviewDecisionCard')
        end = text.index('function renderReview()')
        card = text[start:end]
        for term in RAW_DEBUG_TERMS:
            self.assertNotIn(term, card)
        self.assertNotIn('not available', card)
        self.assertIn('renderReviewTechnicalDetails(decision)', card)

    def test_review_actions_are_author_facing_and_reuse_graph_contract(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('function buildReviewActions({ source, target, candidates, evidence }) {', text)
        for label in [
            "viewEvidence",
            "openSourceEntity",
            "openRelatedEntity",
            "viewRelationshipInGraph",
            "viewInCanonEntities",
            "markCorrect",
            "markFalsePositive",
            "leaveForLater",
        ]:
            self.assertIn(f"t('{label}')", text)
        self.assertIn('data-review-graph-node', text)
        self.assertIn('navigateToGraphNode(term, { from: "Review Queue" });', text)
        self.assertNotIn('data-review-graph="${escapeHtml(item.source_entity)}">Source → graph</button>', text)

    def test_technical_details_collapsed_or_dev_and_not_available_hidden(self):
        text = APP_JS.read_text(encoding='utf-8')
        self.assertIn('showTechnicalDetails: false', text)
        self.assertIn('function renderReviewTechnicalDetails(decision) {', text)
        self.assertIn('class="technical-details review-technical-details"', text)
        self.assertIn("t('technicalDetailsCollapsed')", text)
        self.assertIn('${state.showTechnicalDetails ? `', text)
        report = read_json('review_product_vs_dev_details_after_sp104.json')
        self.assertTrue(report['technical_details_collapsed'])
        self.assertFalse(report['not_available_visible_in_product'])

    def test_settings_button_opens_real_modal(self):
        index = INDEX_HTML.read_text(encoding='utf-8')
        app = APP_JS.read_text(encoding='utf-8')
        self.assertIn('id="settings-modal"', index)
        self.assertIn('class="settings-backdrop"', index)
        self.assertIn('id="settings-body"', index)
        self.assertIn('function openSettingsModal()', app)
        self.assertIn('function closeSettingsModal()', app)
        self.assertIn('$("settings-placeholder")?.addEventListener("click", openSettingsModal);', app)

    def test_visible_product_copy_stops_calling_product_viewer(self):
        index = INDEX_HTML.read_text(encoding='utf-8')
        app = APP_JS.read_text(encoding='utf-8')
        for term in ['TextifAI Viewer', 'Visor TextifAI', 'Read-only preview']:
            self.assertNotIn(term, index)
        self.assertIn('TextifAI Author Workspace', index)
        self.assertIn('Workspace narrativo', index)
        self.assertIn('appTitle: "TextifAI Author Workspace"', app)
        self.assertIn('projectPanelTitle: "Mis obras"', app)

    def test_open_workspace_flow_report_forbids_arbitrary_filesystem_browsing(self):
        report = read_json('open_project_workspace_flow_after_sp104.json')
        self.assertFalse(report['arbitrary_filesystem_browsing_allowed'])
        self.assertIn('Mis obras -> Abrir proyecto -> Workspace narrativo.', report['product_flow'])

    def test_layer_boundaries_report_exists(self):
        report = read_json('layer_boundaries_saas_plan_after_sp104.json')
        self.assertIn('ReviewDecisionItem', report['view_models_introduced'])
        self.assertTrue(report['product_consumes_author_facing_models'])
        self.assertTrue(report['dev_consumes_diagnostics'])

    def test_no_provider_calls_package_changes_or_writeback(self):
        decision = read_json('review_workspace_cleanup_decision_after_sp104.json')
        self.assertFalse(decision['provider_calls'])
        self.assertFalse(decision['package_changes'])
        self.assertFalse(decision['write_back'])
        for path in [PACKAGE_JSON, PACKAGE_LOCK]:
            result = subprocess.run(['git', 'diff', '--exit-code', '--', str(path.relative_to(REPO))], cwd=REPO, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        secret = os.environ.get('DEEPSEEK_API_KEY')
        if secret:
            for name in REPORTS:
                self.assertNotIn(secret, (EXPECTED / name).read_text(encoding='utf-8'))

    def test_private_handoff_path_gitignored(self):
        result = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE / 'decision_handoff_private.md')], cwd=REPO, check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)


if __name__ == '__main__':
    unittest.main()
