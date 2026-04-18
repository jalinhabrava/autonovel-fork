from __future__ import annotations

import hashlib
import re
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentRecord, SourceFragment
from textifai.bootstrap.language import detect_language_profile


_HEADING_RE = re.compile(
    r"^(#{1,6}\s+.+|chapter\s+\d+.*|cap[ií]tulo\s+\d+.*|scene\s+\d+.*|escena\s+\d+.*)$",
    flags=re.IGNORECASE,
)


def segment_source_document(
    document: SourceDocumentRecord,
    text: str,
) -> list[SourceFragment]:
    if not text.strip():
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

    blocks = _split_on_headings(text)
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
    haystack = " ".join(filter(None, [heading, text[:400]])).casefold()
    if _matches(haystack, {"character", "personaje", "profile", "bio", "protagonist"}):
        return "character", 0.92, False
    if _matches(haystack, {"lore", "world", "worldbuilding", "mundo", "setting", "canon"}):
        return "lore", 0.88, False
    if _matches(haystack, {"scene", "escena"}):
        return "scene", 0.9, False
    if _matches(haystack, {"chapter", "capítulo", "capitulo"}):
        return "chapter", 0.94, False
    if len(text.split()) > 700:
        return "chapter", 0.72, True
    if len(text.split()) > 180:
        return "mixed_note", 0.55, True
    return "project_note", 0.42, True


def _matches(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _split_on_headings(text: str) -> list[_FragmentBlock]:
    lines = text.splitlines(keepends=True)
    blocks: list[_FragmentBlock] = []
    current_lines: list[str] = []
    current_start = 0
    current_heading: str | None = None
    offset = 0
    for line in lines:
        stripped = line.strip()
        is_heading = bool(stripped) and bool(_HEADING_RE.match(stripped))
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
    return blocks


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class _FragmentBlock:
    def __init__(self, *, start: int, end: int, text: str, heading: str | None) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.heading = heading
