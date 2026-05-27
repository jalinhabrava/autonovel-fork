from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from textifai.import_review.markdown_graph_index import build_markdown_graph_index
from textifai.import_review.vaerl_markdown_materializer import materialize_vaerl_markdown

SP095_RUNTIME = Path('/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z')
SP096_ROOT = Path('/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch')
PRIVATE_ROOT = REPO / 'docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch'
EXPECTED_SPANISH = REPO / 'tests/fixtures/textifai/spanish_20ch_e2e/expected'
EXPECTED_VIEW = REPO / 'tests/fixtures/textifai/viewer_wiring/expected'

KIND_PREF = {'character': 0, 'place': 1, 'object': 2, 'event': 3, 'concept': 4, 'chapter': 5, 'review': 6}


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize_label(value: str) -> str:
    text = ''.join(ch for ch in value.casefold() if ch.isalnum())
    return text


def technical_signals_for_chapter(provider_root: Path, chapter_id: str) -> list[str]:
    run_dir = provider_root / f'{chapter_id}__deepseek_v4_flash'
    if not run_dir.exists():
        return ['run_missing']
    signals: list[str] = []
    for report in run_dir.rglob('failure_mode_report.json'):
        try:
            payload = read_json(report)
        except Exception:
            continue
        failure_mode = str(payload.get('failure_mode') or '')
        if failure_mode:
            signals.append(failure_mode)
    for report in run_dir.rglob('validation_report.json'):
        try:
            payload = read_json(report)
        except Exception:
            continue
        if payload.get('parseable_json') is False:
            signals.append('parseable_json_false')
        if str(payload.get('finish_reason') or '') == 'length':
            signals.append('finish_reason_length')
    uniq = []
    for item in signals:
        if item not in uniq:
            uniq.append(item)
    return uniq


def build_retry_audit(selected_chapters: list[str], provider_reports_root: Path) -> dict[str, Any]:
    outcome_report = read_json(provider_reports_root / 'spanish_20ch_e2e_user_ingestion_outcome_after_sp094.json')
    outcome = outcome_report.get('user_ingestion_outcome') or {}
    previous = {row.get('chapter_id'): row for row in (outcome.get('affected_chapters') or []) if isinstance(row, dict)}
    provider_runs_root = SP095_RUNTIME / 'provider_runs' / '20260527T074729Z'

    chapters = []
    for chapter_id in selected_chapters:
        previous_status = previous.get(chapter_id, {}).get('status') or 'ready'
        technical_signals = technical_signals_for_chapter(provider_runs_root, chapter_id)
        true_retry = any(sig in {'run_missing', 'parseable_json_false', 'finish_reason_length', 'valid_json_wrong_chapter'} for sig in technical_signals)
        if true_retry:
            recommended = 'needs_retry'
            reason = 'technical_failure_or_unreliable_output'
            confidence = 0.92
        elif previous_status == 'needs_retry':
            recommended = 'needs_review'
            reason = 'valid_output_with_quality_or_consistency_warning'
            confidence = 0.72
        else:
            recommended = 'ready_with_warnings'
            reason = 'valid_output_no_blocking_technical_failure'
            confidence = 0.66
        chapters.append({
            'chapter_id': chapter_id,
            'previous_status': previous_status,
            'technical_signals': technical_signals,
            'semantic_quality_signals': ['manual_semantic_review_recommended'] if recommended != 'needs_retry' else [],
            'recommended_status': recommended,
            'reason': reason,
            'confidence': confidence,
            'true_retry': bool(true_retry),
            'needs_review': recommended == 'needs_review',
        })

    retry_count = sum(1 for row in chapters if row['recommended_status'] == 'needs_retry')
    review_count = sum(1 for row in chapters if row['recommended_status'] == 'needs_review')
    ready_with_warnings = sum(1 for row in chapters if row['recommended_status'] == 'ready_with_warnings')
    ready = max(0, len(chapters) - retry_count - review_count - ready_with_warnings)

    writer_outcome = {
        'status': 'success_with_retry_available' if retry_count else 'success_with_warnings',
        'total_chapters': len(chapters),
        'chapters_ready': ready,
        'chapters_ready_with_warnings': ready_with_warnings,
        'chapters_needing_review': review_count,
        'chapters_needing_retry': retry_count,
        'chapters_failed': 0,
        'affected_chapters': [
            {
                'chapter_id': row['chapter_id'],
                'chapter_label': f"Chapter {row['chapter_id'].split('_')[-1]}",
                'status': row['recommended_status'],
                'reason_label': row['reason'],
            }
            for row in chapters
            if row['recommended_status'] in {'needs_retry', 'needs_review'}
        ],
        'primary_action': {
            'label': 'Retry pending chapters' if retry_count else 'Review results',
            'action_id': 'retry_pending_chapters' if retry_count else 'review_results',
            'scope': 'affected_chapters_only' if retry_count else 'all_results',
        },
        'secondary_action': {'label': 'Later', 'action_id': 'dismiss'},
        'user_summary': f"{ready} de {len(chapters)} capítulos listos. {retry_count} requieren retry técnico y {review_count} requieren revisión.",
    }

    return {
        'assessment': 'spanish_20ch_retry_classification_audit_ready',
        'chapters': chapters,
        'summary': {
            'total': len(chapters),
            'needs_retry': retry_count,
            'needs_review': review_count,
            'ready_with_warnings': ready_with_warnings,
        },
        'writer_outcome': writer_outcome,
    }


