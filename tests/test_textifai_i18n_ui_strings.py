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
    SRC / 'modules/project/ProjectHubView.tsx',
    SRC / 'modules/ingestion/IngestionView.tsx',
    SRC / 'modules/ai/AIStudioView.tsx',
    SRC / 'modules/review/ReviewQueueView.tsx',
    SRC / 'modules/graph/GraphView.tsx',
    SRC / 'graph/GraphInspector.tsx',
    SRC / 'graph/GraphToolbar.tsx',
]

GRAPH_TOOLBAR_KEYS = [
    'graph.toolbar.filters.all',
    'graph.toolbar.filters.chapters',
    'graph.toolbar.filters.characters',
    'graph.toolbar.filters.places',
    'graph.toolbar.filters.objects',
    'graph.toolbar.filters.events',
    'graph.toolbar.filters.concepts',
    'graph.toolbar.filters.review',
    'graph.toolbar.search_placeholder',
    'graph.toolbar.reset_filters',
]

GRAPH_INSPECTOR_KEYS = [
    'graph.inspector.title',
    'graph.inspector.open_fiche',
    'graph.inspector.empty.body',
    'graph.inspector.sections.aliases',
    'graph.inspector.sections.reference_points',
    'graph.inspector.sections.evidence',
    'graph.inspector.sections.relations',
    'graph.inspector.sections.backlinks',
    'graph.inspector.sections.outgoing_links',
    'graph.inspector.sections.local_graph',
    'graph.inspector.sections.review',
    'graph.inspector.empty.reference_points',
    'graph.inspector.local_graph.body',
    'graph.inspector.local_graph.stats',
    'graph.inspector.local_graph.open',
    'graph.inspector.review.body',
    'graph.inspector.review.open',
    'graph.inspector.fiche.body_note',
    'graph.inspector.fiche.editor_placeholder',
    'graph.inspector.fiche.save',
    'graph.inspector.fiche.unsaved',
    'graph.inspector.fiche.saved',
    'graph.inspector.fiche.error',
]

