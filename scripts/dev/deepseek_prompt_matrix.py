from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_REAL_DRYRUN_PATH = Path(__file__).with_name("real_provider_dryrun.py")
_SPEC = importlib.util.spec_from_file_location("real_provider_dryrun_for_matrix", _REAL_DRYRUN_PATH)
assert _SPEC and _SPEC.loader
_REAL_DRYRUN = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _REAL_DRYRUN
_SPEC.loader.exec_module(_REAL_DRYRUN)

DEFAULT_OUTPUT_ROOT = Path("/tmp/textifai_deepseek_prompt_matrix_ch002")
BASELINE_FIXTURE_ROOT = Path("tests/fixtures/textifai/real_provider_dryrun/expected")

@dataclass(frozen=True)
class PromptVariant:
    variant_id: str
    label: str
    overlay_text: str | None
    provider_profile: str
    execute: bool
    reference_fixture: str | None = None

VARIANTS: tuple[PromptVariant, ...] = (
    PromptVariant(
        variant_id="variant_01_generic_reference",
        label="generic_reference_sp060",
        overlay_text=None,
        provider_profile="none",
        execute=False,
        reference_fixture="deepseek_ch002_runtime_summary_after_sp059.json",
    ),
    PromptVariant(
        variant_id="variant_02_compact_json_first",
        label="compact_json_first_sp065",
        overlay_text=None,
        provider_profile="auto",
        execute=False,
        reference_fixture="deepseek_ch002_compact_profile_runtime_summary_after_sp064.json",
    ),
    PromptVariant(
        variant_id="variant_03_dense_explicit",
        label="dense_explicit",
        provider_profile="none",
        execute=True,
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Prioritize complete extraction over brevity.

For this chapter, do not stop after summary.
Extract all meaningful:
- characters and role-significant unnamed actors;
- places and subplaces;
- concepts and magic/system states;
- objects/tools/artifacts/catalysts/weapons;
- durable events;
- evidence-backed relations;
- unresolved but important mentions.

Keep each fact short.
Use review/local_candidate for uncertainty.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_04_section_targets",
        label="section_targets",
        provider_profile="none",
        execute=True,
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Fill every schema section.

For a non-trivial narrative chapter, prefer recall over compression:
- characters: include named, POV, authority, family, and role-significant actors.
- places: include relevant places/subplaces where action or status changes occur.
- objects: include tools, artifacts, catalysts, weapons, restraints, keys, and event-triggering props.
- events: include all durable state changes, not only the final outcome.
- relations: include protagonist-authority, protagonist-place, protagonist-object, object-event, and magic/system relations when supported.
- unresolved_mentions: include important unknown actors, objects, concepts, or pronouns.

Concise facts only.
Uncertain identity stays review/local_candidate.
No invented names.""",
    ),
    PromptVariant(
        variant_id="variant_05_internal_coverage_check",
        label="internal_coverage_check",
        provider_profile="none",
        execute=True,
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Before writing the final JSON, internally check whether you omitted:
characters, places, concepts, objects, events, relations, unresolved_mentions.

If a relevant item is supported by evidence, include it.
If uncertain, include it with needs_review/review_reason or unresolved_mentions.
Do not output your checklist.
Output only the final JSON object.""",
    ),
    PromptVariant(
        variant_id="variant_06_json_skeleton_reinforcement",
        label="json_skeleton_reinforcement",
        provider_profile="none",
        execute=True,
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

The JSON must contain:
work
chapters[0].characters
chapters[0].places
chapters[0].concepts
chapters[0].objects
chapters[0].events
chapters[0].relations
chapters[0].unresolved_mentions

Do not leave a section empty if the chapter contains evidence for it.
Use short facts, but preserve coverage.
Do not invent names.
Keep uncertain identities in review/local_candidate.""",
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run guarded DeepSeek V4 Flash prompt overlay matrix for ch_002.")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--max-provider-requests", type=int, default=0)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--provider", default="deepseek", choices=["deepseek"])
    parser.add_argument("--model", default="deepseek-v4-flash")
    return parser


def variant_definitions() -> list[dict[str, Any]]:
    return [
        {
            "variant_id": item.variant_id,
            "label": item.label,
            "execute": item.execute,
            "provider_profile": item.provider_profile,
            "reference_fixture": item.reference_fixture,
            "overlay_chars": len(item.overlay_text or ""),
        }
        for item in VARIANTS
    ]


def score_variant(*, parseable_json: bool, validation_ok: bool, counts: dict[str, int], event_importance_present: bool, relation_category_present: bool) -> float:
    if not parseable_json or not validation_ok:
        return 0.0
    score = 0.0
    score += counts.get("characters", 0)
    score += counts.get("places", 0)
    score += counts.get("concepts", 0)
    score += counts.get("objects", 0) * 1.5
    score += counts.get("events", 0) * 1.5
    score += counts.get("relations", 0) * 2
    score += counts.get("unresolved_mentions", 0)
    if not event_importance_present:
        score -= 2
    if not relation_category_present:
        score -= 2
    return max(score, 0.0)


def run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_provider_calls:
        raise SystemExit("Refusing provider calls: --allow-provider-calls is required.")
    executed_variants = [item for item in VARIANTS if item.execute]
    if args.max_provider_requests != len(executed_variants):
        raise SystemExit(f"Refusing matrix: --max-provider-requests must equal {len(executed_variants)} for executable variants.")
    if not args.response_format_json:
        raise SystemExit("Refusing matrix: --response-format-json is required.")
    if not args.no_write_back:
        raise SystemExit("Refusing matrix: --no-write-back is required.")

    output_root = Path(args.output_root)
    overlays_dir = output_root / "overlays"
    runs_dir = output_root / "runs"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for variant in VARIANTS:
        if not variant.execute:
            reference = _load_reference_summary(variant.reference_fixture) if variant.reference_fixture else {}
            results.append(_summarize_reference_variant(variant, reference))
            continue

        overlay_file = overlays_dir / f"{variant.variant_id}.md"
        overlay_file.write_text(variant.overlay_text or "", encoding="utf-8")
        parser = _REAL_DRYRUN.build_parser()
        dryrun_args = parser.parse_args(
            [
                "--prompt-file",
                args.prompt_file,
                "--provider",
                args.provider,
                "--model",
                args.model,
                "--output-root",
                str(runs_dir / variant.variant_id),
                "--allow-provider-calls",
                "--max-provider-requests",
                "1",
                "--max-output-tokens",
                str(args.max_output_tokens),
                "--response-format-json",
                "--provider-profile",
                variant.provider_profile,
                "--prompt-overlay-file",
                str(overlay_file),
                "--no-write-back",
            ]
        )
        result = _REAL_DRYRUN.run_once(
            dryrun_args,
            provider_factory=_REAL_DRYRUN.get_text_provider,
            provider_config_error=_REAL_DRYRUN.get_text_provider_config_error,
        )
        results.append(_summarize_executed_variant(variant, result))

    summary = {
        "provider": args.provider,
        "model": args.model,
        "prompt_file_sha256": _read_manifest(results).get("prompt_file_sha256"),
        "max_output_tokens": args.max_output_tokens,
        "variants": results,
        "executed_provider_calls": len(executed_variants),
        "best_variant": _best_variant(results),
    }
    summary_path = output_root / "matrix_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _load_reference_summary(name: str | None) -> dict[str, Any]:
    if not name:
        return {}
    path = BASELINE_FIXTURE_ROOT / name
    if not path.exists():
        return {"missing_reference_fixture": name}
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_reference_variant(variant: PromptVariant, reference: dict[str, Any]) -> dict[str, Any]:
    counts = reference.get("counts")
    if not isinstance(counts, dict):
        counts = (
            reference.get("coverage_comparison", {}).get("runtime_counts")
            if isinstance(reference.get("coverage_comparison"), dict)
            else {}
        )
    parseable = bool(
        reference.get("response_parseable_json", reference.get("schema_validity", {}).get("runtime_json_parseable", False))
    )
    validation_ok = bool(
        reference.get("validation_ok", reference.get("schema_validity", {}).get("runtime_top_level_shape_ok", False))
    )
    event_flag = bool(reference.get("event_importance_present", False))
    rel_flag = bool(reference.get("relation_category_present", False))
    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "source": "reference_fixture",
        "executed": False,
        "reference_fixture": variant.reference_fixture,
        "provider_profile": variant.provider_profile,
        "parseable_json": parseable,
        "validation_ok": validation_ok,
        "chapter_id": reference.get("chapter_id"),
        "response_text_chars": reference.get("response_text_chars"),
        "counts": counts,
        "event_importance_present": event_flag,
        "relation_category_present": rel_flag,
        "score": score_variant(parseable_json=parseable, validation_ok=validation_ok, counts=counts, event_importance_present=event_flag, relation_category_present=rel_flag),
        "output_dir_reference": reference.get("output_dir_reference"),
    }


def _summarize_executed_variant(variant: PromptVariant, result: Any) -> dict[str, Any]:
    output_dir = Path(result.output_dir)
    manifest = json.loads((output_dir / "dryrun_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))
    payload = {}
    response_path = output_dir / "provider_response.json"
    if response_path.exists():
        payload = json.loads(response_path.read_text(encoding="utf-8"))
    counts = _counts(payload)
    event_flag, rel_flag = _flags(payload)
    parseable = bool(validation.get("response_parseable_json"))
    validation_ok = bool(validation.get("ok"))
    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "source": "executed_runtime",
        "executed": True,
        "provider_profile": variant.provider_profile,
        "prompt_overlay_applied": bool(manifest.get("prompt_overlay_applied")),
        "parseable_json": parseable,
        "validation_ok": validation_ok,
        "chapter_id": validation.get("details", {}).get("chapter_id"),
        "response_text_chars": manifest.get("response_text_chars"),
        "counts": counts,
        "event_importance_present": event_flag,
        "relation_category_present": rel_flag,
        "score": score_variant(parseable_json=parseable, validation_ok=validation_ok, counts=counts, event_importance_present=event_flag, relation_category_present=rel_flag),
        "output_dir_reference": str(output_dir),
    }


def _counts(payload: dict[str, Any]) -> dict[str, int]:
    chapter = _chapter(payload)
    return {key: len(chapter.get(key) or []) if isinstance(chapter.get(key), list) else 0 for key in ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]}


def _flags(payload: dict[str, Any]) -> tuple[bool, bool]:
    chapter = _chapter(payload)
    events = chapter.get("events") if isinstance(chapter.get("events"), list) else []
    relations = chapter.get("relations") if isinstance(chapter.get("relations"), list) else []
    return (
        any(isinstance(item, dict) and item.get("event_importance") for item in events),
        any(isinstance(item, dict) and item.get("relation_category") for item in relations),
    )


def _chapter(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
        return chapters[0]
    return {}


def _best_variant(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [item for item in results if item.get("parseable_json") and item.get("validation_ok")]
    if not valid:
        return None
    best = max(valid, key=lambda item: item.get("score", 0))
    return {"variant_id": best["variant_id"], "label": best["label"], "score": best["score"]}


def _read_manifest(results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in results:
        if item.get("executed") and item.get("output_dir_reference"):
            path = Path(item["output_dir_reference"]) / "dryrun_manifest.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    args = build_parser().parse_args()
    summary = run_matrix(args)
    print(json.dumps({"status": "completed", "summary_path": str(Path(args.output_root) / "matrix_summary.json"), "best_variant": summary.get("best_variant")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
