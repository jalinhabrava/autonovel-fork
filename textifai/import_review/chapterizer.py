from __future__ import annotations

import re
from dataclasses import dataclass, field

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.obsidian.parser import strip_obsidian_frontmatter
from vault.schema import slugify


_PAGE_MARKER_RE = re.compile(r"<<TEXTIFAI_PAGE_(?P<page>\d{4})>>")
_MARKDOWN_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
_CHAPTER_LABEL_RE = re.compile(
    r"^(?:(?:chapter|cap[ií]tulo|episode|episodio|part|parte|act|acto|scene|escena)\s+[\wivxlcdm0-9]+(?:\s*[:.\-~]\s*.+)?|(?:prologue|prologo|prólogo|epilogue|epilogo|epílogo))$",
    flags=re.IGNORECASE,
)
_TOC_LINE_RE = re.compile(
    r"^(?P<title>.+?)(?:\.{2,}|\s{2,})(?P<page>\d{1,4})\s*$",
)


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


def detect_story_chapters(
    document: SourceDocumentRecord,
    text: str,
) -> list[DetectedChapter]:
    normalized = strip_obsidian_frontmatter(text).replace("\r\n", "\n")
    if not normalized.strip():
        return []

    toc_titles = _extract_toc_titles(normalized)
    heading_matches = _find_heading_matches(normalized, toc_titles=toc_titles)
    if not heading_matches:
        return []

    chapters: list[DetectedChapter] = []
    for index, current in enumerate(heading_matches, start=1):
        next_start = heading_matches[index].char_start if index < len(heading_matches) else len(normalized)
        chapter_text = _strip_page_markers(normalized[current.char_start:next_start]).strip()
        if len(chapter_text.split()) < 8:
            continue
        page_start = _page_for_offset(normalized, current.char_start)
        page_end = _page_for_offset(normalized, max(current.char_start, next_start - 1))
        title = current.title.strip()
        chapters.append(
            DetectedChapter(
                chapter_id=f"{document.source_id}__chapter_{index:03d}",
                source_id=document.source_id,
                title=title,
                slug=slugify(title) or f"chapter_{index:03d}",
                text=chapter_text,
                char_start=current.char_start,
                char_end=next_start,
                page_start=page_start,
                page_end=page_end,
                confidence=current.confidence,
                heading_text=current.heading_text,
                detection_signals=current.signals,
            )
        )
    return chapters


@dataclass(frozen=True)
class _HeadingMatch:
    char_start: int
    title: str
    confidence: float
    heading_text: str
    signals: list[str]


def _extract_toc_titles(text: str) -> list[str]:
    toc_titles: list[str] = []
    lines = text.splitlines()
    in_toc = False
    for line in lines[: min(len(lines), 400)]:
        stripped = _strip_page_markers(line).strip()
        if not stripped:
            continue
        lowered = stripped.casefold()
        if lowered in {"índice", "indice", "contenido", "contents", "table of contents"}:
            in_toc = True
            continue
        toc_match = _TOC_LINE_RE.match(stripped)
        if toc_match:
            title = toc_match.group("title").strip()
            if _looks_like_chapter_title(title):
                toc_titles.append(title)
                continue
        if in_toc and toc_titles and not toc_match:
            if len(toc_titles) >= 2:
                break
    return _dedupe(toc_titles)


def _find_heading_matches(text: str, *, toc_titles: list[str]) -> list[_HeadingMatch]:
    lines = text.splitlines(keepends=True)
    matches: list[_HeadingMatch] = []
    offset = 0
    previous_blank = True
    has_page_markers = bool(_PAGE_MARKER_RE.search(text))
    for index, line in enumerate(lines):
        stripped = _strip_page_markers(line).strip()
        if not stripped:
            previous_blank = True
            offset += len(line)
            continue
        next_blank = True
        if index + 1 < len(lines):
            next_blank = not _strip_page_markers(lines[index + 1]).strip()

        markdown = _MARKDOWN_HEADING_RE.match(stripped)
        heading_candidate = markdown.group("title").strip() if markdown else stripped
        toc_corroborated = any(slugify(heading_candidate) == slugify(title) for title in toc_titles)
        heading_like = _looks_like_chapter_title(heading_candidate)
        generic_numbered = _is_generic_numbered_heading(heading_candidate)
        if generic_numbered and not (toc_corroborated or has_page_markers):
            heading_like = False
        if (markdown and (heading_like or toc_corroborated)) or (heading_like and previous_blank and next_blank and len(stripped) <= 120):
            confidence = 0.7
            signals: list[str] = []
            if markdown:
                confidence += 0.1
                signals.append("markdown_heading")
                stripped = heading_candidate
            if heading_like:
                confidence += 0.1
                signals.append("chapter_pattern")
            if toc_corroborated:
                confidence += 0.08
                signals.append("toc_match")
            title = _normalize_heading_title(stripped)
            if title:
                matches.append(
                    _HeadingMatch(
                        char_start=offset,
                        title=title,
                        confidence=min(confidence, 0.96),
                        heading_text=stripped,
                        signals=signals or ["standalone_heading"],
                    )
                )
        previous_blank = False
        offset += len(line)

    deduped: list[_HeadingMatch] = []
    seen_offsets: set[int] = set()
    for match in matches:
        if match.char_start in seen_offsets:
            continue
        seen_offsets.add(match.char_start)
        deduped.append(match)
    return deduped


def _page_for_offset(text: str, offset: int) -> int | None:
    pages = [int(match.group("page")) for match in _PAGE_MARKER_RE.finditer(text[:offset + 1])]
    if pages:
        return pages[-1]
    return 1 if _PAGE_MARKER_RE.search(text) else None


def _strip_page_markers(text: str) -> str:
    return _PAGE_MARKER_RE.sub("", text)


def _looks_like_chapter_title(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 140:
        return False
    if _CHAPTER_LABEL_RE.match(stripped):
        return True
    if re.fullmatch(r"[\divxlcdmIVXLCDM]+", stripped):
        return True
    if re.fullmatch(r"(?:[0-9]{1,3}|[IVXLCDM]{1,8})\s*[-–—:.]\s*.+", stripped):
        return True
    return False


def _is_generic_numbered_heading(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"(?:[0-9]{1,3}|[IVXLCDM]{1,8})\s*[-–—:.]\s*.+", stripped))


def _normalize_heading_title(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    return normalized.strip("# ").strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = slugify(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
