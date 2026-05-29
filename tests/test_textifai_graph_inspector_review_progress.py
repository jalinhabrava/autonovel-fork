import json, unittest
from pathlib import Path
from textifai.import_review.markdown_graph_index import build_author_graph, build_markdown_graph_index, CANONICAL_KIND_PRIORITY
from textifai.web_viewer.project_reader import format_author_facing_label, ProjectCatalog, read_project

REPO = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
EXPECTED = REPO / 'tests/fixtures/textifai/graph_inspector_review_progress/expected'
AUTHOR_GRAPH = PROJECT_ROOT / 'graph/author_graph.json'

def read_report(name):
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))

class GraphInspectorReviewProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ag = build_author_graph(markdown_index=build_markdown_graph_index(PROJECT_ROOT), review_queue={})

    def test_canonical_kind_priority_maps_ren_sera_nael(self):
        for target in ['Ren','Sera','Nael']:
            nodes = [n for n in self.ag['nodes'] if n.get('label','').casefold() == target.casefold()]
            self.assertTrue(len(nodes) > 0, f'{target} not found')
            for n in nodes:
                self.assertEqual(n.get('kind'), 'character', f'{target}: expected character got {n.get("kind")}')

    def test_canonical_kind_priority_order(self):
        self.assertGreater(CANONICAL_KIND_PRIORITY.get('character',0), CANONICAL_KIND_PRIORITY.get('concept',0))
        self.assertGreater(CANONICAL_KIND_PRIORITY.get('place',0), CANONICAL_KIND_PRIORITY.get('event',0))

    def test_author_graph_nodes_have_summary(self):
        ag = self.ag
        # summary is empty because frontmatter may not have it; we just assert node schema
        self.assertTrue(all(n.get('kind') for n in ag['nodes']))
        self.assertTrue(all(n.get('label') for n in ag['nodes']))
        self.assertIn('summary', ag['nodes'][0])

    def test_author_facing_label_cleanup(self):
        cases = [
            ('unnamed_girl', 'Chica sin identificar'),
            ('hombre_misterioso', 'Hombre misterioso'),
            ('él (padre de Nael)', 'Padre de Nael'),
            ('protagonista', 'Protagonista'),
        ]
        for inp, expected in cases:
            result = format_author_facing_label(inp)
            self.assertEqual(result, expected, f'{inp} -> {result} != {expected}')

    def test_format_author_facing_label_camel_to_space(self):
        result = format_author_facing_label('hombreMisterioso')
        self.assertIn('hombre misterioso', result.casefold())
        self.assertNotIn('Misterioso', result)

    def test_review_card_hydration_no_placeholder_subtitle(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        rq = detail.get('canon',{}).get('review_queue',{})
        items = rq.get('decision_items',[])
        for item in items:
            self.assertNotEqual(item.get('subtitle','').strip().casefold(), 'review', f"review found: {item.get('title')}")
            self.assertNotIn('Entidad origen / Entidad relacionada', item.get('title',''))
            title = item.get('title','')
            self.assertTrue('→' in title or 'sin entidad sugerida' in title, f"no clear target state in: {title}")

    def test_review_items_not_empty(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        rq = detail.get('canon',{}).get('review_queue',{})
        items = rq.get('decision_items',[])
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertIn('title', item)
            self.assertIn('human_reason', item)
            if item.get('evidence_refs'):
                for ref in item['evidence_refs']:
                    self.assertIn('excerpt', ref)

    def test_dynamic_summary_counts_match_items(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        rq = detail.get('canon',{}).get('review_queue',{})
        summary = rq.get('decision_summary',{})
        items = rq.get('decision_items',[])
        total_from_cats = sum(summary.get(k, 0) for k in ['possible_merges','probable_aliases','uncertain_relationships','insufficient_evidence','pronoun_pov','unconfirmed_local_candidates'])
        self.assertEqual(total_from_cats, summary.get('total_pending',0))
        self.assertEqual(len(items), summary.get('total_pending',0))

    def test_report_exists_and_meta(self):
        self.assertTrue((EXPECTED / 'canonical_kind_priority_after_sp108b.json').exists())
        report = read_report('canonical_kind_priority_after_sp108b.json')
        self.assertIn('assessment', report)
        self.assertIn('priority_order', report)

    def test_no_source_prose_in_report(self):
        for path in EXPECTED.glob('*.json'):
            text = json.dumps(json.loads(path.read_text(encoding='utf-8')), ensure_ascii=False)
            self.assertNotIn('provider_response_raw', text)
            self.assertNotIn('Me llamaron muchas cosas', text)

    def test_graph_inspector_hydrates_via_backend(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        graph = read_project(ref)['graph']
        meta = graph.get('metadata',{})
        self.assertEqual(meta.get('graph_mode'), 'author_graph')
        node = graph['nodes'][0]
        self.assertIn('label', node)
        self.assertIn('kind', node)

    def test_graph_node_has_hydrated_summary_excerpt(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        graph = read_project(ref)['graph']
        nodes = graph['nodes']
        with_summary = [n for n in nodes if n.get('summary_excerpt')]
        self.assertGreater(len(with_summary), 10)

    def test_no_excessive_internal_jargon(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        detail = read_project(ref)
        ws = detail.get('workspace_status',{})
        combined = json.dumps(ws, ensure_ascii=False).lower()
        for internal in ['provider_outputs','viewer_project','99_system','dev/']:
            self.assertNotIn(internal, combined)

if __name__ == '__main__':
    unittest.main()
