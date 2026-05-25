from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
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
from textifai.import_review.deepseek_family_profiles import build_deepseek_budget_bridge, get_deepseek_family_profile, build_thin_output_warnings
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.provider_prompt_profiles import apply_provider_prompt_profile
from textifai.import_review.structured_bootstrap_v1 import (
    CHAPTER_PARTIAL_EXTRACTION_PROMPT,
    CHAPTER_REDUCTION_PROMPT,
    _extract_title_entity_hints,
    _extract_title_parse_signals,
    _estimate_token_count,
)
from textifai.import_review.token_budget import TokenPlanningRequest, build_token_budget_from_planning_request
from textifai.import_review.prompt_experiment_observability import classify_failure_mode

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
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--plan-only", action="store_true")
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
    expected_chapter_ids = [item.strip() for item in args.chapter_ids.split(",") if item.strip()]
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    chapters = _detect_target_chapters(source_path, source_text, expected_chapter_ids)
    plan = _build_execution_plan(
        source_path=source_path,
        source_text=source_text,
        chapters=chapters,
        models=models,
        packet_root=packet_root,
        max_output_tokens=args.max_output_tokens,
    )
    _write_expected("real_deepseek_e2e_execution_plan_after_sp074.json", plan["public_plan"])
    _write_private(packet_root / "chunk_plan_private.md", _private_chunk_plan(plan))
    if plan["public_plan"]["planned_provider_call_count"] > args.max_provider_requests:
        _write_blocked_reports(plan, reason="planned_provider_call_count_exceeds_cap")
        return 2
    if args.plan_only:
        _write_blocked_reports(plan, reason="plan_only")
        return 0
    if not args.allow_provider_calls:
        _write_blocked_reports(plan, reason="missing_allow_provider_calls")
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        _write_blocked_reports(plan, reason="missing_deepseek_api_key")
        return 2
    config_error = get_text_provider_config_error(task_name=TASK, provider_name="deepseek")
    if config_error is not None:
        _write_blocked_reports(plan, reason=f"provider_config_error:{config_error}")
        return 2

    provider = get_text_provider(provider_name="deepseek")
    results = []
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
            response_format_json=args.response_format_json,
            max_output_tokens=args.max_output_tokens,
        )
        call_index += used_calls
        results.append(run_result)
    reports = _build_public_reports(plan=plan, results=results, packet_root=packet_root)
    for name, payload in reports.items():
        _write_expected(name, payload)
    _write_private_matrix_files(packet_root=packet_root, plan=plan, results=results, reports=reports)
    return 0


def _detect_target_chapters(source_path: Path, source_text: str, chapter_ids: list[str]) -> list[dict[str, Any]]:
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
    out = []
    for index, chapter in enumerate(detected, start=1):
        chapter_id = f"ch_{index:03d}"
        if chapter_id in wanted:
            out.append({"chapter_id": chapter_id, "sequence_index": index, "detected": chapter, "source_id": record.source_id})
    missing = sorted(wanted - {item["chapter_id"] for item in out})
    if missing:
        raise SystemExit(f"missing target chapters: {missing}")
    return out


def _build_execution_plan(*, source_path: Path, source_text: str, chapters: list[dict[str, Any]], models: list[str], packet_root: Path, max_output_tokens: int) -> dict[str, Any]:
    source_hash = hashlib.sha256(source_text.encode("utf-8", errors="replace")).hexdigest()
    runs = []
    public_runs = []
    call_count = 0
    for chapter in chapters:
        detected = chapter["detected"]
        for model in models:
            profile = get_deepseek_family_profile(model)
            if profile is None:
                continue
            caps = get_model_capabilities(model)
            planning = TokenPlanningRequest(
                provider="deepseek",
                model=model,
                task=TASK,
                provider_profile_id=profile.profile_id,
                max_output_tokens=max_output_tokens,
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
            run = {"run_id": run_id, "chapter": chapter, "model": model, "profile": profile, "token_plan": token_plan, "chunks": chunks, "planned_calls": planned_calls}
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
            "provider_call_cap": 24,
            "private_packet_root": str(packet_root),
            "write_back": False,
        },
        "budget_bridge": build_deepseek_budget_bridge(),
    }