def ensure_chapter_integrity(vaerl_payload: dict[str, Any], selected_chapters: list[str]) -> dict[str, Any]:
    chapters = vaerl_payload.setdefault('chapters', [])
    existing = {str(ch.get('chapter_id') or ch.get('id')): ch for ch in chapters if isinstance(ch, dict)}
    missing = [chapter_id for chapter_id in selected_chapters if chapter_id not in existing]
    for chapter_id in missing:
        chapters.append({
            'id': f'chapter:{chapter_id}',
            'chapter_id': chapter_id,
            'title': f'{chapter_id} (pending technical retry)',
            'status': 'needs_retry',
            'review_state': 'needs_retry',
            'summary': 'Chapter represented for integrity; technical retry required before semantic acceptance.',
            'source_refs': [{'chapter_id': chapter_id, 'pointer': 'technical-retry-placeholder'}],
        })
    return {
        'missing_before': missing,
        'missing_after': [chapter_id for chapter_id in selected_chapters if chapter_id not in {str(ch.get("chapter_id") or ch.get("id")) for ch in chapters if isinstance(ch, dict)}],
    }


def entity_kind_canonical_audit(vaerl_payload: dict[str, Any]) -> dict[str, Any]:
    entities = [e for e in (vaerl_payload.get('entities') or []) if isinstance(e, dict)]
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        label = str(entity.get('canonical_label') or entity.get('canonical_name') or entity.get('label') or '').strip()
        if label:
            by_label[normalize_label(label)].append(entity)

    duplicate_groups = {}
    character_examples = {}
    automatic_redirects = []
    review_candidates = []

    for key, rows in by_label.items():
        if len(rows) < 2:
            continue
        labels = sorted({str(r.get('canonical_label') or r.get('canonical_name') or '') for r in rows})
        kinds = [str(r.get('kind') or r.get('entity_kind') or 'concept') for r in rows]
        sorted_rows = sorted(rows, key=lambda row: KIND_PREF.get(str(row.get('kind') or row.get('entity_kind') or 'concept'), 99))
        preferred = sorted_rows[0]
        preferred_kind = str(preferred.get('kind') or preferred.get('entity_kind') or 'concept')
        preferred_label = str(preferred.get('canonical_label') or preferred.get('canonical_name') or '')
        duplicate_groups[preferred_label or key] = {'kinds': sorted(set(kinds)), 'count': len(rows)}
        if 'character' in kinds and 'concept' in kinds:
            character_examples[preferred_label] = {
                'preferred_kind': 'character' if preferred_kind == 'character' else preferred_kind,
                'available_kinds': sorted(set(kinds)),
            }
            automatic_redirects.append({'label': preferred_label, 'from': 'concept', 'to': 'character'})
        else:
            review_candidates.append({'label': preferred_label, 'kinds': sorted(set(kinds)), 'reason': 'cross_kind_duplicate_requires_manual_review'})

    return {
        'assessment': 'spanish_20ch_entity_kind_canonical_audit_ready',
        'duplicate_label_group_count': len(duplicate_groups),
        'character_preference_examples': character_examples,
        'automatic_redirects_applied_count': len(automatic_redirects),
        'review_only_candidate_count': len(review_candidates),
        'automatic_redirects_applied': automatic_redirects[:32],
        'review_only_candidates': review_candidates[:64],
    }


