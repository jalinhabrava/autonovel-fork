from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT_DOC = REPO / 'docs/architecture/entity_fiche_semantic_contract.md'
HANDOFF = REPO / 'docs/handoffs/safepoint-122a_entity-fiche-semantic-contract.md'
ENTITY_CARD = REPO / 'textifai/web_viewer/entity_card.py'
INSPECTOR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx'
FIX = REPO / 'tests/fixtures/textifai/graph_fiche/expected'

class TextifAIEntityFicheSemanticContractTests(unittest.TestCase):
    def test_contract_doc_exists(self):
        self.assertTrue(CONTRACT_DOC.exists())
        text = CONTRACT_DOC.read_text(encoding='utf-8')
        self.assertIn('Entity Fiche Semantic Contract', text)

    def test_structured_data_outside_mdx(self):
        payload = json.loads((FIX / 'entity_fiche_semantic_contract_after_sp122a.json').read_text(encoding='utf-8'))
        self.assertFalse(payload['generated_body_duplicates_structured_cards'])
        self.assertEqual(payload['structured_data_location'] if 'structured_data_location' in payload else 'cards_outside_mdx_editor', 'cards_outside_mdx_editor')

    def test_editorial_body_only(self):
        payload = json.loads((FIX / 'entity_fiche_generated_body_policy_after_sp122a.json').read_text(encoding='utf-8'))
        self.assertIn('title', payload['allowed_default_body_parts'])
        self.assertIn('relationships', payload['disallowed_default_body_parts'])
        text = ENTITY_CARD.read_text(encoding='utf-8')
        self.assertNotIn('## Relaciones', text)

    def test_wikilink_policy_and_future_semantics_documented(self):
        text = CONTRACT_DOC.read_text(encoding='utf-8')
        self.assertIn('Wikilinks', text)
        self.assertIn('needs reanalysis', text)
        payload = json.loads((FIX / 'entity_fiche_semantic_contract_after_sp122a.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['editorial_body_preserves_wikilinks_exactly'])
        self.assertEqual(payload['future_semantic_state_on_save'], 'needs_reanalysis')

    def test_no_silent_semantic_mutation(self):
        payload = json.loads((FIX / 'entity_fiche_semantic_contract_after_sp122a.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['semantic_mutation_requires_review'])

    def test_review_merge_propagation_documented(self):
        handoff = HANDOFF.read_text(encoding='utf-8')
        self.assertIn('Review merge propagation future contract', handoff)
        self.assertIn('intentionally not implemented', handoff)

    def test_writeback_deferred(self):
        payload = json.loads((FIX / 'entity_fiche_semantic_contract_after_sp122a.json').read_text(encoding='utf-8'))
        self.assertTrue(payload['no_projectstore_entity_writeback'])
        self.assertTrue(payload['no_vaerl_writeback'])
        self.assertTrue(payload['no_graph_regeneration'])
        self.assertTrue(payload['no_review_regeneration'])

    def test_no_source_prose_in_reports(self):
        for name in ['entity_fiche_semantic_contract_after_sp122a.json', 'entity_fiche_generated_body_policy_after_sp122a.json']:
            payload = json.loads((FIX / name).read_text(encoding='utf-8'))
            text = json.dumps(payload, ensure_ascii=False)
            self.assertTrue(payload['no_source_prose'])
            self.assertNotIn('王者の杖', text)

    def test_inspector_uses_authored_body_directly(self):
        text = INSPECTOR.read_text(encoding='utf-8')
        self.assertIn('if (cleanBody) return cleanBody;', text)

if __name__ == '__main__':
    unittest.main()
