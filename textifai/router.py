from __future__ import annotations

from pathlib import Path
import shlex

from adapters.vault_adapter import VaultProjectAdapter
from interactive.bootstrap_extract import extract_canon, extract_characters, extract_timeline, extract_voice
from interactive.context_commands import (
    build_chapter_context,
    debug_context,
    build_find_context,
    build_scene_context,
    build_world_context,
)
from interactive.context_requests import build_chapter_request, build_find_request, build_scene_request, build_world_request
from interactive.payloads import validate_artifact_payload
from interactive.persistence_commands import consistency_check, decide, reject, validate
from interactive.query import parse_frontmatter, strip_frontmatter
from textifai.prompts import ask_optional, ask_required
from textifai.render import (
    render_bootstrap_result,
    render_check_result,
    render_context_debug_summary,
    render_context_pack_summary,
    render_decision_result,
    render_budget_info,
    render_pack_view,
    render_persistence_result,
    render_policy_info,
    render_request_summary,
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

AVAILABLE_POLICIES = ["default", "strict_canon", "local_scene"]


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
        request = build_world_request(policy=session.policy_name, token_budget=session.token_budget)
        return _run_context_command(
            session,
            build_world_context(str(session.vault_path), policy=session.policy_name, token_budget=session.token_budget),
            request=_request_to_dict(request),
        )

    if command == "find":
        query = " ".join(args).strip() or ask_required(input_fn, session.translator.t("shell.prompt.find"))
        request = build_find_request(query, policy=session.policy_name, token_budget=session.token_budget)
        return _run_context_command(
            session,
            build_find_context(str(session.vault_path), query, policy=session.policy_name, token_budget=session.token_budget),
            request=_request_to_dict(request),
        )

    if command == "scene":
        scene_id = args[0] if args else ask_required(input_fn, session.translator.t("shell.prompt.scene_id"))
        request = build_scene_request(scene_id, policy=session.policy_name, token_budget=session.token_budget)
        return _run_context_command(
            session,
            build_scene_context(str(session.vault_path), scene_id, policy=session.policy_name, token_budget=session.token_budget),
            request=_request_to_dict(request),
        )

    if command == "chapter":
        chapter_id = args[0] if args else ask_required(input_fn, session.translator.t("shell.prompt.chapter_id"))
        request = build_chapter_request(chapter_id, policy=session.policy_name, token_budget=session.token_budget)
        return _run_context_command(
            session,
            build_chapter_context(str(session.vault_path), chapter_id, policy=session.policy_name, token_budget=session.token_budget),
            request=_request_to_dict(request),
        )

    if command == "check":
        if not args:
            return session.translator.t("shell.errors.check_usage")
        return _run_check(session, args[0])

    if command == "decide":
        return _run_decide(session, input_fn=input_fn)

    if command == "validate":
        target = args[0] if args else ask_optional(input_fn, session.translator.t("shell.prompt.artifact_target"))
        if not target:
            return session.translator.t("shell.errors.validate_target")
        return _run_state_change(session, "validated", target)

    if command == "reject":
        target = args[0] if args else ask_optional(input_fn, session.translator.t("shell.prompt.artifact_target"))
        if not target:
            return session.translator.t("shell.errors.reject_target")
        return _run_state_change(session, "rejected", target)

    if command == "bootstrap":
        return _run_bootstrap(session, args, input_fn=input_fn)

    if command == "policy":
        return _run_policy(session, args)

    if command == "budget":
        return _run_budget(session, args)

    if command == "request":
        return _run_request_view(session)

    if command == "pack":
        return _run_pack_view(session)

    if command == "context-debug":
        return _run_context_debug(session)

    return None


def _run_context_command(session: TextifAISession, pack: dict, *, request: dict) -> str:
    session.remember(pack, request=request)
    return render_context_pack_summary(pack, session.locale)


def _run_check(session: TextifAISession, target: str) -> str:
    payload = _artifact_payload_from_target(session, target)
    if payload is None:
        return session.translator.t("shell.errors.check_resolve")
    report = consistency_check(str(session.vault_path), payload)
    report["locale"] = session.locale
    session.remember(report)
    return render_check_result(report)


def _run_decide(session: TextifAISession, *, input_fn=input) -> str:
    title = ask_required(input_fn, session.translator.t("shell.prompt.decision_title"))
    body = ask_required(input_fn, session.translator.t("shell.prompt.decision_body"))
    affects_raw = ask_optional(input_fn, session.translator.t("shell.prompt.decision_affects"))
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
    result["locale"] = session.locale
    session.remember(result)
    return render_decision_result(result)


def _run_state_change(session: TextifAISession, state: str, target: str) -> str:
    resolved = _resolve_note_target(session, target)
    if resolved is None:
        command = "validate" if state == "validated" else "reject"
        return session.translator.t("shell.errors.resolve_target", command=command)
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
    result["locale"] = session.locale
    session.remember(result)
    return render_persistence_result(result)


def _run_bootstrap(session: TextifAISession, args: list[str], *, input_fn=input) -> str:
    subtype = args[0].lower() if args else None
    if subtype not in {None, "voice", "characters", "canon", "timeline"}:
        return session.translator.t("shell.errors.bootstrap_unsupported")

    if subtype is None:
        subtype = _select_bootstrap_subtype(session, input_fn)
        if subtype is None:
            return session.translator.t("shell.errors.bootstrap_cancelled")

    chapter_ids, chapter_from, chapter_to = _collect_bootstrap_chapter_selection(session, args[1:], input_fn=input_fn)

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

    session.remember(
        {
        "type": "bootstrap_result",
        "bootstrap_type": subtype,
        "results": result if isinstance(result, list) else [result],
        }
    )
    return render_bootstrap_result(subtype, result, session.locale)


def _run_policy(session: TextifAISession, args: list[str]) -> str:
    if not args:
        return render_policy_info(session.policy_name, AVAILABLE_POLICIES, session.locale)
    candidate = args[0]
    if candidate not in AVAILABLE_POLICIES:
        return render_policy_info(session.policy_name, AVAILABLE_POLICIES, session.locale)
    session.policy_name = candidate
    return session.translator.t("shell.policy.set", policy=candidate)


def _run_budget(session: TextifAISession, args: list[str]) -> str:
    if not args:
        return render_budget_info(session.token_budget, session.locale)
    try:
        budget = int(args[0])
    except ValueError:
        return session.translator.t("shell.errors.budget_integer")
    if budget <= 0:
        return session.translator.t("shell.errors.budget_positive")
    session.token_budget = budget
    return session.translator.t("shell.budget.set", budget=budget)


def _run_request_view(session: TextifAISession) -> str:
    if not session.last_context_request:
        return session.translator.t("shell.errors.no_request")
    return render_request_summary(session.last_context_request, session.locale)


def _run_pack_view(session: TextifAISession) -> str:
    if not session.last_context_pack:
        return session.translator.t("shell.errors.no_pack")
    return render_pack_view(session.last_context_pack, session.locale)


def _run_context_debug(session: TextifAISession) -> str:
    if session.mode != "advanced":
        return session.translator.t("shell.errors.context_debug_mode")
    if not session.last_context_request:
        return session.translator.t("shell.errors.no_request")
    request = session.last_context_request
    debug = debug_context(
        str(session.vault_path),
        intent=request["intent"],
        narrative_scope=request["narrative_scope"],
        retrieval_scope=list(request["retrieval_scope"]),
        target_id=request["target_id"],
        target_type=request["target_type"],
        policy=request.get("policy_name", request.get("policy", session.policy_name)),
        token_budget=request["token_budget"],
        query_text=request.get("query_text"),
        chapter_refs=list(request.get("chapter_refs", [])),
        character_ids=list(request.get("character_ids", [])),
        debug_mode="summary",
        max_candidates=8,
    )
    session.remember(debug["context_pack"], request=request, debug=debug)
    return render_context_debug_summary(debug, session.locale)


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


def _request_to_dict(request) -> dict:
    return {
        "intent": request.intent,
        "target_id": request.target_id,
        "target_type": request.target_type,
        "narrative_scope": request.narrative_scope,
        "retrieval_scope": list(request.retrieval_scope),
        "query_text": request.query_text,
        "chapter_refs": list(request.chapter_refs),
        "character_ids": list(request.character_ids),
        "policy_name": request.policy_name,
        "token_budget": request.token_budget,
    }


def _select_bootstrap_subtype(session: TextifAISession, input_fn=input) -> str | None:
    choice = ask_optional(
        input_fn,
        session.translator.t("shell.prompt.bootstrap_type"),
    )
    if choice is None:
        return None
    normalized = choice.strip().lower()
    if normalized in {"cancel", "abort", "exit", "quit"}:
        return None
    if normalized in {"voice", "characters", "canon", "timeline"}:
        return normalized
    return None


def _collect_bootstrap_chapter_selection(
    session: TextifAISession,
    args: list[str],
    *,
    input_fn=input,
) -> tuple[list[str] | None, int | None, int | None]:
    if args:
        chapter_ids = _parse_chapter_ids(",".join(args))
        return (chapter_ids or None, None, None)

    chapter_ids_raw = ask_optional(input_fn, session.translator.t("shell.prompt.chapter_ids"))
    chapter_ids = _parse_chapter_ids(chapter_ids_raw)
    if chapter_ids:
        return (chapter_ids, None, None)

    chapter_from_raw = ask_optional(input_fn, session.translator.t("shell.prompt.chapter_from"))
    chapter_to_raw = ask_optional(input_fn, session.translator.t("shell.prompt.chapter_to"))
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
