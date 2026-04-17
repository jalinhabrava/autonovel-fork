from __future__ import annotations

from textifai.render import render_banner, render_first_use_hint, render_help, render_mode, render_status, render_unknown_command
from textifai.router import dispatch_command
from textifai.session import TextifAISession


def run_shell(
    session: TextifAISession,
    *,
    input_fn=input,
    output_fn=print,
) -> int:
    output_fn(render_banner())
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
        return render_help()
    if raw == "status":
        return render_status(session)
    if raw == "mode":
        return render_mode(session)
    if raw in {"exit", "quit"}:
        session.running = False
        return "Leaving TextifAI."
    if raw == "mode normal":
        session.mode = "normal"
        return "Mode set to normal.\n- hint: advanced inspection commands are now hidden behind `mode advanced`."
    if raw == "mode advanced":
        session.mode = "advanced"
        return "Mode set to advanced.\n- hint: try `request`, `pack`, or `context-debug` after loading context."
    routed = dispatch_command(session, raw, input_fn=input_fn)
    if routed is not None:
        return routed
    return render_unknown_command(raw)
