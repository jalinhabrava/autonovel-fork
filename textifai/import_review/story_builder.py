from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap import SourceDocumentInventory
from textifai.bootstrap.segmenter import segment_source_document
from textifai.bootstrap.source_reader import read_source_documents
from textifai.obsidian import open_obsidian_source
from vault.notes import write_artifact_payload
from vault.schema import slugify


@dataclass(frozen=True)
class StoryBuildConfig:
    provider_name: str
    model: str
    task_name: str = "bootstrap_normalization"
    max_tokens: int = 1600
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1


@dataclass(frozen=True)
class StoryBuildResult:
    chapter_paths: list[str] = field(default_factory=list)
    summary_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    audit: dict[str, object] = field(default_factory=dict)


def build_story_notes(
    vault_root: str | Path,
    *,
    inventory: SourceDocumentInventory,
    config: StoryBuildConfig,
    progress_log_path: str | None = None,
) -> StoryBuildResult:
    source_texts = read_source_documents(inventory)
    canonical_notes = _canonical_note_catalog(vault_root)
    chapter_candidates = _discover_chapter_candidates(inventory=inventory, source_texts=source_texts)
    warnings: list[str] = []
    chapter_paths: list[str] = []
    summary_paths: list[str] = []
    audit_entries: list[dict[str, object]] = []
    _emit_progress(progress_log_path, phase="story_builder", event="discovered_candidates", candidate_count=len(chapter_candidates))

    if not chapter_candidates:
        warnings.append("no_chapter_like_sources_detected")
        return StoryBuildResult(
            chapter_paths=[],
            summary_paths=[],
            warnings=warnings,
            audit={"chapter_candidates": [], "written_chapters": [], "written_summaries": [], "warnings": warnings},
        )

    for index, candidate in enumerate(chapter_candidates, start=1):
        chapter_title = candidate["title"]
        chapter_slug = candidate["slug"]
        chapter_text = str(candidate["text"])
        chapter_number = index
        linked_text, linked_subjects = _wikify_text(chapter_text, canonical_notes)
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="chapter_started",
            chapter_index=index,
            chapter_title=chapter_title,
            linked_subject_count=len(linked_subjects),
        )
        chapter_body = "\n\n".join(
            [
                "## Chapter Text",
                linked_text.strip(),
            ]
        ).strip()
        chapter_metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "primary",
            "chapter_number": chapter_number,
            "canonical_subject": chapter_title,
            "semantic_class": "chapter_full_text",
            "source_path": candidate["source_path"],
            "dominant_language": candidate["language"],
            "linked_primary_subjects": ", ".join(linked_subjects),
        }
        chapter_path = write_artifact_payload(
            vault_root,
            artifact_kind="note",
            artifact_type="chapter",
            entity_id=f"ch_{chapter_number:02d}_{chapter_slug}",
            title=chapter_title,
            body=chapter_body,
            status="pending_revision",
            metadata=chapter_metadata,
        )
        chapter_paths.append(str(chapter_path))

        summary_payload = _compose_chapter_summary(
            config=config,
            chapter_title=chapter_title,
            chapter_text=chapter_text,
            language=candidate["language"],
            canonical_catalog=[item["title"] for item in canonical_notes],
        )
        if summary_payload is None:
            warnings.append(f"summary_generation_failed:{chapter_title}")
            audit_entries.append(
                {
                    "chapter_title": chapter_title,
                    "chapter_path": str(chapter_path),
                    "summary_path": None,
                    "linked_subjects": linked_subjects,
                    "status": "chapter_only",
                }
            )
            _emit_progress(progress_log_path, phase="story_builder", event="summary_failed", chapter_title=chapter_title)
            continue
        summary_markdown = str(summary_payload.get("summary_markdown") or "").strip()
        summary_text, summary_links = _wikify_text(summary_markdown, canonical_notes)
        summary_metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "supporting",
            "chapter_number": chapter_number,
            "canonical_subject": chapter_title,
            "semantic_class": "chapter_summary",
            "source_path": candidate["source_path"],
            "dominant_language": candidate["language"],
            "linked_primary_subjects": ", ".join(summary_links),
            "summary_for_chapter": Path(chapter_path).name,
        }
        summary_path = write_artifact_payload(
            vault_root,
            artifact_kind="note",
            artifact_type="chapter_summary",
            entity_id=f"ch_{chapter_number:02d}_{chapter_slug}_summary",
            title=str(summary_payload.get("title") or f"{chapter_title} Summary").strip() or f"{chapter_title} Summary",
            body=summary_text,
            status="pending_revision",
            metadata=summary_metadata,
        )
        summary_paths.append(str(summary_path))
        audit_entries.append(
            {
                "chapter_title": chapter_title,
                "chapter_path": str(chapter_path),
                "summary_path": str(summary_path),
                "linked_subjects": linked_subjects,
                "summary_linked_subjects": summary_links,
                "status": "chapter_and_summary_written",
            }
        )
        _emit_progress(progress_log_path, phase="story_builder", event="chapter_written", chapter_title=chapter_title, chapter_path=str(chapter_path), summary_path=str(summary_path))

    return StoryBuildResult(
        chapter_paths=chapter_paths,
        summary_paths=summary_paths,
        warnings=warnings,
        audit={
            "chapter_candidates": [
                {
                    "title": candidate["title"],
                    "slug": candidate["slug"],
                    "source_path": candidate["source_path"],
                    "language": candidate["language"],
                    "word_count": len(str(candidate["text"]).split()),
                }
                for candidate in chapter_candidates
            ],
            "written_chapters": chapter_paths,
            "written_summaries": summary_paths,
            "entries": audit_entries,
            "warnings": warnings,
        },
    )


