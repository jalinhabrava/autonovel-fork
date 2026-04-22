from __future__ import annotations

import json
import base64
import mimetypes
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap.contracts import SourceDocumentInventory
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.batch_planner import PlannedBatch, pack_items_by_budget, split_markdown_semantically
from textifai.import_review.bootstrap_profile import build_bootstrap_profile, classify_chapter_complexity
from textifai.import_review.empirical_ranker import EmpiricalPolicy, append_empirical_record, make_empirical_record
from textifai.import_review.model_advisor import maybe_advise_model_plan
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.model_router import ResolvedModelPlan, resolve_model_plan
from textifai.import_review.provider_snapshot import build_provider_snapshot
from textifai.import_review.token_budget import TokenBudget, build_token_budget, fits_within_budget
from textifai.runtime_config import synchronize_runtime_environment


GLOBAL_NORMALIZATION_PROMPT = """You are a narrative entity normalization system.

Your task is to analyze an ENTIRE novel or long-form narrative input and return a single JSON object containing a globally normalized entity layer for downstream ingestion into an Obsidian / knowledge graph import pipeline.

Your goal is NOT to summarize every scene.
Your goal is to identify and normalize only the entities and facts that are:

* persistent across the work,
* structurally relevant,
* reusable outside a single scene,
* suitable for long-term entity notes.

Return ONLY valid JSON.
Do not include markdown fences.
Do not include commentary.
Do not omit required fields.
If a field has no valid content, return an empty array.

==================================================
OUTPUT SCHEMA
=============

{
"work": {
"title": "...",
"language": "...",
"normalization_notes": ["..."]
},
"entities": [
{
"canonical_name": "...",
"entity_kind": "...",
"preferred_slug": "...",
"aliases": ["..."],
"summary": "...",
"key_facts": ["..."],
"relationships": [
{
"target": "...",
"type": "...",
"facts": ["..."]
}
],
"chapter_refs": ["..."],
"source_mentions": ["..."],
"confidence": 0.0,
"review_state": "canonical"
}
],
"merge_plan": [
{
"canonical_name": "...",
"merged_surfaces": ["..."],
"reason": "...",
"confidence": 0.0
}
]
}

==================================================
ENTITY KINDS
============

Allowed entity_kind values:

* character
* place
* concept
* magic
* creature
* faction
* object
* lore
* event

==================================================
RELATION TYPES
==============

Allowed relationship types:

* familial
* conflict
* alliance
* authority
* dependency
* magical_link
* located_in
* part_of
* member_of
* uses

==================================================
CORE EXTRACTION OBJECTIVE
=========================

Extract ONLY entities that are useful as standalone notes in a knowledge system.

An entity is worth keeping only if it has at least one of these:

1. narrative identity
2. durable role or capability
3. persistent relationship
4. worldbuilding/system relevance
5. repeated or lasting importance across the work

Do NOT create entities for:

* unnamed extras with no ongoing importance
* one-off gestures or scene-only mentions
* transient background references
* purely atmospheric descriptions

==================================================
GLOBAL NORMALIZATION RULES
==========================

Use the ENTIRE work to normalize entities.

You must:

* merge naming variants when confidence >= 0.80
* keep them separate when confidence < 0.80
* record high-confidence merges in merge_plan
* mark uncertain entities with review_state = "review"

Examples of mergeable variants:

* short name vs full name
* title + name vs plain name
* honorific variants
* place shorthand vs formal place name
* repeated concept labels that clearly refer to the same in-world mechanism

Do NOT merge merely because two items are similar.
Merge only when identity is strongly supported by the work.

If two named identities remain plausibly distinct, keep them separate.
Do not merge one named character into another merely because they share:

* a role,
* a title,
* a burden,
* a magical anomaly,
* or a narrative position.

Explicit personal names take precedence over titles or descriptive labels unless the work clearly confirms they are the same entity.

==================================================
LANGUAGE OUTPUT RULES
=====================

Write all summaries, key_facts, relationship facts, reasons, and normalization notes in LANGUAGE.

Keep names, aliases, chapter IDs, and source mentions in the forms supported by the work,
but the explanatory prose must stay in LANGUAGE.

Do not mix English and Spanish inside explanatory prose unless the input text itself quotes a foreign-language expression that matters narratively.

==================================================
FACT FILTERING RULES
====================

Include only durable facts.

Good facts:

* role, lineage, affiliation, recurring behavior
* abilities, limitations, anomalous properties
* institutional position
* world-rule significance
* persistent injuries, vows, statuses, route commitments, transformations

Bad facts:

* woke up early
* looked at someone
* stood near a window
* walked through a town
* was momentarily tired, angry, embarrassed
* performed minor logistics unless it changes future story state

Each key_fact must be suitable for a standalone Obsidian entity note.

Maximum:

* 5 key_facts per entity
* 5 relationships per entity

==================================================
SUMMARY RULES
=============

Each entity summary must:

* be 1 to 3 sentences
* describe the entity in a reusable way
* use full-work understanding
* avoid chapter-local trivialities

==================================================
CHAPTER REFS
============

chapter_refs must list chapter IDs where the entity is meaningfully relevant,
not merely mentioned in passing.

Use the chapter IDs present in the source text if available.
If the work uses titled chapters/episodes without explicit IDs, generate stable IDs in sequence order, e.g.:

* ch_001
* ch_002
* ch_003

==================================================
SOURCE MENTIONS
===============

source_mentions should include meaningful surface forms found in the text, such as:

* short name
* full name
* titled name
* alternate spelling
* repeated labels for a concept

Do not include generic pronouns.

==================================================
PREFERRED SLUG RULES
====================

preferred_slug must be:

* lowercase
* snake_case
* ASCII if possible
* stable and filesystem-safe

==================================================
REVIEW STATE RULES
==================

* review_state = "canonical" if confidence >= 0.80
* review_state = "review" if confidence < 0.80

==================================================
QUALITY OVERRIDE
================

Before output, remove any entity or fact that would make a poor long-term note in Obsidian.

If the fact only helps understand a single scene, exclude it.
If the entity would not deserve its own note, exclude it.

==================================================
FINAL SELF-CHECK
================

Before producing the JSON:

* remove trivial entities
* remove duplicated facts
* ensure merges are justified
* ensure summaries are globally meaningful
* ensure valid JSON
"""


CHAPTER_EXTRACTION_PROMPT = """You are a narrative chapter extraction system.

Your task is to analyze ONE chapter of a novel and return a JSON object for downstream Obsidian / knowledge graph ingestion.

This chapter must be interpreted using the provided global canonical entity map.

Your objective is NOT to extract everything in the scene.
Your objective is to extract only information that is:

* persistent,
* structurally relevant,
* reusable outside the immediate scene,
* meaningful in relation to the global entity canon.

Return ONLY valid JSON.
Do not include markdown fences.
Do not include commentary.
Do not omit required fields.
If a field has no valid content, return an empty array.

==================================================
OUTPUT SCHEMA
=============

{
"work": {
"title": "...",
"language": "..."
},
"chapters": [
{
"chapter_id": "...",
"chapter_title_original": "...",
"chapter_title_canonical": "...",
"sequence_index": 0,
"chapter_summary": "...",
"characters": [
{
"surface": "...",
"canonical": "...",
"facts": ["..."],
"confidence": 0.0
}
],
"places": [
{
"surface": "...",
"canonical": "...",
"facts": ["..."],
"confidence": 0.0
}
],
"concepts": [
{
"surface": "...",
"canonical": "...",
"facts": ["..."],
"confidence": 0.0
}
],
"events": [
{
"surface": "...",
"canonical": "...",
"facts": ["..."],
"confidence": 0.0
}
],
"relations": [
{
"from_surface": "...",
"from_canonical": "...",
"to_surface": "...",
"to_canonical": "...",
"relation_type": "...",
"facts": ["..."],
"confidence": 0.0
}
],
"unresolved_mentions": [
{
"surface": "...",
"possible_kind": "...",
"facts": ["..."],
"confidence": 0.0
}
]
}
]
}

==================================================
GLOBAL CANON USAGE RULES
========================

You will receive a CANONICAL_ENTITY_MAP produced from the full novel.
You may also receive TITLE_ENTITY_HINTS extracted structurally from the chapter title.

You must:

* prefer canonical names from that map
* reuse existing normalized entities whenever possible
* avoid inventing new canon if a provided canonical entity already matches
* only create unresolved_mentions when a chapter mention cannot be safely matched to the canonical map

If a chapter mention matches a canonical entity with confidence >= 0.80:

* set canonical to that canonical name

If confidence < 0.80:

* keep canonical = surface
* place ambiguous cases in unresolved_mentions if important

Do NOT override the canonical map unless the chapter provides strong contradictory evidence.

If a named identity in the chapter conflicts with a descriptive or titled alias from the canonical map,
prefer the explicit named identity unless the chapter or the global canon clearly confirms the merge.

If TITLE_ENTITY_HINTS contains an explicit proper name and the chapter supports it,
preserve that named identity instead of coercing it into a different canonical entity.

==================================================
RELEVANCE FILTER
================

Include only information that satisfies at least one:

1. identity relevance
2. capability relevance
3. relationship relevance
4. world/system relevance
5. lasting change relevance

Exclude:

* greetings
* posture
* walking/sitting/eating
* temporary emotional color
* local choreography
* atmospheric detail
* minor logistics unless they create a durable consequence

==================================================
CHAPTER SUMMARY RULES
=====================

chapter_summary must:

* be 3 to 6 sentences
* focus on decisions, discoveries, transitions, durable shifts
* avoid micro-actions
* avoid narrating every beat of the scene

==================================================
CHAPTER FACT RULES
==================

For chapter-level characters / places / concepts:

* include only facts that matter beyond the current moment
* do not repeat generic global facts unless the chapter materially reinforces or changes them
* prefer chapter-specific durable updates

Maximum:

* 4 facts per extracted item
* 3 events unless truly necessary

==================================================
EVENT RULES
===========

Include only events that:

* create lasting consequences
* move the plot meaningfully
* introduce new world/system knowledge
* establish a durable transition

Do NOT include events that are just operational scene steps.

==================================================
RELATION RULES
==============

relation_type must be one of:

* familial
* conflict
* alliance
* authority
* dependency
* magical_link
* located_in
* part_of
* member_of
* uses

Include only stable or narratively meaningful relations.

==================================================
UNRESOLVED MENTIONS RULES
=========================

Use unresolved_mentions for important but uncertain references.

possible_kind must be one of:

* character
* place
* concept
* event
* object
* unknown

==================================================
QUALITY OVERRIDE
================

If a chapter-level fact would make a poor addition to an Obsidian note, exclude it.

If an item is already fully explained by the canonical map and the chapter adds nothing durable, omit it from the chapter extraction.

==================================================
LANGUAGE OUTPUT RULES
=====================

Write all explanatory prose in LANGUAGE.

This includes:

* chapter_summary
* facts
* relation facts
* unresolved mention facts

Keep names and source surfaces in the forms supported by the work,
but do not mix English and Spanish inside explanatory prose unless the source itself requires a quoted expression.

==================================================
FINAL SELF-CHECK
================

Before output:

* remove trivial facts
* remove redundant facts already present in canon unless updated here
* ensure canonical names match the supplied entity map
* ensure valid JSON
"""


