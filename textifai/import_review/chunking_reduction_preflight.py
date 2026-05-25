from __future__ import annotations

from copy import deepcopy
from typing import Any

from textifai.import_review.batch_planner import (
    NaturalChunkingThresholdPolicy,
    StructuredSourceChunk,
    build_default_natural_chunking_threshold_policy,
    choose_natural_chunking_split,
)

CRITICAL_SECTIONS = ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]
WRITER_OUTCOME_STATUSES = ["success", "success_with_warnings", "success_with_retry_available", "partial_failure", "failed"]
WRITER_CHAPTER_STATUSES = ["ready", "ready_with_warnings", "needs_retry", "needs_review", "failed"]
WRITER_REASON_LABELS = [
    "analysis_incomplete",
    "temporary_model_error",
    "chapter_needs_second_pass",
    "chapter_processed_with_warnings",
    "manual_review_recommended",
]


def reduce_mock_chunk_partials(
    *,
    chunks: list[StructuredSourceChunk],
    partials: list[dict[str, Any]],
    chapter_id: str,
    work_title: str = "Synthetic Work",
) -> dict[str, Any]:
    merged = {
        "work": {"title": work_title},
        "chapters": [
            {
                "chapter_id": chapter_id,
                "characters": [],
                "places": [],
                "concepts": [],
                "objects": [],
                "events": [],
                "relations": [],
                "unresolved_mentions": [],
                "chunk_audit": [],
                "reduction_warnings": [],
            }
        ],
    }
    chapter = merged["chapters"][0]
    chunk_index = {chunk.chunk_id: chunk for chunk in chunks}
    seen_keys: dict[str, set[str]] = {section: set() for section in CRITICAL_SECTIONS}
    item_index: dict[str, dict[str, dict[str, Any]]] = {section: {} for section in CRITICAL_SECTIONS}

    for partial in partials:
        chunk_id = str(partial.get("chunk_id") or "")
        chunk = chunk_index.get(chunk_id)
        audit = {
            "chunk_id": chunk_id,
            "status": partial.get("status") or ("ok" if partial.get("payload") else "invalid_partial"),
            "failure_mode": partial.get("failure_mode"),
            "source_span": chunk.source_span if chunk else None,
        }
        chapter["chunk_audit"].append(audit)
        payload = partial.get("payload")
        if not isinstance(payload, dict):
            chapter["reduction_warnings"].append({"chunk_id": chunk_id, "warning": "partial_missing_payload"})
            continue
        partial_chapter = _first_chapter(payload)
        if not isinstance(partial_chapter, dict):
            chapter["reduction_warnings"].append({"chunk_id": chunk_id, "warning": "partial_missing_chapter"})
            continue
        for section in CRITICAL_SECTIONS:
            for item in partial_chapter.get(section) or []:
                normalized = _normalize_item(item, chunk=chunk)
                key = _dedupe_key(section=section, item=normalized)
                if key in seen_keys[section]:
                    existing = item_index[section].get(key)
                    if existing is not None:
                        existing["source_refs"] = _merge_source_refs(existing.get("source_refs") or [], normalized.get("source_refs") or [])
                    if section in {"objects", "events", "relations"}:
                        if existing is not None:
                            existing.setdefault("review_state", normalized.get("review_state") or "needs_review")
                            existing.setdefault("review_reason", normalized.get("review_reason") or "duplicate_across_chunk_partials")
                        else:
                            normalized.setdefault("review_state", "needs_review")
                            normalized.setdefault("review_reason", "duplicate_across_chunk_partials")
                    else:
                        continue
                if key not in seen_keys[section]:
                    seen_keys[section].add(key)
                    chapter[section].append(normalized)
                    item_index[section][key] = normalized
    return merged


def build_provider_free_chunking_reduction_fixture_report(result: dict[str, Any]) -> dict[str, Any]:
    chapter = _first_chapter(result) or {}
    chunk_audit = list(chapter.get("chunk_audit") or [])
    return {
        "assessment": "chunking_reduction_gaps_closed_for_provider_free_e2e",
        "partial_count": len(chunk_audit),
        "valid_partial_count": sum(1 for item in chunk_audit if item.get("status") == "ok"),
        "invalid_partial_count": sum(1 for item in chunk_audit if item.get("status") != "ok"),
        "final_counts": {section: len(chapter.get(section) or []) for section in CRITICAL_SECTIONS},
        "source_span_preservation": all(bool(item.get("source_span")) for item in chunk_audit if item.get("status") == "ok"),
        "review_state_preserved": any(bool(item.get("review_state")) for item in chapter.get("objects") or []) or any(
            bool(item.get("review_state")) for item in chapter.get("events") or []
        ),
        "warnings": list(chapter.get("reduction_warnings") or []),
    }