def _discover_chapter_candidates(
    *,
    inventory: SourceDocumentInventory,
    source_texts: dict[str, str],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for document in inventory.documents:
        text = source_texts.get(document.source_id, "")
        if not text.strip():
            continue
        fragments = segment_source_document(document, text)
        chapter_fragments = [
            fragment
            for fragment in fragments
            if fragment.detected_kind == "chapter" and len(fragment.text.split()) >= 8
        ]
        if chapter_fragments:
            for fragment in chapter_fragments:
                title = _fragment_title(fragment.text) or document.filename.rsplit(".", 1)[0]
                candidates.append(
                    {
                        "title": title,
                        "slug": slugify(title),
                        "text": fragment.text.strip(),
                        "language": document.dominant_language,
                        "source_path": document.path,
                    }
                )
            continue
        if "chapter" in document.likely_content_kinds and len(text.split()) >= 12:
            title = document.filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
            candidates.append(
                {
                    "title": title or document.filename,
                    "slug": slugify(title or document.filename),
                    "text": text.strip(),
                    "language": document.dominant_language,
                    "source_path": document.path,
                }
            )
    return candidates


def _canonical_note_catalog(vault_root: str | Path) -> list[dict[str, object]]:
    source = open_obsidian_source(vault_root)
    notes = []
    for note in source.reader.list_notes():
        if "99_Import_Staging" in note.vault_relative_path:
            continue
        note_role = str(note.frontmatter.get("note_role") or "").strip().casefold()
        if note_role and note_role != "primary":
            continue
        if note.artifact_type not in {"character", "location", "lore"}:
            continue
        aliases = []
        for raw in [*note.aliases, *note.project_confirmed_aliases]:
            text = str(raw).strip()
            if text and slugify(text) != slugify(note.title):
                aliases.append(text)
        notes.append(
            {
                "title": note.title,
                "slug": note.note_id,
                "aliases": list(dict.fromkeys(aliases)),
            }
        )
    notes.sort(key=lambda item: len(str(item["title"])), reverse=True)
    return notes


def _wikify_text(text: str, canonical_notes: list[dict[str, object]]) -> tuple[str, list[str]]:
    if not text.strip():
        return text, []
    linked_subjects: list[str] = []
    protected: dict[str, str] = {}

    def _protect(match: re.Match[str]) -> str:
        token = f"__WIKILINK_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    working = re.sub(r"\[\[[^\]]+\]\]", _protect, text)
    for note in canonical_notes:
        title = str(note["title"]).strip()
        if not title:
            continue
        for label in [title, *[str(alias).strip() for alias in note.get("aliases", []) if str(alias).strip()]]:
            pattern = _link_pattern(label)
            if pattern is None:
                continue
            replacement = f"[[{title}]]"
            new_working, replacements = pattern.subn(replacement, working)
            if replacements > 0:
                working = new_working
                linked_subjects.append(title)
                break
    for token, original in protected.items():
        working = working.replace(token, original)
    return working, list(dict.fromkeys(linked_subjects))


def _link_pattern(label: str) -> re.Pattern[str] | None:
    escaped = re.escape(label.strip())
    if not escaped:
        return None
    return re.compile(rf"(?<!\[\[)(?<![\w]){escaped}(?![\w])(?!\]\])")


def _compose_chapter_summary(
    *,
    config: StoryBuildConfig,
    chapter_title: str,
    chapter_text: str,
    language: str | None,
    canonical_catalog: list[str],
) -> dict[str, object] | None:
    if get_text_provider_config_error(config.task_name, config.provider_name):
        return None
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Write an Obsidian-ready chapter summary grounded in the chapter text.",
        "language": language,
        "chapter_title": chapter_title,
        "canonical_note_catalog": canonical_catalog[:80],
        "chapter_excerpt": chapter_text[:12000],
        "required_output_schema": {
            "title": "string",
            "summary_markdown": "string",
        },
        "rules": [
            "Return JSON only.",
            "Write in the requested language when available.",
            "Produce a concise narrative summary in markdown prose, not bullet fragments only.",
            "Do not invent facts outside the chapter.",
            "Use names exactly as they appear in the canonical catalog when possible.",
        ],
    }
    try:
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are composing an Obsidian-ready chapter summary for a fiction vault. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
            )
        )
    except TextProviderError:
        return None
    return extract_json_payload(response.text)


def _fragment_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped:
            break
    return None


def _emit_progress(path: str | None, **payload: object) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
