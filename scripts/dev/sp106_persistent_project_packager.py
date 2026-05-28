from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.import_review.markdown_graph_index import build_markdown_graph_index
from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.web_viewer.project_reader import ProjectRef, build_graph, read_project


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='SP-106 packager: runtime -> persistent TextifAI project package')
    parser.add_argument('--runtime-root', required=True, help='Runtime root or runtime base containing timestamped runs')
    parser.add_argument('--project-root', required=True, help='Persistent project root, e.g. /home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
    parser.add_argument('--source-file', required=True)
    parser.add_argument('--title', default='Ouja no Tsue')
    parser.add_argument('--language', default='es')
    parser.add_argument('--textifai-version', default='1.3.M-b5c-5r')
    parser.add_argument('--registry-path', default='.textifai_runs/registry.local.json')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_input = Path(args.runtime_root).resolve()
    runtime_root = resolve_runtime_root(runtime_input)
    source_file = Path(args.source_file).resolve()
    project_root = Path(args.project_root).resolve()

    if not runtime_root.exists():
        raise SystemExit(f'runtime root missing: {runtime_root}')
    if not source_file.exists():
        raise SystemExit(f'source file missing: {source_file}')

    viewer_root = runtime_root / 'viewer_project'
    markdown_vault_root = runtime_root / 'markdown_vault'
    vaerl_root = runtime_root / 'vaerl'
    reports_root = runtime_root / 'reports'
    provider_runs_root = runtime_root / 'provider_runs'

    project_root.mkdir(parents=True, exist_ok=True)

    ensure_dirs(project_root)

    copy_markdown(markdown_vault_root, project_root / 'markdown')
    materialize_source_chapters(source_file, project_root / 'markdown' / 'Chapters')
    copy_compat_system(viewer_root / '99_System', project_root / '99_System')

    manifest_source = project_root / '99_System' / 'markdown_manifest.json'
    if not manifest_source.exists():
        manifest_source = markdown_vault_root / 'System' / 'materialization_manifest.json'
    manifest = json.loads(manifest_source.read_text(encoding='utf-8'))
    rewrite_markdown_manifest_paths(manifest)
    write_json(project_root / '99_System' / 'markdown_manifest.json', manifest)

    markdown_index = build_markdown_graph_index(project_root)
    write_json(project_root / '99_System' / 'markdown_graph_index.json', markdown_index)
    write_json(project_root / 'graph' / 'markdown_graph_index.json', markdown_index)

    vaerl_payload = read_json(vaerl_root / 'vaerl_projection.json')
    if not (project_root / '99_System' / 'review_queue.json').exists():
        reviews = [row for row in (vaerl_payload.get('reviews') or []) if isinstance(row, dict)]
        derived_queue = {
            'item_count': len(reviews),
            'items': reviews,
            'counts_by_severity': count_by_key(reviews, 'severity', default='medium'),
            'counts_by_type': count_by_key(reviews, 'review_type', default='review'),
        }
        write_json(project_root / '99_System' / 'review_queue.json', derived_queue)
    write_json(project_root / 'vaerl' / 'vaerl.json', vaerl_payload)
    write_json(project_root / 'vaerl' / 'entities.json', {'entities': vaerl_payload.get('entities') or []})
    write_json(project_root / 'vaerl' / 'relationships.json', {'relationships': collect_relationships(vaerl_payload.get('entities') or [])})
    review_queue = read_json(project_root / '99_System' / 'review_queue.json')
    write_json(project_root / 'vaerl' / 'review_queue.json', review_queue if isinstance(review_queue, dict) else {'item_count': 0, 'items': []})

    graph_payload = build_graph(ProjectRef(project_id='tmp', name='tmp', root=project_root, system_root=project_root / '99_System', kind='textifai_project'))
    write_json(project_root / 'graph' / 'graph.json', graph_payload)
    write_json(project_root / 'graph' / 'backlinks.json', build_backlinks_map(markdown_index))

    # Reports + dev folders
    if reports_root.exists():
        for file in reports_root.rglob('*.json'):
            rel = file.relative_to(reports_root)
            dst = project_root / 'dev' / 'raw_artifacts' / 'reports' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dst)
    if provider_runs_root.exists():
        dst = project_root / 'dev' / 'provider_outputs' / provider_runs_root.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(provider_runs_root, dst)

    chapters = sorted((project_root / 'markdown' / 'Chapters').glob('Ch_*.md'))
    project_view = read_project(ProjectRef(project_id='tmp', name='tmp', root=project_root, system_root=project_root / '99_System', kind='textifai_project'))

    write_json(project_root / 'reports' / 'ingestion_summary.json', {
        'assessment': 'persistent_20ch_package_generated',
        'runtime_root': str(runtime_root),
        'chapter_count': len(chapters),
        'note_count': len(project_view.get('notes') or []),
        'graph_nodes': len((project_view.get('graph') or {}).get('nodes') or []),
        'graph_edges': len((project_view.get('graph') or {}).get('edges') or []),
    })
    write_json(project_root / 'reports' / 'project_health.json', project_view.get('health') or {})

    source_hash = sha256_text(source_file)
    writer_outcome = read_json(project_root / '99_System' / 'writer_outcome.json')
    textifai_manifest = build_project_manifest(
        project_root=project_root,
        title=args.title,
        language=args.language,
        source_hash=source_hash,
        source_name=source_file.name,
        chapter_count=len(chapters),
        note_count=len(project_view.get('notes') or []),
        graph_nodes=len((project_view.get('graph') or {}).get('nodes') or []),
        graph_edges=len((project_view.get('graph') or {}).get('edges') or []),
        review_items=int((read_json(project_root / 'vaerl' / 'review_queue.json').get('item_count') or 0)),
        textifai_version=args.textifai_version,
        writer_outcome=writer_outcome,
    )
    write_json(project_root / 'textifai.project.json', textifai_manifest)

    update_registry(Path(args.registry_path), project_root / 'textifai.project.json')

    print(json.dumps({
        'assessment': 'sp106_packager_completed',
        'runtime_root': str(runtime_root),
        'project_root': str(project_root),
        'manifest_path': str(project_root / 'textifai.project.json'),
        'chapter_count': len(chapters),
    }, ensure_ascii=False, indent=2))
    return 0


