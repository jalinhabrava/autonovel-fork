from __future__ import annotations

from pathlib import Path
import shlex

from adapters.vault_adapter import VaultProjectAdapter
from interactive.bootstrap_extract import extract_canon, extract_characters, extract_timeline, extract_voice
from interactive.context_commands import (
    build_chapter_context,
    build_find_context,
    build_scene_context,
    build_world_context,
)
from interactive.payloads import validate_artifact_payload
from interactive.persistence_commands import consistency_check, decide, reject, validate
from interactive.query import parse_frontmatter, strip_frontmatter
from textifai.prompts import ask_optional, ask_required
from textifai.render import (
    render_bootstrap_result,
    render_check_result,
    render_context_pack_summary,
    render_decision_result,
    render_persistence_result,
)
from textifai.session import TextifAISession
from vault.notes import NOTE_TYPE_DIRS
from vault.schema import VAULT_DIRS


NOTE_TYPE_ALIASES = {
    "character": "character",
    "lore": "lore",
    "scene": "scene",
    "decision": "decision",
    "chapter": "chapter",
    "revision_brief": "revision_brief",
    "brief": "revision_brief",
    "review": "review",
    "reader_panel": "reader_panel",
    "panel": "reader_panel",
}


def dispatch_command(
    session: TextifAISession,
    raw: str,
    *,
    input_fn=input,
) -> str | None:
    parts = shlex.split(raw)
    if not parts:
        return None

    command, *args = parts

    if command == "world":
        return _run_context_command(session, build_world_context(str(session.vault_path), policy=session.policy_name, token_budget=session.token_budget))

    if command == "find":
        query = " ".join(args).strip() or ask_required(input_fn, "What do you want to find? ")
        return _run_context_command(
            session,
            build_find_context(str(session.vault_path), query, policy=session.policy_name, token_budget=session.token_budget),
        )

    if command == "scene":
        scene_id = args[0] if args else ask_required(input_fn, "Scene id: ")
        return _run_context_command(
            session,
            build_scene_context(str(session.vault_path), scene_id, policy=session.policy_name, token_budget=session.token_budget),
        )

    if command == "chapter":
        chapter_id = args[0] if args else ask_required(input_fn, "Chapter id: ")
        return _run_context_command(
            session,
            build_chapter_context(str(session.vault_path), chapter_id, policy=session.policy_name, token_budget=session.token_budget),
        )

    if command == "check":
        if not args:
            return "Usage: check <type:slug|note_path>\nExamples: check decision:magic_costs or check 06_Canon/Decisions/magic_costs.md"
        return _run_check(session, args[0])

    if command == "decide":
        return _run_decide(session, input_fn=input_fn)

    if command == "validate":
        target = args[0] if args else ask_optional(input_fn, "Artifact id or note path: ")
        if not target:
            return "Validation needs a target. Use validate <type:slug|note_path>."
        return _run_state_change(session, "validated", target)

    if command == "reject":
        target = args[0] if args else ask_optional(input_fn, "Artifact id or note path: ")
        if not target:
            return "Reject needs a target. Use reject <type:slug|note_path>."
        return _run_state_change(session, "rejected", target)

    if command == "bootstrap":
        return _run_bootstrap(session, args, input_fn=input_fn)

    return None


def _run_context_command(session: TextifAISession, pack: dict) -> str:
    session.last_context_pack = pack
    session.last_result = pack
    return render_context_pack_summary(pack)


def _run_check(session: TextifAISession, target: str) -> str:
    payload = _artifact_payload_from_target(session, target)
    if payload is None:
        return "Could not resolve that target. Use check <type:slug> or a real note path inside the vault."
    report = consistency_check(str(session.vault_path), payload)
    session.last_result = report
    session.last_context_pack = report.get("context_pack")
    return render_check_result(report)


def _run_decide(session: TextifAISession, *, input_fn=input) -> str:
    title = ask_required(input_fn, "Decision title: ")
    body = ask_required(input_fn, "Decision body: ")
    affects_raw = ask_optional(input_fn, "Affects (comma-separated, optional): ")
    affects = [item.strip() for item in (affects_raw or "").split(",") if item.strip()]
    result = decide(
        str(session.vault_path),
        {
            "type": "decision_canon",
            "state": "validated",
            "title": title,
            "body": body,
            "affects": affects,
            "origin": {
                "source": "textifai_shell",
                "user_action": "decide_from_shell",
            },
        },
    )
    session.last_result = result
    return render_decision_result(result)


def _run_state_change(session: TextifAISession, state: str, target: str) -> str:
    resolved = _resolve_note_target(session, target)
    if resolved is None:
        return f"Could not resolve that target. Use {state[:-1] if state.endswith('d') else state} <type:slug|note_path>."
    payload = {
        "type": "artifact_state_change",
        "target_type": resolved["target_type"],
        "target_id": resolved["target_id"],
        "state": state,
        "origin": {
            "source": "textifai_shell",
            "user_action": f"{state}_from_shell",
        },
    }
    result = validate(str(session.vault_path), payload) if state == "validated" else reject(str(session.vault_path), payload)
    session.last_result = result
    return render_persistence_result(result)


