from __future__ import annotations

from textifai import PRODUCT_NAME
from textifai.session import TextifAISession


def render_banner() -> str:
    return f"{PRODUCT_NAME} terminal runtime\nType `help` to see available commands."


def render_first_use_hint(session: TextifAISession) -> str:
    if session.last_result is not None:
        return ""
    return (
        "Getting started: try `world`, `find <query>`, or `bootstrap`.\n"
        "When you want to inspect context internals, switch to `mode advanced`."
    )


def render_help() -> str:
    return "\n".join(
        [
            "TextifAI shell help",
            "",
            "Getting started:",
            "- world",
            "- find <query>",
            "- scene <scene_id>",
            "- chapter <chapter_id>",
            "",
            "Review and decisions:",
            "- check <type:slug|note_path>",
            "- decide",
            "- validate <type:slug|note_path>",
            "- reject <type:slug|note_path>",
            "",
            "Bootstrap:",
            "- bootstrap",
            "- bootstrap voice",
            "- bootstrap characters",
            "- bootstrap canon",
            "- bootstrap timeline",
            "",
            "Advanced inspection:",
            "- context-debug",
            "- policy",
            "- policy <name>",
            "- budget",
            "- budget <int>",
            "- request",
            "- pack",
            "",
            "Shell:",
            "- help",
            "- status",
            "- mode",
            "- mode normal",
            "- mode advanced",
            "- exit",
            "- quit",
            "",
            "Examples:",
            "- find Sera",
            "- scene scene_054_b",
            "- check decision:magic_costs",
            "- bootstrap canon",
        ]
    )


def render_status(session: TextifAISession) -> str:
    next_step = "Try `world`, `find <query>`, or `bootstrap` to start working."
    if session.last_context_pack is not None:
        next_step = "You already have context loaded. Try `pack`, `request`, or `check`."
    if session.mode == "advanced":
        next_step = "Advanced mode is active. You can inspect with `context-debug`, `request`, and `pack`."
    return "\n".join(
        [
            "TextifAI session status",
            f"- vault: {session.vault_path}",
            f"- backend: {session.backend}",
            f"- provider: {session.provider or 'not configured'}",
            f"- writer_model: {session.writer_model or 'default'}",
            f"- mode: {session.mode}",
            f"- policy: {session.policy_name}",
            f"- token_budget: {session.token_budget}",
            f"- last_result: {'present' if session.last_result is not None else 'empty'}",
            f"- last_context_request: {'present' if session.last_context_request is not None else 'empty'}",
            f"- last_context_pack: {'present' if session.last_context_pack is not None else 'empty'}",
            f"- last_context_debug: {'present' if session.last_context_debug is not None else 'empty'}",
            f"- next_step: {next_step}",
        ]
    )


def render_mode(session: TextifAISession) -> str:
    hint = "Use `mode advanced` to inspect requests and packs." if session.mode == "normal" else "Advanced inspection commands are available."
    return f"Current mode: {session.mode}\n- hint: {hint}"


def render_context_pack_summary(pack: dict) -> str:
    voice_context = pack.get("voice_context", {})
    project_voice = voice_context.get("project_voice", [])
    character_voice = voice_context.get("character_voice", [])
    lines = [
        "TextifAI context result",
        f"- intent: {pack.get('intent', 'unknown')}",
        f"- target: {pack.get('scope', {}).get('target_id', pack.get('target_id', 'unknown'))}",
        f"- policy: {pack.get('policy', {}).get('name', 'default')}",
        f"- hard_constraints: {len(pack.get('hard_constraints', []))}",
        f"- narrative_context: {len(pack.get('narrative_context', []))}",
        f"- voice.project: {len(project_voice)}",
        f"- voice.character: {len(character_voice)}",
        f"- evidence: {len(pack.get('evidence', []))}",
    ]
    highlights = _entry_highlights(pack)
    if highlights:
        lines.append("- highlights:")
        for item in highlights:
            lines.append(f"  {item}")
    return "\n".join(lines)


def render_check_result(report: dict) -> str:
    lines = [
        "TextifAI consistency check",
        f"- target: {report.get('target_type')}:{report.get('target_id')}",
        f"- ok: {'yes' if report.get('ok') else 'no'}",
        f"- summary: {report.get('summary', 'No summary')}",
        f"- canon_refs: {', '.join(report.get('canon_refs', [])) or 'none'}",
        f"- lore_refs: {', '.join(report.get('lore_refs', [])) or 'none'}",
    ]
    issues = report.get("issues", [])
    if issues:
        lines.append("- issues:")
        for issue in issues[:4]:
            lines.append(f"  - [{issue.get('severity', 'info')}] {issue.get('message', '')}")
    suggestions = report.get("suggested_actions", [])
    if suggestions:
        lines.append("- suggested_actions:")
        for suggestion in suggestions[:4]:
            lines.append(f"  - {suggestion}")
    return "\n".join(lines)


def render_decision_result(result: dict) -> str:
    return "\n".join(
        [
            "TextifAI decision recorded",
            f"- state: {result.get('state')}",
            f"- target: {result.get('target_type')}:{result.get('target_id')}",
            f"- path: {result.get('path', 'n/a')}",
            "- next_step: review with `check <type:slug>` or continue writing.",
        ]
    )


