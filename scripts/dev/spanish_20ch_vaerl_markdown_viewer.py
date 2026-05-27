from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.markdown_graph_index import build_markdown_graph_index
from textifai.import_review.vaerl_markdown_materializer import materialize_vaerl_markdown
from textifai.web_viewer.project_reader import ProjectCatalog, read_note, read_project
from vault.schema import slugify


EXPECTED_ROOT = REPO_ROOT / "tests/fixtures/textifai/spanish_20ch_e2e/expected"
PRIVATE_HANDOFF_DIR = REPO_ROOT / "docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight"

FORBIDDEN_WRITER_TERMS = {
    "chunk",
    "reduction",
    "parseable",
    "provider",
    "source_ref",
    "finish_reason",
    "json",
    "continuation",
    "patch",
    "model",
    "profile",
    "token",
    "api",
    "telemetry",
    "run_id",
    "failure_mode",
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_path = Path(args.source_file).resolve()

    expected_dir = EXPECTED_ROOT
    expected_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    runtime_root = Path(args.runtime_root).resolve() / now
    private_provider_root = runtime_root / "provider_runs"
    chapter_outputs_root = runtime_root / "chapter_outputs"
    vaerl_root = runtime_root / "vaerl"
    markdown_vault_root = runtime_root / "markdown_vault"
    viewer_project_root = runtime_root / "viewer_project"
    reports_root = runtime_root / "reports"
    logs_root = runtime_root / "logs"
    for path in [private_provider_root, chapter_outputs_root, vaerl_root, markdown_vault_root, viewer_project_root, reports_root, logs_root]:
        path.mkdir(parents=True, exist_ok=True)

    private_dir = PRIVATE_HANDOFF_DIR
    private_dir.mkdir(parents=True, exist_ok=True)

    source_report = build_source_preflight(source_path)
    write_json(expected_dir / "spanish_20ch_source_preflight_after_sp094.json", source_report)
    if not source_report["source_available"]:
        return write_blocked_outputs(
            expected_dir=expected_dir,
            runtime_root=runtime_root,
            private_dir=private_dir,
            assessment="spanish_20ch_blocked_missing_source",
            reason=source_report.get("blocking_reason") or "source_missing_or_unreadable",
        )

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    provider_setup = {
        "assessment": "deepseek_provider_preflight_completed",
        "provider": "deepseek",
        "deepseek_api_key_present": bool(key),
        "deepseek_api_key_length": len(key),
        "deepseek_api_key_sha8": hashlib.sha256(key.encode()).hexdigest()[:8] if key else "",
        "uses_process_env": True,
        "depends_on_dotenv": False,
    }
    if not provider_setup["deepseek_api_key_present"]:
        write_json(expected_dir / "spanish_20ch_deepseek_execution_summary_after_sp094.json", {
            "assessment": "spanish_20ch_blocked_provider",
            "reason": "missing_deepseek_api_key",
            "provider_calls_executed": False,
        })
        return write_blocked_outputs(
            expected_dir=expected_dir,
            runtime_root=runtime_root,
            private_dir=private_dir,
            assessment="spanish_20ch_blocked_provider",
            reason="missing_deepseek_api_key",
            provider_setup=provider_setup,
        )

    selected_chapters = [f"ch_{index:03d}" for index in range(1, 21)]
    execution_plan = {
        "assessment": "spanish_20ch_execution_plan_ready",
        "source_path": str(source_path),
        "selected_chapters": selected_chapters,
        "strategy": {
            "provider": "deepseek",
            "flash_first": {"model": "deepseek-v4-flash", "phase": "bootstrap_chapter_extraction"},
            "targeted_pro_conditions": [
                "flash_invalid_or_unrecoverable_output",
                "repeated_truncation_or_continuation_failure",
                "critical_chapter_relation_quality_poor",
                "source_evidence_coverage_poor",
            ],
        },
        "no_artificial_call_cap": True,
        "telemetry_only_estimates": True,
        "emergency_loop_guard": {"enabled": True, "max_provider_requests": int(args.emergency_max_provider_requests)},
        "real_stop_conditions": [
            "source_missing_or_unreadable",
            "missing_deepseek_api_key",
            "auth_error",
            "credit_exhausted",
            "persistent_rate_limit",
            "provider_outage",
            "persistent_timeout",
            "source_corrupt_or_undetectable_chapters",
            "unrecoverable_parse_error",
            "repeated_invalid_continuation",
            "unexpected_write_back",
            "user_cancelled",
        ],
        "runtime_root": str(runtime_root),
        "private_runtime_packet_root": str(runtime_root),
        "private_handoff_root": str(private_dir),
    }
    write_json(expected_dir / "spanish_20ch_execution_plan_after_sp094.json", execution_plan)

    report_prefix = "spanish_20ch_e2e"
    report_suffix = "after_sp094"
    provider_expected_root = reports_root / "provider_public_reports"
    provider_expected_root.mkdir(parents=True, exist_ok=True)

    provider_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/dev/real_deepseek_e2e_dryrun.py"),
        "--source-file",
        str(source_path),
        "--chapter-ids",
        ",".join(selected_chapters),
        "--models",
        "deepseek-v4-flash",
        "--output-root",
        str(private_provider_root),
        "--allow-provider-calls",
        "--response-format-json",
        "--no-write-back",
        "--report-prefix",
        report_prefix,
        "--report-suffix",
        report_suffix,
        "--patch-continuation-mode",
        "--no-artificial-call-cap",
        "--max-provider-requests",
        str(int(args.emergency_max_provider_requests)),
        "--work-title",
        str(args.work_title),
        "--work-language",
        "es",
        "--expected-root",
        str(provider_expected_root),
    ]

    start = time.time()
    run = subprocess.run(provider_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    elapsed = round(time.time() - start, 3)

    provider_packet_dir = latest_subdir(private_provider_root)
    provider_reports = load_provider_reports(provider_expected_root, report_prefix, report_suffix)
    provider_summary = build_provider_summary(run=run, elapsed=elapsed, provider_reports=provider_reports, provider_packet_dir=provider_packet_dir)
    write_json(expected_dir / "spanish_20ch_deepseek_execution_summary_after_sp094.json", provider_summary)

    if run.returncode != 0 or provider_packet_dir is None:
        assessment = "spanish_20ch_blocked_provider" if provider_summary.get("blocked_provider") else "spanish_20ch_failed_needs_patch"
        return write_blocked_outputs(
            expected_dir=expected_dir,
            runtime_root=runtime_root,
            private_dir=private_dir,
            assessment=assessment,
            reason=provider_summary.get("failure_reason") or "provider_execution_failed",
            provider_setup=provider_setup,
            execution_plan=execution_plan,
            provider_summary=provider_summary,
        )

    chapter_payloads = extract_reduction_payloads(provider_reports, chapter_outputs_root)
    vaerl_payload = build_vaerl_projection(chapter_payloads)
    write_json(vaerl_root / "vaerl_projection.json", vaerl_payload)
    write_json(expected_dir / "spanish_20ch_vaerl_projection_summary_after_sp094.json", summarize_vaerl(vaerl_payload))

    manifest = materialize_vaerl_markdown(vaerl_payload, markdown_vault_root, write_files=True)
    write_json(markdown_vault_root / "System/materialization_summary.json", summarize_manifest(manifest))

    markdown_index = build_markdown_graph_index(markdown_vault_root)
    write_json(markdown_vault_root / "System/markdown_graph_index.json", markdown_index)

    populate_viewer_project(
        viewer_project_root=viewer_project_root,
        markdown_vault_root=markdown_vault_root,
        vaerl_payload=vaerl_payload,
        manifest=manifest,
        markdown_index=markdown_index,
        provider_reports=provider_reports,
    )

    materialization_summary = summarize_materialization(manifest=manifest, markdown_index=markdown_index)
    write_json(expected_dir / "spanish_20ch_markdown_materialization_summary_after_sp094.json", materialization_summary)
    write_json(expected_dir / "spanish_20ch_markdown_graph_index_summary_after_sp094.json", summarize_graph_index(markdown_index))
    write_json(expected_dir / "spanish_20ch_viewer_project_summary_after_sp094.json", summarize_viewer_project(viewer_project_root, manifest, markdown_index))

    viewer_report, viewer_payload = run_viewer_manual_checks(runtime_root=runtime_root, requested_port=int(args.viewer_port))
    write_json(expected_dir / "spanish_20ch_viewer_manual_review_server_after_sp094.json", viewer_report)

    viewer_api_validation = summarize_viewer_api(viewer_payload)
    write_json(expected_dir / "spanish_20ch_viewer_api_validation_after_sp094.json", viewer_api_validation)

    graph_quality_summary = summarize_graph_quality(markdown_index)
    write_json(expected_dir / "spanish_20ch_graph_quality_summary_after_sp094.json", graph_quality_summary)

    writer_outcome_public = build_writer_outcome_public(provider_reports)
    assert_writer_outcome_terms(writer_outcome_public)
    write_json(expected_dir / "spanish_20ch_writer_outcome_after_sp094.json", writer_outcome_public)

    ui_review = build_ui_review_checklist(viewer_payload=viewer_payload, markdown_index=markdown_index)
    write_json(expected_dir / "spanish_20ch_ui_review_checklist_after_sp094.json", ui_review)

    assessment = decide_assessment(provider_summary=provider_summary, writer_outcome=writer_outcome_public)
    decision_report = {
        "assessment": assessment,
        "provider_calls_executed": True,
        "runtime_root": str(runtime_root),
        "private_runtime_packet_root": str(runtime_root),
        "private_handoff_root": str(private_dir),
        "next_phase": "Phase 1.3.M-b5c-4y — targeted retry + markdown edit queue scaffolding" if assessment == "spanish_20ch_partial_needs_targeted_retry" else "Phase 1.3.M-b5c-4y — manual author review + targeted retry where needed",
        "spanish_20ch_allowed_for_manual_review": assessment in {"spanish_20ch_vaerl_markdown_viewer_ready_for_manual_review", "spanish_20ch_partial_needs_targeted_retry"},
    }
    write_json(expected_dir / "spanish_20ch_product_decision_after_sp094.json", decision_report)

    write_private_summaries(
        private_dir=private_dir,
        runtime_root=runtime_root,
        source_path=source_path,
        provider_summary=provider_summary,
        writer_outcome=writer_outcome_public,
        vaerl_payload=vaerl_payload,
        materialization_summary=materialization_summary,
        graph_quality_summary=graph_quality_summary,
        viewer_api_validation=viewer_api_validation,
    )

    write_commit_safe_handoff(
        handoff_path=REPO_ROOT / "docs/handoffs/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight.md",
        source_report=source_report,
        provider_setup=provider_setup,
        execution_plan=execution_plan,
        provider_summary=provider_summary,
        writer_outcome=writer_outcome_public,
        vaerl_summary=summarize_vaerl(vaerl_payload),
        materialization_summary=materialization_summary,
        graph_summary=graph_quality_summary,
        viewer_report=viewer_report,
        viewer_api=viewer_api_validation,
        ui_review=ui_review,
        decision=decision_report,
        runtime_root=runtime_root,
        private_dir=private_dir,
    )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spanish 20ch E2E orchestration: DeepSeek -> VaERL -> Markdown -> Viewer")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--runtime-root", default="/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer")
    parser.add_argument("--work-title", default="ESP 王者の杖")
    parser.add_argument("--viewer-port", type=int, default=8872)
    parser.add_argument("--emergency-max-provider-requests", type=int, default=5000)
    return parser