def build_private_decision_packet_contract() -> dict[str, Any]:
    return {
        "root_location": "/tmp/textifai_private_provider_runs/<matrix_or_run_id>",
        "per_run_files": [
            "run_manifest.json",
            "final_prompt_sent.md",
            "system_prompt.md",
            "user_prompt.md",
            "provider_profile_or_overlay.md",
            "provider_request_payload.redacted.json",
            "provider_response_raw.txt",
            "provider_response_parsed.json",
            "validation_report.json",
            "failure_mode_report.json",
            "variant_diff_and_hypothesis.json",
            "codex_interpretation.md",
        ],
        "per_matrix_files": [
            "matrix_summary_private.md",
            "matrix_comparison_private.md",
            "decision_notes_private.md",
            "README.md",
        ],
        "privacy_rules": {
            "commit_allowed": False,
            "copy_to_desktop_allowed": False,
            "api_key_inclusion_allowed": False,
            "authorization_header_policy": "redact",
            "handoff_must_include_root_path": True,
            "handoff_must_list_priority_files": True,
            "handoff_must_summarize_without_opening_every_file": True,
        },
    }


def build_long_provider_run_contract() -> dict[str, Any]:
    return {
        "progress_log": {
            "required_fields": [
                "run_index",
                "run_total",
                "started_at",
                "last_output_activity_at",
                "finished_at",
                "output_file_size_bytes",
                "status",
            ],
            "incremental": True,
        },
        "timeout_policy": {
            "stall_detection_required": True,
            "stall_detection_rule": "flag if no output activity beyond configured inactivity timeout",
            "timeout_action": "write cancellation report before aborting",
        },
        "cancellation_rules": {
            "manual_cancel_supported": True,
            "cancel_on_stall_supported": True,
            "cancellation_report_fields": [
                "run_index",
                "run_total",
                "cancelled_at",
                "reason",
                "last_output_activity_at",
                "output_file_size_bytes",
            ],
        },
    }


def _first_chapter(payload: dict[str, Any]) -> dict[str, Any] | None:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if isinstance(chapters, list) and chapters:
        chapter = chapters[0]
        if isinstance(chapter, dict):
            return chapter
    return None


def _normalize_item(item: dict[str, Any], *, chunk: StructuredSourceChunk | None) -> dict[str, Any]:
    normalized = deepcopy(item)
    source_refs = list(normalized.get("source_refs") or normalized.get("source_spans") or [])
    if chunk is not None:
        source_refs = _merge_source_refs(source_refs, [_fallback_chunk_source_ref(chunk)])
    normalized["source_refs"] = source_refs
    return normalized

def build_source_ref_carry_forward_report() -> dict[str, Any]:
    return {
        "assessment": "source_refs_and_output_budget_protocol_ready",
        "rules": {
            "preserve_partial_source_refs": True,
            "fallback_to_chunk_span_when_missing": True,
            "merge_multiple_chunk_refs_without_duplicates": True,
            "do_not_invent_item_level_spans_beyond_chunk_span": True,
            "preserve_review_state": True,
        },
        "applies_to_sections": list(CRITICAL_SECTIONS),
    }