def resolve_runtime_root(runtime_input: Path) -> Path:
    if (runtime_input / 'viewer_project').exists():
        return runtime_input
    dirs = [p for p in runtime_input.iterdir() if p.is_dir()]
    dirs = sorted(dirs)
    if not dirs:
        raise SystemExit(f'No runtime folders found in: {runtime_input}')
    candidate = dirs[-1]
    if not (candidate / 'viewer_project').exists():
        raise SystemExit(f'Latest runtime has no viewer_project: {candidate}')
    return candidate


def ensure_dirs(project_root: Path) -> None:
    for rel in [
        'markdown/Chapters', 'markdown/Characters', 'markdown/Places', 'markdown/Events', 'markdown/Objects', 'markdown/Concepts', 'markdown/Reviews',
        'vaerl', 'graph',
        'drafts/chapters', 'drafts/notes',
        'patches/pending', 'patches/applied', 'patches/rejected',
        'reports',
        'dev/diagnostics', 'dev/raw_artifacts', 'dev/provider_outputs',
        '99_System',
    ]:
        (project_root / rel).mkdir(parents=True, exist_ok=True)


def copy_markdown(markdown_vault_root: Path, markdown_dst_root: Path) -> None:
    for folder in ['Chapters', 'Characters', 'Places', 'Events', 'Objects', 'Concepts', 'Reviews']:
        src = markdown_vault_root / folder
        dst = markdown_dst_root / folder
        if src.exists():
            dst.mkdir(parents=True, exist_ok=True)
            for path in src.glob('*.md'):
                name = path.name
                if folder == 'Chapters':
                    name = normalize_chapter_filename(path.name)
                shutil.copy2(path, dst / name)