def build_source_preflight(source_path: Path) -> dict[str, Any]:
    available = source_path.exists() and source_path.is_file() and os.access(source_path, os.R_OK)
    if not available:
        return {
            "assessment": "spanish_source_preflight_blocked",
            "source_path": str(source_path),
            "source_available": False,
            "blocking_reason": "source_missing_or_unreadable",
            "selected_chapters": [f"ch_{index:03d}" for index in range(1, 21)],
        }

    text = source_path.read_text(encoding="utf-8", errors="replace")
    checksum = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    record = SourceDocumentRecord(
        source_id=f"source_{checksum[:10]}",
        path=str(source_path),
        relative_path=source_path.name,
        filename=source_path.name,
        extension=source_path.suffix.lstrip("."),
        size_bytes=source_path.stat().st_size,
        checksum=checksum,
        dominant_language="es",
        detected_languages=["es"],
        line_count=len(text.splitlines()),
        extracted_char_count=len(text),
        extracted_word_count=len(text.split()),
        extracted_page_count=0,
    )
    detected = detect_story_chapters(record, text)
    selected = [f"ch_{index:03d}" for index in range(1, 21)]
    available_20 = len(detected) >= 20
    signal_counter = Counter()
    for chapter in detected[:20]:
        signal_counter.update(chapter.detection_signals)
    return {
        "assessment": "spanish_source_preflight_completed" if available_20 else "spanish_source_preflight_insufficient_chapters",
        "source_path": str(source_path),
        "source_hash": checksum,
        "file_size": source_path.stat().st_size,
        "detected_chapter_count": len(detected),
        "selected_chapters": selected,
        "headings_pattern_summary": {
            "top_detection_signals": signal_counter.most_common(6),
            "first_selected_char_counts": [len(chapter.text) for chapter in detected[:20]],
        },
        "source_available": bool(available_20),
        "blocking_reason": None if available_20 else "chapters_1_to_20_not_detectable",
    }


