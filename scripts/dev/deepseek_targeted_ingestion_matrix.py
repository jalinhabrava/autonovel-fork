from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_REAL_DRYRUN_PATH = Path(__file__).with_name("real_provider_dryrun.py")
_SPEC = importlib.util.spec_from_file_location("real_provider_dryrun_for_targeted_matrix", _REAL_DRYRUN_PATH)
assert _SPEC and _SPEC.loader
_REAL_DRYRUN = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _REAL_DRYRUN
_SPEC.loader.exec_module(_REAL_DRYRUN)

from textifai.import_review.prompt_experiment_observability import (  # noqa: E402
    build_experiment_entry,
    classify_failure_mode,
    classify_variant_decision,
)

DEFAULT_OUTPUT_ROOT = Path("/tmp/textifai_deepseek_targeted_ingestion_matrix")
REQUIRED_SECTIONS = ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]


@dataclass(frozen=True)
class TargetedVariant:
    variant_id: str
    parent_variant_id: str
    hypothesis: str
    prompt_change_type: list[str]
    expected_effect: str
    risk: str
    chapter_focus: str
    overlay_text: str


TARGETED_VARIANTS: tuple[TargetedVariant, ...] = (
    TargetedVariant(
        variant_id="targeted_variant_1_object_event_manifest",
        parent_variant_id="family_variant_2_oer_focus",
        hypothesis="Manifest framing should recover objects/events while preserving JSON validity.",
        prompt_change_type=["json_reliability", "density_boost", "objects_events_relations_focus", "unresolved_mentions_focus"],
        expected_effect="Higher objects/events/relations on ch_002 without JSON regressions.",
        risk="May overfit structural lists and still miss unresolved mentions.",
        chapter_focus="ch_002_priority",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

This is structured ingestion, not summary.

First ensure the final JSON captures a complete evidence-backed inventory of:
- objects/tools/artifacts/catalysts/weapons/restraints/keys/props;
- durable events;
- evidence-backed relations;
- unresolved important mentions.

Objects must include items that trigger, enable, block, reveal, break, transform, or explain events.
Events must include decisions, discoveries, movements, status changes, threats, and magic/system changes.

Keep facts concise.
Use review/local_candidate for uncertainty.
Use unresolved_mentions instead of dropping unclear but important references.
Do not invent names.""",
    ),
    TargetedVariant(
        variant_id="targeted_variant_2_no_zero_sections",
        parent_variant_id="family_variant_1_broad_recall",
        hypothesis="Internal zero-section check should reduce thin outputs and empty critical sections.",
        prompt_change_type=["json_reliability", "section_completion", "internal_check", "density_boost"],
        expected_effect="Fewer zero critical sections with valid JSON.",
        risk="Checklist pressure may reintroduce invalid-json behavior.",
        chapter_focus="both",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Before final JSON, internally check every schema section:
characters, places, concepts, objects, events, relations, unresolved_mentions.

Do not leave objects, events, relations, or unresolved_mentions empty if there is evidence.
If a section remains empty, it must be because the chapter truly gives no usable evidence.

Prefer evidence-backed coverage over brevity.
Keep facts concise.
Keep uncertainty in review/local_candidate.
Do not invent names.
Do not output your checklist.""",
    ),
    TargetedVariant(
        variant_id="targeted_variant_3_ch002_gap_recovery",
        parent_variant_id="family_variant_4_ch002_gap_attack",
        hypothesis="Explicit gap recovery language should recover catalyst/object/authority/magic-state in ch_002.",
        prompt_change_type=["json_reliability", "objects_events_relations_focus", "unresolved_mentions_focus", "density_boost"],
        expected_effect="Better ch_002 objects/events/unresolved with acceptable JSON reliability.",
        risk="Narrative-specific framing may reduce generalization to other chapters.",
        chapter_focus="ch_002_priority",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

This chapter may involve authority pressure, magical failure/success, catalysts or tools, decisions, and escape/movement.

Do not compress those into the summary only.

Extract:
- catalysts/tools/objects and what happens to them;
- decisions and status changes as events;
- authority-character and character-object relations;
- magic/system state changes as concepts/events;
- unresolved but important references.

Also include characters, places, and concepts normally.
Keep facts concise.
Use review/local_candidate for uncertainty.
Do not invent names.""",
    ),
    TargetedVariant(
        variant_id="targeted_variant_4_pro_balanced_dense",
        parent_variant_id="family_variant_3_balanced_kb",
        hypothesis="Pro benefits from direct balanced-dense phrasing with less checklist load.",
        prompt_change_type=["json_reliability", "balanced_knowledge_base", "density_boost", "objects_events_relations_focus"],
        expected_effect="Better balanced coverage on Pro with stable JSON.",
        risk="May underperform on explicit unresolved extraction.",
        chapter_focus="pro_specialized",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Extract a balanced story knowledge-base record.

Prioritize:
- complete entity coverage;
- all event-triggering objects;
- all durable events;
- relation links between characters, places, concepts, objects, and events;
- unresolved important mentions.

Avoid over-summarizing.
Avoid empty sections when evidence exists.
Keep facts concise.
Use review/local_candidate for uncertainty.
Do not invent names.""",
    ),
    TargetedVariant(
        variant_id="targeted_variant_5_json_shape_anchor",
        parent_variant_id="family_variant_2_oer_focus",
        hypothesis="Shape anchor improves JSON reliability under dense instructions.",
        prompt_change_type=["json_reliability", "schema_skeleton", "density_boost", "objects_events_relations_focus"],
        expected_effect="Higher parseability without losing OER-focused extraction.",
        risk="Schema anchor may compress content if model over-prioritizes structure.",
        chapter_focus="both",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown or commentary.

The object must keep the existing schema shape:
work
chapters[0]
chapters[0].characters
chapters[0].places
chapters[0].concepts
chapters[0].objects
chapters[0].events
chapters[0].relations
chapters[0].unresolved_mentions

Within that shape, prefer complete evidence-backed extraction over brevity.
Focus on objects, events, relations, and unresolved mentions.
Keep uncertainty in review/local_candidate.
Do not invent names.""",
    ),
)

FLASH_CH002_VARIANTS = {
    "targeted_variant_1_object_event_manifest",
    "targeted_variant_2_no_zero_sections",
    "targeted_variant_3_ch002_gap_recovery",
    "targeted_variant_5_json_shape_anchor",
}
FLASH_CH003_VARIANTS = {
    "targeted_variant_1_object_event_manifest",
    "targeted_variant_2_no_zero_sections",
    "targeted_variant_5_json_shape_anchor",
}
PRO_CH002_VARIANTS = {
    "targeted_variant_1_object_event_manifest",
    "targeted_variant_3_ch002_gap_recovery",
    "targeted_variant_4_pro_balanced_dense",
    "targeted_variant_5_json_shape_anchor",
}
PRO_CH003_VARIANTS = {
    "targeted_variant_1_object_event_manifest",
    "targeted_variant_4_pro_balanced_dense",
    "targeted_variant_5_json_shape_anchor",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepSeek targeted ingestion matrix runner.")
    parser.add_argument("--prompt-ch002", required=True)
    parser.add_argument("--prompt-ch003", required=True)
    parser.add_argument("--models", default="deepseek-v4-flash,deepseek-v4-pro")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--max-provider-requests", type=int, default=0)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--provider", default="deepseek", choices=["deepseek"])
    parser.add_argument("--per-call-timeout-seconds", type=int, default=300)
    return parser


def score_variant(*, parseable_json: bool, validation_ok: bool, chapter_id_ok: bool, counts: dict[str, int], event_importance_present: bool, relation_category_present: bool, missing_required_sections: list[str], response_text_chars: int) -> float:
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
        raise SystemExit("Refusing provider calls: --allow-provider-calls is required.")
    if not args.response_format_json:
        raise SystemExit("Refusing matrix: --response-format-json is required.")
    if not args.no_write_back:
        raise SystemExit("Refusing matrix: --no-write-back is required.")

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        raise SystemExit("No models provided.")

    plan: list[dict[str, Any]] = []
    variants_by_id = {item.variant_id: item for item in TARGETED_VARIANTS}

    for model in models:
        lower = model.casefold()
        if "flash" in lower:
            plan.extend(_build_plan_for_model(model, "ch_002", args.prompt_ch002, FLASH_CH002_VARIANTS, variants_by_id))
            plan.extend(_build_plan_for_model(model, "ch_003", args.prompt_ch003, FLASH_CH003_VARIANTS, variants_by_id))
        elif "pro" in lower:
            plan.extend(_build_plan_for_model(model, "ch_002", args.prompt_ch002, PRO_CH002_VARIANTS, variants_by_id))
            plan.extend(_build_plan_for_model(model, "ch_003", args.prompt_ch003, PRO_CH003_VARIANTS, variants_by_id))

    if args.max_provider_requests <= 0:
        raise SystemExit("Refusing matrix: --max-provider-requests must be > 0.")
    if len(plan) > args.max_provider_requests:
        raise SystemExit(f"Refusing matrix: planned calls {len(plan)} exceed --max-provider-requests={args.max_provider_requests}.")
    if len(plan) > 16:
        raise SystemExit(f"Refusing matrix: planned calls {len(plan)} exceed hard cap 16.")

    output_root = Path(args.output_root)
    overlays_dir = output_root / "overlays"
    runs_dir = output_root / "runs"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for item in plan:
        chapter_id = item["chapter_id"]
        prompt_file = item["prompt_file"]
        model = item["model"]
        variant: TargetedVariant = item["variant"]

        overlay_file = overlays_dir / f"{model}_{chapter_id}_{variant.variant_id}.md"
        overlay_file.write_text(variant.overlay_text, encoding="utf-8")
        run_output_root = runs_dir / model / chapter_id / variant.variant_id
        run_output_root.mkdir(parents=True, exist_ok=True)

        dryrun_args = _REAL_DRYRUN.build_parser().parse_args(
            [
                "--prompt-file",
                prompt_file,
                "--provider",
                args.provider,
                "--model",
                model,
                "--output-root",
                str(run_output_root),
                "--allow-provider-calls",
                "--max-provider-requests",
                "1",
                "--max-output-tokens",
                str(args.max_output_tokens),
                "--response-format-json",
                "--expected-chapter-id",
                chapter_id,
                "--provider-profile",
                "none",
                "--prompt-overlay-file",
                str(overlay_file),
                "--no-write-back",
            ]
        )

        try:
            dryrun_result = _run_once_with_timeout(
                dryrun_args=dryrun_args,
                timeout_seconds=args.per_call_timeout_seconds,
            )
            result = _summarize_executed(
                dryrun_result=dryrun_result,
                model=model,
                chapter_id=chapter_id,
                variant=variant,
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            error_result = {
                "model": model,
                "chapter_id": chapter_id,
                "variant_id": variant.variant_id,
                "status": "failed_exception",
                "executed": True,
                "error": str(exc),
                "parseable_json": False,
                "validation_ok": False,
                "counts": {key: 0 for key in REQUIRED_SECTIONS},
                "missing_required_sections": list(REQUIRED_SECTIONS),
                "event_importance_present": False,
                "relation_category_present": False,
                "score": 0.0,
                "objects_events_relations_score": 0.0,
                "unresolved_score": 0.0,
                "zero_critical_sections_count": 4,
                "json_reliability": 0.0,
                "failure_mode": "provider_error",
                "decision_candidate": "discard",
                "variant_metadata": _variant_metadata(variant),
            }
            error_result["observability_entry"] = build_experiment_entry(
                experiment_id=f"sp072-{model}-{chapter_id}-{variant.variant_id}",
                provider_family="deepseek",
                model=model,
                task="bootstrap_chapter_extraction",
                chapter_id=chapter_id,
                variant_id=variant.variant_id,
                parent_variant_id=variant.parent_variant_id,
                variant_goal=variant.chapter_focus,
                hypothesis=variant.hypothesis,
                prompt_change_type=variant.prompt_change_type,
                expected_effect=variant.expected_effect,
                risk=variant.risk,
                result_summary=_observability_result_summary(error_result),
                decision=error_result["decision_candidate"],
            )
            results.append(error_result)

    summary = {
        "provider": args.provider,
        "models_tested": models,
        "max_output_tokens": args.max_output_tokens,
        "planned_provider_calls": len(plan),
        "executed_provider_calls": len([r for r in results if r.get("executed")]),
        "variants_executed": sorted({item["variant_id"] for item in results}),
        "results": results,
    }
    summary_path = output_root / "targeted_ingestion_matrix_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _build_plan_for_model(model: str, chapter_id: str, prompt_file: str, variant_ids: set[str], variants_by_id: dict[str, TargetedVariant]) -> list[dict[str, Any]]:
    ordered = [item for item in TARGETED_VARIANTS if item.variant_id in variant_ids]
    return [{"model": model, "chapter_id": chapter_id, "prompt_file": prompt_file, "variant": item} for item in ordered]


def _run_once_with_timeout(*, dryrun_args: argparse.Namespace, timeout_seconds: int) -> Any:
    if timeout_seconds <= 0:
        return _REAL_DRYRUN.run_once(
            dryrun_args,
            provider_factory=_REAL_DRYRUN.get_text_provider,
            provider_config_error=_REAL_DRYRUN.get_text_provider_config_error,
        )

    def _handle_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"provider call timeout after {timeout_seconds}s")

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(timeout_seconds)
    try:
        return _REAL_DRYRUN.run_once(
            dryrun_args,
            provider_factory=_REAL_DRYRUN.get_text_provider,
            provider_config_error=_REAL_DRYRUN.get_text_provider_config_error,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _summarize_executed(*, dryrun_result: Any, model: str, chapter_id: str, variant: TargetedVariant) -> dict[str, Any]:
    output_dir = Path(dryrun_result.output_dir)
    manifest = json.loads((output_dir / "dryrun_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))

    payload: dict[str, Any] = {}
    response_json_path = output_dir / "provider_response.json"
    if response_json_path.exists():
        payload = json.loads(response_json_path.read_text(encoding="utf-8"))

    counts, missing_sections = _counts_and_missing_sections(payload)
    event_ok, relation_ok = _flags(payload)
    parseable = bool(validation.get("response_parseable_json"))
    validation_ok = bool(validation.get("ok"))
    response_text_chars = int(manifest.get("response_text_chars") or 0)
    actual_chapter_id = validation.get("details", {}).get("chapter_id")
    chapter_id_ok = actual_chapter_id == chapter_id

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

    oer_score = round(counts.get("objects", 0) * 1.5 + counts.get("events", 0) * 1.5 + counts.get("relations", 0) * 2, 2)
    unresolved_score = float(counts.get("unresolved_mentions", 0))
    zero_critical_sections_count = sum(1 for key in ("objects", "events", "relations", "unresolved_mentions") if counts.get(key, 0) == 0)
    json_reliability = 1.0 if (parseable and validation_ok) else 0.0

    summary = {
        "model": model,
        "chapter_id": chapter_id,
        "variant_id": variant.variant_id,
        "status": "completed",
        "executed": True,
        "parseable_json": parseable,
        "validation_ok": validation_ok,
        "chapter_id_ok": chapter_id_ok,
        "response_text_chars": response_text_chars,
        "counts": counts,
        "missing_required_sections": missing_sections,
        "event_importance_present": event_ok,
        "relation_category_present": relation_ok,
        "score": score,
        "objects_events_relations_score": oer_score,
        "unresolved_score": unresolved_score,
        "zero_critical_sections_count": zero_critical_sections_count,
        "json_reliability": json_reliability,
        "prompt_sha256": manifest.get("prompt_file_sha256"),
        "output_dir_reference": str(output_dir),
        "variant_metadata": _variant_metadata(variant),
    }
    summary["failure_mode"] = classify_failure_mode(_observability_result_summary(summary))
    summary["decision_candidate"] = classify_variant_decision(
        _observability_result_summary(summary),
        keep_for_mutation=(parseable and validation_ok and score >= 20 and score < 25),
    )
    summary["observability_entry"] = build_experiment_entry(
        experiment_id=f"sp072-{model}-{chapter_id}-{variant.variant_id}",
        provider_family="deepseek",
        model=model,
        task="bootstrap_chapter_extraction",
        chapter_id=chapter_id,
        variant_id=variant.variant_id,
        parent_variant_id=variant.parent_variant_id,
        variant_goal=variant.chapter_focus,
        hypothesis=variant.hypothesis,
        prompt_change_type=variant.prompt_change_type,
        expected_effect=variant.expected_effect,
        risk=variant.risk,
        result_summary=_observability_result_summary(summary),
        decision=summary["decision_candidate"],
    )
    return summary


def _variant_metadata(variant: TargetedVariant) -> dict[str, Any]:
    return {
        "parent_variant_id": variant.parent_variant_id,
        "hypothesis": variant.hypothesis,
        "prompt_change_type": list(variant.prompt_change_type),
        "expected_effect": variant.expected_effect,
        "risk": variant.risk,
        "chapter_focus": variant.chapter_focus,
        "overlay_chars": len(variant.overlay_text),
    }


def _observability_result_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "parseable_json": bool(item.get("parseable_json")),
        "validation_ok": bool(item.get("validation_ok")),
        "score": item.get("score"),
        "counts": item.get("counts", {}),
        "missing_required_sections": item.get("missing_required_sections", []),
        "chapter_id_ok": bool(item.get("chapter_id_ok", True)),
        "response_text_chars": int(item.get("response_text_chars", 0) or 0),
        "event_importance_present": bool(item.get("event_importance_present")),
        "relation_category_present": bool(item.get("relation_category_present")),
        "failure_hint": str(item.get("error", "")),
        "ambiguous_context": item.get("chapter_id") == "ch_002",
    }


def _chapter(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
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
    events = chapter.get("events") if isinstance(chapter.get("events"), list) else []
    relations = chapter.get("relations") if isinstance(chapter.get("relations"), list) else []
    return (
        any(isinstance(item, dict) and item.get("event_importance") for item in events),
        any(isinstance(item, dict) and item.get("relation_category") for item in relations),
    )


def main() -> int:
    args = build_parser().parse_args()
    summary = run_matrix(args)
    print(
        json.dumps(
            {
                "status": "completed",
                "summary_path": str(Path(args.output_root) / "targeted_ingestion_matrix_summary.json"),
                "executed_provider_calls": summary.get("executed_provider_calls"),
                "models_tested": summary.get("models_tested"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