REQUIRED_KEYS = [
    'nav.hub','nav.ingest','nav.review','nav.graph','nav.codex','nav.editor','nav.ask',
    'overview.title','overview.subtitle','overview.open_project',
    'overview.project_hub.title','overview.project_hub.text','overview.ingestion.title','overview.ingestion.text',
    'overview.review.title','overview.review.text','overview.graph.title','overview.graph.text',
    'overview.codex.title','overview.codex.text','overview.editor.title','overview.editor.text','overview.ai.title','overview.ai.text',
    'aiStudio.title','aiStudio.subtitle','aiStudio.actions.openHistory','aiStudio.actions.checkCoverage','aiStudio.actions.send',
    'aiStudio.placeholder.title','aiStudio.empty.title','aiStudio.empty.body','aiStudio.input.placeholder','aiStudio.grounding.title',
    'aiStudio.grounding.value','aiStudio.grounding.note','aiStudio.future.brainstorming','aiStudio.future.brainstormingNote',
    'aiStudio.future.characterLab','aiStudio.future.characterLabNote',
    'ingestion.subtitle','ingestion.disabled','ingestion.progress_title','ingestion.progress_note','ingestion.status_title','ingestion.status_default','ingestion.step','ingestion.pending','ingestion.no_steps','ingestion.completed_review','ingestion.progress','ingestion.run','ingestion.no_run_id','ingestion.safe_workspace',
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

    def test_graph_toolbar_keys_exist_es_en(self):
        text = UI.read_text(encoding='utf-8')
        for key in GRAPH_TOOLBAR_KEYS:
            self.assertGreaterEqual(text.count(f"'{key}'"), 2, key)

    def test_graph_inspector_keys_exist_es_en(self):
        text = UI.read_text(encoding='utf-8')
        for key in GRAPH_INSPECTOR_KEYS:
            self.assertGreaterEqual(text.count(f"'{key}'"), 2, key)

    def test_catalog_keys_match_between_es_and_en(self):
        text = UI.read_text(encoding='utf-8')
        en_block = re.search(r"\n    en: \{(?P<body>.*?)\n    \},\n    es:", text, re.S).group('body')
        es_block = re.search(r"\n    es: \{(?P<body>.*?)\n    \},\n  \},", text, re.S).group('body')
        en_keys = set(re.findall(r"'([^']+)':", en_block))
        es_keys = set(re.findall(r"'([^']+)':", es_block))
        self.assertEqual(sorted(en_keys - es_keys), [])
        self.assertEqual(sorted(es_keys - en_keys), [])

    def test_arc_locale_resolution_foundation_exists(self):
        text = UI.read_text(encoding='utf-8')
        self.assertIn('export const ARC_LOCALE_STORAGE_KEY', text)
        self.assertIn('textifai.arc.locale', text)
        self.assertIn('export function normalizeUiLocale(', text)
        self.assertIn('export function resolveInitialLocale(', text)
        self.assertIn('URLSearchParams', text)
        for sample in ['lang=es', 'locale=en', 'es-ES', 'en-US']:
            self.assertIn(sample, text)

    def test_navigation_uses_i18n(self):
        text = NAV.read_text(encoding='utf-8')
        for key in ['nav.hub','nav.ingest','nav.review','nav.graph','nav.codex','nav.editor','nav.ask']:
            self.assertIn(f"label: '{key}'", text)

    def test_app_editor_states_use_t(self):
        text = APP.read_text(encoding='utf-8')
        for key in ['editor.save.saving','editor.save.chapter_saved','editor.save.conflict_message','editor.reanalysis.notice']:
            self.assertIn(f"t('{key}')", text)

    def test_app_overview_uses_i18n(self):
        text = APP.read_text(encoding='utf-8')
        for key in [
            'overview.title','overview.subtitle','overview.open_project',
            'overview.project_hub.title','overview.project_hub.text',
            'overview.ingestion.title','overview.ingestion.text',
            'overview.review.title','overview.review.text',
            'overview.graph.title','overview.graph.text',
            'overview.codex.title','overview.codex.text',
            'overview.editor.title','overview.editor.text',
            'overview.ai.title','overview.ai.text',
        ]:
            self.assertIn(key, text)
        for migrated in [
            'Local-first ahora; SaaS-ready después. VaERL manda, Markdown se edita.',
            'Abrir proyecto TextifAI completo vía manifest.json; .txtfai queda como dirección futura.',
            'Resolver avisos mediante decisiones explícitas del autor.',
        ]:
            self.assertNotIn(migrated, text)

    def test_project_hub_view_uses_i18n(self):
        text = (SRC / 'modules/project/ProjectHubView.tsx').read_text(encoding='utf-8')
        for key in [
            'project.manifest_name',
            'project.contract_note',
        ]:
            self.assertIn(f"t('{key}')", text)

    def test_graph_toolbar_uses_toolbar_i18n_keys(self):
        text = (SRC / 'graph/GraphToolbar.tsx').read_text(encoding='utf-8')
        for key in GRAPH_TOOLBAR_KEYS[:8]:
            self.assertIn(f"label: '{key}'", text)
        for key in GRAPH_TOOLBAR_KEYS[8:]:
            self.assertIn(f"t('{key}')", text)
        for old_key in ['graph.filter_all', 'graph.filter_chapters', 'graph.filter_characters', 'graph.filter_places', 'graph.filter_objects', 'graph.filter_events', 'graph.filter_concepts', 'graph.filter_review', 'graph.search_placeholder', 'graph.reset_filters']:
            self.assertNotIn(f"t('{old_key}')", text)
        for migrated in [
            'manifest.json',
            'Un archivo abre el bundle completo.',
        ]:
            self.assertNotIn(migrated, text)

    def test_graph_inspector_uses_inspector_i18n_keys(self):
        text = (SRC / 'graph/GraphInspector.tsx').read_text(encoding='utf-8')
        for key in GRAPH_INSPECTOR_KEYS:
            needle = f"t('{key}')"
            if key == 'graph.inspector.local_graph.stats':
                self.assertIn(needle[:-1], text)
                continue
            self.assertIn(needle, text)
        for old_key in [
            'graph.ficha_hint',
            'graph.node_sheet',
            'graph.open_ficha',
            'graph.aliases',
            'graph.reference_points',
            'graph.local_graph',
            'graph.local_graph_note',
            'graph.view_local_graph',
            'graph.view_review',
            'graph.review_filter_hint',
            'graph.fiche_saving',
            'graph.fiche_saved_pending_reanalysis',
            'graph.fiche_conflict',
            'graph.fiche_save_error',
            'graph.fiche_empty_placeholder',
        ]:
            self.assertNotIn(f"t('{old_key}')", text)

    def test_ingestion_view_uses_i18n(self):
        text = (SRC / 'modules/ingestion/IngestionView.tsx').read_text(encoding='utf-8')
        for key in [
            'nav.ingest',
            'ingestion.subtitle',
            'ingestion.disabled',
            'ingestion.progress_title',
            'ingestion.progress_note',
            'ingestion.step',
            'ingestion.pending',
            'ingestion.no_steps',
            'ingestion.status_title',
            'ingestion.status_default',
            'ingestion.completed_review',
            'ingestion.progress',
            'ingestion.run',
            'ingestion.no_run_id',
            'ingestion.safe_workspace',
        ]:
            self.assertIn(f"t('{key}')", text)
        for migrated in [
            'Ingestion disabled',
            'Ingestion progress',
            'No steps available',
            'Safe workspace',
            'Ingestion completed with editorial review.',
        ]:
            self.assertNotIn(migrated, text)

    def test_ai_studio_view_uses_i18n(self):
        text = (SRC / 'modules/ai/AIStudioView.tsx').read_text(encoding='utf-8')
        for key in [
            'aiStudio.title','aiStudio.subtitle','aiStudio.actions.openHistory','aiStudio.actions.checkCoverage','aiStudio.actions.send',
            'aiStudio.placeholder.title','aiStudio.empty.title','aiStudio.empty.body','aiStudio.input.placeholder','aiStudio.grounding.title',
            'aiStudio.grounding.value','aiStudio.grounding.note','aiStudio.future.brainstorming','aiStudio.future.brainstormingNote',
            'aiStudio.future.characterLab','aiStudio.future.characterLabNote',
        ]:
            self.assertIn(f"t('{key}')", text)
        for migrated in [
            'Ask Canon placeholder.',
            'Grounded answer',
            'Placeholder. Canon is not generated without evidence backend.',
            'Ask about canon, brainstorming, or characters...',
            'No unsupported claims.',
        ]:
            self.assertNotIn(migrated, text)

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

    def test_ingestion_catalog_parity(self):
        text = UI.read_text(encoding='utf-8')
        for key in [
            'ingestion.subtitle','ingestion.disabled','ingestion.progress_title','ingestion.progress_note',
            'ingestion.status_title','ingestion.status_default','ingestion.step',
            'ingestion.pending','ingestion.no_steps','ingestion.completed_review','ingestion.progress',
            'ingestion.run','ingestion.no_run_id','ingestion.safe_workspace',
        ]:
            self.assertEqual(text.count(f"'{key}'"), 2, key)

    def test_ai_studio_catalog_parity(self):
        text = UI.read_text(encoding='utf-8')
        for key in [
            'aiStudio.title','aiStudio.subtitle','aiStudio.actions.openHistory','aiStudio.actions.checkCoverage','aiStudio.actions.send',
            'aiStudio.placeholder.title','aiStudio.empty.title','aiStudio.empty.body','aiStudio.input.placeholder','aiStudio.grounding.title',
            'aiStudio.grounding.value','aiStudio.grounding.note','aiStudio.future.brainstorming','aiStudio.future.brainstormingNote',
            'aiStudio.future.characterLab','aiStudio.future.characterLabNote',
        ]:
            self.assertEqual(text.count(f"'{key}'"), 2, key)

    def test_reports_exist(self):
        for p in [CATALOG, AUDIT, ALLOW, NAV_REPORT, EDITOR_REPORT, GRAPH_REVIEW_REPORT]:
            self.assertTrue(p.exists(), str(p))
            payload = json.loads(p.read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)
            self.assertTrue(payload.get('no_source_prose', True))

if __name__ == '__main__':
    unittest.main()
