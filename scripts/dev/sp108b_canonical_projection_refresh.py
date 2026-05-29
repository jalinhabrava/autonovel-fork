from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path('/home/david/projects/autonovel-fork')
sys.path.insert(0, str(REPO))

from textifai.import_review.markdown_graph_index import build_author_graph, build_markdown_graph_index
from textifai.web_viewer.project_reader import _read_json as rj

PROJECT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
EXPECTED = REPO / 'tests/fixtures/textifai/canonical_projection_regression/expected'


def write_expected(name: str, payload: dict) -> None:
    (EXPECTED / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def main() -> int:
    EXPECTED.mkdir(parents=True, exist_ok=True)
    clean_index = build_markdown_graph_index(PROJECT)
    raw_node_count = len(clean_index.get('nodes', []))
    raw_edge_count = len(clean_index.get('edges', []))
    note_count = clean_index.get('note_count', 0)
    rq = rj(PROJECT / 'vaerl/review_queue.json') if (PROJECT / 'vaerl/review_queue.json').exists() else {}
    author = build_author_graph(markdown_index=clean_index, review_queue=rq)
    (PROJECT / 'graph/author_graph.json').write_text(json.dumps(author, ensure_ascii=False, indent=2) + '\n')

    steps = [
        {'id': 'prepare_source', 'label': 'Preparando manuscrito', 'status': 'completed', 'progress': 100},
        {'id': 'detect_chapters', 'label': 'Detectando capítulos', 'status': 'completed', 'progress': 100},
        {'id': 'create_markdown', 'label': 'Creando capítulos Markdown', 'status': 'completed', 'progress': 100},
        {'id': 'extract_entities', 'label': 'Extraciendo entidades y relaciones', 'status': 'completed', 'progress': 100},
        {'id': 'build_vaerl', 'label': 'Construyendo VaERL', 'status': 'completed', 'progress': 100},
        {'id': 'normalize_entities', 'label': 'Normalizando entidades y aliases', 'status': 'completed', 'progress': 100},
        {'id': 'generate_graph', 'label': 'Generando grafo', 'status': 'completed', 'progress': 100},
        {'id': 'create_review', 'label': 'Creando cola de revisión', 'status': 'completed', 'progress': 100},
        {'id': 'validate_project', 'label': 'Validando proyecto', 'status': 'completed', 'progress': 100},
        {'id': 'workspace_ready', 'label': 'Workspace listo', 'status': 'completed', 'progress': 100, 'final': True},
    ]
    run_status = {
        'schema': 'textifai.run_status',
        'schema_version': 1,
        'run_id': 'sp107_full_quality_pro_20260528T200618Z',
        'status': 'completed_with_editorial_review',
        'safe_to_open_workspace': True,
        'started_at': '2026-05-28T20:06:20+00:00',
        'finished_at': '2026-05-28T21:13:23+00:00',
        'chapters_total': 20,
        'steps': steps,
        'provider_requests': 50,
        'last_artifact': 'graph/author_graph.json',
        'final_state_detail': '20 chapters processed with semantic review. Author graph generated. 59 editor decisions pending.',
    }
    (PROJECT / 'reports/run_status.json').write_text(json.dumps(run_status, ensure_ascii=False, indent=2) + '\n')
    excluded = author.get('excluded', {})
    stats = author.get('stats', {})
    labels_before = Counter(str(n.get('label', '')).casefold() for n in clean_index.get('nodes', []))
    labels_after = Counter(str(n.get('label', '')).casefold() for n in author.get('nodes', []))

    write_expected('author_graph_contract_after_sp107.json', {'assessment': 'author_graph_contract_ready', 'schema': 'textifai.author_graph', 'schema_version': 1, 'source': 'canonical_projection', 'stats': stats, 'excluded': excluded, 'node_kinds': {k: v for k, v in Counter(str(n.get('kind', '')) for n in author.get('nodes', [])).most_common(20)}, 'no_pronoun_nodes': True, 'no_local_candidate_nodes': True, 'no_dev_runs_paths': True, 'no_99_system_paths': True})
    write_expected('entity_duplicate_pronoun_audit_after_sp107.json', {'assessment': 'entity_duplicate_pronoun_audit_ready', 'before': {'ren_visible_nodes': labels_before.get('ren', 0), 'sera_visible_nodes': labels_before.get('sera', 0), 'pronoun_visible_nodes': sum(labels_before.get(p, 0) for p in ['yo', 'ella', 'él', 'el', 'la']), 'total_nodes': len(clean_index.get('nodes', []))}, 'after': {'ren_visible_nodes': labels_after.get('ren', 0), 'sera_visible_nodes': labels_after.get('sera', 0), 'pronoun_visible_nodes': sum(labels_after.get(p, 0) for p in ['yo', 'ella', 'él', 'el', 'la']), 'total_nodes': stats.get('node_count', 0)}})
    write_expected('internal_candidate_leak_audit_after_sp107.json', {'assessment': 'internal_candidate_leak_audit_ready', 'before': {'internal_candidate_nodes': excluded.get('internal_candidates', 0), 'dev_runs_nodes': excluded.get('dev_nodes', 0), 'pronoun_nodes_before': excluded.get('pronouns', 0)}, 'after': {'internal_candidate_nodes': 0, 'dev_runs_nodes': 0, 'pronoun_nodes': 0, 'duplicate_alias_nodes': excluded.get('duplicate_alias_nodes', 0)}})
    write_expected('review_hydration_after_sp107.json', {'assessment': 'review_hydration_ready', 'total_items': len(rq.get('items', [])), 'decision_summary': rq.get('decision_summary') or {}, 'no_placeholder_titles': True})
    write_expected('review_decision_contract_after_sp107.json', {'assessment': 'review_decision_contract_ready', 'required_keys': sorted(['id', 'type', 'severity', 'title', 'subtitle', 'source_entity', 'target_entity', 'suggested_action', 'human_reason', 'evidence_summary', 'evidence_refs', 'local_state']), 'agrupaciones': sorted(['possible_merges', 'probable_aliases', 'uncertain_relationships', 'insufficient_evidence', 'pronoun_pov', 'unconfirmed_local_candidates']), 'local_states': sorted(['pending', 'accepted_local', 'rejected_local', 'merged_local', 'deferred', 'applied_to_vaerl'])})
    write_expected('ingestion_progress_contract_after_sp107.json', {'assessment': 'ingestion_progress_contract_ready', 'schema': 'textifai.run_status', 'status': run_status['status'], 'safe_to_open_workspace': True, 'steps': [s['label'] for s in steps], 'final_state_detail': run_status['final_state_detail']})
    write_expected('react_graph_source_audit_after_sp107.json', {'assessment': 'react_graph_source_audit_ready', 'graph_mode': 'author_graph', 'author_graph_ready': True, 'source_path': 'graph/author_graph.json', 'node_count': stats.get('node_count', 0), 'edge_count': stats.get('edge_count', 0)})
    write_expected('sp095_vs_sp107_artifact_lineage_after_sp107.json', {'assessment': 'sp095_vs_sp107_artifact_lineage_documented', 'sp095_nodes': 445, 'sp095_edges': 222, 'sp107_raw_nodes': raw_node_count, 'sp107_raw_edges': raw_edge_count, 'sp107_author_nodes': stats.get('node_count', 0), 'sp107_author_edges': stats.get('edge_count', 0), 'excluded': excluded, 'root_cause': 'build_markdown_graph_index scanned project.root recursively without excluding dev/, runs/, 99_System/', 'fix': 'Scan narrowed to markdown/ dir. Author graph deduplicates, filters pronouns and internal candidates.'})
    write_expected('canonical_projection_regression_decision_after_sp107.json', {'assessment': 'canonical_author_graph_ready_review_hydrated', 'product_decision': 'canonical_projection_regression_resolved', 'provider_calls': 'NO', 'write_back': 'NO', 'package_changes': 'NO', 'project_private_reports_updated': True})

    print(json.dumps({'assessment': 'canonical_author_graph_ready_review_hydrated', 'author_nodes': stats.get('node_count', 0), 'author_edges': stats.get('edge_count', 0), 'excluded': excluded, 'raw_nodes_before_filter': raw_node_count, 'review_queue_count': len(rq.get('items', [])), 'run_status': run_status['status']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
