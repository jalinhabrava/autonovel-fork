from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap import SourceDocumentInventory
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.chapterizer import ChapterBoundaryCandidate, discover_chapter_boundary_candidates
from textifai.obsidian import open_obsidian_source
from vault.notes import write_artifact_payload
from vault.schema import slugify


@dataclass(frozen=True)
class StoryBuildConfig:
    provider_name: str
    model: str
    task_name: str = "bootstrap_normalization"
    max_tokens: int = 1400
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 3
    max_chapter_excerpt_chars: int = 6000
    max_summary_excerpt_chars: int = 2800
    max_llm_calls: int = 120
    max_chapters: int | None = None
    mode: str = "safe_import"
    concurrency: int = 1
    requests_per_minute_cap: int = 8
    tokens_per_minute_cap: int = 18000
    min_request_interval_seconds: float = 2.5
    chapter_map_batch_size: int = 8
    rate_limit_pause_retries: int = 4
    provider_cooldown_base_seconds: float = 20.0
    provider_cooldown_max_seconds: float = 180.0
    checkpoint_dirname: str = "99_System/bootstrap_checkpoints/story_builder"
    progress_filename: str = "99_System/chapter_processing_progress.jsonl"
    rate_limit_audit_filename: str = "99_System/provider_rate_limit_audit.json"
    chapter_map_audit_filename: str = "99_System/chapter_map_audit.json"
    chapter_analysis_audit_filename: str = "99_System/chapter_analysis_audit.json"
    primary_update_audit_filename: str = "99_System/primary_update_audit.json"
    chapter_detection_audit_filename: str = "99_System/chapter_detection_audit.json"


@dataclass(frozen=True)
class StoryBuildResult:
    chapter_paths: list[str] = field(default_factory=list)
    summary_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    audit: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChapterMapEntry:
    source_id: str
    source_path: str
    original_title: str
    normalized_title: str
    slug: str
    text: str
    char_start: int
    char_end: int
    page_start: int | None
    page_end: int | None
    confidence: float
    title_number_hint: str | None
    classification: str
    reason: str
    signals: list[str] = field(default_factory=list)
    source_sequence_index: int | None = None


class _RateLimitController:
    def __init__(self, config: StoryBuildConfig):
        self.config = config
        self._request_times: deque[float] = deque()
        self._token_times: deque[tuple[float, int]] = deque()
        self._last_request_at: float | None = None
        self.audit: dict[str, Any] = {
            "mode": config.mode,
            "requests_per_minute_cap": config.requests_per_minute_cap,
            "tokens_per_minute_cap": config.tokens_per_minute_cap,
            "min_request_interval_seconds": config.min_request_interval_seconds,
            "events": [],
            "sleep_events": [],
            "calls_started": 0,
            "calls_completed": 0,
            "calls_failed": 0,
            "estimated_input_tokens": 0,
            "rate_limit_pauses": [],
        }

    def before_call(self, *, estimated_tokens: int, progress_paths: list[str]) -> None:
        self._prune(time.time())
        now = time.time()
        wait_for = 0.0
        if self._last_request_at is not None:
            wait_for = max(wait_for, self.config.min_request_interval_seconds - (now - self._last_request_at))
        if len(self._request_times) >= self.config.requests_per_minute_cap:
            wait_for = max(wait_for, 60.0 - (now - self._request_times[0]))
        token_window = sum(tokens for _, tokens in self._token_times)
        if token_window + estimated_tokens > self.config.tokens_per_minute_cap and self._token_times:
            wait_for = max(wait_for, 60.0 - (now - self._token_times[0][0]))
        if wait_for > 0:
            payload = {
                "phase": "story_builder",
                "event": "paused_due_to_rate_limit",
                "sleep_seconds": round(wait_for, 2),
                "estimated_tokens": estimated_tokens,
            }
            self.audit["sleep_events"].append(payload)
            _emit_progress_many(progress_paths, **payload)
            time.sleep(wait_for)
        now = time.time()
        self._prune(now)
        self._request_times.append(now)
        self._token_times.append((now, estimated_tokens))
        self._last_request_at = now
        self.audit["calls_started"] += 1
        self.audit["estimated_input_tokens"] += estimated_tokens
        self.audit["events"].append(
            {
                "event": "call_started",
                "timestamp": now,
                "estimated_tokens": estimated_tokens,
            }
        )

    def after_call(self, *, success: bool, provider_error: str | None = None) -> None:
        if success:
            self.audit["calls_completed"] += 1
        else:
            self.audit["calls_failed"] += 1
        self.audit["events"].append(
            {
                "event": "call_completed" if success else "call_failed",
                "timestamp": time.time(),
                "provider_error": provider_error,
            }
        )

    def pause_for_provider_limit(self, *, seconds: float, progress_paths: list[str], scope: str, item_name: str) -> None:
        payload = {
            "phase": "story_builder",
            "event": "paused_due_to_provider_limits",
            "scope": scope,
            "item_name": item_name,
            "sleep_seconds": round(seconds, 2),
        }
        self.audit["rate_limit_pauses"].append(payload)
        _emit_progress_many(progress_paths, **payload)
        time.sleep(seconds)

    def _prune(self, now: float) -> None:
        while self._request_times and now - self._request_times[0] >= 60:
            self._request_times.popleft()
        while self._token_times and now - self._token_times[0][0] >= 60:
            self._token_times.popleft()


