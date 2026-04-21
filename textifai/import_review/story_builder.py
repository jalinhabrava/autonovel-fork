from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap import SourceDocumentInventory
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.obsidian import open_obsidian_source
from vault.notes import write_artifact_payload
from vault.schema import slugify


@dataclass(frozen=True)
class StoryBuildConfig:
    provider_name: str
    model: str
    task_name: str = "bootstrap_normalization"
    max_tokens: int = 1800
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 3
    max_chapter_excerpt_chars: int = 9000
    max_llm_calls: int = 80
    checkpoint_dirname: str = "99_System/bootstrap_checkpoints/story_builder"


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
    vault_root = Path(vault_root)
    source_texts = read_source_documents(inventory, progress_log_path=progress_log_path)
    canonical_notes = _canonical_note_catalog(vault_root)
    chapter_candidates = _discover_chapter_candidates(inventory=inventory, source_texts=source_texts)
    warnings: list[str] = []
    chapter_paths: list[str] = []
    summary_paths: list[str] = []
    audit_entries: list[dict[str, object]] = []
    chapter_analyses: list[dict[str, object]] = []
    checkpoint_dir = vault_root / config.checkpoint_dirname
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    _emit_progress(progress_log_path, phase="story_builder", event="discovered_candidates", candidate_count=len(chapter_candidates))

    if not chapter_candidates:
        warnings.append("no_chapter_like_sources_detected")
        _write_story_builder_audits(
            vault_root=vault_root,
            chapter_candidates=[],
            chapter_analyses=[],
        )
        return StoryBuildResult(
            chapter_paths=[],
            summary_paths=[],
            warnings=warnings,
            audit={
                "chapter_candidates": [],
                "chapter_analyses": [],
                "written_chapters": [],
                "written_summaries": [],
                "warnings": warnings,
            },
        )

    llm_calls_used = 0
    for index, candidate in enumerate(chapter_candidates, start=1):
        chapter_title = str(candidate["title"])
        chapter_slug = str(candidate["slug"])
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
            page_start=candidate.get("page_start"),
            page_end=candidate.get("page_end"),
        )

        analysis_payload = None
        if llm_calls_used < config.max_llm_calls:
            analysis_payload = _load_or_analyze_chapter(
                config=config,
                checkpoint_dir=checkpoint_dir,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_slug=chapter_slug,
                chapter_text=chapter_text,
                language=candidate["language"],
                canonical_catalog=canonical_notes,
                source_path=str(candidate["source_path"]),
                progress_log_path=progress_log_path,
            )
            if analysis_payload is not None and not analysis_payload.get("_loaded_from_checkpoint", False):
                llm_calls_used += int(analysis_payload.get("_llm_calls_used") or 0)
        else:
            warnings.append(f"chapter_analysis_budget_exhausted:{chapter_title}")

        if analysis_payload is None:
            warnings.append(f"chapter_analysis_failed:{chapter_title}")
            analysis_payload = {
                "summary_markdown": "",
                "characters": [],
                "places": [],
                "concepts": [],
                "events": [],
                "relations": [],
                "new_traits": [],
                "aliases": [],
                "review_items": [],
                "confidence": 0.0,
            }

        chapter_analyses.append(
            {
                "chapter_title": chapter_title,
                "chapter_slug": chapter_slug,
                "source_path": str(candidate["source_path"]),
                "page_start": candidate.get("page_start"),
                "page_end": candidate.get("page_end"),
                "detection_confidence": candidate.get("confidence"),
                "analysis": {key: value for key, value in analysis_payload.items() if not str(key).startswith("_")},
            }
        )

        chapter_body = "\n\n".join(["## Chapter Text", linked_text.strip()]).strip()
        chapter_metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "chapter",
            "entity_kind": "chapter",
            "chapter_number": chapter_number,
            "canonical_subject": chapter_title,
            "semantic_class": "chapter_full_text",
            "source_path": candidate["source_path"],
            "dominant_language": candidate["language"],
            "linked_primary_subjects": ", ".join(linked_subjects),
            "evidence_sources": str(candidate["source_path"]),
            "confidence": candidate.get("confidence"),
            "review_state": "canonical",
            "page_start": candidate.get("page_start"),
            "page_end": candidate.get("page_end"),
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

        summary_markdown = str(analysis_payload.get("summary_markdown") or "").strip()
        if not summary_markdown:
            summary_markdown = (
                _synthesize_chapter_summary(
                    config=config,
                    chapter_title=chapter_title,
                    chapter_text=chapter_text,
                    analysis_payload=analysis_payload,
                    language=candidate["language"],
                    canonical_catalog=canonical_notes,
                    progress_log_path=progress_log_path,
                )
                or ""
            ).strip()
        if not summary_markdown:
            warnings.append(f"summary_generation_failed:{chapter_title}")
            audit_entries.append(
                {
                    "chapter_title": chapter_title,
                    "chapter_path": str(chapter_path),
                    "summary_path": None,
                    "linked_subjects": linked_subjects,
                    "page_start": candidate.get("page_start"),
                    "page_end": candidate.get("page_end"),
                    "status": "chapter_only",
                }
            )
            _emit_progress(progress_log_path, phase="story_builder", event="summary_failed", chapter_title=chapter_title)
            continue

        summary_text, summary_links = _wikify_text(summary_markdown, canonical_notes)
        summary_metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "chapter_summary",
            "entity_kind": "chapter_summary",
            "chapter_number": chapter_number,
            "canonical_subject": chapter_title,
            "semantic_class": "chapter_summary",
            "source_path": candidate["source_path"],
            "dominant_language": candidate["language"],
            "linked_primary_subjects": ", ".join(summary_links),
            "summary_for_chapter": Path(chapter_path).name,
            "evidence_sources": str(candidate["source_path"]),
            "confidence": analysis_payload.get("confidence"),
            "review_state": "canonical",
            "page_start": candidate.get("page_start"),
            "page_end": candidate.get("page_end"),
        }
        summary_path = write_artifact_payload(
            vault_root,
            artifact_kind="note",
            artifact_type="chapter_summary",
            entity_id=f"ch_{chapter_number:02d}_{chapter_slug}_summary",
            title=f"{chapter_title} Summary",
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
                "page_start": candidate.get("page_start"),
                "page_end": candidate.get("page_end"),
                "status": "chapter_and_summary_written",
            }
        )
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="chapter_written",
            chapter_title=chapter_title,
            chapter_path=str(chapter_path),
            summary_path=str(summary_path),
        )

    _write_story_builder_audits(
        vault_root=vault_root,
        chapter_candidates=chapter_candidates,
        chapter_analyses=chapter_analyses,
    )
    return StoryBuildResult(
        chapter_paths=chapter_paths,
        summary_paths=summary_paths,
        warnings=warnings,
        audit={
            "chapter_candidates": chapter_candidates,
            "chapter_analyses": chapter_analyses,
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
        detected_chapters = detect_story_chapters(document, text)
        if detected_chapters:
            for chapter in detected_chapters:
                candidates.append(
                    {
                        "title": chapter.title,
                        "slug": chapter.slug,
                        "text": chapter.text,
                        "language": document.dominant_language,
                        "source_path": document.path,
                        "page_start": chapter.page_start,
                        "page_end": chapter.page_end,
                        "confidence": chapter.confidence,
                        "source_id": chapter.source_id,
                        "detection_signals": chapter.detection_signals,
                    }
                )
            continue
        if "chapter" in document.likely_content_kinds and len(text.split()) >= 80:
            title = document.filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
            candidates.append(
                {
                    "title": title or document.filename,
                    "slug": slugify(title or document.filename),
                    "text": text.strip(),
                    "language": document.dominant_language,
                    "source_path": document.path,
                    "page_start": 1 if document.extracted_page_count else None,
                    "page_end": document.extracted_page_count or None,
                    "confidence": 0.35,
                    "source_id": document.source_id,
                    "detection_signals": ["whole_document_fallback"],
                }
            )
    return candidates


def _canonical_note_catalog(vault_root: str | Path) -> list[dict[str, object]]:
    source = open_obsidian_source(vault_root)
    notes = []
    for note in source.reader.list_notes():
        if "99_Import_Staging" in note.vault_relative_path or "90_Review" in note.vault_relative_path:
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
        notes.append({"title": note.title, "slug": note.note_id, "aliases": list(dict.fromkeys(aliases))})
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


def _load_or_analyze_chapter(
    *,
    config: StoryBuildConfig,
    checkpoint_dir: Path,
    chapter_number: int,
    chapter_title: str,
    chapter_slug: str,
    chapter_text: str,
    language: str | None,
    canonical_catalog: list[dict[str, object]],
    source_path: str,
    progress_log_path: str | None = None,
) -> dict[str, object] | None:
    checkpoint_path = checkpoint_dir / f"chapter_{chapter_number:03d}_{chapter_slug}.json"
    source_hash = slugify(f"{chapter_title}_{len(chapter_text)}_{source_path}")
    if checkpoint_path.exists():
        try:
            cached = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if cached.get("source_hash") == source_hash:
                return {**cached.get("analysis", {}), "_loaded_from_checkpoint": True, "_llm_calls_used": 0}
        except json.JSONDecodeError:
            pass

    if get_text_provider_config_error(config.task_name, config.provider_name):
        return None

    chunks = _chunk_chapter_text(chapter_text, max_chars=config.max_chapter_excerpt_chars)
    analyses: list[dict[str, Any]] = []
    llm_calls_used = 0
    for chunk_index, chunk in enumerate(chunks, start=1):
        payload = _analyze_chapter_chunk(
            config=config,
            chapter_title=chapter_title,
            chapter_text=chunk,
            language=language,
            canonical_catalog=canonical_catalog,
            chunk_index=chunk_index,
            chunk_total=len(chunks),
            progress_log_path=progress_log_path,
        )
        if payload is None:
            return None
        analyses.append(payload)
        llm_calls_used += 1

    merged = _merge_chapter_analysis_payloads(analyses)
    checkpoint_path.write_text(
        json.dumps(
            {
                "chapter_title": chapter_title,
                "source_hash": source_hash,
                "source_path": source_path,
                "analysis": merged,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {**merged, "_loaded_from_checkpoint": False, "_llm_calls_used": llm_calls_used}


def _analyze_chapter_chunk(
    *,
    config: StoryBuildConfig,
    chapter_title: str,
    chapter_text: str,
    language: str | None,
    canonical_catalog: list[dict[str, object]],
    chunk_index: int,
    chunk_total: int,
    progress_log_path: str | None,
) -> dict[str, object] | None:
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Analyze one chapter chunk and return structured grounded findings for vault bootstrap.",
        "language": language,
        "chapter_title": chapter_title,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "canonical_note_catalog": [item["title"] for item in canonical_catalog[:120]],
        "chapter_excerpt": chapter_text[: config.max_chapter_excerpt_chars],
        "required_output_schema": {
            "characters": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "places": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "concepts": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "events": [{"title": "string", "summary": "string", "related_subjects": ["string"], "confidence": 0.0}],
            "relations": [{"subjects": ["string"], "description": "string", "confidence": 0.0}],
            "new_traits": [{"subject": "string", "trait": "string", "confidence": 0.0}],
            "aliases": [{"subject": "string", "alias": "string", "confidence": 0.0}],
            "summary_markdown": "string",
            "review_items": ["string"],
            "confidence": 0.0,
        },
        "rules": [
            "Return JSON only.",
            "Write in the requested language when available.",
            "Do not invent facts outside the chapter excerpt.",
            "Use short navigable names when possible; keep longer forms in aliases or facts.",
            "Prefer durable entities, places, and concepts over one-off decorative nouns.",
            "Keep the summary in narrative prose with markdown formatting.",
        ],
    }
    try:
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="llm_call_started",
            call_kind="chapter_analysis",
            chapter_title=chapter_title,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chapter_chars=len(chapter_text),
            retries=config.retries,
            max_tokens=config.max_tokens,
        )
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are extracting chapter-level canonical signals for an Obsidian fiction vault. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
            )
        )
    except TextProviderError as exc:
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="provider_error",
            call_kind="chapter_analysis",
            chapter_title=chapter_title,
            chunk_index=chunk_index,
            error=str(exc),
        )
        return None

    _emit_progress(
        progress_log_path,
        phase="story_builder",
        event="llm_call_succeeded",
        call_kind="chapter_analysis",
        chapter_title=chapter_title,
        chunk_index=chunk_index,
        response_chars=len(response.text),
    )
    return extract_json_payload(response.text)


