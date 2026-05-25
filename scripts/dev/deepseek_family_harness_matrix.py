from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_REAL_DRYRUN_PATH = Path(__file__).with_name("real_provider_dryrun.py")
_SPEC = importlib.util.spec_from_file_location("real_provider_dryrun_for_family_matrix", _REAL_DRYRUN_PATH)
assert _SPEC and _SPEC.loader
_REAL_DRYRUN = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _REAL_DRYRUN
_SPEC.loader.exec_module(_REAL_DRYRUN)

DEFAULT_OUTPUT_ROOT = Path('/tmp/textifai_deepseek_family_harness_matrix')
REQUIRED_SECTIONS = ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]


@dataclass(frozen=True)
class FamilyVariant:
    variant_id: str
    overlay_text: str


FAMILY_VARIANTS: tuple[FamilyVariant, ...] = (
    FamilyVariant(
        variant_id='family_variant_1_broad_recall',
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Prioritize complete extraction over brevity.
Do not stop after summary or final outcome.

Extract all meaningful characters, places, concepts, objects, events, relations, and unresolved mentions.

Before final JSON, internally check whether you omitted:
- role-significant characters;
- event-triggering objects;
- durable state-change events;
- evidence-backed relations;
- important unresolved mentions.

If supported by evidence, include it.
If uncertain, use review/local_candidate or unresolved_mentions.
Do not output your checklist.
Do not invent names.""",
    ),
    FamilyVariant(
        variant_id='family_variant_2_oer_focus',
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Do not compress into summary only.

Focus especially on:
1. objects: include all tools, artifacts, catalysts, weapons, restraints, keys, props that trigger or explain events.
2. events: include all durable state changes, not only the final outcome.
3. relations: include all evidence-backed links involving protagonist, authority, places, objects, concepts, and events.
4. unresolved_mentions: do not drop important unknown references.

Also include characters, places, and concepts normally.
Keep facts concise.
Keep uncertainty in review/local_candidate.
Do not invent names.""",
    ),
    FamilyVariant(
        variant_id='family_variant_3_balanced_kb',
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Extract for a story knowledge base, not for a short summary.

Include evidence-supported:
- characters and important unnamed roles;
- places and subplaces;
- concepts and magic/system states;
- objects, tools, artifacts, catalysts, weapons, restraints, keys, and event-triggering props;
- durable events;
- relations between extracted items;
- unresolved important mentions.

Prefer coverage over brevity, but keep each fact concise.
Use review/local_candidate when identity or canonical merge is uncertain.
Use unresolved_mentions instead of dropping unclear but important references.
Do not invent names.""",
    ),
    FamilyVariant(
        variant_id='family_variant_4_ch002_gap_attack',
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

This chapter may contain important objects, catalysts, authority relations, decisions, and unresolved references. Do not omit them.

After writing the summary, continue extracting:
- every catalyst/object/tool/physical or magical item that changes, breaks, enables, blocks, reveals, or triggers an event;
- every decision, discovery, status change, movement, threat, or magic/system change as an event;
- every relation connecting character-object, character-place, character-concept, object-event, authority-character, and concept-event;
- unresolved important references instead of dropping them.

Keep facts concise.
Use review/local_candidate for uncertain identity.
Do not invent names.""",
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='DeepSeek-family harness matrix runner.')
    parser.add_argument('--prompt-ch002', required=True)
    parser.add_argument('--prompt-ch003', required=True)
    parser.add_argument('--models', required=True, help='Comma-separated DeepSeek model ids discovered by /models.')
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument('--allow-provider-calls', action='store_true')
    parser.add_argument('--max-provider-requests', type=int, default=0)
    parser.add_argument('--max-output-tokens', type=int, default=8192)
    parser.add_argument('--response-format-json', action='store_true')
    parser.add_argument('--no-write-back', action='store_true', default=True)
    parser.add_argument('--provider', default='deepseek', choices=['deepseek'])
    return parser


def variant_definitions() -> list[dict[str, Any]]:
    return [{"variant_id": item.variant_id, "overlay_chars": len(item.overlay_text)} for item in FAMILY_VARIANTS]


def score_variant(*, parseable_json: bool, validation_ok: bool, chapter_id_ok: bool, counts: dict[str, int], event_importance_present: bool, relation_category_present: bool, missing_required_sections: list[str], response_text_chars: int) -> float:
    if not parseable_json or not validation_ok:
        return 0.0
    score = 0.0
    score += counts.get('characters', 0)
    score += counts.get('places', 0)
    score += counts.get('concepts', 0)
    score += counts.get('objects', 0) * 1.5
    score += counts.get('events', 0) * 1.5
    score += counts.get('relations', 0) * 2
    score += counts.get('unresolved_mentions', 0)
    if event_importance_present:
        score += 2
    if relation_category_present:
        score += 2
    if missing_required_sections:
        score -= 5
    if not chapter_id_ok:
        score -= 5
    if response_text_chars < 2500:
        score -= 3
    return round(max(score, 0.0), 2)


def run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_provider_calls:
        raise SystemExit('Refusing provider calls: --allow-provider-calls is required.')
    if not args.response_format_json:
        raise SystemExit('Refusing matrix: --response-format-json is required.')
    if not args.no_write_back:
        raise SystemExit('Refusing matrix: --no-write-back is required.')

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    if not models:
        raise SystemExit('No models provided.')

    plan: list[dict[str, Any]] = []
    for model in models:
        for variant in FAMILY_VARIANTS:
            plan.append({'chapter_id': 'ch_002', 'prompt_file': args.prompt_ch002, 'model': model, 'variant': variant})
        for variant in FAMILY_VARIANTS[:3]:
            plan.append({'chapter_id': 'ch_003', 'prompt_file': args.prompt_ch003, 'model': model, 'variant': variant})

    if args.max_provider_requests <= 0:
        raise SystemExit('Refusing matrix: --max-provider-requests must be > 0.')
    if len(plan) > args.max_provider_requests:
        raise SystemExit(f'Refusing matrix: planned calls {len(plan)} exceed --max-provider-requests={args.max_provider_requests}.')
    if len(plan) > 24:
        raise SystemExit(f'Refusing matrix: planned calls {len(plan)} exceed hard cap 24.')

    output_root = Path(args.output_root)
    overlays_dir = output_root / 'overlays'
    runs_dir = output_root / 'runs'
    overlays_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for item in plan:
        chapter_id = item['chapter_id']
        prompt_file = item['prompt_file']
        model = item['model']
        variant: FamilyVariant = item['variant']

        overlay_file = overlays_dir / f'{model}_{chapter_id}_{variant.variant_id}.md'
        overlay_file.write_text(variant.overlay_text, encoding='utf-8')

        parser = _REAL_DRYRUN.build_parser()
        dryrun_args = parser.parse_args([
            '--prompt-file', prompt_file,
            '--expected-chapter-id', chapter_id,
            '--provider', args.provider,
            '--model', model,
            '--output-root', str(runs_dir / model / chapter_id / variant.variant_id),
            '--allow-provider-calls',
            '--max-provider-requests', '1',
            '--max-output-tokens', str(args.max_output_tokens),
            '--response-format-json',
            '--provider-profile', 'none',
            '--prompt-overlay-file', str(overlay_file),
            '--no-write-back',
        ])

        try:
            dryrun_result = _REAL_DRYRUN.run_once(
                dryrun_args,
                provider_factory=_REAL_DRYRUN.get_text_provider,
                provider_config_error=_REAL_DRYRUN.get_text_provider_config_error,
            )
            results.append(_summarize_executed(dryrun_result=dryrun_result, model=model, chapter_id=chapter_id, variant_id=variant.variant_id))
        except Exception as exc:  # noqa: BLE001
            results.append({
                'model': model,
                'chapter_id': chapter_id,
                'variant_id': variant.variant_id,
                'status': 'failed_exception',
                'executed': True,
                'error': str(exc),
            })

    summary = {
        'provider': args.provider,
        'models_tested': models,
        'max_output_tokens': args.max_output_tokens,
        'planned_provider_calls': len(plan),
        'executed_provider_calls': len([r for r in results if r.get('executed')]),
        'results': results,
    }
    summary_path = output_root / 'family_matrix_summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def _summarize_executed(*, dryrun_result: Any, model: str, chapter_id: str, variant_id: str) -> dict[str, Any]:
    output_dir = Path(dryrun_result.output_dir)
    manifest = json.loads((output_dir / 'dryrun_manifest.json').read_text(encoding='utf-8'))
    validation = json.loads((output_dir / 'validation_report.json').read_text(encoding='utf-8'))

    payload = {}
    response_json_path = output_dir / 'provider_response.json'
    if response_json_path.exists():
        payload = json.loads(response_json_path.read_text(encoding='utf-8'))

    counts, missing_sections = _counts_and_missing_sections(payload)
    event_ok, relation_ok = _flags(payload)
    parseable = bool(validation.get('response_parseable_json'))
    validation_ok = bool(validation.get('ok'))
    response_text_chars = int(manifest.get('response_text_chars') or 0)
    actual_chapter_id = validation.get('details', {}).get('chapter_id')
    chapter_id_ok = (actual_chapter_id == chapter_id)

    score = score_variant(
        parseable_json=parseable,
        validation_ok=validation_ok,
        chapter_id_ok=chapter_id_ok,
        counts=counts,
        event_importance_present=event_ok,
        relation_category_present=relation_ok,
        missing_required_sections=missing_sections,
        response_text_chars=response_text_chars,
    )

    return {
        'model': model,
        'chapter_id': chapter_id,
        'variant_id': variant_id,
        'status': 'completed',
        'executed': True,
        'parseable_json': parseable,
        'validation_ok': validation_ok,
        'chapter_id_ok': chapter_id_ok,
        'response_text_chars': response_text_chars,
        'counts': counts,
        'missing_required_sections': missing_sections,
        'event_importance_present': event_ok,
        'relation_category_present': relation_ok,
        'score': score,
        'prompt_sha256': manifest.get('prompt_file_sha256'),
        'output_dir_reference': str(output_dir),
    }


def _chapter(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = payload.get('chapters') if isinstance(payload, dict) else None
    if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
        return chapters[0]
    return {}


def _counts_and_missing_sections(payload: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    chapter = _chapter(payload)
    counts: dict[str, int] = {}
    missing: list[str] = []
    for key in REQUIRED_SECTIONS:
        if key not in chapter:
            missing.append(key)
            counts[key] = 0
            continue
        value = chapter.get(key)
        counts[key] = len(value) if isinstance(value, list) else 0
    return counts, missing


def _flags(payload: dict[str, Any]) -> tuple[bool, bool]:
    chapter = _chapter(payload)
    events = chapter.get('events') if isinstance(chapter.get('events'), list) else []
    relations = chapter.get('relations') if isinstance(chapter.get('relations'), list) else []
    return (
        any(isinstance(item, dict) and item.get('event_importance') for item in events),
        any(isinstance(item, dict) and item.get('relation_category') for item in relations),
    )


def main() -> int:
    args = build_parser().parse_args()
    summary = run_matrix(args)
    print(json.dumps({'status': 'completed', 'summary_path': str(Path(args.output_root) / 'family_matrix_summary.json'), 'executed_provider_calls': summary.get('executed_provider_calls'), 'models_tested': summary.get('models_tested')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