def build_story_notes(
    vault_root: str | Path,
    *,
    inventory: SourceDocumentInventory,
    config: StoryBuildConfig,
    progress_log_path: str | None = None,
) -> StoryBuildResult:
    vault_root = Path(vault_root)
    progress_paths = _progress_paths(vault_root, progress_log_path, config.progress_filename)
    rate_limiter = _RateLimitController(config)
    source_texts = read_source_documents(inventory, progress_log_path=progress_log_path)
    canonical_notes = _canonical_note_catalog(vault_root)

    candidate_boundaries, source_selection_audit = _discover_boundary_candidates(inventory=inventory, source_texts=source_texts)
    chapter_map = _build_chapter_map(
        vault_root=vault_root,
        config=config,
        candidates=candidate_boundaries,
        source_selection_audit=source_selection_audit,
        source_texts=source_texts,
        progress_paths=progress_paths,
        rate_limiter=rate_limiter,
    )
    warnings: list[str] = []
    chapter_paths: list[str] = []
    summary_paths: list[str] = []
    chapter_analyses: list[dict[str, object]] = []
    primary_updates: list[dict[str, object]] = []
    checkpoint_dir = vault_root / config.checkpoint_dirname
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if not chapter_map:
        warnings.append("no_story_chapters_mapped")
        _write_story_artifacts(
            vault_root=vault_root,
            config=config,
            chapter_map=[],
            chapter_analyses=[],
            primary_updates=[],
            rate_limit_audit=rate_limiter.audit,
        )
        return StoryBuildResult(warnings=warnings, audit={"chapter_map": [], "warnings": warnings})

    _emit_progress_many(
        progress_paths,
        phase="story_builder",
        event="chapter_map_ready",
        chapter_count=len(chapter_map),
        subset_limit=config.max_chapters,
    )

    primary_lookup = _build_primary_lookup(vault_root)
    chapters_to_process = chapter_map[: config.max_chapters] if config.max_chapters else chapter_map
    llm_calls_used = 0

    for chapter in chapters_to_process:
        _emit_progress_many(
            progress_paths,
            phase="story_builder",
            event="chapter_started",
            chapter_title=chapter.original_title,
            page_start=chapter.page_start,
            page_end=chapter.page_end,
            source_number_hint=chapter.title_number_hint,
            source_sequence_index=chapter.source_sequence_index,
        )
        linked_text, linked_subjects = _wikify_text(chapter.text, canonical_notes)
        analysis_payload = None
        if llm_calls_used < config.max_llm_calls:
            analysis_payload = _load_or_analyze_chapter(
                vault_root=vault_root,
                config=config,
                checkpoint_dir=checkpoint_dir,
                chapter=chapter,
                canonical_catalog=canonical_notes,
                progress_paths=progress_paths,
                rate_limiter=rate_limiter,
            )
            if analysis_payload is not None and not analysis_payload.get("_loaded_from_checkpoint", False):
                llm_calls_used += int(analysis_payload.get("_llm_calls_used") or 0)
        else:
            warnings.append(f"chapter_analysis_budget_exhausted:{chapter.original_title}")

        if analysis_payload is None:
            warnings.append(f"chapter_analysis_failed:{chapter.original_title}")
            _emit_progress_many(
                progress_paths,
                phase="story_builder",
                event="chapter_deferred",
                chapter_title=chapter.original_title,
                reason="provider_limit_or_analysis_failure",
            )
            continue

        chapter_analyses.append(
            {
                "chapter_title": chapter.original_title,
                "normalized_title": chapter.normalized_title,
                "chapter_slug": chapter.slug,
                "source_path": chapter.source_path,
                "page_start": chapter.page_start,
                "page_end": chapter.page_end,
                "classification": chapter.classification,
                "confidence": chapter.confidence,
                "analysis": {key: value for key, value in analysis_payload.items() if not str(key).startswith("_")},
            }
        )
        _write_story_artifacts(
            vault_root=vault_root,
            config=config,
            chapter_map=chapter_map,
            chapter_analyses=chapter_analyses,
            primary_updates=primary_updates,
            rate_limit_audit=rate_limiter.audit,
        )

        chapter_body = "\n\n".join(["## Chapter Text", linked_text.strip()]).strip()
        chapter_metadata = {
            "artifact_stage": "promoted_artifact",
            "promotion_status": "promoted_canonical",
            "note_role": "chapter",
            "entity_kind": "chapter",
            "canonical_subject": chapter.normalized_title,
            "source_title": chapter.original_title,
            "source_number_hint": chapter.title_number_hint,
            "source_sequence_index": chapter.source_sequence_index,
            "semantic_class": "chapter_full_text",
            "source_path": chapter.source_path,
            "linked_primary_subjects": ", ".join(linked_subjects),
            "evidence_sources": chapter.source_path,
            "confidence": chapter.confidence,
            "review_state": "canonical",
            "page_start": chapter.page_start,
            "page_end": chapter.page_end,
        }
        chapter_path = write_artifact_payload(
            vault_root,
            artifact_kind="note",
            artifact_type="chapter",
            entity_id=chapter.slug,
            title=chapter.original_title,
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
                    chapter=chapter,
                    analysis_payload=analysis_payload,
                    canonical_catalog=canonical_notes,
                    progress_paths=progress_paths,
                    rate_limiter=rate_limiter,
                )
                or ""
            ).strip()
        if summary_markdown:
            summary_text, summary_links = _wikify_text(summary_markdown, canonical_notes)
            summary_path = write_artifact_payload(
                vault_root,
                artifact_kind="note",
                artifact_type="chapter_summary",
                entity_id=f"{chapter.slug}_summary",
                title=f"{chapter.original_title} Summary",
                body=summary_text,
                status="pending_revision",
                metadata={
                    "artifact_stage": "promoted_artifact",
                    "promotion_status": "promoted_canonical",
                    "note_role": "chapter_summary",
                    "entity_kind": "chapter_summary",
                    "canonical_subject": chapter.normalized_title,
                    "source_title": chapter.original_title,
                    "source_number_hint": chapter.title_number_hint,
                    "source_sequence_index": chapter.source_sequence_index,
                    "semantic_class": "chapter_summary",
                    "source_path": chapter.source_path,
                    "linked_primary_subjects": ", ".join(summary_links),
                    "summary_for_chapter": Path(chapter_path).name,
                    "evidence_sources": chapter.source_path,
                    "confidence": float(analysis_payload.get("confidence") or 0.0),
                    "review_state": "canonical",
                    "page_start": chapter.page_start,
                    "page_end": chapter.page_end,
                },
            )
            summary_paths.append(str(summary_path))
        else:
            warnings.append(f"summary_generation_failed:{chapter.original_title}")

        applied_updates = _apply_primary_updates(
            vault_root=vault_root,
            chapter=chapter,
            analysis_payload=analysis_payload,
            primary_lookup=primary_lookup,
        )
        primary_updates.extend(applied_updates)
        _write_story_artifacts(
            vault_root=vault_root,
            config=config,
            chapter_map=chapter_map,
            chapter_analyses=chapter_analyses,
            primary_updates=primary_updates,
            rate_limit_audit=rate_limiter.audit,
        )
        _emit_progress_many(
            progress_paths,
            phase="story_builder",
            event="chapter_completed",
            chapter_title=chapter.original_title,
            chapter_path=str(chapter_path),
            summary_generated=bool(summary_markdown),
            primary_update_count=len(applied_updates),
        )

    return StoryBuildResult(
        chapter_paths=chapter_paths,
        summary_paths=summary_paths,
        warnings=warnings,
        audit={
            "chapter_map": [entry.__dict__ for entry in chapter_map],
            "chapter_analyses": chapter_analyses,
            "primary_updates": primary_updates,
            "rate_limit_audit": rate_limiter.audit,
            "warnings": warnings,
        },
    )


