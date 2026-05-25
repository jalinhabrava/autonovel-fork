from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.batch_planner import StructuredSourceChunk, split_structured_chapter_into_chunks
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.deepseek_family_profiles import (
    build_finish_reason_length_strategy,
    build_patch_based_continuation_contract,
    build_pro_compact_reduction_policy,
    build_response_control_runtime_policy,
    build_continuation_repair_contract,
    build_deepseek_budget_bridge,
    build_response_control_contract,
    build_thin_output_warnings,
    get_deepseek_family_profile,
)
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.prompt_experiment_observability import classify_failure_mode
from textifai.import_review.provider_prompt_profiles import apply_provider_prompt_profile, inject_compact_reduction_control, inject_output_budget_control
from textifai.import_review.structured_bootstrap_v1 import (
    CHAPTER_PARTIAL_EXTRACTION_PROMPT,
    CHAPTER_REDUCTION_PROMPT,
    _estimate_token_count,
    _extract_title_entity_hints,
    _extract_title_parse_signals,
)
from textifai.import_review.token_budget import (
    TokenPlanningRequest,
    build_token_budget_from_planning_request,
    resolve_effective_output_budget,
)

TASK = "bootstrap_chapter_extraction"
EXPECTED_ROOT = Path("tests/fixtures/textifai/real_provider_dryrun/expected")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Real DeepSeek E2E dry-run with private decision packet.")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--chapter-ids", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--max-provider-requests", type=int, default=24)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--report-prefix", default="real_deepseek_e2e")
    parser.add_argument("--report-suffix", default="after_sp074")
    parser.add_argument("--include-extra-chapter-longest", action="store_true")
    parser.add_argument("--extra-chapter-scan-limit", type=int, default=6)
    parser.add_argument("--continuation-reserve-per-run", type=int, default=1)
    parser.add_argument("--pro-compact-reduction-mode", action="store_true")
    parser.add_argument("--patch-continuation-mode", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.no_write_back:
        raise SystemExit("--no-write-back is required")

    source_path = Path(args.source_file)
    source_text = source_path.read_text(encoding="utf-8", errors="replace")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    packet_root = Path(args.output_root) / timestamp
    packet_root.mkdir(parents=True, exist_ok=True)
    progress_path = packet_root / "progress_log.jsonl"

    required_chapters = [item.strip() for item in args.chapter_ids.split(",") if item.strip()]
    models = [item.strip() for item in args.models.split(",") if item.strip()]

    chapters = _detect_target_chapters(
        source_path=source_path,
        source_text=source_text,
        chapter_ids=required_chapters,
        include_extra_longest=args.include_extra_chapter_longest,
        scan_limit=args.extra_chapter_scan_limit,
    )

    plan = _build_execution_plan(
        source_path=source_path,
        source_text=source_text,
        chapters=chapters,
        models=models,
        packet_root=packet_root,
        cli_max_output_tokens=args.max_output_tokens,
        continuation_reserve_per_run=max(0, int(args.continuation_reserve_per_run)),
        pro_compact_reduction_mode=bool(args.pro_compact_reduction_mode),
        patch_continuation_mode=bool(args.patch_continuation_mode),
        provider_call_cap=int(args.max_provider_requests),
    )

    names = _report_names(prefix=args.report_prefix, suffix=args.report_suffix)
    _write_expected(names["execution_plan"], plan["public_plan"])
    _write_private(packet_root / "execution_plan_private.md", json.dumps(plan["public_plan"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "chunk_plan_private.md", _private_chunk_plan(plan))

    if plan["public_plan"]["planned_provider_call_count"] > args.max_provider_requests:
        _write_blocked_reports(names, plan, reason="planned_provider_call_count_exceeds_cap")
        return 2
    if plan["public_plan"]["planned_provider_call_count_with_continuation_reserve"] > args.max_provider_requests:
        _write_blocked_reports(names, plan, reason="continuation_reserve_exceeds_cap")
        return 2
    if args.plan_only:
        _write_blocked_reports(names, plan, reason="plan_only")
        return 0
    if not args.allow_provider_calls:
        _write_blocked_reports(names, plan, reason="missing_allow_provider_calls")
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        _write_blocked_reports(names, plan, reason="missing_deepseek_api_key")
        return 2
    config_error = get_text_provider_config_error(task_name=TASK, provider_name="deepseek")
    if config_error is not None:
        _write_blocked_reports(names, plan, reason=f"provider_config_error:{config_error}")
        return 2

    provider = get_text_provider(provider_name="deepseek")
    results: list[dict[str, Any]] = []
    total = plan["public_plan"]["planned_provider_call_count"]
    call_index = 0
    for run in plan["runs"]:
        run_result, used_calls = _execute_run(
            provider=provider,
            run=run,
            packet_root=packet_root,
            progress_path=progress_path,
            call_index_start=call_index,
            total_calls=total,
            max_provider_requests=args.max_provider_requests,
            response_format_json=args.response_format_json,
            names=names,
        )
        call_index += used_calls
        results.append(run_result)

    reports = _build_public_reports(plan=plan, results=results, packet_root=packet_root)
    for key, payload in reports.items():
        _write_expected(names[key], payload)
    _write_private_matrix_files(packet_root=packet_root, plan=plan, results=results, reports=reports)
    return 0


def _report_names(*, prefix: str, suffix: str) -> dict[str, str]:
    return {
        "execution_plan": f"{prefix}_execution_plan_{suffix}.json",
        "summary": f"{prefix}_summary_{suffix}.json",
        "chunk_results": f"{prefix}_chunk_results_{suffix}.json",
        "reduction_summary": f"{prefix}_reduction_summary_{suffix}.json",
        "decision": f"{prefix}_decision_{suffix}.json",
        "budget_report": f"{prefix}_budget_report_{suffix}.json",
        "source_ref_audit": f"{prefix}_source_ref_audit_{suffix}.json",
        "truncation_audit": f"{prefix}_truncation_continuation_audit_{suffix}.json",
    }


def _detect_target_chapters(
    *,
    source_path: Path,
    source_text: str,
    chapter_ids: list[str],
    include_extra_longest: bool,
    scan_limit: int,
) -> list[dict[str, Any]]:
    record = SourceDocumentRecord(
        source_id=f"source_{hashlib.sha256(str(source_path).encode()).hexdigest()[:10]}",
        path=str(source_path),
        relative_path=source_path.name,
        filename=source_path.name,
        extension=source_path.suffix.lstrip("."),
        size_bytes=len(source_text.encode("utf-8", errors="replace")),
        checksum=hashlib.sha256(source_text.encode("utf-8", errors="replace")).hexdigest(),
        dominant_language="ja",
        detected_languages=["ja"],
        line_count=len(source_text.splitlines()),
        extracted_char_count=len(source_text),
        extracted_word_count=len(source_text.split()),
        extracted_page_count=0,
    )
    detected = detect_story_chapters(record, source_text)
    wanted = set(chapter_ids)
    out: list[dict[str, Any]] = []
    for index, chapter in enumerate(detected, start=1):
        chapter_id = f"ch_{index:03d}"
        if chapter_id in wanted:
            out.append({"chapter_id": chapter_id, "sequence_index": index, "detected": chapter, "source_id": record.source_id})

    missing = sorted(wanted - {item["chapter_id"] for item in out})
    if missing:
        raise SystemExit(f"missing target chapters: {missing}")

    if include_extra_longest:
        selected = {item["chapter_id"] for item in out}
        candidates = []
        for index, chapter in enumerate(detected[: max(1, scan_limit)], start=1):
            chapter_id = f"ch_{index:03d}"
            if chapter_id in selected:
                continue
            candidates.append((len(chapter.text), chapter_id, index, chapter))
        if candidates:
            _chars, chapter_id, index, chapter = sorted(candidates, reverse=True)[0]
            out.append({"chapter_id": chapter_id, "sequence_index": index, "detected": chapter, "source_id": record.source_id, "selected_as_extra_longest": True})
    out.sort(key=lambda item: item["sequence_index"])
    return out


def _build_execution_plan(
    *,
    source_path: Path,
    source_text: str,
    chapters: list[dict[str, Any]],
    models: list[str],
    packet_root: Path,
    cli_max_output_tokens: int | None,
    continuation_reserve_per_run: int,
    pro_compact_reduction_mode: bool = False,
    patch_continuation_mode: bool = False,
    provider_call_cap: int = 24,
) -> dict[str, Any]:
    source_hash = hashlib.sha256(source_text.encode("utf-8", errors="replace")).hexdigest()
    runs: list[dict[str, Any]] = []
    public_runs: list[dict[str, Any]] = []
    call_count = 0
    continuation_reserve = 0
    for chapter in chapters:
        detected = chapter["detected"]
        for model in models:
            profile = get_deepseek_family_profile(model)
            if profile is None:
                continue
            caps = get_model_capabilities(model)
            effective_budget = resolve_effective_output_budget(
                provider="deepseek",
                model=model,
                task=TASK,
                capabilities=caps,
                provider_profile_id=profile.profile_id,
                profile_default_max_output_tokens=profile.default_max_output_tokens,
                cli_override_max_output_tokens=cli_max_output_tokens,
                provider_default_max_output_tokens=None,
            )
            planning = TokenPlanningRequest(
                provider="deepseek",
                model=model,
                task=TASK,
                provider_profile_id=profile.profile_id,
                max_output_tokens=effective_budget.effective_max_output_tokens,
                prompt_overhead_tokens=5000,
                source_text_budget_tokens=6000,
                safety_margin=caps.recommended_safety_margin,
            )
            token_plan = build_token_budget_from_planning_request(capabilities=caps, planning=planning)
            chunks = split_structured_chapter_into_chunks(
                source_id=chapter["source_id"],
                chapter_id=chapter["chapter_id"],
                chapter_text=detected.text,
                chapter_char_start=detected.char_start,
                max_chunk_tokens=max(1000, token_plan["usable_input_budget"] - 4000),
                estimate_tokens=_estimate_token_count,
                overlap_paragraphs=1,
                budget_profile_id=f"{model}:budget:sp070",
                provider_profile_id=profile.profile_id,
            )
            run_id = f"{chapter['chapter_id']}__{model.replace('-', '_')}"
            planned_calls = len(chunks) + 1
            call_count += planned_calls
            continuation_reserve += continuation_reserve_per_run
            run = {
                "run_id": run_id,
                "chapter": chapter,
                "model": model,
                "profile": profile,
                "effective_output_budget": effective_budget,
                "token_plan": token_plan,
                "chunks": chunks,
                "planned_calls": planned_calls,
                "continuation_reserve": continuation_reserve_per_run,
                "compact_reduction_mode": bool(pro_compact_reduction_mode and model == "deepseek-v4-pro"),
                "patch_continuation_mode": bool(patch_continuation_mode),
            }
            runs.append(run)
            public_runs.append(_public_run_plan(run))
    return {
        "runs": runs,
        "public_plan": {
            "assessment": "real_deepseek_e2e_execution_plan_ready",
            "source_file_reference": str(source_path),
            "source_sha256": source_hash,
            "source_text_committed": False,
            "chapters": [item["chapter_id"] for item in chapters],
            "models": models,
            "profiles": [run["profile"].profile_id for run in runs],
            "planned_runs": public_runs,
            "planned_provider_call_count": call_count,
            "planned_continuation_reserve_calls": continuation_reserve,
            "planned_provider_call_count_with_continuation_reserve": call_count + continuation_reserve,
            "provider_call_cap": provider_call_cap,
            "pro_compact_reduction_mode": bool(pro_compact_reduction_mode),
            "patch_continuation_mode": bool(patch_continuation_mode),
            "compact_reduction_policy": build_pro_compact_reduction_policy() if pro_compact_reduction_mode else None,
            "patch_continuation_contract": build_patch_based_continuation_contract() if patch_continuation_mode else None,
            "private_packet_root": str(packet_root),
            "write_back": False,
        },
        "budget_bridge": build_deepseek_budget_bridge(),
    }


def _execute_run(
    *,
    provider: Any,
    run: dict[str, Any],
    packet_root: Path,
    progress_path: Path,
    call_index_start: int,
    total_calls: int,
    max_provider_requests: int,
    response_format_json: bool,
    names: dict[str, str],
) -> tuple[dict[str, Any], int]:
    run_dir = packet_root / run["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    partial_payloads: list[dict[str, Any]] = []
    chunk_results: list[dict[str, Any]] = []
    calls = 0

    for chunk in run["chunks"]:
        calls += 1
        call_no = call_index_start + calls
        print(
            f"run {call_no}/{total_calls} model={run['model']} chapter={run['chapter']['chapter_id']} chunk={chunk.chunk_id} profile={run['profile'].profile_id}",
            flush=True,
        )
        result = _call_chunk(
            provider=provider,
            run=run,
            chunk=chunk,
            run_dir=run_dir,
            call_no=call_no,
            total_calls=total_calls,
            response_format_json=response_format_json,
            progress_path=progress_path,
        )
        result, extra_calls = _maybe_continue_or_repair(
            provider=provider,
            run=run,
            call_result=result,
            run_dir=run_dir,
            response_format_json=response_format_json,
            progress_path=progress_path,
            call_index_start=call_index_start,
            current_calls=calls,
            total_calls=total_calls,
            max_provider_requests=max_provider_requests,
        )
        calls += extra_calls
        chunk_results.append(result)
        if isinstance(result.get("parsed"), dict):
            partial_payloads.append(result["parsed"])

    calls += 1
    call_no = call_index_start + calls
    print(
        f"run {call_no}/{total_calls} model={run['model']} chapter={run['chapter']['chapter_id']} chunk=reduction profile={run['profile'].profile_id}",
        flush=True,
    )
    reduction = _call_reduction(
        provider=provider,
        run=run,
        partial_payloads=partial_payloads,
        run_dir=run_dir,
        call_no=call_no,
        total_calls=total_calls,
        response_format_json=response_format_json,
        progress_path=progress_path,
        compact_mode=bool(run.get("compact_reduction_mode")),
    )
    reduction["compact_mode_used"] = bool(run.get("compact_reduction_mode"))
    reduction, extra_calls = _recover_reduction_if_needed(
        provider=provider,
        run=run,
        reduction=reduction,
        partial_payloads=partial_payloads,
        run_dir=run_dir,
        response_format_json=response_format_json,
        progress_path=progress_path,
        call_index_start=call_index_start,
        current_calls=calls,
        total_calls=total_calls,
        max_provider_requests=max_provider_requests,
    )
    calls += extra_calls

    manifest = {
        "run_id": run["run_id"],
        "model": run["model"],
        "profile_id": run["profile"].profile_id,
        "chapter_id": run["chapter"]["chapter_id"],
        "chunk_count": len(run["chunks"]),
        "provider_call_count": calls,
        "status": "completed",
        "write_back": False,
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    return {
        "run_id": run["run_id"],
        "model": run["model"],
        "profile_id": run["profile"].profile_id,
        "chapter_id": run["chapter"]["chapter_id"],
        "effective_output_budget": asdict(run["effective_output_budget"]),
        "chunks": chunk_results,
        "reduction": reduction,
        "provider_call_count": calls,
    }, calls


def _recover_reduction_if_needed(
    *,
    provider: Any,
    run: dict[str, Any],
    reduction: dict[str, Any],
    partial_payloads: list[dict[str, Any]],
    run_dir: Path,
    response_format_json: bool,
    progress_path: Path,
    call_index_start: int,
    current_calls: int,
    total_calls: int,
    max_provider_requests: int,
) -> tuple[dict[str, Any], int]:
    extra_calls = 0
    strategy = _finish_reason_length_recovery_signal(reduction)
    reduction["recovery_strategy"] = strategy

    need_compact_retry = (
        "deepseek-v4-pro" in str(run.get("model") or "")
        and strategy["should_retry_compact_mode"]
        and not bool(run.get("compact_reduction_mode"))
    )
    if need_compact_retry and call_index_start + current_calls + extra_calls + 1 <= max_provider_requests:
        retry_call_no = call_index_start + current_calls + extra_calls + 1
        compact_retry = _call_reduction(
            provider=provider,
            run=run,
            partial_payloads=partial_payloads,
            run_dir=run_dir,
            call_no=retry_call_no,
            total_calls=total_calls,
            response_format_json=response_format_json,
            progress_path=progress_path,
            compact_mode=True,
            stem="reduction__compact_retry",
        )
        extra_calls += 1
        compact_retry["compact_mode_used"] = True
        compact_retry["recovery_strategy"] = strategy
        reduction["compact_retry_private_dir"] = compact_retry.get("private_dir")
        if compact_retry.get("parseable_json"):
            compact_retry["recovery_status"] = "compact_retry_replaced_primary"
            reduction = compact_retry
        else:
            reduction["recovery_status"] = "compact_retry_failed"
            reduction["compact_retry_failure_mode"] = compact_retry.get("failure_mode")
            reduction["compact_retry_finish_reason"] = compact_retry.get("finish_reason")
            if not bool(run.get("patch_continuation_mode")):
                return reduction, extra_calls

    use_patch_continuation = bool(run.get("patch_continuation_mode")) and (
        strategy["should_patch_continue"] or reduction.get("failure_mode") in {"invalid_json_truncated", "finish_reason_length", "output_near_max_tokens", "unterminated_string", "unterminated_array_or_object"}
    )
    if use_patch_continuation:
        reduction, continuation_calls = _maybe_patch_continue_reduction(
            provider=provider,
            run=run,
            call_result=reduction,
            partial_payloads=partial_payloads,
            run_dir=run_dir,
            response_format_json=response_format_json,
            progress_path=progress_path,
            call_index_start=call_index_start,
            current_calls=current_calls + extra_calls,
            total_calls=total_calls,
            max_provider_requests=max_provider_requests,
        )
        extra_calls += continuation_calls
    else:
        reduction, continuation_calls = _maybe_continue_or_repair(
            provider=provider,
            run=run,
            call_result=reduction,
            run_dir=run_dir,
            response_format_json=response_format_json,
            progress_path=progress_path,
            call_index_start=call_index_start,
            current_calls=current_calls + extra_calls,
            total_calls=total_calls,
            max_provider_requests=max_provider_requests,
        )
        extra_calls += continuation_calls
    return reduction, extra_calls


def _finish_reason_length_recovery_signal(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    completion_tokens = float(usage.get("completion_tokens") or 0)
    max_output_tokens = float(result.get("effective_max_output_tokens") or 0)
    reasoning_tokens = float(((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0))
    finish_reason = str(result.get("finish_reason") or "").casefold()
    output_budget_exhausted = bool(max_output_tokens and completion_tokens >= max_output_tokens * 0.95)
    reasoning_tokens_present = reasoning_tokens > 0
    reasoning_tokens_ratio = (reasoning_tokens / completion_tokens) if completion_tokens > 0 else 0.0
    reasoning_tokens_high = reasoning_tokens_present and reasoning_tokens_ratio >= 0.5
    return {
        "finish_reason": finish_reason,
        "completion_tokens": int(completion_tokens) if completion_tokens else None,
        "effective_max_output_tokens": int(max_output_tokens) if max_output_tokens else None,
        "output_budget_exhausted": output_budget_exhausted,
        "reasoning_tokens_present": reasoning_tokens_present,
        "reasoning_tokens_high": reasoning_tokens_high,
        "reasoning_tokens_ratio": reasoning_tokens_ratio if reasoning_tokens_present else None,
        "visible_output_too_short_for_completion": bool(not result.get("parseable_json")),
        "pro_reasoning_budget_exhaustion": finish_reason == "length" and reasoning_tokens_high,
        "should_retry_compact_mode": finish_reason == "length" or output_budget_exhausted,
        "should_patch_continue": finish_reason == "length" or output_budget_exhausted,
    }


def _call_chunk(
    *,
    provider: Any,
    run: dict[str, Any],
    chunk: StructuredSourceChunk,
    run_dir: Path,
    call_no: int,
    total_calls: int,
    response_format_json: bool,
    progress_path: Path,
) -> dict[str, Any]:
    detected = run["chapter"]["detected"]
    title_hints = _extract_title_entity_hints(detected.title)
    title_signals = _extract_title_parse_signals(detected.title)
    prompt = (
        f"{CHAPTER_PARTIAL_EXTRACTION_PROMPT}\n\n"
        f"WORK_TITLE: 王者の杖\n"
        f"WORK_LANGUAGE: ja\n\n"
        f"CHAPTER_ID: {run['chapter']['chapter_id']}\n"
        f"CHUNK_ID: {chunk.chunk_id}\n"
        f"CHAPTER_TITLE: {detected.title}\n\n"
        f"STRUCTURED_CHUNK_METADATA:\n{json.dumps(chunk.to_dict(), ensure_ascii=False)}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_hints, ensure_ascii=False)}\n\n"
        f"TITLE_PARSE_SIGNALS: {json.dumps(title_signals, ensure_ascii=False)}\n\n"
        f"CANONICAL_ENTITY_MAP:\n[]\n\n"
        f"CHUNK_TEXT:\n{chunk.text}"
    )
    system, user = apply_provider_prompt_profile("Return only valid JSON for one chapter subchunk extraction.", prompt, run["profile"])
    system = inject_output_budget_control(system, effective_max_output_tokens=run["effective_output_budget"].effective_max_output_tokens)
    user = (
        f"{user}\n\n"
        "BUDGET_PRIORITY_NOTE: Keep candidate_summary_points short and optional. "
        "Prioritize structured extraction sections over long prose summaries."
    )
    return _execute_request(
        provider=provider,
        run=run,
        run_dir=run_dir,
        stem=chunk.chunk_id,
        system=system,
        user=user,
        mode="chapter_partial_extraction",
        chunk=chunk,
        call_no=call_no,
        total_calls=total_calls,
        response_format_json=response_format_json,
        progress_path=progress_path,
    )


def _call_reduction(
    *,
    provider: Any,
    run: dict[str, Any],
    partial_payloads: list[dict[str, Any]],
    run_dir: Path,
    call_no: int,
    total_calls: int,
    response_format_json: bool,
    progress_path: Path,
    compact_mode: bool = False,
    stem: str = "reduction",
) -> dict[str, Any]:
    detected = run["chapter"]["detected"]
    title_hints = _extract_title_entity_hints(detected.title)
    title_signals = _extract_title_parse_signals(detected.title)
    chunk_metadata = [chunk.to_dict() for chunk in run["chunks"]]
    prompt = (
        f"{CHAPTER_REDUCTION_PROMPT}\n\n"
        f"WORK_TITLE: 王者の杖\n"
        f"WORK_LANGUAGE: ja\n\n"
        f"CHAPTER_ID: {run['chapter']['chapter_id']}\n"
        f"SEQUENCE_INDEX: {run['chapter']['sequence_index']}\n"
        f"CHAPTER_TITLE: {detected.title}\n\n"
        f"STRUCTURED_CHUNK_METADATA:\n{json.dumps(chunk_metadata, ensure_ascii=False)}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_hints, ensure_ascii=False)}\n\n"
        f"TITLE_PARSE_SIGNALS: {json.dumps(title_signals, ensure_ascii=False)}\n\n"
        f"CANONICAL_ENTITY_MAP:\n[]\n\n"
        f"PARTIAL_SIGNALS:\n{json.dumps(partial_payloads, ensure_ascii=False)}"
    )
    system, user = apply_provider_prompt_profile("Return only valid JSON for chapter reduction.", prompt, run["profile"])
    system = inject_output_budget_control(system, effective_max_output_tokens=run["effective_output_budget"].effective_max_output_tokens)
    if compact_mode:
        system = inject_compact_reduction_control(system, mode_label=build_pro_compact_reduction_policy()["mode_id"])
    user = (
        f"{user}\n\n"
        "SOURCE_REF_RULE: Every final item in characters, places, concepts, objects, events, relations, and unresolved_mentions "
        "must preserve source_refs from matching partial signals. If exact item spans are unavailable, use contributing chunk spans."
    )
    if compact_mode:
        compact_policy = build_pro_compact_reduction_policy()
        user = (
            f"{user}\n\n"
            "COMPACT_REDUCTION_MODE: true\n"
            f"COMPACT_POLICY: {json.dumps(compact_policy['caps'], ensure_ascii=False)}\n"
            "PRIORITY: valid JSON > complete coverage > short evidence > no prose.\n"
            "Do not expand candidate_summary_points.\n"
            "Limit each item to short facts.\n"
            "Keep review/local_candidate if uncertain."
        )
    return _execute_request(
        provider=provider,
        run=run,
        run_dir=run_dir,
        stem=stem,
        system=system,
        user=user,
        mode="chapter_reduction_compact" if compact_mode else "chapter_reduction",
        chunk=None,
        call_no=call_no,
        total_calls=total_calls,
        response_format_json=response_format_json,
        progress_path=progress_path,
    )


def _execute_request(
    *,
    provider: Any,
    run: dict[str, Any],
    run_dir: Path,
    stem: str,
    system: str,
    user: str,
    mode: str,
    chunk: StructuredSourceChunk | None,
    call_no: int,
    total_calls: int,
    response_format_json: bool,
    progress_path: Path,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    _append_progress(
        progress_path,
        {
            "run_index": call_no,
            "run_total": total_calls,
            "started_at": started.isoformat(),
            "model": run["model"],
            "chapter": run["chapter"]["chapter_id"],
            "chunk_id": stem,
            "profile_id": run["profile"].profile_id,
            "status": "started",
        },
    )

    call_dir = run_dir / stem
    call_dir.mkdir(parents=True, exist_ok=True)

    _write_private(call_dir / "system_prompt.md", system)
    _write_private(call_dir / "user_prompt.md", user)
    _write_private(call_dir / "final_prompt_sent.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    _write_private(call_dir / "provider_profile_or_overlay.md", run["profile"].prompt_overlay)

    max_output_tokens = run["effective_output_budget"].effective_max_output_tokens
    request_payload = {
        "model": run["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_output_tokens,
        "temperature": 0.1,
        "response_format": {"type": "json_object"} if response_format_json else None,
        "effective_max_output_tokens": max_output_tokens,
        "headers": {"Authorization": "<redacted>"},
    }
    _write_json(call_dir / "provider_request_payload.redacted.json", request_payload)

    parsed = None
    error = None
    response_text = ""
    provider_metadata: dict[str, Any] = {}
    started_perf = time.perf_counter()
    try:
        response = provider.generate(
            TextGenerationRequest(
                task=TASK,
                provider_name="deepseek",
                model=run["model"],
                system=system,
                messages=[TextMessage(role="user", content=user)],
                max_tokens=max_output_tokens,
                temperature=0.1,
                timeout_seconds=180,
                retries=1,
                response_format={"type": "json_object"} if response_format_json else None,
            )
        )
        response_text = response.text or ""
        provider_metadata = _extract_provider_metadata(response.raw)
        _write_private(call_dir / "provider_response_raw.txt", response_text)
        parsed = extract_json_payload(response_text)
        if isinstance(parsed, dict):
            if mode.startswith("chapter_reduction"):
                parsed = _carry_forward_reduction_source_refs(parsed, chunks=run["chunks"])
            _write_json(call_dir / "provider_response_parsed.json", parsed)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        _write_private(call_dir / "provider_response_raw.txt", response_text)

    duration = time.perf_counter() - started_perf
    parseable = isinstance(parsed, dict)

    _write_json(call_dir / "provider_usage.json", provider_metadata.get("usage") or {})
    _write_json(
        call_dir / "finish_reason_report.json",
        {
            "finish_reason": provider_metadata.get("finish_reason"),
            "effective_max_output_tokens": max_output_tokens,
            "model": provider_metadata.get("model"),
            "response_id": provider_metadata.get("id"),
            "created": provider_metadata.get("created"),
        },
    )

    validation = _validation_report(
        parsed=parsed,
        expected_chapter_id=run["chapter"]["chapter_id"],
        mode=mode,
        chunk=chunk,
        response_text=response_text,
        error=error,
        provider_metadata=provider_metadata,
        effective_max_output_tokens=max_output_tokens,
    )
    failure_mode = _failure_mode(validation)

    _write_json(call_dir / "validation_report.json", validation)
    _write_json(
        call_dir / "failure_mode_report.json",
        {
            "failure_mode": failure_mode,
            "validation_ok": validation["validation_ok"],
            "parseable_json": parseable,
        },
    )
    _write_json(call_dir / "response_control_report.json", _extract_response_control(parsed))
    _write_json(
        call_dir / "variant_diff_and_hypothesis.json",
        {
            "profile_id": run["profile"].profile_id,
            "hypothesis": "SP076 protocol: dynamic budget + response_control + source-ref carry-forward + truncation recovery improves robustness.",
            "prompt_change_type": ["structured_chunk_metadata", "output_budget_control", "response_control", "source_ref_carry_forward"],
        },
    )
    _write_private(
        call_dir / "codex_interpretation.md",
        f"mode={mode}\nparseable_json={parseable}\nvalidation_ok={validation['validation_ok']}\nfailure_mode={failure_mode}\n",
    )

    finished = datetime.now(UTC)
    size = (call_dir / "provider_response_raw.txt").stat().st_size if (call_dir / "provider_response_raw.txt").exists() else 0
    _append_progress(
        progress_path,
        {
            "run_index": call_no,
            "run_total": total_calls,
            "started_at": started.isoformat(),
            "last_output_activity_at": finished.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": duration,
            "output_file_size_bytes": size,
            "model": run["model"],
            "chapter": run["chapter"]["chapter_id"],
            "chunk_id": stem,
            "profile_id": run["profile"].profile_id,
            "status": "finished",
            "failure_mode": failure_mode,
        },
    )

    return {
        "mode": mode,
        "chunk_id": stem,
        "parseable_json": parseable,
        "validation_ok": validation["validation_ok"],
        "failure_mode": failure_mode,
        "counts": validation["counts"],
        "score": validation["score"],
        "thin_warnings": validation["thin_warnings"],
        "source_span": chunk.source_span if chunk else None,
        "finish_reason": provider_metadata.get("finish_reason"),
        "usage": provider_metadata.get("usage") or {},
        "effective_max_output_tokens": max_output_tokens,
        "response_control": _extract_response_control(parsed),
        "parsed": parsed if isinstance(parsed, dict) else None,
        "private_dir": str(call_dir),
    }


def _maybe_patch_continue_reduction(
    *,
    provider: Any,
    run: dict[str, Any],
    call_result: dict[str, Any],
    partial_payloads: list[dict[str, Any]],
    run_dir: Path,
    response_format_json: bool,
    progress_path: Path,
    call_index_start: int,
    current_calls: int,
    total_calls: int,
    max_provider_requests: int,
) -> tuple[dict[str, Any], int]:
    if call_result.get("parseable_json") and call_result.get("response_control", {}).get("completion_status") != "partial":
        call_result["continuation_status"] = call_result.get("continuation_status") or "not_triggered"
        return call_result, 0

    if call_index_start + current_calls + 1 > max_provider_requests:
        call_result["continuation_status"] = "skipped_cap_reached"
        call_result["continuation_mode"] = "patch_based"
        return call_result, 0

    patch_contract = build_patch_based_continuation_contract()
    recovery_context = {
        "chapter_id": run["chapter"]["chapter_id"],
        "run_id": run["run_id"],
        "failure_mode": call_result.get("failure_mode"),
        "finish_reason": call_result.get("finish_reason"),
        "known_partial_counts": _summarize_partial_counts(partial_payloads),
        "known_chunk_spans": [
            {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "chapter_id": chunk.chapter_id,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
            }
            for chunk in run["chunks"]
        ],
    }
    prompt = (
        "PATCH_BASED_CONTINUATION_REQUEST\n\n"
        "Return ONLY one valid JSON object.\n"
        "Do NOT reconstruct the full extraction JSON.\n"
        "Return only continuation_patch and patch_metadata.\n"
        f"PATCH_CONTRACT: {json.dumps(patch_contract, ensure_ascii=False)}\n"
        f"RECOVERY_CONTEXT: {json.dumps(recovery_context, ensure_ascii=False)}"
    )
    system = inject_output_budget_control(
        inject_compact_reduction_control("Return valid JSON patch only.", mode_label="patch_compact_recovery_v1"),
        effective_max_output_tokens=run["effective_output_budget"].effective_max_output_tokens,
    )

    patch_call_no = call_index_start + current_calls + 1
    patch_result = _execute_request(
        provider=provider,
        run=run,
        run_dir=run_dir,
        stem=f"{call_result['chunk_id']}__patch_continuation",
        system=system,
        user=prompt,
        mode=f"{call_result['mode']}_patch_continuation",
        chunk=None,
        call_no=patch_call_no,
        total_calls=total_calls,
        response_format_json=response_format_json,
        progress_path=progress_path,
    )

    call_result["continuation_mode"] = "patch_based"
    call_result["continuation_status"] = "executed"
    call_result["continuation_private_dir"] = patch_result["private_dir"]

    merged = _merge_patch_into_reduction(call_result=call_result, patch_result=patch_result, run=run, partial_payloads=partial_payloads)
    if merged is not None:
        merged["continuation_status"] = "patch_merged"
        merged["continuation_mode"] = "patch_based"
        merged["continuation_private_dir"] = patch_result["private_dir"]
        return merged, 1

    call_result["continuation_status"] = "executed_but_not_parseable"
    return call_result, 1


def _summarize_partial_counts(partials: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"characters": 0, "places": 0, "concepts": 0, "objects": 0, "events": 0, "relations": 0, "unresolved_mentions": 0}
    for partial in partials:
        signals = partial.get("partial_signals") if isinstance(partial, dict) else None
        if not isinstance(signals, dict):
            continue
        for key in counts:
            value = signals.get(key)
            if isinstance(value, list):
                counts[key] += len(value)
    return counts


def _merge_patch_into_reduction(
    *, call_result: dict[str, Any], patch_result: dict[str, Any], run: dict[str, Any], partial_payloads: list[dict[str, Any]]
) -> dict[str, Any] | None:
    patch_payload = patch_result.get("parsed")
    if not isinstance(patch_payload, dict):
        return None
    patch = patch_payload.get("continuation_patch")
    if not isinstance(patch, dict):
        return None

    base_payload = call_result.get("parsed") if isinstance(call_result.get("parsed"), dict) else _build_reduction_fallback_from_partials(run, partial_payloads)
    if not isinstance(base_payload, dict):
        return None
    chapter = _first_chapter(base_payload)
    if not isinstance(chapter, dict):
        return None

    for section in ("characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"):
        target = chapter.get(section)
        if not isinstance(target, list):
            target = []
            chapter[section] = target
        patch_items = patch.get(section)
        if not isinstance(patch_items, list):
            continue
        for item in patch_items:
            if not isinstance(item, dict):
                continue
            _merge_item_into_section(target, item)

    merged_payload = _carry_forward_reduction_source_refs(base_payload, chunks=run["chunks"])
    validation = _validation_report(
        parsed=merged_payload,
        expected_chapter_id=run["chapter"]["chapter_id"],
        mode="chapter_reduction_patch_merged",
        chunk=None,
        response_text=json.dumps(merged_payload, ensure_ascii=False),
        error=None,
        provider_metadata={
            "finish_reason": patch_result.get("finish_reason"),
            "usage": patch_result.get("usage") or {},
        },
        effective_max_output_tokens=run["effective_output_budget"].effective_max_output_tokens,
    )
    if not validation.get("parseable_json"):
        return None

    merged = dict(call_result)
    merged.update(
        {
            "parseable_json": True,
            "parsed": merged_payload,
            "validation_ok": bool(validation.get("validation_ok")),
            "failure_mode": _failure_mode(validation),
            "counts": validation.get("counts") or merged.get("counts") or {},
            "score": validation.get("score") if validation.get("score") is not None else merged.get("score"),
            "thin_warnings": validation.get("thin_warnings") or merged.get("thin_warnings") or [],
        }
    )
    return merged


def _build_reduction_fallback_from_partials(run: dict[str, Any], partial_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    chapter = {
        "chapter_id": run["chapter"]["chapter_id"],
        "characters": [],
        "places": [],
        "concepts": [],
        "objects": [],
        "events": [],
        "relations": [],
        "unresolved_mentions": [],
    }
    fallback_refs = [
        {
            "source_id": chunk.source_id,
            "chapter_id": chunk.chapter_id,
            "chunk_id": chunk.chunk_id,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }
        for chunk in run["chunks"]
    ]
    section_keys = ("characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions")
    for payload in partial_payloads:
        signals = payload.get("partial_signals") if isinstance(payload, dict) else None
        if not isinstance(signals, dict):
            continue
        for section in section_keys:
            raw_items = signals.get(section)
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                mapped = {
                    "canonical_name": item.get("canonical") or item.get("canonical_name") or item.get("surface") or item.get("name"),
                    "surface": item.get("surface"),
                    "source_refs": _dedupe_source_refs(list(item.get("source_refs") or []) + fallback_refs),
                }
                if isinstance(item.get("facts"), list) and item.get("facts"):
                    mapped["facts"] = item.get("facts")[:2]
                if section == "relations":
                    mapped["source"] = item.get("source") or mapped.get("canonical_name")
                    mapped["target"] = item.get("target")
                    mapped["relation_category"] = item.get("relation_category") or item.get("type")
                if section == "events":
                    mapped["event_importance"] = item.get("event_importance") or "minor"
                _merge_item_into_section(chapter[section], mapped)
    return _carry_forward_reduction_source_refs({"chapters": [chapter]}, chunks=run["chunks"])


def _item_identity(item: dict[str, Any]) -> tuple[str, str]:
    key = str(item.get("canonical_name") or item.get("surface") or item.get("name") or item.get("source") or item.get("target") or "unknown")
    secondary = str(item.get("relation_category") or item.get("type") or "")
    return key.casefold(), secondary.casefold()


def _merge_item_into_section(target: list[dict[str, Any]], patch_item: dict[str, Any]) -> None:
    identity = _item_identity(patch_item)
    for existing in target:
        if not isinstance(existing, dict):
            continue
        if _item_identity(existing) != identity:
            continue
        patch_refs = patch_item.get("source_refs") if isinstance(patch_item.get("source_refs"), list) else []
        existing_refs = existing.get("source_refs") if isinstance(existing.get("source_refs"), list) else []
        existing["source_refs"] = _dedupe_source_refs(existing_refs + patch_refs)
        for key, value in patch_item.items():
            if key == "source_refs":
                continue
            if key not in existing or existing.get(key) in (None, "", [], {}):
                existing[key] = value
        return
    target.append(patch_item)


def _maybe_continue_or_repair(
    *,
    provider: Any,
    run: dict[str, Any],
    call_result: dict[str, Any],
    run_dir: Path,
    response_format_json: bool,
    progress_path: Path,
    call_index_start: int,
    current_calls: int,
    total_calls: int,
    max_provider_requests: int,
) -> tuple[dict[str, Any], int]:
    if call_result.get("parseable_json") and call_result.get("response_control", {}).get("completion_status") != "partial":
        return call_result, 0

    should_continue = False
    triggers = []
    if call_result.get("response_control", {}).get("completion_status") == "partial":
        should_continue = True
        triggers.append("response_control.partial")
    if call_result.get("failure_mode") in {
        "invalid_json_truncated",
        "finish_reason_length",
        "output_near_max_tokens",
        "unterminated_string",
        "unterminated_array_or_object",
        "pro_reasoning_budget_exhaustion",
    }:
        should_continue = True
        triggers.append(call_result.get("failure_mode"))

    if not should_continue:
        return call_result, 0
    if call_index_start + current_calls + 1 > max_provider_requests:
        call_result["continuation_status"] = "skipped_cap_reached"
        call_result["continuation_triggers"] = triggers
        return call_result, 0

    next_call_no = call_index_start + current_calls + 1
    stem = f"{call_result['chunk_id']}__continuation"
    prior_dir = Path(call_result["private_dir"])
    prior_raw = (prior_dir / "provider_response_raw.txt").read_text(encoding="utf-8", errors="replace") if (prior_dir / "provider_response_raw.txt").exists() else ""

    continuation_contract = build_continuation_repair_contract()
    prompt = (
        "CONTINUATION_REPAIR_REQUEST\n\n"
        "Return ONLY one valid JSON object.\n"
        "Do not repeat full prose. Repair or continue previous output to a complete valid JSON object.\n"
        f"TRIGGERS: {json.dumps(triggers, ensure_ascii=False)}\n"
        f"CONTRACT: {json.dumps(continuation_contract, ensure_ascii=False)}\n\n"
        f"PREVIOUS_RESPONSE_TAIL:\n{prior_raw[-6000:]}"
    )
    system = inject_output_budget_control(
        "Return valid JSON continuation/repair only.",
        effective_max_output_tokens=run["effective_output_budget"].effective_max_output_tokens,
    )
    continuation_result = _execute_request(
        provider=provider,
        run=run,
        run_dir=run_dir,
        stem=stem,
        system=system,
        user=prompt,
        mode=f"{call_result['mode']}_continuation",
        chunk=None,
        call_no=next_call_no,
        total_calls=total_calls,
        response_format_json=response_format_json,
        progress_path=progress_path,
    )

    call_result["continuation_status"] = "executed"
    call_result["continuation_triggers"] = triggers
    call_result["continuation_private_dir"] = continuation_result["private_dir"]
    if continuation_result.get("parseable_json"):
        call_result.update(continuation_result)
        call_result["continuation_status"] = "executed_replaced_primary"
    else:
        call_result["continuation_status"] = "executed_but_not_parseable"
    return call_result, 1


def _validation_report(
    *,
    parsed: Any,
    expected_chapter_id: str,
    mode: str,
    chunk: StructuredSourceChunk | None,
    response_text: str,
    error: str | None,
    provider_metadata: dict[str, Any] | None = None,
    effective_max_output_tokens: int | None = None,
) -> dict[str, Any]:
    counts = {"characters": 0, "places": 0, "concepts": 0, "objects": 0, "events": 0, "relations": 0, "unresolved_mentions": 0}
    chapter_ok = False
    relation_category_present = False
    event_importance_present = False

    if isinstance(parsed, dict):
        if mode.startswith("chapter_partial_extraction"):
            chapter_ok = str(parsed.get("chapter_id") or "") == expected_chapter_id
            signals = parsed.get("partial_signals") if isinstance(parsed.get("partial_signals"), dict) else {}
            counts = {key: len(signals.get(key) or []) for key in counts}
            event_importance_present = any(bool(item.get("event_importance")) for item in signals.get("events") or [] if isinstance(item, dict))
            relation_category_present = any(bool(item.get("relation_category")) for item in signals.get("relations") or [] if isinstance(item, dict))
        else:
            chapter = _first_chapter(parsed)
            chapter_ok = isinstance(chapter, dict) and str(chapter.get("chapter_id") or "") == expected_chapter_id
            if isinstance(chapter, dict):
                counts = {key: len(chapter.get(key) or []) for key in counts}
                event_importance_present = any(bool(item.get("event_importance")) for item in chapter.get("events") or [] if isinstance(item, dict))
                relation_category_present = any(bool(item.get("relation_category")) for item in chapter.get("relations") or [] if isinstance(item, dict))

    score = _score(counts, event_importance_present, relation_category_present, len(response_text), chapter_ok)
    usage = (provider_metadata or {}).get("usage") or {}
    thin = build_thin_output_warnings(
        {
            "score": score,
            "counts": counts,
            "response_text_chars": len(response_text),
            "validation_ok": chapter_ok,
            "response_parseable_json": isinstance(parsed, dict),
        }
    )
    return {
        "validation_ok": isinstance(parsed, dict) and chapter_ok and error is None,
        "parseable_json": isinstance(parsed, dict),
        "expected_chapter_id": expected_chapter_id,
        "chapter_id_ok": chapter_ok,
        "error": error,
        "counts": counts,
        "score": score,
        "event_importance_present": event_importance_present,
        "relation_category_present": relation_category_present,
        "response_text_chars": len(response_text),
        "thin_warnings": thin["warnings"],
        "source_span_preserved": bool(chunk.source_span) if chunk else True,
        "finish_reason": (provider_metadata or {}).get("finish_reason"),
        "model": (provider_metadata or {}).get("model"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") if isinstance(usage, dict) else None),
        "effective_max_output_tokens": effective_max_output_tokens,
        "response_tail": response_text[-200:],
    }


def _failure_mode(validation: dict[str, Any]) -> str | None:
    if validation.get("validation_ok"):
        return None
    error = str(validation.get("error") or "").casefold()
    if "textprovidererror" in error or "http" in error or "unauthorized" in error:
        return "provider_error"
    if not validation.get("parseable_json"):
        return classify_failure_mode(validation) or "invalid_json_unknown"
    if not validation.get("chapter_id_ok"):
        return "valid_json_wrong_chapter"
    if validation.get("score", 0) < 20:
        return "valid_json_thin"
    return "validation_failed_missing_required_sections"


def _extract_provider_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    return {
        "finish_reason": first.get("finish_reason"),
        "usage": raw.get("usage") if isinstance(raw.get("usage"), dict) else {},
        "model": raw.get("model"),
        "id": raw.get("id"),
        "created": raw.get("created"),
    }


def _extract_response_control(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"present": False, "completion_status": "unknown", "continuation_required": None, "continuation_cursor": None, "omitted_sections": []}
    control = parsed.get("response_control") if isinstance(parsed.get("response_control"), dict) else {}
    return {
        "present": bool(control),
        "completion_status": control.get("completion_status", "unknown"),
        "continuation_required": control.get("continuation_required"),
        "continuation_cursor": control.get("continuation_cursor"),
        "omitted_sections": list(control.get("omitted_sections") or []),
    }


def _carry_forward_reduction_source_refs(payload: dict[str, Any], *, chunks: list[StructuredSourceChunk]) -> dict[str, Any]:
    if not chunks:
        return payload
    fallback_refs = [
        {
            "source_id": chunk.source_id,
            "chapter_id": chunk.chapter_id,
            "chunk_id": chunk.chunk_id,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }
        for chunk in chunks
    ]
    chapter = _first_chapter(payload)
    if not isinstance(chapter, dict):
        return payload
    for section in ("characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"):
        for item in chapter.get(section) or []:
            if isinstance(item, dict):
                item["source_refs"] = _dedupe_source_refs(list(item.get("source_refs") or item.get("source_spans") or []) + fallback_refs)
    return payload


def _dedupe_source_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        normalized = {
            "source_id": ref.get("source_id"),
            "chapter_id": ref.get("chapter_id"),
            "chunk_id": ref.get("chunk_id"),
            "char_start": ref.get("char_start"),
            "char_end": ref.get("char_end"),
        }
        key = tuple(normalized.values())
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _score(counts: dict[str, int], event_importance: bool, relation_category: bool, chars: int, chapter_ok: bool) -> float:
    score = (
        counts["characters"]
        + counts["places"]
        + counts["concepts"]
        + counts["objects"] * 1.5
        + counts["events"] * 1.5
        + counts["relations"] * 2
        + counts["unresolved_mentions"]
    )
    if event_importance:
        score += 2
    if relation_category:
        score += 2
    if not chapter_ok:
        score -= 5
    if chars < 2500:
        score -= 3
    return score


def _build_public_reports(*, plan: dict[str, Any], results: list[dict[str, Any]], packet_root: Path) -> dict[str, Any]:
    chunk_rows: list[dict[str, Any]] = []
    reduction_rows: list[dict[str, Any]] = []
    budget_rows: list[dict[str, Any]] = []
    truncation_rows: list[dict[str, Any]] = []
    source_ref_rows: list[dict[str, Any]] = []

    for result in results:
        budget_rows.append(
            {
                "run_id": result["run_id"],
                "model": result["model"],
                "profile_id": result["profile_id"],
                **result["effective_output_budget"],
            }
        )

        for chunk in result["chunks"]:
            row = {key: result[key] for key in ("run_id", "model", "profile_id", "chapter_id")}
            row.update({k: v for k, v in chunk.items() if k not in {"parsed", "private_dir"}})
            row["private_dir"] = _private_path_hint(chunk["private_dir"])
            chunk_rows.append(row)
            truncation_rows.append(
                {
                    "run_id": row["run_id"],
                    "model": row["model"],
                    "profile_id": row["profile_id"],
                    "chapter_id": row["chapter_id"],
                    "chunk_id": row["chunk_id"],
                    "mode": row["mode"],
                    "failure_mode": row.get("failure_mode"),
                    "finish_reason": row.get("finish_reason"),
                    "completion_tokens": (row.get("usage") or {}).get("completion_tokens"),
                    "reasoning_tokens": ((row.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens"),
                    "total_tokens": (row.get("usage") or {}).get("total_tokens"),
                    "effective_max_output_tokens": row.get("effective_max_output_tokens"),
                    "response_control": row.get("response_control"),
                    "continuation_status": row.get("continuation_status", "not_triggered"),
                    "recovery_strategy": row.get("recovery_strategy"),
                }
            )

        red = {key: result[key] for key in ("run_id", "model", "profile_id", "chapter_id")}
        red.update({k: v for k, v in result["reduction"].items() if k not in {"parsed", "private_dir"}})
        red["private_dir"] = _private_path_hint(result["reduction"]["private_dir"])
        reduction_rows.append(red)
        truncation_rows.append(
            {
                "run_id": red["run_id"],
                "model": red["model"],
                "profile_id": red["profile_id"],
                "chapter_id": red["chapter_id"],
                "chunk_id": red["chunk_id"],
                "mode": red["mode"],
                "failure_mode": red.get("failure_mode"),
                "finish_reason": red.get("finish_reason"),
                "completion_tokens": (red.get("usage") or {}).get("completion_tokens"),
                "reasoning_tokens": ((red.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens"),
                "total_tokens": (red.get("usage") or {}).get("total_tokens"),
                "effective_max_output_tokens": red.get("effective_max_output_tokens"),
                "response_control": red.get("response_control"),
                "continuation_status": red.get("continuation_status", "not_triggered"),
                "recovery_strategy": red.get("recovery_strategy"),
            }
        )

        parsed = result["reduction"].get("parsed")
        source_ref_rows.append(_source_ref_audit_row(result=result, parsed=parsed))

    valid_reductions = [row for row in reduction_rows if row["parseable_json"] and row["validation_ok"]]
    all_reductions_valid = bool(reduction_rows) and len(valid_reductions) == len(reduction_rows)
    source_ref_preservation = all(item["item_level_source_ref_coverage_ratio"] >= 1.0 for item in source_ref_rows if item["parseable_json"]) if source_ref_rows else False
    all_parseable_reductions_have_source_refs = all(
        item["parseable_json"] and item["item_level_source_ref_coverage_ratio"] >= 1.0
        for item in source_ref_rows
        if item["parseable_json"]
    ) if source_ref_rows else False
    continuation_problem = any(
        item.get("continuation_status") in {"executed_but_not_parseable", "skipped_cap_reached"}
        or item.get("failure_mode") in {"invalid_json_truncated", "finish_reason_length", "output_near_max_tokens", "unterminated_string", "unterminated_array_or_object"}
        for item in truncation_rows
    )

    pro_compact_phase = bool(plan["public_plan"].get("pro_compact_reduction_mode") and plan["public_plan"].get("patch_continuation_mode"))
    if pro_compact_phase:
        if all_reductions_valid and source_ref_preservation and not continuation_problem:
            assessment = "pro_compact_reduction_recovery_ready"
        elif valid_reductions:
            assessment = "pro_compact_reduction_improved_but_needs_review"
        elif any(row["parseable_json"] for row in reduction_rows + chunk_rows):
            assessment = "pro_compact_reduction_improved_but_needs_review"
        else:
            assessment = "pro_reduction_truncation_still_blocking"
    else:
        if all_reductions_valid and source_ref_preservation and all_parseable_reductions_have_source_refs and not continuation_problem:
            assessment = "real_deepseek_e2e_validation_passed_ready_for_larger_e2e"
        elif valid_reductions:
            assessment = "real_deepseek_e2e_validation_passed_with_review_warnings"
        elif any(row["parseable_json"] for row in reduction_rows + chunk_rows):
            assessment = "real_deepseek_e2e_validation_partial_success_needs_patch"
        else:
            assessment = "real_deepseek_e2e_validation_failed_but_debuggable"

    summary = {
        "assessment": assessment,
        "provider": "deepseek",
        "models": plan["public_plan"]["models"],
        "chapters": plan["public_plan"]["chapters"],
        "provider_call_count": sum(item["provider_call_count"] for item in results),
        "provider_call_cap": plan["public_plan"]["provider_call_cap"],
        "compact_mode_used": bool(plan["public_plan"].get("pro_compact_reduction_mode")),
        "patch_continuation_mode": bool(plan["public_plan"].get("patch_continuation_mode")),
        "valid_reduction_count": len(valid_reductions),
        "total_reduction_count": len(reduction_rows),
        "triggered_continuation_count": sum(1 for item in truncation_rows if item.get("continuation_status", "not_triggered") != "not_triggered"),
        "private_packet_root": str(packet_root),
        "recommended_files_to_upload_to_chatgpt": [
            "README.md",
            "execution_plan_private.md",
            "matrix_summary_private.md",
            "decision_notes_private.md",
            "source_ref_audit_private.md",
            "truncation_recovery_audit_private.md",
            "reduction_trace_private.md",
        ],
        "comparison_vs_sp075": {
            "sp075_assessment": "real_deepseek_e2e_dryrun_partial_success",
            "sp075_best_reduction_score": 57.5,
            "sp077_best_reduction_score": max((row.get("score", -999) for row in reduction_rows), default=-999),
            "source_ref_item_level_improved": source_ref_preservation,
            "continuation_or_truncation_issue_remaining": continuation_problem,
        },
        "write_back": False,
    }

    decision = {
        "assessment": assessment,
        "ready_for_larger_real_e2e": assessment in {"real_deepseek_e2e_validation_passed_ready_for_larger_e2e", "real_deepseek_e2e_validation_passed_with_review_warnings", "pro_compact_reduction_recovery_ready", "pro_compact_reduction_improved_but_needs_review"},
        "needs_review_warnings": assessment not in {"real_deepseek_e2e_validation_passed_ready_for_larger_e2e", "pro_compact_reduction_recovery_ready"},
        "private_packet_root": str(packet_root),
        "product_decision": assessment,
        "next_suggested_phase": "Phase 1.3.M-b5c-4h — Larger DeepSeek E2E with Multi-chunk Chapters" if assessment in {"pro_compact_reduction_recovery_ready", "pro_compact_reduction_improved_but_needs_review"} else "Phase 1.3.M-b5c-4h — Compact Reduction Policy Hardening before Larger E2E",
    }

    return {
        "summary": summary,
        "chunk_results": {"assessment": assessment, "chunks": chunk_rows},
        "reduction_summary": {"assessment": assessment, "reductions": reduction_rows, "source_ref_preservation": source_ref_preservation},
        "budget_report": {
            "assessment": assessment,
            "runs": budget_rows,
            "resolution_sources": sorted({item.get("decision_source") for item in budget_rows if item.get("decision_source")}),
        },
        "source_ref_audit": {
            "assessment": assessment,
            "runs": source_ref_rows,
            "item_level_source_ref_coverage_ratio": (
                sum(item["item_level_source_ref_coverage_ratio"] for item in source_ref_rows) / len(source_ref_rows)
                if source_ref_rows
                else 0.0
            ),
            "parseable_reduction_runs": sum(1 for item in source_ref_rows if item.get("parseable_json")),
            "missing_source_ref_runs": sum(
                1 for item in source_ref_rows if item.get("parseable_json") and item.get("item_level_source_ref_coverage_ratio", 0.0) < 1.0
            ),
        },
        "truncation_audit": {
            "assessment": assessment,
            "events": truncation_rows,
            "triggered_continuation_count": sum(1 for item in truncation_rows if item.get("continuation_status", "not_triggered") != "not_triggered"),
            "continuation_problem_count": sum(
                1 for item in truncation_rows if item.get("continuation_status") in {"executed_but_not_parseable", "skipped_cap_reached"}
            ),
        },
        "decision": decision,
    }


def _source_ref_audit_row(*, result: dict[str, Any], parsed: dict[str, Any] | None) -> dict[str, Any]:
    section_totals = {section: {"items": 0, "with_source_refs": 0} for section in ("characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions")}
    if not isinstance(parsed, dict):
        return {
            "run_id": result["run_id"],
            "model": result["model"],
            "profile_id": result["profile_id"],
            "chapter_id": result["chapter_id"],
            "parseable_json": False,
            "item_level_source_ref_coverage_ratio": 0.0,
            "sections": section_totals,
            "missing_examples": [],
        }
    chapter = _first_chapter(parsed)
    missing_examples = []
    total = 0
    with_refs = 0
    if isinstance(chapter, dict):
        for section, audit in section_totals.items():
            for item in chapter.get(section) or []:
                if not isinstance(item, dict):
                    continue
                total += 1
                audit["items"] += 1
                refs = item.get("source_refs") or []
                if refs:
                    with_refs += 1
                    audit["with_source_refs"] += 1
                elif len(missing_examples) < 5:
                    missing_examples.append(
                        {
                            "section": section,
                            "item_label": item.get("canonical") or item.get("canonical_name") or item.get("surface") or item.get("source") or item.get("target") or "unknown",
                        }
                    )
    return {
        "run_id": result["run_id"],
        "model": result["model"],
        "profile_id": result["profile_id"],
        "chapter_id": result["chapter_id"],
        "parseable_json": True,
        "item_level_source_ref_coverage_ratio": (with_refs / total) if total else 0.0,
        "sections": section_totals,
        "missing_examples": missing_examples,
    }


def _write_blocked_reports(names: dict[str, str], plan: dict[str, Any], *, reason: str) -> None:
    pro_compact_phase = bool(plan["public_plan"].get("pro_compact_reduction_mode") and plan["public_plan"].get("patch_continuation_mode"))
    assessment = "pro_reduction_recovery_blocked" if pro_compact_phase else "real_deepseek_e2e_validation_blocked"
    base = {
        "assessment": assessment,
        "blocked_reason": reason,
        "private_packet_root": plan["public_plan"]["private_packet_root"],
        "provider_call_count": 0,
        "write_back": False,
    }
    _write_expected(names["summary"], base)
    _write_expected(names["chunk_results"], {"assessment": assessment, "chunks": []})
    _write_expected(names["reduction_summary"], {"assessment": assessment, "reductions": []})
    _write_expected(names["budget_report"], {"assessment": assessment, "runs": []})
    _write_expected(names["source_ref_audit"], {"assessment": assessment, "runs": []})
    _write_expected(names["truncation_audit"], {"assessment": assessment, "events": []})
    _write_expected(
        names["decision"],
        {
            **base,
            "next_suggested_phase": "Phase 1.3.M-b5c-4h — Compact Reduction Policy Hardening before Larger E2E"
            if pro_compact_phase
            else "Phase 1.3.M-b5c-4f — Retry Full Real DeepSeek E2E Validation after unblock",
        },
    )


def _public_run_plan(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "chapter_id": run["chapter"]["chapter_id"],
        "model": run["model"],
        "profile_id": run["profile"].profile_id,
        "planned_provider_calls": run["planned_calls"],
        "planned_continuation_reserve_calls": run["continuation_reserve"],
        "compact_reduction_mode": bool(run.get("compact_reduction_mode")),
        "patch_continuation_mode": bool(run.get("patch_continuation_mode")),
        "token_plan": run["token_plan"],
        "effective_output_budget": asdict(run["effective_output_budget"]),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "chapter_id": chunk.chapter_id,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "char_count": chunk.char_count,
                "estimated_tokens": chunk.estimated_tokens,
                "chunk_kind": chunk.chunk_kind,
                "split_reason": chunk.split_reason,
                "source_span": chunk.source_span,
            }
            for chunk in run["chunks"]
        ],
    }


def _first_chapter(payload: dict[str, Any]) -> dict[str, Any] | None:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    return chapters[0] if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict) else None


def _write_expected(name: str, payload: dict[str, Any]) -> None:
    EXPECTED_ROOT.mkdir(parents=True, exist_ok=True)
    _write_json(EXPECTED_ROOT / name, payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_progress(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _private_path_hint(path: str) -> str:
    return str(path)


def _private_chunk_plan(plan: dict[str, Any]) -> str:
    return json.dumps(plan["public_plan"], ensure_ascii=False, indent=2)


def _write_private_matrix_files(*, packet_root: Path, plan: dict[str, Any], results: list[dict[str, Any]], reports: dict[str, Any]) -> None:
    _write_private(packet_root / "README.md", "Private DeepSeek full E2E validation packet. Do not commit.\n")
    _write_private(packet_root / "compact_reduction_policy_private.md", json.dumps(build_pro_compact_reduction_policy(), ensure_ascii=False, indent=2))
    _write_private(packet_root / "patch_continuation_trace_private.md", json.dumps(build_patch_based_continuation_contract(), ensure_ascii=False, indent=2))
    _write_private(packet_root / "matrix_summary_private.md", json.dumps(reports["summary"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "matrix_comparison_private.md", json.dumps(reports["decision"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "decision_notes_private.md", json.dumps(reports["decision"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "source_ref_audit_private.md", json.dumps(reports["source_ref_audit"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "truncation_recovery_audit_private.md", json.dumps(reports["truncation_audit"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "reduction_trace_private.md", json.dumps(reports["reduction_summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
