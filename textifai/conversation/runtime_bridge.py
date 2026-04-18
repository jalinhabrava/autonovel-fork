from __future__ import annotations

from pathlib import Path

from interactive.query import parse_frontmatter
from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.manager import ConversationManager
from textifai.render import (
    render_check_result,
    render_context_pack_summary,
    render_decision_result,
    render_help,
    render_persistence_result,
)
from textifai.session import TextifAISession
from vault.schema import slugify


DIRECT_COMMAND_PREFIXES = (
    "world",
    "find",
    "scene",
    "chapter",
    "check",
    "decide",
    "validate",
    "reject",
    "bootstrap",
    "policy",
    "budget",
    "request",
    "pack",
    "context-debug",
)


def is_direct_runtime_command(raw: str) -> bool:
    stripped = raw.strip()
    if not stripped:
        return False
    head = stripped.split(maxsplit=1)[0].lower()
    return head in DIRECT_COMMAND_PREFIXES


def build_conversation_request(session: TextifAISession, raw: str) -> ConversationRequest:
    state = session.conversation_state
    artifact_target_language = None
    if state and state.last_target_type:
        artifact_target_language = session.resolve_language(
            artifact_type=state.last_target_type,
            operation_origin="user",
        ).artifact_target_language
    elif state and state.artifact_target_language:
        artifact_target_language = state.artifact_target_language

    return ConversationRequest(
        raw_text=raw,
        source="user",
        mode=session.mode,
        interface_language=session.language_policy.interface_language,
        user_command_language=session.language_policy.user_command_language,
        internal_system_language=session.language_policy.internal_system_language,
        project_default_language=session.language_policy.project_default_language,
        mixed_language_allowed=session.language_policy.mixed_language_allowed,
        artifact_target_language=artifact_target_language,
        explanation_language=session.language_policy.interface_language,
        target_hint=None,
        metadata={
            "known_characters": _load_known_characters(session.vault_path),
        },
    )


def handle_conversational_runtime_input(session: TextifAISession, raw: str) -> str:
    manager = ConversationManager(session=session)
    request = build_conversation_request(session, raw)
    turn = manager.handle_request(request)
    execution = manager.last_execution_result
    if execution is None:
        return turn.result_summary or render_help(session.locale)
    return render_execution_result(session, execution)


def render_execution_result(session: TextifAISession, execution) -> str:
    if execution.type == "conversation_help":
        return str(execution.result)
    if execution.type == "context_pack":
        return render_context_pack_summary(execution.context_pack or execution.result or {}, session.locale)
    if execution.type == "consistency_report":
        report = dict(execution.result or {})
        report.setdefault("locale", session.locale)
        return render_check_result(report)
    if execution.type == "decision_canon":
        result = dict(execution.result or {})
        result.setdefault("locale", session.locale)
        return render_decision_result(result)
    if execution.type == "artifact_state_change":
        result = dict(execution.result or {})
        result.setdefault("locale", session.locale)
        return render_persistence_result(result)
    return execution.result_summary


def _load_known_characters(vault_path: Path) -> list[dict[str, object]]:
    notes_dir = vault_path / "03_Characters" / "Profiles"
    if not notes_dir.exists():
        return []
    known: list[dict[str, object]] = []
    for path in sorted(notes_dir.glob("*.md")):
        text = path.read_text()
        frontmatter = parse_frontmatter(text)
        title = frontmatter.get("title", path.stem.replace("_", " ").replace("-", " ").title()).strip()
        slug = frontmatter.get("slug", slugify(path.stem))
        names = [title]
        if slug and slug not in names:
            names.append(slug.replace("_", " ").replace("-", " "))
        known.append(
            {
                "id": slugify(str(slug or path.stem)),
                "names": [name for name in names if name],
            }
        )
    return known