def _run_bootstrap(session: TextifAISession, args: list[str], *, input_fn=input) -> str:
    subtype = args[0].lower() if args else None
    if subtype not in {None, "voice", "characters", "canon", "timeline"}:
        return "Unsupported bootstrap command. Use bootstrap voice|characters|canon|timeline."

    if subtype is None:
        subtype = _select_bootstrap_subtype(input_fn)
        if subtype is None:
            return "Bootstrap cancelled."

    chapter_ids, chapter_from, chapter_to = _collect_bootstrap_chapter_selection(args[1:], input_fn=input_fn)

    kwargs = {
        "chapter_ids": chapter_ids,
        "chapter_from": chapter_from,
        "chapter_to": chapter_to,
    }
    vault_root = str(session.vault_path)

    if subtype == "voice":
        result = extract_voice(vault_root, **kwargs)
    elif subtype == "characters":
        result = extract_characters(vault_root, **kwargs)
    elif subtype == "canon":
        result = extract_canon(vault_root, **kwargs)
    else:
        result = extract_timeline(vault_root, **kwargs)

    session.last_result = {
        "type": "bootstrap_result",
        "bootstrap_type": subtype,
        "results": result if isinstance(result, list) else [result],
    }
    return render_bootstrap_result(subtype, result)


def _artifact_payload_from_target(session: TextifAISession, target: str) -> dict | None:
    resolved = _resolve_note_target(session, target)
    if resolved is None:
        return None
    text = resolved["path"].read_text()
    frontmatter = parse_frontmatter(text)
    body = strip_frontmatter(text)
    payload = {
        "type": "artifact_payload",
        "artifact_kind": "note",
        "artifact_type": resolved["target_type"],
        "entity_id": resolved["target_id"],
        "title": frontmatter.get("title", resolved["path"].stem.replace("_", " ").title()),
        "body": body,
        "state": frontmatter.get("status", "proposed"),
        "metadata": {},
        "origin": {
            "source": "textifai_shell",
            "user_action": "check_from_shell",
        },
    }
    return validate_artifact_payload(payload)


def _select_bootstrap_subtype(input_fn=input) -> str | None:
    choice = ask_optional(
        input_fn,
        "Bootstrap type [voice|characters|canon|timeline] or `cancel`: ",
    )
    if choice is None:
        return None
    normalized = choice.strip().lower()
    if normalized in {"cancel", "abort", "exit", "quit"}:
        return None
    if normalized in {"voice", "characters", "canon", "timeline"}:
        return normalized
    return None


def _collect_bootstrap_chapter_selection(args: list[str], *, input_fn=input) -> tuple[list[str] | None, int | None, int | None]:
    if args:
        chapter_ids = _parse_chapter_ids(",".join(args))
        return (chapter_ids or None, None, None)

    chapter_ids_raw = ask_optional(input_fn, "Chapter ids (comma-separated, optional): ")
    chapter_ids = _parse_chapter_ids(chapter_ids_raw)
    if chapter_ids:
        return (chapter_ids, None, None)

    chapter_from_raw = ask_optional(input_fn, "Chapter from (optional): ")
    chapter_to_raw = ask_optional(input_fn, "Chapter to (optional): ")
    chapter_from = _parse_optional_int(chapter_from_raw)
    chapter_to = _parse_optional_int(chapter_to_raw)
    return (None, chapter_from, chapter_to)


def _parse_chapter_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_optional_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _resolve_note_target(session: TextifAISession, target: str) -> dict | None:
    if ":" in target and not target.endswith(".md"):
        note_type, slug = target.split(":", 1)
        normalized_type = NOTE_TYPE_ALIASES.get(note_type.strip().lower())
        if normalized_type is None:
            return None
        path = VaultProjectAdapter(session.vault_path).note_path(normalized_type, slug.strip())
        if not path.exists():
            return None
        return {
            "target_type": normalized_type,
            "target_id": path.stem,
            "path": path,
        }

    path = _resolve_existing_path(session, target)
    if path is None or not path.exists() or path.suffix.lower() != ".md":
        return None

    note_type = _infer_note_type_from_path(session, path)
    if note_type is None:
        return None
    return {
        "target_type": note_type,
        "target_id": path.stem,
        "path": path,
    }


def _resolve_existing_path(session: TextifAISession, target: str) -> Path | None:
    raw = Path(target).expanduser()
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            [
                session.base_dir / raw,
                session.vault_path / raw,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _infer_note_type_from_path(session: TextifAISession, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(session.vault_path.resolve())
    except ValueError:
        return None
    relative_text = relative.as_posix()
    for note_type, attr_name in NOTE_TYPE_DIRS.items():
        prefix = VAULT_DIRS[attr_name].rstrip("/")
        if relative_text.startswith(prefix + "/") or relative_text == prefix:
            return note_type
    return None
