from __future__ import annotations

import re
from dataclasses import dataclass, field

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.obsidian.parser import strip_obsidian_frontmatter
from vault.schema import slugify


_PAGE_MARKER_RE = re.compile(r"<<TEXTIFAI_PAGE_(?P<page>\d{4})>>")
_MARKDOWN_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
_TOC_LINE_RE = re.compile(r"^(?P<title>.+?)\s+(?:\.{2,}|[-–—_=~·•]{2,}|\s{2,})\s*(?P<page>\d{1,4})\s*$")
_STRONG_SEPARATOR_RE = re.compile(r"^(?:[-=_*~•·]{3,}|[◆◇■□●○]{2,}|(?:\*\s*){3,})$")
_NUMERIC_PREFIX_RE = re.compile(r"^(?P<number>(?:\d{1,4}|[IVXLCDM]{1,10}))(?:\s*[-–—:.)]+\s*|\s+)(?P<rest>.+)$")
_EARLY_TOKEN_NUMBER_RE = re.compile(r"^(?:\S+\s+){0,2}(?P<number>(?:\d{1,4}|[IVXLCDM]{1,10}))(?:\s*[-–—:.)]+\s*|\s+)(?P<rest>.+)$")


@dataclass(frozen=True)
class ChapterBoundaryCandidate:
    candidate_id: str
    source_id: str
    original_title: str
    normalized_title: str
    char_start: int
    page: int | None = None
    heading_text: str | None = None
    signals: list[str] = field(default_factory=list)
    context_before: str = ""
    context_after: str = ""
    title_number_hint: str | None = None
    toc_page_hint: int | None = None


@dataclass(frozen=True)
class DetectedChapter:
    chapter_id: str
    source_id: str
    title: str
    slug: str
    text: str
    char_start: int
    char_end: int
    page_start: int | None = None
    page_end: int | None = None
    confidence: float = 0.0
    heading_text: str | None = None
    detection_signals: list[str] = field(default_factory=list)
    source_number_hint: str | None = None
    source_sequence_index: int | None = None


def detect_story_chapters(
    document: SourceDocumentRecord,
    text: str,
) -> list[DetectedChapter]:
    normalized = _normalize_text(text)
    candidates = discover_chapter_boundary_candidates(document, normalized)
    structural_chapters = select_structural_chapters(document, normalized, candidates)
    return structural_chapters