CHAPTER_PARTIAL_EXTRACTION_PROMPT = """You are a narrative chapter subchunk extraction system.

Analyze ONE partial segment of a chapter and return only persistent or structurally relevant signals.

Return ONLY valid JSON.
Do not include markdown fences.
Do not include commentary.
Do not invent canon beyond the provided canonical entity map.

==================================================
OUTPUT SCHEMA
=============

{
"chapter_id": "...",
"chunk_id": "...",
"partial_signals": {
"characters": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"places": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"concepts": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"events": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"relations": [{"from_surface": "...", "from_canonical": "...", "to_surface": "...", "to_canonical": "...", "relation_type": "...", "facts": ["..."], "confidence": 0.0}],
"unresolved_mentions": [{"surface": "...", "possible_kind": "...", "facts": ["..."], "confidence": 0.0}],
"candidate_summary_points": ["..."]
}
}

==================================================
RULES
=====

Write all explanatory prose in LANGUAGE.
Keep explicit names separate unless identity is clearly confirmed.
Use TITLE_ENTITY_HINTS as additional identity evidence when the title explicitly names a focal entity.
Do not output chapter_text_markdown.
Prefer high-signal durable facts over local choreography.
"""


CHAPTER_REDUCTION_PROMPT = """You are a narrative chapter reducer.

You will receive partial signals extracted from multiple subchunks of the same chapter.
Produce the final normalized chapter JSON for downstream Obsidian ingestion.

Return ONLY valid JSON.
Do not include markdown fences.
Do not include commentary.

==================================================
OUTPUT SCHEMA
=============

{
"work": {
"title": "...",
"language": "..."
},
"chapters": [
{
"chapter_id": "...",
"chapter_title_original": "...",
"chapter_title_canonical": "...",
"sequence_index": 0,
"chapter_summary": "...",
"characters": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"places": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"concepts": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"events": [{"surface": "...", "canonical": "...", "facts": ["..."], "confidence": 0.0}],
"relations": [{"from_surface": "...", "from_canonical": "...", "to_surface": "...", "to_canonical": "...", "relation_type": "...", "facts": ["..."], "confidence": 0.0}],
"unresolved_mentions": [{"surface": "...", "possible_kind": "...", "facts": ["..."], "confidence": 0.0}]
}
]
}

==================================================
RULES
=====

Write all explanatory prose in LANGUAGE.
Do not merge different named entities unless the combined partial signals strongly confirm the identity.
If uncertainty remains, keep the explicit surface as canonical and leave the ambiguity in unresolved_mentions.
Use the canonical entity map when there is a safe match.
Use TITLE_ENTITY_HINTS as a guardrail when the chapter title explicitly names a focal entity.
"""


@dataclass(frozen=True)
class NovelBootstrapV1Config:
    provider_name: str | None
    model: str | None
    advisor_task_name: str = "bootstrap_model_advisor"
    global_task_name: str = "bootstrap_global_normalization"
    chapter_task_name: str = "bootstrap_chapter_extraction"
    global_max_tokens: int = 9000
    chapter_max_tokens: int = 3000
    chapter_reduce_max_tokens: int = 3000
    global_batch_input_token_budget: int | None = 6000
    global_batch_prompt_overhead_tokens: int = 5000
    global_batch_complexity_penalty_base: int = 500
    global_batch_complexity_penalty_per_chapter: int = 250
    global_batch_failure_retry_threshold: int = 2
    chapter_chunk_overlap_paragraphs: int = 1
    temperature: float = 0.0
    timeout_seconds: int = 600
    retries: int = 1
    max_global_text_chars: int = 350000
    max_chapters: int | None = None
    request_trace_sample_chapters: int = 3
    empirical_min_samples_for_hard_preference: int = 8
    empirical_confidence_weight: float = 0.7
    empirical_cold_start_mode: str = "prefer_defaults"
    empirical_freshness_half_life_days: float = 21.0


@dataclass(frozen=True)
class NovelBootstrapV1Result:
    source_document: str
    chapter_count: int
    global_normalization_path: str
    global_batch_audit_path: str
    model_plan_audit_path: str
    canonical_entity_map_path: str
    chapter_outputs_dir: str
    chapters_enriched_path: str
    obsidian_import_path: str
    warnings: list[str] = field(default_factory=list)


