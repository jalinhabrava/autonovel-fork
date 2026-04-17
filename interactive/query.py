from __future__ import annotations

import re
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter


def read_markdown(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    lines = text.splitlines()
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return {}
    data: dict[str, str] = {}
    for line in lines[1:closing]:
        key, sep, value = line.partition(":")
        if sep:
            data[key.strip()] = value.strip()
    return data


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    lines = text.splitlines()
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return text
    return "\n".join(lines[closing + 1:]).lstrip()


def line_span(text: str, query: str | None = None, radius: int = 4) -> dict[str, int]:
    lines = text.splitlines() or [""]
    if not query:
        return {"start_line": 1, "end_line": len(lines)}

    needle = query.lower()
    for index, line in enumerate(lines, start=1):
        if needle in line.lower():
            return {
                "start_line": max(1, index - radius),
                "end_line": min(len(lines), index + radius),
            }
    return {"start_line": 1, "end_line": min(len(lines), 12)}


def note_record(path: Path, kind: str) -> dict:
    text = read_markdown(path)
    frontmatter = parse_frontmatter(text)
    body = strip_frontmatter(text)
    return {
        "id": frontmatter.get("slug", path.stem),
        "kind": kind,
        "title": frontmatter.get("title", path.stem.replace("_", " ").title()),
        "chapter": frontmatter.get("chapter"),
        "path": path,
        "text": text,
        "body": body,
        "frontmatter": frontmatter,
    }


def list_note_records(directory: Path, kind: str) -> list[dict]:
    if not directory.exists():
        return []
    return [note_record(path, kind) for path in sorted(directory.glob("*.md"))]


def list_character_titles(adapter: VaultProjectAdapter) -> list[str]:
    return [record["title"] for record in list_note_records(adapter.character_profiles_dir, "character")]


def infer_characters(text: str, candidates: list[str]) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for name in candidates:
        pattern = re.compile(rf"\b{re.escape(name.lower())}\b")
        if pattern.search(lowered):
            found.append(name)
    return found


def infer_refs(text: str, records: list[dict]) -> list[str]:
    lowered = text.lower()
    refs: list[str] = []
    for record in records:
        slug = str(record["id"])
        title = str(record["title"])
        if slug.lower() in lowered or title.lower() in lowered:
            refs.append(slug)
    return refs


def infer_pov(text: str, candidates: list[str]) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("pov:"):
            return stripped.split(":", 1)[1].strip() or None
    characters = infer_characters(text, candidates)
    return characters[0] if characters else None


def chapter_ref(value: int | str | None) -> str | None:
    if value in {None, ""}:
        return None
    if isinstance(value, str) and value.startswith("ch_"):
        return value
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return f"ch_{number:02d}"


def extract_summary(text: str, fallback: str) -> str:
    body = strip_frontmatter(text)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:240]
    return fallback


def search_records(records: list[dict], query: str, limit: int = 8) -> list[dict]:
    matches: list[dict] = []
    for record in records:
        haystack = f"{record['title']}\n{record['body']}"
        span = line_span(record["body"], query)
        if query.lower() in haystack.lower():
            matches.append(
                {
                    "id": record["id"],
                    "kind": record["kind"],
                    "title": record["title"],
                    "path": str(record["path"]),
                    "selected_fragment": span,
                }
            )
        if len(matches) >= limit:
            break
    return matches


def filter_records_by_status(records: list[dict], statuses: set[str]) -> list[dict]:
    return [record for record in records if record["frontmatter"].get("status", "proposed") in statuses]
