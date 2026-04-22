from __future__ import annotations

import hashlib
import re
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentRecord, SourceFragment
from textifai.bootstrap.language import detect_language_profile
from textifai.obsidian.parser import strip_obsidian_frontmatter


_MARKDOWN_HEADING_RE = re.compile(
    r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$",
)
_STRUCTURAL_HEADING_RE = re.compile(
    r"^(?:(?:ch|chapter|scene|scn)[\s_-]*\d+.*)$",
    flags=re.IGNORECASE,
)


def segment_source_document(
    document: SourceDocumentRecord,
    text: str,
) -> list[SourceFragment]:
    normalized_text = strip_obsidian_frontmatter(text)

    if not normalized_text.strip():
        return [
            SourceFragment(
                fragment_id=f"{document.source_id}__frag_001",
                source_id=document.source_id,
                char_start=0,
                char_end=0,
                text="",
                literal_text_hash=_hash_text(""),
                detected_kind="mixed_note",
                kind_confidence=0.0,
                language=document.dominant_language,
                has_mixed_language=document.has_mixed_language,
                register_signals=["empty"],
                needs_review=True,
            )
        ]

    blocks = _split_on_headings(normalized_text)
    fragments: list[SourceFragment] = []
    for index, block in enumerate(blocks, start=1):
        detection = detect_language_profile(block.text)
        detected_kind, confidence, needs_review = _classify_block(document, block.text, block.heading)
        fragments.append(
            SourceFragment(
                fragment_id=f"{document.source_id}__frag_{index:03d}",
                source_id=document.source_id,
                char_start=block.start,
                char_end=block.end,
                text=block.text,
                literal_text_hash=_hash_text(block.text),
                detected_kind=detected_kind,
                kind_confidence=confidence,
                language=detection.dominant_language or document.dominant_language,
                has_mixed_language=detection.has_mixed_language or document.has_mixed_language,
                register_signals=detection.register_signals,
                needs_review=needs_review or detection.has_mixed_language,
            )
        )
    return fragments


def _classify_block(document: SourceDocumentRecord, text: str, heading: str | None) -> tuple[str, float, bool]:
    heading_text = (heading or "").strip().casefold()
    stem = Path(document.filename).stem.casefold()
    if heading_text.startswith("scene ") or stem.startswith("scene_") or stem.startswith("scn_"):
        return "scene", 0.9, False
    if heading_text.startswith("chapter ") or stem.startswith("chapter_") or stem.startswith("ch_"):
        return "chapter", 0.9, False
    if len(text.split()) > 900:
        return "chapter", 0.6, True
    if len(text.split()) > 120:
        return "mixed_note", 0.45, True
    return "project_note", 0.3, True


def _split_on_headings(text: str) -> list[_FragmentBlock]:
    markdown_blocks = _split_markdown_sections(text)
    if markdown_blocks:
        return _merge_heading_only_blocks(markdown_blocks)

    lines = text.splitlines(keepends=True)
    blocks: list[_FragmentBlock] = []
    current_lines: list[str] = []
    current_start = 0
    current_heading: str | None = None
    offset = 0
    for line in lines:
        stripped = line.strip()
        is_heading = bool(stripped) and bool(_STRUCTURAL_HEADING_RE.match(stripped))
        if is_heading and current_lines:
            block_text = "".join(current_lines).strip("\n")
            if block_text.strip():
                blocks.append(_FragmentBlock(start=current_start, end=offset, text=block_text, heading=current_heading))
            current_lines = []
            current_start = offset
            current_heading = stripped
        if not current_lines and not stripped:
            current_start = offset + len(line)
        else:
            current_lines.append(line)
            if current_heading is None and is_heading:
                current_heading = stripped
        offset += len(line)
    if current_lines:
        block_text = "".join(current_lines).strip("\n")
        if block_text.strip():
            blocks.append(_FragmentBlock(start=current_start, end=len(text), text=block_text, heading=current_heading))
    if not blocks:
        return [_FragmentBlock(start=0, end=len(text), text=text, heading=None)]
    return _merge_heading_only_blocks(blocks)