def run_structured_bootstrap_v1(
    vault_root: str | Path,
    *,
    inventory: SourceDocumentInventory,
    config: NovelBootstrapV1Config,
    progress_log_path: str | None = None,
) -> NovelBootstrapV1Result | None:
    synchronize_runtime_environment(Path(__file__).resolve().parents[2])
    if get_text_provider_config_error(config.global_task_name, config.provider_name) is not None:
        return None
    if get_text_provider_config_error(config.chapter_task_name, config.provider_name) is not None:
        return None

    vault_root = Path(vault_root)
    texts = read_source_documents(inventory, progress_log_path=progress_log_path)
    source_doc = _select_primary_novel_document(inventory, texts)
    if source_doc is None:
        return None
    source_text = texts.get(source_doc.source_id, "")
    chapters = detect_story_chapters(source_doc, source_text)
    if config.max_chapters:
        chapters = chapters[: config.max_chapters]
    if not chapters:
        return None

    language = source_doc.dominant_language or "unknown"
    work_title = Path(source_doc.filename).stem

    system_root = vault_root / "99_System"
    system_root.mkdir(parents=True, exist_ok=True)
    chapter_outputs_dir = system_root / "chapter_outputs"
    chapter_outputs_dir.mkdir(parents=True, exist_ok=True)
    request_trace_dir = system_root / "api_call_traces"
    request_trace_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    repo_root = Path(__file__).resolve().parents[2]
    telemetry_path = repo_root / ".textifai" / "bootstrap_model_telemetry.json"
    provider_snapshot_path = system_root / "provider_snapshot.json"
    model_plan_audit_path = system_root / "model_plan_audit.json"
    bootstrap_profile = build_bootstrap_profile(
        work_title=work_title,
        language=language,
        chapters=chapters,
        estimate_tokens=_estimate_token_count,
    )
    provider_snapshot = build_provider_snapshot(
        provider_name=config.provider_name,
        requested_model=config.model,
        timeout_seconds=config.timeout_seconds,
        cache_path=provider_snapshot_path,
    )
    advisor_recommendation = maybe_advise_model_plan(
        provider_name=config.provider_name,
        advisor_task_name=config.advisor_task_name,
        requested_model=config.model,
        snapshot=provider_snapshot,
        profile=bootstrap_profile,
        timeout_seconds=config.timeout_seconds,
        retries=config.retries,
    )
    resolved_model_plan, model_plan_audit = resolve_model_plan(
        provider_name=config.provider_name,
        requested_model=config.model,
        snapshot=provider_snapshot,
        profile=bootstrap_profile,
        advisor=advisor_recommendation,
        telemetry_path=telemetry_path,
        empirical_policy=EmpiricalPolicy(
            min_samples_for_hard_preference=config.empirical_min_samples_for_hard_preference,
            confidence_weight=config.empirical_confidence_weight,
            cold_start_mode=config.empirical_cold_start_mode,
            freshness_half_life_days=config.empirical_freshness_half_life_days,
        ),
    )
    model_plan_audit_path.write_text(json.dumps(model_plan_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    global_batch_audit_path = system_root / "global_batch_plan_audit.json"
    global_payload = _run_global_normalization(
        work_title=work_title,
        language=language,
        chapters=chapters,
        source_text=source_text,
        source_path=Path(source_doc.path),
        config=config,
        request_trace_dir=request_trace_dir,
        audit_path=global_batch_audit_path,
        progress_log_path=progress_log_path,
        resolved_model_plan=resolved_model_plan,
        telemetry_path=telemetry_path,
    )
    if global_payload is None:
        return None
    global_normalization_path = system_root / "global_normalization.json"
    global_normalization_path.write_text(json.dumps(global_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    canonical_entity_map = build_canonical_entity_map(global_payload)
    canonical_entity_map_path = system_root / "canonical_entity_map.json"
    canonical_entity_map_path.write_text(json.dumps(canonical_entity_map, ensure_ascii=False, indent=2), encoding="utf-8")

    chapter_outputs: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        chapter_id = f"ch_{index:03d}"
        _append_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="chapter_extraction_started",
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            sequence_index=index,
        )
        chapter_payload = _run_chapter_extraction(
            work_title=work_title,
            language=language,
            chapter_id=chapter_id,
            sequence_index=index,
            chapter_title=chapter.title,
            chapter_text=chapter.text,
            canonical_entity_map=canonical_entity_map,
            config=config,
            resolved_model_plan=resolved_model_plan,
            telemetry_path=telemetry_path,
            request_trace_path=(
                request_trace_dir / f"{chapter_id}_request.json"
                if index <= max(0, config.request_trace_sample_chapters)
                else None
            ),
        )
        if chapter_payload is None:
            warnings.append(f"chapter_extraction_failed:{chapter.title}")
            _append_progress(
                progress_log_path,
                phase="structured_bootstrap_v1",
                event="chapter_extraction_failed",
                chapter_id=chapter_id,
                chapter_title=chapter.title,
            )
            continue
        chapter_payload = _normalize_chapter_payload(
            chapter_payload,
            chapter_id=chapter_id,
            sequence_index=index,
            chapter_title=chapter.title,
            chapter_text=chapter.text,
            work_title=work_title,
            language=language,
        )
        chapter_outputs.append(chapter_payload)
        (chapter_outputs_dir / f"{chapter_id}.json").write_text(json.dumps(chapter_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _append_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="chapter_extraction_completed",
            chapter_id=chapter_id,
            chapter_title=chapter.title,
        )

    chapters_enriched = {
        "work": global_payload.get("work") or {"title": work_title, "language": language},
        "chapters": [item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
    }
    chapters_enriched_path = system_root / "chapters_enriched.json"
    chapters_enriched_path.write_text(json.dumps(chapters_enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    obsidian_import = assemble_obsidian_import(
        global_data=global_payload,
        chapter_outputs=[item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
    )
    obsidian_import_path = system_root / "obsidian_import.json"
    obsidian_import_path.write_text(json.dumps(obsidian_import, ensure_ascii=False, indent=2), encoding="utf-8")

    return NovelBootstrapV1Result(
        source_document=source_doc.path,
        chapter_count=len(chapters),
        global_normalization_path=str(global_normalization_path),
        global_batch_audit_path=str(global_batch_audit_path),
        model_plan_audit_path=str(model_plan_audit_path),
        canonical_entity_map_path=str(canonical_entity_map_path),
        chapter_outputs_dir=str(chapter_outputs_dir),
        chapters_enriched_path=str(chapters_enriched_path),
        obsidian_import_path=str(obsidian_import_path),
        warnings=warnings,
    )


def build_canonical_entity_map(
    global_data: dict[str, Any],
    *,
    include_review: bool = True,
    max_key_facts: int = 4,
) -> list[dict[str, Any]]:
    entities = global_data.get("entities", [])
    canonical_map: list[dict[str, Any]] = []
    for ent in entities:
        review_state = ent.get("review_state", "review")
        if not include_review and review_state != "canonical":
            continue
        canonical_map.append(
            {
                "canonical_name": ent.get("canonical_name", ""),
                "entity_kind": ent.get("entity_kind", ""),
                "aliases": ent.get("aliases", []),
                "summary": ent.get("summary", ""),
                "key_facts": (ent.get("key_facts", []) or [])[:max_key_facts],
                "review_state": review_state,
                "confidence": ent.get("confidence", 0.0),
            }
        )
    canonical_map.sort(key=lambda x: (str(x["entity_kind"]), str(x["canonical_name"]).lower()))
    return canonical_map


def assemble_obsidian_import(*, global_data: dict[str, Any], chapter_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    work = global_data.get("work", {})
    entities = enrich_global_entities_conservative(global_data.get("entities", []) or [], chapter_outputs)
    entities = _promote_recurring_chapter_entities(entities, chapter_outputs)
    entities = _promote_title_hint_entities(entities, chapter_outputs)
    entities = _stabilize_character_entities_with_title_hints(
        entities,
        chapter_outputs,
        language=str(work.get("language") or "unknown"),
    )
    chapters = sorted(chapter_outputs, key=lambda ch: (ch.get("sequence_index", 0), ch.get("chapter_id", "")))
    return {"work": work, "chapters": chapters, "entities": entities}


def enrich_global_entities_conservative(global_entities: list[dict[str, Any]], chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entity_index = build_entity_index(global_entities)
    chapter_refs_map: dict[str, list[str]] = {}
    source_mentions_map: dict[str, list[str]] = {}
    relationship_candidates_map: dict[str, list[dict[str, Any]]] = {}
    for ent in global_entities:
        name = str(ent.get("canonical_name") or "").strip()
        if name:
            chapter_refs_map[name] = []
            source_mentions_map[name] = []
            relationship_candidates_map[name] = []
    for ch in chapters:
        chapter_id = str(ch.get("chapter_id") or "").strip()
        if not chapter_id:
            continue
        for mention in extract_local_entity_mentions(ch):
            canonical = mention["canonical"]
            surface = mention["surface"]
            if canonical in entity_index:
                chapter_refs_map[canonical].append(chapter_id)
                if surface:
                    source_mentions_map[canonical].append(surface)
        for rel in ch.get("relations", []):
            from_canonical = str(rel.get("from_canonical") or "").strip()
            to_canonical = str(rel.get("to_canonical") or "").strip()
            if from_canonical in entity_index:
                converted = chapter_relation_to_entity_relation(rel, from_canonical)
                if converted:
                    relationship_candidates_map[from_canonical].append(converted)
            if to_canonical in entity_index:
                converted = chapter_relation_to_entity_relation(rel, to_canonical)
                if converted:
                    relationship_candidates_map[to_canonical].append(converted)
    enriched: list[dict[str, Any]] = []
    for ent in global_entities:
        canonical_name = str(ent.get("canonical_name") or "").strip()
        if not canonical_name:
            continue
        enriched.append(
            {
                **ent,
                "chapter_refs": unique_preserve_order((ent.get("chapter_refs", []) or []) + chapter_refs_map[canonical_name]),
                "source_mentions": unique_preserve_order((ent.get("source_mentions", []) or []) + source_mentions_map[canonical_name]),
                "relationships": merge_relationship_lists(ent.get("relationships", []) or [], relationship_candidates_map[canonical_name]),
            }
        )
    enriched.sort(key=lambda e: (e.get("entity_kind", ""), str(e.get("canonical_name", "")).lower()))
    return enriched


def build_entity_index(global_entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for ent in global_entities:
        name = str(ent.get("canonical_name") or "").strip()
        if name:
            idx[name] = ent
    return idx


def _promote_recurring_chapter_entities(
    global_entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_index = build_entity_index(global_entities)
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    section_kind = {"characters": "character", "places": "place", "concepts": "concept", "events": "event"}

    for chapter in chapter_outputs:
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        for section, entity_kind in section_kind.items():
            for item in chapter.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                canonical = str(item.get("canonical") or item.get("surface") or "").strip()
                surface = str(item.get("surface") or canonical).strip()
                if not canonical or canonical in entity_index:
                    continue
                key = (entity_kind, canonical)
                bucket = candidates.setdefault(
                    key,
                    {
                        "canonical_name": canonical,
                        "entity_kind": entity_kind,
                        "preferred_slug": "",
                        "aliases": [],
                        "summary": "",
                        "key_facts": [],
                        "relationships": [],
                        "chapter_refs": [],
                        "source_mentions": [],
                        "confidence_values": [],
                        "review_state": "review",
                    },
                )
                bucket["aliases"] = unique_preserve_order(bucket["aliases"] + ([surface] if surface else []))
                bucket["key_facts"] = unique_preserve_order(bucket["key_facts"] + (item.get("facts") or []))[:5]
                bucket["chapter_refs"] = unique_preserve_order(bucket["chapter_refs"] + ([chapter_id] if chapter_id else []))
                bucket["source_mentions"] = unique_preserve_order(bucket["source_mentions"] + ([surface] if surface else []))
                bucket["confidence_values"].append(float(item.get("confidence") or 0.0))

    promoted: list[dict[str, Any]] = []
    for candidate in candidates.values():
        chapter_refs = candidate["chapter_refs"]
        avg_confidence = (
            sum(candidate["confidence_values"]) / len(candidate["confidence_values"])
            if candidate["confidence_values"]
            else 0.0
        )
        if len(chapter_refs) < 2 and avg_confidence < 0.9:
            continue
        summary = ""
        if candidate["key_facts"]:
            summary = candidate["key_facts"][0]
        review_state = "canonical" if len(chapter_refs) >= 2 and avg_confidence >= 0.85 else "review"
        promoted.append(
            {
                "canonical_name": candidate["canonical_name"],
                "entity_kind": candidate["entity_kind"],
                "preferred_slug": "",
                "aliases": candidate["aliases"],
                "summary": summary,
                "key_facts": candidate["key_facts"],
                "relationships": [],
                "chapter_refs": chapter_refs,
                "source_mentions": candidate["source_mentions"],
                "confidence": avg_confidence,
                "review_state": review_state,
            }
        )

    merged = [*global_entities, *promoted]
    merged.sort(key=lambda e: (e.get("entity_kind", ""), str(e.get("canonical_name", "")).lower()))
    return merged


def _promote_title_hint_entities(
    global_entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_index = build_entity_index(global_entities)
    title_candidates: dict[str, dict[str, Any]] = {}

    for chapter in chapter_outputs:
        title = str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "").strip()
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        hints = _extract_title_entity_hints(title)
        for hint in hints:
            if not hint or hint in entity_index:
                continue
            bucket = title_candidates.setdefault(
                hint,
                {
                    "canonical_name": hint,
                    "entity_kind": "character",
                    "preferred_slug": "",
                    "aliases": [],
                    "summary_candidates": [],
                    "key_facts": [],
                    "chapter_refs": [],
                    "source_mentions": [],
                },
            )
            bucket["chapter_refs"] = unique_preserve_order(bucket["chapter_refs"] + ([chapter_id] if chapter_id else []))
            bucket["source_mentions"] = unique_preserve_order(bucket["source_mentions"] + [hint])
            summary = str(chapter.get("chapter_summary") or "").strip()
            if summary:
                bucket["summary_candidates"].append(summary)
            for character in chapter.get("characters", []) or []:
                if not isinstance(character, dict):
                    continue
                surface = str(character.get("surface") or "").strip()
                canonical = str(character.get("canonical") or surface).strip()
                if canonical != hint and surface != hint:
                    continue
                facts = [str(fact).strip() for fact in (character.get("facts") or []) if str(fact).strip()]
                bucket["key_facts"] = unique_preserve_order(bucket["key_facts"] + facts)[:5]

    promoted: list[dict[str, Any]] = []
    for bucket in title_candidates.values():
        if len(bucket["chapter_refs"]) < 2:
            continue
        summary = (
            f"{bucket['canonical_name']} aparece como identidad focal explícita en varios títulos de capítulo y concentra un tramo reconocible del foco narrativo."
            if not bucket["key_facts"]
            else f"{bucket['canonical_name']} aparece como identidad focal explícita en varios capítulos de la obra."
        )
        promoted.append(
            {
                "canonical_name": bucket["canonical_name"],
                "entity_kind": "character",
                "preferred_slug": "",
                "aliases": bucket["aliases"],
                "summary": summary,
                "key_facts": bucket["key_facts"],
                "relationships": [],
                "chapter_refs": bucket["chapter_refs"],
                "source_mentions": bucket["source_mentions"],
                "confidence": 0.9,
                "review_state": "canonical",
            }
        )

    merged = [*global_entities, *promoted]
    merged.sort(key=lambda e: (e.get("entity_kind", ""), str(e.get("canonical_name", "")).lower()))
    return merged


def _stabilize_character_entities_with_title_hints(
    global_entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
    *,
    language: str,
) -> list[dict[str, Any]]:
    chapter_title_hints: dict[str, list[str]] = {}
    chapter_character_mentions: dict[str, list[dict[str, Any]]] = {}
    chapter_summaries: dict[str, str] = {}
    for chapter in chapter_outputs:
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        if not chapter_id:
            continue
        title = str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "").strip()
        chapter_title_hints[chapter_id] = _extract_title_entity_hints(title)
        chapter_character_mentions[chapter_id] = [
            item for item in (chapter.get("characters") or []) if isinstance(item, dict)
        ]
        chapter_summaries[chapter_id] = str(chapter.get("chapter_summary") or "").strip()

    stabilized: list[dict[str, Any]] = []
    for entity in global_entities:
        if str(entity.get("entity_kind") or "").strip() != "character":
            stabilized.append(entity)
            continue

        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not canonical_name:
            stabilized.append(entity)
            continue

        chapter_refs = [str(ref).strip() for ref in (entity.get("chapter_refs") or []) if str(ref).strip()]
        aligned_refs: list[str] = []
        neutral_refs: list[str] = []
        conflicting_refs: list[str] = []
        for chapter_ref in chapter_refs:
            hints = chapter_title_hints.get(chapter_ref, [])
            if not hints:
                neutral_refs.append(chapter_ref)
                continue
            if canonical_name in hints:
                aligned_refs.append(chapter_ref)
            else:
                conflicting_refs.append(chapter_ref)

        # Keep original entity untouched unless title evidence clearly points to contamination.
        if not aligned_refs or not conflicting_refs:
            stabilized.append(entity)
            continue

        kept_refs = unique_preserve_order(aligned_refs + neutral_refs)
        if not kept_refs:
            stabilized.append(entity)
            continue

        local_facts: list[str] = []
        for chapter_ref in kept_refs:
            for mention in chapter_character_mentions.get(chapter_ref, []):
                surface = str(mention.get("surface") or "").strip()
                canonical = str(mention.get("canonical") or surface).strip()
                if canonical != canonical_name and surface != canonical_name:
                    continue
                facts = [str(fact).strip() for fact in (mention.get("facts") or []) if str(fact).strip()]
                local_facts = unique_preserve_order(local_facts + facts)[:5]

        summary = str(entity.get("summary") or "").strip()
        if local_facts:
            summary = _compose_entity_summary_from_local_facts(
                canonical_name=canonical_name,
                key_facts=local_facts,
                language=language,
            )
        elif conflicting_refs and summary:
            summary = _strip_entity_summary_to_safe_sentence(summary, canonical_name=canonical_name, language=language)

        stabilized.append(
            {
                **entity,
                "summary": summary,
                "key_facts": local_facts or (entity.get("key_facts") or []),
                "chapter_refs": kept_refs,
            }
        )

    stabilized.sort(key=lambda e: (e.get("entity_kind", ""), str(e.get("canonical_name", "")).lower()))
    return stabilized


def _compose_entity_summary_from_local_facts(*, canonical_name: str, key_facts: list[str], language: str) -> str:
    if not key_facts:
        return ""
    lead = key_facts[0].rstrip(".")
    follow_up = key_facts[1].rstrip(".") if len(key_facts) > 1 else ""
    if str(language).lower().startswith("es"):
        summary = f"{canonical_name} destaca en los capítulos analizados por un papel persistente en la historia. {lead}."
        if follow_up:
            summary += f" {follow_up}."
        return summary
    summary = f"{canonical_name} has a persistent role across the analyzed chapters. {lead}."
    if follow_up:
        summary += f" {follow_up}."
    return summary


def _strip_entity_summary_to_safe_sentence(summary: str, *, canonical_name: str, language: str) -> str:
    cleaned = re.sub(r"\s+", " ", summary).strip()
    if not cleaned:
        return summary
    first_sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0].strip()
    if canonical_name.casefold() in first_sentence.casefold():
        return first_sentence
    if str(language).lower().startswith("es"):
        return f"{canonical_name} mantiene una presencia narrativa persistente en los capítulos analizados."
    return f"{canonical_name} maintains a persistent narrative presence across the analyzed chapters."


def extract_local_entity_mentions(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for section in ("characters", "places", "concepts"):
        for item in chapter.get(section, []):
            mentions.append(
                {
                    "section": section,
                    "surface": str(item.get("surface") or "").strip(),
                    "canonical": str(item.get("canonical") or "").strip(),
                    "facts": item.get("facts", []) or [],
                    "confidence": item.get("confidence", 0.0),
                }
            )
    return mentions


def chapter_relation_to_entity_relation(rel: dict[str, Any], entity_name: str) -> dict[str, Any] | None:
    from_canonical = str(rel.get("from_canonical") or "").strip()
    to_canonical = str(rel.get("to_canonical") or "").strip()
    relation_type = str(rel.get("relation_type") or "").strip()
    facts = rel.get("facts", []) or []
    if not relation_type:
        return None
    if from_canonical == entity_name and to_canonical:
        return {"target": to_canonical, "type": relation_type, "facts": facts}
    if to_canonical == entity_name and from_canonical:
        return {"target": from_canonical, "type": relation_type, "facts": facts}
    return None


def merge_relationship_lists(existing: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[tuple[str, str], dict[str, Any]] = {}

    def _add(rel: dict[str, Any]) -> None:
        target = str(rel.get("target") or "").strip()
        rel_type = str(rel.get("type") or "").strip()
        if not target or not rel_type:
            return
        key = (target, rel_type)
        facts = rel.get("facts", []) or []
        if key not in bucket:
            bucket[key] = {"target": target, "type": rel_type, "facts": unique_preserve_order(facts)}
        else:
            bucket[key]["facts"] = unique_preserve_order(bucket[key]["facts"] + facts)

    for rel in existing:
        _add(rel)
    for rel in candidates:
        _add(rel)
    return sorted(bucket.values(), key=lambda r: (r["type"], str(r["target"]).lower()))


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalize_text(item)
        if key and key not in seen:
            seen.add(key)
            out.append(str(item).strip())
    return out


def normalize_text(text: str) -> str:
    return " ".join(str(text).strip().split()).lower()


def _estimate_token_count(text: str) -> int:
    compact = str(text or "").strip()
    if not compact:
        return 0
    return max(1, len(compact) // 4)


def _build_global_normalization_batches(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    config: NovelBootstrapV1Config,
    resolved_model_plan: ResolvedModelPlan | None = None,
) -> tuple[list[list[dict[str, Any]]], dict[str, Any]]:
    global_model = _resolve_structured_model(config, phase="global_normalization", resolved_model_plan=resolved_model_plan)
    capabilities = get_model_capabilities(global_model)
    budget = _build_global_token_budget(config=config, resolved_model_plan=resolved_model_plan)
    chapter_rows: list[dict[str, Any]] = []
    chapter_items = [
        {
            "sequence_index": sequence_index,
            "title": chapter.title,
            "text": chapter.text,
        }
        for sequence_index, chapter in enumerate(chapters, start=1)
    ]

    max_total_cost = capabilities.context_window - budget.safety_margin

    def measure_batch(candidate: list[dict[str, Any]]) -> tuple[int, str]:
        tokens, token_method = _count_global_batch_input_tokens(
            work_title=work_title,
            language=language,
            batch=candidate,
            config=config,
            resolved_model_plan=resolved_model_plan,
        )
        if candidate:
            chapter_rows.append(
                {
                    "chapter_id": f"ch_{candidate[-1]['sequence_index']:03d}",
                    "chapter_title": candidate[-1]["title"],
                    "candidate_batch_size": len(candidate),
                    "candidate_input_tokens": tokens,
                    "token_count_method": token_method,
                }
            )
        return tokens, token_method

    def measure_total_cost(candidate: list[dict[str, Any]], input_tokens: int) -> int:
        expected_output_tokens = min(
            config.global_max_tokens,
            800 + (len(candidate) * 450),
        )
        complexity_penalty = _estimate_global_batch_complexity_penalty(candidate, config=config)
        return input_tokens + expected_output_tokens + complexity_penalty

    planned_batches = pack_items_by_budget(
        items=chapter_items,
        budget=budget,
        measure_tokens=measure_batch,
        measure_total_cost=measure_total_cost,
        max_total_cost=max_total_cost,
    )
    batches = [planned.items for planned in planned_batches]
    audit_batches = [
        {
            "batch_index": index,
            "chapter_ids": [f"ch_{item['sequence_index']:03d}" for item in planned.items],
            "chapter_count": len(planned.items),
            "input_tokens": planned.input_tokens,
            "estimated_total_cost": planned.estimated_total_cost,
            "token_count_method": planned.token_count_method,
            "budget": budget.usable_input_budget,
        }
        for index, planned in enumerate(planned_batches, start=1)
    ]
    return (
        batches,
        {
            "work_title": work_title,
            "language": language,
            "provider_name": config.provider_name,
            "model": global_model,
            "model_capabilities": {
                "context_window": capabilities.context_window,
                "max_output_tokens": capabilities.max_output_tokens,
                "recommended_output_reserve": capabilities.recommended_output_reserve,
                "recommended_safety_margin": capabilities.recommended_safety_margin,
                "supports_structured_outputs": capabilities.supports_structured_outputs,
            },
            "budget_tokens": budget.usable_input_budget,
            "max_total_cost": max_total_cost,
            "reserved_output_tokens": budget.reserved_output_tokens,
            "safety_margin": budget.safety_margin,
            "budget_method": "model_registry_plus_counted_input",
            "chapter_count": len(chapters),
            "batch_count": len(batches),
            "candidate_measurements": chapter_rows,
            "batches": audit_batches,
        },
    )


def _estimate_global_batch_complexity_penalty(
    batch: list[dict[str, Any]],
    *,
    config: NovelBootstrapV1Config,
) -> int:
    penalty = config.global_batch_complexity_penalty_base
    for item in batch:
        title = str(item.get("title") or "")
        text = str(item.get("text") or "")
        penalty += config.global_batch_complexity_penalty_per_chapter
        if "[" in title or "]" in title or "(" in title or ")" in title or "*" in title or "http" in title.casefold():
            penalty += 200
        markdown_noise = text.count("[[") + text.count("]]") + text.count("](") + text.casefold().count("http")
        heading_count = len(re.findall(r"(?m)^#+\s+", text))
        penalty += min(800, markdown_noise * 20)
        penalty += min(600, heading_count * 40)
        penalty += min(1200, max(0, len(text) // 2500))
    return penalty

def _build_global_token_budget(*, config: NovelBootstrapV1Config, resolved_model_plan: ResolvedModelPlan | None = None) -> TokenBudget:
    capabilities = get_model_capabilities(_resolve_structured_model(config, phase="global_normalization", resolved_model_plan=resolved_model_plan))
    override_budget = config.global_batch_input_token_budget
    budget = build_token_budget(
        capabilities=capabilities,
        requested_output_tokens=config.global_max_tokens,
    )
    if override_budget is None:
        return budget
    return TokenBudget(
        context_window=budget.context_window,
        reserved_output_tokens=budget.reserved_output_tokens,
        safety_margin=budget.safety_margin,
        usable_input_budget=min(budget.usable_input_budget, override_budget),
    )


def _build_chapter_token_budget(*, config: NovelBootstrapV1Config, resolved_model_plan: ResolvedModelPlan | None = None) -> TokenBudget:
    capabilities = get_model_capabilities(_resolve_structured_model(config, phase="chapter_extraction", resolved_model_plan=resolved_model_plan))
    return build_token_budget(
        capabilities=capabilities,
        requested_output_tokens=max(config.chapter_max_tokens, config.chapter_reduce_max_tokens),
    )


def _count_global_batch_input_tokens(
    *,
    work_title: str,
    language: str,
    batch: list[dict[str, Any]],
    config: NovelBootstrapV1Config,
    resolved_model_plan: ResolvedModelPlan | None = None,
) -> tuple[int, str]:
    global_model = _resolve_structured_model(config, phase="global_normalization", resolved_model_plan=resolved_model_plan)
    prompt = _build_global_normalization_prompt(
        work_title=work_title,
        language=language,
        batch_index=1,
        batch=batch,
    )
    if config.provider_name == "openai":
        counted = _count_openai_input_tokens_for_prompt(
            model=global_model,
            prompt=prompt,
            timeout_seconds=config.timeout_seconds,
        )
        if counted is not None:
            return counted, "openai_responses_input_tokens"
    return _estimate_token_count(prompt), "estimated_chars_div_4"


def _build_global_normalization_prompt(
    *,
    work_title: str,
    language: str,
    batch_index: int,
    batch: list[dict[str, Any]],
) -> str:
    batch_text = "\n\n".join(
        f"[ch_{item['sequence_index']:03d}] {item['title']}\n{item['text']}"
        for item in batch
    )
    batch_chapter_ids = [f"ch_{item['sequence_index']:03d}" for item in batch]
    return (
        f"{GLOBAL_NORMALIZATION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        "BATCH_SCOPE:\n"
        f"- Batch index: {batch_index}\n"
        f"- Chapter IDs: {', '.join(batch_chapter_ids)}\n"
        "Normalize persistent entities using only this batch as evidence. "
        "Return entities worth keeping as long-term notes plus high-confidence merges supported by this batch.\n\n"
        f"FULL_TEXT:\n{batch_text}"
    )


def _render_global_batch_text(batch: list[dict[str, Any]], *, max_chars: int) -> str:
    rendered = "\n\n".join(
        f"[ch_{item['sequence_index']:03d}] {item['title']}\n{item['text']}"
        for item in batch
    )
    if len(rendered) > max_chars:
        return rendered[:max_chars]
    return rendered


def _merge_global_normalization_batches(
    batch_payloads: list[dict[str, Any]],
    *,
    work_title: str,
    language: str,
) -> dict[str, Any]:
    entity_bucket: dict[str, dict[str, Any]] = {}
    merge_plan_bucket: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    normalization_notes: list[str] = []

    for payload in batch_payloads:
        work = payload.get("work") or {}
        normalization_notes.extend(
            str(item).strip()
            for item in (work.get("normalization_notes") or [])
            if str(item).strip()
        )
        for entity in payload.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            canonical_name = str(entity.get("canonical_name") or "").strip()
            if not canonical_name:
                continue
            existing = entity_bucket.get(canonical_name)
            if existing is None:
                entity_bucket[canonical_name] = {
                    **entity,
                    "aliases": unique_preserve_order([str(item).strip() for item in (entity.get("aliases") or []) if str(item).strip()]),
                    "key_facts": unique_preserve_order([str(item).strip() for item in (entity.get("key_facts") or []) if str(item).strip()])[:5],
                    "chapter_refs": unique_preserve_order([str(item).strip() for item in (entity.get("chapter_refs") or []) if str(item).strip()]),
                    "source_mentions": unique_preserve_order([str(item).strip() for item in (entity.get("source_mentions") or []) if str(item).strip()]),
                    "relationships": merge_relationship_lists([], entity.get("relationships") or []),
                }
                continue
            merged_summary = str(existing.get("summary") or "").strip()
            incoming_summary = str(entity.get("summary") or "").strip()
            if len(incoming_summary) > len(merged_summary):
                existing["summary"] = incoming_summary
            existing["aliases"] = unique_preserve_order(existing.get("aliases", []) + (entity.get("aliases") or []))
            existing["key_facts"] = unique_preserve_order(existing.get("key_facts", []) + (entity.get("key_facts") or []))[:5]
            existing["chapter_refs"] = unique_preserve_order(existing.get("chapter_refs", []) + (entity.get("chapter_refs") or []))
            existing["source_mentions"] = unique_preserve_order(existing.get("source_mentions", []) + (entity.get("source_mentions") or []))
            existing["relationships"] = merge_relationship_lists(existing.get("relationships", []) or [], entity.get("relationships") or [])
            existing["confidence"] = max(float(existing.get("confidence") or 0.0), float(entity.get("confidence") or 0.0))
            if str(existing.get("review_state") or "review") != "canonical" and str(entity.get("review_state") or "review") == "canonical":
                existing["review_state"] = "canonical"
            if not str(existing.get("preferred_slug") or "").strip():
                existing["preferred_slug"] = entity.get("preferred_slug")
        for merge in payload.get("merge_plan") or []:
            if not isinstance(merge, dict):
                continue
            canonical_name = str(merge.get("canonical_name") or "").strip()
            surfaces = unique_preserve_order([str(item).strip() for item in (merge.get("merged_surfaces") or []) if str(item).strip()])
            if not canonical_name or not surfaces:
                continue
            key = (canonical_name, tuple(surfaces))
            existing_merge = merge_plan_bucket.get(key)
            if existing_merge is None or float(merge.get("confidence") or 0.0) > float(existing_merge.get("confidence") or 0.0):
                merge_plan_bucket[key] = {
                    "canonical_name": canonical_name,
                    "merged_surfaces": surfaces,
                    "reason": str(merge.get("reason") or "").strip(),
                    "confidence": float(merge.get("confidence") or 0.0),
                }

    entities = sorted(entity_bucket.values(), key=lambda item: (str(item.get("entity_kind") or ""), str(item.get("canonical_name") or "").lower()))
    merge_plan = sorted(merge_plan_bucket.values(), key=lambda item: (item["canonical_name"].lower(), item["merged_surfaces"]))
    return {
        "work": {
            "title": work_title,
            "language": language,
            "normalization_notes": unique_preserve_order(normalization_notes + [f"batched_global_normalization:{len(batch_payloads)}"]),
        },
        "entities": entities,
        "merge_plan": merge_plan,
    }


def _run_global_normalization(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    source_text: str,
    source_path: Path,
    config: NovelBootstrapV1Config,
    request_trace_dir: Path | None = None,
    audit_path: Path | None = None,
    progress_log_path: str | None = None,
    resolved_model_plan: ResolvedModelPlan | None = None,
    telemetry_path: Path | None = None,
) -> dict[str, Any] | None:
    global_model = _resolve_structured_model(config, phase="global_normalization", resolved_model_plan=resolved_model_plan)
    _ = source_text
    _ = source_path
    provider = get_text_provider(config.global_task_name, config.provider_name)
    chapter_batches, batch_audit = _build_global_normalization_batches(
        work_title=work_title,
        language=language,
        chapters=chapters,
        config=config,
        resolved_model_plan=resolved_model_plan,
    )
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(batch_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    batch_payloads: list[dict[str, Any]] = []
    batch_meta_by_key = {
        tuple(item["chapter_ids"]): item
        for item in batch_audit.get("batches", [])
        if item.get("chapter_ids")
    }

    for batch_index, batch in enumerate(chapter_batches, start=1):
        batch_payloads.extend(
            _run_global_normalization_batch_with_fallbacks(
                provider=provider,
                work_title=work_title,
                language=language,
                batch=batch,
                batch_index=batch_index,
                global_model=global_model,
                config=config,
                batch_meta_by_key=batch_meta_by_key,
                request_trace_dir=request_trace_dir,
                progress_log_path=progress_log_path,
                telemetry_path=telemetry_path,
            )
        )

    if not batch_payloads:
        return None
    return _merge_global_normalization_batches(batch_payloads, work_title=work_title, language=language)


def _run_global_normalization_batch_with_fallbacks(
    *,
    provider,
    work_title: str,
    language: str,
    batch: list[dict[str, Any]],
    batch_index: int,
    global_model: str,
    config: NovelBootstrapV1Config,
    batch_meta_by_key: dict[tuple[str, ...], dict[str, Any]],
    request_trace_dir: Path | None,
    progress_log_path: str | None,
    telemetry_path: Path | None,
    subdivision_depth: int = 0,
) -> list[dict[str, Any]]:
    batch_text = _render_global_batch_text(batch, max_chars=config.max_global_text_chars)
    if not batch_text.strip():
        return []
    batch_chapter_ids = [f"ch_{item['sequence_index']:03d}" for item in batch]
    batch_key = tuple(batch_chapter_ids)
    batch_meta = batch_meta_by_key.get(batch_key, {})
    prompt = _build_global_normalization_prompt(
        work_title=work_title,
        language=language,
        batch_index=batch_index,
        batch=batch,
    )
    _append_progress(
        progress_log_path,
        phase="structured_bootstrap_v1",
        event="global_normalization_batch_started",
        batch_index=batch_index,
        chapter_ids=batch_chapter_ids,
        estimated_input_tokens=batch_meta.get("input_tokens"),
        estimated_total_cost=batch_meta.get("estimated_total_cost"),
        token_count_method=batch_meta.get("token_count_method"),
        subdivision_depth=subdivision_depth,
    )

    if request_trace_dir is not None and batch_index == 1 and subdivision_depth == 0:
        _write_json_trace(
            request_trace_dir / "global_normalization_batch_001_request.json",
            {
                "provider": config.provider_name,
                "task": config.global_task_name,
                "payload": {
                    "model": config.model,
                    "resolved_model": global_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": config.temperature,
                    "max_tokens": config.global_max_tokens,
                    "response_format": {"type": "json_object"},
                },
            },
        )

    last_error: str | None = None
    for failure_attempt in range(1, config.global_batch_failure_retry_threshold + 1):
        started_at = time.perf_counter()
        try:
            response = provider.generate(
                TextGenerationRequest(
                    task=config.global_task_name,
                    provider_name=config.provider_name,
                    model=global_model,
                    system="Return only valid JSON for global novel normalization.",
                    messages=[TextMessage(role="user", content=prompt)],
                    max_tokens=config.global_max_tokens,
                    temperature=config.temperature,
                    timeout_seconds=config.timeout_seconds,
                    retries=config.retries,
                    response_format={"type": "json_object"},
                )
            )
            payload = extract_json_payload(response.text)
            normalized = _normalize_global_payload(
                payload,
                work_title=work_title,
                language=language,
                batch_note=f"batch_{batch_index}:{','.join(batch_chapter_ids)}",
            )
            if request_trace_dir is not None and batch_index == 1 and subdivision_depth == 0:
                _write_json_trace(
                    request_trace_dir / "global_normalization_batch_001_response.json",
                    {"raw_text": response.text},
                )
            _append_progress(
                progress_log_path,
                phase="structured_bootstrap_v1",
                event="global_normalization_batch_completed",
                batch_index=batch_index,
                chapter_ids=batch_chapter_ids,
                entity_count=len(normalized.get("entities") or []),
                subdivision_depth=subdivision_depth,
            )
            if telemetry_path is not None:
                append_empirical_record(
                    telemetry_path,
                    make_empirical_record(
                        provider_name=str(config.provider_name or ""),
                        phase="global_normalization",
                        complexity_bucket="large_or_complex" if len(batch) > 1 else "medium_complex",
                        model=global_model,
                        success=True,
                        json_valid=True,
                        latency_seconds=time.perf_counter() - started_at,
                        estimated_total_cost=int(batch_meta.get("estimated_total_cost") or 0),
                    ),
                )
            return [normalized]
        except TextProviderError as exc:
            last_error = str(exc)
            _append_progress(
                progress_log_path,
                phase="structured_bootstrap_v1",
                event="global_normalization_batch_failed",
                batch_index=batch_index,
                chapter_ids=batch_chapter_ids,
                failure_attempt=failure_attempt,
                subdivision_depth=subdivision_depth,
                error=last_error,
            )
            if telemetry_path is not None and failure_attempt == config.global_batch_failure_retry_threshold:
                append_empirical_record(
                    telemetry_path,
                    make_empirical_record(
                        provider_name=str(config.provider_name or ""),
                        phase="global_normalization",
                        complexity_bucket="large_or_complex" if len(batch) > 1 else "medium_complex",
                        model=global_model,
                        success=False,
                        json_valid=False,
                        latency_seconds=time.perf_counter() - started_at,
                        estimated_total_cost=int(batch_meta.get("estimated_total_cost") or 0),
                        subdivided=len(batch) > 1,
                        stalled=True,
                        timed_out="timeout" in last_error.casefold(),
                    ),
                )

    if len(batch) > 1:
        midpoint = max(1, len(batch) // 2)
        left = batch[:midpoint]
        right = batch[midpoint:]
        _append_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="global_normalization_batch_subdivided",
            batch_index=batch_index,
            chapter_ids=batch_chapter_ids,
            subdivision_depth=subdivision_depth,
            left_chapter_ids=[f"ch_{item['sequence_index']:03d}" for item in left],
            right_chapter_ids=[f"ch_{item['sequence_index']:03d}" for item in right],
            error=last_error,
        )
        payloads: list[dict[str, Any]] = []
        payloads.extend(
            _run_global_normalization_batch_with_fallbacks(
                provider=provider,
                work_title=work_title,
                language=language,
                batch=left,
                batch_index=batch_index,
                global_model=global_model,
                config=config,
                batch_meta_by_key=batch_meta_by_key,
                request_trace_dir=request_trace_dir,
                progress_log_path=progress_log_path,
                telemetry_path=telemetry_path,
                subdivision_depth=subdivision_depth + 1,
            )
        )
        payloads.extend(
            _run_global_normalization_batch_with_fallbacks(
                provider=provider,
                work_title=work_title,
                language=language,
                batch=right,
                batch_index=batch_index,
                global_model=global_model,
                config=config,
                batch_meta_by_key=batch_meta_by_key,
                request_trace_dir=request_trace_dir,
                progress_log_path=progress_log_path,
                telemetry_path=telemetry_path,
                subdivision_depth=subdivision_depth + 1,
            )
        )
        return payloads

    _append_progress(
        progress_log_path,
        phase="structured_bootstrap_v1",
        event="global_normalization_batch_abandoned",
        batch_index=batch_index,
        chapter_ids=batch_chapter_ids,
        subdivision_depth=subdivision_depth,
        error=last_error,
    )
    return []


def _run_chapter_extraction(
    *,
    work_title: str,
    language: str,
    chapter_id: str,
    sequence_index: int,
    chapter_title: str,
    chapter_text: str,
    canonical_entity_map: list[dict[str, Any]],
    config: NovelBootstrapV1Config,
    resolved_model_plan: ResolvedModelPlan | None = None,
    telemetry_path: Path | None = None,
    request_trace_path: Path | None = None,
) -> dict[str, Any] | None:
    provider = get_text_provider(config.chapter_task_name, config.provider_name)
    draft_prompt = _build_chapter_extraction_prompt(
        work_title=work_title,
        language=language,
        chapter_id=chapter_id,
        sequence_index=sequence_index,
        chapter_title=chapter_title,
        chapter_text=chapter_text,
        canonical_entity_map=canonical_entity_map,
    )
    chapter_complexity = classify_chapter_complexity(
        title=chapter_title,
        text=chapter_text,
        input_tokens=_estimate_token_count(chapter_text),
    )
    chapter_model = _resolve_structured_model(
        config,
        phase="chapter_extraction",
        input_tokens=_estimate_token_count(draft_prompt),
        complexity_bucket=chapter_complexity,
        resolved_model_plan=resolved_model_plan,
    )
    prompt = draft_prompt
    chapter_budget = _build_chapter_token_budget(config=config, resolved_model_plan=resolved_model_plan)
    input_tokens, token_method = _count_prompt_input_tokens(
        prompt=prompt,
        provider_name=config.provider_name,
        model=chapter_model,
        timeout_seconds=config.timeout_seconds,
    )
    if not fits_within_budget(input_tokens=input_tokens, budget=chapter_budget):
        return _run_chapter_extraction_chunked(
            provider=provider,
            work_title=work_title,
            language=language,
            chapter_id=chapter_id,
            sequence_index=sequence_index,
            chapter_title=chapter_title,
            chapter_text=chapter_text,
            canonical_entity_map=canonical_entity_map,
            config=config,
            budget=chapter_budget,
            resolved_model_plan=resolved_model_plan,
            telemetry_path=telemetry_path,
            request_trace_path=request_trace_path,
        )
    if request_trace_path is not None:
        _write_json_trace(
            request_trace_path,
            {
                "provider": config.provider_name,
                "task": config.chapter_task_name,
                "endpoint": _chapter_endpoint_for_provider(config.provider_name),
                "headers": _redacted_openai_headers(),
                "payload": {
                    "model": chapter_model,
                    "messages": [
                        {"role": "system", "content": "Return only valid JSON for one chapter extraction."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": config.temperature,
                    "max_tokens": config.chapter_max_tokens,
                    "response_format": {"type": "json_object"},
                    "input_tokens": input_tokens,
                    "input_token_method": token_method,
                },
            },
        )
    try:
        started_at = time.perf_counter()
        response = provider.generate(
            TextGenerationRequest(
                task=config.chapter_task_name,
                provider_name=config.provider_name,
                model=chapter_model,
                system="Return only valid JSON for one chapter extraction.",
                messages=[TextMessage(role="user", content=prompt)],
                max_tokens=config.chapter_max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
                response_format={"type": "json_object"},
            )
        )
    except TextProviderError:
        if telemetry_path is not None:
            append_empirical_record(
                telemetry_path,
                make_empirical_record(
                    provider_name=str(config.provider_name or ""),
                    phase="chapter_extraction",
                    complexity_bucket=chapter_complexity,
                    model=chapter_model,
                    success=False,
                    json_valid=False,
                    latency_seconds=0.0,
                    estimated_total_cost=input_tokens + config.chapter_max_tokens,
                    stalled=True,
                ),
            )
        return None
    payload = extract_json_payload(response.text)
    if not isinstance(payload, dict):
        if telemetry_path is not None:
            append_empirical_record(
                telemetry_path,
                make_empirical_record(
                    provider_name=str(config.provider_name or ""),
                    phase="chapter_extraction",
                    complexity_bucket=chapter_complexity,
                    model=chapter_model,
                    success=False,
                    json_valid=False,
                    latency_seconds=time.perf_counter() - started_at,
                    estimated_total_cost=input_tokens + config.chapter_max_tokens,
                ),
            )
        return None
    if telemetry_path is not None:
        append_empirical_record(
            telemetry_path,
            make_empirical_record(
                provider_name=str(config.provider_name or ""),
                phase="chapter_extraction",
                complexity_bucket=chapter_complexity,
                model=chapter_model,
                success=True,
                json_valid=True,
                latency_seconds=time.perf_counter() - started_at,
                estimated_total_cost=input_tokens + config.chapter_max_tokens,
            ),
        )
    return payload


def _build_chapter_extraction_prompt(
    *,
    work_title: str,
    language: str,
    chapter_id: str,
    sequence_index: int,
    chapter_title: str,
    chapter_text: str,
    canonical_entity_map: list[dict[str, Any]],
) -> str:
    title_entity_hints = _extract_title_entity_hints(chapter_title)
    return (
        f"{CHAPTER_EXTRACTION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        f"CHAPTER_ID: {chapter_id}\n"
        f"SEQUENCE_INDEX: {sequence_index}\n"
        f"CHAPTER_TITLE: {chapter_title}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
        f"CANONICAL_ENTITY_MAP:\n{json.dumps(canonical_entity_map, ensure_ascii=False)}\n\n"
        f"CHAPTER_TEXT:\n{chapter_text}"
    )


def _count_prompt_input_tokens(
    *,
    prompt: str,
    provider_name: str | None,
    model: str,
    timeout_seconds: int,
) -> tuple[int, str]:
    if provider_name == "openai":
        counted = _count_openai_input_tokens_for_prompt(
            model=model,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
        if counted is not None:
            return counted, "openai_responses_input_tokens"
    return _estimate_token_count(prompt), "estimated_chars_div_4"


def _run_chapter_extraction_chunked(
    *,
    provider,
    work_title: str,
    language: str,
    chapter_id: str,
    sequence_index: int,
    chapter_title: str,
    chapter_text: str,
    canonical_entity_map: list[dict[str, Any]],
    config: NovelBootstrapV1Config,
    budget: TokenBudget,
    resolved_model_plan: ResolvedModelPlan | None,
    telemetry_path: Path | None,
    request_trace_path: Path | None,
) -> dict[str, Any] | None:
    partial_budget = max(1000, budget.usable_input_budget - 4000)
    subchunks = split_markdown_semantically(
        chapter_text=chapter_text,
        max_chunk_tokens=partial_budget,
        estimate_tokens=_estimate_token_count,
        overlap_paragraphs=config.chapter_chunk_overlap_paragraphs,
    )
    title_entity_hints = _extract_title_entity_hints(chapter_title)
    partial_payloads: list[dict[str, Any]] = []
    for chunk_index, chunk_text in enumerate(subchunks, start=1):
        partial_model = _resolve_structured_model(
            config,
            phase="chapter_partial_extraction",
            input_tokens=_estimate_token_count(chunk_text),
            complexity_bucket="large_or_complex",
            resolved_model_plan=resolved_model_plan,
        )
        prompt = (
            f"{CHAPTER_PARTIAL_EXTRACTION_PROMPT}\n\n"
            f"WORK_TITLE: {work_title}\n"
            f"LANGUAGE: {language}\n\n"
            f"CHAPTER_ID: {chapter_id}\n"
            f"CHUNK_ID: {chapter_id}_part_{chunk_index:02d}\n"
            f"CHAPTER_TITLE: {chapter_title}\n\n"
            f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
            f"CANONICAL_ENTITY_MAP:\n{json.dumps(canonical_entity_map, ensure_ascii=False)}\n\n"
            f"CHUNK_TEXT:\n{chunk_text}"
        )
        try:
            partial_started_at = time.perf_counter()
            response = provider.generate(
                TextGenerationRequest(
                    task=config.chapter_task_name,
                    provider_name=config.provider_name,
                    model=partial_model,
                    system="Return only valid JSON for one chapter subchunk extraction.",
                    messages=[TextMessage(role="user", content=prompt)],
                    max_tokens=config.chapter_max_tokens,
                    temperature=config.temperature,
                    timeout_seconds=config.timeout_seconds,
                    retries=config.retries,
                    response_format={"type": "json_object"},
                )
            )
        except TextProviderError:
            if telemetry_path is not None:
                append_empirical_record(
                    telemetry_path,
                    make_empirical_record(
                        provider_name=str(config.provider_name or ""),
                        phase="chapter_partial_extraction",
                        complexity_bucket="large_or_complex",
                        model=partial_model,
                        success=False,
                        json_valid=False,
                        latency_seconds=0.0,
                        estimated_total_cost=_estimate_token_count(prompt) + config.chapter_max_tokens,
                        stalled=True,
                    ),
                )
            return None
        payload = extract_json_payload(response.text)
        if not isinstance(payload, dict):
            if telemetry_path is not None:
                append_empirical_record(
                    telemetry_path,
                    make_empirical_record(
                        provider_name=str(config.provider_name or ""),
                        phase="chapter_partial_extraction",
                        complexity_bucket="large_or_complex",
                        model=partial_model,
                        success=False,
                        json_valid=False,
                        latency_seconds=time.perf_counter() - partial_started_at,
                        estimated_total_cost=_estimate_token_count(prompt) + config.chapter_max_tokens,
                    ),
                )
            return None
        if telemetry_path is not None:
            append_empirical_record(
                telemetry_path,
                make_empirical_record(
                    provider_name=str(config.provider_name or ""),
                    phase="chapter_partial_extraction",
                    complexity_bucket="large_or_complex",
                    model=partial_model,
                    success=True,
                    json_valid=True,
                    latency_seconds=time.perf_counter() - partial_started_at,
                    estimated_total_cost=_estimate_token_count(prompt) + config.chapter_max_tokens,
                    subdivided=True,
                ),
            )
        partial_payloads.append(payload)

    reduction_prompt = (
        f"{CHAPTER_REDUCTION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        f"CHAPTER_ID: {chapter_id}\n"
        f"SEQUENCE_INDEX: {sequence_index}\n"
        f"CHAPTER_TITLE: {chapter_title}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
        f"CANONICAL_ENTITY_MAP:\n{json.dumps(canonical_entity_map, ensure_ascii=False)}\n\n"
        f"PARTIAL_SIGNALS:\n{json.dumps(partial_payloads, ensure_ascii=False)}"
    )
    reduction_model = _resolve_structured_model(
        config,
        phase="chapter_reduction",
        input_tokens=_estimate_token_count(reduction_prompt),
        complexity_bucket="large_or_complex",
        resolved_model_plan=resolved_model_plan,
    )
    if request_trace_path is not None:
        _write_json_trace(
            request_trace_path,
            {
                "provider": config.provider_name,
                "task": config.chapter_task_name,
                "endpoint": _chapter_endpoint_for_provider(config.provider_name),
                "headers": _redacted_openai_headers(),
                "payload": {
                    "mode": "chapter_reduction",
                    "model": reduction_model,
                    "subchunk_count": len(subchunks),
                    "messages": [
                        {"role": "system", "content": "Return only valid JSON for chapter reduction."},
                        {"role": "user", "content": reduction_prompt},
                    ],
                    "temperature": config.temperature,
                    "max_tokens": config.chapter_reduce_max_tokens,
                    "response_format": {"type": "json_object"},
                },
            },
        )
    try:
        reduction_started_at = time.perf_counter()
        response = provider.generate(
            TextGenerationRequest(
                task=config.chapter_task_name,
                provider_name=config.provider_name,
                model=reduction_model,
                system="Return only valid JSON for chapter reduction.",
                messages=[TextMessage(role="user", content=reduction_prompt)],
                max_tokens=config.chapter_reduce_max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
                response_format={"type": "json_object"},
            )
        )
    except TextProviderError:
        if telemetry_path is not None:
            append_empirical_record(
                telemetry_path,
                make_empirical_record(
                    provider_name=str(config.provider_name or ""),
                    phase="chapter_reduction",
                    complexity_bucket="large_or_complex",
                    model=reduction_model,
                    success=False,
                    json_valid=False,
                    latency_seconds=0.0,
                    estimated_total_cost=_estimate_token_count(reduction_prompt) + config.chapter_reduce_max_tokens,
                    stalled=True,
                    subdivided=True,
                ),
            )
        return None
    payload = extract_json_payload(response.text)
    if not isinstance(payload, dict):
        if telemetry_path is not None:
            append_empirical_record(
                telemetry_path,
                make_empirical_record(
                    provider_name=str(config.provider_name or ""),
                    phase="chapter_reduction",
                    complexity_bucket="large_or_complex",
                    model=reduction_model,
                    success=False,
                    json_valid=False,
                    latency_seconds=time.perf_counter() - reduction_started_at,
                    estimated_total_cost=_estimate_token_count(reduction_prompt) + config.chapter_reduce_max_tokens,
                    subdivided=True,
                ),
            )
        return None
    if telemetry_path is not None:
        append_empirical_record(
            telemetry_path,
            make_empirical_record(
                provider_name=str(config.provider_name or ""),
                phase="chapter_reduction",
                complexity_bucket="large_or_complex",
                model=reduction_model,
                success=True,
                json_valid=True,
                latency_seconds=time.perf_counter() - reduction_started_at,
                estimated_total_cost=_estimate_token_count(reduction_prompt) + config.chapter_reduce_max_tokens,
                subdivided=True,
            ),
        )
    return payload


def _extract_title_entity_hints(chapter_title: str) -> list[str]:
    cleaned = re.sub(r"\[[^\]]+\]\([^)]+\)", "", str(chapter_title or ""))
    cleaned = cleaned.replace("*", " ").replace("·", " ")
    blocked = {
        "episodio",
        "episode",
        "capitulo",
        "capítulo",
        "chapter",
        "parte",
        "part",
        "prologo",
        "prólogo",
        "prologue",
        "interludio",
        "interlude",
    }
    tokens = [token.strip(" .,:;!?()[]{}\"'") for token in cleaned.split()]
    candidates = [
        token
        for token in tokens
        if token
        and len(token) > 2
        and any(char.isalpha() for char in token)
        and token[0].isupper()
        and not token.isupper()
        and not any(char.isdigit() for char in token)
        and token.casefold() not in blocked
    ]
    if not candidates:
        return []
    last = candidates[-1]
    if len(candidates) >= 2 and candidates[-2].lower() in {"de", "del", "of"}:
        return [f"{candidates[-2]} {last}", last]
    return [last]


def _select_primary_novel_document(inventory: SourceDocumentInventory, source_texts: dict[str, str]):
    candidates = []
    for doc in inventory.documents:
        if doc.extension != "md":
            continue
        text = source_texts.get(doc.source_id, "")
        chapters = detect_story_chapters(doc, text)
        candidates.append((len(chapters), len(text), doc))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _resolve_structured_model(
    config: NovelBootstrapV1Config,
    *,
    phase: str,
    input_tokens: int | None = None,
    complexity_bucket: str | None = None,
    resolved_model_plan: ResolvedModelPlan | None = None,
) -> str:
    requested = str(config.model or "").strip()
    provider = str(config.provider_name or "").strip().casefold()
    if requested and requested.casefold() != "auto":
        return requested
    if resolved_model_plan is not None:
        if phase == "global_normalization":
            return resolved_model_plan.global_normalization_default_model
        if phase == "chapter_extraction":
            if complexity_bucket == "large_or_complex":
                return resolved_model_plan.chapter_extraction_large_chapter_model
            if complexity_bucket == "medium_complex":
                return resolved_model_plan.chapter_extraction_high_complexity_model
            return resolved_model_plan.chapter_extraction_default_model
        if phase == "chapter_partial_extraction":
            return resolved_model_plan.chapter_partial_extraction_default_model
        if phase == "chapter_reduction":
            return resolved_model_plan.chapter_reduction_default_model
        if phase == "entity_cleanup":
            return resolved_model_plan.entity_cleanup_default_model
        return resolved_model_plan.safe_default_model
    if provider == "openai":
        token_count = max(int(input_tokens or 0), 0)
        if phase == "global_normalization":
            return "gpt-4.1-mini"
        if phase in {"chapter_extraction", "chapter_partial_extraction", "chapter_reduction"}:
            return "gpt-4o-mini" if token_count <= 90000 else "gpt-4.1-mini"
        return "gpt-4.1-mini"
    if provider == "lmstudio":
        return "qwen/qwen3.5-9b"
    return requested or "gpt-4.1-mini"


def _normalize_global_payload(
    payload: dict[str, Any] | None,
    *,
    work_title: str,
    language: str,
    batch_note: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    work = payload.get("work")
    if not isinstance(work, dict):
        work = {}
    entities = payload.get("entities")
    merge_plan = payload.get("merge_plan")
    normalization_notes = [
        str(item).strip()
        for item in (work.get("normalization_notes") or payload.get("normalization_notes") or [])
        if str(item).strip()
    ]
    if batch_note:
        normalization_notes.append(batch_note)
    normalized = {
        "work": {
            "title": str(work.get("title") or work_title).strip() or work_title,
            "language": str(work.get("language") or language).strip() or language,
            "normalization_notes": unique_preserve_order(normalization_notes),
        },
        "entities": entities if isinstance(entities, list) else [],
        "merge_plan": merge_plan if isinstance(merge_plan, list) else [],
    }
    return normalized


def _normalize_chapter_payload(
    payload: dict[str, Any],
    *,
    chapter_id: str,
    sequence_index: int,
    chapter_title: str,
    chapter_text: str,
    work_title: str,
    language: str,
) -> dict[str, Any]:
    work = payload.get("work")
    if not isinstance(work, dict):
        work = {}
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        chapters = [{}]
    chapter = chapters[0]
    if not isinstance(chapter, dict):
        chapter = {}
    chapter["chapter_id"] = str(chapter.get("chapter_id") or chapter_id).strip() or chapter_id
    chapter["chapter_title_original"] = str(chapter.get("chapter_title_original") or chapter_title).strip() or chapter_title
    chapter["chapter_title_canonical"] = str(chapter.get("chapter_title_canonical") or chapter["chapter_title_original"]).strip() or chapter["chapter_title_original"]
    chapter["sequence_index"] = int(chapter.get("sequence_index") or sequence_index)
    chapter["chapter_summary"] = str(chapter.get("chapter_summary") or "").strip()
    chapter["chapter_text_markdown"] = str(chapter.get("chapter_text_markdown") or chapter_text).strip()
    for key in ("characters", "places", "concepts", "events", "relations", "unresolved_mentions"):
        if not isinstance(chapter.get(key), list):
            chapter[key] = []
    return {
        "work": {
            "title": str(work.get("title") or work_title).strip() or work_title,
            "language": str(work.get("language") or language).strip() or language,
        },
        "chapters": [chapter],
    }


def _append_progress(path: str | None, **payload: Any) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _run_global_normalization_openai_file_input(
    *,
    work_title: str,
    language: str,
    source_path: Path,
    config: NovelBootstrapV1Config,
    request_trace_dir: Path | None = None,
) -> dict[str, Any] | None:
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    api_base = os.environ.get("AUTONOVEL_OPENAI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        return None

    prompt = (
        f"{GLOBAL_NORMALIZATION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        "FULL_TEXT:\n"
        "Use the attached novel document as the full source of truth. "
        "The chapter IDs to emit must be stable sequential IDs like ch_001, ch_002, etc."
    )
    if config.max_chapters:
        prompt += (
            f"\n\nVALIDATION FOCUS:\n"
            f"This run will only extract and import chapters ch_001 to ch_{config.max_chapters:03d}. "
            f"Use the full attached novel to normalize identities globally, but prioritize entities, facts, and merges "
            f"that are materially relevant to chapters ch_001 to ch_{config.max_chapters:03d}. "
            "You may omit later-only entities if they do not help these chapters."
        )
    response_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    mime_type = mimetypes.guess_type(source_path.name)[0] or "text/markdown"
    file_data = f"data:{mime_type};base64," + base64.b64encode(source_path.read_bytes()).decode("ascii")

    payload = {
        "model": config.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": source_path.name,
                        "file_data": file_data,
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
        "max_output_tokens": config.global_max_tokens,
    }
    if request_trace_dir is not None:
        _write_json_trace(
            request_trace_dir / "global_normalization_response_request.json",
            {
                "provider": "openai",
                "endpoint": f"{api_base}/responses",
                "headers": _redacted_openai_headers(),
                "source_path": str(source_path),
                "mime_type": mime_type,
                "payload": payload,
            },
        )

    raw: dict[str, Any] | None = None
    response_meta: dict[str, Any] | None = None
    for attempt in range(1, config.retries + 2):
        try:
            resp = httpx.post(
                f"{api_base}/responses",
                headers=response_headers,
                json=payload,
                timeout=config.timeout_seconds,
            )
            resp.raise_for_status()
            raw = resp.json()
            response_meta = {
                "status_code": resp.status_code,
                "request_id": resp.headers.get("x-request-id"),
                "rate_limit_remaining_requests": resp.headers.get("x-ratelimit-remaining-requests"),
                "rate_limit_remaining_tokens": resp.headers.get("x-ratelimit-remaining-tokens"),
            }
            break
        except Exception as exc:  # pragma: no cover - network failure path
            last_error = exc
            if attempt >= config.retries + 1:
                return None
            time.sleep(min(2 ** (attempt - 1), 8) + random.uniform(0.0, 0.35))
    if raw is None:
        return None
    if request_trace_dir is not None:
        _write_json_trace(
            request_trace_dir / "global_normalization_response_response.json",
            {
                "meta": response_meta,
                "raw": raw,
            },
        )
    text = _extract_responses_text(raw)
    payload = extract_json_payload(text)
    return _normalize_global_payload(payload, work_title=work_title, language=language)


def _count_openai_input_tokens_for_prompt(
    *,
    model: str,
    prompt: str,
    timeout_seconds: int,
) -> int | None:
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    api_base = os.environ.get("AUTONOVEL_OPENAI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key or not model:
        return None
    payload = {
        "model": model,
        "instructions": "Return only valid JSON for global novel normalization.",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
    }
    try:
        response = httpx.post(
            f"{api_base}/responses/input_tokens",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        raw = response.json()
    except Exception:
        return None
    input_tokens = raw.get("input_tokens")
    if isinstance(input_tokens, int) and input_tokens >= 0:
        return input_tokens
    return None


def _extract_responses_text(raw: dict[str, Any]) -> str:
    output_text = raw.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    parts: list[str] = []
    for item in raw.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts).strip()


def _redacted_openai_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer ***REDACTED***",
        "Content-Type": "application/json",
    }


def _chapter_endpoint_for_provider(provider_name: str | None) -> str:
    if provider_name == "openai":
        return f"{os.environ.get('AUTONOVEL_OPENAI_API_BASE_URL', 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
    return "provider_managed"


def _write_json_trace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
