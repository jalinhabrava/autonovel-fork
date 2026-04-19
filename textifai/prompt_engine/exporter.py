from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def export_prompt_cases(
    cases: Sequence[Mapping[str, Any]],
    json_path: str | Path,
    md_path: str | Path,
    *,
    export_title: str = "TextifAI Prompt Export",
) -> dict[str, Any]:
    payload = {
        "export_title": export_title,
        "evaluation_status": "partial_pipeline_only_until_obsidian_bridge_snapshot_is_fresh_and_validated",
        "evaluation_note": (
            "Prompt/output review is paused as definitive validation until a fresh and valid Obsidian bridge snapshot "
            "is available as the preferred VaERL context source, or a future live Obsidian bridge exists."
        ),
        "cases": [_normalize_case(case) for case in cases],
    }
    json_path = Path(json_path)
    md_path = Path(md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_prompt_export_markdown(payload), encoding="utf-8")
    return payload


def render_prompt_export_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload.get('export_title', 'TextifAI Prompt Export')}",
        "",
        f"_evaluation_status_: `{payload.get('evaluation_status')}`",
        "",
        payload.get("evaluation_note", ""),
        "",
    ]
    for case in payload.get("cases", []):
        lines.extend(
            [
                f"## {case['case_id']}",
                f"- Case: `{case['case_id']}`",
                f"- Input: {case.get('input', '')}",
                f"- Flow: `{case.get('flow_name')}`",
                f"- Semantic response kind: `{case.get('semantic_response_kind')}`",
                f"- Provider execution enabled: `{case.get('provider_execution_enabled')}`",
                f"- Provider execution mode: `{case.get('provider_execution_mode')}`",
                f"- Response generation mode: `{case.get('response_generation_mode')}`",
                f"- Response generation reason: `{case.get('response_generation_reason')}`",
                f"- Simulated preview enabled: `{case.get('simulated_preview_enabled')}`",
                f"- Prompt base: `{case.get('prompt_base_id')}` / `{case.get('prompt_base_version')}`",
                f"- Prompt template: `{case.get('prompt_template_id')}` / `{case.get('prompt_template_version')}`",
                f"- Model profile used: `{case.get('model_profile_used')}`",
                f"- Response generation ready: `{case.get('response_generation_ready')}`",
                f"- Followthrough from previous turn: `{case.get('followthrough_from_previous_turn')}`",
                f"- Resolved target: {json.dumps(case.get('resolved_target'), ensure_ascii=False)}",
                f"- Candidate targets: {json.dumps(case.get('candidate_targets', []), ensure_ascii=False)}",
                f"- Entity hints: {json.dumps(case.get('entity_hints', []), ensure_ascii=False)}",
                f"- Anchored evidence summary: {json.dumps(case.get('anchored_evidence_used', {}), ensure_ascii=False)}",
                f"- Response support summary: {json.dumps(case.get('response_support_summary', {}), ensure_ascii=False)}",
                "- Trace rendered prompt payload:",
                "```json",
                json.dumps(case.get("trace_rendered_prompt_payload", {}), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "- LLM rendered prompt payload:",
                "```json",
                json.dumps(case.get("llm_rendered_prompt_payload", {}), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                f"- Simulated preview output: {case.get('simulated_preview_output', '')}",
                f"- Author-facing response: {case.get('author_facing_response', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(case.get("steps", []))
    first_step = _pick_prompt_step(steps) or (steps[0] if steps else {})
    resolved_target = first_step.get("resolved_target") or _extract_resolved_target(case)
    candidate_targets = first_step.get("candidate_targets") or _extract_candidate_targets(case)
    entity_hints = first_step.get("entity_hints") or _extract_entity_hints(case)
    trace_rendered_prompt_payload = first_step.get("trace_rendered_prompt_payload") or first_step.get("rendered_prompt_payload") or {}
    llm_rendered_prompt_payload = first_step.get("llm_rendered_prompt_payload") or {}
    if not isinstance(trace_rendered_prompt_payload, Mapping):
        trace_rendered_prompt_payload = {"_trace_payload_note": str(trace_rendered_prompt_payload)}
    if not isinstance(llm_rendered_prompt_payload, Mapping):
        llm_rendered_prompt_payload = {"_llm_payload_note": str(llm_rendered_prompt_payload)}
    response_support_summary = first_step.get("response_support_summary") or first_step.get("anchored_evidence_used") or {}
    if not isinstance(response_support_summary, Mapping):
        response_support_summary = {"_response_support_note": str(response_support_summary)}
    return {
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "input": case.get("input"),
        "flow_name": first_step.get("flow_name") or case.get("flow_chosen"),
        "semantic_response_kind": first_step.get("semantic_response_kind"),
        "provider_mode": first_step.get("provider_mode"),
        "provider_execution_enabled": first_step.get("provider_execution_enabled", False),
        "provider_execution_mode": first_step.get("provider_execution_mode"),
        "response_generation_mode": first_step.get("response_generation_mode"),
        "response_generation_reason": first_step.get("response_generation_reason"),
        "simulated_preview_enabled": first_step.get("simulated_preview_enabled", False),
        "prompt_base_id": first_step.get("prompt_base_id"),
        "prompt_base_version": first_step.get("prompt_base_version"),
        "prompt_template_id": first_step.get("prompt_template_id"),
        "prompt_template_version": first_step.get("prompt_template_version"),
        "model_profile_used": first_step.get("model_profile_used"),
        "response_generation_ready": first_step.get("response_generation_ready"),
        "followthrough_from_previous_turn": response_support_summary.get("followthrough_from_previous_turn"),
        "resolved_target": resolved_target,
        "candidate_targets": candidate_targets,
        "entity_hints": entity_hints,
        "vault_context_snippets": trace_rendered_prompt_payload.get("user_payload", {}).get("vault_context_snippets", []),
        "supporting_canon": trace_rendered_prompt_payload.get("user_payload", {}).get("supporting_canon", []),
        "trace_rendered_prompt_payload": trace_rendered_prompt_payload,
        "llm_rendered_prompt_payload": llm_rendered_prompt_payload,
        "author_facing_response": case.get("author_facing_response"),
        "simulated_preview_output": first_step.get("simulated_preview_output"),
        "response_support_summary": response_support_summary,
        "anchored_evidence_used": first_step.get("anchored_evidence_used") or {},
        "provider_model_used": first_step.get("provider_model_used"),
        "live_model_response": first_step.get("live_model_response"),
    }


def _extract_resolved_target(case: Mapping[str, Any]) -> dict[str, Any] | None:
    for step in case.get("steps", []):
        if isinstance(step, Mapping):
            resolved = step.get("resolved_target")
            if isinstance(resolved, Mapping):
                return dict(resolved)
    return None


def _extract_candidate_targets(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    for step in case.get("steps", []):
        if isinstance(step, Mapping):
            candidates = step.get("candidate_targets")
            if isinstance(candidates, list):
                return [dict(item) for item in candidates if isinstance(item, Mapping)]
    return []


def _extract_entity_hints(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    for step in case.get("steps", []):
        if isinstance(step, Mapping):
            hints = step.get("entity_hints")
            if isinstance(hints, list):
                return [dict(item) for item in hints if isinstance(item, Mapping)]
    return []


def _pick_prompt_step(steps: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for step in reversed(list(steps)):
        if not isinstance(step, Mapping):
            continue
        if step.get("trace_rendered_prompt_payload") or step.get("rendered_prompt_payload") or step.get("prompt_template_id"):
            return step
    return None