def materialize_source_chapters(source_file: Path, chapters_root: Path) -> None:
    text = source_file.read_text(encoding='utf-8', errors='replace')
    checksum = hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()
    record = SourceDocumentRecord(
        source_id=f'source_{checksum[:10]}',
        path=str(source_file),
        relative_path=source_file.name,
        filename=source_file.name,
        extension=source_file.suffix.lstrip('.'),
        size_bytes=source_file.stat().st_size,
        checksum=checksum,
        dominant_language='es',
        detected_languages=['es'],
        line_count=len(text.splitlines()),
        extracted_char_count=len(text),
        extracted_word_count=len(text.split()),
        extracted_page_count=0,
    )
    chapters = detect_story_chapters(record, text)[:20]
    if len(chapters) < 20:
        raise SystemExit(f'chapterizer detected only {len(chapters)} chapters; expected 20')
    chapters_root.mkdir(parents=True, exist_ok=True)
    for index, chapter in enumerate(chapters, start=1):
        path = chapters_root / f'Ch_{index:03d}.md'
        title = str(chapter.title or f'Capítulo {index:03d}').strip()
        body = chapter.text.strip()
        frontmatter = [
            '---',
            f'vaerl_id: chapter:ch_{index:03d}',
            'kind: chapter',
            f'canonical_label: {json.dumps(title, ensure_ascii=False)}',
            'tags:',
            '  - chapter',
            'status: ready',
            'review_state: ready',
            'chapter_ids:',
            f'  - ch_{index:03d}',
            'source_refs: []',
            '---',
            '',
            f'# {title}',
            '',
        ]
        path.write_text('\n'.join(frontmatter) + body + '\n', encoding='utf-8')


def copy_compat_system(system_src: Path, system_dst: Path) -> None:
    system_dst.mkdir(parents=True, exist_ok=True)
    for name in ['obsidian_import.json', 'review_queue.json', 'semantic_invariants_audit.json', 'canonical_entity_map.json', 'resolved_entities.json', 'cleaned_entities.json', 'run_comparability_manifest.json', 'writer_outcome.json', 'markdown_manifest.json', 'markdown_graph_index.json', 'ingestion_graph.json']:
        src = system_src / name
        if src.exists():
            shutil.copy2(src, system_dst / name)
    materialization_manifest = system_src.parent.parent / 'markdown_vault' / 'System' / 'materialization_manifest.json'
    if materialization_manifest.exists() and not (system_dst / 'markdown_manifest.json').exists():
        shutil.copy2(materialization_manifest, system_dst / 'markdown_manifest.json')
    chapter_outputs = system_src / 'chapter_outputs'
    if chapter_outputs.exists():
        dst = system_dst / 'chapter_outputs'
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(chapter_outputs, dst)


def normalize_chapter_filename(name: str) -> str:
    stem = Path(name).stem
    digits = ''.join(ch for ch in stem if ch.isdigit())
    if digits:
        return f"Ch_{int(digits):03d}.md"
    return name


def rewrite_markdown_manifest_paths(manifest: dict[str, Any]) -> None:
    notes = manifest.get('notes') or []
    for note in notes:
        if not isinstance(note, dict):
            continue
        path = str(note.get('path') or '')
        if path.startswith('Chapters/'):
            path = f"markdown/Chapters/{normalize_chapter_filename(Path(path).name)}"
        elif path and not path.startswith('markdown/'):
            path = f"markdown/{path}"
        note['path'] = path
    manifest['output_root'] = 'markdown'
    manifest['note_count'] = len([note for note in notes if isinstance(note, dict)])


def collect_relationships(entities: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        source = entity.get('canonical_label') or entity.get('canonical_name') or entity.get('id')
        for rel in entity.get('relationships') or []:
            if not isinstance(rel, dict):
                continue
            rows.append({
                'source': source,
                'target': rel.get('target_label') or rel.get('target') or rel.get('to'),
                'label': rel.get('label') or rel.get('type') or rel.get('relation_type') or 'related_to',
                'source_refs': rel.get('source_refs') or [],
            })
    return rows


def count_by_key(rows: list[dict[str, Any]], key: str, *, default: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).lower()
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_backlinks_map(markdown_index: dict[str, Any]) -> dict[str, Any]:
    backlinks: dict[str, list[str]] = {}
    for edge in markdown_index.get('edges') or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get('source') or '')
        target = str(edge.get('target') or '')
        if source and target:
            backlinks.setdefault(target, []).append(source)
    return {'backlinks_by_note': {k: sorted(set(v)) for k, v in backlinks.items()}}