def render_persistence_result(result: dict) -> str:
    return "\n".join(
        [
            "TextifAI persistence result",
            f"- state: {result.get('state')}",
            f"- target: {result.get('target_type')}:{result.get('target_id')}",
            f"- path: {result.get('path', 'n/a')}",
            "- next_step: use `check`, `request`, or `pack` if you want to inspect related context.",
        ]
    )


def render_bootstrap_result(bootstrap_type: str, result) -> str:
    items = result if isinstance(result, list) else [result]
    written = [item for item in items if item.get("status") == "written"]
    blocked = [item for item in items if item.get("status") == "blocked"]
    skipped = [item for item in items if item.get("status") == "skipped"]
    lines = [
        "TextifAI bootstrap result",
        f"- type: {bootstrap_type}",
        f"- total_results: {len(items)}",
        f"- written: {len(written)}",
        f"- blocked: {len(blocked)}",
        f"- skipped: {len(skipped)}",
    ]
    if bootstrap_type == "canon":
        lines.append("- note: canon bootstrap creates extracted proposals, not validated canon.")
    if bootstrap_type == "timeline":
        lines.append("- note: timeline bootstrap is currently stored as provisional lore notes.")
    highlights = [item.get("target_id") for item in items[:3] if item.get("target_id")]
    if highlights:
        lines.append(f"- highlights: {', '.join(highlights)}")
    return "\n".join(lines)


def render_policy_info(active: str, available: list[str]) -> str:
    return "\n".join(
        [
            "TextifAI policy settings",
            f"- active_policy: {active}",
            f"- available_policies: {', '.join(available)}",
        ]
    )


def render_budget_info(budget: int) -> str:
    return f"Current token budget: {budget}\n- note: this affects future context requests in the current session."


def render_request_summary(request: dict) -> str:
    return "\n".join(
        [
            "TextifAI context request",
            f"- intent: {request.get('intent', 'unknown')}",
            f"- target_id: {request.get('target_id', 'unknown')}",
            f"- target_type: {request.get('target_type', 'unknown')}",
            f"- narrative_scope: {request.get('narrative_scope', 'unknown')}",
            f"- retrieval_scope: {', '.join(request.get('retrieval_scope', [])) or 'none'}",
            f"- policy: {request.get('policy', request.get('policy_name', 'default'))}",
            f"- token_budget: {request.get('token_budget', 'unknown')}",
        ]
    )


def render_pack_view(pack: dict) -> str:
    voice_context = pack.get("voice_context", {})
    project_voice = voice_context.get("project_voice", [])
    character_voice = voice_context.get("character_voice", [])
    lines = [
        "TextifAI context pack",
        f"- intent: {pack.get('intent', 'unknown')}",
        f"- target: {pack.get('scope', {}).get('target_id', pack.get('target_id', 'unknown'))}",
        f"- hard_constraints: {len(pack.get('hard_constraints', []))}",
        f"- narrative_context: {len(pack.get('narrative_context', []))}",
        f"- voice.project: {len(project_voice)}",
        f"- voice.character: {len(character_voice)}",
        f"- evidence: {len(pack.get('evidence', []))}",
    ]
    for label, entries in (
        ("hard_constraints", pack.get("hard_constraints", [])),
        ("narrative_context", pack.get("narrative_context", [])),
        ("evidence", pack.get("evidence", [])),
    ):
        if entries:
            top = entries[0]
            lines.append(f"- top_{label}: {top.get('title', top.get('id', 'entry'))}")
    return "\n".join(lines)


def render_context_debug_summary(debug: dict) -> str:
    candidates = debug.get("candidates", [])
    lines = [
        "TextifAI context debug",
        f"- intent: {debug.get('resolved_intent', {}).get('name', debug.get('request', {}).get('intent', 'unknown'))}",
        f"- target: {debug.get('request', {}).get('target_id', 'unknown')}",
        f"- policy: {debug.get('policy', {}).get('name', 'default')}",
        f"- candidates_shown: {len(candidates)}",
    ]
    for candidate in candidates[:3]:
        score = candidate.get("score", {})
        lines.append(
            f"- candidate: {candidate.get('id', 'unknown')} | section={candidate.get('final_section', 'n/a')} | score={score.get('total', 'n/a')}"
        )
    return "\n".join(lines)


def render_unknown_command(raw: str) -> str:
    return "\n".join(
        [
            f"TextifAI does not recognize `{raw}`.",
            "Try `help` to see commands, or start with `world`, `find <query>`, or `bootstrap`.",
        ]
    )


def _entry_highlights(pack: dict) -> list[str]:
    highlights: list[str] = []
    sections = (
        ("hard_constraints", pack.get("hard_constraints", [])),
        ("narrative_context", pack.get("narrative_context", [])),
        ("evidence", pack.get("evidence", [])),
    )
    for section_name, entries in sections:
        if not entries:
            continue
        top = entries[0]
        highlights.append(f"{section_name}: {top.get('title', top.get('id', 'entry'))}")
    return highlights[:3]
