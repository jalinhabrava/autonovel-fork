from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textifai.web_viewer.upload_staging import resolve_upload_session_source_root

SAFE_OUTPUT_ROOT = Path("runs/web_ingestion")
JOB_METADATA_FILE = "web_ingestion_job.json"
JOB_LOG_FILE = "web_ingestion_job.log"
MAX_LOG_CHARS = 160_000
ACTIVE_STATUSES = {"queued", "running"}
FINAL_STATUSES = {"succeeded", "failed"}
JOB_STAGE_STATUS_VALUES = ["pending", "running", "completed", "warning", "blocked", "failed", "skipped"]
JOB_STATUS_VALUES = ["queued", "running", "blocked", "completed", "completed_with_warnings", "failed", "cancelled"]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[=:]\s*)([^\s]+)"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_run_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)[:80]
    if not slug:
        raise ValueError("run_name must contain at least one alphanumeric character")
    return slug


def redact_log(text: str) -> str:
    redacted = str(text or "")
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)"):
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redacted_summary(value: Any) -> str | None:
    if value is None:
        return None
    text = redact_log(str(value).strip())
    return text or None


def _json_list_count(path: Path, key: str) -> int:
    payload = _read_json(path)
    if isinstance(payload, dict):
        items = payload.get(key)
        if isinstance(items, list):
            return len(items)
    return 0


def _bootstrap_progress_warnings(system_root: Path) -> list[str]:
    progress_path = system_root / "bootstrap_progress.jsonl"
    warnings: list[str] = []
    if not progress_path.exists():
        return warnings
    try:
        lines = progress_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return warnings
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_name = str(event.get("event") or "")
        if event_name == "chapter_extraction_failed":
            chapter = str(event.get("chapter_title") or event.get("chapter_id") or "chapter").strip()
            failure_type = str(event.get("failure_type") or "failed").strip()
            attempt_count = event.get("attempt_count")
            suffix = f" after {attempt_count} attempts" if attempt_count else ""
            warnings.append(f"Chapter extraction warning: {chapter} {failure_type}{suffix}")
        elif event_name == "global_normalization_batch_abandoned":
            chapter_ids = ", ".join(str(item) for item in event.get("chapter_ids") or [])
            warnings.append(f"Global normalization warning: abandoned batch {chapter_ids}".strip())
    return warnings[:12]


def _bootstrap_progress_snapshot(system_root: Path) -> dict[str, Any]:
    progress_path = system_root / "bootstrap_progress.jsonl"
    snapshot: dict[str, Any] = {
        "chapter_total": 0,
        "chapter_completed": 0,
        "normalization_total": 0,
        "normalization_completed": 0,
        "semantic_started": False,
    }
    if not progress_path.exists():
        return snapshot
    chapter_started: set[str] = set()
    chapter_done: set[str] = set()
    normalization_started: set[str] = set()
    normalization_done: set[str] = set()
    try:
        lines = progress_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return snapshot
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_name = str(event.get("event") or "")
        chapter_id = str(event.get("chapter_id") or "").strip()
        if event_name == "chapter_extraction_started" and chapter_id:
            chapter_started.add(chapter_id)
        elif event_name in {"chapter_extraction_completed", "chapter_extraction_failed"} and chapter_id:
            chapter_done.add(chapter_id)
        elif event_name == "global_normalization_batch_started":
            normalization_started.add(str(event.get("batch_index") or len(normalization_started) + 1))
            snapshot["semantic_started"] = True
        elif event_name in {"global_normalization_batch_completed", "global_normalization_batch_abandoned"}:
            normalization_done.add(str(event.get("batch_index") or len(normalization_done) + 1))
            snapshot["semantic_started"] = True
        elif event_name == "semantic_bootstrap_started":
            snapshot["semantic_started"] = True
    snapshot["chapter_total"] = max(len(chapter_started), len(chapter_done))
    snapshot["chapter_completed"] = len(chapter_done)
    snapshot["normalization_total"] = max(len(normalization_started), len(normalization_done))
    snapshot["normalization_completed"] = len(normalization_done)
    return snapshot


def _project_id_from_output(output_path: Path) -> str:
    return output_path.resolve().as_posix().replace("/", "__").strip("_")


def _resolve_uv_executable() -> str:
    configured = str(os.environ.get("UV") or "").strip()
    candidates = [configured, shutil.which("uv") or "", str(Path.home() / ".local" / "bin" / "uv")]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return "uv"


def _duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return round(max((end_dt - start_dt).total_seconds(), 0.0), 3)


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _safe_under(parent: Path, candidate: Path) -> bool:
    parent_resolved = parent.resolve()
    candidate_resolved = candidate.resolve()
    return candidate_resolved == parent_resolved or parent_resolved in candidate_resolved.parents


def _metadata_path_for_output(output_path: Path) -> Path:
    return output_path / JOB_METADATA_FILE


def _log_path_for_output(output_path: Path, relative: str | None = None) -> Path:
    return output_path / (relative or JOB_LOG_FILE)


