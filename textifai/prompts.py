from __future__ import annotations


def ask_required(input_fn, prompt: str) -> str:
    while True:
        value = input_fn(prompt).strip()
        if value:
            return value


def ask_optional(input_fn, prompt: str) -> str | None:
    value = input_fn(prompt).strip()
    return value or None