def _chunk_chapter_text(text: str, *, max_chars: int) -> list[str]:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return [stripped]
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    for paragraph in paragraphs:
        addition = len(paragraph) + (2 if current else 0)
        if current and current_chars + addition > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_chars = len(paragraph)
        else:
            current.append(paragraph)
            current_chars += addition
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [stripped[:max_chars]]


def _merge_chapter_analysis_payloads(payloads: list[dict[str, object]]) -> dict[str, object]:
    merged: dict[str, object] = {
        "characters": [],
        "places": [],
        "concepts": [],
        "events": [],
        "relations": [],
        "new_traits": [],
        "aliases": [],
        "review_items": [],
        "summary_markdown": "",
        "confidence": 0.0,
    }
    summaries: list[str] = []
    confidence_values: list[float] = []
    for payload in payloads:
        for key in ("characters", "places", "concepts", "events", "relations", "new_traits", "aliases", "review_items"):
            items = payload.get(key)
            if isinstance(items, list):
                merged[key] = [*merged[key], *items]
        summary = str(payload.get("summary_markdown") or "").strip()
        if summary:
            summaries.append(summary)
        try:
            confidence_values.append(float(payload.get("confidence") or 0.0))
        except (TypeError, ValueError):
            pass
    merged["summary_markdown"] = "\n\n".join(summaries[:3]).strip()
    merged["confidence"] = max(confidence_values) if confidence_values else 0.0
    for key in ("characters", "places", "concepts", "events", "relations", "new_traits", "aliases", "review_items"):
        merged[key] = _dedupe_payload_items(list(merged[key]))
    return merged


