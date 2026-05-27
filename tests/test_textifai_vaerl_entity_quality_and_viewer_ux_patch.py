from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

from textifai.import_review.vaerl_markdown_materializer import materialize_vaerl_markdown
from textifai.web_viewer.project_reader import ProjectCatalog, read_project

SPANISH = Path('tests/fixtures/textifai/spanish_20ch_e2e/expected')
VIEW = Path('tests/fixtures/textifai/viewer_wiring/expected')
PRIVATE = Path('docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch')

REPORTS = [
    'spanish_20ch_retry_classification_audit_after_sp095.json',
    'spanish_20ch_entity_kind_canonical_audit_after_sp095.json',
    'spanish_20ch_alias_merge_candidates_after_sp095.json',
    'spanish_20ch_graph_link_resolution_audit_after_sp095.json',
    'spanish_20ch_chapter_count_integrity_after_sp095.json',
    'spanish_20ch_node_bio_enrichment_contract_after_sp095.json',
]
VIEW_REPORTS = [
    'viewer_writer_outcome_loading_patch_after_sp095.json',
    'viewer_graph_layout_patch_after_sp095.json',
    'viewer_graph_drag_position_patch_after_sp095.json',
    'viewer_internal_navigation_patch_after_sp095.json',
    'viewer_kind_color_legend_patch_after_sp095.json',
    'viewer_author_ux_manual_review_server_after_sp095.json',
    'viewer_author_ux_patch_decision_after_sp095.json',
]

class TextifAISP096Tests(unittest.TestCase):
    def test_reports_parse(self):
        for name in REPORTS:
            payload = json.loads((SPANISH / name).read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)
        for name in VIEW_REPORTS:
            payload = json.loads((VIEW / name).read_text(encoding='utf-8'))
            self.assertIn('assessment', payload)

    def test_retry_taxonomy(self):
        payload = json.loads((SPANISH / 'spanish_20ch_retry_classification_audit_after_sp095.json').read_text(encoding='utf-8'))
        self.assertIn('chapters', payload)
        rows = {row['chapter_id']: row for row in payload['chapters']}
        self.assertEqual(rows['ch_019']['recommended_status'], 'needs_retry')
        self.assertTrue(rows['ch_019']['true_retry'])
        self.assertIn(rows['ch_001']['recommended_status'], {'needs_review', 'ready_with_warnings'})
        self.assertFalse(rows['ch_001']['true_retry'])

    def test_character_preference_duplicate_labels(self):
        audit = json.loads((SPANISH / 'spanish_20ch_entity_kind_canonical_audit_after_sp095.json').read_text(encoding='utf-8'))
        pref = audit['character_preference_examples']
        self.assertEqual(pref['Sera']['preferred_kind'], 'character')
        self.assertEqual(pref['Ren']['preferred_kind'], 'character')

    def test_alias_candidates_separate_automatic_and_review(self):
        payload = json.loads((SPANISH / 'spanish_20ch_alias_merge_candidates_after_sp095.json').read_text(encoding='utf-8'))
        self.assertIn('automatic_redirects_applied', payload)
        self.assertIn('review_only_candidates', payload)

    def test_link_resolution_improves_counts(self):
        payload = json.loads((SPANISH / 'spanish_20ch_graph_link_resolution_audit_after_sp095.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['before_unresolved_links'], 401)
        self.assertLess(payload['after_unresolved_links'], 401)
        self.assertEqual(payload['before_orphan_notes'], 283)
        self.assertLessEqual(payload['after_orphan_notes'], 283)

    def test_chapter_integrity(self):
        payload = json.loads((SPANISH / 'spanish_20ch_chapter_count_integrity_after_sp095.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['selected_count'], 20)
        self.assertEqual(payload['represented_count_before'], 19)
        self.assertEqual(payload['represented_count_after'], 20)
        self.assertEqual(payload['ch_019_status'], 'needs_retry')

    def test_writer_outcome_loading_report(self):
        payload = json.loads((VIEW / 'viewer_writer_outcome_loading_patch_after_sp095.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['reads_99_system_writer_outcome'])
        self.assertTrue(payload['overview_exposes_writer_outcome'])

    def test_private_folder_ignored(self):
        result = subprocess.run(['git','check-ignore','-v',str(PRIVATE / 'decision_handoff_private.md')], check=False, capture_output=True, text=True)
        self.assertIn('docs/handoffs/private/', result.stdout)

    def test_no_private_outputs_committed(self):
        for root in [SPANISH, VIEW]:
            for path in root.glob('*.json'):
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('provider_response_raw', text)
                self.assertNotIn('final_prompt_sent', text)
                self.assertNotIn('html-anything', text.casefold())
                secret = os.environ.get('DEEPSEEK_API_KEY')
                if secret:
                    self.assertNotIn(secret, text)

    def test_static_app_hooks_present(self):
        text = Path('textifai/web_viewer/static/app.js').read_text(encoding='utf-8')
        for token in ['viewerNavBack', 'viewerNavForward', 'persistGraphPositions', 'loadGraphPositions', 'clearGraphPositions', 'kindColor', 'bindNodeDrag']:
            self.assertIn(token, text)

    def test_materializer_uses_final_paths_for_wikilinks(self):
        payload = {
            'entities': [
                {'id': 'character:sera', 'kind': 'character', 'canonical_label': 'Sera', 'relationships': [{'target': 'Ren'}]},
                {'id': 'concept:sera', 'kind': 'concept', 'canonical_label': 'Sera', 'relationships': []},
                {'id': 'character:ren', 'kind': 'character', 'canonical_label': 'Ren', 'relationships': []},
            ],
            'chapters': [],
            'reviews': [],
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            manifest = materialize_vaerl_markdown(payload, Path(tmp), write_files=True)
            notes = {n['canonical_label'] + ':' + n['kind']: n for n in manifest['notes']}
            sera = Path(tmp) / notes['Sera:character']['path']
            txt = sera.read_text(encoding='utf-8')
            self.assertIn('[[Characters/Ren', txt)

if __name__ == '__main__':
    unittest.main()
