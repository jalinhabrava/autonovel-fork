import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / 'textifai/web_viewer/react_shell/src'
UI = SRC / 'i18n/ui.ts'
NAV = SRC / 'shell/navigation.ts'
APP = SRC / 'App.tsx'
STORY_ALIAS_VIEW = SRC / 'modules/canon/StoryAliasView.tsx'
ENTITY_FICHE_VIEW = SRC / 'modules/canon/EntityFicheView.tsx'

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

CANON_VAERL_KEYS = [
    'canon.title',
    'canon.subtitle',
    'canon.actions.export_selection',
    'canon.actions.open_evidence',
    'canon.sections.story_bible',
    'canon.empty.select_project',
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
    'graph.node_sheet','graph.reset_filters','graph.search_placeholder','graph.related_only','graph.edit_draft.readonly',
    'review.title','review.author_decisions_subtitle','review.apply_decisions','review.rerun_validation','review.search_placeholder',
    'review.severity','review.severity.all','review.severity.high','review.severity.medium','review.severity.low',
    'review.accept','review.reject','review.view_evidence','review.pending_decisions',
    'review.no_linked_chapters','review.accept_relationship','review.accept_alias','review.accept_suggestion','review.create_entity',
    'review.evidence','review.evidence_item','review.chapter','review.technical_details','review.pointer',
    'review.no_structured_evidence','review.decision_type','review.recommendation','review.severity_label',
    'review.editorial_decision','review.needs_author_decision','review.no_structured_reference',
    'review.possible_merges','review.probable_aliases','review.uncertain_relations','review.insufficient_evidence',
    'review.pronoun_pov','review.unconfirmed_local_candidates',
]

STORY_ALIAS_KEYS = [
    'story_alias.vault_tree',
    'story_alias.open_canon',
    'story_alias.legacy_notes_title',
]