def _discover_boundary_candidates(
    *,
    inventory: SourceDocumentInventory,
    source_texts: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    source_audit: list[dict[str, object]] = []
    for document in inventory.documents:
        text = source_texts.get(document.source_id, "")
        if not text.strip():
            continue
        structural_candidates = discover_chapter_boundary_candidates(document, text)
        include_source, audit_entry = _should_use_document_for_story_mapping(
            document=document,
            candidates=structural_candidates,
            text=text,
        )
        source_audit.append(audit_entry)
        if not include_source:
            continue
        for candidate in structural_candidates:
            candidates.append(
                {
                    "source_id": candidate.source_id,
                    "source_path": document.path,
                    "original_title": candidate.original_title,
                    "normalized_title": candidate.normalized_title,
                    "char_start": candidate.char_start,
                    "page": candidate.page,
                    "heading_text": candidate.heading_text,
                    "signals": candidate.signals,
                    "context_before": candidate.context_before,
                    "context_after": candidate.context_after,
                    "title_number_hint": candidate.title_number_hint,
                    "toc_page_hint": candidate.toc_page_hint,
                    "candidate_id": candidate.candidate_id,
                    "language": document.dominant_language,
                }
            )
    candidates.sort(key=lambda item: (str(item["source_path"]), int(item.get("page") or 0), int(item["char_start"])))
    return candidates, source_audit


def _build_chapter_map(
    *,
    vault_root: Path,
    config: StoryBuildConfig,
    candidates: list[dict[str, object]],
    source_selection_audit: list[dict[str, object]],
    source_texts: dict[str, str],
    progress_paths: list[str],
    rate_limiter: _RateLimitController,
) -> list[ChapterMapEntry]:
    if not candidates:
        return []

    decisions = _classify_boundary_candidates(
        config=config,
        candidates=candidates,
        progress_paths=progress_paths,
        rate_limiter=rate_limiter,
    )
    accepted: list[dict[str, object]] = []
    for candidate in candidates:
        decision = decisions.get(candidate["candidate_id"])
        if not decision or str(decision.get("reason") or "").strip() == "missing_llm_decision":
            decision = _fallback_chapter_map_decision(candidate)
        candidate["decision"] = decision
        if decision["classification"] in {"chapter", "prologue", "epilogue", "interlude"}:
            accepted.append(candidate)

    chapter_map: list[ChapterMapEntry] = []
    grouped: dict[str, list[dict[str, object]]] = {}
    for candidate in accepted:
        grouped.setdefault(str(candidate["source_id"]), []).append(candidate)

    for source_id, source_candidates in grouped.items():
        source_text = source_texts.get(source_id, "")
        source_candidates.sort(key=lambda item: int(item["char_start"]))
        for index, candidate in enumerate(source_candidates, start=1):
            next_start = source_candidates[index].get("char_start") if index < len(source_candidates) else len(source_text)
            chapter_text = _strip_page_markers(source_text[int(candidate["char_start"]) : int(next_start)]).strip()
            if len(chapter_text.split()) < 8:
                continue
            page_start = candidate.get("page") or _page_for_offset(source_text, int(candidate["char_start"]))
            page_end = _page_for_offset(source_text, max(int(candidate["char_start"]), int(next_start) - 1))
            decision = candidate["decision"]
            normalized_title = str(decision.get("normalized_title") or candidate["normalized_title"]).strip() or str(candidate["original_title"])
            slug = slugify(normalized_title)
            if not slug:
                slug = f"{source_id}_{int(candidate['char_start'])}"
            chapter_map.append(
                ChapterMapEntry(
                    source_id=source_id,
                    source_path=str(candidate["source_path"]),
                    original_title=str(candidate["original_title"]),
                    normalized_title=normalized_title,
                    slug=slug,
                    text=chapter_text,
                    char_start=int(candidate["char_start"]),
                    char_end=int(next_start),
                    page_start=page_start,
                    page_end=page_end,
                    confidence=float(decision.get("confidence") or 0.0),
                    title_number_hint=str(decision.get("chapter_number") or candidate.get("title_number_hint") or "").strip() or None,
                    classification=str(decision.get("classification") or "chapter"),
                    reason=str(decision.get("reason") or ""),
                    signals=list(candidate.get("signals") or []),
                    source_sequence_index=index,
                )
            )

    chapter_map.sort(key=lambda entry: (entry.source_path, entry.page_start or 0, entry.char_start))
    _write_chapter_map_audit(
        vault_root=vault_root,
        config=config,
        candidates=candidates,
        chapter_map=chapter_map,
        source_selection_audit=source_selection_audit,
    )
    return chapter_map


def _classify_boundary_candidates(
    *,
    config: StoryBuildConfig,
    candidates: list[dict[str, object]],
    progress_paths: list[str],
    rate_limiter: _RateLimitController,
) -> dict[str, dict[str, object]]:
    if get_text_provider_config_error(config.task_name, config.provider_name):
        return {
            candidate["candidate_id"]: {
                "classification": "chapter" if "toc_match" in candidate.get("signals", []) else "continuation_of_previous_chapter",
                "normalized_title": candidate["normalized_title"],
                "confidence": 0.2,
                "reason": "provider_unavailable_fallback",
                "chapter_number": candidate.get("title_number_hint"),
            }
            for candidate in candidates
        }
    provider = get_text_provider(config.task_name, config.provider_name)
    decisions: dict[str, dict[str, object]] = {}
    for batch_index, batch in enumerate(_chunk_list(candidates, config.chapter_map_batch_size), start=1):
        payload = {
            "goal": "Classify structural boundary candidates in a long fiction manuscript.",
            "rules": [
                "Return JSON only.",
                "Do not rely on language-specific words alone.",
                "Use structure, title shape, continuity, and surrounding context.",
                "Valid classifications: chapter, scene, prologue, epilogue, interlude, appendix_meta_noise, continuation_of_previous_chapter.",
                "Use chapter when this boundary clearly begins a full chapter-sized narrative unit.",
                "Use continuation_of_previous_chapter when the boundary is a subsection or ornamental title inside an existing chapter.",
            ],
            "candidates": [
                {
                    "candidate_id": item["candidate_id"],
                    "original_title": item["original_title"],
                    "normalized_title": item["normalized_title"],
                    "page": item.get("page"),
                    "signals": item.get("signals"),
                    "title_number_hint": item.get("title_number_hint"),
                    "context_before": item.get("context_before"),
                    "context_after": item.get("context_after"),
                }
                for item in batch
            ],
            "required_output_schema": {
                "decisions": [
                    {
                        "candidate_id": "string",
                        "classification": "chapter|scene|prologue|epilogue|interlude|appendix_meta_noise|continuation_of_previous_chapter",
                        "normalized_title": "string",
                        "chapter_number": "string|null",
                        "confidence": 0.0,
                        "reason": "string",
                    }
                ]
            },
        }
        for attempt in range(1, config.rate_limit_pause_retries + 2):
            estimated_tokens = _estimate_tokens(json.dumps(batch, ensure_ascii=False)) + config.max_tokens
            rate_limiter.before_call(estimated_tokens=estimated_tokens, progress_paths=progress_paths)
            try:
                _emit_progress_many(progress_paths, phase="story_builder", event="chapter_map_batch_started", batch_index=batch_index, batch_size=len(batch), attempt=attempt)
                response = provider.generate(
                    TextGenerationRequest(
                        task=config.task_name,
                        provider_name=config.provider_name,
                    model=config.model,
                    system="You are classifying structural chapter boundaries for a fiction manuscript. Return strict JSON only.",
                    messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                    max_tokens=min(config.max_tokens, 1200),
                    temperature=0.0,
                    timeout_seconds=config.timeout_seconds,
                    retries=config.retries,
                    response_format={"type": "json_object"},
                )
            )
                rate_limiter.after_call(success=True)
                raw = extract_json_payload(response.text) or {}
                for item in raw.get("decisions", []):
                    candidate_id = str(item.get("candidate_id") or "").strip()
                    if not candidate_id:
                        continue
                    decisions[candidate_id] = {
                        "classification": str(item.get("classification") or "continuation_of_previous_chapter").strip(),
                        "normalized_title": str(item.get("normalized_title") or "").strip(),
                        "chapter_number": item.get("chapter_number"),
                        "confidence": float(item.get("confidence") or 0.0),
                        "reason": str(item.get("reason") or "").strip(),
                    }
                _emit_progress_many(progress_paths, phase="story_builder", event="chapter_map_batch_completed", batch_index=batch_index, decision_count=len(raw.get("decisions", [])), attempt=attempt)
                break
            except TextProviderError as exc:
                rate_limiter.after_call(success=False, provider_error=str(exc))
                _emit_progress_many(progress_paths, phase="story_builder", event="provider_error", call_kind="chapter_map", batch_index=batch_index, attempt=attempt, error=str(exc))
                if "429" not in str(exc) or attempt > config.rate_limit_pause_retries:
                    return decisions
                cooldown = _provider_limit_sleep_seconds(config=config, attempt=attempt)
                rate_limiter.pause_for_provider_limit(
                    seconds=cooldown,
                    progress_paths=progress_paths,
                    scope="chapter_map",
                    item_name=f"batch_{batch_index}",
                )
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id in decisions:
            continue
        decisions[candidate_id] = _fallback_chapter_map_decision(candidate)
    return decisions


def _load_or_analyze_chapter(
    *,
    vault_root: Path,
    config: StoryBuildConfig,
    checkpoint_dir: Path,
    chapter: ChapterMapEntry,
    canonical_catalog: list[dict[str, object]],
    progress_paths: list[str],
    rate_limiter: _RateLimitController,
) -> dict[str, object] | None:
    checkpoint_path = checkpoint_dir / f"{chapter.slug}.json"
    source_hash = slugify(f"{chapter.original_title}_{len(chapter.text)}_{chapter.source_path}")
    completed_analyses: list[dict[str, Any]] = []
    resume_chunk_index = 1
    if checkpoint_path.exists():
        try:
            cached = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if cached.get("source_hash") == source_hash:
                if cached.get("status") == "complete":
                    _emit_progress_many(progress_paths, phase="story_builder", event="chapter_checkpoint_loaded", chapter_title=chapter.original_title)
                    return {**cached.get("analysis", {}), "_loaded_from_checkpoint": True, "_llm_calls_used": 0}
                completed_analyses = list(cached.get("completed_chunk_analyses") or [])
                resume_chunk_index = int(cached.get("next_chunk_index") or 1)
                _emit_progress_many(
                    progress_paths,
                    phase="story_builder",
                    event="chapter_checkpoint_resuming",
                    chapter_title=chapter.original_title,
                    next_chunk_index=resume_chunk_index,
                    completed_chunk_count=len(completed_analyses),
                )
        except json.JSONDecodeError:
            pass

    if get_text_provider_config_error(config.task_name, config.provider_name):
        return None

    chunks = _chunk_chapter_text(chapter.text, max_chars=config.max_chapter_excerpt_chars)
    analyses: list[dict[str, Any]] = list(completed_analyses)
    llm_calls_used = 0
    for chunk_index, chunk in enumerate(chunks, start=1):
        if chunk_index < resume_chunk_index:
            continue
        payload = None
        for attempt in range(1, config.rate_limit_pause_retries + 2):
            payload = _analyze_chapter_chunk(
                config=config,
                chapter=chapter,
                chapter_text=chunk,
                canonical_catalog=canonical_catalog,
                chunk_index=chunk_index,
                chunk_total=len(chunks),
                progress_paths=progress_paths,
                rate_limiter=rate_limiter,
                attempt=attempt,
            )
            if payload is not None:
                break
            cooldown = _provider_limit_sleep_seconds(config=config, attempt=attempt)
            rate_limiter.pause_for_provider_limit(
                seconds=cooldown,
                progress_paths=progress_paths,
                scope="chapter_analysis",
                item_name=chapter.original_title,
            )
        if payload is None:
            checkpoint_path.write_text(
                json.dumps(
                    {
                        "chapter_title": chapter.original_title,
                        "source_hash": source_hash,
                        "source_path": chapter.source_path,
                        "status": "pending_rate_limit",
                        "completed_chunk_analyses": analyses,
                        "next_chunk_index": chunk_index,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return None
        analyses.append(payload)
        llm_calls_used += 1

    merged = _merge_chapter_analysis_payloads(analyses)
    checkpoint_path.write_text(
        json.dumps(
            {
                "chapter_title": chapter.original_title,
                "source_hash": source_hash,
                "source_path": chapter.source_path,
                "status": "complete",
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
    chapter: ChapterMapEntry,
    chapter_text: str,
    canonical_catalog: list[dict[str, object]],
    chunk_index: int,
    chunk_total: int,
    progress_paths: list[str],
    rate_limiter: _RateLimitController,
    attempt: int,
) -> dict[str, object] | None:
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Extract chapter-level canonical updates for a fiction vault.",
        "chapter_title": chapter.original_title,
        "page_start": chapter.page_start,
        "page_end": chapter.page_end,
        "canonical_note_catalog": [item["title"] for item in canonical_catalog[:120]],
        "chapter_excerpt": chapter_text[: config.max_chapter_excerpt_chars],
        "required_output_schema": {
            "summary_markdown": "string",
            "characters": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "places": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "concepts": [{"name": "string", "aliases": ["string"], "facts": ["string"], "confidence": 0.0}],
            "events": [{"title": "string", "summary": "string", "related_subjects": ["string"], "confidence": 0.0}],
            "relations": [{"subjects": ["string"], "description": "string", "confidence": 0.0}],
            "new_traits": [{"subject": "string", "trait": "string", "confidence": 0.0}],
            "aliases": [{"subject": "string", "alias": "string", "confidence": 0.0}],
            "review_items": ["string"],
            "confidence": 0.0,
        },
        "rules": [
            "Return JSON only.",
            "Write the summary in the same dominant language as the excerpt.",
            "Do not invent facts outside the excerpt.",
            "Use short navigable names when possible and keep longer forms in aliases or facts.",
            "Only include items with actual evidence in the excerpt.",
            "If a field has no evidence, return an empty list, not prose.",
        ],
    }
    estimated_tokens = _estimate_tokens(json.dumps(payload, ensure_ascii=False)) + config.max_tokens
    rate_limiter.before_call(estimated_tokens=estimated_tokens, progress_paths=progress_paths)
    try:
        _emit_progress_many(
            progress_paths,
            phase="story_builder",
            event="llm_call_started",
            call_kind="chapter_analysis",
            chapter_title=chapter.original_title,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            attempt=attempt,
            chapter_chars=len(chapter_text),
        )
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are extracting grounded chapter-level narrative facts for an Obsidian fiction vault. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=config.max_tokens,
                temperature=0.0,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
                response_format={"type": "json_object"},
            )
        )
        rate_limiter.after_call(success=True)
    except TextProviderError as exc:
        rate_limiter.after_call(success=False, provider_error=str(exc))
        _emit_progress_many(
            progress_paths,
            phase="story_builder",
            event="provider_error",
            call_kind="chapter_analysis",
            chapter_title=chapter.original_title,
            chunk_index=chunk_index,
            attempt=attempt,
            error=str(exc),
        )
        return None

    payload = extract_json_payload(response.text)
    _emit_progress_many(
        progress_paths,
        phase="story_builder",
        event="llm_call_succeeded",
        call_kind="chapter_analysis",
        chapter_title=chapter.original_title,
        chunk_index=chunk_index,
        attempt=attempt,
        response_chars=len(response.text),
        payload_present=payload is not None,
    )
    if payload is None:
        return {
            "summary_markdown": "",
            "characters": [],
            "places": [],
            "concepts": [],
            "events": [],
            "relations": [],
            "new_traits": [],
            "aliases": [],
            "review_items": ["llm_response_not_parseable"],
            "confidence": 0.0,
        }
    return payload


def _synthesize_chapter_summary(
    *,
    config: StoryBuildConfig,
    chapter: ChapterMapEntry,
    analysis_payload: dict[str, object],
    canonical_catalog: list[dict[str, object]],
    progress_paths: list[str],
    rate_limiter: _RateLimitController,
) -> str | None:
    provider = get_text_provider(config.task_name, config.provider_name)
    payload = {
        "goal": "Write a concise chapter summary for an Obsidian fiction vault using the grounded analysis and excerpt.",
        "chapter_title": chapter.original_title,
        "canonical_note_catalog": [item["title"] for item in canonical_catalog[:120]],
        "analysis_payload": {k: analysis_payload.get(k) for k in ("characters", "places", "concepts", "events", "relations", "new_traits")},
        "chapter_excerpt": chapter.text[: config.max_summary_excerpt_chars],
        "required_output_schema": {"summary_markdown": "string"},
        "rules": [
            "Return JSON only.",
            "Write in the same dominant language as the excerpt.",
            "Write 1-3 short narrative paragraphs.",
            "Do not invent facts outside the excerpt and structured analysis.",
        ],
    }
    estimated_tokens = _estimate_tokens(json.dumps(payload, ensure_ascii=False)) + min(config.max_tokens, 900)
    rate_limiter.before_call(estimated_tokens=estimated_tokens, progress_paths=progress_paths)
    try:
        _emit_progress_many(progress_paths, phase="story_builder", event="llm_call_started", call_kind="chapter_summary_fallback", chapter_title=chapter.original_title)
        response = provider.generate(
            TextGenerationRequest(
                task=config.task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="You are writing a grounded chapter summary for an Obsidian fiction vault. Return strict JSON only.",
                messages=[TextMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                max_tokens=min(config.max_tokens, 900),
                temperature=0.0,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
            )
        )
        rate_limiter.after_call(success=True)
    except TextProviderError as exc:
        rate_limiter.after_call(success=False, provider_error=str(exc))
        _emit_progress_many(progress_paths, phase="story_builder", event="provider_error", call_kind="chapter_summary_fallback", chapter_title=chapter.original_title, error=str(exc))
        return None
    raw = extract_json_payload(response.text) or {}
    _emit_progress_many(progress_paths, phase="story_builder", event="llm_call_succeeded", call_kind="chapter_summary_fallback", chapter_title=chapter.original_title, response_chars=len(response.text))
    return str(raw.get("summary_markdown") or "").strip() or None


def _apply_primary_updates(
    *,
    vault_root: Path,
    chapter: ChapterMapEntry,
    analysis_payload: dict[str, object],
    primary_lookup: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    updates: list[dict[str, object]] = []
    for item_kind in ("characters", "places", "concepts"):
        for item in analysis_payload.get(item_kind, []) or []:
            subject = str(item.get("name") or "").strip()
            if not subject:
                continue
            note = _resolve_primary(subject, item.get("aliases", []) or [], primary_lookup)
            if note is None:
                continue
            applied = _append_chapter_evidence(
                note_path=Path(note["path"]),
                chapter=chapter,
                subject=subject,
                facts=[str(fact).strip() for fact in item.get("facts", []) if str(fact).strip()],
            )
            if applied:
                updates.append(
                    {
                        "subject": subject,
                        "note_path": str(note["path"]),
                        "chapter_title": chapter.original_title,
                        "update_type": item_kind,
                        "facts_added": applied,
                    }
                )
    return updates


def _append_chapter_evidence(
    *,
    note_path: Path,
    chapter: ChapterMapEntry,
    subject: str,
    facts: list[str],
) -> list[str]:
    if not note_path.exists() or not facts:
        return []
    text = note_path.read_text(encoding="utf-8")
    marker = f"### {chapter.original_title}"
    if marker in text:
        return []
    bullet_lines = "\n".join(f"- {fact}" for fact in facts[:6])
    section = f"\n\n## Chapter-Derived Evidence\n\n{marker}\n\n- Source chapter: [[{chapter.original_title}]]\n{bullet_lines}\n"
    if "## Chapter-Derived Evidence" in text:
        text = text.rstrip() + f"\n\n{marker}\n\n- Source chapter: [[{chapter.original_title}]]\n{bullet_lines}\n"
    else:
        text = text.rstrip() + section
    note_path.write_text(text, encoding="utf-8")
    return facts[:6]


def _resolve_primary(subject: str, aliases: list[object], primary_lookup: dict[str, dict[str, object]]) -> dict[str, object] | None:
    keys = [slugify(subject), *[slugify(str(alias)) for alias in aliases if str(alias).strip()]]
    for key in keys:
        if key and key in primary_lookup:
            return primary_lookup[key]
    return None


def _build_primary_lookup(vault_root: Path) -> dict[str, dict[str, object]]:
    source = open_obsidian_source(vault_root)
    lookup: dict[str, dict[str, object]] = {}
    for note in source.reader.list_notes():
        if str((note.frontmatter or {}).get("note_role") or "").strip().casefold() != "primary":
            continue
        data = {
            "path": note.path,
            "title": note.title,
        }
        for raw in [note.title, str((note.frontmatter or {}).get("canonical_subject") or ""), *note.aliases, *note.project_confirmed_aliases]:
            key = slugify(str(raw))
            if key and key not in lookup:
                lookup[key] = data
    return lookup


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
    merged["summary_markdown"] = "\n\n".join(summaries[:2]).strip()
    merged["confidence"] = max(confidence_values) if confidence_values else 0.0
    for key in ("characters", "places", "concepts", "events", "relations", "new_traits", "aliases", "review_items"):
        merged[key] = _dedupe_payload_items(list(merged[key]))
    return merged


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


def _write_story_artifacts(
    *,
    vault_root: Path,
    config: StoryBuildConfig,
    chapter_map: list[ChapterMapEntry],
    chapter_analyses: list[dict[str, object]],
    primary_updates: list[dict[str, object]],
    rate_limit_audit: dict[str, object],
) -> None:
    system_root = vault_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    (system_root / Path(config.chapter_detection_audit_filename).name).write_text(
        json.dumps({"chapter_count": len(chapter_map), "chapters": [entry.__dict__ for entry in chapter_map]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (system_root / Path(config.chapter_analysis_audit_filename).name).write_text(
        json.dumps({"analysis_count": len(chapter_analyses), "chapters": chapter_analyses}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (system_root / Path(config.primary_update_audit_filename).name).write_text(
        json.dumps({"update_count": len(primary_updates), "updates": primary_updates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (system_root / Path(config.rate_limit_audit_filename).name).write_text(
        json.dumps(rate_limit_audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_chapter_map_audit(
    *,
    vault_root: Path,
    config: StoryBuildConfig,
    candidates: list[dict[str, object]],
    chapter_map: list[ChapterMapEntry],
    source_selection_audit: list[dict[str, object]],
) -> None:
    system_root = vault_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    (system_root / Path(config.chapter_map_audit_filename).name).write_text(
        json.dumps(
            {
                "source_selection": source_selection_audit,
                "candidate_boundary_count": len(candidates),
                "candidate_boundaries": candidates,
                "chapter_count": len(chapter_map),
                "chapter_map": [entry.__dict__ for entry in chapter_map],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _progress_paths(vault_root: Path, bootstrap_progress_path: str | None, story_progress_filename: str) -> list[str]:
    paths = [str(vault_root / story_progress_filename)]
    if bootstrap_progress_path:
        paths.append(bootstrap_progress_path)
    return list(dict.fromkeys(paths))


def _emit_progress_many(paths: list[str], **payload: object) -> None:
    for path in paths:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _chunk_list(values: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _fallback_chapter_map_decision(candidate: dict[str, object]) -> dict[str, object]:
    signals = set(candidate.get("signals") or [])
    is_chapter_like = bool(candidate.get("title_number_hint")) or "markdown_heading" in signals or "toc_match" in signals
    return {
        "classification": "chapter" if is_chapter_like else "continuation_of_previous_chapter",
        "normalized_title": str(candidate.get("normalized_title") or candidate.get("original_title") or "").strip(),
        "chapter_number": candidate.get("title_number_hint"),
        "confidence": 0.42 if is_chapter_like else 0.12,
        "reason": "deterministic_structural_fallback_after_provider_limit",
    }


def _should_use_document_for_story_mapping(
    *,
    document: object,
    candidates: list[ChapterBoundaryCandidate],
    text: str,
) -> tuple[bool, dict[str, object]]:
    strong_candidates = [
        candidate
        for candidate in candidates
        if candidate.title_number_hint
        or "toc_match" in candidate.signals
        or "markdown_heading" in candidate.signals
    ]
    candidate_starts = sorted(candidate.char_start for candidate in candidates)
    span_sizes = [right - left for left, right in zip(candidate_starts, candidate_starts[1:])]
    average_span = round(sum(span_sizes) / len(span_sizes), 2) if span_sizes else 0.0
    extracted_pages = int(getattr(document, "extracted_page_count", 0) or 0)
    extracted_chars = int(getattr(document, "extracted_char_count", 0) or 0)

    qualifies = False
    reason = "insufficient_structural_story_signals"
    if len(strong_candidates) >= 2 and (extracted_pages >= 3 or average_span >= 2500):
        qualifies = True
        reason = "multiple_strong_structural_boundaries"
    elif len(strong_candidates) == 1 and extracted_chars >= 80 and any("markdown_heading" in candidate.signals for candidate in strong_candidates):
        qualifies = True
        reason = "single_markdown_story_unit"
    elif len(candidates) >= 2 and average_span >= 6000 and extracted_chars >= 12000:
        qualifies = True
        reason = "large_document_with_sparse_boundary_units"

    return qualifies, {
        "source_id": getattr(document, "source_id", ""),
        "source_path": getattr(document, "path", ""),
        "filename": getattr(document, "filename", ""),
        "candidate_count": len(candidates),
        "strong_candidate_count": len(strong_candidates),
        "average_candidate_span_chars": average_span,
        "extracted_page_count": extracted_pages,
        "extracted_char_count": extracted_chars,
        "selected_for_story_mapping": qualifies,
        "selection_reason": reason,
    }


def _provider_limit_sleep_seconds(*, config: StoryBuildConfig, attempt: int) -> float:
    return round(
        min(
            config.provider_cooldown_base_seconds * (2 ** max(attempt - 1, 0)),
            config.provider_cooldown_max_seconds,
        ),
        2,
    )


def _strip_page_markers(text: str) -> str:
    return re.sub(r"<<TEXTIFAI_PAGE_\d{4}>>", "", text)


def _page_for_offset(text: str, offset: int) -> int | None:
    matches = list(re.finditer(r"<<TEXTIFAI_PAGE_(\d{4})>>", text[: offset + 1]))
    if matches:
        return int(matches[-1].group(1))
    return None