def discover_chapter_boundary_candidates(
    document: SourceDocumentRecord,
    text: str,
) -> list[ChapterBoundaryCandidate]:
    normalized = _normalize_text(text)
    if not normalized.strip():
        return []

    toc_titles, toc_line_indexes = _extract_toc_titles(normalized)
    toc_title_map = {slugify(title): page for title, page in toc_titles}
    lines = normalized.splitlines(keepends=True)
    candidates: list[ChapterBoundaryCandidate] = []
    offset = 0
    previous_blank = True
    page_recently_changed = False

    for index, line in enumerate(lines):
        raw_line = line
        stripped = _strip_page_markers(raw_line).strip()
        if _PAGE_MARKER_RE.search(raw_line):
            page_recently_changed = True
        if not stripped:
            previous_blank = True
            offset += len(raw_line)
            continue
        if index in toc_line_indexes:
            previous_blank = False
            page_recently_changed = False
            offset += len(raw_line)
            continue

        next_nonempty = _next_nonempty_line(lines, index + 1)
        next_line_blank = _next_line_is_blank(lines, index + 1)
        markdown = _MARKDOWN_HEADING_RE.match(stripped)
        title_text = markdown.group("title").strip() if markdown else stripped
        title_continuation = _title_continuation_text(lines, index)
        if title_continuation:
            title_text = f"{title_text} {title_continuation}".strip()
        normalized_title = _normalize_heading_title(title_text)
        title_key = slugify(normalized_title)
        toc_page_hint = toc_title_map.get(title_key)
        signals: list[str] = []

        if markdown:
            signals.append("markdown_heading")
        if _STRONG_SEPARATOR_RE.match(stripped):
            previous_blank = True
            page_recently_changed = False
            offset += len(raw_line)
            continue

        if len(normalized_title) > 140 or len(normalized_title.split()) > 18:
            previous_blank = False
            page_recently_changed = False
            offset += len(raw_line)
            continue

        numeric_hint = _extract_number_hint(normalized_title)
        isolated = previous_blank
        surrounded_by_blank = previous_blank and next_line_blank
        title_score = _title_likelihood_score(normalized_title)
        previous_nonempty = _previous_nonempty_line(lines, index - 1)
        follows_sentence = bool(previous_nonempty and previous_nonempty.rstrip().endswith((".", "!", "?", "…", "」", "”", "\"")))
        if isolated:
            signals.append("isolated_line")
        if page_recently_changed:
            signals.append("page_top")
        if numeric_hint:
            signals.append("numeric_prefix")
        if toc_page_hint is not None:
            signals.append("toc_match")
        if title_continuation:
            signals.append("continued_title_line")

        title_shape_ok = _looks_like_title_shape(normalized_title)
        strong_structural_candidate = bool(markdown) or toc_page_hint is not None
        numbered_structural_candidate = bool(numeric_hint) and title_shape_ok and title_score >= 0.55 and (isolated or next_line_blank or follows_sentence)
        untitled_structural_candidate = surrounded_by_blank and title_shape_ok and title_score >= 0.88 and len(normalized_title.split()) <= 6
        if strong_structural_candidate or numbered_structural_candidate or untitled_structural_candidate:
            page = _page_for_offset(normalized, offset)
            candidates.append(
                ChapterBoundaryCandidate(
                    candidate_id=f"{document.source_id}__candidate_{len(candidates)+1:03d}",
                    source_id=document.source_id,
                    original_title=normalized_title,
                    normalized_title=normalized_title,
                    char_start=offset,
                    page=page,
                    heading_text=title_text,
                    signals=signals or ["structural_candidate"],
                    context_before=_context_window(lines, index, before=True),
                    context_after=_context_window(lines, index, before=False),
                    title_number_hint=numeric_hint,
                    toc_page_hint=toc_page_hint,
                )
            )

        previous_blank = False
        page_recently_changed = False
        offset += len(raw_line)

    return _dedupe_candidates(candidates)


def select_structural_chapters(
    document: SourceDocumentRecord,
    text: str,
    candidates: list[ChapterBoundaryCandidate],
) -> list[DetectedChapter]:
    if not candidates:
        return []
    chapters: list[DetectedChapter] = []
    for index, current in enumerate(candidates, start=1):
        next_start = candidates[index].char_start if index < len(candidates) else len(text)
        chapter_text = _strip_page_markers(text[current.char_start:next_start]).strip()
        if len(chapter_text.split()) < 8:
            continue
        if current.page == 1 and not current.title_number_hint and len(current.normalized_title.split()) <= 2:
            continue
        page_start = _page_for_offset(text, current.char_start)
        page_end = _page_for_offset(text, max(current.char_start, next_start - 1))
        confidence = 0.45
        if current.title_number_hint:
            confidence += 0.2
        if current.page is not None:
            confidence += 0.1
        if "page_top" in current.signals:
            confidence += 0.08
        if "toc_match" in current.signals:
            confidence += 0.08
        chapters.append(
            DetectedChapter(
                chapter_id=f"{document.source_id}__chapter_{index:03d}",
                source_id=document.source_id,
                title=current.normalized_title,
                slug=slugify(current.normalized_title) or f"{document.source_id}_chapter_{index:03d}",
                text=chapter_text,
                char_start=current.char_start,
                char_end=next_start,
                page_start=page_start,
                page_end=page_end,
                confidence=min(confidence, 0.95),
                heading_text=current.heading_text,
                detection_signals=list(current.signals),
                source_number_hint=current.title_number_hint,
                source_sequence_index=index,
            )
        )
    return chapters


def _normalize_text(text: str) -> str:
    return strip_obsidian_frontmatter(text).replace("\r\n", "\n")


def _extract_toc_titles(text: str) -> tuple[list[tuple[str, int]], set[int]]:
    titles: list[tuple[str, int]] = []
    line_indexes: set[int] = set()
    lines = text.splitlines()
    consecutive_hits = 0
    for index, line in enumerate(lines[: min(len(lines), 400)]):
        stripped = _strip_page_markers(line).strip()
        if not stripped:
            continue
        match = _TOC_LINE_RE.match(stripped)
        if not match:
            if consecutive_hits >= 2:
                break
            continue
        title = _normalize_heading_title(match.group("title"))
        page = int(match.group("page"))
        if title:
            titles.append((title, page))
            line_indexes.add(index)
            consecutive_hits += 1
    return _dedupe_toc_entries(titles), line_indexes


