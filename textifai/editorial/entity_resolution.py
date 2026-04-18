from __future__ import annotations

from pathlib import Path

from textifai.vaerl.resolver import resolve_text_against_vault


def resolve_entities(
    *,
    text: str,
    vault_path: Path,
    known_characters: list[dict[str, object]] | None = None,
    entity_hints: list[str] | None = None,
):
    return resolve_text_against_vault(
        text=text,
        vault_path=vault_path,
        known_characters=known_characters,
        entity_hints=entity_hints,
    )
