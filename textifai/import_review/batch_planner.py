from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from textifai.import_review.token_budget import TokenBudget, fits_within_budget


_MARKDOWN_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+.+$")


@dataclass(frozen=True)
class PlannedBatch:
    items: list[dict[str, Any]]
    input_tokens: int
    token_count_method: str
    estimated_total_cost: int = 0

@dataclass(frozen=True)
class StructuredSourceChunk:
    source_id: str
    chunk_id: str
    chapter_id: str
    section_id: str
    sequence_index: int
    heading_path: list[str]
    text: str
    char_start: int
    char_end: int
    char_count: int
    estimated_tokens: int
    chunk_kind: str
    split_reason: str
    predecessor_chunk_id: str | None
    successor_chunk_id: str | None
    parent_chunk_id: str | None
    source_span: dict[str, Any]
    budget_profile_id: str | None = None
    provider_profile_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pack_items_by_budget(
    *,
    items: list[dict[str, Any]],
    budget: TokenBudget,
    measure_tokens: Callable[[list[dict[str, Any]]], tuple[int, str]],
    measure_total_cost: Callable[[list[dict[str, Any]], int], int] | None = None,
    max_total_cost: int | None = None,
) -> list[PlannedBatch]:
    batches: list[PlannedBatch] = []
    current: list[dict[str, Any]] = []

    for item in items:
        candidate = current + [item]
        candidate_tokens, method = measure_tokens(candidate)
        candidate_cost = (
            measure_total_cost(candidate, candidate_tokens)
            if measure_total_cost is not None
            else candidate_tokens
        )
        exceeds_input = not fits_within_budget(input_tokens=candidate_tokens, budget=budget)
        exceeds_total_cost = max_total_cost is not None and candidate_cost > max_total_cost
        if current and (exceeds_input or exceeds_total_cost):
            current_tokens, current_method = measure_tokens(current)
            current_cost = (
                measure_total_cost(current, current_tokens)
                if measure_total_cost is not None
                else current_tokens
            )
            batches.append(
                PlannedBatch(
                    items=list(current),
                    input_tokens=current_tokens,
                    token_count_method=current_method,
                    estimated_total_cost=current_cost,
                )
            )
            current = [item]
        else:
            current = candidate

    if current:
        current_tokens, current_method = measure_tokens(current)
        current_cost = (
            measure_total_cost(current, current_tokens)
            if measure_total_cost is not None
            else current_tokens
        )
        batches.append(
            PlannedBatch(
                items=list(current),
                input_tokens=current_tokens,
                token_count_method=current_method,
                estimated_total_cost=current_cost,
            )
        )
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

def split_structured_chapter_into_chunks(
    *,
    source_id: str,
    chapter_id: str,
    chapter_text: str,
    chapter_char_start: int,
    max_chunk_tokens: int,
    estimate_tokens: Callable[[str], int],
    overlap_paragraphs: int = 1,
    budget_profile_id: str | None = None,
    provider_profile_id: str | None = None,
) -> list[StructuredSourceChunk]:
    text = str(chapter_text or "")
    legacy_chunks = split_markdown_semantically(
        chapter_text=text,
        max_chunk_tokens=max_chunk_tokens,
        estimate_tokens=estimate_tokens,
        overlap_paragraphs=overlap_paragraphs,
    )
    records: list[StructuredSourceChunk] = []
    search_start = 0
    for index, chunk_text in enumerate(legacy_chunks, start=1):
        local_start = text.find(chunk_text, search_start)
        if local_start < 0:
            local_start = text.find(chunk_text)
        if local_start < 0:
            local_start = search_start
        local_end = min(len(text), local_start + len(chunk_text))
        search_start = max(search_start, local_end)
        chunk_id = f"{source_id}_{chapter_id}_chunk_{index:03d}"
        heading_path = _heading_path_for_chunk(chunk_text, fallback=[chapter_id])
        section_id = _stable_section_id(chapter_id=chapter_id, heading_path=heading_path, sequence_index=index)
        split_reason = "semantic_budget_split" if len(legacy_chunks) > 1 else "chapter_within_budget"
        records.append(
            StructuredSourceChunk(
                source_id=source_id,
                chunk_id=chunk_id,
                chapter_id=chapter_id,
                section_id=section_id,
                sequence_index=index,
                heading_path=heading_path,
                text=chunk_text,
                char_start=chapter_char_start + local_start,
                char_end=chapter_char_start + local_end,
                char_count=len(chunk_text),
                estimated_tokens=estimate_tokens(chunk_text),
                chunk_kind="structured_chapter_subchunk",
                split_reason=split_reason,
                predecessor_chunk_id=None,
                successor_chunk_id=None,
                parent_chunk_id=chapter_id,
                source_span={
                    "source_id": source_id,
                    "chapter_id": chapter_id,
                    "char_start": chapter_char_start + local_start,
                    "char_end": chapter_char_start + local_end,
                },
                budget_profile_id=budget_profile_id,
                provider_profile_id=provider_profile_id,
            )
        )
    return _link_structured_chunks(records)

def _link_structured_chunks(records: list[StructuredSourceChunk]) -> list[StructuredSourceChunk]:
    linked: list[StructuredSourceChunk] = []
    for index, record in enumerate(records):
        predecessor = records[index - 1].chunk_id if index > 0 else None
        successor = records[index + 1].chunk_id if index + 1 < len(records) else None
        linked.append(
            StructuredSourceChunk(
                **{
                    **record.to_dict(),
                    "predecessor_chunk_id": predecessor,
                    "successor_chunk_id": successor,
                }
            )
        )
    return linked

def _heading_path_for_chunk(text: str, *, fallback: list[str]) -> list[str]:
    headings = [match.group(0).lstrip("#").strip() for match in _MARKDOWN_HEADING_RE.finditer(text)]
    return headings or list(fallback)

def _stable_section_id(*, chapter_id: str, heading_path: list[str], sequence_index: int) -> str:
    suffix = "_".join(re.sub(r"[^a-zA-Z0-9]+", "_", part).strip("_").lower() for part in heading_path if part).strip("_")
    return f"{chapter_id}:{suffix or f'section_{sequence_index:03d}'}"


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
