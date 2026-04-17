from __future__ import annotations

from textifai import PRODUCT_NAME
from textifai.session import TextifAISession


def render_banner() -> str:
    return f"{PRODUCT_NAME} terminal runtime\nType `help` to see available commands."


def render_help() -> str:
    return "\n".join(
        [
            "Available commands:",
            "- help",
            "- status",
            "- mode",
            "- mode normal",
            "- mode advanced",
            "- exit",
            "- quit",
            "",
            "This is the base TextifAI shell. Domain commands arrive in the next runtime block.",
        ]
    )


def render_status(session: TextifAISession) -> str:
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
            f"- last_context_pack: {'present' if session.last_context_pack is not None else 'empty'}",
        ]
    )


def render_mode(session: TextifAISession) -> str:
    return f"Current mode: {session.mode}"
