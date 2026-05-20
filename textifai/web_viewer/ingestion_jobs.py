from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
from dataclasses import asdict, dataclass, field
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
    log: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def append_log(self, chunk: str) -> None:
        with self._lock:
            self.log = (self.log + redact_log(chunk))[-MAX_LOG_CHARS:]

    def snapshot(self, *, log_tail_chars: int = 8000) -> dict[str, Any]:
        with self._lock:
            data = asdict(self)
            data.pop("_lock", None)
            data["log_tail"] = self.log[-log_tail_chars:]
            data.pop("log", None)
            return data


class IngestionJobRegistry:
    def __init__(self, *, repo_root: Path, output_root: Path = SAFE_OUTPUT_ROOT) -> None:
        self.repo_root = repo_root.resolve()
        self.output_root = (self.repo_root / output_root).resolve()
        self._jobs: dict[str, IngestionJob] = {}
        self._targets: set[str] = set()
        self._lock = threading.Lock()

    def create_job(self, payload: dict[str, Any]) -> IngestionJob:
        spec = build_ingestion_command(payload, repo_root=self.repo_root, output_root=self.output_root)
        job_id = f"ing_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(4)}"
        target = spec["output_root"]
        with self._lock:
            if target in self._targets:
                raise ValueError("duplicate job for output target")
            if Path(target).exists():
                raise ValueError("output target already exists")
            self._targets.add(target)
            job = IngestionJob(
                job_id=job_id,
                status="queued",
                created_at=utc_now(),
                output_root=target,
                command_preview=spec["args"],
                source_root=spec["source_root"],
                project_title=spec["project_title"],
                run_name=spec["run_name"],
            )
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def get_job(self, job_id: str) -> IngestionJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(job_id) from exc

    def _run_job(self, job: IngestionJob) -> None:
        job.status = "running"
        job.started_at = utc_now()
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
            job.exit_code = process.wait()
            job.finished_at = utc_now()
            if job.exit_code == 0:
                job.status = "succeeded"
                job.project_id = _project_id_from_output(output_path)
                job.append_log(f"Job succeeded at {job.finished_at}\n")
            else:
                job.status = "failed"
                job.error = f"command exited with code {job.exit_code}"
                job.append_log(f"Job failed at {job.finished_at}: {job.error}\n")
        except Exception as exc:  # pragma: no cover - defensive job boundary
            job.status = "failed"
            job.finished_at = utc_now()
            job.error = str(exc)
            job.append_log(f"Job failed before completion: {job.error}\n")


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


def job_to_json(job: IngestionJob) -> dict[str, Any]:
    return job.snapshot()


def log_json(job: IngestionJob, *, max_chars: int = 64_000) -> dict[str, Any]:
    with job._lock:
        return {"job_id": job.job_id, "log": job.log[-max_chars:]}