def _title_likelihood_score(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    words = stripped.split()
    if 1 <= len(words) <= 14:
        score += 0.25
    if len(stripped) <= 110:
        score += 0.15
    if _extract_number_hint(stripped):
        score += 0.25
    if re.search(r"[A-ZÀ-Ý一-龯ァ-ンぁ-ん]", stripped):
        score += 0.1
    if not stripped.endswith((".", "?", "!", ";")):
        score += 0.1
    if sum(ch.isalpha() for ch in stripped) >= 4:
        score += 0.1
    if len(words) >= 3:
        score += 0.05
    return min(score, 1.0)


def _looks_like_title_shape(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith((".", "?", "!")):
        return False
    words = stripped.split()
    capitalized = sum(1 for word in words if word[:1].isupper() or re.match(r"^[0-9IVXLCDMivxlcdm]+$", word))
    ratio = capitalized / max(len(words), 1)
    return ratio >= 0.4 or bool(_extract_number_hint(stripped)) or len(words) <= 5


def _extract_number_hint(text: str) -> str | None:
    stripped = text.strip()
    if re.fullmatch(r"\d{1,4}", stripped):
        return stripped
    if re.fullmatch(r"[IVXLCDM]{1,10}", stripped):
        return stripped
    match = _NUMERIC_PREFIX_RE.match(stripped)
    if match:
        return match.group("number")
    match = _EARLY_TOKEN_NUMBER_RE.match(stripped)
    if match:
        return match.group("number")
    return None


def _context_window(lines: list[str], index: int, *, before: bool) -> str:
    if before:
        start = max(0, index - 3)
        chunk = lines[start:index]
    else:
        end = min(len(lines), index + 4)
        chunk = lines[index + 1 : end]
    return "\n".join(_strip_page_markers(line).strip() for line in chunk if _strip_page_markers(line).strip())


def _next_nonempty_line(lines: list[str], start: int) -> str | None:
    for line in lines[start:]:
        stripped = _strip_page_markers(line).strip()
        if stripped:
            return stripped
    return None


def _previous_nonempty_line(lines: list[str], start: int) -> str | None:
    for index in range(start, -1, -1):
        stripped = _strip_page_markers(lines[index]).strip()
        if stripped:
            return stripped
    return None


def _next_line_is_blank(lines: list[str], index: int) -> bool:
    if index >= len(lines):
        return True
    return not _strip_page_markers(lines[index]).strip()


def _title_continuation_text(lines: list[str], index: int) -> str | None:
    next_index = index + 1
    if next_index >= len(lines):
        return None
    current = _strip_page_markers(lines[index]).strip()
    following = _strip_page_markers(lines[next_index]).strip()
    if not current or not following:
        return None
    if len(following.split()) > 5:
        return None
    if following.endswith((".", "?", "!")):
        return None
    if _extract_number_hint(following):
        return None
    if not _looks_like_title_shape(following):
        return None
    return following


def _page_for_offset(text: str, offset: int) -> int | None:
    pages = [int(match.group("page")) for match in _PAGE_MARKER_RE.finditer(text[: offset + 1])]
    if pages:
        return pages[-1]
    return 1 if _PAGE_MARKER_RE.search(text) else None


def _strip_page_markers(text: str) -> str:
    return _PAGE_MARKER_RE.sub("", text)


def _normalize_heading_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).strip("# ").strip()


def _dedupe_toc_entries(values: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[str] = set()
    result: list[tuple[str, int]] = []
    for title, page in values:
        key = slugify(title)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append((title, page))
    return result


def _dedupe_candidates(candidates: list[ChapterBoundaryCandidate]) -> list[ChapterBoundaryCandidate]:
    deduped: list[ChapterBoundaryCandidate] = []
    seen_offsets: set[int] = set()
    for candidate in candidates:
        if candidate.char_start in seen_offsets:
            continue
        seen_offsets.add(candidate.char_start)
        deduped.append(candidate)
    return deduped