ENTITY_FICHE_KEYS = [
    'entityFiche.actions.save',
    'entityFiche.editor.title',
    'entityFiche.editor.placeholder',
    'entityFiche.editor.helper',
    'entityFiche.editor.unsaved',
    'entityFiche.editor.saving',
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

    def test_story_alias_keys_exist_es_en(self):
        text = UI.read_text(encoding='utf-8')
        for key in STORY_ALIAS_KEYS:
            self.assertGreaterEqual(text.count(f"'{key}'"), 2, key)

    def test_story_alias_view_uses_i18n_for_static_chrome(self):
        text = STORY_ALIAS_VIEW.read_text(encoding='utf-8')
        for key in ['story_alias.open_canon', 'story_alias.vault_tree', 'canon.select_project', 'nav.codex', 'canon.subtitle']:
            self.assertIn(f"t('{key}')", text)
        for raw in ['Open Canon / VaERL', 'Vault tree']:
            self.assertNotIn(raw, text)

    def test_story_alias_app_callsite_uses_i18n_legacy_embed_title(self):
        text = APP.read_text(encoding='utf-8')
        self.assertIn("t('story_alias.legacy_notes_title')", text)
        self.assertNotIn('legacyNotes={<LegacyEmbed title="Story Bible alias inside Canon / VaERL"', text)

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

    def test_app_editor_chrome_sp139_keys_exist_in_both_locales(self):
        text = UI.read_text(encoding='utf-8')
        for key in [
            'editor.title',
            'editor.subtitle',
            'editor.chapters',
            'editor.chapter_list.hide',
            'editor.chapter_list.show',
            'editor.chapter_list.selected',
            'editor.chapter_list.empty',
            'editor.chapter.add',
            'editor.chapter.add_body',
            'editor.toolbar.contract',
            'editor.markdown_placeholder',
            'editor.context_panel',
            'editor.source_text',
            'editor.save.error_prefix',
            'editor.save.not_saved_yet',
            'editor.save.saved_since',
            'editor.no_chapter_content',
            'editor.reanalysis.pending_not_implemented',
            'project.kind.workspace',
            'project.kind.default',
            'project.fixture.dev',
            'project.fixture.real',
            'project.language.pending',
            'project.workspace_status.chapters_detected',
            'project.workspace_status.chapters_ready',
            'project.workspace_status.chapters_failed',
            'project.workspace_status.semantic_review',
            'project.count.chapters',
            'project.count.nodes',
            'review.source.candidate',
            'review.source.evidence_pending',
            'review.item.needs_decision',
            'review.item.reviewing_target',
            'review.item.source_with_entity',
            'review.item.no_fragment',
            'review.evidence_store',
            'review.yes',
            'review.no',
            'review.entity',
            'review.confidence',
            'review.state',
            'review.inspector.label',
            'review.inspector.empty',
            'review.inspector.summary_missing',
            'review.inspector.edit_draft',
            'graph.inspector.empty_legacy',
            'graph.inspector.aliases_legacy',
            'graph.inspector.relations_count',
            'graph.inspector.evidence_count',
            'graph.no_fragment_fallback',
            'codex.title',
            'codex.subtitle',
            'codex.export_selection',
            'codex.view_evidence',
            'codex.story_bible',
            'codex.select_project',
            'graph.select_project',
            'graph.title',
            'graph.route.subtitle',
            'graph.reset_filters',
            'graph.kind.chapter',
            'graph.kind.character',
            'graph.kind.concept',
            'graph.kind.event',
            'graph.kind.object',
            'graph.kind.place',
            'graph.kind.review',
        ]:
            self.assertEqual(text.count(f"'{key}'"), 2, key)

    def test_app_editor_chrome_sp139_hardcoded_copy_removed(self):
        text = APP.read_text(encoding='utf-8')
        for migrated in [
            'Solo capítulos/manuscrito desde chapter manifest canónico.',
            'Capítulos',
            'Ocultar',
            'Mostrar',
            'Añadir capítulo',
            'Draft local pendiente. No hay write-back semántico en SP-116.',
            'Seleccionado:',
            'Sin capítulo',
            'Write-back Markdown con hash guard y backup',
            'Escribe capítulo en Markdown',
            'Panel de contexto',
            'Origen',
            'aún no guardado',
            'guardado hace ',
            'Proyecto narrativo',
            'idioma pendiente',
            'Sin resumen de ingestión',
            '0 siguen necesitando reintento',
            '0 decisiones editoriales pendientes',
            'Necesita decisión editorial.',
            'Evidencia pendiente',
            'Revisar “',
            'Reanálisis aún no implementado.',
            'Sin contenido de capítulo disponible.',
            'No hay fragmento resoluble porque source_ref no se pudo mapear a chunk narrativo.',
            'Selecciona un nodo.',
            'Draft local/read-only. Guardar cambios llegará con patch queue.',
            'relaciones',
            'evidencias',
            'No hay fragmento textual resoluble porque source_map.chunks está vacío para este source_ref.',
            'Selecciona un proyecto para abrir Graph.',
        ]:
            self.assertNotIn(migrated, text)

    def test_app_editor_chrome_sp139_does_not_ban_unrelated_literals(self):
        text = APP.read_text(encoding='utf-8')
        for still_raw in [
            'chapter_manifest',
            '20 capítulos',
        ]:
            self.assertIn(still_raw, text)

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

    def test_app_review_queue_chrome_uses_i18n(self):
        text = APP.read_text(encoding='utf-8')
        for key in [
            'review.title','review.author_decisions_subtitle','review.apply_decisions','review.rerun_validation',
            'review.search_placeholder','review.severity','review.no_linked_chapters','review.accept_relationship',
            'review.accept_alias','review.accept_suggestion','review.create_entity','review.view_evidence',
            'review.pending_decisions','review.summary_note','review.evidence','review.chapter',
            'review.technical_details','review.pointer','review.no_structured_evidence','review.decision_type',
            'review.recommendation','review.severity_label','review.editorial_decision',
            'review.needs_author_decision','review.no_structured_reference',
        ]:
            self.assertIn(f"t('{key}')", text)
        for key in ['review.severity.all','review.severity.high','review.severity.medium','review.severity.low']:
            self.assertIn(key, text)
        self.assertIn('review.evidence_item', text)
        for key in [
            'review.possible_merges','review.probable_aliases','review.uncertain_relations',
            'review.insufficient_evidence','review.pronoun_pov','review.unconfirmed_local_candidates',
        ]:
            self.assertIn(key, text)
        for migrated in [
            'Review Queue',
            'Decisiones del autor convierten ambigüedad semántica en canon estable.',
            'Aplicar decisiones',
            'Re-ejecutar validación',
            'Buscar decisión...',
            'Sin capítulos vinculados',
            'Aceptar relación',
            'Aceptar alias',
            'Aceptar sugerencia',
            'Crear entidad nueva',
            'Decisiones pendientes',
            'Resumen dinámico de cola editorial.',
            'Posibles fusiones',
            'Aliases probables',
            'Relaciones inciertas',
            'Evidencia insuficiente',
            'Pronombres/POV',
            'Candidatos no confirmados',
            'Capítulo:',
            'Detalles técnicos',
            'Necesita decisión explícita del autor.',
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

    def test_graph_edit_draft_modal_uses_i18n(self):
        text = (SRC / 'graph/GraphNodeEditDraftModal.tsx').read_text(encoding='utf-8')
        self.assertIn("t('graph.edit_draft.readonly')", text)
        self.assertNotIn('No write-back', text)

    def test_canon_vaerl_view_uses_i18n_chrome_keys(self):
        text = (SRC / 'modules/canon/CanonVaerlView.tsx').read_text(encoding='utf-8')
        for key in CANON_VAERL_KEYS:
            self.assertIn(f"t('{key}')", text)
        for old_key in [
            'nav.codex',
            'canon.export_selection',
            'review.open_evidence',
            'canon.story_bible',
            'canon.select_project',
        ]:
            self.assertNotIn(f"t('{old_key}')", text)

    def test_canon_vaerl_catalog_parity(self):
        text = UI.read_text(encoding='utf-8')
        for key in CANON_VAERL_KEYS:
            self.assertEqual(text.count(f"'{key}'"), 2, key)

    def test_entity_fiche_view_uses_i18n_chrome_keys(self):
        text = ENTITY_FICHE_VIEW.read_text(encoding='utf-8')
        for key in ENTITY_FICHE_KEYS:
            self.assertIn(f"t('{key}')", text)
        for old_key in [
            'graph.fiche_body',
            'graph.fiche_save',
            'graph.fiche_saving',
            'graph.fiche_local_note',
            'graph.fiche_local_dirty',
            'graph.fiche_empty_placeholder',
        ]:
            self.assertNotIn(f"t('{old_key}')", text)

    def test_entity_fiche_catalog_parity(self):
        text = UI.read_text(encoding='utf-8')
        for key in ENTITY_FICHE_KEYS:
            self.assertEqual(text.count(f"'{key}'"), 2, key)

    def test_ingestion_view_uses_i18n(self):
        text = (SRC / 'modules/ingestion/IngestionView.tsx').read_text(encoding='utf-8')
        for key in [
            'nav.ingest',
            'ingestion.subtitle',
            'ingestion.progress_title',
            'ingestion.progress_note',
            'ingestion.step',
            'ingestion.pending',
            'ingestion.no_steps',
            'ingestion.status_title',
            'ingestion.status_default',
            'ingestion.completed_review',
            'ingestion.progress',
            'ingestion.job.progress_indeterminate',
            'ingestion.run',
            'ingestion.no_run_id',
            'ingestion.safe_workspace',
            'ingestion.upload.accepted_formats',
            'ingestion.upload.choose_files',
            'ingestion.job.project_not_ready',
            'ingestion.job.project_not_ready_note',
            'ingestion.job.run_name_label',
            'ingestion.job.status.completed_with_warnings',
            'ingestion.job.input_mode.upload_session',
            'ingestion.stage.preparing_manuscript',
            'ingestion.stage.workspace_ready',
        ]:
            self.assertIn(f"t('{key}')", text)
        for migrated in [
            'Ingestion disabled',
            'Ingestion progress',
            'No steps available',
            'Accepted:',
            'Safe workspace',
            'Ingestion completed with editorial review.',
            'Nombre de corrida',
            'Acciones disponibles',
        ]:
            self.assertNotIn(migrated, text)

    def test_ingestion_stage_labels_are_i18n_first(self):
        text = (SRC / 'modules/ingestion/IngestionView.tsx').read_text(encoding='utf-8')
        self.assertIn('STAGE_LABEL_KEYS[stageId]', text)
        self.assertIn('t(mapped)', text)
        self.assertLess(text.index('STAGE_LABEL_KEYS[stageId]'), text.index('return label;'))

    def test_project_open_indicator_uses_i18n(self):
        app = APP.read_text(encoding='utf-8')
        hub = (SRC / 'modules/project/ProjectHubView.tsx').read_text(encoding='utf-8')
        self.assertIn("t('project.open_badge')", app)
        self.assertIn("t('project.open_indicator')", hub)

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