def sha256_text(path: Path) -> str:
    data = path.read_text(encoding='utf-8', errors='replace').encode('utf-8', errors='replace')
    return hashlib.sha256(data).hexdigest()


def build_project_manifest(
    *,
    project_root: Path,
    title: str,
    language: str,
    source_hash: str,
    source_name: str,
    chapter_count: int,
    note_count: int,
    graph_nodes: int,
    graph_edges: int,
    review_items: int,
    textifai_version: str,
    writer_outcome: Any,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    writer_outcome_path = '99_System/writer_outcome.json' if (project_root / '99_System/writer_outcome.json').exists() else None
    return {
        'schema': 'textifai.project',
        'schema_version': 1,
        'project_id': 'ont-spanish-20ch',
        'title': title,
        'language': language,
        'created_at': now,
        'updated_at': now,
        'textifai_version': textifai_version,
        'source': {
            'kind': 'manuscript_markdown',
            'original_filename': source_name,
            'source_hash': f'sha256:{source_hash}',
            'stored_in_project': False,
        },
        'paths': {
            'markdown_root': 'markdown',
            'chapters_root': 'markdown/Chapters',
            'characters_root': 'markdown/Characters',
            'places_root': 'markdown/Places',
            'events_root': 'markdown/Events',
            'objects_root': 'markdown/Objects',
            'concepts_root': 'markdown/Concepts',
            'reviews_root': 'markdown/Reviews',
            'vaerl': 'vaerl/vaerl.json',
            'entities': 'vaerl/entities.json',
            'relationships': 'vaerl/relationships.json',
            'review_queue': 'vaerl/review_queue.json',
            'graph': 'graph/graph.json',
            'backlinks': 'graph/backlinks.json',
            'markdown_graph_index': 'graph/markdown_graph_index.json',
            'markdown_manifest': '99_System/markdown_manifest.json',
            'writer_outcome': writer_outcome_path,
            'drafts': 'drafts',
            'patches': 'patches',
            'reports': 'reports',
            'dev': 'dev',
        },
        'status': {
            'chapters_total': chapter_count,
            'chapters_ready': int((writer_outcome or {}).get('chapters_ready') or chapter_count),
            'retry_required': int((writer_outcome or {}).get('chapters_needing_retry') or 0),
            'review_items': review_items,
            'graph_nodes': graph_nodes,
            'graph_edges': graph_edges,
            'vaerl_ready': graph_nodes > 0,
            'graph_ready': graph_nodes > 0,
            'review_ready': review_items >= 0,
        },
        'capabilities': {
            'read_only': True,
            'editable_markdown': False,
            'drafts': True,
            'patch_queue': False,
            'chapter_mini_ingestion': False,
            'vaerl_update': False,
        },
        'privacy': {
            'contains_source_prose': True,
            'contains_provider_outputs': True,
            'safe_to_commit': False,
            'shareable_package': False,
        },
        'dev': {
            'runtime_origin': 'sp106_spanish_20ch_e2e',
            'contains_private_provider_outputs': True,
        },
        'workspace_entry': {
            'default_screen': 'Project Hub',
            'editor_source': 'markdown/Chapters',
            'graph_source': 'graph/graph.json',
            'review_source': 'vaerl/review_queue.json',
        },
    }


def update_registry(registry_path: Path, manifest_path: Path) -> None:
    registry = {'schema': 'textifai.local_registry', 'schema_version': 1, 'projects': []}
    if registry_path.exists():
        current = read_json(registry_path)
        if isinstance(current, dict):
            registry = current
    projects = [row for row in (registry.get('projects') or []) if isinstance(row, dict)]
    manifest_value = str(manifest_path)
    projects = [row for row in projects if str(row.get('manifest_path') or '') != manifest_value]
    projects.insert(0, {
        'manifest_path': manifest_value,
        'added_at': datetime.now(UTC).isoformat(),
    })
    registry['projects'] = projects[:20]
    write_json(registry_path, registry)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
