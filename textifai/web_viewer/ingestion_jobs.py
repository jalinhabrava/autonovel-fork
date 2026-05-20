from __future__ import annotations

import os
import re
import secrets
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_OUTPUT_ROOT = Path("runs/web_ingestion")
MAX_LOG_CHARS = 160_000
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
    safe_output_root: str = str(SAFE_OUTPUT_ROOT)
    duplicate_key: str = ""
    log: str = ""
    log_size_bytes: int = 0
    log_truncated: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

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
    ) -> None:
        with self._lock:
            self.status = status
            self.finished_at = utc_now()
            self.exit_code = exit_code
            self.error = error
            self.project_id = project_id
            self.result_detected = result_detected
            self.result_warnings = list(result_warnings or [])
            self.review_queue_available = review_queue_available
            self.inspectable_artifacts_available = inspectable_artifacts_available
            self.result_status = result_status

    def snapshot(self, *, log_tail_chars: int = 8000) -> dict[str, Any]:
        with self._lock:
            data = {
                "job_id": self.job_id,
                "status": self.status,
                "created_at": self.created_at,
                "output_root": self.output_root,
                "command_preview": list(self.command_preview),
                "source_root": self.source_root,
                "project_title": self.project_title,
                "run_name": self.run_name,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "project_id": self.project_id,
                "error": self.error,
                "result_detected": self.result_detected,
                "result_warnings": list(self.result_warnings),
                "review_queue_available": self.review_queue_available,
                "inspectable_artifacts_available": self.inspectable_artifacts_available,
                "result_status": self.result_status,
                "safe_output_root": self.safe_output_root,
                "log_size_bytes": self.log_size_bytes,
                "log_truncated": self.log_truncated,
            }
            data["log_tail"] = self.log[-log_tail_chars:] if log_tail_chars > 0 else ""
            lines = [line for line in self.log.splitlines() if line.strip()]
            data["last_log_lines"] = lines[-12:]
            data["duration_seconds"] = _duration_seconds(data.get("started_at") or data.get("created_at"), data.get("finished_at"))
            data.pop("log", None)
            return data


class IngestionJobRegistry:
    def __init__(self, *, repo_root: Path, output_root: Path = SAFE_OUTPUT_ROOT, start_immediately: bool = True) -> None:
        self.repo_root = repo_root.resolve()
        self.output_root = (self.repo_root / output_root).resolve()
        self.start_immediately = start_immediately
        self._jobs: dict[str, IngestionJob] = {}
        self._targets: set[str] = set()
        self._active_keys: set[str] = set()
        self._lock = threading.Lock()

    def create_job(self, payload: dict[str, Any]) -> IngestionJob:
        spec = build_ingestion_command(payload, repo_root=self.repo_root, output_root=self.output_root)
        job_id = f"ing_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(4)}"
        target = spec["output_root"]
        duplicate_key = _duplicate_key(spec["source_root"], spec["project_title"], spec["run_name"])
        with self._lock:
            if duplicate_key in self._active_keys:
                raise ValueError("active job already exists for source/project/run combination")
            if target in self._targets:
                raise ValueError("duplicate job for output target")
            if Path(target).exists():
                raise ValueError("output target already exists")
            self._targets.add(target)
            self._active_keys.add(duplicate_key)
            job = IngestionJob(
                job_id=job_id,
                status="queued",
                created_at=utc_now(),
                output_root=target,
                command_preview=spec["args"],
                source_root=spec["source_root"],
                project_title=spec["project_title"],
                run_name=spec["run_name"],
                safe_output_root=str(self.output_root),
                duplicate_key=duplicate_key,
            )
            self._jobs[job_id] = job
        if self.start_immediately:
            thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
            thread.start()
        return job

    def list_jobs(self) -> list[IngestionJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id: str) -> IngestionJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(job_id) from exc

    def _run_job(self, job: IngestionJob) -> None:
        job.set_running()
        output_path = Path(job.output_root)
        try:
            output_path.mkdir(parents=True, exist_ok=False)
            log_path = output_path / "web_ingestion_job.log"
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
            if exit_code == 0:
                detection = detect_job_result(output_path)
                job.finalize(
                    status="succeeded",
                    exit_code=exit_code,
                    project_id=_project_id_from_output(output_path) if detection["result_detected"] else None,
                    result_detected=detection["result_detected"],
                    result_warnings=detection["result_warnings"],
                    review_queue_available=detection["review_queue_available"],
                    inspectable_artifacts_available=detection["inspectable_artifacts_available"],
                    result_status=detection["result_status"],
                )
                job.append_log(f"Job succeeded at {job.finished_at}\n")
            else:
                job.finalize(
                    status="failed",
                    exit_code=exit_code,
                    error=f"command exited with code {exit_code}",
                    result_detected=False,
                    result_warnings=["job exited without producing confirmed inspectable artifacts"],
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
            self._release_job(job)

    def _release_job(self, job: IngestionJob) -> None:
        with self._lock:
            self._active_keys.discard(job.duplicate_key)


def build_ingestion_command(payload: dict[str, Any], *, repo_root: Path, output_root: Path) -> dict[str, Any]:
    source_root_raw = str(payload.get("source_root") or "").strip()
    project_title = str(payload.get("project_title") or "").strip()
    run_name = str(payload.get("run_name") or "").strip()
    if not source_root_raw:
        raise ValueError("source_root is required")
    if not project_title:
        raise ValueError("project_title is required")
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
        "uv", "run", "python", "scripts/textifai.py", "init",
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
    }


def _project_id_from_output(output_path: Path) -> str:
    return output_path.resolve().as_posix()


def detect_job_result(output_path: Path) -> dict[str, Any]:
    system_root = output_path / "99_System"
    warnings: list[str] = []
    inspectable_artifacts_available = (system_root / "obsidian_import.json").exists()
    review_queue_available = (system_root / "review_queue.json").exists()
    if not system_root.exists():
        warnings.append("99_System directory not found; result may not be inspectable in viewer yet.")
    if system_root.exists() and not inspectable_artifacts_available:
        warnings.append("obsidian_import.json not found; result detection is incomplete.")
    if system_root.exists() and not review_queue_available:
        warnings.append("review_queue.json not found; review queue view may be unavailable.")
    result_detected = system_root.exists() and inspectable_artifacts_available
    result_status = "inspectable" if result_detected else "warning"
    return {
        "result_detected": result_detected,
        "result_warnings": warnings,
        "review_queue_available": review_queue_available,
        "inspectable_artifacts_available": inspectable_artifacts_available,
        "result_status": result_status,
    }


def _duplicate_key(source_root: str, project_title: str, run_name: str) -> str:
    return "||".join(
        [
            str(Path(source_root).resolve()).casefold(),
            str(project_title or "").strip().casefold(),
            sanitize_run_slug(run_name),
        ]
    )


def _duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return round(max((end_dt - start_dt).total_seconds(), 0.0), 3)


def job_to_json(job: IngestionJob) -> dict[str, Any]:
    return job.snapshot()


def jobs_list_json(jobs: list[IngestionJob]) -> dict[str, Any]:
    return {"jobs": [job.snapshot(log_tail_chars=0) for job in jobs]}


def log_json(job: IngestionJob, *, max_chars: int = 64_000) -> dict[str, Any]:
    with job._lock:
        log_value = job.log[-max_chars:]
        last_lines = deque(job.log.splitlines(), maxlen=30)
        return {
            "job_id": job.job_id,
            "log": log_value,
            "log_size_bytes": job.log_size_bytes,
            "log_truncated": job.log_truncated or len(job.log) > max_chars,
            "last_log_lines": list(last_lines),
        }