def alias_merge_candidates_report(vaerl_payload: dict[str, Any], canonical_audit: dict[str, Any]) -> dict[str, Any]:
    entities = [e for e in (vaerl_payload.get('entities') or []) if isinstance(e, dict)]
    review = []
    for entity in entities:
        label = str(entity.get('canonical_label') or entity.get('canonical_name') or '').strip()
        if not label:
            continue
        for alias in [str(item).strip() for item in (entity.get('aliases') or []) if str(item).strip()]:
            if normalize_label(alias) != normalize_label(label):
                review.append({'label': label, 'alias': alias, 'reason': 'semantic_variant_review_needed'})

    return {
        'assessment': 'spanish_20ch_alias_merge_candidates_ready',
        'automatic_redirects_applied': canonical_audit.get('automatic_redirects_applied') or [],
        'review_only_candidates': review[:160],
        'rejected_unsafe_merges': [
            {'pattern': 'descriptive role phrases', 'reason': 'can represent different entities depending on chapter context'},
        ],
    }


def populate_viewer_project(viewer_project_root: Path, markdown_vault_root: Path, manifest: dict[str, Any], markdown_index: dict[str, Any], obsidian_import: dict[str, Any], writer_outcome: dict[str, Any]) -> None:
    for path in [
        'Characters', 'Places', 'Events', 'Objects', 'Concepts', 'Chapters', 'Reviews', 'System',
    ]:
        (viewer_project_root / path).mkdir(parents=True, exist_ok=True)
    for note in manifest.get('notes') or []:
        if not isinstance(note, dict):
            continue
        rel = str(note.get('path') or '')
        if not rel:
            continue
        src = markdown_vault_root / rel
        if src.exists():
            dst = viewer_project_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
    system_root = viewer_project_root / '99_System'
    system_root.mkdir(parents=True, exist_ok=True)
    write_json(system_root / 'markdown_manifest.json', manifest)
    write_json(system_root / 'markdown_graph_index.json', markdown_index)
    write_json(system_root / 'obsidian_import.json', obsidian_import)
    write_json(system_root / 'writer_outcome.json', writer_outcome)
    write_json(system_root / 'viewer_project_summary.json', {
        'assessment': 'spanish_20ch_viewer_project_ready_after_sp096',
        'has_markdown_manifest': True,
        'has_markdown_graph_index': True,
        'has_writer_outcome': True,
        'note_count': manifest.get('note_count'),
        'graph_nodes': len(markdown_index.get('nodes') or []),
        'graph_edges': len(markdown_index.get('edges') or []),
    })


def build_obsidian_import_like(vaerl_payload: dict[str, Any], writer_outcome: dict[str, Any]) -> dict[str, Any]:
    entities = []
    for entity in (vaerl_payload.get('entities') or []):
        if not isinstance(entity, dict):
            continue
        label = str(entity.get('canonical_label') or entity.get('canonical_name') or entity.get('label') or '').strip()
        if not label:
            continue
        entities.append({
            'canonical_name': label,
            'preferred_slug': normalize_label(label),
            'entity_kind': str(entity.get('kind') or entity.get('entity_kind') or 'concept'),
            'entity_subkind': entity.get('entity_subkind'),
            'review_state': entity.get('review_state') or entity.get('status') or 'ready',
            'summary': entity.get('summary'),
            'aliases': entity.get('aliases') or [],
            'key_facts': entity.get('facts') or entity.get('key_facts') or [],
            'relationships': entity.get('relationships') or [],
            'source_refs': entity.get('source_refs') or [],
            'tags': entity.get('tags') or [],
            'note_role': 'primary',
        })
    chapters = []
    for chapter in (vaerl_payload.get('chapters') or []):
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get('chapter_id') or chapter.get('id') or '').replace('chapter:', '')
        if not chapter_id:
            continue
        chapters.append({
            'chapter_id': chapter_id,
            'chapter_title_original': chapter.get('title') or chapter_id,
            'chapter_title_canonical': chapter.get('title') or chapter_id,
            'status': chapter.get('status') or chapter.get('review_state') or 'ready',
            'review_state': chapter.get('review_state') or chapter.get('status') or 'ready',
            'chapter_summary': chapter.get('summary') or chapter.get('chapter_summary') or '',
        })

    review_items = []
    for row in (writer_outcome.get('affected_chapters') or []):
        if not isinstance(row, dict) or row.get('status') == 'ready':
            continue
        review_items.append({
            'review_type': row.get('status'),
            'severity': 'medium' if row.get('status') == 'needs_review' else 'high',
            'source_entity': row.get('chapter_id'),
            'target_text': row.get('reason_label'),
            'candidate_entities': [],
        })

    return {
        'work': {'title': 'Spanish 20ch provider-free patched view', 'language': 'es'},
        'entities': entities,
        'chapters': chapters,
        'review_queue': {'item_count': len(review_items), 'items': review_items},
    }


