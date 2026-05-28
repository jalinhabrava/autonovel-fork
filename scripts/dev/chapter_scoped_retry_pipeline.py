from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.import_review.chapter_scoped_retry import (
    build_chapter_graph_patch,
    build_chapter_retry_result,
    build_chapter_review_patch,
    build_chapter_subchunks,
    build_chapter_vaerl_patch,
    read_json,
    write_json,
)

FAILED_DEFAULT = ['ch_005','ch_006','ch_007','ch_008','ch_009','ch_010','ch_011','ch_012','ch_015','ch_016','ch_018','ch_019','ch_020']


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Chapter-scoped adaptive retry pipeline')
    p.add_argument('--project-root', required=True)
    p.add_argument('--chapter-ids', default='')
    p.add_argument('--provider-pilot', action='store_true')
    p.add_argument('--pilot-limit', type=int, default=2)
    return p.parse_args()


def parse_chapter_ids(raw: str | None) -> list[str]:
    if not raw:
        return list(FAILED_DEFAULT)
    out = []
    for item in str(raw).split(','):
        item = item.strip()
        if not item:
            continue
        if not item.startswith('ch_') or len(item) != 6 or not item[-3:].isdigit():
            raise SystemExit(f'invalid chapter id: {item}')
        out.append(item)
    if not out:
        raise SystemExit('no chapter ids selected')
    return out


def chapter_markdown_path(project_root: Path, chapter_id: str) -> Path:
    idx = int(chapter_id.split('_')[1])
    return project_root / 'markdown' / 'Chapters' / f'Ch_{idx:03d}.md'


def chapter_retry_private_dir(project_root: Path) -> Path:
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    return project_root / 'dev' / 'provider_outputs' / 'chapter_scoped_retry_sp106e' / stamp


def previous_score(project_root: Path, chapter_id: str) -> int | None:
    retry_root = project_root / 'dev' / 'provider_outputs' / 'targeted_retry_sp106b' / '20260528T184056Z' / 'private' / '20260528T184056Z'
    d = next((p for p in retry_root.glob(f'{chapter_id}__*') if p.is_dir()), None)
    if not d:
        return None
    for rpt in d.rglob('validation_report.json'):
        try:
            data = json.loads(rpt.read_text(encoding='utf-8'))
            if data.get('score') is not None:
                return int(data['score'])
        except Exception:
            pass
    return None


def previous_parsed(project_root: Path, chapter_id: str) -> dict[str, Any] | None:
    retry_root = project_root / 'dev' / 'provider_outputs' / 'targeted_retry_sp106b' / '20260528T184056Z' / 'private' / '20260528T184056Z'
    d = next((p for p in retry_root.glob(f'{chapter_id}__*') if p.is_dir()), None)
    if not d:
        return None
    parsed = d / 'reduction' / 'provider_response_parsed.json'
    if parsed.exists():
        return read_json(parsed)
    return None


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root)
    chapter_ids = parse_chapter_ids(args.chapter_ids)
    out_root = chapter_retry_private_dir(project_root)
    selected = chapter_ids[: args.pilot_limit] if args.provider_pilot else chapter_ids
    results = []
    for chapter_id in selected:
        md_path = chapter_markdown_path(project_root, chapter_id)
        markdown = md_path.read_text(encoding='utf-8', errors='replace') if md_path.exists() else ''
        subchunks = build_chapter_subchunks(chapter_id, markdown)
        parsed = previous_parsed(project_root, chapter_id) or {'chapters': [{'chapter_id': chapter_id, 'characters': [], 'places': [], 'concepts': [], 'objects': [], 'events': [], 'relations': [], 'unresolved_mentions': [], 'chapter_summary': ''}]}
        vaerl_patch = build_chapter_vaerl_patch(parsed)
        graph_patch = build_chapter_graph_patch(vaerl_patch)
        review_patch = build_chapter_review_patch(vaerl_patch)
        croot = out_root / chapter_id
        vp = croot / 'chapter_vaerl_patch.json'
        gp = croot / 'chapter_graph_patch.json'
        rp = croot / 'chapter_review_patch.json'
        ip = croot / 'integration_report.json'
        write_json(vp, vaerl_patch)
        write_json(gp, graph_patch)
        write_json(rp, review_patch)
        integration_report = {
            'chapter_id': chapter_id,
            'integration_supported': False,
            'integration_applied': False,
            'reason': 'provider pilot disabled in dry pipeline' if not args.provider_pilot else 'provider pilot not implemented in this script',
        }
        write_json(ip, integration_report)
        result = build_chapter_retry_result(
            chapter_id=chapter_id,
            pre_retry_score=previous_score(project_root, chapter_id),
            post_retry_score=None,
            subchunks=subchunks,
            vaerl_patch_path=str(vp),
            graph_patch_path=str(gp),
            review_patch_path=str(rp),
            integration_report_path=str(ip),
            integration_applied=False,
            status='still_needs_retry',
        )
        write_json(croot / 'chapter_retry_result.json', result)
        results.append(result)
    write_json(out_root / 'run_summary.json', {
        'schema': 'textifai.chapter_scoped_retry_run',
        'schema_version': 1,
        'selected_chapter_ids': chapter_ids,
        'provider_pilot': bool(args.provider_pilot),
        'pilot_selected_chapters': selected,
        'results': results,
    })
    print(out_root)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
