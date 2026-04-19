from __future__ import annotations

import ast
import re
from typing import Any

from vault.schema import slugify

try:
    import yaml
except Exception:  # pragma: no cover - fallback if PyYAML is unavailable
    yaml = None


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def parse_obsidian_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    lines = text.splitlines()
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return {}
    raw = "\n".join(lines[1:closing])
    if yaml is not None:
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, dict):
            return parsed
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if current_list_key and stripped.startswith("- "):
            data.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = value
            current_list_key = None
        else:
            data[key] = []
            current_list_key = key
    return data


def strip_obsidian_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    lines = text.splitlines()
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return text
    return "\n".join(lines[closing + 1 :]).lstrip()


def extract_obsidian_links(text: str) -> list[str]:
    return [slugify(link.strip()) for link in WIKILINK_RE.findall(text) if link.strip()]


def extract_heading_title(text: str) -> str | None:
    match = HEADING_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def normalize_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [stripped]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