def _tail_redacted_log(log_path: Path, *, max_chars: int) -> tuple[str, int, bool]:
    if not log_path.exists() or not log_path.is_file():
        return "", 0, False
    size = log_path.stat().st_size
    read_size = min(size, max_chars * 4 + 4096)
    with log_path.open("rb") as handle:
        if read_size and size > read_size:
            handle.seek(-read_size, os.SEEK_END)
        data = handle.read()
    decoded = data.decode("utf-8", errors="replace")
    redacted = redact_log(decoded)
    tail = redacted[-max_chars:]
    truncated = size > len(data) or len(redacted) > max_chars
    return tail, size, truncated


@dataclass
class IngestionJob:
    job_id: str
    status: str
    created_at: str
    output_root: str
    command_preview: list[str]
    source_root: str
    project_title: str
    run_name: str
    input_mode: str = "local_path"
    upload_session_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    project_id: str | None = None
    error: str | None = None
    result_detected: bool = False
    result_warnings: list[str] = field(default_factory=list)
    review_queue_available: bool = False
    inspectable_artifacts_available: bool = False
    result_status: str = "pending"
    artifact_availability: dict[str, bool] = field(default_factory=dict)
    project_package_ready: bool = False
    semantic_artifacts_available: bool = False
    semantic_status: str = "pending"
    semantic_artifact_counts: dict[str, int] = field(default_factory=dict)
    safe_output_root: str = str(SAFE_OUTPUT_ROOT)
    duplicate_key: str = ""
    restored_from_disk: bool = False
    log_path_relative: str = JOB_LOG_FILE
    metadata_path_relative: str = JOB_METADATA_FILE
    log: str = ""
    log_size_bytes: int = 0
    log_truncated: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add_warning(self, message: str) -> None:
        warning = str(message or "").strip()
        if not warning:
            return
        with self._lock:
            if warning not in self.result_warnings:
                self.result_warnings.append(warning)

    def append_log(self, chunk: str) -> None:
        with self._lock:
            safe_chunk = redact_log(chunk)
            self.log_size_bytes += len(safe_chunk.encode("utf-8", errors="replace"))
            combined = self.log + safe_chunk
            if len(combined) > MAX_LOG_CHARS:
                self.log_truncated = True
            self.log = combined[-MAX_LOG_CHARS:]

    def set_running(self) -> None:
        with self._lock:
            self.status = "running"
            self.started_at = utc_now()

    def finalize(
        self,
        *,
        status: str,
        exit_code: int | None = None,
        error: str | None = None,
        project_id: str | None = None,
        result_detected: bool = False,
        result_warnings: list[str] | None = None,
        review_queue_available: bool = False,
        inspectable_artifacts_available: bool = False,
        result_status: str = "pending",
        artifact_availability: dict[str, bool] | None = None,
        project_package_ready: bool = False,
        semantic_artifacts_available: bool = False,
        semantic_status: str = "pending",
        semantic_artifact_counts: dict[str, int] | None = None,
    ) -> None:
        with self._lock:
            merged_warnings = list(self.result_warnings)
            for warning in result_warnings or []:
                text = str(warning or "").strip()
                if text and text not in merged_warnings:
                    merged_warnings.append(text)
            self.status = status
            self.finished_at = utc_now()
            self.exit_code = exit_code
            self.error = _redacted_summary(error)
            self.project_id = project_id
            self.result_detected = result_detected
            self.result_warnings = merged_warnings
            self.review_queue_available = review_queue_available
            self.inspectable_artifacts_available = inspectable_artifacts_available
            self.result_status = result_status
            if artifact_availability is not None:
                self.artifact_availability = dict(artifact_availability)
            self.project_package_ready = project_package_ready
            self.semantic_artifacts_available = semantic_artifacts_available
            self.semantic_status = semantic_status
            if semantic_artifact_counts is not None:
                self.semantic_artifact_counts = dict(semantic_artifact_counts)

    def snapshot(self, *, log_tail_chars: int = 8000) -> dict[str, Any]:
        with self._lock:
            lines = [line for line in self.log.splitlines() if line.strip()]
            return {
                "job_id": self.job_id,
                "status": self.status,
                "created_at": self.created_at,
                "output_root": self.output_root,
                "command_preview": list(self.command_preview),
                "source_root": self.source_root,
                "project_title": self.project_title,
                "run_name": self.run_name,
                "input_mode": self.input_mode,
                "upload_session_id": self.upload_session_id,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration_seconds": _duration_seconds(self.started_at or self.created_at, self.finished_at),
                "exit_code": self.exit_code,
                "project_id": self.project_id,
                "error": self.error,
                "result_detected": self.result_detected,
                "result_warnings": list(self.result_warnings),
                "display_label": self.project_title or self.run_name or self.job_id,
                "result_summary": self.semantic_status if self.semantic_status != "pending" else (self.result_status or self.status),
                "review_queue_available": self.review_queue_available,
                "inspectable_artifacts_available": self.inspectable_artifacts_available,
                "result_status": self.result_status,
                "artifact_availability": dict(self.artifact_availability),
                "semantic_artifact_counts": dict(self.semantic_artifact_counts),
                "can_compare": bool(self.project_id and self.artifact_availability.get("obsidian_import.json")),
                "compare_unavailable_reason": _compare_unavailable_reason(self.project_id, self.artifact_availability),
                "comparability_manifest_available": bool(self.artifact_availability.get("run_comparability_manifest.json")),
                "project_package_ready": self.project_package_ready,
                "semantic_artifacts_available": self.semantic_artifacts_available or bool(self.artifact_availability.get("obsidian_import.json")),
                "semantic_status": self.semantic_status,
                "safe_output_root": self.safe_output_root,
                "restored_from_disk": self.restored_from_disk,
                "log_path_relative": self.log_path_relative,
                "metadata_path_relative": self.metadata_path_relative,
                "log_size_bytes": self.log_size_bytes,
                "log_truncated": self.log_truncated,
                "log_tail": self.log[-log_tail_chars:] if log_tail_chars > 0 else "",
                "last_log_lines": lines[-12:],
                "stage_status": _stage_status_snapshot(self),
            }