def _synthesize_chapter_summary(
    *,
    config: StoryBuildConfig,
    chapter_title: str,
    chapter_text: str,
    analysis_payload: dict[str, object],
    language: str | None,
    canonical_catalog: list[dict[str, object]],
    progress_log_path: str | None,
) -> str | None:
    if get_text_provider_config_error(config.task_name, config.provider_name):
        return None
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Write a concise chapter summary for an Obsidian fiction vault using wikilinks-friendly names.",
        "language": language,
        "chapter_title": chapter_title,
        "canonical_note_catalog": [item["title"] for item in canonical_catalog[:120]],
        "analysis_payload": {
            "characters": analysis_payload.get("characters", []),
            "places": analysis_payload.get("places", []),
            "concepts": analysis_payload.get("concepts", []),
            "events": analysis_payload.get("events", []),
            "relations": analysis_payload.get("relations", []),
            "new_traits": analysis_payload.get("new_traits", []),
        },
        "chapter_excerpt": chapter_text[:3500],
        "rules": [
            "Return JSON only.",
            "Use the requested language when available.",
            "Write 1-3 short paragraphs in narrative prose, not bullet points.",
            "Prefer short navigable names that can be wikilinked later.",
            "Do not invent facts outside the provided excerpt and analysis.",
        ],
        "required_output_schema": {
            "summary_markdown": "string",
        },
    }
    try:
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="llm_call_started",
            call_kind="chapter_summary_fallback",
            chapter_title=chapter_title,
            max_tokens=min(config.max_tokens, 900),
        )
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are writing a grounded chapter summary for an Obsidian fiction vault. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=min(config.max_tokens, 900),
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
            )
        )
    except TextProviderError as exc:
        _emit_progress(
            progress_log_path,
            phase="story_builder",
            event="provider_error",
            call_kind="chapter_summary_fallback",
            chapter_title=chapter_title,
            error=str(exc),
        )
        return None

    _emit_progress(
        progress_log_path,
        phase="story_builder",
        event="llm_call_succeeded",
        call_kind="chapter_summary_fallback",
        chapter_title=chapter_title,
        response_chars=len(response.text),
    )
    payload = extract_json_payload(response.text)
    return str(payload.get("summary_markdown") or "").strip() or None


def _dedupe_payload_items(items: list[object]) -> list[object]:
    seen: set[str] = set()
    result: list[object] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _write_story_builder_audits(
    *,
    vault_root: Path,
    chapter_candidates: list[dict[str, object]],
    chapter_analyses: list[dict[str, object]],
) -> None:
    system_root = vault_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    (system_root / "chapter_detection_audit.json").write_text(
        json.dumps(
            {
                "chapter_count": len(chapter_candidates),
                "chapters": chapter_candidates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (system_root / "chapter_analysis_audit.json").write_text(
        json.dumps(
            {
                "analysis_count": len(chapter_analyses),
                "chapters": chapter_analyses,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _emit_progress(path: str | None, **payload: object) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
