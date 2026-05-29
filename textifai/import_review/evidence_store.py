"""Project-owned evidence store and source map for TextifAI."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


@dataclass
class SourceMap:
    """Maps chapter_id and chunk refs to project-owned locations."""
    schema: str = "textifai.source_map"
    schema_version: int = 1
    source_hash: str = ""
    chapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_ref_aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    """A single evidence item in the evidence index."""
    evidence_id: str
    chapter_id: str
    chapter_title: str
    chapter_path: str
    char_start: int
    char_end: int
    excerpt: str
    summary: str
    technical_pointer: str
    review_ids: list[str] = field(default_factory=list)


@dataclass
class EvidenceIndex:
    schema: str = "textifai.evidence_index"
    schema_version: int = 1
    items: list[dict[str, Any]] = field(default_factory=list)


def build_source_map(
    chapter_manifest: dict[str, Any],
    source_hash: str,
) -> SourceMap:
    """Build source map from chapter manifest."""
    sm = SourceMap(source_hash=source_hash)

    for ch in chapter_manifest.get("chapters", []):
        cid = ch.get("chapter_id", "")
        sm.chapters[cid] = {
            "chapter_id": cid,
            "order": ch.get("order"),
            "title": ch.get("title"),
            "display_title": ch.get("display_title"),
            "markdown_path": ch.get("markdown_path"),
            "source_start": ch.get("source_start"),
            "source_end": ch.get("source_end"),
            "char_count": ch.get("char_count"),
        }
        # Alias: ch_001 -> markdown/Chapters/Ch_001.md
        sm.source_ref_aliases[cid] = ch.get("markdown_path", "")

    return sm


def build_evidence_index(
    review_queue: dict[str, Any],
    source_map: SourceMap,
    project_root: Path,
) -> EvidenceIndex:
    """Build evidence index from review queue and source map."""
    ei = EvidenceIndex()

    items = review_queue.get("items", review_queue.get("decision_items", []))
    for item in items:
        source_refs = item.get("source_refs", [])
        for ref in source_refs:
            chapter_id = ref.get("chapter_id", "")
            chunk_id = ref.get("chunk_id", "")
            char_start = ref.get("char_start", 0) or 0
            char_end = ref.get("char_end", 0) or 0

            # Resolve chapter
            ch_info = source_map.chapters.get(chapter_id, {})
            chapter_path = ch_info.get("markdown_path", "")
            chapter_title = ch_info.get("display_title", ch_info.get("title", chapter_id))

            # Try to resolve excerpt from chapter markdown
            excerpt = ""
            if chapter_path:
                md_path = project_root / chapter_path
                if md_path.exists():
                    try:
                        text = md_path.read_text(encoding="utf-8")
                        # Use char_start/char_end if available
                        if char_start < len(text):
                            end = min(len(text), char_end + 120) if char_end else char_start + 240
                            excerpt = text[char_start:end][:360]
                            # Clean excerpt
                            excerpt = ' '.join(excerpt.split())
                    except OSError:
                        pass

            # Generate evidence_id
            chunk_str = str(chunk_id or "unknown")
            chunk_str = str(chunk_id or 'unknown')
            evidence_id = f"ev_{chapter_id}_{chunk_str.split('_')[-1] if '_' in chunk_str else '0001'}"
            # Summary from review item
            summary = item.get("summary", item.get("human_reason", ""))

            ei.items.append({
                "evidence_id": evidence_id,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "chapter_path": chapter_path,
                "char_start": char_start,
                "char_end": char_end,
                "excerpt": excerpt,
                "summary": summary,
                "technical_pointer": chunk_id,
                "review_ids": [item.get("id", "")],
            })

    return ei


def write_evidence_store(
    project_root: Path,
    chapter_manifest: dict[str, Any],
    review_queue: dict[str, Any],
    source_hash: str,
) -> tuple[SourceMap, EvidenceIndex]:
    """Write evidence store to project and return (source_map, evidence_index)."""
    source_map = build_source_map(chapter_manifest, source_hash)
    evidence_index = build_evidence_index(review_queue, source_map, project_root)

    # Write source map
    evidence_dir = project_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    source_map_path = evidence_dir / "source_map.json"
    source_map_path.write_text(
        json.dumps(asdict(source_map), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Write evidence index
    evidence_index_path = evidence_dir / "evidence_index.json"
    evidence_index_path.write_text(
        json.dumps(asdict(evidence_index), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return source_map, evidence_index


def hydrate_review_evidence(
    review_queue: dict[str, Any],
    evidence_index: EvidenceIndex,
    source_map: SourceMap,
) -> dict[str, Any]:
    """Hydrate review queue with project-owned evidence."""
    hydrated = dict(review_queue)

    # Build evidence lookup by review_id
    evidence_by_review: dict[str, list[dict[str, Any]]] = {}
    for ev in evidence_index.items:
        for rid in ev.get("review_ids", []):
            if rid not in evidence_by_review:
                evidence_by_review[rid] = []
            evidence_by_review[rid].append(ev)

    # Update review items
    items = hydrated.get("decision_items", hydrated.get("items", []))
    for item in items:
        rid = item.get("id", "")
        if rid in evidence_by_review:
            # Enrich with evidence from index
            evs = evidence_by_review[rid]
            item["evidence_refs"] = [
                {
                    "evidence_id": ev["evidence_id"],
                    "chapter_id": ev["chapter_id"],
                    "chapter_label": ev["chapter_title"],
                    "chapter_path": ev["chapter_path"],
                    "has_text": bool(ev["excerpt"]),
                    "excerpt": ev["excerpt"],
                    "pointer": ev["technical_pointer"],
                    "pointer_short": ev["technical_pointer"].split("_")[-2:] if len(ev["technical_pointer"].split("_")) > 2 else ev["technical_pointer"],
                }
                for ev in evs
            ]

    return hydrated


if __name__ == "__main__":
    import sys
    print("Evidence store module loaded.")