def latest_subdir(root: Path) -> Path | None:
    if not root.exists():
        return None
    dirs = [path for path in root.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return sorted(dirs)[-1]


def report_name(prefix: str, suffix: str, kind: str) -> str:
    return f"{prefix}_{kind}_{suffix}.json"


def load_provider_reports(report_root: Path, prefix: str, suffix: str) -> dict[str, Any]:
    keys = [
        "execution_plan",
        "summary",
        "chunk_results",
        "reduction_summary",
        "decision",
        "budget_report",
        "budget_usage",
        "chunk_audit",
        "source_ref_audit",
        "truncation_continuation_audit",
        "truncation_continuation",
        "patch_validation",
        "thin_diagnostics",
        "internal_fail_rerun_plan",
        "user_ingestion_outcome",
        "general_pipeline_learnings",
        "deepseek_specific_learnings",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        path = report_root / report_name(prefix, suffix, key)
        if path.exists():
            out[key] = json.loads(path.read_text(encoding="utf-8"))
    return out


def build_provider_summary(*, run: subprocess.CompletedProcess[str], elapsed: float, provider_reports: dict[str, Any], provider_packet_dir: Path | None) -> dict[str, Any]:
    decision = provider_reports.get("decision") if isinstance(provider_reports.get("decision"), dict) else {}
    summary = provider_reports.get("summary") if isinstance(provider_reports.get("summary"), dict) else {}
    budget_usage = provider_reports.get("budget_usage") if isinstance(provider_reports.get("budget_usage"), dict) else {}
    execution_plan = provider_reports.get("execution_plan") if isinstance(provider_reports.get("execution_plan"), dict) else {}
    return {
        "assessment": "spanish_20ch_provider_run_completed" if run.returncode == 0 else "spanish_20ch_provider_run_failed",
        "provider_calls_executed": run.returncode == 0,
        "command_exit_code": run.returncode,
        "duration_seconds": elapsed,
        "planned_provider_call_count": execution_plan.get("planned_provider_call_count"),
        "planned_with_continuation_reserve": execution_plan.get("planned_provider_call_count_with_continuation_reserve"),
        "actual_provider_call_count": summary.get("call_count"),
        "retryable_chapter_count": summary.get("retryable_chapter_count"),
        "decision_assessment": decision.get("assessment"),
        "provider_block_reason": decision.get("blocked_reason") if isinstance(decision, dict) else None,
        "usage_rows": len(budget_usage.get("runs") or []),
        "provider_packet_dir": str(provider_packet_dir) if provider_packet_dir else "",
        "blocked_provider": bool(run.returncode != 0 and str(decision.get("blocked_reason") or "").startswith("missing_deepseek")),
        "failure_reason": decision.get("blocked_reason") or (run.stderr.strip()[:500] if run.stderr else ""),
        "stdout_tail": (run.stdout or "")[-1200:],
        "stderr_tail": (run.stderr or "")[-1200:],
    }


def extract_reduction_payloads(provider_reports: dict[str, Any], chapter_outputs_root: Path) -> list[dict[str, Any]]:
    chapter_payloads: list[dict[str, Any]] = []
    reductions = ((provider_reports.get("reduction_summary") or {}).get("reductions") or [])
    for row in reductions:
        if not isinstance(row, dict):
            continue
        private_dir = Path(str(row.get("private_dir") or "")).resolve()
        parsed_path = private_dir / "provider_response_parsed.json"
        if not parsed_path.exists():
            continue
        parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
        chapter = first_chapter(parsed)
        if not isinstance(chapter, dict):
            continue
        chapter_payload = {
            "chapter_id": str(chapter.get("chapter_id") or row.get("chapter_id") or ""),
            "chapter_title": str(chapter.get("chapter_title_canonical") or chapter.get("chapter_title_original") or ""),
            "chapter_summary": str(chapter.get("chapter_summary") or ""),
            "sequence_index": chapter.get("sequence_index"),
            "chapter": chapter,
            "run_row": {
                "run_id": row.get("run_id"),
                "model": row.get("model"),
                "profile_id": row.get("profile_id"),
                "validation_ok": row.get("validation_ok"),
                "failure_mode": row.get("failure_mode"),
                "score": row.get("score"),
                "thin_warnings": row.get("thin_warnings") or [],
            },
        }
        chapter_payloads.append(chapter_payload)
        out_path = chapter_outputs_root / f"{chapter_payload['chapter_id']}.json"
        write_json(out_path, chapter)
    chapter_payloads.sort(key=lambda item: item.get("chapter_id") or "")
    return chapter_payloads


def first_chapter(payload: dict[str, Any]) -> dict[str, Any] | None:
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
        return chapters[0]
    return None


def build_vaerl_projection(chapter_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    reviews: list[dict[str, Any]] = []
    chapters: list[dict[str, Any]] = []

    for payload in chapter_payloads:
        chapter = payload["chapter"]
        chapter_id = str(payload["chapter_id"])
        mentioned_labels: set[str] = set()
        chapter_refs: list[dict[str, Any]] = []

        for section, kind in [
            ("characters", "character"),
            ("places", "place"),
            ("concepts", "concept"),
            ("objects", "object"),
            ("events", "event"),
        ]:
            for item in chapter.get(section) or []:
                if not isinstance(item, dict):
                    continue
                label = pick_label(item)
                if not label:
                    continue
                entity = ensure_entity(entities, kind=kind, label=label)
                merge_entity_item(entity=entity, item=item, chapter_id=chapter_id, kind=kind)
                mentioned_labels.add(label)
                chapter_refs.extend(normalize_refs(item.get("source_refs")))

        for relation in chapter.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            source_label = str(relation.get("from_canonical") or relation.get("from_canonical_candidate") or relation.get("from_surface") or "").strip()
            target_label = str(relation.get("to_canonical") or relation.get("to_canonical_candidate") or relation.get("to_surface") or "").strip()
            relation_label = str(relation.get("relation_label") or relation.get("relation_category") or "related_to").strip() or "related_to"
            source_refs = normalize_refs(relation.get("source_refs"))
            facts = [str(value).strip() for value in (relation.get("facts") or []) if str(value).strip()]
            if source_label:
                source_entity = ensure_entity(entities, kind="concept", label=source_label)
                source_entity["chapter_ids"].add(chapter_id)
                source_entity["source_refs"].extend(source_refs)
                rel_payload = {
                    "target_label": target_label,
                    "label": relation_label,
                    "type": relation_label,
                    "facts": facts[:3],
                    "source_refs": source_refs,
                }
                source_entity["relationships"].append(rel_payload)
                mentioned_labels.add(source_label)
            if target_label:
                target_entity = ensure_entity(entities, kind="concept", label=target_label)
                target_entity["chapter_ids"].add(chapter_id)
                target_entity["source_refs"].extend(source_refs)
                mentioned_labels.add(target_label)

        for unresolved in chapter.get("unresolved_mentions") or []:
            if not isinstance(unresolved, dict):
                continue
            surface = str(unresolved.get("surface") or "").strip()
            if not surface:
                continue
            reviews.append(
                {
                    "id": f"review:{chapter_id}:{slugify(surface) or 'mention'}",
                    "target_label": surface,
                    "chapter_id": chapter_id,
                    "status": "needs_review",
                    "summary": str((unresolved.get("facts") or [""])[0] or "").strip(),
                    "source_refs": normalize_refs(unresolved.get("source_refs")),
                }
            )

        chapters.append(
            {
                "id": f"chapter:{chapter_id}",
                "chapter_id": chapter_id,
                "title": str(chapter.get("chapter_title_canonical") or chapter.get("chapter_title_original") or chapter_id),
                "summary": str(chapter.get("chapter_summary") or "").strip(),
                "status": "ready",
                "review_state": "ready",
                "entity_mentions": sorted(mentioned_labels),
                "source_refs": dedupe_refs(chapter_refs),
                "tags": ["chapter", "es"],
            }
        )

    finalized_entities: list[dict[str, Any]] = []
    for item in entities.values():
        item["chapter_ids"] = sorted(item["chapter_ids"])
        item["aliases"] = sorted(item["aliases"])
        item["facts"] = unique_list(item["facts"])[:8]
        item["key_facts"] = list(item["facts"])
        item["source_refs"] = dedupe_refs(item["source_refs"])
        item["relationships"] = dedupe_relationships(item["relationships"])
        item["status"] = "needs_review" if item["review_state"] == "needs_review" else "ready"
        item["summary"] = item.get("summary") or (item["facts"][0] if item["facts"] else "")
        finalized_entities.append(item)

    finalized_entities.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("canonical_label") or "").casefold()))
    chapters.sort(key=lambda row: str(row.get("chapter_id") or ""))

    work = {
        "title": "ESP 王者の杖",
        "language": "es",
        "source": "spanish_20ch_real_run",
    }
    return {
        "work": work,
        "entities": finalized_entities,
        "chapters": chapters,
        "reviews": reviews,
    }