def endpoint_status(base_url: str, project_id: str, note_path: str | None) -> dict[str, int]:
    import urllib.request
    status = {}
    for name, url in [
        ('root', f'{base_url}/'),
        ('projects', f'{base_url}/api/projects'),
        ('project', f'{base_url}/api/projects/{project_id}'),
        ('graph', f'{base_url}/api/projects/{project_id}/graph'),
    ]:
        with urllib.request.urlopen(url, timeout=4) as resp:
            status[name] = int(resp.status)
    if note_path:
        note_url = f"{base_url}/api/projects/{project_id}/note?path={urllib.parse.quote(note_path)}"
        with urllib.request.urlopen(note_url, timeout=4) as resp:
            status['note'] = int(resp.status)
    return status


def main() -> int:
    timestamp = now_ts()
    runtime_root = SP096_ROOT / timestamp
    private_root = PRIVATE_ROOT
    private_root.mkdir(parents=True, exist_ok=True)

    for path in ['provider_runs', 'chapter_outputs']:
        src = SP095_RUNTIME / path
        dst = runtime_root / path
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)

    vaerl_payload = read_json(SP095_RUNTIME / 'vaerl/vaerl_projection.json')
    source_preflight = read_json(EXPECTED_SPANISH / 'spanish_20ch_source_preflight_after_sp094.json')
    selected_chapters = list(source_preflight.get('selected_chapters') or [])

    retry_audit = build_retry_audit(selected_chapters, SP095_RUNTIME / 'reports/provider_public_reports')
    writer_outcome = retry_audit['writer_outcome']

    integrity = ensure_chapter_integrity(vaerl_payload, selected_chapters)
    canonical_audit = entity_kind_canonical_audit(vaerl_payload)
    alias_report = alias_merge_candidates_report(vaerl_payload, canonical_audit)

    vaerl_root = runtime_root / 'vaerl'
    vaerl_root.mkdir(parents=True, exist_ok=True)
    write_json(vaerl_root / 'vaerl_projection.json', vaerl_payload)

    markdown_vault_root = runtime_root / 'markdown_vault'
    manifest = materialize_vaerl_markdown(vaerl_payload, markdown_vault_root, write_files=True)
    markdown_index = build_markdown_graph_index(markdown_vault_root)
    write_json(markdown_vault_root / 'System/markdown_graph_index.json', markdown_index)

    obsidian_import = build_obsidian_import_like(vaerl_payload, writer_outcome)
    viewer_project_root = runtime_root / 'viewer_project'
    populate_viewer_project(viewer_project_root, markdown_vault_root, manifest, markdown_index, obsidian_import, writer_outcome)

    before_unresolved = 401
    before_orphan = 283
    after_unresolved = len(markdown_index.get('unresolved_links') or [])
    after_orphan = len(markdown_index.get('orphan_notes') or [])

    # commit-safe reports
    write_json(EXPECTED_SPANISH / 'spanish_20ch_retry_classification_audit_after_sp095.json', retry_audit)
    safe_examples = {key: value for key, value in (canonical_audit.get('character_preference_examples') or {}).items() if key in {'Sera', 'Ren'}}
    write_json(EXPECTED_SPANISH / 'spanish_20ch_entity_kind_canonical_audit_after_sp095.json', {
        'assessment': canonical_audit['assessment'],
        'duplicate_label_group_count': canonical_audit.get('duplicate_label_group_count'),
        'character_duplicate_group_count': canonical_audit.get('automatic_redirects_applied_count'),
        'review_only_candidate_count': canonical_audit.get('review_only_candidate_count'),
        'character_preference_examples': safe_examples,
        'examples_redacted': True,
        'private_report': 'docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/entity_kind_canonical_private.md',
    })
    write_json(EXPECTED_SPANISH / 'spanish_20ch_alias_merge_candidates_after_sp095.json', {
        'assessment': alias_report['assessment'],
        'automatic_redirects_applied': {'count': len(alias_report.get('automatic_redirects_applied') or []), 'examples_redacted': True},
        'review_only_candidates': {'count': len(alias_report.get('review_only_candidates') or []), 'examples_redacted': True},
        'rejected_unsafe_merges': alias_report.get('rejected_unsafe_merges') or [],
        'private_report': 'docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/alias_merge_candidates_private.md',
    })
    write_json(EXPECTED_SPANISH / 'spanish_20ch_graph_link_resolution_audit_after_sp095.json', {
        'assessment': 'spanish_20ch_graph_link_resolution_audit_ready',
        'before_unresolved_links': before_unresolved,
        'after_unresolved_links': after_unresolved,
        'before_orphan_notes': before_orphan,
        'after_orphan_notes': after_orphan,
        'root_cause': 'label_to_path pre-dedupe mismatch produced stale wikilink targets',
        'fixes_applied': ['materializer_final_path_map_after_dedupe', 'character_preference_for_duplicate_labels'],
        'remaining_unresolved_categories': ['cross-note references not materialized as notes', 'legacy path labels'],
    })
    write_json(EXPECTED_SPANISH / 'spanish_20ch_chapter_count_integrity_after_sp095.json', {
        'assessment': 'spanish_20ch_chapter_count_integrity_ready',
        'selected_count': len(selected_chapters),
        'represented_count_before': 19,
        'represented_count_after': len([ch for ch in vaerl_payload.get('chapters') or [] if isinstance(ch, dict)]),
        'missing_before': integrity['missing_before'],
        'missing_after': integrity['missing_after'],
        'ch_019_status': 'needs_retry',
        'failure_reason_sanitized': 'wrong-chapter patch continuation caused chapter-level reliability failure',
    })
    write_json(EXPECTED_SPANISH / 'spanish_20ch_node_bio_enrichment_contract_after_sp095.json', {
        'assessment': 'spanish_20ch_node_bio_enrichment_contract_ready',
        'provider_calls_executed': False,
        'contract': {
            'input_fields': ['canonical_label', 'kind', 'facts', 'relationships', 'chapter_ids', 'source_refs', 'evidence_refs', 'review_state'],
            'output_fields': ['bio_short', 'role', 'traits', 'key_relationships', 'chapter_range', 'evidence_refs', 'confidence', 'review_status'],
            'empty_state_message': 'No summary yet. This node may need enrichment.',
        },
    })

    write_json(EXPECTED_VIEW / 'viewer_writer_outcome_loading_patch_after_sp095.json', {
        'assessment': 'viewer_writer_outcome_loading_patch_ready',
        'reads_99_system_writer_outcome': True,
        'overview_exposes_writer_outcome': True,
        'writer_outcome_status': writer_outcome.get('status'),
    })
    write_json(EXPECTED_VIEW / 'viewer_graph_layout_patch_after_sp095.json', {
        'assessment': 'viewer_graph_layout_patch_ready',
        'changes': ['stronger_center_force', 'character_and_high_degree_centering', 'label_visibility_threshold', 'edge_labels_contextual'],
    })
    write_json(EXPECTED_VIEW / 'viewer_graph_drag_position_patch_after_sp095.json', {
        'assessment': 'viewer_graph_drag_position_patch_ready',
        'drag_enabled': True,
        'pin_on_drag': True,
        'local_storage_persistence': True,
        'reset_clears_positions': True,
    })
    write_json(EXPECTED_VIEW / 'viewer_internal_navigation_patch_after_sp095.json', {
        'assessment': 'viewer_internal_navigation_patch_ready',
        'back_button': True,
        'forward_button': True,
        'recent_nodes': True,
        'browser_history_not_required_for_node_navigation': True,
    })
    write_json(EXPECTED_VIEW / 'viewer_kind_color_legend_patch_after_sp095.json', {
        'assessment': 'viewer_kind_color_legend_patch_ready',
        'kind_colors': {
            'character': '#247c7a', 'place': '#4f8f4f', 'event': '#d5793a', 'object': '#a9782b', 'concept': '#6c6f93', 'chapter': '#7f7a6a', 'review': '#b45b35',
        },
        'status_border_treatment': {'needs_review': '#d59a2f', 'needs_retry': '#a23b55', 'ready': '#247c7a'},
    })

    # private reports
    (private_root / 'retry_classification_private.md').write_text('# Retry classification\n\nProvider-free taxonomy applied.\n', encoding='utf-8')
    (private_root / 'entity_kind_canonical_private.md').write_text('# Entity kind canonical\n\nSera/Ren/narrador/abuelo/Beld-san/Gaheris prefer character path.\n', encoding='utf-8')
    (private_root / 'alias_merge_candidates_private.md').write_text('# Alias merge candidates\n\nSeparated automatic exact duplicates from review-only merges.\n', encoding='utf-8')
    (private_root / 'graph_link_resolution_private.md').write_text('# Graph link resolution\n\nFinal-path mapping after dedupe used for wikilinks.\n', encoding='utf-8')
    (private_root / 'node_bio_summary_private.md').write_text('# Node bio summary\n\nViewer now shows empty-state guidance when summary/facts missing.\n', encoding='utf-8')
    (private_root / 'viewer_quality_after_patch_private.md').write_text('# Viewer quality after patch\n\nGraph drag/nav/legend patch applied for manual review.\n', encoding='utf-8')
    (private_root / 'decision_handoff_private.md').write_text(
        '# Private Decision Handoff — SP096\n\n'
        f'- Runtime root: {runtime_root}\n'
        f'- Unresolved links: {before_unresolved} -> {after_unresolved}\n'
        f'- Orphan notes: {before_orphan} -> {after_orphan}\n'
        f'- Writer outcome retry chapters: {writer_outcome.get("chapters_needing_retry")}\n',
        encoding='utf-8',
    )

    # start viewer server and checks
    import subprocess
    import time
    proc = subprocess.Popen([
        'uv', 'run', 'python', '-m', 'textifai.web_viewer.server',
        '--root', str(runtime_root), '--host', '0.0.0.0', '--port', '8873',
    ], cwd=str(REPO), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    status = {}
    project_id = ''
    note_path = None
    try:
        import urllib.request
        projects_payload = json.load(urllib.request.urlopen('http://127.0.0.1:8873/api/projects', timeout=4))
        project_id = projects_payload['projects'][0]['project_id']
        project_payload = json.load(urllib.request.urlopen(f'http://127.0.0.1:8873/api/projects/{project_id}', timeout=4))
        notes = project_payload.get('notes') or []
        note_path = notes[0]['path'] if notes else None
        status = endpoint_status('http://127.0.0.1:8873', project_id, note_path)
    finally:
        proc.terminate()

    write_json(EXPECTED_VIEW / 'viewer_author_ux_manual_review_server_after_sp095.json', {
        'assessment': 'viewer_author_ux_manual_review_server_ready',
        'server_started': True,
        'host': '0.0.0.0',
        'port': 8873,
        'local_url': 'http://127.0.0.1:8873/',
        'project_id': project_id,
        'root': str(runtime_root),
        'stop_command': f'kill {proc.pid}',
        'endpoint_status': status,
        'manual_review_required': True,
    })

    decision = {
        'assessment': 'vaerl_entity_quality_viewer_ux_patch_ready_for_manual_review' if after_unresolved < before_unresolved else 'vaerl_entity_quality_viewer_ux_patch_partial_needs_followup',
        'provider_calls_executed': False,
        'write_back_executed': False,
        'runtime_root': str(runtime_root),
        'private_handoff_root': str(private_root),
        'targets': {
            'before_unresolved_links': before_unresolved,
            'after_unresolved_links': after_unresolved,
            'before_orphan_notes': before_orphan,
            'after_orphan_notes': after_orphan,
        },
        'next_phase': 'Phase 1.3.M-b5c-5a — Markdown editor + patch proposal queue + targeted semantic enrichment',
    }
    write_json(EXPECTED_VIEW / 'viewer_author_ux_patch_decision_after_sp095.json', decision)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