def _split_markdown_sections(text: str) -> list["_FragmentBlock"]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    offset = 0
    headings: list[_MarkdownHeading] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = _MARKDOWN_HEADING_RE.match(stripped) if stripped else None
        if match is not None:
            headings.append(
                _MarkdownHeading(
                    line_index=index,
                    char_start=offset,
                    level=len(match.group("marks")),
                    text=stripped,
                )
            )
        offset += len(line)

    if not headings:
        return []

    split_level = _choose_split_level(text=text, headings=headings)
    selected = [heading for heading in headings if heading.level == split_level]
    if not selected:
        return []

    sections: list[_FragmentBlock] = []
    first_start = selected[0].char_start
    if text[:first_start].strip():
        sections.append(
            _FragmentBlock(
                start=0,
                end=first_start,
                text=text[:first_start].strip("\n"),
                heading=None,
            )
        )

    for index, heading in enumerate(selected):
        next_start = len(text)
        for candidate in headings:
            if candidate.line_index <= heading.line_index:
                continue
            if candidate.level <= split_level:
                next_start = candidate.char_start
                break
        block_text = text[heading.char_start:next_start].strip("\n")
        if not block_text.strip():
            continue
        sections.append(
            _FragmentBlock(
                start=heading.char_start,
                end=next_start,
                text=block_text,
                heading=heading.text,
            )
        )

    return sections


def _choose_split_level(*, text: str, headings: list["_MarkdownHeading"]) -> int:
    levels = sorted({heading.level for heading in headings})
    best_level: int | None = None
    best_score: tuple[int, int, int, int] | None = None
    max_level = max(levels)
    for level in levels:
        sections = _simulate_sections_for_level(text=text, headings=headings, level=level)
        substantive = [section for section in sections if _is_substantive_section(section.text)]
        if len(substantive) < 2:
            continue
        average_words = sum(len(section.text.split()) for section in substantive) / len(substantive)
        if average_words < 35:
            continue
        deeper_levels_exist = max_level > level
        nested_sections = sum(1 for section in substantive if _section_has_nested_headings(section.text, base_level=level))
        if deeper_levels_exist and nested_sections == 0:
            continue
        score = (nested_sections, len(substantive), int(average_words), -level)
        if best_score is None or score > best_score:
            best_level = level
            best_score = score
    if best_level is not None:
        return best_level
    return min(levels)


def _simulate_sections_for_level(
    *,
    text: str,
    headings: list["_MarkdownHeading"],
    level: int,
) -> list["_FragmentBlock"]:
    selected = [heading for heading in headings if heading.level == level]
    sections: list[_FragmentBlock] = []
    for heading in selected:
        next_start = len(text)
        for candidate in headings:
            if candidate.line_index <= heading.line_index:
                continue
            if candidate.level <= level:
                next_start = candidate.char_start
                break
        block_text = text[heading.char_start:next_start].strip("\n")
        if not block_text.strip():
            continue
        sections.append(
            _FragmentBlock(
                start=heading.char_start,
                end=next_start,
                text=block_text,
                heading=heading.text,
            )
        )
    return sections


def _is_substantive_section(text: str) -> bool:
    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not nonempty_lines:
        return False
    word_count = len(text.split())
    return word_count >= 18 or len(nonempty_lines) >= 4


def _section_has_nested_headings(text: str, *, base_level: int) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        match = _MARKDOWN_HEADING_RE.match(stripped) if stripped else None
        if match is None:
            continue
        if len(match.group("marks")) > base_level:
            return True
    return False


def _merge_heading_only_blocks(blocks: list["_FragmentBlock"]) -> list["_FragmentBlock"]:
    merged: list[_FragmentBlock] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if _is_heading_only_block(block) and index + 1 < len(blocks):
            next_block = blocks[index + 1]
            text = f"{block.text.rstrip()}\n\n{next_block.text.lstrip()}".strip()
            merged.append(
                _FragmentBlock(
                    start=block.start,
                    end=next_block.end,
                    text=text,
                    heading=next_block.heading or block.heading,
                )
            )
            index += 2
            continue
        merged.append(block)
        index += 1
    return merged


def _is_heading_only_block(block: "_FragmentBlock") -> bool:
    lines = [line.strip() for line in block.text.splitlines() if line.strip()]
    return len(lines) == 1 and lines[0].startswith("#")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class _FragmentBlock:
    def __init__(self, *, start: int, end: int, text: str, heading: str | None) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.heading = heading


class _MarkdownHeading:
    def __init__(self, *, line_index: int, char_start: int, level: int, text: str) -> None:
        self.line_index = line_index
        self.char_start = char_start
        self.level = level
        self.text = text