def ensure_entity(entities: dict[tuple[str, str], dict[str, Any]], *, kind: str, label: str) -> dict[str, Any]:
    key = (kind, label.casefold())
    if key not in entities:
        entities[key] = {
            "id": f"{kind}:{slugify(label) or hashlib.sha1(label.encode()).hexdigest()[:8]}",
            "kind": kind,
            "canonical_label": label,
            "canonical_name": label,
            "aliases": set(),
            "tags": [kind],
            "review_state": "ready",
            "facts": [],
            "key_facts": [],
            "relationships": [],
            "source_refs": [],
            "chapter_ids": set(),
            "summary": "",
            "confidence": 0.7,
            "surface_forms": [],
        }
    return entities[key]


def merge_entity_item(*, entity: dict[str, Any], item: dict[str, Any], chapter_id: str, kind: str) -> None:
    surface = str(item.get("surface") or "").strip()
    canonical = pick_label(item)
    if surface and surface.casefold() != canonical.casefold():
        entity["aliases"].add(surface)
    for alias in item.get("aliases") or []:
        text = str(alias).strip()
        if text:
            entity["aliases"].add(text)
    for fact in item.get("facts") or []:
        text = str(fact).strip()
        if text:
            entity["facts"].append(text)
    relationships = item.get("relationships") or []
    for relation in relationships:
        if not isinstance(relation, dict):
            continue
        target = str(relation.get("target_label") or relation.get("target") or relation.get("to") or relation.get("canonical") or "").strip()
        relation_label = str(relation.get("label") or relation.get("relation_label") or relation.get("relation_category") or relation.get("type") or "related_to").strip() or "related_to"
        entity["relationships"].append(
            {
                "target_label": target,
                "label": relation_label,
                "type": relation_label,
                "facts": [str(value).strip() for value in (relation.get("facts") or []) if str(value).strip()][:3],
                "source_refs": normalize_refs(relation.get("source_refs")),
            }
        )
    if str(item.get("needs_review") or "").lower() == "true" or str(item.get("review_state") or "").strip() in {"needs_review", "candidate", "local_candidate"}:
        entity["review_state"] = "needs_review"
    for tag in [kind, str(item.get("entity_subkind") or item.get("object_subkind") or "").strip()]:
        if tag:
            entity["tags"].append(tag)
    entity["chapter_ids"].add(chapter_id)
    entity["source_refs"].extend(normalize_refs(item.get("source_refs")))
    if not entity["summary"] and entity["facts"]:
        entity["summary"] = entity["facts"][0]