def build_natural_chunking_policy_report() -> dict[str, Any]:
    base = build_default_natural_chunking_threshold_policy(hard_max_source_tokens=6000)
    deepseek_flash = build_default_natural_chunking_threshold_policy(
        hard_max_source_tokens=6000,
        provider_chunking_preferences={"soft_chunk_target_tokens": 1200, "soft_chunk_max_tokens": 1800},
    )
    deepseek_pro = build_default_natural_chunking_threshold_policy(
        hard_max_source_tokens=6000,
        provider_chunking_preferences={"soft_chunk_target_tokens": 1100, "soft_chunk_max_tokens": 1700},
    )
    return {
        "assessment": "natural_chunking_threshold_patch_ready_for_e2e",
        "general_provider_agnostic_defaults": base.to_dict(),
        "deepseek_suggested_overrides": {
            "deepseek-v4-flash": {**deepseek_flash.to_dict(), "compact_reduction_recommended": False},
            "deepseek-v4-pro": {**deepseek_pro.to_dict(), "compact_reduction_recommended": True},
        },
        "overlap_policy": {"preferred_overlap_paragraphs": base.preferred_overlap_paragraphs, "preferred_overlap_tokens": None},
        "split_reasons": [
            "chapter_within_budget",
            "soft_quality_split",
            "hard_budget_split",
            "heading_boundary_split",
            "paragraph_boundary_split",
        ],
        "default_change_status": "product-default-change",
        "justification": "split earlier for ingestion quality and reduction robustness, not only hard context fit",
    }

def build_patch_continuation_chapter_validation_report() -> dict[str, Any]:
    return {
        "assessment": "natural_chunking_threshold_patch_ready_for_e2e",
        "rules": {
            "patch_chapter_id_must_match_expected": True,
            "continuation_for_chapter_must_match_expected": True,
            "chunk_ids_must_belong_to_expected_chapter": True,
            "reject_valid_json_wrong_chapter": True,
            "merge_block_on_mismatch": True,
        },
        "failure_mode": "valid_json_wrong_chapter",
    }

def validate_patch_continuation_chapter(
    *,
    expected_chapter_id: str,
    patch_payload: dict[str, Any],
    expected_chunk_ids: list[str] | None = None,
) -> dict[str, Any]:
    expected_chunks = set(expected_chunk_ids or [])
    metadata = patch_payload.get("patch_metadata") if isinstance(patch_payload, dict) else None
    continuation_for = patch_payload.get("continuation_for") if isinstance(patch_payload, dict) else None
    chapter_ids: set[str] = set()
    chunk_ids: set[str] = set()

    def _collect(value: Any) -> None:
        if isinstance(value, dict):
            chapter_id = value.get("chapter_id")
            if chapter_id:
                chapter_ids.add(str(chapter_id))
            chunk_id = value.get("chunk_id")
            if chunk_id:
                chunk_ids.add(str(chunk_id))
            refs = value.get("source_refs")
            if isinstance(refs, list):
                for ref in refs:
                    _collect(ref)
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    _collect(nested)
        elif isinstance(value, list):
            for item in value:
                _collect(item)

    _collect(patch_payload.get("continuation_patch") if isinstance(patch_payload, dict) else None)
    _collect(metadata)
    _collect(continuation_for)

    metadata_chapter = None
    if isinstance(metadata, dict):
        metadata_chapter = metadata.get("chapter_id") or metadata.get("continues_from_chapter_id")
    continuation_for_chapter = continuation_for.get("chapter_id") if isinstance(continuation_for, dict) else None
    chapter_mismatch = any(ch != expected_chapter_id for ch in chapter_ids if ch)
    metadata_mismatch = bool(metadata_chapter and metadata_chapter != expected_chapter_id)
    continuation_for_mismatch = bool(continuation_for_chapter and continuation_for_chapter != expected_chapter_id)
    chunk_mismatch = bool(expected_chunks and any(not chunk_id.startswith(f"source_") and chunk_id not in expected_chunks for chunk_id in chunk_ids))
    # allow regular expected chunk ids; also reject explicit foreign chapter id in chunk id shape
    foreign_chapter_chunk = any(f"_{expected_chapter_id}_" not in chunk_id and "_ch_" in chunk_id for chunk_id in chunk_ids)
    valid = not any((chapter_mismatch, metadata_mismatch, continuation_for_mismatch, chunk_mismatch, foreign_chapter_chunk))
    return {
        "valid": valid,
        "failure_mode": None if valid else "valid_json_wrong_chapter",
        "expected_chapter_id": expected_chapter_id,
        "chapter_ids_seen": sorted(chapter_ids),
        "chunk_ids_seen": sorted(chunk_ids),
        "metadata_chapter_id": metadata_chapter,
        "continuation_for_chapter_id": continuation_for_chapter,
    }

