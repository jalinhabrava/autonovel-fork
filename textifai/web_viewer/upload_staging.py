from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_UPLOAD_ROOT = Path('runs/web_ingestion_uploads')
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {'.md', '.txt'}
SUPPORTED_UPLOAD_CONTENT_TYPES = {
    '.md': 'text/markdown',
    '.txt': 'text/plain',
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_upload_session_id() -> str:
    return f"upl_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(4)}"


def _safe_under(parent: Path, candidate: Path) -> bool:
    parent_resolved = parent.resolve()
    candidate_resolved = candidate.resolve()
    return candidate_resolved == parent_resolved or parent_resolved in candidate_resolved.parents


def _is_hidden_or_system_filename(filename: str) -> bool:
    base = Path(filename).name
    return (
        not base
        or base.startswith('.')
        or base.startswith('._')
        or base in {'.DS_Store', 'Thumbs.db'}
    )


def _validate_filename(filename: str) -> tuple[str, str]:
    base = Path(filename).name
    if base != filename or any(part in {'..', ''} for part in Path(filename).parts):
        raise UploadValidationError('path traversal rejected', filename=filename)
    if _is_hidden_or_system_filename(base):
        raise UploadValidationError('hidden or system filenames rejected', filename=filename)
    suffix = base.lower().rsplit('.', 1)
    ext = f".{suffix[-1]}" if len(suffix) == 2 else ''
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        message = f"unsupported extension: {ext or 'unknown'}; accepted: .md, .txt"
        raise UploadValidationError(message, filename=filename, extension=ext or None)
    return base, ext


def _safe_content_type(extension: str) -> str:
    return SUPPORTED_UPLOAD_CONTENT_TYPES.get(extension, 'text/plain')


@dataclass
class StagedUploadFile:
    file_id: str
    filename: str
    size_bytes: int
    content_type: str
    status: str = 'staged'

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UploadSession:
    upload_session_id: str
    created_at: str
    files: list[StagedUploadFile]

    def to_json(self) -> dict[str, Any]:
        return {
            'upload_session_id': self.upload_session_id,
            'created_at': self.created_at,
            'files': [item.to_json() for item in self.files],
        }


def session_root(repo_root: Path, upload_session_id: str) -> Path:
    root = (repo_root / SAFE_UPLOAD_ROOT / upload_session_id).resolve()
    safe_root = (repo_root / SAFE_UPLOAD_ROOT).resolve()
    if not _safe_under(safe_root, root):
        raise ValueError('upload session root rejected')
    return root


def session_manifest_path(repo_root: Path, upload_session_id: str) -> Path:
    return session_root(repo_root, upload_session_id) / 'upload_session.json'


def save_upload_session(repo_root: Path, session: UploadSession) -> None:
    root = session_root(repo_root, session.upload_session_id)
    root.mkdir(parents=True, exist_ok=True)
    session_manifest_path(repo_root, session.upload_session_id).write_text(
        json.dumps(session.to_json(), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def load_upload_session(repo_root: Path, upload_session_id: str) -> UploadSession:
    payload = json.loads(session_manifest_path(repo_root, upload_session_id).read_text(encoding='utf-8'))
    files = [StagedUploadFile(**item) for item in payload.get('files', [])]
    return UploadSession(
        upload_session_id=str(payload['upload_session_id']),
        created_at=str(payload.get('created_at', '')),
        files=files,
    )


def stage_uploaded_files(repo_root: Path, uploads: list[tuple[str, bytes]]) -> UploadSession:
    if not uploads:
        raise UploadValidationError('at least one file required')
    upload_session_id = new_upload_session_id()
    root = session_root(repo_root, upload_session_id)
    root.mkdir(parents=True, exist_ok=False)
    staged_files: list[StagedUploadFile] = []
    for index, (filename, raw_bytes) in enumerate(uploads, start=1):
        base, ext = _validate_filename(filename)
        if not raw_bytes:
            raise UploadValidationError('empty files rejected', filename=filename, extension=ext)
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise UploadValidationError('file too large', filename=filename, extension=ext)
        file_id = f'file_{index:03d}'
        target = root / base
        if not _safe_under(root, target):
            raise ValueError('path traversal rejected')
        target.write_bytes(raw_bytes)
        staged_files.append(
            StagedUploadFile(
                file_id=file_id,
                filename=base,
                size_bytes=len(raw_bytes),
                content_type=_safe_content_type(ext),
            )
        )
    session = UploadSession(upload_session_id=upload_session_id, created_at=utc_now(), files=staged_files)
    save_upload_session(repo_root, session)
    return session


def upload_session_json(repo_root: Path, upload_session_id: str) -> dict[str, Any]:
    return load_upload_session(repo_root, upload_session_id).to_json()


def resolve_upload_session_source_root(repo_root: Path, upload_session_id: str) -> Path:
    session = load_upload_session(repo_root, upload_session_id)
    root = session_root(repo_root, session.upload_session_id)
    valid_files: list[Path] = []
    for item in session.files:
        filename = str(item.filename or '')
        try:
            base, _ = _validate_filename(filename)
        except UploadValidationError:
            continue
        candidate = root / base
        if _safe_under(root, candidate) and candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            valid_files.append(candidate)
    if not valid_files:
        raise UploadValidationError('upload session has no valid staged files')
    return root


INGESTION_JOB_STATUS_VALUES = [
    'queued',
    'running',
    'blocked',
    'completed',
    'completed_with_warnings',
    'failed',
    'cancelled',
]

INGESTION_STAGE_STATUS_VALUES = [
    'pending',
    'running',
    'completed',
    'warning',
    'blocked',
    'failed',
    'skipped',
]

INGESTION_STAGE_SNAPSHOT_SCHEMA = {
    'id': 'chapter_detection',
    'status': 'warning',
    'progress': 100,
    'summary': '3 chapters detected',
    'warnings': [],
    'errors': [],
    'actions': ['inspect', 'continue_with_warnings'],
}
class UploadValidationError(ValueError):
    def __init__(self, message: str, *, filename: str | None = None, extension: str | None = None) -> None:
        super().__init__(message)
        self.filename = filename
        self.extension = extension

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'error': 'upload_validation_failed',
            'message': str(self),
            'allowed_extensions': sorted(ALLOWED_UPLOAD_EXTENSIONS),
        }
        if self.filename is not None:
            payload['filename'] = self.filename
        if self.extension is not None:
            payload['extension'] = self.extension
        return payload
