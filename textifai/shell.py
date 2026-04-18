from __future__ import annotations

from textifai.conversation.runtime_bridge import handle_conversational_runtime_input, is_direct_runtime_command
from textifai.render import render_banner, render_first_use_hint, render_help, render_mode, render_status, render_unknown_command
from textifai.router import dispatch_command
from textifai.session import TextifAISession


def run_shell(
    session: TextifAISession,
    *,
    input_fn=input,
    output_fn=print,
) -> int:
    output_fn(render_banner(session.locale))
    first_use_hint = render_first_use_hint(session)
    if first_use_hint:
        output_fn(first_use_hint)
    while session.running:
        raw = input_fn("textifai> ").strip()
        if not raw:
            continue
        response = handle_command(session, raw, input_fn=input_fn)
        if response:
            output_fn(response)
    return 0


def handle_command(session: TextifAISession, raw: str, *, input_fn=input) -> str:
    if raw == "help":
        return render_help(session.locale)
    if raw == "status":
        return render_status(session)
    if raw == "mode":
        return render_mode(session)
    if raw in {"exit", "quit"}:
        session.running = False
        return session.translator.t("shell.exit")
    if raw == "mode normal":
        session.mode = "normal"
        return session.translator.t("shell.mode.set.normal")
    if raw == "mode advanced":
        session.mode = "advanced"
        return session.translator.t("shell.mode.set.advanced")
    if is_direct_runtime_command(raw):
        routed = dispatch_command(session, raw, input_fn=input_fn)
        if routed is not None:
            return routed
    if session.mode == "normal" or not is_direct_runtime_command(raw):
        return handle_conversational_runtime_input(session, raw)
    routed = dispatch_command(session, raw, input_fn=input_fn)
    if routed is not None:
        return routed
    return render_unknown_command(raw, session.locale)