class IngestionJobRegistry:
    def __init__(self, *, repo_root: Path, output_root: Path = SAFE_OUTPUT_ROOT, start_immediately: bool = True) -> None:
        self.repo_root = repo_root.resolve()
        self.output_root = (self.repo_root / output_root).resolve()
        self.start_immediately = start_immediately
        self._jobs: dict[str, IngestionJob] = {}
        self._targets: set[str] = set()
        self._active_keys: set[str] = set()
        self._ignored_output_dirs_without_metadata = 0
        self._lock = threading.Lock()
        self._rehydrate_jobs()

    def create_job(self, payload: dict[str, Any]) -> IngestionJob:
        spec = build_ingestion_command(payload, repo_root=self.repo_root, output_root=self.output_root)
        job_id = f"ing_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(4)}"
        target = Path(spec["output_root"]).resolve()
        duplicate_key = _duplicate_key(spec["source_root"], spec["project_title"], spec["run_name"])

        with self._lock:
            if duplicate_key in self._active_keys:
                raise ValueError("active job already exists for source/project/run combination")
            if str(target) in self._targets:
                raise ValueError("duplicate job for output target")
            if target.exists():
                raise ValueError("output target already exists")
            target.mkdir(parents=True, exist_ok=False)
            job = IngestionJob(
                job_id=job_id,
                status="queued",
                created_at=utc_now(),
                output_root=str(target),
                command_preview=spec["args"],
                source_root=spec["source_root"],
                project_title=spec["project_title"],
                run_name=spec["run_name"],
                input_mode=str(spec.get("input_mode") or "local_path"),
                upload_session_id=str(spec.get("upload_session_id") or "") or None,
                safe_output_root=str(self.output_root),
                duplicate_key=duplicate_key,
            )
            self._jobs[job_id] = job
            self._targets.add(str(target))
            self._active_keys.add(duplicate_key)

        self._persist_job_metadata(job)
        if self.start_immediately:
            thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
            thread.start()
        return job

    def list_jobs(self) -> list[IngestionJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda item: item.created_at or "", reverse=True)

    def history_summary(self) -> dict[str, Any]:
        jobs = self.list_jobs()
        return {
            "job_count": len(jobs),
            "restored_count": sum(1 for job in jobs if job.restored_from_disk),
            "active_count": sum(1 for job in jobs if job.status in ACTIVE_STATUSES),
            "inspectable_count": sum(1 for job in jobs if job.result_detected or job.project_id),
            "failed_count": sum(1 for job in jobs if job.status == "failed"),
            "ignored_output_dirs_without_metadata": self._ignored_output_dirs_without_metadata,
            "approx_log_bytes": sum(int(job.log_size_bytes or 0) for job in jobs),
        }

    def get_job(self, job_id: str) -> IngestionJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(job_id) from exc

    def get_job_log(self, job_id: str, *, max_chars: int = 64_000) -> dict[str, Any]:
        return log_json(self.get_job(job_id), max_chars=max_chars)

    def _run_job(self, job: IngestionJob) -> None:
        job.set_running()
        self._persist_job_metadata(job)

        output_path = Path(job.output_root)
        log_path = _log_path_for_output(output_path, job.log_path_relative)
        try:
            job.append_log(f"Job {job.job_id} started at {job.started_at}\n")
            job.append_log(f"Output root: {job.output_root}\n")
            process = subprocess.Popen(
                job.command_preview,
                cwd=self.repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                bufsize=1,
                env=os.environ.copy(),
            )
            with log_path.open("a", encoding="utf-8") as handle:
                assert process.stdout is not None
                for line in process.stdout:
                    safe_line = redact_log(line)
                    handle.write(safe_line)
                    handle.flush()
                    job.append_log(safe_line)
            exit_code = process.wait()
            detection = detect_job_result(output_path)
            if exit_code == 0:
                post_warnings = list(detection["result_warnings"])
                if not detection["result_detected"]:
                    post_warnings.append("process exited with code 0 but inspectable result was not fully detected")
                job.artifact_availability = dict(detection["artifact_availability"])
                job.finalize(
                    status="succeeded",
                    exit_code=exit_code,
                    project_id=_project_id_from_output(output_path) if detection["project_openable"] else None,
                    result_detected=detection["result_detected"],
                    result_warnings=post_warnings,
                    review_queue_available=detection["review_queue_available"],
                    inspectable_artifacts_available=detection["inspectable_artifacts_available"],
                    result_status=detection["result_status"],
                    artifact_availability=dict(detection["artifact_availability"]),
                    project_package_ready=bool(detection.get("project_package_ready")),
                    semantic_artifacts_available=bool(detection.get("semantic_artifacts_available")),
                    semantic_status=str(detection.get("semantic_status") or "pending"),
                    semantic_artifact_counts=dict(detection.get("semantic_artifact_counts") or {}),
                )
                job.append_log(f"Job succeeded at {job.finished_at}\n")
            else:
                job.artifact_availability = dict(detection["artifact_availability"])
                job.finalize(
                    status="failed",
                    exit_code=exit_code,
                    error=f"command exited with code {exit_code}",
                    project_id=_project_id_from_output(output_path) if detection["project_openable"] else None,
                    result_detected=detection["result_detected"],
                    result_warnings=detection["result_warnings"],
                    review_queue_available=detection["review_queue_available"],
                    inspectable_artifacts_available=detection["inspectable_artifacts_available"],
                    result_status="failed",
                )
                job.append_log(f"Job failed at {job.finished_at}: {job.error}\n")
        except Exception as exc:  # pragma: no cover - defensive job boundary
            job.finalize(
                status="failed",
                error=str(exc),
                result_detected=False,
                result_warnings=["job failed before inspectable result detection"],
                result_status="failed",
            )
            job.append_log(f"Job failed before completion: {job.error}\n")
        finally:
            self._persist_job_metadata(job)
            self._release_job(job)

    def _release_job(self, job: IngestionJob) -> None:
        with self._lock:
            self._active_keys.discard(job.duplicate_key)

    def _persist_job_metadata(self, job: IngestionJob) -> None:
        output_path = Path(job.output_root).resolve()
        if not _safe_under(self.output_root, output_path):
            job.add_warning("job metadata persistence skipped: output root escaped safe root")
            return
        metadata_path = _metadata_path_for_output(output_path)
        payload = _job_metadata_payload(job)
        try:
            _write_json_atomic(metadata_path, payload)
        except Exception as exc:  # pragma: no cover - defensive persistence boundary
            job.add_warning(f"job metadata persistence failed: {redact_log(str(exc))}")

    def _rehydrate_jobs(self) -> None:
        if not self.output_root.exists():
            return
        metadata_dirs = {
            metadata_path.parent.resolve()
            for metadata_path in self.output_root.glob(f"*/{JOB_METADATA_FILE}")
            if metadata_path.is_file()
        }
        all_dirs = {path.resolve() for path in self.output_root.iterdir() if path.is_dir()}
        self._ignored_output_dirs_without_metadata = len([path for path in all_dirs if path not in metadata_dirs])
        seen_ids: set[str] = set()
        seen_outputs: set[str] = set()
        metadata_files = sorted((path / JOB_METADATA_FILE for path in all_dirs if (path / JOB_METADATA_FILE).exists()), key=lambda item: item.stat().st_mtime, reverse=True)
        for metadata_path in metadata_files:
            data = _read_json(metadata_path)
            if not isinstance(data, dict):
                continue
            output_path = Path(str(data.get("output_root") or metadata_path.parent)).resolve()
            if not _safe_under(self.output_root, output_path):
                continue
            job_id = str(data.get("job_id") or f"rehydrated_{metadata_path.parent.name}").strip()
            if not job_id:
                continue
            output_key = str(output_path)
            if job_id in seen_ids or output_key in seen_outputs:
                continue

            raw_status = str(data.get("status") or "failed").strip().lower()
            status = raw_status if raw_status in ACTIVE_STATUSES.union(FINAL_STATUSES) else "failed"
            stale_warning = "server restarted while job was active; status cannot be trusted"
            warnings = _coerce_string_list(data.get("result_warnings"))
            if status in ACTIVE_STATUSES:
                status = "failed"
                if stale_warning not in warnings:
                    warnings.append(stale_warning)

            detection = detect_job_result(output_path)
            for warning in detection["result_warnings"]:
                if warning not in warnings:
                    warnings.append(warning)

            log_path_relative = str(data.get("log_path_relative") or JOB_LOG_FILE)
            log_path = _log_path_for_output(output_path, log_path_relative)
            log_size = log_path.stat().st_size if log_path.exists() and log_path.is_file() else 0

            project_id = str(data.get("project_id") or "").strip() or None
            if detection["project_openable"] and not project_id:
                project_id = _project_id_from_output(output_path)
            if not detection["project_openable"]:
                project_id = None

            job = IngestionJob(
                job_id=job_id,
                status=status,
                created_at=str(data.get("created_at") or ""),
                output_root=output_key,
                command_preview=[str(arg) for arg in (data.get("command_preview") or []) if str(arg)],
                source_root=str(data.get("source_root") or ""),
                project_title=str(data.get("project_title") or ""),
                run_name=str(data.get("run_name") or ""),
                input_mode=str(data.get("input_mode") or "local_path"),
                upload_session_id=str(data.get("upload_session_id") or "") or None,
                started_at=str(data.get("started_at") or "") or None,
                finished_at=str(data.get("finished_at") or "") or None,
                exit_code=_coerce_int(data.get("exit_code")),
                project_id=project_id,
                error=_redacted_summary(data.get("error")),
                result_detected=detection["result_detected"],
                result_warnings=warnings,
                review_queue_available=detection["review_queue_available"],
                inspectable_artifacts_available=detection["inspectable_artifacts_available"],
                result_status=("warning" if status == "failed" and stale_warning in warnings else detection["result_status"]),
                artifact_availability=dict(detection["artifact_availability"]),
                project_package_ready=bool(detection.get("project_package_ready")),
                semantic_artifacts_available=bool(detection.get("semantic_artifacts_available")),
                semantic_status=str(detection.get("semantic_status") or "pending"),
                semantic_artifact_counts=dict(detection.get("semantic_artifact_counts") or {}),
                safe_output_root=str(self.output_root),
                duplicate_key=f"rehydrated::{job_id}",
                restored_from_disk=True,
                log_path_relative=log_path_relative,
                metadata_path_relative=JOB_METADATA_FILE,
                log_size_bytes=log_size,
                log_truncated=bool(data.get("log_truncated") or False),
            )
            self._jobs[job_id] = job
            self._targets.add(output_key)
            seen_ids.add(job_id)
            seen_outputs.add(output_key)


