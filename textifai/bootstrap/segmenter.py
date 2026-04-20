from __future__ import annotations

import hashlib
import re
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentRecord, SourceFragment
from textifai.bootstrap.language import detect_language_profile
from textifai.obsidian.parser import strip_obsidian_frontmatter


_HEADING_RE = re.compile(
    r"^(#{1,6}\s+.+|(?:ch|chapter|scene|scn)[\s_-]*\d+.*)$",
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
    return _merge_heading_only_blocks(blocks)


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
