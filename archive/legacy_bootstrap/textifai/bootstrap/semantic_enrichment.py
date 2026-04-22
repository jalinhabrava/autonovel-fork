from __future__ import annotations

import re
from dataclasses import dataclass, field

from textifai.bootstrap.contracts import SourceDocumentRecord, SourceFragment
from vault.schema import slugify


_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", flags=re.MULTILINE)
_LIST_LINE_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", flags=re.MULTILINE)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class FragmentSemanticProfile:
    artifact_type: str
    title: str
    slug: str
    artifact_stage: str
    promotion_status: str
    canonical_subject: str | None
    semantic_class: str | None
    source_section_title: str | None
    fragment_role: str | None
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    world_terms: list[str] = field(default_factory=list)
    character_refs: list[str] = field(default_factory=list)
    lore_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def enrich_fragment_semantics(
    *,
    document: SourceDocumentRecord,
    fragment: SourceFragment,
    artifact_type: str,
    fragment_title_hint: str | None,
    fragment_notes: list[str] | None = None,
) -> FragmentSemanticProfile:
    heading = _extract_heading(fragment_title_hint, fragment.text)
    section_title = heading or _first_heading(fragment.text)
    title = _fallback_title(document=document, heading=heading, fragment=fragment)
    normalized_artifact_type = artifact_type if artifact_type in {
        "character",
        "lore",
        "scene",
        "chapter",
        "mixed_note",
        "project_note",
    } else "mixed_note"
    if normalized_artifact_type == "project_note":
        normalized_artifact_type = "mixed_note"

    semantic_class = _structural_semantic_class(fragment.text, heading=heading)
    fragment_role = _fragment_role(fragment.text, heading=heading)
    notes = list(fragment_notes or [])
    notes.extend(
        [
            "semantic_normalization_requires_llm",
            "kept_in_staging_by_default",
        ]
    )
    if heading:
        notes.append("heading_preserved_as_structural_context")
    if semantic_class == "structural_note":
        notes.append("structural_fragment_not_promoted_without_llm")

    return FragmentSemanticProfile(
        artifact_type=normalized_artifact_type,
        title=title,
        slug=slugify(title) or slugify(document.filename.rsplit(".", 1)[0]) or "imported-fragment",
        artifact_stage="candidate_artifact",
        promotion_status="staged_candidate",
        canonical_subject=None,
        semantic_class=semantic_class,
        source_section_title=section_title,
        fragment_role=fragment_role,
        entities=[],
        topics=[],
        world_terms=[],
        character_refs=[],
        lore_refs=[],
        notes=_dedupe(notes),
    )


def _extract_heading(fragment_title_hint: str | None, text: str) -> str | None:
    if fragment_title_hint and fragment_title_hint.strip():
        return _clean_heading(fragment_title_hint)
    return _first_heading(text)


def _first_heading(text: str) -> str | None:
    match = _HEADING_LINE_RE.search(text)
    if not match:
        return None
    return _clean_heading(match.group("title"))


def _clean_heading(value: str) -> str:
    cleaned = value.strip().strip("#").strip()
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned


def _fallback_title(*, document: SourceDocumentRecord, heading: str | None, fragment: SourceFragment) -> str:
    if heading:
        return heading
    text = fragment.text.strip()
    first_nonempty = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_nonempty:
        return _truncate_title(first_nonempty.lstrip("#").strip())
    stem = document.filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    return stem or "Imported fragment"


def _truncate_title(value: str, *, limit: int = 80) -> str:
    compact = _WHITESPACE_RE.sub(" ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _structural_semantic_class(text: str, *, heading: str | None) -> str:
    stripped = text.strip()
    nonempty_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if heading and len(nonempty_lines) <= 2:
        return "structural_note"
    if nonempty_lines and all(_LIST_LINE_RE.match(line) for line in nonempty_lines):
        return "list_fragment"
    if _LIST_LINE_RE.search(stripped):
        return "section_fragment"
    return "unresolved_without_llm"


def _fragment_role(text: str, *, heading: str | None) -> str:
    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if heading and len(nonempty_lines) <= 2:
        return "structural_container"
    if nonempty_lines and all(_LIST_LINE_RE.match(line) for line in nonempty_lines):
        return "list_section"
    if heading:
        return "headed_section"
    return "body_section"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
