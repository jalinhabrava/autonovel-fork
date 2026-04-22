from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from textifai.import_review.token_budget import TokenBudget, fits_within_budget


_MARKDOWN_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+.+$")


@dataclass(frozen=True)
class PlannedBatch:
    items: list[dict[str, Any]]
    input_tokens: int
    token_count_method: str


def pack_items_by_budget(
    *,
    items: list[dict[str, Any]],
    budget: TokenBudget,
    measure_tokens: Callable[[list[dict[str, Any]]], tuple[int, str]],
) -> list[PlannedBatch]:
    batches: list[PlannedBatch] = []
    current: list[dict[str, Any]] = []

    for item in items:
        candidate = current + [item]
        candidate_tokens, method = measure_tokens(candidate)
        if current and not fits_within_budget(input_tokens=candidate_tokens, budget=budget):
            current_tokens, current_method = measure_tokens(current)
            batches.append(PlannedBatch(items=list(current), input_tokens=current_tokens, token_count_method=current_method))
            current = [item]
        else:
            current = candidate

    if current:
        current_tokens, current_method = measure_tokens(current)
        batches.append(PlannedBatch(items=list(current), input_tokens=current_tokens, token_count_method=current_method))
    return batches


def split_markdown_semantically(
    *,
    chapter_text: str,
    max_chunk_tokens: int,
    estimate_tokens: Callable[[str], int],
    overlap_paragraphs: int = 1,
) -> list[str]:
    sections = _split_markdown_sections(chapter_text)
    chunks: list[str] = []
    current_parts: list[str] = []

    for section in sections:
        candidate = "\n\n".join([*current_parts, section]).strip()
        if current_parts and estimate_tokens(candidate) > max_chunk_tokens:
            chunk = "\n\n".join(current_parts).strip()
            if chunk:
                chunks.append(chunk)
            carry = _tail_paragraphs(chunk, count=overlap_paragraphs)
            current_parts = [carry, section] if carry else [section]
        else:
            current_parts.append(section)

    final_chunk = "\n\n".join(current_parts).strip()
    if final_chunk:
        chunks.append(final_chunk)
    return chunks


def _split_markdown_sections(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    headings = list(_MARKDOWN_HEADING_RE.finditer(normalized))
    if not headings:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        return paragraphs or [normalized]
    sections: list[str] = []
    for index, match in enumerate(headings):
        start = match.start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(normalized)
        section = normalized[start:end].strip()
        if section:
            sections.append(section)
    return sections or [normalized]


def _tail_paragraphs(text: str, *, count: int) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text or "").strip()) if part.strip()]
    if not paragraphs:
        return ""
    return "\n\n".join(paragraphs[-count:])