def build_ingestion_command(payload: dict[str, Any], *, repo_root: Path, output_root: Path) -> dict[str, Any]:
    source_root_raw = str(payload.get("source_root") or "").strip()
    upload_session_id = str(payload.get("upload_session_id") or "").strip()
    project_title = str(payload.get("project_title") or "").strip()
    run_name = str(payload.get("run_name") or "").strip()
    if bool(source_root_raw) == bool(upload_session_id):
        raise ValueError("exactly one of source_root or upload_session_id is required")
    if not project_title:
        raise ValueError("project_title is required")

    input_mode = "upload_session" if upload_session_id else "local_path"
    if upload_session_id:
        source_root = resolve_upload_session_source_root(repo_root, upload_session_id).resolve()
    else:
        source_root = Path(source_root_raw).expanduser().resolve()
    if not source_root.exists():
        raise ValueError("source_root does not exist")
    if not source_root.is_dir():
        raise ValueError("source_root must be a directory")

    slug = sanitize_run_slug(run_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = (output_root / f"{timestamp}_{slug}").resolve()
    if output_root.resolve() not in target.parents:
        raise ValueError("output target escapes safe output root")
    if target.exists():
        raise ValueError("output target already exists")

    args = [
        _resolve_uv_executable(), "run", "python", "scripts/textifai.py", "init",
        "--vault-root", str(target),
        "--source-root", str(source_root),
        "--project-title", project_title,
    ]

    primary_language = str(payload.get("primary_language") or "").strip()
    if primary_language:
        args.extend(["--primary-language", primary_language])

    working_languages = payload.get("working_languages") or []
    if isinstance(working_languages, str):
        working_languages = [item.strip() for item in working_languages.split(",") if item.strip()]
    for language in working_languages:
        value = str(language or "").strip()
        if value:
            args.extend(["--working-language", value])

    if payload.get("skip_plugin_install", True) is not False:
        args.append("--skip-plugin-install")

    return {
        "args": args,
        "output_root": str(target),
        "source_root": str(source_root),
        "project_title": project_title,
        "run_name": slug,
        "input_mode": input_mode,
        "upload_session_id": upload_session_id or None,
    }


def detect_job_result(output_path: Path) -> dict[str, Any]:
    system_root = output_path / "99_System"
    project_manifest = output_path / "textifai.project.json"
    markdown_manifest = system_root / "markdown_manifest.json"
    markdown_graph_index = system_root / "markdown_graph_index.json"
    writer_outcome = system_root / "writer_outcome.json"
    semantic_artifact_paths = {
        "entities.json": output_path / "vaerl" / "entities.json",
        "relationships.json": output_path / "vaerl" / "relationships.json",
        "graph.json": output_path / "graph" / "graph.json",
    }
    artifact_names = [
        "obsidian_import.json",
        "review_queue.json",
        "semantic_invariants_audit.json",
        "run_comparability_manifest.json",
    ]
    artifact_availability = {name: (system_root / name).exists() for name in artifact_names}
    project_package_ready = project_manifest.exists() and markdown_manifest.exists() and markdown_graph_index.exists() and writer_outcome.exists()

    warnings: list[str] = []
    inspectable_artifacts_available = artifact_availability["obsidian_import.json"]
    review_queue_available = artifact_availability["review_queue.json"]
    semantic_artifacts_available = all(path.exists() for path in semantic_artifact_paths.values()) or inspectable_artifacts_available
    semantic_artifact_counts = {
        "entities": _json_list_count(semantic_artifact_paths["entities.json"], "entities"),
        "relationships": _json_list_count(semantic_artifact_paths["relationships.json"], "relationships"),
        "graph_nodes": len((_read_json(semantic_artifact_paths["graph.json"]) or {}).get("nodes") or []) if isinstance(_read_json(semantic_artifact_paths["graph.json"]), dict) else 0,
        "graph_edges": len((_read_json(semantic_artifact_paths["graph.json"]) or {}).get("edges") or []) if isinstance(_read_json(semantic_artifact_paths["graph.json"]), dict) else 0,
        "review_items": _json_list_count(output_path / "vaerl" / "review_queue.json", "items"),
    }
    semantic_status = "semantic_ready" if semantic_artifacts_available else ("structural_only" if project_package_ready else "pending")

    if not system_root.exists():
        warnings.append("99_System directory not found; result may not be inspectable in viewer yet")
    if system_root.exists() and not inspectable_artifacts_available and not project_package_ready:
        warnings.append("obsidian_import.json not found; result detection is incomplete")
    if system_root.exists() and not review_queue_available and not project_package_ready:
        warnings.append("review_queue.json not found; review queue view may be unavailable")
    for warning in _bootstrap_progress_warnings(system_root):
        if warning not in warnings:
            warnings.append(warning)

    project_openable = system_root.exists() and (inspectable_artifacts_available or review_queue_available or project_package_ready)
    result_detected = system_root.exists() and (inspectable_artifacts_available or project_package_ready)
    result_status = "inspectable" if result_detected else "warning"

    return {
        "result_detected": result_detected,
        "project_openable": project_openable,
        "result_warnings": warnings,
        "review_queue_available": review_queue_available,
        "inspectable_artifacts_available": inspectable_artifacts_available,
        "project_package_ready": project_package_ready,
        "semantic_artifacts_available": semantic_artifacts_available,
        "semantic_status": semantic_status,
        "semantic_artifact_counts": semantic_artifact_counts,
        "artifact_availability": artifact_availability,
        "result_status": result_status,
    }


def _duplicate_key(source_root: str, project_title: str, run_name: str) -> str:
    run_fragment = sanitize_run_slug(run_name or "run")
    return "||".join(
        [
            str(Path(source_root).resolve()).casefold(),
            str(project_title or "").strip().casefold(),
            run_fragment,
        ]
    )


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compare_unavailable_reason(project_id: str | None, artifact_availability: dict[str, bool]) -> str | None:
    if not project_id:
        return "project_id missing"
    if not artifact_availability.get("obsidian_import.json"):
        return "obsidian_import.json missing"
    return None


def _job_global_status(job: IngestionJob) -> str:
    if job.status == "queued":
        return "queued"
    if job.status == "running":
        return "running"
    if job.status == "failed":
        return "failed"
    if job.status == "succeeded":
        return "completed_with_warnings" if job.result_warnings else "completed"
    return "failed"

def _build_stage(
    stage_id: str,
    label: str,
    status: str,
    *,
    progress: int | None,
    summary: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "label": label,
        "status": status if status in JOB_STAGE_STATUS_VALUES else "pending",
        "progress": progress,
        "summary": summary,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "retry_count": 0,
        "actions": list(actions or []),
    }

def _stage_status_snapshot(job: IngestionJob) -> dict[str, Any]:
    warnings = list(job.result_warnings)
    errors = [job.error] if job.error else []
    stages: list[dict[str, Any]] = []
    progress = _bootstrap_progress_snapshot(Path(job.output_root) / "99_System") if getattr(job, "output_root", None) else {}

    is_upload = job.input_mode == "upload_session"
    is_running = job.status == "running"
    is_succeeded = job.status == "succeeded"
    is_failed = job.status == "failed"
    has_artifacts = bool(job.result_detected or job.project_id)
    semantic_status_value = str(getattr(job, "semantic_status", "pending") or "pending")

    def phase_status(*, before_done: bool = False) -> str:
        if is_failed:
            return "failed"
        if is_succeeded:
            return "completed"
        if is_running:
            return "running" if not before_done else "completed"
        if before_done:
            return "completed"
        if has_artifacts:
            return "completed"
        return "pending"

    def phase_progress(status: str) -> int | None:
        if status == "completed":
            return 100
        if status == "running":
            return None
        if status in {"failed", "blocked"}:
            return 0
        return 0

    if is_upload:
        stages.append(
            _build_stage(
                "preparing_manuscript",
                "Preparing manuscript",
                "completed",
                progress=100,
                summary="Files are staged under controlled upload root",
                actions=["inspect"],
            )
        )

    chapter_total = int(progress.get("chapter_total") or 0)
    chapter_completed = int(progress.get("chapter_completed") or 0)
    chapter_progress = int(round((chapter_completed / chapter_total) * 100)) if chapter_total else (100 if is_succeeded else 0)
    chapter_status = "completed" if is_succeeded and chapter_total and chapter_completed >= chapter_total else ("running" if job.status in {"queued", "running"} else "completed")
    chapter_summary = (
        f"{chapter_completed}/{chapter_total} chapters extracted" if chapter_total else (
            "Job accepted and waiting for subprocess execution" if job.status == "queued" else "Chapter detection finished"
        )
    )
    stages.append(_build_stage("detecting_chapters", "Detecting chapters", chapter_status, progress=chapter_progress, summary=chapter_summary, actions=["inspect"]))

    normalization_total = int(progress.get("normalization_total") or 0)
    normalization_completed = int(progress.get("normalization_completed") or 0)
    semantic_progress = int(round((normalization_completed / normalization_total) * 100)) if normalization_total else (100 if semantic_status_value == "semantic_ready" else (50 if progress.get("semantic_started") else 0))
    running_status = "completed" if is_succeeded else ("running" if job.status == "running" or chapter_total or chapter_completed else "pending")
    running_progress = chapter_progress if running_status != "pending" else 0
    running_summary = f"{chapter_completed}/{chapter_total or '?'} chapters extracted" if chapter_total else ("Ingestion is running" if running_status == "running" else "Ingestion has not started yet")
    stages.append(_build_stage("writing_markdown", "Creating markdown chapters", running_status, progress=running_progress, summary=running_summary, errors=errors if running_status == "failed" else [], actions=["inspect"]))

    semantic_has_progress = bool(progress.get("semantic_started") or normalization_total or normalization_completed)
    artifact_status = (
        "warning"
        if is_succeeded and (semantic_status_value != "semantic_ready" or not has_artifacts)
        else ("completed" if semantic_status_value == "semantic_ready" and has_artifacts and not is_failed else ("running" if (is_running or semantic_has_progress) else ("failed" if is_failed else "pending")))
    )
    artifact_summary = f"Semantic normalization {normalization_completed}/{normalization_total or '?'} batches" if normalization_total else ("Inspectable artifacts detected under 99_System" if artifact_status == "completed" else ("Inspectable artifacts not detected yet" if artifact_status == "pending" else "Inspectable artifacts not detected"))
    artifact_warnings = warnings if warnings and artifact_status == "completed" else []
    artifact_errors = errors if artifact_status == "failed" else []
    stages.append(_build_stage("extracting_entities", "Extracting entities and relations", artifact_status, progress=semantic_progress if artifact_status != "pending" else 0, summary=artifact_summary, warnings=artifact_warnings, errors=artifact_errors, actions=["inspect"]))

    ready_status = "completed" if job.project_id else ("warning" if is_succeeded else ("failed" if is_failed else ("running" if is_running else "pending")))
    ready_progress = 100 if ready_status in {"completed", "warning"} else 0
    ready_summary = "Project is ready for viewer inspection" if ready_status == "completed" else ("Project was not materialized into ready viewer state" if ready_status == "failed" else "Project not ready yet")
    ready_warnings = []
    ready_errors = errors if ready_status == "failed" else []
    stages.append(_build_stage("building_vaerl", "Building VaERL", ready_status, progress=ready_progress, summary=ready_summary, warnings=ready_warnings, errors=ready_errors, actions=["inspect"] if (job.project_id or job.error or warnings or is_succeeded) else []))

    semantic_status = semantic_status_value
    semantic_counts = getattr(job, "semantic_artifact_counts", {}) if isinstance(getattr(job, "semantic_artifact_counts", {}), dict) else {}
    semantic_detail = f"entities={semantic_counts.get('entities', 0)}; relationships={semantic_counts.get('relationships', 0)}; graph_nodes={semantic_counts.get('graph_nodes', 0)}; graph_edges={semantic_counts.get('graph_edges', 0)}; review_items={semantic_counts.get('review_items', 0)}"
    semantic_phase_status = (
        "completed"
        if semantic_status == "semantic_ready"
        else (
            "warning"
            if is_succeeded and (semantic_status == "structural_only" or warnings)
            else ("failed" if is_failed else ("running" if is_running else "pending"))
        )
    )
    normalized_status = semantic_phase_status
    stages.append(_build_stage("normalizing_entities", "Normalizing entities and aliases", normalized_status, progress=100 if normalized_status == "completed" else (None if normalized_status == "running" else 0), summary=("Entities and aliases normalized" if normalized_status == "completed" else ("Entities and aliases not finalized" if normalized_status == "warning" else "Entities and aliases not ready yet")) + (f"; {semantic_detail}" if normalized_status == "warning" else ""), warnings=warnings if normalized_status == "warning" else [], errors=errors if normalized_status == "failed" else [], actions=["inspect"]))
    stages.append(_build_stage("building_graph", "Generating graph", normalized_status, progress=100 if normalized_status == "completed" else (None if normalized_status == "running" else 0), summary=("Graph generated" if normalized_status == "completed" else ("Graph not generated yet" if normalized_status == "warning" else "Graph not ready yet")) + (f"; {semantic_detail}" if normalized_status == "warning" else ""), warnings=warnings if normalized_status == "warning" else [], errors=errors if normalized_status == "failed" else [], actions=["inspect"]))
    stages.append(_build_stage("building_review_queue", "Creating review queue", normalized_status, progress=100 if normalized_status == "completed" else (None if normalized_status == "running" else 0), summary=("Review queue created" if normalized_status == "completed" else ("Review queue not created yet" if normalized_status == "warning" else "Review queue not ready yet")) + (f"; {semantic_detail}" if normalized_status == "warning" else ""), warnings=warnings if normalized_status == "warning" else [], errors=errors if normalized_status == "failed" else [], actions=["inspect"]))
    stages.append(_build_stage("validating_project", "Validating project", normalized_status, progress=100 if normalized_status == "completed" else (None if normalized_status == "running" else 0), summary=("Project validated" if normalized_status == "completed" else ("Project not validated yet" if normalized_status == "warning" else "Project not ready yet")) + (f"; {semantic_detail}" if normalized_status == "warning" else ""), warnings=warnings if normalized_status == "warning" else [], errors=errors if normalized_status == "failed" else [], actions=["inspect"]))
    stages.append(_build_stage("workspace_ready", "Workspace ready", "completed" if job.project_id else ("warning" if ready_status == "warning" else ("failed" if is_failed else ("running" if is_running else "pending"))), progress=100 if job.project_id else (None if is_running else 0), summary="Workspace ready to open" if job.project_id else ("Run finished but workspace is not ready" if ready_status == "warning" else ("Workspace not ready" if is_failed else "Workspace not ready yet")), warnings=warnings if not job.project_id and ready_status == "warning" else [], errors=errors if is_failed else [], actions=["inspect"] if (job.project_id or job.error or warnings or is_succeeded) else []))

    current_stage_id = "detecting_chapters"
    for stage in stages:
        current_stage_id = stage["id"]
        if stage["status"] in {"running", "failed", "warning", "pending"}:
            break

    global_status = _job_global_status(job)
    project_ready = bool(job.project_id)
    progress = 100 if global_status in {"completed", "completed_with_warnings"} and project_ready else (None if global_status in {"running", "completed_with_warnings"} else 0)
    return {
        "schema": "textifai.ingestion_job_progress.v1",
        "global_status": global_status,
        "current_stage_id": current_stage_id,
        "project_ready": project_ready,
        "progress": progress,
        "stages": stages,
    }

def _job_metadata_payload(job: IngestionJob) -> dict[str, Any]:
    snapshot = job.snapshot(log_tail_chars=0)
    return {
        "job_id": snapshot["job_id"],
        "status": snapshot["status"],
        "created_at": snapshot["created_at"],
        "started_at": snapshot["started_at"],
        "finished_at": snapshot["finished_at"],
        "duration_seconds": snapshot["duration_seconds"],
        "exit_code": snapshot["exit_code"],
        "project_title": snapshot["project_title"],
        "source_root": snapshot["source_root"],
        "input_mode": snapshot["input_mode"],
        "upload_session_id": snapshot["upload_session_id"],
        "output_root": snapshot["output_root"],
        "safe_output_root": snapshot["safe_output_root"],
        "command_preview": snapshot["command_preview"],
        "result_detected": snapshot["result_detected"],
        "result_status": snapshot["result_status"],
        "artifact_availability": snapshot["artifact_availability"],
        "can_compare": snapshot["can_compare"],
        "compare_unavailable_reason": snapshot["compare_unavailable_reason"],
        "comparability_manifest_available": snapshot["comparability_manifest_available"],
        "semantic_artifacts_available": snapshot["semantic_artifacts_available"],
        "result_warnings": snapshot["result_warnings"],
        "inspectable_artifacts_available": snapshot["inspectable_artifacts_available"],
        "review_queue_available": snapshot["review_queue_available"],
        "project_id": snapshot["project_id"],
        "error": _redacted_summary(snapshot["error"]),
        "run_name": snapshot["run_name"],
        "stage_status": snapshot["stage_status"],
        "log_path_relative": snapshot["log_path_relative"],
        "restored_from_disk": snapshot["restored_from_disk"],
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def job_to_json(job: IngestionJob) -> dict[str, Any]:
    return job.snapshot()


def jobs_list_json(jobs: list[IngestionJob]) -> dict[str, Any]:
    return {"jobs": [job.snapshot(log_tail_chars=0) for job in jobs]}


def jobs_history_json(registry: IngestionJobRegistry) -> dict[str, Any]:
    jobs = registry.list_jobs()
    return {
        "jobs": [job.snapshot(log_tail_chars=0) for job in jobs],
        "summary": registry.history_summary(),
    }


def log_json(job: IngestionJob, *, max_chars: int = 64_000) -> dict[str, Any]:
    with job._lock:
        memory_log = job.log
        memory_size = job.log_size_bytes
        memory_truncated = job.log_truncated

    if memory_log:
        tail = memory_log[-max_chars:]
        lines = deque(memory_log.splitlines(), maxlen=30)
        return {
            "job_id": job.job_id,
            "log": tail,
            "log_size_bytes": memory_size,
            "log_truncated": memory_truncated or len(memory_log) > max_chars,
            "last_log_lines": list(lines),
            "log_source": "memory",
            "warning": None,
        }

    output_path = Path(job.output_root)
    log_path = _log_path_for_output(output_path, job.log_path_relative)
    if not log_path.exists() or not log_path.is_file():
        return {
            "job_id": job.job_id,
            "log": "",
            "log_size_bytes": 0,
            "log_truncated": False,
            "last_log_lines": [],
            "log_source": "missing",
            "warning": "persisted log file not found for this job",
        }

    tail, size, truncated = _tail_redacted_log(log_path, max_chars=max_chars)
    lines = deque(tail.splitlines(), maxlen=30)
    return {
        "job_id": job.job_id,
        "log": tail,
        "log_size_bytes": size,
        "log_truncated": truncated,
        "last_log_lines": list(lines),
        "log_source": "persisted",
        "warning": None,
    }
