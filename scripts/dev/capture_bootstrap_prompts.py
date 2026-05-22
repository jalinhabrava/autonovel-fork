from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != SCRIPT_DIR]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.bootstrap.source_reader import build_source_document_inventory
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.structured_bootstrap_v1 import (
    NovelBootstrapV1Config,
    build_canonical_entity_map,
    run_structured_bootstrap_v1,
)


@dataclass
class CapturedRequest:
    index: int
    task: str | None
    provider_name: str | None
    model: str | None
    system: str | None
    messages: list[dict[str, str]]
    max_tokens: int | None
    temperature: float | None
    timeout_seconds: int | None
    retries: int | None
    response_format: dict[str, Any] | None
    source_file: str
    source_root: str
    detected_chapter_id: str | None
    detected_chapter_title: str | None
    chapter_text_char_count: int | None
    estimated_input_chars: int
    captured_at: str


class _CaptureProvider:
    def __init__(
        self,
        *,
        source_file: Path,
        source_root: Path,
        source_language: str,
        chapter_lookup: dict[str, dict[str, Any]],
        captures: list[CapturedRequest],
        global_normalization_override: dict[str, Any] | None = None,
    ):
        self._source_file = source_file
        self._source_root = source_root
        self._source_language = source_language
        self._chapter_lookup = chapter_lookup
        self._captures = captures
        self._global_normalization_override = global_normalization_override

    def generate(self, request):
        chapter_id = _extract_prefixed_value(request.messages, "CHAPTER_ID:")
        chapter_meta = self._chapter_lookup.get(chapter_id or "", {})
        capture = CapturedRequest(
            index=len(self._captures) + 1,
            task=request.task,
            provider_name=request.provider_name,
            model=request.model,
            system=request.system,
            messages=[{"role": message.role, "content": message.content} for message in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            retries=request.retries,
            response_format=request.response_format,
            source_file=str(self._source_file),
            source_root=str(self._source_root),
            detected_chapter_id=chapter_id,
            detected_chapter_title=chapter_meta.get("title"),
            chapter_text_char_count=chapter_meta.get("text_char_count"),
            estimated_input_chars=len(request.system or "") + sum(len(message.content or "") for message in request.messages),
            captured_at=datetime.now(timezone.utc).isoformat(),
        )
        self._captures.append(capture)
        return SimpleNamespace(
            text=_fake_response_text(
                request.task,
                chapter_id,
                chapter_meta,
                self._source_language,
                global_normalization_override=self._global_normalization_override,
            )
        )


def capture_bootstrap_prompts(
    *,
    source_root: str | Path,
    output_root: str | Path,
    primary_language: str | None = None,
    max_chapters: int = 3,
    source_file: str | Path | None = None,
    timestamp: str | None = None,
    global_normalization_json: str | Path | None = None,
) -> Path:
    source_root = Path(source_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    capture_id = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    capture_dir = output_root / capture_id
    capture_dir.mkdir(parents=True, exist_ok=True)
    vault_root = Path(tempfile.mkdtemp(prefix="textifai_capture_vault_"))

    explicit_paths = [Path(source_file).expanduser().resolve()] if source_file else None
    inventory = build_source_document_inventory(source_root, explicit_paths=explicit_paths)
    if not inventory.documents:
        raise SystemExit(f"No source documents found under {source_root}")

    source_doc = inventory.documents[0]
    source_path = Path(source_doc.path)
    global_normalization_override_path = (
        Path(global_normalization_json).expanduser().resolve() if global_normalization_json else None
    )
    global_normalization_override = (
        _load_global_normalization_override(global_normalization_override_path)
        if global_normalization_override_path is not None
        else None
    )
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    detected_chapters = detect_story_chapters(source_doc, source_text)
    if max_chapters:
        detected_chapters = detected_chapters[:max_chapters]
    chapter_lookup = {
        f"ch_{index:03d}": {
            "title": chapter.title,
            "text_char_count": len(chapter.text),
        }
        for index, chapter in enumerate(detected_chapters, start=1)
    }

    captures: list[CapturedRequest] = []
    provider = _CaptureProvider(
        source_file=source_path,
        source_root=source_root,
        source_language=source_doc.dominant_language or primary_language or "unknown",
        chapter_lookup=chapter_lookup,
        captures=captures,
        global_normalization_override=global_normalization_override,
    )

    config = NovelBootstrapV1Config(
        provider_name="capture_fake",
        model="capture-fake-model",
        max_chapters=max_chapters,
        prose_language_validation_mode="warn",
    )
    if primary_language:
        _ = primary_language

    with (
        patch("textifai.import_review.structured_bootstrap_v1.get_text_provider_config_error", return_value=None),
        patch("textifai.import_review.structured_bootstrap_v1.get_text_provider", return_value=provider),
        patch("textifai.import_review.structured_bootstrap_v1.synchronize_runtime_environment"),
    ):
        result = run_structured_bootstrap_v1(vault_root, inventory=inventory, config=config)
    if result is None:
        raise SystemExit("Structured bootstrap capture failed before request capture.")

    manifest = {
        "capture_id": capture_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "source_file": str(source_path),
        "primary_language": primary_language or source_doc.dominant_language,
        "max_chapters": max_chapters,
        "request_count": len(captures),
        "provider_calls": False,
        "capture_only": True,
        "global_normalization_override_enabled": global_normalization_override is not None,
        "global_normalization_override_json": str(global_normalization_override_path) if global_normalization_override_path else None,
        "vault_root_used": str(vault_root),
        "result_artifacts_root": str(vault_root / "99_System"),
        "canonical_entity_map_pipeline_path": str(result.canonical_entity_map_path),
        "canonical_entity_map_from_override": None,
        "requests": [],
    }
    if global_normalization_override is not None:
        canonical_map_from_override = build_canonical_entity_map(global_normalization_override)
        canonical_map_from_override_path = capture_dir / "canonical_entity_map_from_override.json"
        canonical_map_from_override_path.write_text(
            json.dumps(canonical_map_from_override, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest["canonical_entity_map_from_override"] = str(canonical_map_from_override_path)

    for capture in captures:
        task_slug = _slugify_task(capture.task)
        chapter_suffix = f"_{capture.detected_chapter_id}" if capture.detected_chapter_id else ""
        stem = f"request_{capture.index:03d}_{task_slug}{chapter_suffix}"
        json_path = capture_dir / f"{stem}.json"
        md_path = capture_dir / f"{stem}.md"
        payload = {
            "task": capture.task,
            "provider_name": capture.provider_name,
            "model": capture.model,
            "system": capture.system,
            "messages": capture.messages,
            "max_tokens": capture.max_tokens,
            "temperature": capture.temperature,
            "timeout_seconds": capture.timeout_seconds,
            "retries": capture.retries,
            "response_format": capture.response_format,
            "source_file": capture.source_file,
            "source_root": capture.source_root,
            "detected_chapter_id": capture.detected_chapter_id,
            "detected_chapter_title": capture.detected_chapter_title,
            "chapter_text_char_count": capture.chapter_text_char_count,
            "estimated_input_chars": capture.estimated_input_chars,
            "captured_at": capture.captured_at,
            "provider_calls": False,
            "capture_only": True,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(_render_capture_markdown(payload), encoding="utf-8")
        manifest["requests"].append({"json": str(json_path), "md": str(md_path), "task": capture.task})

    manifest_path = capture_dir / "capture_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _render_capture_markdown(payload: dict[str, Any]) -> str:
    message_sections = []
    for index, message in enumerate(payload.get("messages") or [], start=1):
        message_sections.append(
            f"### Message {index}\n"
            f"- role: `{message.get('role')}`\n\n"
            f"```text\n{message.get('content') or ''}\n```"
        )
    return (
        "# TextifAI Bootstrap Prompt Capture\n\n"
        f"- task: `{payload.get('task')}`\n"
        f"- model: `{payload.get('model')}`\n"
        f"- provider_name: `{payload.get('provider_name')}`\n"
        f"- source_file: `{payload.get('source_file')}`\n"
        f"- detected_chapter_id: `{payload.get('detected_chapter_id') or ''}`\n"
        f"- detected_chapter_title: `{payload.get('detected_chapter_title') or ''}`\n\n"
        "## System\n\n"
        f"```text\n{payload.get('system') or ''}\n```\n\n"
        "## Messages\n\n"
        f"{chr(10).join(message_sections)}\n"
    )


def _extract_prefixed_value(messages: list[Any], prefix: str) -> str | None:
    for message in messages:
        content = str(getattr(message, "content", "") or "")
        for line in content.splitlines():
            if line.startswith(prefix):
                return line.split(":", 1)[1].strip()
    return None


def _slugify_task(task: str | None) -> str:
    raw = (task or "unknown").strip().lower().replace("-", "_")
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw).strip("_") or "unknown"


def _fake_response_text(
    task: str | None,
    chapter_id: str | None,
    chapter_meta: dict[str, Any],
    source_language: str,
    *,
    global_normalization_override: dict[str, Any] | None = None,
) -> str:
    if task == "bootstrap_global_normalization":
        if isinstance(global_normalization_override, dict):
            return json.dumps(global_normalization_override, ensure_ascii=False)
        return json.dumps(
            {
                "work": {"title": "Capture Stub", "language": source_language},
                "entities": [],
                "merge_plan": [],
            },
            ensure_ascii=False,
        )
    title = chapter_meta.get("title") or f"{chapter_id or 'ch_001'} title"
    return json.dumps(
        {
            "work": {"title": "Capture Stub", "language": source_language},
            "chapters": [
                {
                    "chapter_id": chapter_id or "ch_001",
                    "chapter_title_original": title,
                    "chapter_title_canonical": title,
                    "sequence_index": int((chapter_id or "ch_001").split("_")[-1]) if chapter_id else 1,
                    "chapter_label_type": "other",
                    "chapter_number_in_label": None,
                    "title_parse_signals": {},
                    "chapter_summary": "capture stub",
                    "chapter_text_markdown": "capture stub",
                    "characters": [],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
        },
        ensure_ascii=False,
    )


def _load_global_normalization_override(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Global normalization override file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Global normalization override must be a JSON object.")
    for key in ["work", "entities", "merge_plan"]:
        if key not in payload:
            raise SystemExit(f"Global normalization override missing required top-level key: {key}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture real TextifAI bootstrap prompts without provider calls.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--source-file")
    parser.add_argument("--output-root", default="/tmp/textifai_prompt_capture")
    parser.add_argument("--primary-language")
    parser.add_argument("--max-chapters", type=int, default=3)
    parser.add_argument("--global-normalization-json")
    args = parser.parse_args()

    manifest_path = capture_bootstrap_prompts(
        source_root=args.source_root,
        source_file=args.source_file,
        output_root=args.output_root,
        primary_language=args.primary_language,
        max_chapters=args.max_chapters,
        global_normalization_json=args.global_normalization_json,
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