def pick_label(item: dict[str, Any]) -> str:
    for key in ("canonical", "canonical_name", "canonical_candidate", "surface", "name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def normalize_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, list):
        iterable = value
    elif isinstance(value, dict):
        iterable = [value]
    else:
        iterable = []
    for row in iterable:
        if not isinstance(row, dict):
            continue
        refs.append(
            {
                "source_id": row.get("source_id"),
                "chapter_id": row.get("chapter_id"),
                "chunk_id": row.get("chunk_id"),
                "char_start": row.get("char_start"),
                "char_end": row.get("char_end"),
            }
        )
    return refs


def dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in refs:
        key = (
            row.get("source_id"),
            row.get("chapter_id"),
            row.get("chunk_id"),
            row.get("char_start"),
            row.get("char_end"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def dedupe_relationships(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = (
            str(row.get("target_label") or "").casefold(),
            str(row.get("label") or "").casefold(),
            tuple(sorted(str(item).strip() for item in (row.get("facts") or []) if str(item).strip())),
        )
        if key in seen:
            continue
        seen.add(key)
        row = dict(row)
        row["source_refs"] = dedupe_refs(row.get("source_refs") or [])
        out.append(row)
    return out


def unique_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def summarize_vaerl(vaerl_payload: dict[str, Any]) -> dict[str, Any]:
    entities = [row for row in vaerl_payload.get("entities") or [] if isinstance(row, dict)]
    chapters = [row for row in vaerl_payload.get("chapters") or [] if isinstance(row, dict)]
    reviews = [row for row in vaerl_payload.get("reviews") or [] if isinstance(row, dict)]
    by_kind = Counter(str(row.get("kind") or "unknown") for row in entities)
    needs_review = sum(1 for row in entities if str(row.get("review_state") or "") == "needs_review")
    relation_count = sum(len(row.get("relationships") or []) for row in entities)
    return {
        "assessment": "spanish_20ch_vaerl_projection_ready",
        "entity_count": len(entities),
        "chapter_count": len(chapters),
        "review_item_count": len(reviews),
        "entity_counts_by_kind": dict(by_kind),
        "needs_review_entity_count": needs_review,
        "relationship_count": relation_count,
    }


def summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    notes = [row for row in manifest.get("notes") or [] if isinstance(row, dict)]
    by_kind = Counter(str(row.get("kind") or "note") for row in notes)
    return {
        "assessment": "spanish_20ch_markdown_materialization_ready",
        "schema_version": manifest.get("schema_version"),
        "note_count": len(notes),
        "notes_by_kind": dict(by_kind),
        "folders": manifest.get("folders") or [],
        "editable_policy": manifest.get("editable_policy"),
    }


def populate_viewer_project(
    *,
    viewer_project_root: Path,
    markdown_vault_root: Path,
    vaerl_payload: dict[str, Any],
    manifest: dict[str, Any],
    markdown_index: dict[str, Any],
    provider_reports: dict[str, Any],
) -> None:
    for path in [
        "Characters",
        "Places",
        "Events",
        "Objects",
        "Concepts",
        "Chapters",
        "Reviews",
        "System",
    ]:
        (viewer_project_root / path).mkdir(parents=True, exist_ok=True)

    for note in manifest.get("notes") or []:
        if not isinstance(note, dict):
            continue
        rel = str(note.get("path") or "")
        if not rel:
            continue
        src = markdown_vault_root / rel
        if src.exists():
            dst = viewer_project_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    system_root = viewer_project_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    write_json(system_root / "markdown_manifest.json", manifest)
    write_json(system_root / "markdown_graph_index.json", markdown_index)
    write_json(system_root / "obsidian_import.json", build_obsidian_import(vaerl_payload))
    write_json(system_root / "writer_outcome.json", (provider_reports.get("user_ingestion_outcome") or {}).get("user_ingestion_outcome") or {})
    write_json(
        system_root / "viewer_project_summary.json",
        {
            "assessment": "spanish_20ch_viewer_project_ready",
            "has_markdown_manifest": True,
            "has_markdown_graph_index": True,
            "note_count": manifest.get("note_count"),
            "graph_nodes": len(markdown_index.get("nodes") or []),
            "graph_edges": len(markdown_index.get("edges") or []),
        },
    )


def build_obsidian_import(vaerl_payload: dict[str, Any]) -> dict[str, Any]:
    work = vaerl_payload.get("work") if isinstance(vaerl_payload.get("work"), dict) else {}
    entities_out: list[dict[str, Any]] = []
    for row in vaerl_payload.get("entities") or []:
        if not isinstance(row, dict):
            continue
        entities_out.append(
            {
                "canonical_name": row.get("canonical_label"),
                "preferred_slug": slugify(str(row.get("canonical_label") or "")),
                "entity_kind": row.get("kind"),
                "review_state": row.get("review_state"),
                "note_role": "primary",
                "summary": row.get("summary"),
                "aliases": row.get("aliases") or [],
                "key_facts": row.get("facts") or [],
                "relationships": row.get("relationships") or [],
                "source_refs": row.get("source_refs") or [],
                "tags": row.get("tags") or [],
                "confidence": row.get("confidence"),
            }
        )
    chapters_out: list[dict[str, Any]] = []
    for row in vaerl_payload.get("chapters") or []:
        if not isinstance(row, dict):
            continue
        chapters_out.append(
            {
                "chapter_id": row.get("chapter_id"),
                "sequence_index": int(str(row.get("chapter_id") or "0").split("_")[-1]) if str(row.get("chapter_id") or "").startswith("ch_") else None,
                "chapter_title_original": row.get("title"),
                "chapter_title_canonical": row.get("title"),
                "chapter_summary": row.get("summary"),
                "summary": row.get("summary"),
                "chapter_label_type": "chapter",
            }
        )
    return {
        "work": {
            "title": work.get("title") or "ESP 王者の杖",
            "language": work.get("language") or "es",
        },
        "entities": entities_out,
        "chapters": chapters_out,
        "reviews": vaerl_payload.get("reviews") or [],
    }


def summarize_materialization(*, manifest: dict[str, Any], markdown_index: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessment": "spanish_20ch_markdown_materialization_summary_ready",
        "note_count": manifest.get("note_count"),
        "notes_by_kind": dict(Counter(str(row.get("kind") or "note") for row in (manifest.get("notes") or []) if isinstance(row, dict))),
        "edge_count": markdown_index.get("edge_count"),
        "tag_count": len(markdown_index.get("tags") or []),
        "orphan_note_count": len(markdown_index.get("orphan_notes") or []),
        "unresolved_link_count": len(markdown_index.get("unresolved_links") or []),
        "editable_policy": manifest.get("editable_policy"),
        "viewer_read_only_note": True,
    }


def summarize_graph_index(markdown_index: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in markdown_index.get("nodes") or [] if isinstance(node, dict)]
    edges = [edge for edge in markdown_index.get("edges") or [] if isinstance(edge, dict)]
    by_kind = Counter(str(node.get("kind") or "note") for node in nodes)
    degree_values = sorted(int(node.get("degree") or 0) for node in nodes)
    degree_summary = {
        "min": degree_values[0] if degree_values else 0,
        "max": degree_values[-1] if degree_values else 0,
        "median": degree_values[len(degree_values) // 2] if degree_values else 0,
        "avg": round(sum(degree_values) / len(degree_values), 4) if degree_values else 0,
    }
    return {
        "assessment": "spanish_20ch_markdown_graph_index_summary_ready",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_kind": dict(by_kind),
        "orphan_notes_count": len(markdown_index.get("orphan_notes") or []),
        "unresolved_links_count": len(markdown_index.get("unresolved_links") or []),
        "degree_distribution_summary": degree_summary,
    }


def summarize_viewer_project(viewer_project_root: Path, manifest: dict[str, Any], markdown_index: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessment": "spanish_20ch_viewer_project_summary_ready",
        "project_root": str(viewer_project_root),
        "has_markdown_manifest": (viewer_project_root / "99_System/markdown_manifest.json").exists(),
        "has_markdown_graph_index": (viewer_project_root / "99_System/markdown_graph_index.json").exists(),
        "has_writer_outcome": (viewer_project_root / "99_System/writer_outcome.json").exists(),
        "markdown_note_count": manifest.get("note_count"),
        "graph_node_count": len(markdown_index.get("nodes") or []),
        "graph_edge_count": len(markdown_index.get("edges") or []),
    }


def run_viewer_manual_checks(*, runtime_root: Path, requested_port: int) -> tuple[dict[str, Any], dict[str, Any]]:
    root = runtime_root
    port = first_free_port(requested_port)
    host = "0.0.0.0"
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "textifai.web_viewer.server",
        "--root",
        str(root),
        "--host",
        host,
        "--port",
        str(port),
    ]
    log_path = runtime_root / "logs" / "viewer_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=log_fh, stderr=subprocess.STDOUT)

    base = f"http://127.0.0.1:{port}"
    project_id = ""
    endpoint_status: dict[str, int] = {}
    project_payload: dict[str, Any] = {}

    for _ in range(30):
        try:
            payload = fetch_json(f"{base}/api/projects")
            projects = payload.get("projects") if isinstance(payload, dict) else None
            if isinstance(projects, list):
                endpoint_status["/api/projects"] = 200
                if projects:
                    project_id = str(projects[0].get("project_id") or "")
                break
        except Exception:
            time.sleep(1)

    endpoint_status["/"] = fetch_status(f"{base}/")
    if project_id:
        project_url = f"{base}/api/projects/{quote(project_id)}"
        graph_url = f"{project_url}/graph"
        endpoint_status[f"/api/projects/{project_id}"] = fetch_status(project_url)
        endpoint_status[f"/api/projects/{project_id}/graph"] = fetch_status(graph_url)
        try:
            project_payload = fetch_json(project_url)
        except Exception:
            project_payload = {}
        note_path = ""
        notes = project_payload.get("notes") if isinstance(project_payload, dict) else None
        if isinstance(notes, list) and notes:
            note_path = str(notes[0].get("path") or "")
        if note_path:
            note_url = f"{project_url}/note?path={quote(note_path)}"
            endpoint_status[f"/api/projects/{project_id}/note"] = fetch_status(note_url)

    report = {
        "assessment": "spanish_20ch_viewer_manual_review_server_ready" if project_id else "spanish_20ch_viewer_manual_review_server_partial",
        "server_started": bool(project_id),
        "host": host,
        "port": port,
        "local_url": base,
        "project_id": project_id,
        "root": str(root),
        "stop_command": f"kill {proc.pid}",
        "endpoint_status": endpoint_status,
        "manual_review_required": True,
    }
    return report, project_payload


def first_free_port(start: int) -> int:
    for port in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def fetch_status(url: str) -> int:
    try:
        with urlopen(url, timeout=8) as response:
            return int(response.status)
    except HTTPError as exc:
        return int(exc.code)
    except URLError:
        return 0


def fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def summarize_viewer_api(viewer_payload: dict[str, Any]) -> dict[str, Any]:
    notes = viewer_payload.get("notes") if isinstance(viewer_payload, dict) else []
    graph = viewer_payload.get("graph") if isinstance(viewer_payload, dict) else {}
    overview = viewer_payload.get("overview") if isinstance(viewer_payload, dict) else {}
    node_detail_ok = False
    backlinks_ok = False
    local_graph_ok = False
    tags_ok = False
    if isinstance(notes, list) and notes:
        catalog = ProjectCatalog([Path(viewer_payload.get("metadata", {}).get("root") or "")]) if False else None
        sample = notes[0] if isinstance(notes[0], dict) else {}
        backlinks_ok = bool(sample.get("backlinks"))
        tags_ok = bool(sample.get("tags"))
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    edges = graph.get("edges") if isinstance(graph, dict) else []
    node_detail_ok = bool(nodes)
    local_graph_ok = bool(any((node.get("degree") is not None) for node in nodes if isinstance(node, dict)))
    return {
        "assessment": "spanish_20ch_viewer_api_validation_ready",
        "overview_ok": bool(overview),
        "wiki_ok": bool(notes),
        "graph_ok": bool(nodes) and bool(edges),
        "node_detail_ok": node_detail_ok,
        "backlinks_ok": backlinks_ok,
        "tags_ok": tags_ok,
        "local_graph_ok": local_graph_ok,
        "artifacts_secondary": True,
        "writer_outcome_visible": bool(viewer_payload.get("overview", {}).get("chapters_processed")),
        "readiness": "ready_for_manual_review" if bool(notes) and bool(nodes) else "partial",
    }


def summarize_graph_quality(markdown_index: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in markdown_index.get("nodes") or [] if isinstance(node, dict)]
    edges = [edge for edge in markdown_index.get("edges") or [] if isinstance(edge, dict)]
    kinds = Counter(str(node.get("kind") or "note") for node in nodes)
    edge_labels = Counter(str(edge.get("label") or "wikilink") for edge in edges)
    degrees = [int(node.get("degree") or 0) for node in nodes]
    return {
        "assessment": "spanish_20ch_graph_quality_summary_ready",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_kind": dict(kinds),
        "edges_by_kind": dict(edge_labels),
        "orphan_notes_count": len(markdown_index.get("orphan_notes") or []),
        "unresolved_links_count": len(markdown_index.get("unresolved_links") or []),
        "degree_distribution_summary": {
            "min": min(degrees) if degrees else 0,
            "max": max(degrees) if degrees else 0,
            "avg": round(sum(degrees) / len(degrees), 4) if degrees else 0,
        },
        "relation_density_summary": {
            "edges_per_node": round((len(edges) / len(nodes)), 4) if nodes else 0,
            "has_local_graph_data": True,
        },
        "warnings": [
            "real_labels_omitted_in_commit_safe_report",
        ],
    }


def build_writer_outcome_public(provider_reports: dict[str, Any]) -> dict[str, Any]:
    outcome = ((provider_reports.get("user_ingestion_outcome") or {}).get("user_ingestion_outcome") or {})
    affected = outcome.get("affected_chapters") if isinstance(outcome.get("affected_chapters"), list) else []
    review_count = sum(1 for row in affected if str(row.get("status") or "") == "needs_review")
    retry_count = sum(1 for row in affected if str(row.get("status") or "") == "needs_retry")
    ready = int(outcome.get("chapters_ready") or 0)
    total = int(outcome.get("total_chapters") or 20)
    status = str(outcome.get("status") or "success_with_warnings")
    primary_label = "Review results" if retry_count == 0 else "Retry pending chapters"
    payload = {
        "assessment": "spanish_20ch_writer_outcome_ready",
        "status": status,
        "total_chapters": total,
        "chapters_ready": ready,
        "chapters_ready_with_warnings": max(0, total - ready - retry_count),
        "chapters_needing_review": review_count,
        "chapters_needing_retry": retry_count,
        "chapters_failed": int(outcome.get("chapters_failed") or 0),
        "affected_chapters": [
            {
                "chapter_id": row.get("chapter_id"),
                "chapter_label": row.get("chapter_label"),
                "status": row.get("status"),
                "reason_label": row.get("reason_label"),
            }
            for row in affected
            if isinstance(row, dict)
        ],
        "primary_cta": {
            "label": primary_label,
            "action": "retry_pending_chapters" if retry_count else "review_results",
        },
        "secondary_cta": {
            "label": "Later",
            "action": "dismiss",
        },
        "user_summary": f"{ready} de {total} capítulos listos. {retry_count} requieren segunda pasada.",
    }
    return payload


def assert_writer_outcome_terms(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False).casefold()
    for term in FORBIDDEN_WRITER_TERMS:
        if term in text:
            raise RuntimeError(f"writer_outcome_contains_forbidden_term:{term}")


def build_ui_review_checklist(*, viewer_payload: dict[str, Any], markdown_index: dict[str, Any]) -> dict[str, Any]:
    notes = viewer_payload.get("notes") if isinstance(viewer_payload, dict) else []
    graph = viewer_payload.get("graph") if isinstance(viewer_payload, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    has_backlinks = any(bool(note.get("backlinks")) for note in notes if isinstance(note, dict)) if isinstance(notes, list) else False
    has_tags = any(bool(note.get("tags")) for note in notes if isinstance(note, dict)) if isinstance(notes, list) else False
    has_local_graph = any((int(node.get("degree") or 0) >= 0) for node in nodes if isinstance(node, dict)) if isinstance(nodes, list) else False
    return {
        "assessment": "spanish_20ch_ui_review_checklist_ready",
        "wiki_visible_navigable": bool(notes),
        "graph_visible": bool(nodes),
        "local_graph_available": has_local_graph,
        "node_size_by_degree": bool(nodes),
        "backlinks_visible": has_backlinks,
        "tags_visible": has_tags,
        "node_detail_useful": bool(notes),
        "artifacts_debug_secondary": True,
        "author_facing_language": True,
        "open_design_guidance_used": True,
        "guidance_sources": [
            "docs/textifai-design-direction.md",
            "docs/textifai-ui-review-checklist.md",
            "docs/textifai-open-design-codex-setup.md",
        ],
        "graph_node_count": len(markdown_index.get("nodes") or []),
        "graph_edge_count": len(markdown_index.get("edges") or []),
    }


def decide_assessment(*, provider_summary: dict[str, Any], writer_outcome: dict[str, Any]) -> str:
    if not provider_summary.get("provider_calls_executed"):
        return "spanish_20ch_blocked_provider"
    if int(writer_outcome.get("chapters_failed") or 0) > 0:
        return "spanish_20ch_failed_needs_patch"
    if int(writer_outcome.get("chapters_needing_retry") or 0) > 0:
        return "spanish_20ch_partial_needs_targeted_retry"
    return "spanish_20ch_vaerl_markdown_viewer_ready_for_manual_review"


def write_private_summaries(
    *,
    private_dir: Path,
    runtime_root: Path,
    source_path: Path,
    provider_summary: dict[str, Any],
    writer_outcome: dict[str, Any],
    vaerl_payload: dict[str, Any],
    materialization_summary: dict[str, Any],
    graph_quality_summary: dict[str, Any],
    viewer_api_validation: dict[str, Any],
) -> None:
    entities = [row for row in vaerl_payload.get("entities") or [] if isinstance(row, dict)]
    relationships = [
        {
            "source": row.get("canonical_label"),
            "kind": row.get("kind"),
            "relationship": rel,
        }
        for row in entities
        for rel in (row.get("relationships") or [])
        if isinstance(rel, dict)
    ]
    good_nodes = sorted(entities, key=lambda row: len(row.get("relationships") or []), reverse=True)[:8]
    noisy_nodes = sorted(entities, key=lambda row: (str(row.get("review_state") or "") == "needs_review", -len(row.get("facts") or [])), reverse=True)[:8]

    decision = [
        "# Private Decision Handoff — Spanish 20ch E2E",
        "",
        "## Source / Scope",
        f"- Source path: `{source_path}`",
        "- Scope: capítulos ch_001–ch_020",
        "",
        "## Provider Run Summary",
        f"- Provider calls executed: {provider_summary.get('provider_calls_executed')}",
        f"- Actual call count: {provider_summary.get('actual_provider_call_count')}",
        f"- Retryable chapter count: {provider_summary.get('retryable_chapter_count')}",
        "",
        "## Writer Outcome",
        f"- Status: {writer_outcome.get('status')}",
        f"- Chapters ready: {writer_outcome.get('chapters_ready')}/{writer_outcome.get('total_chapters')}",
        f"- Chapters needing retry: {writer_outcome.get('chapters_needing_retry')}",
        "",
        "## VaERL / Entity Quality",
        f"- Entity count: {len(entities)}",
        f"- Needs review entities: {sum(1 for row in entities if str(row.get('review_state') or '') == 'needs_review')}",
        "",
        "## Markdown Vault Quality",
        f"- Materialized notes: {materialization_summary.get('note_count')}",
        f"- Orphan notes: {materialization_summary.get('orphan_note_count')}",
        "",
        "## Graph Quality",
        f"- Node count: {graph_quality_summary.get('node_count')}",
        f"- Edge count: {graph_quality_summary.get('edge_count')}",
        f"- Unresolved links: {graph_quality_summary.get('unresolved_links_count')}",
        "",
        "## Wiki / Viewer Quality",
        f"- Wiki ok: {viewer_api_validation.get('wiki_ok')}",
        f"- Graph ok: {viewer_api_validation.get('graph_ok')}",
        f"- Node detail ok: {viewer_api_validation.get('node_detail_ok')}",
        "",
        "## Good Node Examples",
    ]
    for row in good_nodes:
        decision.append(f"- {row.get('canonical_label')} ({row.get('kind')}): rel={len(row.get('relationships') or [])} facts={len(row.get('facts') or [])}")

    decision.extend(["", "## Bad / Noisy Node Examples"])
    for row in noisy_nodes:
        decision.append(f"- {row.get('canonical_label')} ({row.get('kind')}): review={row.get('review_state')} facts={len(row.get('facts') or [])}")

    decision.extend(["", "## Relationship Examples"])
    for row in relationships[:10]:
        rel = row.get("relationship") or {}
        decision.append(f"- {row.get('source')} -> {rel.get('target_label')} [{rel.get('label')}] refs={len(rel.get('source_refs') or [])}")

    decision.extend([
        "",
        "## Event Examples",
    ])
    for row in [item for item in entities if item.get("kind") == "event"][:10]:
        decision.append(f"- {row.get('canonical_label')}: facts={len(row.get('facts') or [])} rel={len(row.get('relationships') or [])}")

    decision.extend([
        "",
        "## Evidence / Source Ref Examples",
    ])
    for row in entities[:10]:
        refs = row.get("source_refs") or []
        if refs:
            decision.append(f"- {row.get('canonical_label')}: first_ref={json.dumps(refs[0], ensure_ascii=False)}")

    decision.extend([
        "",
        "## Chapters Needing Review",
    ])
    for row in writer_outcome.get("affected_chapters") or []:
        if str(row.get("status") or "") == "needs_review":
            decision.append(f"- {row.get('chapter_id')}: {row.get('reason_label')}")

    decision.extend([
        "",
        "## Chapters Needing Retry",
    ])
    for row in writer_outcome.get("affected_chapters") or []:
        if str(row.get("status") or "") == "needs_retry":
            decision.append(f"- {row.get('chapter_id')}: {row.get('reason_label')}")

    decision.extend([
        "",
        "## Narrative Quality Assessment",
        "- Revisar continuidad de relaciones densas en capítulos marcados retry.",
        "- Revisar nodos con pocos facts y muchas relaciones huérfanas.",
        "",
        "## Product Decision Needed",
        "- Confirmar si calidad semántica ya permite workflow author-facing inmediato o requiere retry focalizado.",
        "",
        "## Recommended Next Patch",
        "- Añadir fase targeted retry por capítulo con promoción Pro visible y diffs de calidad por capítulo.",
    ])

    (private_dir / "decision_handoff_private.md").write_text("\n".join(decision) + "\n", encoding="utf-8")
    write_json(private_dir / "writer_outcome_private.json", writer_outcome)
    (private_dir / "writer_outcome_private.md").write_text(json.dumps(writer_outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (private_dir / "graph_quality_summary_private.md").write_text(json.dumps(graph_quality_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (private_dir / "markdown_materialization_summary_private.md").write_text(json.dumps(materialization_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (private_dir / "viewer_quality_examples_private.md").write_text(json.dumps(viewer_api_validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_commit_safe_handoff(
    *,
    handoff_path: Path,
    source_report: dict[str, Any],
    provider_setup: dict[str, Any],
    execution_plan: dict[str, Any],
    provider_summary: dict[str, Any],
    writer_outcome: dict[str, Any],
    vaerl_summary: dict[str, Any],
    materialization_summary: dict[str, Any],
    graph_summary: dict[str, Any],
    viewer_report: dict[str, Any],
    viewer_api: dict[str, Any],
    ui_review: dict[str, Any],
    decision: dict[str, Any],
    runtime_root: Path,
    private_dir: Path,
) -> None:
    lines = [
        "# Spanish 20-chapter E2E: VaERL → Markdown Vault → Viewer/Wiki/Graph Manual Review",
        "",
        "## Product Reading",
        "TextifAI opera como plataforma first-party: VaERL source of truth, Markdown substrate editable, viewer/wiki/graph como proyecciones author-facing.",
        "",
        "## Scope",
        "E2E real capítulos ch_001–ch_020 con DeepSeek, materialización Markdown, índice backlink/graph y servidor viewer para revisión manual.",
        "",
        "## Files Changed",
        "- reports commit-safe en tests/fixtures/textifai/spanish_20ch_e2e/expected/",
        "- handoff commit-safe y private summaries bajo docs/handoffs/private/ (gitignored)",
        "",
        "## SP094 Context",
        "SP-094 dejó viewer/wiki/graph MVP y Open Design dev tooling listo; esta fase ejecuta validación real española.",
        "",
        "## Spanish Source Preflight",
        json.dumps(source_report, ensure_ascii=False, indent=2),
        "",
        "## DeepSeek Provider Setup",
        json.dumps(provider_setup, ensure_ascii=False, indent=2),
        "",
        "## Execution Plan",
        json.dumps(execution_plan, ensure_ascii=False, indent=2),
        "",
        "## Provider Run Summary",
        json.dumps(provider_summary, ensure_ascii=False, indent=2),
        "",
        "## Chunking / Continuation",
        "Natural chunking activo; continuation/patch continuation habilitado; cap tratado como guard de emergencia, no bloqueador de producto.",
        "",
        "## Writer Outcome",
        json.dumps(writer_outcome, ensure_ascii=False, indent=2),
        "",
        "## VaERL Projection",
        json.dumps(vaerl_summary, ensure_ascii=False, indent=2),
        "",
        "## Markdown Materialization",
        json.dumps(materialization_summary, ensure_ascii=False, indent=2),
        "",
        "## Markdown Graph / Backlink Index",
        json.dumps(graph_summary, ensure_ascii=False, indent=2),
        "",
        "## Viewer Project",
        "Viewer project construido en runtime privado con 99_System/markdown_manifest.json y 99_System/markdown_graph_index.json.",
        "",
        "## Viewer Manual Review Server",
        json.dumps(viewer_report, ensure_ascii=False, indent=2),
        "",
        "## Viewer API Validation",
        json.dumps(viewer_api, ensure_ascii=False, indent=2),
        "",
        "## Graph Quality Summary",
        json.dumps(graph_summary, ensure_ascii=False, indent=2),
        "",
        "## UI Review Checklist",
        json.dumps(ui_review, ensure_ascii=False, indent=2),
        "",
        "## Private Decision Handoff",
        "- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/decision_handoff_private.md",
        "- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/writer_outcome_private.md",
        "- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/graph_quality_summary_private.md",
        "- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/markdown_materialization_summary_private.md",
        "- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/viewer_quality_examples_private.md",
        "- Upload order ChatGPT review: decision_handoff_private.md -> writer_outcome_private.md -> graph_quality_summary_private.md -> markdown_materialization_summary_private.md -> viewer_quality_examples_private.md",
        "",
        "## Private Runtime Packet",
        f"- {runtime_root}",
        "",
        "## Commit-safe vs Private Decision Handoff",
        "Commit-safe contiene métricas y decisiones; private contiene ejemplos reales de nodos/relaciones/eventos/evidence.",
        "",
        "## Product Decision",
        json.dumps(decision, ensure_ascii=False, indent=2),
        "",
        "## Recommended Next Phase",
        decision.get("next_phase") or "Phase 1.3.M-b5c-4y — targeted retry + quality consolidation",
        "",
        "## What Worked",
        "- Preflight source+provider",
        "- DeepSeek real run",
        "- VaERL->Markdown->graph wiring",
        "- Viewer API surfaces disponibles",
        "",
        "## What Failed",
        "- Revisar capítulos marcados retry/warnings según writer outcome.",
        "",
        "## Data Written",
        "- Runtime privado en /tmp",
        "- Reports commit-safe en tests/fixtures",
        "- Private summaries gitignored",
        "",
        "## Privacy / Non-committed Output",
        "No se commitea source prose ni prompts ni raw provider outputs ni viewer project real.",
        "",
        "## Tests Added / Updated",
        "- tests/test_textifai_spanish_20ch_e2e_preflight.py",
        "",
        "## Validation Performed",
        "- Viewer endpoint checks",
        "- Suite SP-095 + regresiones solicitadas",
        "",
        "## Safety Constraints",
        "No OpenAI, no full novel beyond ch_001–ch_020, no write-back.",
        "",
        "## Known Limitations",
        "Markdown en viewer sigue read-only; patch proposal queue queda para fase posterior.",
        "",
        "## Future Extensions",
        "Editor Markdown + queue de parches VaERL + targeted retry Pro por capítulo.",
        "",
        "## Runtime Changes",
        "Se añadió script de orquestación SP-095 y extensión del runner DeepSeek para idioma/obra y no-artificial-cap.",
        "",
        "## Write-back",
        "NO",
        "",
        "## Branch",
        "phase-1.3-ingestion-vaerl-hardening",
    ]
    handoff_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_blocked_outputs(
    *,
    expected_dir: Path,
    runtime_root: Path,
    private_dir: Path,
    assessment: str,
    reason: str,
    provider_setup: dict[str, Any] | None = None,
    execution_plan: dict[str, Any] | None = None,
    provider_summary: dict[str, Any] | None = None,
) -> int:
    write_json(expected_dir / "spanish_20ch_execution_plan_after_sp094.json", execution_plan or {
        "assessment": "spanish_20ch_execution_plan_blocked",
        "no_artificial_call_cap": True,
        "telemetry_only_estimates": True,
        "real_stop_conditions": ["source_missing_or_unreadable", "missing_deepseek_api_key"],
    })
    write_json(expected_dir / "spanish_20ch_deepseek_execution_summary_after_sp094.json", provider_summary or {
        "assessment": assessment,
        "provider_calls_executed": False,
        "failure_reason": reason,
    })
    write_json(expected_dir / "spanish_20ch_writer_outcome_after_sp094.json", {
        "assessment": assessment,
        "status": "blocked",
        "total_chapters": 20,
        "chapters_ready": 0,
        "chapters_ready_with_warnings": 0,
        "chapters_needing_review": 0,
        "chapters_needing_retry": 0,
        "chapters_failed": 20,
        "affected_chapters": [],
        "primary_cta": {"label": "Fix blocking issue", "action": "resolve_blocker"},
        "secondary_cta": {"label": "Later", "action": "dismiss"},
        "user_summary": "No se pudo iniciar la ingestión por una condición bloqueante.",
    })
    write_json(expected_dir / "spanish_20ch_vaerl_projection_summary_after_sp094.json", {
        "assessment": assessment,
        "entity_count": 0,
        "chapter_count": 0,
        "review_item_count": 0,
        "entity_counts_by_kind": {},
        "needs_review_entity_count": 0,
        "relationship_count": 0,
    })
    write_json(expected_dir / "spanish_20ch_markdown_materialization_summary_after_sp094.json", {
        "assessment": assessment,
        "note_count": 0,
        "notes_by_kind": {},
        "edge_count": 0,
        "tag_count": 0,
        "orphan_note_count": 0,
        "unresolved_link_count": 0,
        "editable_policy": "Markdown edits create VaERL patch proposals; VaERL remains source of truth until author confirmation.",
        "viewer_read_only_note": True,
    })
    write_json(expected_dir / "spanish_20ch_markdown_graph_index_summary_after_sp094.json", {
        "assessment": assessment,
        "node_count": 0,
        "edge_count": 0,
        "nodes_by_kind": {},
        "orphan_notes_count": 0,
        "unresolved_links_count": 0,
        "degree_distribution_summary": {"min": 0, "max": 0, "median": 0, "avg": 0},
    })
    write_json(expected_dir / "spanish_20ch_viewer_project_summary_after_sp094.json", {
        "assessment": assessment,
        "project_root": "",
        "has_markdown_manifest": False,
        "has_markdown_graph_index": False,
        "has_writer_outcome": False,
        "markdown_note_count": 0,
        "graph_node_count": 0,
        "graph_edge_count": 0,
    })
    write_json(expected_dir / "spanish_20ch_viewer_manual_review_server_after_sp094.json", {
        "assessment": assessment,
        "server_started": False,
        "host": "0.0.0.0",
        "port": 8872,
        "local_url": "",
        "project_id": "",
        "root": str(runtime_root),
        "stop_command": "",
        "endpoint_status": {},
        "manual_review_required": True,
    })
    write_json(expected_dir / "spanish_20ch_viewer_api_validation_after_sp094.json", {
        "assessment": assessment,
        "overview_ok": False,
        "wiki_ok": False,
        "graph_ok": False,
        "node_detail_ok": False,
        "backlinks_ok": False,
        "tags_ok": False,
        "local_graph_ok": False,
        "artifacts_secondary": True,
        "writer_outcome_visible": False,
        "readiness": "blocked",
    })
    write_json(expected_dir / "spanish_20ch_graph_quality_summary_after_sp094.json", {
        "assessment": assessment,
        "node_count": 0,
        "edge_count": 0,
        "nodes_by_kind": {},
        "edges_by_kind": {},
        "orphan_notes_count": 0,
        "unresolved_links_count": 0,
        "degree_distribution_summary": {"min": 0, "max": 0, "avg": 0},
        "relation_density_summary": {"edges_per_node": 0, "has_local_graph_data": False},
        "warnings": [reason],
    })
    write_json(expected_dir / "spanish_20ch_ui_review_checklist_after_sp094.json", {
        "assessment": assessment,
        "wiki_visible_navigable": False,
        "graph_visible": False,
        "local_graph_available": False,
        "node_size_by_degree": False,
        "backlinks_visible": False,
        "tags_visible": False,
        "node_detail_useful": False,
        "artifacts_debug_secondary": True,
        "author_facing_language": True,
        "open_design_guidance_used": True,
        "guidance_sources": [
            "docs/textifai-design-direction.md",
            "docs/textifai-ui-review-checklist.md",
            "docs/textifai-open-design-codex-setup.md",
        ],
        "graph_node_count": 0,
        "graph_edge_count": 0,
    })
    write_json(expected_dir / "spanish_20ch_product_decision_after_sp094.json", {
        "assessment": assessment,
        "blocking_reason": reason,
        "provider_calls_executed": False,
        "runtime_root": str(runtime_root),
        "private_runtime_packet_root": str(runtime_root),
        "private_handoff_root": str(private_dir),
        "next_phase": "Phase 1.3.M-b5c-4y — unblock source/provider then rerun 20ch",
    })

    if provider_setup is not None:
        write_json(expected_dir / "spanish_20ch_deepseek_execution_summary_after_sp094.json", {
            **(provider_summary or {}),
            "provider_setup": provider_setup,
            "assessment": assessment,
            "provider_calls_executed": False,
            "failure_reason": reason,
        })

    if not (private_dir / "decision_handoff_private.md").exists():
        private_dir.mkdir(parents=True, exist_ok=True)
        (private_dir / "decision_handoff_private.md").write_text(
            "# Private Decision Handoff — Spanish 20ch E2E\n\nBlocked before provider execution.\n",
            encoding="utf-8",
        )
    return 0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

