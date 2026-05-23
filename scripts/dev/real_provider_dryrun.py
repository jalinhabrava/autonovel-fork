from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.text_provider import (
    TextGenerationRequest,
    TextGenerationResponse,
    TextMessage,
    get_text_provider,
    get_text_provider_config_error,
)
from textifai.author_understanding.normalization import extract_json_payload

DEFAULT_OUTPUT_ROOT = Path("/tmp/textifai_real_provider_dryrun")
BOOTSTRAP_TASK = "bootstrap_chapter_extraction"
DEFAULT_BOOTSTRAP_MAX_OUTPUT_TOKENS = 8192


class DryRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapturedPrompt:
    system_prompt: str
    user_prompt: str
    file_sha256: str
    file_chars: int


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    details: dict[str, Any]


@dataclass(frozen=True)
class DryRunResult:
    status: str
    output_dir: str
    manifest_path: str
    validation_path: str
    response_json_path: str | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one guarded real-provider dry-run from captured prompt markdown.")
    parser.add_argument("--prompt-file", required=True, help="Path to captured prompt markdown file.")
    parser.add_argument("--provider", required=True, choices=["deepseek", "openai", "openai_compatible"])
    parser.add_argument("--model", required=True, help="Model name used in TextGenerationRequest.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Root output directory. Default /tmp path.")
    parser.add_argument("--allow-provider-calls", action="store_true", help="Required gate to allow real provider calls.")
    parser.add_argument(
        "--max-provider-requests",
        type=int,
        default=0,
        help="Must be exactly 1 for this dry-run.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Maximum output tokens. Defaults to 8192 for bootstrap_chapter_extraction dry-runs.",
    )
    parser.add_argument("--response-format-json", action="store_true")
    parser.add_argument("--no-write-back", action="store_true", default=True)
    parser.add_argument("--save-trace", action="store_true")
    parser.add_argument("--redact-prompts", action="store_true")
    return parser


def _read_capture_markdown(path: Path) -> CapturedPrompt:
    if not path.exists():
        raise DryRunError(f"Prompt file does not exist: {path}")
    markdown = path.read_text(encoding="utf-8")
    system_prompt = _extract_fenced_section(markdown, "## System")
    user_prompt = _extract_message_one(markdown)
    if not system_prompt.strip():
        raise DryRunError("Missing system prompt section in capture markdown.")
    if not user_prompt.strip():
        raise DryRunError("Missing Message 1 section in capture markdown.")
    return CapturedPrompt(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        file_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        file_chars=len(markdown),
    )


def _extract_message_one(markdown: str) -> str:
    marker = "### Message 1"
    start = markdown.find(marker)
    if start < 0:
        raise DryRunError("Missing heading: ### Message 1")
    tail = markdown[start + len(marker) :]
    fence = re.search(r"```(?:text)?\n(.*?)\n```", tail, flags=re.DOTALL)
    if not fence:
        raise DryRunError("Message 1 section missing fenced text block.")
    return fence.group(1)


