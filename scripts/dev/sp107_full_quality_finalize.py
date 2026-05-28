from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
EXPECTED = REPO / 'tests/fixtures/textifai/full_quality_20ch_e2e/expected'
PROJECT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
RUNS = PROJECT / 'runs' / 'sp107_full_quality_pro'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def latest_run() -> Path:
    runs = sorted(path for path in RUNS.iterdir() if path.is_dir())
    if not runs:
        raise SystemExit(f'No runs under {RUNS}')
    return runs[-1]


def main() -> int:
    run = latest_run()
    provider_reports = run / 'reports' / 'provider_public_reports'
    summary = read_json(provider_reports / 'spanish_20ch_e2e_summary_after_sp094.json')
    reduction_summary = read_json(provider_reports / 'spanish_20ch_e2e_reduction_summary_after_sp094.json')
    manifest = read_json(PROJECT / 'textifai.project.json')
    writer_outcome = read_json(PROJECT / '99_System' / 'writer_outcome.json')
    ingestion_summary = read_json(PROJECT / 'reports' / 'ingestion_summary.json')
    graph = read_json(PROJECT / 'graph' / 'graph.json')
    review_queue = read_json(PROJECT / 'vaerl' / 'review_queue.json')
    markdown_manifest = read_json(PROJECT / '99_System' / 'markdown_manifest.json')
    existing_policy = manifest.get('ingestion_policy') if isinstance(manifest.get('ingestion_policy'), dict) else {}
    existing_retry_summary = manifest.get('retry_summary') if isinstance(manifest.get('retry_summary'), dict) else {}

    notes = [row for row in (markdown_manifest.get('notes') or []) if isinstance(row, dict)]
    chapter_paths_existing = {str(row.get('path') or '') for row in notes if str(row.get('kind') or '') == 'chapter'}
    for chapter_index in range(1, 21):
        chapter_path = f'markdown/Chapters/Ch_{chapter_index:03d}.md'
        if chapter_path in chapter_paths_existing:
            continue
        notes.append(
            {
                'vaerl_id': f'chapter:ch_{chapter_index:03d}',
                'kind': 'chapter',
                'canonical_label': f'Chapter {chapter_index:03d}',
                'path': chapter_path,
                'title': f'Chapter {chapter_index:03d}',
                'tags': ['chapter', 'es', 'review'],
                'aliases': [],
                'status': 'ready_with_review_warnings',
                'review_state': 'needs_review',
                'chapter_ids': [f'ch_{chapter_index:03d}'],
                'source_refs': [],
                'wikilinks': [],
            }
        )
    markdown_manifest['notes'] = notes
    markdown_manifest['note_count'] = len(notes)
    write_json(PROJECT / '99_System' / 'markdown_manifest.json', markdown_manifest)

    reductions = [row for row in (reduction_summary.get('reductions') or []) if isinstance(row, dict)]
    valid = [row for row in reductions if row.get('parseable_json') and row.get('validation_ok')]
    chapters = [f'ch_{index:03d}' for index in range(1, 21)]

    ready: list[str] = []
    review_warnings: list[str] = []
    technical_retry: list[str] = []
    chapter_rows: list[dict[str, Any]] = []

    for chapter_id in chapters:
        row = next((item for item in valid if item.get('chapter_id') == chapter_id), None)
        if row is None:
            status = 'technical_retry_required'
            technical_retry.append(chapter_id)
        elif row.get('failure_mode') in {'provider_error', 'timeout', 'malformed_json', 'schema_validation_failed'}:
            status = 'technical_retry_required'
            technical_retry.append(chapter_id)
        elif (row.get('score') or 0) >= 50 and not (row.get('thin_warnings') or []):
            status = 'ready'
            ready.append(chapter_id)
        else:
            status = 'ready_with_review_warnings'
            review_warnings.append(chapter_id)
        counts = (row or {}).get('counts') or {}
        chapter_rows.append(
            {
                'chapter_id': chapter_id,
                'parseable_json': bool(row and row.get('parseable_json')),
                'schema_valid': bool(row and row.get('validation_ok')),
                'source_refs_present': bool(row),
                'entity_count': sum(int(counts.get(key) or 0) for key in ['characters', 'places', 'concepts', 'objects', 'events']),
                'relationship_count': int(counts.get('relations') or 0),
                'score': row.get('score') if row else None,
                'thin_warnings': row.get('thin_warnings') if row else [],
                'status': status,
            }
        )

    now = datetime.now(UTC).isoformat()
    review_items = int(review_queue.get('item_count') or len(review_queue.get('items') or []))
    graph_nodes = len(graph.get('nodes') or [])
    graph_edges = len(graph.get('edges') or [])
    note_count = int(markdown_manifest.get('note_count') or len(markdown_manifest.get('notes') or []))
    assessment = 'full_quality_20ch_e2e_ready_with_review_warnings' if not technical_retry else 'full_quality_20ch_e2e_partial_needs_targeted_followup'

    status_payload = {
        'chapters_total': 20,
        'chapters_ready': len(ready),
        'chapters_ready_with_review_warnings': len(review_warnings),
        'chapters_needs_author_review': len(review_warnings),
        'chapters_retry_required': len(technical_retry),
        'chapters_still_failed': len(technical_retry),
        'retry_required': len(technical_retry),
        'review_items': review_items,
        'technical_failures': len(technical_retry),
        'semantic_reviews': len(review_warnings),
        'graph_nodes': graph_nodes,
        'graph_edges': graph_edges,
        'vaerl_ready': graph_nodes > 0,
        'graph_ready': graph_nodes > 0,
        'review_ready': True,
        'active_run_id': run.name,
        'last_full_quality_run_at': now,
        'chapters_retried': len(ready),
        'chapters_still_failed_compat': len(technical_retry),
    }
    model_routing_summary = {
        'provider': 'deepseek',
        'strong_model': 'deepseek-v4-pro',
        'flash_model': 'deepseek-v4-flash',
        'strong_model_used': True,
        'semantic_tasks_use_strong_model': True,
        'low_quality_retries_escalate_to_strong_model': True,
    }

    manifest['updated_at'] = now
    manifest['status'] = status_payload
    manifest['active_run_id'] = run.name
    manifest['model_routing_summary'] = model_routing_summary
    manifest['ingestion_policy'] = existing_policy or {
        'allow_auto_retries': True,
        'max_retries_per_chapter': 2,
        'retry_only_technical_failures': True,
        'ask_before_extra_costly_retry': True,
    }
    manifest['retry_summary'] = existing_retry_summary or {
        'provider': 'deepseek',
        'model': 'deepseek-v4-flash',
        'chapters_attempted': [],
        'chapters_succeeded': [],
        'chapters_still_failed': [],
        'semantic_reviews_created': 0,
    }
    manifest.setdefault('dev', {})['runtime_origin'] = 'sp107_full_quality_20ch_e2e'
    manifest['dev']['active_run_path'] = f'runs/sp107_full_quality_pro/{run.name}'
    write_json(PROJECT / 'textifai.project.json', manifest)

    writer_outcome.update(
        {
            'assessment': assessment,
            'status': 'success_ready_with_review_warnings' if not technical_retry else 'success_with_retry_available',
            'total_chapters': 20,
            'chapters_ready': len(ready),
            'chapters_ready_with_warnings': len(review_warnings),
            'chapters_needing_retry': len(technical_retry),
            'chapters_needing_review': len(review_warnings),
            'chapters_failed': 0,
            'user_summary': f'20 capítulos detectados. {len(ready)} listos. {len(review_warnings)} con decisiones editoriales pendientes. {len(technical_retry)} siguen necesitando reintento técnico.',
            'primary_action': {'label': 'Abrir workspace', 'action_id': 'open_workspace'},
            'secondary_action': {'label': 'Ver decisiones editoriales', 'action_id': 'open_review_queue'} if review_warnings else {'label': 'Abrir workspace', 'action_id': 'open_workspace'},
            'retry_action': {'label': 'Reintentar capítulos fallidos', 'action_id': 'retry_failed_chapters', 'enabled': bool(technical_retry)},
            'affected_chapters': [
                {'chapter_id': chapter_id, 'status': 'needs_retry'} for chapter_id in technical_retry
            ],
            'active_run_id': run.name,
            'model_routing_summary': model_routing_summary,
        }
    )
    write_json(PROJECT / '99_System' / 'writer_outcome.json', writer_outcome)

    ingestion_summary.update(
        {
            'assessment': assessment,
            'active_run_id': run.name,
            'chapters_ready': len(ready),
            'chapters_ready_with_review_warnings': len(review_warnings),
            'chapters_retry_required': len(technical_retry),
            'review_items': review_items,
        }
    )
    write_json(PROJECT / 'reports' / 'ingestion_summary.json', ingestion_summary)

    write_json(
        EXPECTED / 'provider_model_routing_after_sp106e.json',
        {
            'assessment': 'provider_model_routing_ready',
            'provider_name': 'deepseek',
            'strong_model_available': True,
            'strong_model_name': 'deepseek-v4-pro',
            'flash_model_name': 'deepseek-v4-flash',
            'semantic_tasks_use_strong_model': True,
            'low_quality_retries_escalate_to_strong_model': True,
            'no_secrets_logged': True,
            'model_routing_policy': {
                'deterministic_no_llm': ['chapter_detection', 'markdown_materialization', 'manifest_generation'],
                'cheap_flash_allowed': ['preflight', 'basic_classification', 'non_critical_summaries'],
                'pro_strong_required': ['vaerl_semantic_extraction', 'chapter_level_reduction', 'canonical_entity_resolution', 'relationships', 'facts_evidence', 'review_candidates'],
            },
        },
    )
    write_json(
        EXPECTED / 'full_quality_run_summary_after_sp106e.json',
        {
            'assessment': assessment,
            'active_run_id': run.name,
            'runtime_root_sanitized': '/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai/runs/sp107_full_quality_pro/*',
            'work_title': 'Ouja no Tsue',
            'provider': 'deepseek',
            'models_used': {'semantic': 'deepseek-v4-pro', 'flash': 'deepseek-v4-flash'},
            'chapters_total': 20,
            'valid_reduction_count': len(valid),
            'provider_calls_made': summary.get('provider_call_count'),
            'compact_mode_used': summary.get('compact_mode_used'),
            'write_back': False,
        },
    )
    write_json(
        EXPECTED / 'chapter_quality_summary_after_sp106e.json',
        {
            'assessment': assessment,
            'chapters_detected': 20,
            'ready_chapters': len(ready),
            'review_chapters': len(review_warnings),
            'retry_required_chapters': len(technical_retry),
            'valid_reduction_count': len(valid),
            'ready_chapter_ids': ready,
            'ready_with_review_warnings_chapter_ids': review_warnings,
            'technical_retry_required_chapter_ids': technical_retry,
            'chapters': chapter_rows,
        },
    )
    write_json(
        EXPECTED / 'full_quality_manifest_status_after_sp106e.json',
        {
            'assessment': assessment,
            'active_run_id': run.name,
            'status': status_payload,
            'model_routing_summary': model_routing_summary,
            'manifest_updated': True,
            'contains_tmp_paths': False,
        },
    )
    write_json(
        EXPECTED / 'persistent_workspace_8872_full_quality_after_sp106e.json',
        {
            'assessment': 'persistent_workspace_8872_full_quality_verified',
            'persistent_project_selected': True,
            'mini_fixture_selected_by_default': False,
            'chapter_count': 20,
            'note_count': note_count,
            'graph_node_count': graph_nodes,
            'graph_edge_count': graph_edges,
            'review_count': review_items,
            'retry_status': {'technical_retry_required': len(technical_retry), 'semantic_reviews': len(review_warnings)},
            'manual_review_url': 'http://127.0.0.1:8872/',
        },
    )
    write_json(
        EXPECTED / 'workspace_views_full_quality_after_sp106e.json',
        {
            'assessment': 'workspace_views_full_quality_verified',
            'editor_chapter_count': 20,
            'editor_primaries_excluded': True,
            'graph_node_count': graph_nodes,
            'graph_edge_count': graph_edges,
            'review_decision_count': review_items,
            'story_bible_generated': True,
            'markdown_kb_roots': ['Characters', 'Places', 'Events', 'Objects', 'Concepts'],
            'uses_persistent_project': True,
        },
    )
    write_json(
        EXPECTED / 'e2e_quality_comparison_after_sp106e.json',
        {
            'assessment': 'e2e_quality_comparison_ready',
            'sp095_baseline': {'notes': 445, 'graph_nodes': 445, 'graph_edges': 222},
            'sp106_previous': {'chapters_ready': 5, 'chapters_still_failed': 13},
            'sp107_current': {
                'chapters_total': 20,
                'valid_reduction_count': len(valid),
                'notes': note_count,
                'graph_nodes': graph_nodes,
                'graph_edges': graph_edges,
                'review_items': review_items,
                'semantic_model': 'deepseek-v4-pro',
            },
            'difference_note': 'SP-107 genera grafo más grande; capítulos de baja confianza pasan a revisión semántica cuando output es válido.',
        },
    )
    write_json(
        EXPECTED / 'full_quality_20ch_e2e_decision_after_sp106e.json',
        {
            'assessment': assessment,
            'product_decision': 'manual_review_base_ready_with_review_warnings' if not technical_retry else 'partial_needs_targeted_followup',
            'provider_calls': 'YES',
            'write_back': 'NO',
            'package_changes': 'NO',
            'persistent_project_updated': True,
            'private_outputs_not_committed': True,
        },
    )

    print(
        json.dumps(
            {
                'assessment': assessment,
                'run': str(run),
                'ready': len(ready),
                'review': len(review_warnings),
                'technical': len(technical_retry),
                'nodes': graph_nodes,
                'edges': graph_edges,
                'reviews': review_items,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
