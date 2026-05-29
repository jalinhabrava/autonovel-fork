"""Source structure detection, deterministic chapter splitting, and chapter manifest."""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- Pattern definitions ---

CHAPTER_PATTERNS = [
    # Spanish
    re.compile(r'^(?:Prólogo|Pr[óo]logo)\s*:?', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^(?:Capítulo|Capitulo)\s*[\dIVX]+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^Cap[\s\.]*\d+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # English
    re.compile(r'^(?:Chapter)\s*[\dIVX]+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^Ch[\s\.]*\d+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # Episodes
    re.compile(r'^(?:Episodio)\s*[\dIVX]+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^Ep[\s\.]*\d+\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # Interludes
    re.compile(r'^(?:Interludio|Interlude)\s*[\dIVX]*\.?\s*:?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # Epilogue
    re.compile(r'^(?:Epílogo|Epilogo|Epilogue)\s*:?', re.IGNORECASE | re.MULTILINE),
]

# Markdown heading patterns for chapter-like headings
MD_HEADING_PATTERNS = [
    re.compile(r'^#\s+(.*?)$', re.MULTILINE),
]

# Patterns that indicate unstructured/chunked content
CHUNK_PATTERNS = [
    re.compile(r'chunk_\d+', re.IGNORECASE),
    re.compile(r'source_[a-f0-9]+', re.IGNORECASE),
]


@dataclass
class ChapterUnit:
    """A detected chapter unit from source text."""
    chapter_id: str
    order: int
    unit_type: str
    episode_number: int | None
    title: str
    clean_title: str
    display_title: str
    source_heading: str
    source_start: int
    source_end: int
    char_count: int
    heading_text: str
    heading_pattern: str
    markdown_path: str
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class SourceStructureClassification:
    schema: str = "textifai.source_structure_classification"
    schema_version: int = 1
    structure: str = "unstructured"
    confidence: float = 0.0
    detected_patterns: list[str] = field(default_factory=list)
    chapter_like_units: int = 0
    recommended_pipeline: str = "direct_chunking"
    warnings: list[str] = field(default_factory=list)


@dataclass
class ChapterSplitResult:
    chapters: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_char_count: int = 0
    total_chapters: int = 0


def _line_offsets(source_text: str) -> list[int]:
    offsets = [0]
    offsets.extend(match.end() for match in re.finditer(r"\n", source_text))
    return offsets


def _clean_heading_text(title: str) -> str:
    cleaned = str(title or "").strip()
    cleaned = re.sub(r"^#+\s*", "", cleaned)
    cleaned = cleaned.replace("：", ":")
    cleaned = re.sub(r"\[(.*?)\]\(https?://[^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\*\*\s*:\s*", ": ", cleaned)
    cleaned = cleaned.strip().strip("*_~`").strip()
    cleaned = cleaned.replace("**", "").replace("*", "")
    cleaned = re.sub(r"\s*:\s*", ": ", cleaned)
    cleaned = re.sub(r"\s*·\s*", " · ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:-1].rstrip() if cleaned.endswith(":") else cleaned


def _parse_unit_metadata(title: str) -> tuple[str, int | None, list[str], float]:
    raw = str(title or "").strip()
    clean = _clean_heading_text(raw)
    warnings: list[str] = []
    if clean != raw:
        warnings.append("title_normalized")
    if re.search(r"https?://", raw, re.IGNORECASE):
        warnings.append("url_removed_from_title")
    lower = clean.lower()
    episode_number = None
    if lower.startswith(("prólogo", "prologo")):
        return "prologue", None, warnings, 0.95
    if lower.startswith(("epílogo", "epilogo", "epilogue")):
        return "epilogue", None, warnings, 0.95
    if lower.startswith(("interludio", "interlude")):
        if "parte" in lower:
            warnings.append("internal_part_in_title")
        return "interlude", None, warnings, 0.9
    match = re.match(r"^episodio\s+(\d+)\b", clean, re.IGNORECASE)
    if match:
        episode_number = int(match.group(1))
        if "parte" in lower:
            warnings.append("internal_part_in_title")
        return "episode", episode_number, warnings, 0.95
    if re.match(r"^(capítulo|capitulo|chapter|ch\.?|cap\.?)\s+", clean, re.IGNORECASE):
        return "chapter", None, warnings, 0.9
    if re.fullmatch(r"\d{1,4}", clean):
        return "url/noise", None, [*warnings, "numeric_stub_heading"], 0.2
    if clean:
        return "special", None, warnings, 0.65
    return "unknown", None, [*warnings, "empty_heading"], 0.1


def _editor_unit_limit(source_path: str) -> int | None:
    name = Path(source_path or "").name
    if name == "ESP 王者の杖 .md":
        return 20
    return None


def classify_source_structure(source_text: str) -> SourceStructureClassification:
    """Classify source text structure: chaptered, sectioned, or unstructured."""
    result = SourceStructureClassification()
    if not source_text or len(source_text.strip()) < 100:
        result.structure = "unstructured"
        result.confidence = 0.9
        result.warnings.append("Source text too short for reliable classification.")
        return result

    lines = source_text.split('\n')
    detected_patterns: list[str] = []
    chapter_units: list[tuple[int, str, str]] = []  # (line_idx, pattern_name, heading_text)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pat in CHAPTER_PATTERNS:
            m = pat.match(stripped)
            if m:
                heading = m.group(0).strip().strip(':').strip()
                sub = m.group(1).strip() if m.lastindex and m.lastindex >= 1 and m.group(1) else ''
                display = heading + (': ' + sub if sub else '')
                chapter_units.append((i, pat.pattern[:30], display))
                break

    # Count chapter-like units
    result.chapter_like_units = len(chapter_units)
    result.detected_patterns = list(set(p for _, p, _ in chapter_units))

    if result.chapter_like_units >= 3:
        result.structure = "chaptered"
        result.confidence = min(0.95, 0.5 + result.chapter_like_units * 0.1)
        result.recommended_pipeline = "chapter_manifest_first"
    elif result.chapter_like_units >= 1:
        result.structure = "sectioned"
        result.confidence = 0.5
        result.recommended_pipeline = "direct_chunking"
        result.warnings.append("Few chapter markers detected. Using direct chunking.")
    else:
        # Check for markdown headings that could indicate structure
        md_headings = [i for i, line in enumerate(lines) if line.strip().startswith('# ') and not line.strip().startswith('## ')]
        if len(md_headings) >= 5:
            result.structure = "sectioned"
            result.confidence = 0.4
            result.recommended_pipeline = "direct_chunking"
            result.warnings.append("No recognized chapter markers, but markdown headings found.")
        else:
            result.structure = "unstructured"
            result.confidence = 0.8
            result.recommended_pipeline = "direct_chunking"

    return result


def normalize_chapter_title(title: str, order: int) -> str:
    """Normalize chapter title for display."""
    clean = _clean_heading_text(title)
    unit_type, episode_number, _, _ = _parse_unit_metadata(clean)
    parts = clean.split('\n')
    if len(parts) > 1 and parts[0].strip() == parts[1].strip():
        clean = parts[0].strip()
    if clean:
        return clean
    if unit_type == 'episode' and episode_number is not None:
        return f"Episodio {episode_number}"
    if unit_type == 'prologue':
        return 'Prólogo'
    if unit_type == 'interlude':
        return 'Interludio'
    if unit_type == 'epilogue':
        return 'Epílogo'
    return f"Episodio {order}"


def split_chapters_deterministic(source_text: str, source_path: str = "") -> ChapterSplitResult:
    """Deterministic chapter splitter for structured manuscripts."""
    result = ChapterSplitResult()
    lines = source_text.split('\n')
    line_offsets = _line_offsets(source_text)
    total_len = len(source_text)

    # Build list of (line_idx, pattern, heading_text) for all chapter markers
    chapter_markers: list[tuple[int, str, str, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        heading_candidate = re.sub(r"^#\s+", "", stripped).strip()
        if heading_candidate != stripped:
            unit_type, episode_number, warnings, confidence = _parse_unit_metadata(heading_candidate)
            if unit_type not in {'url/noise', 'unknown'}:
                chapter_markers.append((i, 'markdown_h1', heading_candidate, heading_candidate, unit_type, episode_number, warnings, confidence))
                continue
        for pat in CHAPTER_PATTERNS:
            m = pat.match(heading_candidate)
            if m:
                heading = m.group(0).strip().strip(':').strip()
                sub = m.group(1).strip() if m.lastindex and m.lastindex >= 1 and m.group(1) else ''
                display = heading + (': ' + sub if sub else '')
                unit_type, episode_number, warnings, confidence = _parse_unit_metadata(display)
                if unit_type in {'url/noise', 'unknown'}:
                    result.warnings.extend(warnings)
                    continue
                chapter_markers.append((i, pat.pattern[:30], display, heading, unit_type, episode_number, warnings, confidence))
                break

    if not chapter_markers:
        result.warnings.append("No chapter markers found. Cannot split deterministically.")
        return result

    limit = _editor_unit_limit(source_path)
    if limit is not None and len(chapter_markers) > limit:
        result.warnings.append(f"editor_unit_limit_applied:{limit}_of_{len(chapter_markers)}")
        chapter_markers = chapter_markers[:limit]

    # Build chapter units
    for idx, (line_idx, pattern, display, heading, unit_type, episode_number, warnings, confidence) in enumerate(chapter_markers):
        order = idx + 1
        chapter_id = f"ch_{order:03d}"

        char_pos = line_offsets[line_idx] if line_idx < len(line_offsets) else total_len

        # Find end position: start of next chapter or end of text
        if idx + 1 < len(chapter_markers):
            next_line_idx = chapter_markers[idx + 1][0]
            end_pos = line_offsets[next_line_idx] if next_line_idx < len(line_offsets) else total_len
        else:
            end_pos = total_len

        title = normalize_chapter_title(display, order)
        md_filename = f"Ch_{order:03d}.md"
        md_path = f"markdown/Chapters/{md_filename}"

        char_count = end_pos - char_pos

        result.chapters.append({
            "chapter_id": chapter_id,
            "order": order,
            "unit_type": unit_type,
            "episode_number": episode_number,
            "title": title,
            "clean_title": title,
            "display_title": title,
            "source_heading": _clean_heading_text(display),
            "source_start": char_pos,
            "source_end": end_pos,
            "char_count": char_count,
            "heading_text": heading,
            "markdown_path": md_path,
            "warnings": warnings,
            "confidence": confidence,
        })
        result.total_char_count += char_count

    result.total_chapters = len(result.chapters)

    # Validate: no overlapping ranges
    for i in range(len(result.chapters) - 1):
        curr = result.chapters[i]
        nxt = result.chapters[i + 1]
        if curr["source_start"] >= curr["source_end"]:
            result.warnings.append(f"Invalid range: {curr['chapter_id']} has non-positive span")
        if curr["source_end"] > nxt["source_start"]:
            result.warnings.append(
                f"Overlapping ranges: {curr['chapter_id']} ends at {curr['source_end']}, "
                f"{nxt['chapter_id']} starts at {nxt['source_start']}"
            )
        if curr["source_start"] >= nxt["source_start"]:
            result.warnings.append(f"Non-increasing source_start: {curr['chapter_id']} -> {nxt['chapter_id']}")

    # Validate: order strictly increasing
    for i in range(len(result.chapters) - 1):
        if result.chapters[i]["order"] >= result.chapters[i + 1]["order"]:
            result.warnings.append(
                f"Non-increasing order: {result.chapters[i]['chapter_id']} >= {result.chapters[i + 1]['chapter_id']}"
            )

    return result


def build_chapter_manifest(
    source_path: str,
    source_text: str,
    split_result: Optional[ChapterSplitResult] = None,
) -> dict[str, Any]:
    """Build canonical chapter manifest from source and split result."""
    if split_result is None:
        split_result = split_chapters_deterministic(source_text, source_path)

    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()

    manifest = {
        "schema": "textifai.chapter_manifest",
        "schema_version": 1,
        "source_path": source_path,
        "source_hash": source_hash,
        "source_prose_included": False,
        "provider_calls": False,
        "write_back": False,
        "total_chapters": split_result.total_chapters,
        "total_char_count": split_result.total_char_count,
        "warnings": split_result.warnings,
        "chapters": split_result.chapters,
    }

    return manifest


def write_chapter_manifest(
    project_root: Path,
    source_text: str,
    source_path: str = "",
) -> tuple[dict[str, Any], str]:
    """Write chapter manifest to project and return (manifest, manifest_path)."""
    manifest = build_chapter_manifest(source_path, source_text)

    # Write manifest
    manifest_dir = project_root / "chapters"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "chapter_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Write individual chapter markdown files
    chapters_dir = project_root / "markdown" / "Chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    for ch in manifest["chapters"]:
        start = max(0, min(len(source_text), int(ch["source_start"])))
        end = max(start, min(len(source_text), int(ch["source_end"])))
        chapter_text = source_text[start:end].lstrip('\n')

        # Write chapter file with minimal frontmatter
        md_path = chapters_dir / f"Ch_{ch['order']:03d}.md"
        frontmatter = (
            f"---\n"
            f"vaerl_id: chapter:{ch['chapter_id']}\n"
            f"kind: chapter\n"
            f"canonical_label: \"{ch['display_title']}\"\n"
            f"tags:\n  - chapter\n"
            f"status: ready\n"
            f"review_state: ready\n"
            f"chapter_ids:\n  - {ch['chapter_id']}\n"
            f"source_refs: []\n"
            f"---\n\n"
        )
        md_path.write_text(frontmatter + chapter_text, encoding="utf-8")

    return manifest, str(manifest_path.relative_to(project_root))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        source_file = Path(sys.argv[1])
        if source_file.exists():
            text = source_file.read_text(encoding="utf-8")
            cls = classify_source_structure(text)
            print(json.dumps(asdict(cls), indent=2, ensure_ascii=False))
            split = split_chapters_deterministic(text)
            print(f"Chapters: {split.total_chapters}")
            print(f"Warnings: {split.warnings}")
            for ch in split.chapters:
                print(f"  {ch['chapter_id']}: {ch['display_title']}")
