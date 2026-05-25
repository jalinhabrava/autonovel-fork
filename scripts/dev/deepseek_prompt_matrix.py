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
_SPEC = importlib.util.spec_from_file_location("real_provider_dryrun_for_matrix", _REAL_DRYRUN_PATH)
assert _SPEC and _SPEC.loader
_REAL_DRYRUN = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _REAL_DRYRUN
_SPEC.loader.exec_module(_REAL_DRYRUN)

DEFAULT_OUTPUT_ROOT = Path("/tmp/textifai_deepseek_strategy_matrix")
REQUIRED_SECTIONS = ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]


@dataclass(frozen=True)
class PromptVariant:
    variant_id: str
    overlay_text: str


SP067_VARIANTS: tuple[PromptVariant, ...] = (
    PromptVariant(
        variant_id="variant_a_dense_explicit",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Prioritize complete extraction over brevity.

For this chapter, do not stop after summary.
Extract all meaningful:
- characters and role-significant unnamed actors;
- places and subplaces;
- concepts and magic/system states;
- objects/tools/artifacts/catalysts/weapons/restraints/keys/event-triggering props;
- durable events;
- evidence-backed relations;
- unresolved but important mentions.

Keep each fact short.
Use review/local_candidate for uncertainty.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_b_dense_plus_check",
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
    PromptVariant(
        variant_id="variant_c_section_targets_json_safe",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Fill every schema section.

Coverage targets:
characters = named, POV, authority, family, role-significant actors.
places = locations/subplaces where action, status, or threat changes.
objects = tools, artifacts, catalysts, weapons, restraints, keys, event-triggering props.
events = durable changes in role, status, location, threat, magic/system, or decision.
relations = evidence-backed links between protagonist, authority, places, objects, events, concepts.
unresolved_mentions = important unknown actors, objects, concepts, or pronouns.

Keep facts concise.
Uncertain identity stays review/local_candidate.
No invented names.""",
    ),
    PromptVariant(
        variant_id="variant_d_schema_skeleton_plus_density",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

The JSON must contain all schema sections:
characters, places, concepts, objects, events, relations, unresolved_mentions.

Do not leave a section empty if the chapter contains evidence for it.

Prefer recall over compression.
Keep facts short.
Use review/local_candidate for uncertain identity.
Use unresolved_mentions for important unresolved references.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_e_objects_events_relations_boost",
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
    PromptVariant(
        variant_id="variant_f_two_stage_instruction",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Internally perform two steps:
1. Identify all relevant extraction candidates for every schema section.
2. Write the final JSON using those candidates.

Do not output step 1.
Output only the final JSON.

Prioritize coverage over brevity.
Keep facts concise.
Use review/local_candidate for uncertainty.
Do not invent names.""",
    ),
)


ROUND2_VARIANTS: tuple[PromptVariant, ...] = (
    PromptVariant(
        variant_id="variant_g_combined_best",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Prioritize complete extraction over brevity.
Do not stop after summary or final outcome.

Extract all meaningful characters, places, concepts, objects, events, relations, and unresolved mentions.

Pay special attention to:
- role-significant unnamed actors;
- subplaces where action, status, or threat changes;
- objects/tools/artifacts/catalysts/weapons/restraints/keys/event-triggering props;
- durable state-change events;
- evidence-backed relations involving protagonist, authority, places, objects, concepts, and events;
- important unresolved mentions.

Before final JSON, internally check whether any schema section is missing useful evidence.
If uncertain, use review/local_candidate or unresolved_mentions.
Do not output your checklist.
Keep facts concise.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_h_counts_targeted",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

This is not a summary task. It is structured extraction.

For a non-trivial narrative chapter, aim to include:
- multiple characters when multiple actors/roles are present;
- multiple events when the chapter has more than one state change;
- multiple relations when entities interact or depend on each other;
- all event-triggering objects/tools/artifacts;
- unresolved_mentions for important unclear references.

Do not invent items to satisfy counts.
Only include evidence-supported items.
Keep facts concise.
Keep uncertainty in review/local_candidate.""",
    ),
    PromptVariant(
        variant_id="variant_i_schema_section_completion",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Complete every schema section using evidence from the chapter.

For each section:
characters: named or role-significant actors.
places: locations and sublocations.
concepts: magic/system/status concepts.
objects: physical or magical tools, artifacts, catalysts, weapons, restraints, keys, props.
events: durable changes, decisions, threats, discoveries, movements, magic/system changes.
relations: evidence-backed links between extracted items.
unresolved_mentions: important unclear actors, objects, concepts, pronouns, or references.

Empty sections are allowed only when no evidence exists.
Concise facts.
No invented names.
Uncertainty stays review/local_candidate.""",
    ),
    PromptVariant(
        variant_id="variant_j_review_and_unresolved_boost",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

Prioritize useful extraction for author review.

Do not drop ambiguous but important references.
If an actor, object, concept, pronoun, relation, or identity is important but uncertain:
- include it in unresolved_mentions; or
- keep it as local_candidate/review with review_reason.

Also extract evidence-supported characters, places, concepts, objects, events, and relations.
Do not compress the chapter into summary only.
Keep facts concise.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_k_objects_events_relations_v2",
        overlay_text="""Return exactly one valid JSON object. Do not use markdown.

After identifying the summary, continue extracting structural data.

Focus on three high-value groups:
1. Objects: tools, artifacts, catalysts, weapons, restraints, keys, props that trigger, explain, block, enable, or symbolize events.
2. Events: every durable change in identity, role, status, place, threat, decision, or magic/system state.
3. Relations: evidence-backed links between people, places, objects, concepts, and events.

Also include characters, places, concepts, and unresolved_mentions when supported.
Use review/local_candidate for uncertainty.
Keep facts concise.
Do not invent names.""",
    ),
    PromptVariant(
        variant_id="variant_l_balanced_final_candidate",
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
)


VARIANT_SETS: dict[str, tuple[PromptVariant, ...]] = {
    "sp067": SP067_VARIANTS,
    "round2": ROUND2_VARIANTS,
}
VARIANTS = SP067_VARIANTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepSeek extraction matrix runner.")
    parser.add_argument("--prompt-ch002", required=True)
    parser.add_argument("--prompt-ch003", required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--max-provider-requests", type=int, default=0, help="Global max calls allowed.")
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--provider", default="deepseek", choices=["deepseek"])
    parser.add_argument("--flash-model", default="deepseek-v4-flash")
    parser.add_argument("--pro-model", default="deepseek-v4-pro")
    parser.add_argument("--attempt-pro", action="store_true")
    parser.add_argument("--variant-set", default="sp067", choices=sorted(VARIANT_SETS.keys()))
    return parser


def variant_definitions(variant_set: str = "sp067") -> list[dict[str, Any]]:
    variants = VARIANT_SETS[variant_set]
    return [{"variant_id": item.variant_id, "overlay_chars": len(item.overlay_text)} for item in variants]


def score_variant(
    *,
    parseable_json: bool,
    validation_ok: bool,
    counts: dict[str, int],
    event_importance_present: bool,
    relation_category_present: bool,
    missing_required_sections: list[str],
    response_text_chars: int,
) -> float:
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

    variants = VARIANT_SETS[args.variant_set]
    chapters = [
        {"chapter_id": "ch_002", "prompt_file": args.prompt_ch002},
        {"chapter_id": "ch_003", "prompt_file": args.prompt_ch003},
    ]

    plan: list[dict[str, Any]] = []
    for chapter in chapters:
        for variant in variants:
            plan.append(
                {
                    "chapter_id": chapter["chapter_id"],
                    "prompt_file": chapter["prompt_file"],
                    "model": args.flash_model,
                    "variant": variant,
                    "tier": "flash",
                }
            )

    if args.attempt_pro:
        pro_variants = [item for item in variants if item.variant_id in {"variant_a_dense_explicit", "variant_b_dense_plus_check"}]
        for chapter in chapters:
            for variant in pro_variants:
                plan.append(
                    {
                        "chapter_id": chapter["chapter_id"],
                        "prompt_file": chapter["prompt_file"],
                        "model": args.pro_model,
                        "variant": variant,
                        "tier": "pro",
                    }
                )

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
    pro_blocked = False
    pro_block_reason: str | None = None

    for item in plan:
        chapter_id = item["chapter_id"]
        prompt_file = item["prompt_file"]
        model = item["model"]
        variant: PromptVariant = item["variant"]
        tier = item["tier"]

        if tier == "pro" and pro_blocked:
            results.append(
                {
                    "model": model,
                    "tier": tier,
                    "chapter_id": chapter_id,
                    "variant_id": variant.variant_id,
                    "status": "skipped_pro_model_unavailable_or_failed",
                    "error": pro_block_reason,
                    "executed": False,
                }
            )
            continue

        overlay_file = overlays_dir / f"{model}_{chapter_id}_{variant.variant_id}.md"
        overlay_file.write_text(variant.overlay_text, encoding="utf-8")

        parser = _REAL_DRYRUN.build_parser()
        dryrun_args = parser.parse_args(
            [
                "--prompt-file",
                prompt_file,
                "--expected-chapter-id",
                chapter_id,
                "--provider",
                args.provider,
                "--model",
                model,
                "--output-root",
                str(runs_dir / model / chapter_id / variant.variant_id),
                "--allow-provider-calls",
                "--max-provider-requests",
                "1",
                "--max-output-tokens",
                str(args.max_output_tokens),
                "--response-format-json",
                "--provider-profile",
                "none",
                "--prompt-overlay-file",
                str(overlay_file),
                "--no-write-back",
            ]
        )

        try:
            dryrun_result = _REAL_DRYRUN.run_once(
                dryrun_args,
                provider_factory=_REAL_DRYRUN.get_text_provider,
                provider_config_error=_REAL_DRYRUN.get_text_provider_config_error,
            )
            results.append(
                _summarize_executed(
                    dryrun_result=dryrun_result,
                    model=model,
                    chapter_id=chapter_id,
                    tier=tier,
                    variant_id=variant.variant_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            results.append(
                {
                    "model": model,
                    "tier": tier,
                    "chapter_id": chapter_id,
                    "variant_id": variant.variant_id,
                    "status": "failed_exception",
                    "error": error_message,
                    "executed": True,
                }
            )
            if tier == "pro":
                pro_blocked = True
                pro_block_reason = error_message

    summary = {
        "provider": args.provider,
        "variant_set": args.variant_set,
        "models_attempted": sorted({item["model"] for item in plan}),
        "attempt_pro": bool(args.attempt_pro),
        "pro_block_reason": pro_block_reason,
        "max_output_tokens": args.max_output_tokens,
        "planned_provider_calls": len(plan),
        "executed_provider_calls": len([item for item in results if item.get("executed")]),
        "results": results,
    }
    summary_path = output_root / "strategy_matrix_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _summarize_executed(*, dryrun_result: Any, model: str, chapter_id: str, tier: str, variant_id: str) -> dict[str, Any]:
    output_dir = Path(dryrun_result.output_dir)
    manifest = json.loads((output_dir / "dryrun_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))

    payload = {}
    response_json_path = output_dir / "provider_response.json"
    if response_json_path.exists():
        payload = json.loads(response_json_path.read_text(encoding="utf-8"))

    counts, missing_sections = _counts_and_missing_sections(payload)
    event_importance_present, relation_category_present = _flags(payload)
    parseable = bool(validation.get("response_parseable_json"))
    validation_ok = bool(validation.get("ok"))
    response_text_chars = int(manifest.get("response_text_chars") or 0)

    score = score_variant(
        parseable_json=parseable,
        validation_ok=validation_ok,
        counts=counts,
        event_importance_present=event_importance_present,
        relation_category_present=relation_category_present,
        missing_required_sections=missing_sections,
        response_text_chars=response_text_chars,
    )

    return {
        "model": model,
        "tier": tier,
        "chapter_id": chapter_id,
        "variant_id": variant_id,
        "status": "completed",
        "executed": True,
        "parseable_json": parseable,
        "validation_ok": validation_ok,
        "response_text_chars": response_text_chars,
        "counts": counts,
        "missing_required_sections": missing_sections,
        "event_importance_present": event_importance_present,
        "relation_category_present": relation_category_present,
        "score": score,
        "prompt_sha256": manifest.get("prompt_file_sha256"),
        "output_dir_reference": str(output_dir),
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
                "summary_path": str(Path(args.output_root) / "strategy_matrix_summary.json"),
                "executed_provider_calls": summary.get("executed_provider_calls"),
                "models_attempted": summary.get("models_attempted"),
                "variant_set": summary.get("variant_set"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