def _execute_run(*, provider: Any, run: dict[str, Any], packet_root: Path, progress_path: Path, call_index_start: int, total_calls: int, response_format_json: bool, max_output_tokens: int) -> tuple[dict[str, Any], int]:
    run_dir = packet_root / run["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    partial_payloads = []
    chunk_results = []
    calls = 0
    for chunk in run["chunks"]:
        calls += 1
        call_no = call_index_start + calls
        print(f"run {call_no}/{total_calls} model={run['model']} chapter={run['chapter']['chapter_id']} chunk={chunk.chunk_id} profile={run['profile'].profile_id}", flush=True)
        result = _call_chunk(provider=provider, run=run, chunk=chunk, run_dir=run_dir, call_no=call_no, total_calls=total_calls, response_format_json=response_format_json, max_output_tokens=max_output_tokens, progress_path=progress_path)
        chunk_results.append(result)
        if isinstance(result.get("parsed"), dict):
            partial_payloads.append(result["parsed"])
    calls += 1
    call_no = call_index_start + calls
    print(f"run {call_no}/{total_calls} model={run['model']} chapter={run['chapter']['chapter_id']} chunk=reduction profile={run['profile'].profile_id}", flush=True)
    reduction = _call_reduction(provider=provider, run=run, partial_payloads=partial_payloads, run_dir=run_dir, call_no=call_no, total_calls=total_calls, response_format_json=response_format_json, max_output_tokens=max_output_tokens, progress_path=progress_path)
    manifest = {"run_id": run["run_id"], "model": run["model"], "profile_id": run["profile"].profile_id, "chapter_id": run["chapter"]["chapter_id"], "chunk_count": len(run["chunks"]), "provider_call_count": calls, "status": "completed", "write_back": False}
    _write_json(run_dir / "run_manifest.json", manifest)
    return {"run_id": run["run_id"], "model": run["model"], "profile_id": run["profile"].profile_id, "chapter_id": run["chapter"]["chapter_id"], "chunks": chunk_results, "reduction": reduction, "provider_call_count": calls}, calls


def _call_chunk(*, provider: Any, run: dict[str, Any], chunk: StructuredSourceChunk, run_dir: Path, call_no: int, total_calls: int, response_format_json: bool, max_output_tokens: int, progress_path: Path) -> dict[str, Any]:
    detected = run["chapter"]["detected"]
    title_hints = _extract_title_entity_hints(detected.title)
    title_signals = _extract_title_parse_signals(detected.title)
    prompt = (
        f"{CHAPTER_PARTIAL_EXTRACTION_PROMPT}\n\n"
        f"WORK_TITLE: {Path(run['chapter']['detected'].source_path).stem if hasattr(run['chapter']['detected'], 'source_path') else '王者の杖'}\n"
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
    return _execute_request(provider=provider, run=run, run_dir=run_dir, stem=chunk.chunk_id, system=system, user=user, mode="chapter_partial_extraction", chunk=chunk, call_no=call_no, total_calls=total_calls, response_format_json=response_format_json, max_output_tokens=max_output_tokens, progress_path=progress_path)


def _call_reduction(*, provider: Any, run: dict[str, Any], partial_payloads: list[dict[str, Any]], run_dir: Path, call_no: int, total_calls: int, response_format_json: bool, max_output_tokens: int, progress_path: Path) -> dict[str, Any]:
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
    return _execute_request(provider=provider, run=run, run_dir=run_dir, stem="reduction", system=system, user=user, mode="chapter_reduction", chunk=None, call_no=call_no, total_calls=total_calls, response_format_json=response_format_json, max_output_tokens=max_output_tokens, progress_path=progress_path)


def _execute_request(*, provider: Any, run: dict[str, Any], run_dir: Path, stem: str, system: str, user: str, mode: str, chunk: StructuredSourceChunk | None, call_no: int, total_calls: int, response_format_json: bool, max_output_tokens: int, progress_path: Path) -> dict[str, Any]:
    started = datetime.now(UTC)
    _append_progress(progress_path, {"run_index": call_no, "run_total": total_calls, "started_at": started.isoformat(), "model": run["model"], "chapter": run["chapter"]["chapter_id"], "chunk_id": stem, "status": "started"})
    call_dir = run_dir / stem
    call_dir.mkdir(parents=True, exist_ok=True)
    _write_private(call_dir / "system_prompt.md", system)
    _write_private(call_dir / "user_prompt.md", user)
    _write_private(call_dir / "final_prompt_sent.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    _write_private(call_dir / "provider_profile_or_overlay.md", run["profile"].prompt_overlay)
    request_payload = {"model": run["model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": max_output_tokens, "temperature": 0.1, "response_format": {"type": "json_object"} if response_format_json else None, "headers": {"Authorization": "<redacted>"}}
    _write_json(call_dir / "provider_request_payload.redacted.json", request_payload)
    started_perf = time.perf_counter()
    parsed = None
    error = None
    response_text = ""
    try:
        response = provider.generate(TextGenerationRequest(task=TASK, provider_name="deepseek", model=run["model"], system=system, messages=[TextMessage(role="user", content=user)], max_tokens=max_output_tokens, temperature=0.1, timeout_seconds=180, retries=1, response_format={"type": "json_object"} if response_format_json else None))
        response_text = response.text or ""
        _write_private(call_dir / "provider_response_raw.txt", response_text)
        parsed = extract_json_payload(response_text)
        if isinstance(parsed, dict):
            _write_json(call_dir / "provider_response_parsed.json", parsed)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        _write_private(call_dir / "provider_response_raw.txt", response_text)
    duration = time.perf_counter() - started_perf
    parseable = isinstance(parsed, dict)
    validation = _validation_report(parsed=parsed, expected_chapter_id=run["chapter"]["chapter_id"], mode=mode, chunk=chunk, response_text=response_text, error=error)
    failure_mode = _failure_mode(validation)
    _write_json(call_dir / "validation_report.json", validation)
    _write_json(call_dir / "failure_mode_report.json", {"failure_mode": failure_mode, "validation_ok": validation["validation_ok"], "parseable_json": parseable})
    _write_json(call_dir / "variant_diff_and_hypothesis.json", {"profile_id": run["profile"].profile_id, "hypothesis": "SP070 profile plus SP074 structured chunk metadata improves chunked extraction traceability.", "prompt_change_type": ["structured_chunk_metadata", "provider_profile", "budget_bridge"]})
    _write_private(call_dir / "codex_interpretation.md", f"mode={mode}\nparseable_json={parseable}\nvalidation_ok={validation['validation_ok']}\nfailure_mode={failure_mode}\n")
    finished = datetime.now(UTC)
    size = (call_dir / "provider_response_raw.txt").stat().st_size if (call_dir / "provider_response_raw.txt").exists() else 0
    _append_progress(progress_path, {"run_index": call_no, "run_total": total_calls, "started_at": started.isoformat(), "last_output_activity_at": finished.isoformat(), "finished_at": finished.isoformat(), "duration_seconds": duration, "output_file_size_bytes": size, "model": run["model"], "chapter": run["chapter"]["chapter_id"], "chunk_id": stem, "status": "finished", "failure_mode": failure_mode})
    return {"mode": mode, "chunk_id": stem, "parseable_json": parseable, "validation_ok": validation["validation_ok"], "failure_mode": failure_mode, "counts": validation["counts"], "score": validation["score"], "thin_warnings": validation["thin_warnings"], "source_span": chunk.source_span if chunk else None, "parsed": parsed if isinstance(parsed, dict) else None, "private_dir": str(call_dir)}


def _validation_report(*, parsed: Any, expected_chapter_id: str, mode: str, chunk: StructuredSourceChunk | None, response_text: str, error: str | None) -> dict[str, Any]:
    counts = {"characters": 0, "places": 0, "concepts": 0, "objects": 0, "events": 0, "relations": 0, "unresolved_mentions": 0}
    chapter_ok = False
    relation_category_present = False
    event_importance_present = False
    if isinstance(parsed, dict):
        if mode == "chapter_partial_extraction":
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
    thin = build_thin_output_warnings({"score": score, "counts": counts, "response_text_chars": len(response_text), "validation_ok": chapter_ok, "response_parseable_json": isinstance(parsed, dict)})
    return {"validation_ok": isinstance(parsed, dict) and chapter_ok and error is None, "parseable_json": isinstance(parsed, dict), "expected_chapter_id": expected_chapter_id, "chapter_id_ok": chapter_ok, "error": error, "counts": counts, "score": score, "event_importance_present": event_importance_present, "relation_category_present": relation_category_present, "response_text_chars": len(response_text), "thin_warnings": thin["warnings"], "source_span_preserved": bool(chunk.source_span) if chunk else True}


def _failure_mode(validation: dict[str, Any]) -> str | None:
    if validation.get("validation_ok"):
        return None
    error = str(validation.get("error") or "").casefold()
    if "textprovidererror" in error or "http" in error or "unauthorized" in error:
        return "provider_error"
    if not validation.get("parseable_json"):
        return "invalid_json_unknown"
    if not validation.get("chapter_id_ok"):
        return "valid_json_wrong_chapter"
    if validation.get("score", 0) < 20:
        return "valid_json_thin"
    return "validation_failed_missing_required_sections"


def _score(counts: dict[str, int], event_importance: bool, relation_category: bool, chars: int, chapter_ok: bool) -> float:
    score = counts["characters"] + counts["places"] + counts["concepts"] + counts["objects"] * 1.5 + counts["events"] * 1.5 + counts["relations"] * 2 + counts["unresolved_mentions"]
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
    chunk_rows = []
    reduction_rows = []
    for result in results:
        for chunk in result["chunks"]:
            row = {key: result[key] for key in ("run_id", "model", "profile_id", "chapter_id")}
            row.update({k: v for k, v in chunk.items() if k not in {"parsed", "private_dir"}})
            row["private_dir"] = _private_path_hint(chunk["private_dir"])
            chunk_rows.append(row)
        red = {key: result[key] for key in ("run_id", "model", "profile_id", "chapter_id")}
        red.update({k: v for k, v in result["reduction"].items() if k not in {"parsed", "private_dir"}})
        red["private_dir"] = _private_path_hint(result["reduction"]["private_dir"])
        reduction_rows.append(red)
    valid_reductions = [row for row in reduction_rows if row["parseable_json"] and row["validation_ok"]]
    source_ref_preservation = all(_chapter_has_source_refs(result.get("reduction", {}).get("parsed")) for result in results if isinstance(result.get("reduction", {}).get("parsed"), dict))
    if valid_reductions and source_ref_preservation:
        assessment = "real_deepseek_e2e_dryrun_passed_with_review_warnings"
    elif valid_reductions:
        assessment = "real_deepseek_e2e_dryrun_partial_success"
    elif any(row["parseable_json"] for row in reduction_rows + chunk_rows):
        assessment = "real_deepseek_e2e_dryrun_partial_success"
    else:
        assessment = "real_deepseek_e2e_dryrun_failed_but_debuggable"
    summary = {
        "assessment": assessment,
        "provider": "deepseek",
        "models": plan["public_plan"]["models"],
        "chapters": plan["public_plan"]["chapters"],
        "provider_call_count": sum(item["provider_call_count"] for item in results),
        "private_packet_root": str(packet_root),
        "recommended_files_to_upload_to_chatgpt": [
            "README.md",
            "matrix_summary_private.md",
            "matrix_comparison_private.md",
            "decision_notes_private.md",
            "chunk_plan_private.md",
            "reduction_trace_private.md",
        ],
        "comparison_vs_previous_non_chunked_runs": {
            "sp069_best_ch002_score": 26.5,
            "sp069_best_ch003_score": 25.0,
            "sp075_best_reduction_score": max((row.get("score", -999) for row in reduction_rows), default=-999),
            "chunked_input_shape_tested": True,
        },
        "write_back": False,
    }
    decision = {
        "assessment": assessment,
        "ready_for_larger_real_e2e": assessment == "real_deepseek_e2e_dryrun_passed_with_review_warnings",
        "needs_review_warnings": True,
        "private_packet_root": str(packet_root),
        "next_suggested_phase": "Phase 1.3.M-b5c-4e — Review Real DeepSeek E2E Packet and Decide Larger Dry-run",
    }
    return {
        "real_deepseek_e2e_summary_after_sp074.json": summary,
        "real_deepseek_e2e_chunk_results_after_sp074.json": {"assessment": assessment, "chunks": chunk_rows},
        "real_deepseek_e2e_reduction_summary_after_sp074.json": {
            "assessment": assessment,
            "reductions": reduction_rows,
            "source_ref_preservation": source_ref_preservation,
        },
        "real_deepseek_e2e_decision_after_sp074.json": decision,
    }


def _write_blocked_reports(plan: dict[str, Any], *, reason: str) -> None:
    assessment = "real_deepseek_e2e_dryrun_blocked"
    base = {"assessment": assessment, "blocked_reason": reason, "private_packet_root": plan["public_plan"]["private_packet_root"], "provider_call_count": 0, "write_back": False}
    _write_expected("real_deepseek_e2e_summary_after_sp074.json", base)
    _write_expected("real_deepseek_e2e_chunk_results_after_sp074.json", {"assessment": assessment, "chunks": []})
    _write_expected("real_deepseek_e2e_reduction_summary_after_sp074.json", {"assessment": assessment, "reductions": []})
    _write_expected("real_deepseek_e2e_decision_after_sp074.json", {**base, "next_suggested_phase": "Phase 1.3.M-b5c-4d — Retry Real DeepSeek E2E Dry-run after unblock"})


def _public_run_plan(run: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": run["run_id"], "chapter_id": run["chapter"]["chapter_id"], "model": run["model"], "profile_id": run["profile"].profile_id, "planned_provider_calls": run["planned_calls"], "token_plan": run["token_plan"], "chunks": [{"chunk_id": chunk.chunk_id, "chapter_id": chunk.chapter_id, "char_start": chunk.char_start, "char_end": chunk.char_end, "char_count": chunk.char_count, "estimated_tokens": chunk.estimated_tokens, "chunk_kind": chunk.chunk_kind, "split_reason": chunk.split_reason, "source_span": chunk.source_span} for chunk in run["chunks"]]}


def _first_chapter(payload: dict[str, Any]) -> dict[str, Any] | None:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    return chapters[0] if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict) else None


def _chapter_has_source_refs(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    chapter = _first_chapter(payload)
    if not isinstance(chapter, dict):
        return False
    for section in ("characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"):
        for item in chapter.get(section) or []:
            if isinstance(item, dict) and (item.get("source_refs") or item.get("source_spans")):
                return True
    return False


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
    _write_private(packet_root / "README.md", "Private DeepSeek E2E packet. Do not commit. Start with matrix_summary_private.md and decision_notes_private.md.\n")
    _write_private(packet_root / "matrix_summary_private.md", json.dumps(reports["real_deepseek_e2e_summary_after_sp074.json"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "matrix_comparison_private.md", "Compare SP070 non-chunked baselines with SP075 chunked E2E outputs in per-run folders.\n")
    _write_private(packet_root / "decision_notes_private.md", json.dumps(reports["real_deepseek_e2e_decision_after_sp074.json"], ensure_ascii=False, indent=2))
    _write_private(packet_root / "reduction_trace_private.md", json.dumps(reports["real_deepseek_e2e_reduction_summary_after_sp074.json"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