def _extract_fenced_section(markdown: str, heading: str) -> str:
    section_match = re.search(
        rf"^{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        raise DryRunError(f"Missing heading: {heading}")
    section = section_match.group(1)
    fence = re.search(r"```(?:text)?\n(.*?)\n```", section, flags=re.DOTALL)
    if not fence:
        raise DryRunError(f"Section {heading} missing fenced text block.")
    return fence.group(1)


def _validate_contract_v2_for_ch002(payload: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    details: dict[str, Any] = {}

    if not payload:
        errors.append("response_json_empty")
    work = payload.get("work") if isinstance(payload, dict) else None
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if not isinstance(work, dict):
        errors.append("missing_top_level_work")
    if not isinstance(chapters, list) or not chapters:
        errors.append("missing_top_level_chapters")
        chapters = []

    first = chapters[0] if chapters and isinstance(chapters[0], dict) else {}
    chapter_id = first.get("chapter_id")
    details["chapter_id"] = chapter_id
    if chapter_id != "ch_002":
        errors.append("first_chapter_id_not_ch_002")

    if "objects" not in first:
        errors.append("missing_objects")
    if "events" not in first:
        errors.append("missing_events")
    if "relations" not in first:
        errors.append("missing_relations")

    events = first.get("events") if isinstance(first.get("events"), list) else []
    relations = first.get("relations") if isinstance(first.get("relations"), list) else []

    if not any(isinstance(event, dict) and event.get("event_importance") for event in events):
        errors.append("missing_event_importance")
    if not any(isinstance(rel, dict) and rel.get("relation_category") for rel in relations):
        errors.append("missing_relation_category")

    details.update(
        {
            "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            "chapter_count": len(chapters),
            "events_count": len(events),
            "relations_count": len(relations),
            "objects_count": len(first.get("objects") or []) if isinstance(first.get("objects"), list) else 0,
        }
    )

    return ValidationResult(ok=not errors, errors=errors, details=details)


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _resolve_max_output_tokens(value: int | None) -> tuple[int, str]:
    if value is None:
        return DEFAULT_BOOTSTRAP_MAX_OUTPUT_TOKENS, "default"
    if value <= 0:
        raise DryRunError("Refusing provider call: --max-output-tokens must be greater than 0.")
    return value, "user_provided"


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(
    argv: list[str] | None = None,
    *,
    provider_factory: Callable[[str | None, str | None], Any] = get_text_provider,
    provider_config_error: Callable[[str | None, str | None], str | None] = get_text_provider_config_error,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_once(args, provider_factory=provider_factory, provider_config_error=provider_config_error)
    except DryRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0


def run_once(
    args: argparse.Namespace,
    *,
    provider_factory: Callable[[str | None, str | None], Any],
    provider_config_error: Callable[[str | None, str | None], str | None],
) -> DryRunResult:
    if not args.allow_provider_calls:
        raise DryRunError("Refusing provider call: --allow-provider-calls is required.")
    if args.max_provider_requests != 1:
        raise DryRunError("Refusing provider call: --max-provider-requests must be exactly 1.")
    if not args.no_write_back:
        raise DryRunError("Refusing provider call: --no-write-back must stay enabled.")
    max_output_tokens, max_output_tokens_source = _resolve_max_output_tokens(args.max_output_tokens)

    prompt_path = Path(args.prompt_file)
    captured = _read_capture_markdown(prompt_path)

    cfg_error = provider_config_error(BOOTSTRAP_TASK, args.provider)
    if cfg_error:
        raise DryRunError(f"Provider configuration error: {cfg_error}")

    output_root = Path(args.output_root)
    output_dir = output_root / _utc_stamp()
    output_dir.mkdir(parents=True, exist_ok=False)

    provider = provider_factory(BOOTSTRAP_TASK, args.provider)
    response = provider.generate(
        TextGenerationRequest(
            task=BOOTSTRAP_TASK,
            provider_name=args.provider,
            model=args.model,
            system=captured.system_prompt,
            messages=[TextMessage(role="user", content=captured.user_prompt)],
            max_tokens=max_output_tokens,
            temperature=0.0,
            timeout_seconds=180,
            retries=0,
            response_format={"type": "json_object"} if args.response_format_json else None,
        )
    )
    if not isinstance(response, TextGenerationResponse):
        response = TextGenerationResponse(
            text=str(getattr(response, "text", "")),
            raw=getattr(response, "raw", {}) if isinstance(getattr(response, "raw", {}), dict) else {},
            provider_name=str(getattr(response, "provider_name", args.provider)),
            model=str(getattr(response, "model", args.model)),
            task=str(getattr(response, "task", BOOTSTRAP_TASK)),
        )

    raw_text_path = output_dir / "provider_response_raw.txt"
    raw_text_path.write_text(response.text or "", encoding="utf-8")

    parsed = extract_json_payload(response.text or "")
    response_json_path: Path | None = None
    if isinstance(parsed, dict):
        response_json_path = output_dir / "provider_response.json"
        _json_dump(response_json_path, parsed)

    validation = _validate_contract_v2_for_ch002(parsed if isinstance(parsed, dict) else {})
    validation_payload = {
        "ok": validation.ok,
        "errors": validation.errors,
        "details": validation.details,
        "response_parseable_json": isinstance(parsed, dict),
    }
    validation_path = output_dir / "validation_report.json"
    _json_dump(validation_path, validation_payload)

    manifest = {
        "status": "completed",
        "provider": args.provider,
        "model": args.model,
        "task": BOOTSTRAP_TASK,
        "allow_provider_calls": args.allow_provider_calls,
        "max_provider_requests": args.max_provider_requests,
        "max_output_tokens": max_output_tokens,
        "max_output_tokens_source": max_output_tokens_source,
        "response_format_json": bool(args.response_format_json),
        "no_write_back": bool(args.no_write_back),
        "save_trace": bool(args.save_trace),
        "redact_prompts": bool(args.redact_prompts),
        "prompt_file": str(prompt_path),
        "prompt_file_chars": captured.file_chars,
        "prompt_file_sha256": captured.file_sha256,
        "provider_response_raw_path": str(raw_text_path),
        "provider_response_json_path": str(response_json_path) if response_json_path else None,
        "validation_report_path": str(validation_path),
        "response_text_chars": len(response.text or ""),
        "response_provider_name": response.provider_name,
        "response_model": response.model,
        "timestamp_utc": _utc_stamp(),
    }

    if args.save_trace:
        trace_payload = {
            "system_prompt": "[REDACTED]" if args.redact_prompts else captured.system_prompt,
            "user_prompt": "[REDACTED]" if args.redact_prompts else captured.user_prompt,
        }
        _json_dump(output_dir / "prompt_trace.json", trace_payload)

    manifest_path = output_dir / "dryrun_manifest.json"
    _json_dump(manifest_path, manifest)

    return DryRunResult(
        status="completed",
        output_dir=str(output_dir),
        manifest_path=str(manifest_path),
        validation_path=str(validation_path),
        response_json_path=str(response_json_path) if response_json_path else None,
    )


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
