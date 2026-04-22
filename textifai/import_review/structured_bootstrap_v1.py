from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap import SourceDocumentInventory
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.chapterizer import detect_story_chapters


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
"chapter_text_markdown": "...",
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
FINAL SELF-CHECK
================

Before output:

* remove trivial facts
* remove redundant facts already present in canon unless updated here
* ensure canonical names match the supplied entity map
* ensure valid JSON
"""


@dataclass(frozen=True)
class NovelBootstrapV1Config:
    provider_name: str | None
    model: str | None
    global_task_name: str = "bootstrap_global_normalization"
    chapter_task_name: str = "bootstrap_chapter_extraction"
    global_max_tokens: int = 9000
    chapter_max_tokens: int = 3000
    temperature: float = 0.0
    timeout_seconds: int = 600
    retries: int = 1
    max_global_text_chars: int = 350000
    max_chapters: int | None = None


@dataclass(frozen=True)
class NovelBootstrapV1Result:
    source_document: str
    chapter_count: int
    global_normalization_path: str
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

    warnings: list[str] = []

    global_payload = _run_global_normalization(
        work_title=work_title,
        language=language,
        chapters=chapters,
        source_text=source_text,
        config=config,
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


def _run_global_normalization(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    source_text: str,
    config: NovelBootstrapV1Config,
) -> dict[str, Any] | None:
    provider = get_text_provider(config.global_task_name, config.provider_name)
    chapter_text = "\n\n".join(f"[ch_{index:03d}] {chapter.title}\n{chapter.text}" for index, chapter in enumerate(chapters, start=1))
    full_text = chapter_text
    if len(full_text) > config.max_global_text_chars:
        full_text = full_text[: config.max_global_text_chars]
    prompt = (
        f"{GLOBAL_NORMALIZATION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        f"FULL_TEXT:\n{full_text}"
    )
    try:
        response = provider.generate(
            TextGenerationRequest(
                task=config.global_task_name,
                provider_name=config.provider_name,
                model=config.model,
                system="Return only valid JSON for global novel normalization.",
                messages=[TextMessage(role="user", content=prompt)],
                max_tokens=config.global_max_tokens,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
                retries=config.retries,
                response_format={"type": "json_object"},
            )
        )
    except TextProviderError:
        return None
    payload = extract_json_payload(response.text)
    return _normalize_global_payload(payload, work_title=work_title, language=language)


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
) -> dict[str, Any] | None:
    provider = get_text_provider(config.chapter_task_name, config.provider_name)
    prompt = (
        f"{CHAPTER_EXTRACTION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"LANGUAGE: {language}\n\n"
        f"CHAPTER_ID: {chapter_id}\n"
        f"SEQUENCE_INDEX: {sequence_index}\n"
        f"CHAPTER_TITLE: {chapter_title}\n\n"
        f"CANONICAL_ENTITY_MAP:\n{json.dumps(canonical_entity_map, ensure_ascii=False)}\n\n"
        f"CHAPTER_TEXT:\n{chapter_text}"
    )
    try:
        response = provider.generate(
            TextGenerationRequest(
                task=config.chapter_task_name,
                provider_name=config.provider_name,
                model=config.model,
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
        return None
    payload = extract_json_payload(response.text)
    if not isinstance(payload, dict):
        return None
    return payload


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


def _normalize_global_payload(payload: dict[str, Any] | None, *, work_title: str, language: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    work = payload.get("work")
    if not isinstance(work, dict):
        work = {}
    entities = payload.get("entities")
    merge_plan = payload.get("merge_plan")
    normalized = {
        "work": {
            "title": str(work.get("title") or work_title).strip() or work_title,
            "language": str(work.get("language") or language).strip() or language,
            "normalization_notes": [
                str(item).strip()
                for item in (work.get("normalization_notes") or payload.get("normalization_notes") or [])
                if str(item).strip()
            ],
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
