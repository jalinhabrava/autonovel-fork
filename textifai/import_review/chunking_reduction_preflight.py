from __future__ import annotations

from copy import deepcopy
from typing import Any

from textifai.import_review.batch_planner import StructuredSourceChunk

CRITICAL_SECTIONS = ["characters", "places", "concepts", "objects", "events", "relations", "unresolved_mentions"]


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
