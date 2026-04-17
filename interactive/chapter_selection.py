from __future__ import annotations

import re
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.query import note_record


def select_chapter_records(
    adapter: VaultProjectAdapter,
    *,
    chapter_ids: list[str] | None = None,
    chapter_from: int | None = None,
    chapter_to: int | None = None,
) -> list[dict]:
    explicit_ids = {normalize_chapter_id(chapter_id) for chapter_id in (chapter_ids or [])}
    records: list[dict] = []

    for path in adapter.list_chapter_paths():
        chapter_id = path.stem
        chapter_number = chapter_number_from_id(chapter_id)
        if explicit_ids and chapter_id not in explicit_ids:
            continue
        if chapter_from is not None and (chapter_number is None or chapter_number < chapter_from):
            continue
        if chapter_to is not None and (chapter_number is None or chapter_number > chapter_to):
            continue

        record = note_record(path, "chapter")
        record["id"] = chapter_id
        record["chapter_number"] = chapter_number
        records.append(record)

    return records


def normalize_chapter_id(chapter_id: str | int) -> str:
    if isinstance(chapter_id, int):
        return f"ch_{chapter_id:02d}"
    text = str(chapter_id).strip()
    if text.startswith("ch_"):
        return text
    try:
        number = int(text)
    except ValueError:
        return text
    return f"ch_{number:02d}"


def chapter_number_from_id(chapter_id: str) -> int | None:
    match = re.search(r"(\d+)$", chapter_id)
    if not match:
        return None
    return int(match.group(1))


def chapter_ids_for(records: list[dict]) -> list[str]:
    return [str(record["id"]) for record in records]


def chapter_path_strings(records: list[dict]) -> list[str]:
    return [str(Path(record["path"])) for record in records]