def build_thin_reduction_diagnostics(*, parsed: dict[str, Any] | None) -> dict[str, Any]:
    section_counts = {section: 0 for section in CRITICAL_SECTIONS}
    chapter = _first_chapter(parsed) if isinstance(parsed, dict) else None
    if isinstance(chapter, dict):
        for section in CRITICAL_SECTIONS:
            value = chapter.get(section)
            section_counts[section] = len(value) if isinstance(value, list) else 0
    critical_empty = [section for section, count in section_counts.items() if section in {"objects", "events", "relations"} and count == 0]
    total_items = sum(section_counts.values())
    warnings: list[str] = []
    if total_items == 0:
        warnings.append("valid_reduction_no_items")
    if critical_empty:
        warnings.append("valid_reduction_thin_sections")
    if total_items == 0 or critical_empty:
        warnings.append("source_ref_coverage_lower_due_no_items")
    return {
        "assessment": "natural_chunking_threshold_patch_ready_for_e2e",
        "section_item_counts": section_counts,
        "empty_critical_sections": critical_empty,
        "total_items": total_items,
        "no_item_reduction": total_items == 0,
        "source_ref_coverage_denominator_explanation": "coverage ratio uses extracted item count; no-item reductions lower coverage without proving missing refs",
        "warnings": warnings,
    }

