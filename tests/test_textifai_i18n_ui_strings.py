import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / 'textifai/web_viewer/react_shell/src'
UI = SRC / 'i18n/ui.ts'
NAV = SRC / 'shell/navigation.ts'
APP = SRC / 'App.tsx'

FIX = REPO / 'tests/fixtures/textifai/i18n/expected'
CATALOG = FIX / 'ui_i18n_catalog_after_sp119.json'
AUDIT = FIX / 'ui_i18n_audit_after_sp119.json'
ALLOW = FIX / 'ui_hardcoded_strings_allowlist_after_sp119.json'
NAV_REPORT = FIX / 'ui_i18n_navigation_after_sp119.json'
EDITOR_REPORT = FIX / 'ui_i18n_editor_after_sp119.json'
GRAPH_REVIEW_REPORT = FIX / 'ui_i18n_graph_review_after_sp119.json'

KEY_MODULES = [
    SRC / 'App.tsx',
    SRC / 'shell/AppShell.tsx',
    SRC / 'modules/review/ReviewQueueView.tsx',
    SRC / 'modules/graph/GraphView.tsx',
    SRC / 'graph/GraphInspector.tsx',
    SRC / 'graph/GraphToolbar.tsx',
]

REQUIRED_KEYS = [
    'nav.hub','nav.ingest','nav.review','nav.graph','nav.codex','nav.editor','nav.ask',
    'editor.save.chapter','editor.save.dirty','editor.save.saving','editor.save.saved','editor.save.conflict_message','editor.save.error',
    'editor.reanalysis.pending','editor.reanalysis.notice','editor.reanalysis.action',
    'graph.node_sheet','graph.reset_filters','graph.search_placeholder','graph.related_only',
    'review.accept','review.reject','review.view_evidence','review.pending_decisions',
]

class TestTextifAII18nUiStrings(unittest.TestCase):
    def test_catalog_and_t_exist(self):
        text = UI.read_text(encoding='utf-8')
        self.assertIn('catalogs: {', text)
        self.assertIn('en: {', text)
        self.assertIn('es: {', text)
        self.assertIn('export function t(', text)

    def test_required_keys_exist_es_en(self):
        text = UI.read_text(encoding='utf-8')
        for key in REQUIRED_KEYS:
            self.assertGreaterEqual(text.count(f"'{key}'"), 2, key)

    def test_navigation_uses_i18n(self):
        text = NAV.read_text(encoding='utf-8')
        for key in ['nav.hub','nav.ingest','nav.review','nav.graph','nav.codex','nav.editor','nav.ask']:
            self.assertIn(f"label: '{key}'", text)

    def test_app_editor_states_use_t(self):
        text = APP.read_text(encoding='utf-8')
        for key in ['editor.save.saving','editor.save.chapter_saved','editor.save.conflict_message','editor.reanalysis.notice']:
            self.assertIn(f"t('{key}')", text)

    def test_no_obvious_hardcoded_ui_literals_in_key_modules(self):
        allow = json.loads(ALLOW.read_text(encoding='utf-8'))
        allowed_literals = set(allow['allowed_literal_substrings'])
        str_re = re.compile(r"(['\"])([^'\"\\n]{4,})\\1")
        offenders = []
        for path in KEY_MODULES:
            text = path.read_text(encoding='utf-8')
            for m in str_re.finditer(text):
                s = m.group(2)
                if 'className=' in s or s.startswith('http'):
                    continue
                if 't(' in s or 'nav.' in s or 'editor.' in s or 'review.' in s or 'graph.' in s:
                    continue
                if any(k in s for k in ['bg-', 'text-', 'border-', 'rounded-', 'chapter_manifest', 'project_store', 'schema:', 'created_at:', 'updated_at:', 'canonical_id:']):
                    continue
                if any(a in s for a in allowed_literals):
                    continue
                if re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]{4,}\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}', s):
                    offenders.append((str(path), s))
        self.assertFalse(offenders[:10], offenders[:10])

    def test_reports_exist(self):
        for p in [CATALOG, AUDIT, ALLOW, NAV_REPORT, EDITOR_REPORT, GRAPH_REVIEW_REPORT]:
            self.assertTrue(p.exists(), str(p))
            payload = json.loads(p.read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)
            self.assertTrue(payload.get('no_source_prose', True))

if __name__ == '__main__':
    unittest.main()
