from __future__ import annotations

import json
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from vault.notes import write_or_update_note, write_root_artifact_note
from vault.schema import NOTE_STATUSES, VAULT_SCHEMA_VERSION, slugify


ROOT_ARTIFACTS = {"seed", "mystery", "voice", "world", "characters", "outline", "canon", "manuscript", "arc_summary"}
STRUCTURED_NOTE_TYPES = {"character", "concept", "event", "scene", "decision", "review", "reader_panel", "revision_brief"}


def import_existing_chapters(
    vault_root: str | Path,
    source_dir: str | Path,
    *,
    pattern: str = "*.md",
    status: str = "pending_revision",
    source_label: str = "existing_manuscript",
) -> list[Path]:
    if status not in NOTE_STATUSES:
        raise ValueError(f"Invalid note status {status!r}. Expected one of {NOTE_STATUSES}.")

    adapter = VaultProjectAdapter(vault_root)
    source_root = Path(source_dir)
    imported_paths: list[Path] = []

    for index, source_path in enumerate(sorted(source_root.glob(pattern)), start=1):
        if not source_path.is_file():
            continue
        title = _title_from_markdown(source_path, fallback=f"Chapter {index:02d}")
        chapter_path = adapter.chapter_path(index)
        chapter_path.parent.mkdir(parents=True, exist_ok=True)
        body = source_path.read_text().strip()
        metadata = {
            "source": source_label,
            "source_path": str(source_path),
            "origin_type": "existing_chapter",
            "origin_ref": source_path.stem,
            "import_status": status,
        }
        chapter_path.write_text(_markdown_note("chapter", title, body, status=status, metadata=metadata))
        imported_paths.append(chapter_path)

    return imported_paths


def ingest_digested_context(vault_root: str | Path, payload: dict) -> list[Path]:
    adapter = VaultProjectAdapter(vault_root)
    adapter.ensure_runtime_dirs()

    written: list[Path] = []
    for item in payload.get("artifacts", []):
        artifact = item["artifact"]
        title = item.get("title") or artifact.replace("_", " ").title()
        body = item.get("body", "")
        status = item.get("status", "proposed")
        metadata = dict(item.get("metadata", {}))
        metadata.setdefault("source", "obsidian_cli")
        metadata.setdefault("origin_type", "digested_context")
        metadata.setdefault("origin_ref", payload.get("source_id", "manual_payload"))

        if artifact in ROOT_ARTIFACTS:
            written.append(
                write_root_artifact_note(
                    vault_root,
                    artifact=artifact,
                    title=title,
                    body=body,
                    status=status,
                    metadata=metadata,
                )
            )
            continue

        if artifact in STRUCTURED_NOTE_TYPES:
            written.append(
                write_or_update_note(
                    vault_root,
                    note_type=artifact,
                    slug=item.get("slug") or title,
                    title=title,
                    body=body,
                    status=status,
                    metadata=metadata,
                )
            )
            continue

        raise ValueError(f"Unsupported ingested artifact type: {artifact}")

    return written


def load_ingest_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def _markdown_note(
    kind: str,
    title: str,
    body: str,
    *,
    status: str,
    metadata: dict[str, str | int | None],
) -> str:
    lines = [
        "---",
        f"kind: {kind}",
        f"title: {title}",
        f"status: {status}",
        f"schema_version: {VAULT_SCHEMA_VERSION}",
    ]
    for key, value in metadata.items():
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    lines.extend(["---", "", f"# {title}", "", body.strip(), ""])
    return "\n".join(lines)


def _title_from_markdown(path: Path, *, fallback: str) -> str:
    text = path.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return slugify(path.stem).replace("_", " ").title() or fallback
