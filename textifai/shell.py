from __future__ import annotations

from textifai.render import render_banner, render_help, render_mode, render_status
from textifai.session import TextifAISession


def run_shell(
    session: TextifAISession,
    *,
    input_fn=input,
    output_fn=print,
) -> int:
    output_fn(render_banner())
    while session.running:
        raw = input_fn("textifai> ").strip()
        if not raw:
            continue
        response = handle_command(session, raw)
        if response:
            output_fn(response)
    return 0


def handle_command(session: TextifAISession, raw: str) -> str:
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
        return "Mode set to normal."
    if raw == "mode advanced":
        session.mode = "advanced"
        return "Mode set to advanced."
    return "Unknown command. Type `help`."
