"""Project-owned evidence store and source map for TextifAI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceMap:
    schema: str = "textifai.source_map"
    schema_version: int = 2
    source_hash: str = ""
    chapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_ref_aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceIndex:
    schema: str = "textifai.evidence_index"
    schema_version: int = 2
    items: list[dict[str, Any]] = field(default_factory=list)


def _clean_excerpt(text: str) -> str:
    return " ".join((text or "").replace("\r", "\n").split())[:360]


def _meaningful_excerpt(text: str) -> str:
    lines = [line.strip() for line in (text or '').replace('\r', '\n').split('\n')]
    filtered: list[str] = []
    in_frontmatter = False
    for line in lines:
        if line == '---':
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not line:
            continue
        if ':' in line and line.split(':', 1)[0].strip() in {'vaerl_id', 'kind', 'canonical_label', 'status', 'review_state', 'source_refs', 'chapter_ids', 'tags'}:
            continue
        filtered.append(line)
    return _clean_excerpt(' '.join(filtered[:8]))


def _extract_excerpt(project_root: Path, chapter_path: str, char_start: int, char_end: int) -> str:
    if not chapter_path:
        return ""
    md_path = project_root / chapter_path
    if not md_path.exists():
        return ""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if char_start < 0 or char_start >= len(text):
        return ""
    end = min(len(text), (char_end if char_end > char_start else char_start + 220) + 120)
    return _meaningful_excerpt(text[max(0, char_start - 40):end])


def _source_ref_key(chapter_id: str, chunk_id: str, char_start: int, char_end: int) -> str:
    raw = f"{chapter_id}|{chunk_id}|{char_start}|{char_end}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_source_map(chapter_manifest: dict[str, Any], source_hash: str, review_queue: dict[str, Any], project_root: Path) -> SourceMap:
    sm = SourceMap(source_hash=source_hash)
    for ch in chapter_manifest.get("chapters", []):
        cid = str(ch.get("chapter_id") or "").strip()
        if not cid:
            continue
        chapter_path = str(ch.get("markdown_path") or "")
        sm.chapters[cid] = {
            "chapter_id": cid,
            "order": ch.get("order"),
            "title": ch.get("title"),
            "display_title": ch.get("display_title"),
            "markdown_path": chapter_path,
            "source_start": ch.get("source_start"),
            "source_end": ch.get("source_end"),
            "char_count": ch.get("char_count"),
        }
        sm.source_ref_aliases[cid] = chapter_path

    items = review_queue.get("items", review_queue.get("decision_items", []))
    for item in items:
        for ref in item.get("source_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            chapter_id = str(ref.get("chapter_id") or "").strip()
            chunk_id = str(ref.get("chunk_id") or "").strip()
            if not chapter_id or not chunk_id:
                continue
            ch_info = sm.chapters.get(chapter_id) or {}
            chapter_path = str(ch_info.get("markdown_path") or "")
            char_start = int(ref.get("char_start") or 0)
            char_end = int(ref.get("char_end") or 0)
            if char_end < char_start:
                char_end = char_start
            excerpt = _extract_excerpt(project_root, chapter_path, char_start, char_end)
            text_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest() if excerpt else ""
            sm.chunks[chunk_id] = {
                "chunk_id": chunk_id,
                "chapter_id": chapter_id,
                "chapter_path": chapter_path,
                "char_start": char_start,
                "char_end": char_end,
                "text_hash": text_hash,
                "excerpt": excerpt,
                "resolvable_range": {
                    "chapter_path": chapter_path,
                    "char_start": char_start,
                    "char_end": char_end,
                },
            }
    return sm


def build_evidence_index(review_queue: dict[str, Any], source_map: SourceMap, project_root: Path) -> EvidenceIndex:
    ei = EvidenceIndex()
    items = review_queue.get("items", review_queue.get("decision_items", []))
    for item in items:
        review_item_id = str(item.get("review_item_id") or item.get("id") or "").strip()
        summary = str(item.get("summary") or item.get("human_reason") or "")
        for ref in item.get("source_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            chapter_id = str(ref.get("chapter_id") or "").strip()
            chunk_id = str(ref.get("chunk_id") or "").strip()
            char_start = int(ref.get("char_start") or 0)
            char_end = int(ref.get("char_end") or 0)
            source_ref_key = _source_ref_key(chapter_id, chunk_id, char_start, char_end)
            ch_info = source_map.chapters.get(chapter_id, {})
            chapter_path = str(ch_info.get("markdown_path") or "")
            chapter_title = str(ch_info.get("display_title") or ch_info.get("title") or chapter_id)
            chunk = source_map.chunks.get(chunk_id, {})
            if chunk:
                chapter_path = str(chunk.get("chapter_path") or chapter_path)
                char_start = int(chunk.get("char_start") or char_start)
                char_end = int(chunk.get("char_end") or char_end)
            excerpt = str(chunk.get("excerpt") or _extract_excerpt(project_root, chapter_path, char_start, char_end))
            reason = "" if excerpt else ("missing_chunk" if not chunk_id else "chunk_unresolvable")
            evidence_id = f"ev_{review_item_id or 'unknown'}_{source_ref_key}"
            ei.items.append({
                "evidence_id": evidence_id,
                "review_item_id": review_item_id,
                "source_ref_key": source_ref_key,
                "chunk_id": chunk_id,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "chapter_path": chapter_path,
                "char_start": char_start,
                "char_end": char_end,
                "excerpt": excerpt,
                "summary": summary,
                "reason": reason,
                "technical_pointer": chunk_id or source_ref_key,
                "review_ids": [review_item_id] if review_item_id else [],
            })
    return ei


def write_evidence_store(project_root: Path, chapter_manifest: dict[str, Any], review_queue: dict[str, Any], source_hash: str) -> tuple[SourceMap, EvidenceIndex]:
    source_map = build_source_map(chapter_manifest, source_hash, review_queue, project_root)
    evidence_index = build_evidence_index(review_queue, source_map, project_root)
    evidence_dir = project_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "source_map.json").write_text(json.dumps(asdict(source_map), ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "evidence_index.json").write_text(json.dumps(asdict(evidence_index), ensure_ascii=False, indent=2), encoding="utf-8")
    return source_map, evidence_index