def build_natural_chunking_calibration_report(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    soft_target = 1200
    soft_max = 1800
    calibration_rows = []
    for row in rows:
        estimated_tokens = int(row.get("estimated_tokens") or 0)
        would_two = estimated_tokens > soft_max
        calibration_rows.append(
            {
                "chapter_id": row.get("chapter_id"),
                "model": row.get("model"),
                "estimated_tokens": estimated_tokens,
                "old_natural_chunk_count": row.get("natural_chunk_count"),
                "threshold_for_2_chunks": (estimated_tokens // 2) + 1 if estimated_tokens else None,
                "threshold_for_3_chunks": (estimated_tokens // 3) + 1 if estimated_tokens else None,
                "would_soft_split_under_proposed_policy": would_two,
            }
        )
    return {
        "assessment": "natural_chunking_threshold_patch_ready_with_review_warnings",
        "why_all_rows_were_single_chunk": "current natural budget tracks hard fit only; selected chapters stayed far below usable input budget",
        "proposed_soft_thresholds": {
            "soft_chunk_target_tokens": soft_target,
            "soft_chunk_max_tokens": soft_max,
            "min_chunk_tokens": 450,
        },
        "risk_of_over_splitting": "medium if chapters cluster near 1800 tokens; mitigated by min_chunk_tokens",
        "risk_of_under_splitting": "high under current hard-fit-only behavior for full-novel readiness",
        "validation_candidate_chapters": sorted({row.get("chapter_id") for row in calibration_rows if row.get("would_soft_split_under_proposed_policy")}),
        "rows": calibration_rows,
    }

def build_natural_chunking_replan_simulation(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_chapter: dict[str, dict[str, Any]] = {}
    for row in rows:
        chapter_id = str(row.get("chapter_id"))
        estimated_tokens = int(row.get("estimated_tokens") or 0)
        old_count = int(row.get("natural_chunk_count") or 0)
        policy = build_default_natural_chunking_threshold_policy(hard_max_source_tokens=int(row.get("effective_source_text_budget_tokens") or 6000), provider_chunking_preferences={"soft_chunk_target_tokens": 1200, "soft_chunk_max_tokens": 1800})
        decision = choose_natural_chunking_split(chapter_tokens=estimated_tokens, hard_max_source_tokens=policy.hard_max_source_tokens, threshold_policy=policy)
        if decision["split_quality_reason"] == "chapter_within_budget":
            new_count = 1
        else:
            new_count = max(2, -(-estimated_tokens // policy.soft_chunk_target_tokens))
        chapter_entry = per_chapter.setdefault(chapter_id, {"chapter_id": chapter_id, "old_natural_chunk_count": old_count, "new_natural_chunk_count": new_count, "estimated_tokens": estimated_tokens, "models": []})
        chapter_entry["models"].append(row.get("model"))
    chapter_rows = list(per_chapter.values())
    flash_pro_calls = sum((item["new_natural_chunk_count"] + 1) * 2 for item in chapter_rows)
    reserve = len(chapter_rows) * 2
    return {
        "assessment": "natural_chunking_threshold_patch_ready_with_review_warnings",
        "chapters": chapter_rows,
        "estimated_call_count_flash_plus_pro": flash_pro_calls,
        "expected_continuation_reserve": reserve,
        "provider_call_cap": 64,
        "fits_cap_64": flash_pro_calls + reserve <= 64,
        "would_produce_natural_multichunk": any(item["new_natural_chunk_count"] > 1 for item in chapter_rows),
        "suggested_subset_if_over_cap": [item["chapter_id"] for item in sorted(chapter_rows, key=lambda item: item["estimated_tokens"], reverse=True)[:4]],
    }


def map_technical_signals_to_writer_status(
    *,
    final_chapter_valid: bool,
    has_internal_warnings: bool,
    has_retryable_failures: bool,
    has_semantic_thinness: bool,
    unrecoverable_failure: bool,
) -> dict[str, Any]:
    if unrecoverable_failure:
        return {
            "chapter_status": "failed",
            "reason_label": "manual_review_recommended",
            "user_message": "This chapter could not be completed and needs manual review.",
        }
    if has_retryable_failures:
        return {
            "chapter_status": "needs_retry",
            "reason_label": "chapter_needs_second_pass",
            "user_message": "This chapter needs a second pass to complete the analysis.",
        }
    if has_semantic_thinness and final_chapter_valid:
        return {
            "chapter_status": "needs_review",
            "reason_label": "manual_review_recommended",
            "user_message": "This chapter is complete but should be reviewed once before finalizing.",
        }
    if final_chapter_valid and has_internal_warnings:
        return {
            "chapter_status": "ready_with_warnings",
            "reason_label": "chapter_processed_with_warnings",
            "user_message": "This chapter is ready with minor warnings.",
        }
    if final_chapter_valid:
        return {
            "chapter_status": "ready",
            "reason_label": "analysis_incomplete",
            "user_message": "This chapter is ready.",
        }
    return {
        "chapter_status": "needs_retry",
        "reason_label": "temporary_model_error",
        "user_message": "This chapter needs another pass due to a temporary issue.",
    }


def build_writer_facing_ingestion_outcome_contract() -> dict[str, Any]:
    return {
        "assessment": "fail_only_retry_contract_ready_with_review_warnings",
        "allowed_outcome_statuses": WRITER_OUTCOME_STATUSES,
        "allowed_chapter_statuses": WRITER_CHAPTER_STATUSES,
        "allowed_reason_labels": WRITER_REASON_LABELS,
        "primary_action": {
            "label": "Retry pending chapters",
            "action_id": "retry_pending_chapters",
            "scope": "affected_chapters_only",
        },
        "secondary_action": {
            "label": "Later",
            "action_id": "dismiss",
        },
        "writer_summary_template": "X of Y chapters are ready. Z chapters need a second pass.",
    }


def build_technical_to_user_status_mapping_report() -> dict[str, Any]:
    return {
        "assessment": "fail_only_retry_contract_ready_with_review_warnings",
        "rules": [
            {
                "rule_id": "R1",
                "technical_condition": "final reduction valid and no warnings",
                "writer_status": "ready",
                "reason_label": "analysis_incomplete",
            },
            {
                "rule_id": "R2",
                "technical_condition": "final reduction valid and graph usable with warnings",
                "writer_status": "ready_with_warnings",
                "reason_label": "chapter_processed_with_warnings",
            },
            {
                "rule_id": "R3",
                "technical_condition": "retryable failure or low-density output",
                "writer_status": "needs_retry",
                "reason_label": "chapter_needs_second_pass",
            },
            {
                "rule_id": "R4",
                "technical_condition": "valid output with suspicious semantic thinness",
                "writer_status": "needs_review",
                "reason_label": "manual_review_recommended",
            },
            {
                "rule_id": "R5",
                "technical_condition": "unrecoverable technical failure",
                "writer_status": "failed",
                "reason_label": "manual_review_recommended",
            },
        ],
        "user_output_hides_internal_signals": True,
    }


def build_fail_only_retry_contract(
    *,
    summary_report: dict[str, Any],
    internal_rerun_report: dict[str, Any],
    user_outcome_report: dict[str, Any],
    retry_cap: int = 24,
) -> dict[str, Any]:
    outcome = user_outcome_report.get("user_ingestion_outcome") if isinstance(user_outcome_report, dict) else {}
    all_chapters = sorted({item.get("chapter_id") for item in outcome.get("affected_chapters", []) if isinstance(item, dict)})
    retryable_chapters = sorted(set(internal_rerun_report.get("retryable_chapters") or []))
    warning_chapters = sorted(set(internal_rerun_report.get("warning_chapters") or []))
    successful_chapters = sorted(set(internal_rerun_report.get("successful_chapters") or []))
    if not successful_chapters and isinstance(summary_report.get("chapters"), list):
        all_from_summary = [str(item) for item in summary_report.get("chapters") if isinstance(item, str)]
        successful_chapters = sorted(set(all_from_summary) - set(retryable_chapters) - set(warning_chapters))
    retry_units: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for unit in internal_rerun_report.get("retryable_units_internal") or []:
        if not isinstance(unit, dict):
            continue
        chapter_id = str(unit.get("chapter_id") or "")
        if chapter_id not in retryable_chapters:
            continue
        key = (
            chapter_id,
            str(unit.get("run_id") or ""),
            str(unit.get("technical_unit_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        retry_units.append(unit)
    expected_calls = sum(int(unit.get("expected_provider_calls") or 0) for unit in retry_units)
    return {
        "assessment": "fail_only_retry_contract_ready_with_review_warnings",
        "ingestion_run_id": internal_rerun_report.get("dryrun_id") or internal_rerun_report.get("ingestion_run_id"),
        "total_chapters": int(outcome.get("total_chapters") or len(successful_chapters) + len(warning_chapters) + len(retryable_chapters)),
        "retryable_chapters": retryable_chapters,
        "non_retryable_chapters": sorted(set(successful_chapters + warning_chapters) - set(retryable_chapters)),
        "retryable_units_internal": retry_units,
        "dependency_policy": {
            "successful_chapters_excluded_by_default": True,
            "allow_successful_chapter_only_if_dependency_explicit": True,
            "cross_chapter_dependency_default": "none",
        },
        "expected_provider_calls": expected_calls,
        "cap_recommendation": {
            "recommended_cap": retry_cap,
            "expected_provider_calls": expected_calls,
            "within_recommended_cap": expected_calls <= retry_cap,
        },
        "safe_to_rerun_without_full_ingestion": bool(internal_rerun_report.get("safe_to_rerun_without_full_ingestion", True)),
        "graph_completion_status_before_retry": internal_rerun_report.get("graph_completion_status_internal", "complete_with_retryable_warnings"),
        "graph_completion_status_after_retry": {
            "if_all_retryable_units_recovered": "complete_ready_or_warning",
            "if_some_units_still_retryable": "complete_with_retryable_warnings",
            "if_unrecoverable_units_remain": "partial_failure",
        },
        "consolidation_rules": [
            "only retried chapters can change status after retry",
            "non-retried successful chapters remain ready or ready_with_warnings",
            "final writer outcome recomputes chapter counts and affected list",
        ],
        "successful_chapters_excluded_from_retry_scope": sorted(set(successful_chapters) - set(retryable_chapters)),
    }


def build_sp083_fail_only_rerun_execution_plan(
    *,
    source_sha256: str,
    retryable_chapters: list[str],
    excluded_chapters: list[str],
    retry_cap: int = 24,
) -> dict[str, Any]:
    per_chapter_plan = {
        "ch_106": {
            "models": [
                "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
                "deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1",
            ],
            "planned_base_calls": 8,
            "continuation_reserve": 4,
            "why": "second-pass divergences plus low-density pro result",
        },
        "ch_115": {
            "models": [
                "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
                "deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1",
            ],
            "planned_base_calls": 7,
            "continuation_reserve": 4,
            "why": "second-pass divergence plus thin low-density pro output",
        },
    }
    rows = [
        {
            "chapter_id": chapter_id,
            **per_chapter_plan.get(
                chapter_id,
                {
                    "models": ["deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1"],
                    "planned_base_calls": 4,
                    "continuation_reserve": 2,
                    "why": "chapter flagged for targeted retry",
                },
            ),
        }
        for chapter_id in retryable_chapters
    ]
    planned_base_calls = sum(int(row["planned_base_calls"]) for row in rows)
    reserve = sum(int(row["continuation_reserve"]) for row in rows)
    return {
        "assessment": "fail_only_retry_contract_ready_with_review_warnings",
        "source_sha256": source_sha256,
        "chapters_to_retry": retryable_chapters,
        "why_selected": "chapters marked needs_retry in SP-083 writer outcome",
        "chapters_excluded_because_successful": excluded_chapters,
        "model_profile_strategy": rows,
        "planned_provider_calls": planned_base_calls,
        "continuation_reserve": reserve,
        "planned_total_calls": planned_base_calls + reserve,
        "cap": retry_cap,
        "fits_cap": planned_base_calls + reserve <= retry_cap,
        "safe_to_rerun_without_full_ingestion": True,
        "expected_writer_outcome_after_retry": {
            "best_case": "4 of 4 chapters ready",
            "conservative_case": "3 of 4 chapters ready, 1 chapter needs second pass",
        },
    }


def build_controlled_full_source_dryrun_plan(
    *,
    source_sha256: str,
    estimated_chapter_count: int,
    flash_only_total_calls_with_reserve: int,
    flash_plus_pro_total_calls_with_reserve: int,
) -> dict[str, Any]:
    return {
        "assessment": "fail_only_retry_contract_ready_with_review_warnings",
        "source_sha256": source_sha256,
        "estimated_chapter_count": estimated_chapter_count,
        "chapter_selection_strategy": "process all chapters in staged batches; prioritize longest chapters early in each batch",
        "estimated_calls": {
            "flash_only_with_reserve": flash_only_total_calls_with_reserve,
            "flash_plus_pro_with_reserve": flash_plus_pro_total_calls_with_reserve,
        },
        "proposed_cap": 96,
        "continuation_reserve_policy": "reserve at least 20 percent of batch cap for continuation and patch recovery",
        "staged_execution_proposal": [
            {
                "phase": "A",
                "scope": "first 24 chapters flash-only",
                "target_cap": 96,
                "goal": "establish baseline chapter readiness and retry scope",
            },
            {
                "phase": "B",
                "scope": "next 24 chapters flash-only plus pro on flagged high-risk chapters",
                "target_cap": 96,
                "goal": "validate difficult chapters while keeping cost bounded",
            },
            {
                "phase": "C",
                "scope": "remaining chapters flash-only then fail-only retries",
                "target_cap": 96,
                "goal": "close graph completion without full rerun",
            },
        ],
        "stop_conditions": [
            "stop batch if planned calls exceed cap",
            "stop batch if continuation reserve drops below 10 percent",
            "stop before any automatic write-back",
        ],
        "fail_only_retry_after_each_phase": True,
        "cost_risk_notes": [
            "flash-only sweep is materially cheaper and faster",
            "flash+pro on all chapters is high-cost and should remain opt-in",
            "fail-only retry reduces repeated processing for ready chapters",
        ],
        "private_packet_requirements": [
            "per-call redacted payload and response artifacts",
            "phase summary with writer-facing outcome snapshot",
            "internal retry plan and consolidated outcome notes",
        ],
        "writer_facing_outcome_at_end": "X chapters ready, Y chapters need a second pass, retry pending chapters available",
    }

def _fallback_chunk_source_ref(chunk: StructuredSourceChunk) -> dict[str, Any]:
    return {
        "source_id": chunk.source_id,
        "chapter_id": chunk.chapter_id,
        "chunk_id": chunk.chunk_id,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
    }

def _merge_source_refs(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in [*existing, *incoming]:
        if not isinstance(item, dict):
            continue
        normalized = {
            "source_id": item.get("source_id"),
            "chapter_id": item.get("chapter_id"),
            "chunk_id": item.get("chunk_id"),
            "char_start": item.get("char_start"),
            "char_end": item.get("char_end"),
        }
        key = tuple(normalized.get(field) for field in ("source_id", "chapter_id", "chunk_id", "char_start", "char_end"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _dedupe_key(*, section: str, item: dict[str, Any]) -> str:
    if section == "relations":
        return "::".join(str(item.get(key) or "").strip().casefold() for key in ("source", "target", "type"))
    if section == "unresolved_mentions":
        return str(item.get("mention_text") or item.get("canonical_name") or "").strip().casefold()
    return str(item.get("canonical_name") or item.get("name") or item.get("id") or "").strip().casefold()
