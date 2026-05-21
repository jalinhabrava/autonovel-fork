from __future__ import annotations

import json
import base64
import hashlib
import mimetypes
import os
import random
import re
import shutil
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage, TextProviderError, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.bootstrap.contracts import SourceDocumentInventory
from textifai.bootstrap.prose_language_validation import resolve_prose_language_validator
from textifai.bootstrap.source_reader import read_source_documents
from textifai.import_review.batch_planner import PlannedBatch, pack_items_by_budget, split_markdown_semantically
from textifai.import_review.bootstrap_profile import build_bootstrap_profile, classify_chapter_complexity
from textifai.import_review.entity_cleanup import cleanup_resolved_entities
from textifai.import_review.entity_cluster_resolution import (
    normalize_entity_key,
    normalize_entity_text,
    resolve_entity_clusters,
)
from textifai.import_review.entity_reconciliation import reconcile_entities_for_vaerl, reconcile_primary_relationship_mentions
from textifai.import_review.auxiliary_ingestion import AuxiliaryDocumentInput, ingest_auxiliary_documents
from textifai.import_review.empirical_ranker import EmpiricalPolicy, append_empirical_record, make_empirical_record
from textifai.import_review.model_advisor import maybe_advise_model_plan
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.model_router import ResolvedModelPlan, resolve_model_plan
from textifai.import_review.primary_note_synthesis import synthesize_primary_note_summaries
from textifai.import_review.provider_snapshot import build_provider_snapshot
from textifai.import_review.token_budget import TokenBudget, build_token_budget, fits_within_budget
from textifai.runtime_config import synchronize_runtime_environment
from textifai.vaerl.invariants import write_semantic_invariants_audit
from textifai.vaerl.review_queue import write_review_queue


CHAPTER_LABEL_TYPES = {"episode", "prologue", "epilogue", "interlude", "other"}


def _preferred_slug_for_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    normalized = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower().replace("’", "").replace("'", "")
    normalized = re.sub(r"[^\w\s-]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-\s]+", "_", normalized).strip("_")
    return normalized or "note"


def _validate_explanatory_language_texts(*, texts: list[str], language: str, context: str) -> list[str]:
    errors, _warnings = _validate_explanatory_language_with_policy(
        texts=texts,
        language=language,
        context=context,
        validator_name="heuristic",
        validation_mode="strict",
    )
    return errors


def _validate_explanatory_language_with_policy(
    *,
    texts: list[str],
    language: str,
    context: str,
    validator_name: str | None,
    validation_mode: str,
) -> tuple[list[str], list[str]]:
    validator = resolve_prose_language_validator(validator_name)
    mode = str(validation_mode or "strict").strip().casefold()
    if validator is None:
        message = (
            f"{context} language validation is unavailable "
            f"(expected={language}, validator={validator_name or 'none'})"
        )
        return ([message], []) if mode == "strict" else ([], [message])
    result = validator.validate_texts(
        texts=texts,
        expected_language=language,
        context=context,
    )
    if not result.available:
        messages = [item.message for item in result.messages] or [
            f"{context} language validation is unavailable (expected={language}, validator={result.validator_name})"
        ]
        return (messages, []) if mode == "strict" else ([], messages)
    errors = [item.message for item in result.messages if item.severity == "error"]
    warnings = [item.message for item in result.messages if item.severity != "error"]
    return errors, warnings


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
"canonical_candidate": "...",
"entity_kind": "...",
"entity_subkind": "...",
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
"review_state": "canonical",
"naming_quality": "proper_name",
"gender_presentation_signal": "unknown",
"is_stable_entity": true,
"needs_review": false,
"review_reason": ""
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
* faction
* concept
* object
* creature
* event

Do not use magic or lore as primary entity_kind values.
If the source describes magic, mana systems, rituals, metaphysical rules, or similar systems,
represent them as concept entities with an appropriate entity_subkind such as system, phenomenon, ritual, law, role, title, or doctrine.

If the source describes historical background, named disasters, wars, or foundational changes,
represent them as event entities when they deserve standalone notes.

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
NAMING QUALITY RULES
====================

Each entity must classify naming_quality as one of:

* proper_name
* title_plus_name
* descriptor
* pronoun_like
* unknown

Use proper_name when the work provides a stable explicit personal or place name.
Use title_plus_name when the work repeatedly uses a titled form with a stable name.
Use descriptor when the label is contextual or descriptive rather than a true stable name.
Use pronoun_like for pronouns or speaker placeholders.
Use unknown only when the naming status is genuinely unclear.

canonical_candidate should be the strongest current candidate for later cross-chapter resolution.
is_stable_entity should be true only when the entity appears durable enough to track across the work.
needs_review should be true when naming or identity remains uncertain.
review_reason should briefly explain the uncertainty in WORK_LANGUAGE when needs_review is true.

gender_presentation_signal is optional and must be one of masculine, feminine, unknown, or mixed.
Use it only when aliases or narrative context provide clear evidence. Do not infer it from a proper name alone.
If evidence is weak, return unknown. This is a soft merge/alias signal, not a hard identity rule.

==================================================
WORK LANGUAGE RULES
===================

The working language for all generated prose fields is: WORK_LANGUAGE.

Generate all summaries, key facts, relationship facts, chapter summaries, normalization notes, and explanatory prose in WORK_LANGUAGE.

This includes:

* summaries
* key_facts
* relationship facts
* reasons
* normalization notes

Keep proper names, aliases, chapter IDs, source mentions, and canonical names in the forms supported by the work.
Do not translate proper names or canonical names.
Do not mix explanatory prose from multiple languages unless the source text itself quotes a foreign-language expression that matters narratively.

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
"chapter_label_type": "episode",
"chapter_number_in_label": null,
"title_parse_signals": {
"has_explicit_number": true,
"explicit_number_value": 1,
"has_colon": true,
"has_em_dash": false,
"primary_separator": ":",
"prefix_segment": "...",
"suffix_segment": "..."
},
"chapter_summary": "...",
"characters": [
{
"surface": "...",
"canonical": "...",
"canonical_candidate": "...",
"entity_subkind": "...",
"naming_quality": "proper_name",
"gender_presentation_signal": "unknown",
"needs_review": false,
"facts": ["..."],
"confidence": 0.0
}
],
"places": [
{
"surface": "...",
"canonical": "...",
"canonical_candidate": "...",
"entity_subkind": "...",
"naming_quality": "proper_name",
"gender_presentation_signal": "unknown",
"needs_review": false,
"facts": ["..."],
"confidence": 0.0
}
],
"concepts": [
{
"surface": "...",
"canonical": "...",
"canonical_candidate": "...",
"entity_subkind": "...",
"naming_quality": "proper_name",
"gender_presentation_signal": "unknown",
"needs_review": false,
"facts": ["..."],
"confidence": 0.0
}
],
"events": [
{
"surface": "...",
"canonical": "...",
"canonical_candidate": "...",
"entity_subkind": "...",
"naming_quality": "proper_name",
"gender_presentation_signal": "unknown",
"needs_review": false,
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

Each extracted item must set canonical_candidate to the strongest local candidate for later entity resolution.
Each extracted item should set entity_subkind when a stable subtype is evident.

Each extracted item must classify naming_quality as one of:

* proper_name
* title_plus_name
* descriptor
* pronoun_like
* unknown

Set needs_review = true when the mention remains semantically important but the identity is still uncertain.

Each extracted item may set gender_presentation_signal to one of:

* masculine
* feminine
* unknown
* mixed

Use this only when the chapter provides clear narrative evidence through context, aliases, or co-occurrence. Do not infer from a proper name alone. If evidence is weak or absent, use unknown. This signal is a soft merge/alias feature, not an identity rule.

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
WORK LANGUAGE RULES
===================

The working language for all generated prose fields is: WORK_LANGUAGE.

Generate all summaries, key facts, relationship facts, chapter summaries, normalization notes, and explanatory prose in WORK_LANGUAGE.

This includes:

* chapter_summary
* facts
* relation facts
* unresolved mention facts

Keep names and source surfaces in the forms supported by the work.
Do not mix explanatory prose from multiple languages unless the source itself requires a quoted expression.
Do not translate chapter titles, character names, place names, faction names, object names, or canonical names.
chapter_title_original must be copied exactly from CHAPTER_TITLE.
chapter_title_canonical must preserve the source language and should only remove markup, links, unsafe filesystem characters, or obvious formatting noise.
chapter_title_canonical must not translate the title.
surface must preserve the exact source-language mention when possible.
canonical and canonical_candidate must use the source-language name or the supplied canonical entity map.
Do not invent English equivalents.

==================================================
TITLE STRUCTURE SIGNALS
=======================

You are given title_parse_signals extracted deterministically from the chapter title.

Use these signals to help classify the chapter, but do not reinterpret or modify them.

The structural title parser supports ":" and "—" as title separators. If both appear, ":" is the primary separator.

* Do not translate the title.
* Do not normalize the title.
* Do not invent structure that is not present.

CHAPTER LABEL RULES
===================

Determine chapter_label_type using both chapter_title_original and title_parse_signals:

* If the title clearly represents a prologue, return "prologue"
* If it clearly represents an epilogue, return "epilogue"
* If it clearly represents an interlude, return "interlude"
* If it clearly represents a numbered chapter/episode unit, return "episode"
* Otherwise return "other"

Determine chapter_number_in_label:

* Use explicit_number_value if it clearly corresponds to the main chapter numbering
* Return null if the number is absent or belongs to a secondary structure (e.g., "Part 2" inside a subtitle)
* Do not derive numbers from sequence_index
* Do not infer or invent numbers

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

The working language for all generated prose fields is: WORK_LANGUAGE.
Generate all summaries, key facts, relationship facts, chapter summaries, normalization notes, and explanatory prose in WORK_LANGUAGE.
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
"chapter_label_type": "episode",
"chapter_number_in_label": null,
"title_parse_signals": {
"has_explicit_number": true,
"explicit_number_value": 1,
"has_colon": true,
"has_em_dash": false,
"primary_separator": ":",
"prefix_segment": "...",
"suffix_segment": "..."
},
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

The working language for all generated prose fields is: WORK_LANGUAGE.
Generate all summaries, key facts, relationship facts, chapter summaries, normalization notes, and explanatory prose in WORK_LANGUAGE.
Do not merge different named entities unless the combined partial signals strongly confirm the identity.
If uncertainty remains, keep the explicit surface as canonical and leave the ambiguity in unresolved_mentions.
Use the canonical entity map when there is a safe match.
Use TITLE_ENTITY_HINTS as a guardrail when the chapter title explicitly names a focal entity.
Preserve chapter_title_original and chapter_title_canonical in the source language.
Do not translate chapter titles, character names, place names, faction names, object names, or canonical names.

==================================================
CHAPTER LABEL RULES
===================

Extract structural information from the chapter title without altering it.

* sequence_index must represent the order of appearance in the source text only.
* Do not reinterpret, renumber, or normalize sequence_index based on the narrative title.
* chapter_label_type must be one of: episode, prologue, epilogue, interlude, other.
* chapter_number_in_label must be an integer or null.
* title_parse_signals must be copied from the deterministic TITLE_PARSE_SIGNALS input.
* title_parse_signals may use ":" or "—" as a structural title separator; if both appear, ":" is primary.
* return the explicit narrative number present in the original main title label if it exists.
* return null if no explicit number exists.
* do not infer, invent, translate, or normalize numbers.
* do not derive chapter_number_in_label from sequence_index.
* only use numbers attached to the main label type; do not use secondary subtitle numbers such as "Parte 2" in an interlude title.
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
    chapter_extraction_retries: int = 2
    chapter_extraction_retry_backoff_seconds: float = 2.0
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
    selective_global_min_chapters: int = 3
    selective_global_max_chapters: int = 10
    selective_global_dense_token_threshold: int = 1200
    prose_language_validator: str | None = "heuristic"
    prose_language_validation_mode: str = "strict"


@dataclass(frozen=True)
class NovelBootstrapV1Result:
    source_document: str
    chapter_count: int
    novel_index_path: str
    global_normalization_pass1_path: str
    global_normalization_pass2_path: str
    ambiguous_entity_queue_path: str
    selective_normalization_trace_path: str
    selective_normalization_metrics_path: str
    global_normalization_path: str
    global_batch_audit_path: str
    model_plan_audit_path: str
    canonical_entity_map_path: str
    chapter_extraction_audit_path: str
    chapter_outputs_dir: str
    chapters_enriched_path: str
    resolved_entities_path: str
    entity_clusters_audit_path: str
    entity_resolution_audit_path: str
    gender_signal_audit_path: str
    semantic_context_probe_audit_path: str
    semantic_context_probe_trace_path: str
    cleaned_entities_path: str
    entity_cleanup_audit_path: str
    promotion_decisions_audit_path: str
    pre_vaerl_reconciliation_audit_path: str
    primary_note_synthesis_audit_path: str
    obsidian_import_path: str
    playbook_boundary_audit_path: str
    llm_call_ledger_path: str
    run_limits_audit_path: str
    run_comparability_manifest_path: str
    semantic_invariants_audit_path: str
    review_queue_path: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticReplayResult:
    input_system_root: str
    output_root: str
    global_normalization_path: str
    chapter_outputs_dir: str
    resolved_entities_path: str
    entity_clusters_audit_path: str
    entity_resolution_audit_path: str
    gender_signal_audit_path: str
    semantic_context_probe_audit_path: str
    semantic_context_probe_trace_path: str
    cleaned_entities_path: str
    entity_cleanup_audit_path: str
    promotion_decisions_audit_path: str
    pre_vaerl_reconciliation_audit_path: str
    auxiliary_source_index_path: str | None
    auxiliary_chunks_dir: str | None
    auxiliary_extractions_dir: str | None
    auxiliary_enrichment_audit_path: str | None
    primary_note_synthesis_audit_path: str
    obsidian_import_path: str
    replay_audit_path: str
    run_limits_audit_path: str
    run_comparability_manifest_path: str
    semantic_invariants_audit_path: str
    review_queue_path: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterExtractionAttemptResult:
    payload: dict[str, Any] | None
    attempt_count: int
    failure_type: str | None = None
    failure_reason: str | None = None
    exception_type: str | None = None
    response_excerpt: str | None = None
    response_sha256: str | None = None
    json_valid: bool = False
    schema_valid: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.payload is not None and self.failure_type is None and self.json_valid and self.schema_valid


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

    run_id = vault_root.name or f"structured_bootstrap_v1_{int(time.time())}"
    selective_normalization_trace_path = system_root / "selective_normalization_trace.jsonl"
    selective_normalization_trace_path.write_text("", encoding="utf-8")
    llm_call_ledger_path = system_root / "llm_call_ledger.jsonl"
    llm_call_ledger_path.write_text("", encoding="utf-8")

    novel_index = build_novel_index(
        work_title=work_title,
        language=language,
        chapters=chapters,
        source_path=Path(source_doc.path),
    )
    novel_index_path = system_root / "novel_index.json"
    novel_index_path.write_text(json.dumps(novel_index, ensure_ascii=False, indent=2), encoding="utf-8")

    _append_selective_trace(
        selective_normalization_trace_path,
        run_id=run_id,
        event_type="planner_started",
        reason="metadata_first_planning",
        metadata={"chapter_count_total": len(novel_index.get("chapters") or [])},
    )
    global_normalization_pass1 = build_global_normalization_pass1(
        novel_index=novel_index,
        config=config,
    )
    _append_pass1_trace_events(
        selective_normalization_trace_path,
        run_id=run_id,
        pass1_payload=global_normalization_pass1,
    )
    global_normalization_pass1_path = system_root / "global_normalization_pass1.json"
    global_normalization_pass1_path.write_text(
        json.dumps(global_normalization_pass1, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ambiguous_entity_queue = build_ambiguous_entity_queue(global_normalization_pass1)
    _append_ambiguous_queue_trace_events(
        selective_normalization_trace_path,
        run_id=run_id,
        ambiguity_queue=ambiguous_entity_queue,
    )
    ambiguous_entity_queue_path = system_root / "ambiguous_entity_queue.json"
    ambiguous_entity_queue_path.write_text(json.dumps(ambiguous_entity_queue, ensure_ascii=False, indent=2), encoding="utf-8")

    global_batch_audit_path = system_root / "global_batch_plan_audit.json"
    global_payload = _run_global_normalization(
        work_title=work_title,
        language=language,
        chapters=chapters,
        source_text=source_text,
        source_path=Path(source_doc.path),
        novel_index=novel_index,
        pass1_payload=global_normalization_pass1,
        ambiguity_queue=ambiguous_entity_queue,
        config=config,
        request_trace_dir=request_trace_dir,
        audit_path=global_batch_audit_path,
        progress_log_path=progress_log_path,
        resolved_model_plan=resolved_model_plan,
        telemetry_path=telemetry_path,
        trace_path=selective_normalization_trace_path,
        llm_call_ledger_path=llm_call_ledger_path,
        run_id=run_id,
    )
    if global_payload is None:
        return None
    global_normalization_pass2 = _build_global_normalization_pass2_artifact(global_payload)
    global_normalization_pass2_path = system_root / "global_normalization_pass2.json"
    global_normalization_pass2_path.write_text(json.dumps(global_normalization_pass2, ensure_ascii=False, indent=2), encoding="utf-8")
    selective_normalization_metrics = build_selective_normalization_metrics(
        run_status=None,
        novel_index=novel_index,
        pass1_payload=global_normalization_pass1,
        ambiguity_queue=ambiguous_entity_queue,
        pass2_payload=global_normalization_pass2,
        global_payload=global_payload,
    )
    selective_normalization_metrics_path = system_root / "selective_normalization_metrics.json"
    selective_normalization_metrics_path.write_text(
        json.dumps(selective_normalization_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _append_selective_trace(
        selective_normalization_trace_path,
        run_id=run_id,
        event_type="selective_normalization_finished",
        reason="selective_normalization_metrics_persisted",
        metadata={
            "metrics_path": str(selective_normalization_metrics_path),
            "selected_chapters_that_contributed_changes": selective_normalization_metrics.get("selected_chapters_that_contributed_changes"),
            "selected_chapters_with_no_observable_changes": selective_normalization_metrics.get("selected_chapters_with_no_observable_changes"),
        },
    )
    global_normalization_path = system_root / "global_normalization.json"
    global_normalization_path.write_text(json.dumps(global_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    canonical_entity_map = build_canonical_entity_map(global_payload)
    canonical_entity_map_path = system_root / "canonical_entity_map.json"
    canonical_entity_map_path.write_text(json.dumps(canonical_entity_map, ensure_ascii=False, indent=2), encoding="utf-8")

    chapter_outputs: list[dict[str, Any]] = []
    expected_chapters: list[dict[str, Any]] = []
    generated_chapters: list[dict[str, Any]] = []
    failed_chapters: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        chapter_id = f"ch_{index:03d}"
        expected_chapters.append(
            {
                "chapter_id": chapter_id,
                "sequence_index": index,
                "chapter_title": chapter.title,
            }
        )
        _append_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="chapter_extraction_started",
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            sequence_index=index,
        )
        chapter_result = _run_chapter_extraction(
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
            llm_call_ledger_path=llm_call_ledger_path,
            request_trace_path=(
                request_trace_dir / f"{chapter_id}_request.json"
                if index <= max(0, config.request_trace_sample_chapters)
                else None
            ),
        )
        if not chapter_result.ok or chapter_result.payload is None:
            warnings.append(f"chapter_extraction_failed:{chapter.title}")
            failed_chapters.append(
                {
                    "chapter_id": chapter_id,
                    "sequence_index": index,
                    "chapter_title": chapter.title,
                    "attempt_count": chapter_result.attempt_count,
                    "failure_type": chapter_result.failure_type,
                    "failure_reason": chapter_result.failure_reason,
                    "exception_type": chapter_result.exception_type,
                    "response_excerpt": chapter_result.response_excerpt,
                    "response_sha256": chapter_result.response_sha256,
                    "json_valid": chapter_result.json_valid,
                    "schema_valid": chapter_result.schema_valid,
                    "warnings": chapter_result.warnings,
                }
            )
            _append_progress(
                progress_log_path,
                phase="structured_bootstrap_v1",
                event="chapter_extraction_failed",
                chapter_id=chapter_id,
                chapter_title=chapter.title,
                attempt_count=chapter_result.attempt_count,
                failure_type=chapter_result.failure_type,
            )
            continue
        chapter_payload = chapter_result.payload
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
        generated_chapters.append(
            {
                "chapter_id": chapter_id,
                "sequence_index": index,
                "chapter_title": chapter.title,
                "attempt_count": chapter_result.attempt_count,
                "warnings": chapter_result.warnings,
            }
        )
        (chapter_outputs_dir / f"{chapter_id}.json").write_text(json.dumps(chapter_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _append_progress(
            progress_log_path,
            phase="structured_bootstrap_v1",
            event="chapter_extraction_completed",
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            attempt_count=chapter_result.attempt_count,
        )

    run_status = _build_run_status(
        expected_chapter_count=len(expected_chapters),
        generated_chapter_count=len(generated_chapters),
        failed_chapter_count=len(failed_chapters),
    )
    selective_normalization_metrics = _with_run_status(selective_normalization_metrics, run_status)
    selective_normalization_metrics_path.write_text(
        json.dumps(selective_normalization_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    chapter_extraction_audit = _build_chapter_extraction_audit(
        run_status=run_status,
        expected_chapters=expected_chapters,
        generated_chapters=generated_chapters,
        failed_chapters=failed_chapters,
    )
    chapter_extraction_audit_path = system_root / "chapter_extraction_audit.json"
    chapter_extraction_audit_path.write_text(json.dumps(chapter_extraction_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    chapters_enriched = {
        "run_status": run_status,
        "work": global_payload.get("work") or {"title": work_title, "language": language},
        "chapters": [item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
    }
    chapters_enriched_path = system_root / "chapters_enriched.json"
    chapters_enriched_path.write_text(json.dumps(chapters_enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    resolved_entities, entity_clusters_audit, entity_resolution_audit = resolve_entity_clusters(
        global_data=global_payload,
        chapter_outputs=[item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
        language=language,
    )
    resolution_language_errors, resolution_language_warnings = _validate_downstream_entity_explanations_language(
        entities=resolved_entities,
        language=language,
        context="entity_resolution",
        validator_name=config.prose_language_validator,
        validation_mode=config.prose_language_validation_mode,
    )
    if resolution_language_errors:
        raise ValueError("; ".join(resolution_language_errors))
    resolved_entities_path = system_root / "resolved_entities.json"
    resolved_entities_path.write_text(json.dumps(resolved_entities, ensure_ascii=False, indent=2), encoding="utf-8")
    entity_clusters_audit_path = system_root / "entity_clusters_audit.json"
    entity_clusters_audit_path.write_text(json.dumps(_with_run_status(entity_clusters_audit, run_status), ensure_ascii=False, indent=2), encoding="utf-8")
    entity_resolution_audit_path = system_root / "entity_resolution_audit.json"
    entity_resolution_audit_payload = _with_run_status(entity_resolution_audit, run_status)
    if resolution_language_warnings:
        entity_resolution_audit_payload["language_validation_warnings"] = resolution_language_warnings
    entity_resolution_audit_path.write_text(json.dumps(entity_resolution_audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cleaned_entities, entity_cleanup_audit, promotion_decisions_audit = cleanup_resolved_entities(
        entities=resolved_entities,
        chapter_outputs=[item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
        language=language,
    )
    cleaned_entities, pre_vaerl_reconciliation_audit = reconcile_entities_for_vaerl(
        entities=cleaned_entities,
        language=language,
    )
    cleaned_entities, primary_note_synthesis_audit = synthesize_primary_note_summaries(
        entities=cleaned_entities,
        language=language,
    )
    cleanup_language_errors, cleanup_language_warnings = _validate_downstream_entity_explanations_language(
        entities=cleaned_entities,
        language=language,
        context="entity_cleanup",
        validator_name=config.prose_language_validator,
        validation_mode=config.prose_language_validation_mode,
    )
    if cleanup_language_errors:
        raise ValueError("; ".join(cleanup_language_errors))
    cleaned_entities_path = system_root / "cleaned_entities.json"
    cleaned_entities_path.write_text(json.dumps(cleaned_entities, ensure_ascii=False, indent=2), encoding="utf-8")
    entity_cleanup_audit_path = system_root / "entity_cleanup_audit.json"
    entity_cleanup_audit_payload = _with_run_status(entity_cleanup_audit, run_status)
    if cleanup_language_warnings:
        entity_cleanup_audit_payload["language_validation_warnings"] = cleanup_language_warnings
    entity_cleanup_audit_path.write_text(json.dumps(entity_cleanup_audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    promotion_decisions_audit_path = system_root / "promotion_decisions_audit.json"
    promotion_decisions_audit_path.write_text(json.dumps(_with_run_status(promotion_decisions_audit, run_status), ensure_ascii=False, indent=2), encoding="utf-8")
    pre_vaerl_reconciliation_audit_path = system_root / "pre_vaerl_reconciliation_audit.json"
    pre_vaerl_reconciliation_audit_path.write_text(
        json.dumps(_with_run_status(pre_vaerl_reconciliation_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    primary_note_synthesis_audit_path = system_root / "primary_note_synthesis_audit.json"
    primary_note_synthesis_audit_path.write_text(
        json.dumps(_with_run_status(primary_note_synthesis_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gender_signal_audit_path = system_root / "gender_signal_audit.json"
    gender_signal_audit_path.write_text(
        json.dumps(
            _with_run_status(
                _build_gender_signal_audit(
                    resolved_entities=resolved_entities,
                    cleaned_entities=cleaned_entities,
                ),
                run_status,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    semantic_context_probe_audit_path, semantic_context_probe_trace_path = _write_semantic_context_probe_artifacts(
        system_root=system_root,
        cleaned_entities=cleaned_entities,
        chapter_outputs=[item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
        run_status=run_status,
    )

    obsidian_import = assemble_obsidian_import(
        global_data={**global_payload, "entities": cleaned_entities},
        chapter_outputs=[item["chapters"][0] for item in chapter_outputs if item.get("chapters")],
    )
    obsidian_import["entities"], obsidian_relationship_reconciliation_audit = reconcile_primary_relationship_mentions(
        entities=obsidian_import.get("entities", []) or []
    )
    obsidian_relationship_reconciliation_audit_path = system_root / "obsidian_relationship_reconciliation_audit.json"
    obsidian_relationship_reconciliation_audit_path.write_text(
        json.dumps(_with_run_status(obsidian_relationship_reconciliation_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    obsidian_language_errors, obsidian_language_warnings = _validate_downstream_entity_explanations_language(
        entities=obsidian_import.get("entities", []) or [],
        language=language,
        context="obsidian_import",
        validator_name=config.prose_language_validator,
        validation_mode=config.prose_language_validation_mode,
    )
    if obsidian_language_errors:
        raise ValueError("; ".join(obsidian_language_errors))
    obsidian_import = _with_run_status(obsidian_import, run_status)
    if obsidian_language_warnings:
        obsidian_import["language_validation_warnings"] = obsidian_language_warnings
    obsidian_import_path = system_root / "obsidian_import.json"
    obsidian_import_path.write_text(json.dumps(obsidian_import, ensure_ascii=False, indent=2), encoding="utf-8")
    (system_root / "e2e_artifact_contract.json").write_text(
        json.dumps(
            _build_runtime_e2e_artifact_contract(
                system_root=system_root,
                chapter_outputs_dir=chapter_outputs_dir,
                run_status=run_status,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    playbook_boundary_audit_path = system_root / "playbook_boundary_audit.json"
    playbook_boundary_audit_path.write_text(
        json.dumps(
            _build_playbook_boundary_audit(
                system_root=system_root,
                chapter_outputs_dir=chapter_outputs_dir,
                run_status=run_status,
                chapter_extraction_audit=chapter_extraction_audit,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    run_limits_audit_path = system_root / "run_limits_audit.json"
    run_limits_audit_path.write_text(
        json.dumps(_build_run_limits_audit(run_status=run_status, config=config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    run_comparability_manifest_path = system_root / "run_comparability_manifest.json"
    run_comparability_manifest_path.write_text(
        json.dumps(
            _build_run_comparability_manifest(
                system_root=system_root,
                chapter_outputs_dir=chapter_outputs_dir,
                run_status=run_status,
                pipeline_mode="full_semantic_ingestion",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    semantic_invariants_audit_path = system_root / "semantic_invariants_audit.json"
    semantic_invariants_audit = write_semantic_invariants_audit(
        output_path=semantic_invariants_audit_path,
        system_root=system_root,
        obsidian_import_path=obsidian_import_path,
        language=language,
    )
    review_queue_path = system_root / "review_queue.json"
    write_review_queue(
        output_path=review_queue_path,
        obsidian_import=obsidian_import,
        semantic_invariants_audit=semantic_invariants_audit,
        retention_context={
            "promotion_decisions": promotion_decisions_audit.get("decisions") or [],
            "resolved_entities": resolved_entities,
            "cleaned_entities": cleaned_entities,
            "global_entities": global_payload.get("entities") or [],
        },
    )

    return NovelBootstrapV1Result(
        source_document=source_doc.path,
        chapter_count=len(chapters),
        novel_index_path=str(novel_index_path),
        global_normalization_pass1_path=str(global_normalization_pass1_path),
        global_normalization_pass2_path=str(global_normalization_pass2_path),
        ambiguous_entity_queue_path=str(ambiguous_entity_queue_path),
        selective_normalization_trace_path=str(selective_normalization_trace_path),
        selective_normalization_metrics_path=str(selective_normalization_metrics_path),
        global_normalization_path=str(global_normalization_path),
        global_batch_audit_path=str(global_batch_audit_path),
        model_plan_audit_path=str(model_plan_audit_path),
        canonical_entity_map_path=str(canonical_entity_map_path),
        chapter_extraction_audit_path=str(chapter_extraction_audit_path),
        chapter_outputs_dir=str(chapter_outputs_dir),
        chapters_enriched_path=str(chapters_enriched_path),
        resolved_entities_path=str(resolved_entities_path),
        entity_clusters_audit_path=str(entity_clusters_audit_path),
        entity_resolution_audit_path=str(entity_resolution_audit_path),
        gender_signal_audit_path=str(gender_signal_audit_path),
        semantic_context_probe_audit_path=str(semantic_context_probe_audit_path),
        semantic_context_probe_trace_path=str(semantic_context_probe_trace_path),
        cleaned_entities_path=str(cleaned_entities_path),
        entity_cleanup_audit_path=str(entity_cleanup_audit_path),
        promotion_decisions_audit_path=str(promotion_decisions_audit_path),
        pre_vaerl_reconciliation_audit_path=str(pre_vaerl_reconciliation_audit_path),
        primary_note_synthesis_audit_path=str(primary_note_synthesis_audit_path),
        obsidian_import_path=str(obsidian_import_path),
        playbook_boundary_audit_path=str(playbook_boundary_audit_path),
        llm_call_ledger_path=str(llm_call_ledger_path),
        run_limits_audit_path=str(run_limits_audit_path),
        run_comparability_manifest_path=str(run_comparability_manifest_path),
        semantic_invariants_audit_path=str(semantic_invariants_audit_path),
        review_queue_path=str(review_queue_path),
        warnings=warnings,
    )


def run_semantic_ingestion_replay(
    *,
    input_system_root: str | Path,
    output_root: str | Path,
    language: str | None = None,
    prose_language_validator: str | None = "heuristic",
    prose_language_validation_mode: str = "strict",
    auxiliary_documents: list[AuxiliaryDocumentInput] | None = None,
    auxiliary_provider_name: str | None = None,
    auxiliary_model: str | None = None,
) -> SemanticReplayResult:
    """Replay deterministic semantic compilation from frozen extraction artifacts."""
    synchronize_runtime_environment(Path(__file__).resolve().parents[2])
    input_system = Path(input_system_root)
    output = Path(output_root)
    system_root = output / "99_System"
    chapter_outputs_dir = system_root / "chapter_outputs"
    system_root.mkdir(parents=True, exist_ok=True)
    chapter_outputs_dir.mkdir(parents=True, exist_ok=True)

    source_global_path = input_system / "global_normalization.json"
    source_chapter_outputs_dir = input_system / "chapter_outputs"
    source_chapter_audit_path = input_system / "chapter_extraction_audit.json"
    if not source_global_path.exists():
        raise FileNotFoundError(f"Missing frozen global_normalization.json: {source_global_path}")
    if not source_chapter_outputs_dir.exists():
        raise FileNotFoundError(f"Missing frozen chapter_outputs directory: {source_chapter_outputs_dir}")

    global_payload = json.loads(source_global_path.read_text(encoding="utf-8"))
    chapter_output_payloads: list[dict[str, Any]] = []
    for path in sorted(source_chapter_outputs_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        chapter_output_payloads.append(payload)
        (chapter_outputs_dir / path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    chapter_outputs = [item["chapters"][0] for item in chapter_output_payloads if item.get("chapters")]
    detected_language = str(language or (global_payload.get("work") or {}).get("language") or "unknown")
    if source_chapter_audit_path.exists():
        chapter_audit = json.loads(source_chapter_audit_path.read_text(encoding="utf-8"))
        shutil.copy2(source_chapter_audit_path, system_root / "chapter_extraction_audit.json")
        run_status = chapter_audit.get("run_status") or _build_run_status(
            expected_chapter_count=len(chapter_outputs),
            generated_chapter_count=len(chapter_outputs),
            failed_chapter_count=0,
        )
    else:
        run_status = _build_run_status(
            expected_chapter_count=len(chapter_outputs),
            generated_chapter_count=len(chapter_outputs),
            failed_chapter_count=0,
        )
        (system_root / "chapter_extraction_audit.json").write_text(
            json.dumps({"run_status": run_status}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    global_normalization_path = system_root / "global_normalization.json"
    global_normalization_path.write_text(json.dumps(global_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    resolved_entities, entity_clusters_audit, entity_resolution_audit = resolve_entity_clusters(
        global_data=global_payload,
        chapter_outputs=chapter_outputs,
        language=detected_language,
    )
    resolution_language_errors, resolution_language_warnings = _validate_downstream_entity_explanations_language(
        entities=resolved_entities,
        language=detected_language,
        context="entity_resolution_replay",
        validator_name=prose_language_validator,
        validation_mode=prose_language_validation_mode,
    )
    if resolution_language_errors:
        raise ValueError("; ".join(resolution_language_errors))
    resolved_entities_path = system_root / "resolved_entities.json"
    resolved_entities_path.write_text(json.dumps(resolved_entities, ensure_ascii=False, indent=2), encoding="utf-8")
    entity_clusters_audit_path = system_root / "entity_clusters_audit.json"
    entity_clusters_audit_path.write_text(json.dumps(_with_run_status(entity_clusters_audit, run_status), ensure_ascii=False, indent=2), encoding="utf-8")
    entity_resolution_audit_path = system_root / "entity_resolution_audit.json"
    entity_resolution_audit_payload = _with_run_status(entity_resolution_audit, run_status)
    if resolution_language_warnings:
        entity_resolution_audit_payload["language_validation_warnings"] = resolution_language_warnings
    entity_resolution_audit_path.write_text(json.dumps(entity_resolution_audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cleaned_entities, entity_cleanup_audit, promotion_decisions_audit = cleanup_resolved_entities(
        entities=resolved_entities,
        chapter_outputs=chapter_outputs,
        language=detected_language,
    )
    cleaned_entities, pre_vaerl_reconciliation_audit = reconcile_entities_for_vaerl(
        entities=cleaned_entities,
        language=detected_language,
    )
    auxiliary_source_index_path: Path | None = None
    auxiliary_chunks_dir: Path | None = None
    auxiliary_extractions_dir: Path | None = None
    auxiliary_enrichment_audit_path: Path | None = None
    auxiliary_audit: dict[str, Any] | None = None
    if auxiliary_documents:
        if get_text_provider_config_error("auxiliary_source_extraction", auxiliary_provider_name) is not None:
            raise RuntimeError(
                get_text_provider_config_error("auxiliary_source_extraction", auxiliary_provider_name)
                or "Auxiliary source extraction provider is not configured."
            )
        cleaned_entities, auxiliary_audit = ingest_auxiliary_documents(
            system_root=system_root,
            entities=cleaned_entities,
            auxiliary_documents=auxiliary_documents,
            language=detected_language,
            provider=get_text_provider("auxiliary_source_extraction", auxiliary_provider_name),
            provider_name=auxiliary_provider_name,
            model=auxiliary_model,
        )
        auxiliary_source_index_path = system_root / "auxiliary_source_index.json"
        auxiliary_chunks_dir = system_root / "auxiliary_chunks"
        auxiliary_extractions_dir = system_root / "auxiliary_extractions"
        auxiliary_enrichment_audit_path = system_root / "auxiliary_enrichment_audit.json"
    cleaned_entities, primary_note_synthesis_audit = synthesize_primary_note_summaries(
        entities=cleaned_entities,
        language=detected_language,
    )
    cleanup_language_errors, cleanup_language_warnings = _validate_downstream_entity_explanations_language(
        entities=cleaned_entities,
        language=detected_language,
        context="entity_cleanup_replay",
        validator_name=prose_language_validator,
        validation_mode=prose_language_validation_mode,
    )
    if cleanup_language_errors:
        raise ValueError("; ".join(cleanup_language_errors))
    cleaned_entities_path = system_root / "cleaned_entities.json"
    cleaned_entities_path.write_text(json.dumps(cleaned_entities, ensure_ascii=False, indent=2), encoding="utf-8")
    entity_cleanup_audit_path = system_root / "entity_cleanup_audit.json"
    entity_cleanup_audit_payload = _with_run_status(entity_cleanup_audit, run_status)
    if cleanup_language_warnings:
        entity_cleanup_audit_payload["language_validation_warnings"] = cleanup_language_warnings
    entity_cleanup_audit_path.write_text(json.dumps(entity_cleanup_audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    promotion_decisions_audit_path = system_root / "promotion_decisions_audit.json"
    promotion_decisions_audit_path.write_text(json.dumps(_with_run_status(promotion_decisions_audit, run_status), ensure_ascii=False, indent=2), encoding="utf-8")
    pre_vaerl_reconciliation_audit_path = system_root / "pre_vaerl_reconciliation_audit.json"
    pre_vaerl_reconciliation_audit_path.write_text(
        json.dumps(_with_run_status(pre_vaerl_reconciliation_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    primary_note_synthesis_audit_path = system_root / "primary_note_synthesis_audit.json"
    primary_note_synthesis_audit_path.write_text(
        json.dumps(_with_run_status(primary_note_synthesis_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    gender_signal_audit_path = system_root / "gender_signal_audit.json"
    gender_signal_audit_path.write_text(
        json.dumps(
            _with_run_status(
                _build_gender_signal_audit(
                    resolved_entities=resolved_entities,
                    cleaned_entities=cleaned_entities,
                ),
                run_status,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    semantic_context_probe_audit_path, semantic_context_probe_trace_path = _write_semantic_context_probe_artifacts(
        system_root=system_root,
        cleaned_entities=cleaned_entities,
        chapter_outputs=chapter_outputs,
        run_status=run_status,
    )

    obsidian_import = assemble_obsidian_import(
        global_data={**global_payload, "entities": cleaned_entities},
        chapter_outputs=chapter_outputs,
    )
    obsidian_import["entities"], obsidian_relationship_reconciliation_audit = reconcile_primary_relationship_mentions(
        entities=obsidian_import.get("entities", []) or []
    )
    obsidian_relationship_reconciliation_audit_path = system_root / "obsidian_relationship_reconciliation_audit.json"
    obsidian_relationship_reconciliation_audit_path.write_text(
        json.dumps(_with_run_status(obsidian_relationship_reconciliation_audit, run_status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    obsidian_language_errors, obsidian_language_warnings = _validate_downstream_entity_explanations_language(
        entities=obsidian_import.get("entities", []) or [],
        language=detected_language,
        context="obsidian_import_replay",
        validator_name=prose_language_validator,
        validation_mode=prose_language_validation_mode,
    )
    if obsidian_language_errors:
        raise ValueError("; ".join(obsidian_language_errors))
    obsidian_import = _with_run_status(obsidian_import, run_status)
    if obsidian_language_warnings:
        obsidian_import["language_validation_warnings"] = obsidian_language_warnings
    obsidian_import_path = system_root / "obsidian_import.json"
    obsidian_import_path.write_text(json.dumps(obsidian_import, ensure_ascii=False, indent=2), encoding="utf-8")

    replay_audit = {
        "schema_version": "textifai.semantic_replay.v1",
        "input_system_root": str(input_system),
        "output_root": str(output),
        "frozen_boundaries": ["global_normalization", "chapter_extraction"],
        "replayed_boundaries": ["entity_resolution", "entity_cleanup", "auxiliary_ingestion", "obsidian_import"]
        if auxiliary_documents
        else ["entity_resolution", "entity_cleanup", "obsidian_import"],
        "language": detected_language,
        "run_status": run_status,
        "auxiliary_ingestion": {
            "enabled": bool(auxiliary_documents),
            "document_count": len(auxiliary_documents or []),
            "source_index_path": str(auxiliary_source_index_path) if auxiliary_source_index_path else None,
            "chunks_dir": str(auxiliary_chunks_dir) if auxiliary_chunks_dir else None,
            "extractions_dir": str(auxiliary_extractions_dir) if auxiliary_extractions_dir else None,
            "enrichment_audit_path": str(auxiliary_enrichment_audit_path) if auxiliary_enrichment_audit_path else None,
            "created_entity_count": (auxiliary_audit or {}).get("created_entity_count"),
            "enriched_entity_count": (auxiliary_audit or {}).get("enriched_entity_count"),
            "planned_relationship_count": (auxiliary_audit or {}).get("planned_relationship_count"),
            "extraction_error_count": (auxiliary_audit or {}).get("extraction_error_count"),
        },
    }
    replay_audit_path = system_root / "semantic_replay_audit.json"
    replay_audit_path.write_text(json.dumps(replay_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    run_limits_audit_path = system_root / "run_limits_audit.json"
    run_limits_audit_path.write_text(
        json.dumps(_build_run_limits_audit(run_status=run_status, config=None, replay=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    run_comparability_manifest_path = system_root / "run_comparability_manifest.json"
    run_comparability_manifest_path.write_text(
        json.dumps(
            _build_run_comparability_manifest(
                system_root=system_root,
                chapter_outputs_dir=chapter_outputs_dir,
                run_status=run_status,
                pipeline_mode="downstream_replay",
                upstream_system_root=input_system,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    semantic_invariants_audit_path = system_root / "semantic_invariants_audit.json"
    semantic_invariants_audit = write_semantic_invariants_audit(
        output_path=semantic_invariants_audit_path,
        system_root=system_root,
        obsidian_import_path=obsidian_import_path,
        language=detected_language,
    )
    review_queue_path = system_root / "review_queue.json"
    write_review_queue(
        output_path=review_queue_path,
        obsidian_import=obsidian_import,
        semantic_invariants_audit=semantic_invariants_audit,
        retention_context={
            "promotion_decisions": promotion_decisions_audit.get("decisions") or [],
            "resolved_entities": resolved_entities,
            "cleaned_entities": cleaned_entities,
            "global_entities": global_payload.get("entities") or [],
        },
    )

    return SemanticReplayResult(
        input_system_root=str(input_system),
        output_root=str(output),
        global_normalization_path=str(global_normalization_path),
        chapter_outputs_dir=str(chapter_outputs_dir),
        resolved_entities_path=str(resolved_entities_path),
        entity_clusters_audit_path=str(entity_clusters_audit_path),
        entity_resolution_audit_path=str(entity_resolution_audit_path),
        gender_signal_audit_path=str(gender_signal_audit_path),
        semantic_context_probe_audit_path=str(semantic_context_probe_audit_path),
        semantic_context_probe_trace_path=str(semantic_context_probe_trace_path),
        cleaned_entities_path=str(cleaned_entities_path),
        entity_cleanup_audit_path=str(entity_cleanup_audit_path),
        promotion_decisions_audit_path=str(promotion_decisions_audit_path),
        pre_vaerl_reconciliation_audit_path=str(pre_vaerl_reconciliation_audit_path),
        auxiliary_source_index_path=str(auxiliary_source_index_path) if auxiliary_source_index_path else None,
        auxiliary_chunks_dir=str(auxiliary_chunks_dir) if auxiliary_chunks_dir else None,
        auxiliary_extractions_dir=str(auxiliary_extractions_dir) if auxiliary_extractions_dir else None,
        auxiliary_enrichment_audit_path=str(auxiliary_enrichment_audit_path) if auxiliary_enrichment_audit_path else None,
        primary_note_synthesis_audit_path=str(primary_note_synthesis_audit_path),
        obsidian_import_path=str(obsidian_import_path),
        replay_audit_path=str(replay_audit_path),
        run_limits_audit_path=str(run_limits_audit_path),
        run_comparability_manifest_path=str(run_comparability_manifest_path),
        semantic_invariants_audit_path=str(semantic_invariants_audit_path),
        review_queue_path=str(review_queue_path),
        warnings=[*resolution_language_warnings, *cleanup_language_warnings, *obsidian_language_warnings],
    )


def _build_run_status(
    *,
    expected_chapter_count: int,
    generated_chapter_count: int,
    failed_chapter_count: int,
) -> dict[str, Any]:
    complete = failed_chapter_count == 0 and generated_chapter_count == expected_chapter_count
    return {
        "semantic_integrity": "complete" if complete else "incomplete",
        "chapter_extraction_complete": complete,
        "expected_chapter_count": expected_chapter_count,
        "generated_chapter_count": generated_chapter_count,
        "failed_chapter_count": failed_chapter_count,
    }


def _with_run_status(payload: dict[str, Any], run_status: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "run_status": run_status}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_directory_json_files(path: Path) -> str:
    manifest: list[dict[str, str]] = []
    if path.exists():
        for item in sorted(path.glob("*.json")):
            manifest.append({"name": item.name, "sha256": _sha256_file(item)})
    return _sha256_json(manifest)


def _estimate_request_tokens(request: TextGenerationRequest) -> int:
    parts = [request.system or ""]
    parts.extend(str(message.content or "") for message in request.messages)
    return _estimate_token_count("\n".join(parts))


def _append_llm_call_ledger(
    ledger_path: Path,
    *,
    request: TextGenerationRequest,
    status: str,
    started_at: float,
    response_text: str | None = None,
    error: str | None = None,
    attempt: int = 1,
    phase: str | None = None,
) -> None:
    messages_payload = [{"role": message.role, "content": message.content} for message in request.messages]
    input_payload = {
        "system": request.system,
        "messages": messages_payload,
        "response_format": request.response_format,
    }
    record = {
        "call_id": f"llm_{uuid.uuid4().hex}",
        "phase": phase or request.task or "unknown",
        "task": request.task,
        "provider": request.provider_name,
        "model": request.model,
        "prompt_hash": _sha256_json(input_payload),
        "input_hash": _sha256_json(input_payload),
        "output_hash": _sha256_text(response_text or "") if response_text is not None else None,
        "attempt": attempt,
        "status": status,
        "error": error,
        "latency_seconds": round(time.perf_counter() - started_at, 4),
        "token_estimate": {
            "input": _estimate_request_tokens(request),
            "output": _estimate_token_count(response_text or "") if response_text is not None else 0,
        },
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class _LedgerTextProvider:
    def __init__(self, provider: Any, ledger_path: Path, *, phase: str | None = None):
        self._provider = provider
        self._ledger_path = ledger_path
        self._phase = phase

    def generate(self, request: TextGenerationRequest):
        started_at = time.perf_counter()
        try:
            response = self._provider.generate(request)
        except TextProviderError as exc:
            _append_llm_call_ledger(
                self._ledger_path,
                request=request,
                status="api_failure",
                started_at=started_at,
                error=str(exc),
                phase=self._phase,
            )
            raise
        _append_llm_call_ledger(
            self._ledger_path,
            request=request,
            status="success",
            started_at=started_at,
            response_text=response.text,
            phase=self._phase,
        )
        return response


def _build_run_limits_audit(
    *,
    run_status: dict[str, Any],
    config: NovelBootstrapV1Config | None = None,
    replay: bool = False,
) -> dict[str, Any]:
    phase_limits = {
        "global_normalization": {
            "max_failed_outputs": 0,
            "max_attempts": config.global_batch_failure_retry_threshold if config is not None else None,
        },
        "chapter_extraction": {
            "max_failed_chapters": 0,
            "max_retry_per_chapter": config.chapter_extraction_retries if config is not None else None,
        },
        "entity_resolution": {"max_schema_failures": 0},
        "entity_cleanup": {"max_schema_failures": 0},
        "obsidian_import": {"max_schema_failures": 0},
    }
    semantic_integrity = str(run_status.get("semantic_integrity") or "")
    failed_chapters = int(run_status.get("failed_chapter_count") or 0)
    comparable = semantic_integrity == "complete" and failed_chapters == 0
    return {
        "schema_version": "textifai.run_limits.v1",
        "run_status": run_status,
        "phase_limits": phase_limits,
        "artifact_status": "complete" if comparable else "partial",
        "valid_for": ["debugging", "semantic_quality_comparison"] if comparable else ["debugging"],
        "invalid_for": [] if comparable else ["semantic_quality_comparison"],
        "not_comparable_reason": None if comparable else "run_incomplete_or_failed_boundary",
        "replay": replay,
    }


def _build_run_comparability_manifest(
    *,
    system_root: Path,
    chapter_outputs_dir: Path,
    run_status: dict[str, Any],
    pipeline_mode: str,
    upstream_system_root: Path | None = None,
) -> dict[str, Any]:
    upstream_root = upstream_system_root or system_root
    global_path = upstream_root / "global_normalization.json"
    canonical_map_path = upstream_root / "canonical_entity_map.json"
    source_chapter_outputs = upstream_root / "chapter_outputs"
    upstream_hashes = {
        "global_normalization": _sha256_file(global_path) if global_path.exists() else None,
        "canonical_entity_map": _sha256_file(canonical_map_path) if canonical_map_path.exists() else None,
        "chapter_outputs": _sha256_directory_json_files(source_chapter_outputs if source_chapter_outputs.exists() else chapter_outputs_dir),
    }
    downstream_hashes = {
        "resolved_entities": _sha256_file(system_root / "resolved_entities.json") if (system_root / "resolved_entities.json").exists() else None,
        "cleaned_entities": _sha256_file(system_root / "cleaned_entities.json") if (system_root / "cleaned_entities.json").exists() else None,
        "obsidian_import": _sha256_file(system_root / "obsidian_import.json") if (system_root / "obsidian_import.json").exists() else None,
    }
    comparable = str(run_status.get("semantic_integrity") or "") == "complete" and int(run_status.get("failed_chapter_count") or 0) == 0
    return {
        "schema_version": "textifai.run_comparability.v1",
        "pipeline_mode": pipeline_mode,
        "run_status": run_status,
        "upstream_system_root": str(upstream_root),
        "upstream_hashes": upstream_hashes,
        "downstream_hashes": downstream_hashes,
        "pipeline_version": "structured_bootstrap_v1",
        "prompt_hashes": {
            "global_normalization": _sha256_text(GLOBAL_NORMALIZATION_PROMPT),
            "chapter_extraction": _sha256_text(CHAPTER_EXTRACTION_PROMPT),
            "chapter_partial_extraction": _sha256_text(CHAPTER_PARTIAL_EXTRACTION_PROMPT),
            "chapter_reduction": _sha256_text(CHAPTER_REDUCTION_PROMPT),
        },
        "comparable_for_semantic_quality": comparable,
        "not_comparable_reason": None if comparable else "run_incomplete_or_failed_boundary",
    }


def _build_gender_signal_audit(
    *,
    resolved_entities: list[dict[str, Any]],
    cleaned_entities: list[dict[str, Any]],
) -> dict[str, Any]:
    cleaned_index = {
        str(entity.get("canonical_name") or "").strip(): entity
        for entity in cleaned_entities
        if str(entity.get("canonical_name") or "").strip()
    }
    entities: list[dict[str, Any]] = []
    for entity in resolved_entities:
        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not canonical_name:
            continue
        cleaned = cleaned_index.get(canonical_name)
        entities.append(
            {
                "canonical_name": canonical_name,
                "entity_kind": str(entity.get("entity_kind") or ""),
                "review_state": str(entity.get("review_state") or ""),
                "cleanup_decision": str(cleaned.get("cleanup_decision") or "") if isinstance(cleaned, dict) else "",
                "gender_presentation_signal": str(entity.get("gender_presentation_signal") or "unknown"),
                "gender_signal_confidence": _normalize_optional_float(entity.get("gender_signal_confidence")),
                "gender_signal_conflict": bool(entity.get("gender_signal_conflict", False)),
                "gender_signal_downgraded": bool(entity.get("gender_signal_downgraded", False)),
                "gender_signal_evidence": _normalize_gender_signal_evidence(entity.get("gender_signal_evidence")),
            }
        )
    entities.sort(key=lambda item: (item["entity_kind"], item["canonical_name"].lower()))
    return {
        "schema_version": 1,
        "entity_count": len(entities),
        "entities": entities,
    }


def _semantic_probe_entity_id(entity: dict[str, Any]) -> str:
    return str(entity.get("preferred_slug") or entity.get("canonical_name") or "").strip()


def _semantic_probe_relationship_targets(entity: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    for relationship in entity.get("relationships") or []:
        if not isinstance(relationship, dict):
            continue
        target = normalize_entity_key(relationship.get("target") or "")
        if target:
            targets.add(target)
    return targets


def _semantic_probe_text_fields(entity: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    summary = str(entity.get("summary") or "").strip()
    if summary:
        fields.append(("summary", summary))
    for index, fact in enumerate(entity.get("key_facts") or []):
        text = str(fact or "").strip()
        if text:
            fields.append((f"key_facts[{index}]", text))
    return fields


def _semantic_probe_mentions_name(text: str, name: str) -> bool:
    normalized_name = normalize_entity_text(name)
    if len(normalized_name) < 3:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", str(text or ""), flags=re.IGNORECASE) is not None


def _build_semantic_context_probe(
    *,
    cleaned_entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
    run_status: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Inspect persisted semantic context without mutating the pipeline output."""
    trace: list[dict[str, Any]] = [
        {
            "event_type": "semantic_probe_started",
            "entity_id": "",
            "chapter_id": "",
            "reason": "inspect_persisted_semantic_context",
            "metadata": {
                "entity_count": len(cleaned_entities),
                "chapter_count": len(chapter_outputs),
            },
        }
    ]
    primary_by_id: dict[str, dict[str, Any]] = {}
    review_by_id: dict[str, dict[str, Any]] = {}
    for entity in cleaned_entities:
        entity_id = _semantic_probe_entity_id(entity) or f"{entity.get('entity_kind')}::{entity.get('canonical_name')}"
        note_role = str(entity.get("note_role") or "").casefold()
        review_state = str(entity.get("review_state") or "").casefold()
        if note_role:
            if note_role == "primary":
                primary_by_id.setdefault(entity_id, entity)
            elif note_role == "review":
                review_by_id.setdefault(entity_id, entity)
            continue
        if review_state == "canonical":
            primary_by_id.setdefault(entity_id, entity)
        elif review_state == "review":
            review_by_id.setdefault(entity_id, entity)
    primary_entities = list(primary_by_id.values())
    review_entities = list(review_by_id.values())
    primary_names = [
        normalize_entity_text(entity.get("canonical_name") or "")
        for entity in primary_entities
        if normalize_entity_text(entity.get("canonical_name") or "")
    ]
    primary_name_by_key = {normalize_entity_key(name): name for name in primary_names}
    title_hints_by_chapter = {
        str(chapter.get("chapter_id") or "").strip(): _extract_title_entity_hints(
            str(chapter.get("chapter_title_original") or chapter.get("chapter_title_canonical") or "")
        )
        for chapter in chapter_outputs
        if isinstance(chapter, dict) and str(chapter.get("chapter_id") or "").strip()
    }

    contamination_signals: list[dict[str, Any]] = []
    contamination_signal_keys: set[tuple[str, str, str, str]] = set()
    rejected_alias_source_mentions: list[dict[str, Any]] = []
    for entity in primary_entities:
        entity_id = _semantic_probe_entity_id(entity)
        canonical_name = normalize_entity_text(entity.get("canonical_name") or "")
        relationship_targets = _semantic_probe_relationship_targets(entity)
        trace.append(
            {
                "event_type": "semantic_probe_entity_loaded",
                "entity_id": entity_id,
                "chapter_id": "",
                "reason": "primary_context_slice",
                "metadata": {
                    "canonical_name": canonical_name,
                    "chapter_refs": entity.get("chapter_refs") or [],
                    "relationship_targets": sorted(relationship_targets),
                },
            }
        )
        rejected_keys = {
            normalize_entity_key(alias)
            for alias in (entity.get("rejected_aliases") or [])
            if normalize_entity_text(alias)
        }
        source_mention_keys = {
            normalize_entity_key(mention)
            for mention in (entity.get("source_mentions") or [])
            if normalize_entity_text(mention)
        }
        leaked_rejected = sorted(rejected_keys & source_mention_keys)
        if leaked_rejected:
            signal = {
                "entity_id": entity_id,
                "canonical_name": canonical_name,
                "rejected_aliases_still_present_in_source_mentions": [
                    primary_name_by_key.get(item, item) for item in leaked_rejected
                ],
                "severity": "warning",
                "reason": "rejected_alias_still_in_source_mentions",
            }
            rejected_alias_source_mentions.append(signal)
            trace.append(
                {
                    "event_type": "semantic_probe_contamination_signal",
                    "entity_id": entity_id,
                    "chapter_id": "",
                    "reason": "rejected_alias_still_in_source_mentions",
                    "metadata": signal,
                }
            )
        for other_name in primary_names:
            if normalize_entity_key(other_name) == normalize_entity_key(canonical_name):
                continue
            if normalize_entity_key(other_name) in relationship_targets:
                continue
            for field_name, text in _semantic_probe_text_fields(entity):
                if not _semantic_probe_mentions_name(text, other_name):
                    continue
                signal = {
                    "entity_id": entity_id,
                    "canonical_name": canonical_name,
                    "field": field_name,
                    "mentioned_primary": other_name,
                    "reason": "primary_name_mentioned_without_relationship",
                    "severity": "info",
                    "excerpt": text[:240],
                }
                signal_key = (entity_id, field_name, normalize_entity_key(other_name), signal["reason"])
                if signal_key in contamination_signal_keys:
                    continue
                contamination_signal_keys.add(signal_key)
                contamination_signals.append(signal)
                trace.append(
                    {
                        "event_type": "semantic_probe_contamination_signal",
                        "entity_id": entity_id,
                        "chapter_id": "",
                        "reason": "primary_name_mentioned_without_relationship",
                        "metadata": signal,
                    }
                )

    merge_candidates: list[dict[str, Any]] = []
    for entity in review_entities:
        if str(entity.get("entity_kind") or "") != "character":
            continue
        if str(entity.get("naming_quality") or "") != "pronoun_like":
            continue
        entity_id = _semantic_probe_entity_id(entity)
        chapter_refs = [str(ref).strip() for ref in (entity.get("chapter_refs") or []) if str(ref).strip()]
        hint_counts: dict[str, int] = {}
        supporting_chapters: dict[str, list[str]] = {}
        for chapter_ref in chapter_refs:
            hints = title_hints_by_chapter.get(chapter_ref, [])
            matched_primary_hints = [
                name
                for name in primary_names
                if any(normalize_entity_key(hint) == normalize_entity_key(name) for hint in hints)
            ]
            if len({normalize_entity_key(name) for name in matched_primary_hints}) != 1:
                continue
            name = matched_primary_hints[0]
            key = normalize_entity_key(name)
            hint_counts[key] = hint_counts.get(key, 0) + 1
            supporting_chapters.setdefault(key, []).append(chapter_ref)
        for key, count in sorted(hint_counts.items(), key=lambda item: (-item[1], item[0])):
            if count < 2:
                continue
            candidate = {
                "review_entity_id": entity_id,
                "review_canonical_name": normalize_entity_text(entity.get("canonical_name") or ""),
                "candidate_primary": primary_name_by_key.get(key, key),
                "reason": "pronoun_like_entity_repeatedly_appears_in_title_focused_chapters",
                "supporting_chapters": supporting_chapters.get(key, []),
                "confidence": "medium",
            }
            merge_candidates.append(candidate)
            trace.append(
                {
                    "event_type": "semantic_probe_merge_candidate",
                    "entity_id": entity_id,
                    "chapter_id": "",
                    "reason": candidate["reason"],
                    "metadata": candidate,
                }
            )

    audit = {
        "schema_version": "textifai.semantic_context_probe.v1",
        "run_status": run_status,
        "strategy": "external_context_selective_probe",
        "inspected_entity_count": len(cleaned_entities),
        "primary_count": len(primary_entities),
        "review_count": len(review_entities),
        "contamination_signal_count": len(contamination_signals) + len(rejected_alias_source_mentions),
        "merge_candidate_count": len(merge_candidates),
        "contamination_signals": contamination_signals,
        "rejected_alias_source_mentions": rejected_alias_source_mentions,
        "merge_candidates": merge_candidates,
        "notes": [
            "This probe is diagnostic only; it does not mutate cleaned_entities or obsidian_import.",
            "It treats persisted artifacts as external context and inspects selected slices instead of compacting the whole run.",
        ],
    }
    trace.append(
        {
            "event_type": "semantic_probe_finished",
            "entity_id": "",
            "chapter_id": "",
            "reason": "probe_complete",
            "metadata": {
                "contamination_signal_count": audit["contamination_signal_count"],
                "merge_candidate_count": audit["merge_candidate_count"],
            },
        }
    )
    return audit, trace


def _write_semantic_context_probe_artifacts(
    *,
    system_root: Path,
    cleaned_entities: list[dict[str, Any]],
    chapter_outputs: list[dict[str, Any]],
    run_status: dict[str, Any],
) -> tuple[Path, Path]:
    audit, trace = _build_semantic_context_probe(
        cleaned_entities=cleaned_entities,
        chapter_outputs=chapter_outputs,
        run_status=run_status,
    )
    audit_path = system_root / "semantic_context_probe_audit.json"
    trace_path = system_root / "semantic_context_probe_trace.jsonl"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    trace_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in trace) + "\n",
        encoding="utf-8",
    )
    return audit_path, trace_path


def _build_chapter_extraction_audit(
    *,
    run_status: dict[str, Any],
    expected_chapters: list[dict[str, Any]],
    generated_chapters: list[dict[str, Any]],
    failed_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_status": run_status,
        "expected_chapters": expected_chapters,
        "generated_chapters": generated_chapters,
        "failed_chapters": failed_chapters,
    }


def _build_playbook_boundary_audit(
    *,
    system_root: Path,
    chapter_outputs_dir: Path,
    run_status: dict[str, Any],
    chapter_extraction_audit: dict[str, Any],
) -> dict[str, Any]:
    chapter_output_paths = sorted(str(path) for path in chapter_outputs_dir.glob("*.json"))
    boundaries = {
        "global_normalization": {
            "artifact": "global_normalization.json",
            "path": str(system_root / "global_normalization.json"),
            "exists": (system_root / "global_normalization.json").exists(),
            "owner_if_first_failure": "prompt_extraction",
        },
        "chapter_extraction": {
            "artifact": "chapter_outputs/*.json",
            "path": str(chapter_outputs_dir),
            "exists": bool(chapter_output_paths),
            "artifact_count": len(chapter_output_paths),
            "artifacts": chapter_output_paths,
            "expected_chapter_count": run_status["expected_chapter_count"],
            "generated_chapter_count": run_status["generated_chapter_count"],
            "failed_chapter_count": run_status["failed_chapter_count"],
            "complete": run_status["chapter_extraction_complete"],
            "failed_chapters": chapter_extraction_audit["failed_chapters"],
            "owner_if_first_failure": "prompt_extraction",
        },
        "entity_resolution": {
            "artifact": "resolved_entities.json",
            "path": str(system_root / "resolved_entities.json"),
            "exists": (system_root / "resolved_entities.json").exists(),
            "owner_if_first_failure": "cluster_resolution",
        },
        "entity_cleanup": {
            "artifact": "cleaned_entities.json",
            "path": str(system_root / "cleaned_entities.json"),
            "exists": (system_root / "cleaned_entities.json").exists(),
            "owner_if_first_failure": "cleanup",
        },
        "obsidian_import": {
            "artifact": "obsidian_import.json",
            "path": str(system_root / "obsidian_import.json"),
            "exists": (system_root / "obsidian_import.json").exists(),
            "owner_if_first_failure": "assembly_importer_vaerl",
        },
    }
    return {
        "schema_version": 1,
        "scope": "semantic_ingestion_end_to_end_until_vaerl",
        "not_scope": "full_product_e2e_chat_utility_evaluation",
        "active_pipeline": "textifai_structured_bootstrap_v1",
        "artifact_root": str(system_root),
        "run_status": run_status,
        "rerun_policy": {
            "api_required_for_boundaries": ["global_normalization", "chapter_extraction"],
            "api_not_required_for_boundaries": ["entity_resolution", "entity_cleanup", "obsidian_import"],
            "notes": [
                "Prompt or schema changes require rerunning extraction artifacts.",
                "Resolution, cleanup, assembly, json import, scoring, tagging, and visualization should reuse frozen upstream artifacts.",
            ],
        },
        "boundaries": boundaries,
    }


def _build_runtime_e2e_artifact_contract(
    *,
    system_root: Path,
    chapter_outputs_dir: Path,
    run_status: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "semantic_ingestion_end_to_end_until_vaerl",
        "not_scope": "full_product_e2e_chat_utility_evaluation",
        "run_status": run_status,
        "artifact_root": str(system_root),
        "required_full_run_artifacts": {
            "source_extraction_audit": str(system_root / "source_extraction_audit.json"),
            "provider_snapshot": str(system_root / "provider_snapshot.json"),
            "model_plan_audit": str(system_root / "model_plan_audit.json"),
            "novel_index": str(system_root / "novel_index.json"),
            "global_normalization_pass1": str(system_root / "global_normalization_pass1.json"),
            "ambiguous_entity_queue": str(system_root / "ambiguous_entity_queue.json"),
            "global_normalization_pass2": str(system_root / "global_normalization_pass2.json"),
            "selective_normalization_trace": str(system_root / "selective_normalization_trace.jsonl"),
            "selective_normalization_metrics": str(system_root / "selective_normalization_metrics.json"),
            "global_batch_plan_audit": str(system_root / "global_batch_plan_audit.json"),
            "global_normalization": str(system_root / "global_normalization.json"),
            "canonical_entity_map": str(system_root / "canonical_entity_map.json"),
            "chapter_extraction_audit": str(system_root / "chapter_extraction_audit.json"),
            "chapter_outputs": str(chapter_outputs_dir),
            "chapters_enriched": str(system_root / "chapters_enriched.json"),
            "resolved_entities": str(system_root / "resolved_entities.json"),
            "entity_clusters_audit": str(system_root / "entity_clusters_audit.json"),
            "entity_resolution_audit": str(system_root / "entity_resolution_audit.json"),
            "cleaned_entities": str(system_root / "cleaned_entities.json"),
            "entity_cleanup_audit": str(system_root / "entity_cleanup_audit.json"),
            "promotion_decisions_audit": str(system_root / "promotion_decisions_audit.json"),
            "pre_vaerl_reconciliation_audit": str(system_root / "pre_vaerl_reconciliation_audit.json"),
            "primary_note_synthesis_audit": str(system_root / "primary_note_synthesis_audit.json"),
            "obsidian_import": str(system_root / "obsidian_import.json"),
            "playbook_boundary_audit": str(system_root / "playbook_boundary_audit.json"),
            "json_import_audit": str(system_root / "json_import_audit.json"),
            "bootstrap_progress": str(system_root / "bootstrap_progress.jsonl"),
        },
        "notes": [
            "global_normalization and chapter_extraction are extraction boundaries and generally require API reruns when prompt/schema changes.",
            "entity_resolution, entity_cleanup, and obsidian_import are downstream boundaries that should be reproducible from frozen upstream artifacts.",
        ],
    }


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
                "canonical_candidate": ent.get("canonical_candidate", ent.get("canonical_name", "")),
                "entity_subkind": ent.get("entity_subkind", ""),
                "naming_quality": ent.get("naming_quality", "unknown"),
                "needs_review": ent.get("needs_review", review_state != "canonical"),
            }
        )
    canonical_map.sort(key=lambda x: (str(x["entity_kind"]), str(x["canonical_name"]).lower()))
    return canonical_map


def build_novel_index(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    source_path: Path,
) -> dict[str, Any]:
    indexed_chapters: list[dict[str, Any]] = []
    for sequence_index, chapter in enumerate(chapters, start=1):
        chapter_id = f"ch_{sequence_index:03d}"
        title = str(getattr(chapter, "title", "") or "").strip()
        text = str(getattr(chapter, "text", "") or "")
        title_parse_signals = _extract_title_parse_signals(title)
        indexed_chapters.append(
            {
                "chapter_id": chapter_id,
                "sequence_index": sequence_index,
                "chapter_title_original": title,
                "chapter_title_canonical": title,
                "chapter_label_type": _deterministic_chapter_label_type(title_parse_signals),
                "chapter_number_in_label": title_parse_signals.get("explicit_number_value"),
                "title_parse_signals": title_parse_signals,
                "token_count_estimate": _estimate_token_count(text),
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_path": f"{source_path}#{chapter_id}",
            }
        )
    return {
        "schema_version": 1,
        "generation": {
            "method": "deterministic_metadata_index",
            "llm_required": False,
        },
        "work": {
            "title": work_title,
            "language": language,
        },
        "chapters": indexed_chapters,
    }


def _deterministic_chapter_label_type(title_parse_signals: dict[str, Any]) -> str:
    prefix = str(title_parse_signals.get("prefix_segment") or "")
    explicit_number = title_parse_signals.get("explicit_number_value")
    if isinstance(explicit_number, int) and str(explicit_number) in prefix:
        return "episode"
    return "other"


def build_global_normalization_pass1(
    *,
    novel_index: dict[str, Any],
    config: NovelBootstrapV1Config,
) -> dict[str, Any]:
    chapters = [chapter for chapter in novel_index.get("chapters", []) if isinstance(chapter, dict)]
    work = novel_index.get("work") if isinstance(novel_index.get("work"), dict) else {}
    language = str(work.get("language") or "unknown").strip() or "unknown"
    dense_chapters = _select_dense_chapters(chapters, config=config)
    high_narrative_chapters = _select_high_narrative_value_chapters(chapters, config=config)
    ambiguous_clusters = _detect_index_ambiguity_clusters(chapters)
    ambiguous_chapter_ids = unique_preserve_order(
        [
            chapter_id
            for cluster in ambiguous_clusters
            for chapter_id in (cluster.get("supporting_chapters") or [])
            if str(chapter_id).strip()
        ]
    )
    selected_chapter_ids = _select_chapters_for_global_expansion(
        chapters=chapters,
        dense_chapter_ids=[item["chapter_id"] for item in dense_chapters],
        high_narrative_chapter_ids=[item["chapter_id"] for item in high_narrative_chapters],
        ambiguous_chapter_ids=ambiguous_chapter_ids,
        config=config,
    )
    chapter_selection = _build_chapter_selection_rows(
        chapters=chapters,
        selected_chapter_ids=selected_chapter_ids,
        dense_chapters=dense_chapters,
        high_narrative_chapters=high_narrative_chapters,
        ambiguous_clusters=ambiguous_clusters,
    )
    return {
        "schema_version": 1,
        "strategy": "metadata_first_selective_expansion",
        "generation": {
            "method": "deterministic_index_planner",
            "llm_required": False,
        },
        "work": work,
        "chapter_count": len(chapters),
        "candidate_entities": [],
        "recurrent_entities": [],
        "dense_chapters": dense_chapters,
        "high_narrative_value_chapters": high_narrative_chapters,
        "ambiguous_clusters": ambiguous_clusters,
        "selected_chapter_ids": selected_chapter_ids,
        "rejected_chapter_ids": [
            row["chapter_id"]
            for row in chapter_selection
            if not row.get("selected")
        ],
        "chapter_selection": chapter_selection,
        "normalization_notes": [
            "planner:pass1_metadata_only",
            "planner:pass2_selective_expansion_available",
        ],
    }


def _build_chapter_selection_rows(
    *,
    chapters: list[dict[str, Any]],
    selected_chapter_ids: list[str],
    dense_chapters: list[dict[str, Any]],
    high_narrative_chapters: list[dict[str, Any]],
    ambiguous_clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = set(selected_chapter_ids)
    reason_map: dict[str, list[str]] = {}
    dense_ids = {str(item.get("chapter_id") or "") for item in dense_chapters}
    for chapter_id in dense_ids:
        if chapter_id:
            reason_map.setdefault(chapter_id, []).append("dense_named_entities")
    for item in high_narrative_chapters:
        chapter_id = str(item.get("chapter_id") or "").strip()
        if chapter_id:
            reason_map.setdefault(chapter_id, []).append("high_narrative_value")
    for cluster in ambiguous_clusters:
        reason = _cluster_selection_reason(cluster)
        for chapter_id in cluster.get("supporting_chapters") or []:
            chapter_id = str(chapter_id).strip()
            if chapter_id:
                reason_map.setdefault(chapter_id, []).append(reason)
    rows: list[dict[str, Any]] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        reasons = unique_preserve_order(reason_map.get(chapter_id, []))
        is_selected = chapter_id in selected
        if is_selected and not reasons:
            reasons = ["selected_for_manual_threshold"]
        if not is_selected:
            reasons = reasons or ["not_selected_low_signal"]
        rows.append(
            {
                "chapter_id": chapter_id,
                "sequence_index": chapter.get("sequence_index"),
                "selected": is_selected,
                "reasons": reasons,
                "token_count_estimate": chapter.get("token_count_estimate"),
            }
        )
    return rows


def _cluster_selection_reason(cluster: dict[str, Any]) -> str:
    cluster_id = str(cluster.get("cluster_id") or "")
    reason = str(cluster.get("reason") or "")
    if cluster_id == "unclear_title_structure":
        return "ambiguous_title_signals"
    if cluster_id.startswith("title_number_") or "number" in reason:
        return "reused_explicit_number"
    if cluster_id.startswith("title_prefix_") or "prefix" in reason:
        return "repeated_prefix_segment"
    return "ambiguous_title_signals"


def _select_dense_chapters(
    chapters: list[dict[str, Any]],
    *,
    config: NovelBootstrapV1Config,
) -> list[dict[str, Any]]:
    if not chapters:
        return []
    token_counts = [int(chapter.get("token_count_estimate") or 0) for chapter in chapters]
    sorted_counts = sorted(token_counts)
    median = sorted_counts[len(sorted_counts) // 2]
    threshold = max(config.selective_global_dense_token_threshold, int(median * 1.25))
    dense: list[dict[str, Any]] = []
    for chapter in chapters:
        token_count = int(chapter.get("token_count_estimate") or 0)
        if token_count < threshold:
            continue
        dense.append(
            {
                "chapter_id": chapter.get("chapter_id"),
                "sequence_index": chapter.get("sequence_index"),
                "token_count_estimate": token_count,
                "reason": "high_token_density",
            }
        )
    dense.sort(key=lambda item: (-int(item["token_count_estimate"]), int(item["sequence_index"] or 0)))
    return dense[: max(0, config.selective_global_max_chapters)]


def _select_high_narrative_value_chapters(
    chapters: list[dict[str, Any]],
    *,
    config: NovelBootstrapV1Config,
) -> list[dict[str, Any]]:
    if not chapters:
        return []
    token_counts = sorted(int(chapter.get("token_count_estimate") or 0) for chapter in chapters)
    median = token_counts[len(token_counts) // 2]
    late_start = max(1, int(len(chapters) * 0.85))
    selected: list[dict[str, Any]] = []
    for chapter in chapters:
        sequence_index = int(chapter.get("sequence_index") or 0)
        signals = chapter.get("title_parse_signals") if isinstance(chapter.get("title_parse_signals"), dict) else {}
        token_count = int(chapter.get("token_count_estimate") or 0)
        has_structural_signal = bool(signals.get("has_explicit_number") or signals.get("primary_separator"))
        late_and_structural = sequence_index >= late_start and has_structural_signal
        late_and_dense = sequence_index >= late_start - 1 and token_count >= median
        if not (late_and_structural or late_and_dense):
            continue
        selected.append(
            {
                "chapter_id": chapter.get("chapter_id"),
                "sequence_index": sequence_index,
                "token_count_estimate": token_count,
                "reason": "high_narrative_value",
            }
        )
    return selected[: max(0, config.selective_global_max_chapters)]


def _detect_index_ambiguity_clusters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    prefix_buckets: dict[str, dict[str, Any]] = {}
    number_buckets: dict[int, list[str]] = {}
    unclear_title_chapters: list[str] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "").strip()
        signals = chapter.get("title_parse_signals") if isinstance(chapter.get("title_parse_signals"), dict) else {}
        prefix = str(signals.get("prefix_segment") or "").strip()
        prefix_key = normalize_text(prefix)
        if chapter_id and prefix_key:
            bucket = prefix_buckets.setdefault(prefix_key, {"candidate_name": prefix, "chapter_ids": []})
            bucket["chapter_ids"].append(chapter_id)
        explicit_number = signals.get("explicit_number_value")
        if chapter_id and isinstance(explicit_number, int) and not isinstance(explicit_number, bool):
            number_buckets.setdefault(explicit_number, []).append(chapter_id)
        if chapter_id and not signals.get("primary_separator") and not signals.get("has_explicit_number"):
            unclear_title_chapters.append(chapter_id)

    for index, bucket in enumerate(prefix_buckets.values(), start=1):
        chapter_ids = unique_preserve_order(bucket["chapter_ids"])
        if len(chapter_ids) < 2:
            continue
        clusters.append(
            {
                "cluster_id": f"title_prefix_{index:03d}",
                "entity_kind": "unknown",
                "candidate_names": [bucket["candidate_name"]],
                "supporting_chapters": chapter_ids,
                "reason": "repeated title prefix in novel_index",
            }
        )
    for number, chapter_ids in sorted(number_buckets.items()):
        unique_chapters = unique_preserve_order(chapter_ids)
        if len(unique_chapters) < 2:
            continue
        clusters.append(
            {
                "cluster_id": f"title_number_{number}",
                "entity_kind": "unknown",
                "candidate_names": [str(number)],
                "supporting_chapters": unique_chapters,
                "reason": "reused explicit title number",
            }
        )
    if unclear_title_chapters:
        clusters.append(
            {
                "cluster_id": "unclear_title_structure",
                "entity_kind": "unknown",
                "candidate_names": [],
                "supporting_chapters": unclear_title_chapters,
                "reason": "titles without deterministic separator or explicit number",
            }
        )
    clusters.sort(key=lambda item: str(item.get("cluster_id") or ""))
    return clusters


def _select_chapters_for_global_expansion(
    *,
    chapters: list[dict[str, Any]],
    dense_chapter_ids: list[str],
    high_narrative_chapter_ids: list[str],
    ambiguous_chapter_ids: list[str],
    config: NovelBootstrapV1Config,
) -> list[str]:
    selected = unique_preserve_order(ambiguous_chapter_ids + dense_chapter_ids + high_narrative_chapter_ids)
    by_id = {str(chapter.get("chapter_id") or ""): chapter for chapter in chapters}
    if len(selected) < config.selective_global_min_chapters:
        for chapter in sorted(chapters, key=lambda item: -int(item.get("token_count_estimate") or 0)):
            chapter_id = str(chapter.get("chapter_id") or "").strip()
            if chapter_id and chapter_id not in selected:
                selected.append(chapter_id)
            if len(selected) >= config.selective_global_min_chapters:
                break
    ordered = sorted(
        [chapter_id for chapter_id in selected if chapter_id in by_id],
        key=lambda chapter_id: int(by_id[chapter_id].get("sequence_index") or 0),
    )
    return ordered[: max(1, config.selective_global_max_chapters)]


def build_ambiguous_entity_queue(pass1_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generation": {
            "method": "deterministic_pass1_projection",
            "llm_required": False,
        },
        "ambiguous_clusters": pass1_payload.get("ambiguous_clusters") or [],
        "selected_chapter_ids": pass1_payload.get("selected_chapter_ids") or [],
    }


def _append_selective_trace(
    path: Path,
    *,
    run_id: str,
    event_type: str,
    chapter_id: str | None = None,
    cluster_id: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": event_type,
        "timestamp": _utc_timestamp(),
        "run_id": run_id,
        "chapter_id": chapter_id,
        "cluster_id": cluster_id,
        "reason": reason,
        "metadata": metadata or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_pass1_trace_events(path: Path, *, run_id: str, pass1_payload: dict[str, Any]) -> None:
    for row in pass1_payload.get("chapter_selection") or []:
        chapter_id = str(row.get("chapter_id") or "").strip() or None
        reasons = [str(item) for item in (row.get("reasons") or []) if str(item).strip()]
        event_type = "planner_selected_chapter" if row.get("selected") else "planner_rejected_chapter"
        _append_selective_trace(
            path,
            run_id=run_id,
            event_type=event_type,
            chapter_id=chapter_id,
            reason=",".join(reasons) if reasons else None,
            metadata={
                "reasons": reasons,
                "sequence_index": row.get("sequence_index"),
                "token_count_estimate": row.get("token_count_estimate"),
            },
        )
    _append_selective_trace(
        path,
        run_id=run_id,
        event_type="planner_finished",
        reason="selection_plan_persisted",
        metadata={
            "chapter_count_total": pass1_payload.get("chapter_count", 0),
            "chapter_count_selected_for_pass2": len(pass1_payload.get("selected_chapter_ids") or []),
            "chapter_count_rejected_for_pass2": len(pass1_payload.get("rejected_chapter_ids") or []),
            "ambiguous_cluster_count": len(pass1_payload.get("ambiguous_clusters") or []),
        },
    )


def _append_ambiguous_queue_trace_events(path: Path, *, run_id: str, ambiguity_queue: dict[str, Any]) -> None:
    for cluster in ambiguity_queue.get("ambiguous_clusters") or []:
        if not isinstance(cluster, dict):
            continue
        _append_selective_trace(
            path,
            run_id=run_id,
            event_type="ambiguous_cluster_created",
            cluster_id=str(cluster.get("cluster_id") or "").strip() or None,
            reason=_cluster_selection_reason(cluster),
            metadata={
                "entity_kind": cluster.get("entity_kind"),
                "candidate_names": cluster.get("candidate_names") or [],
                "supporting_chapters": cluster.get("supporting_chapters") or [],
            },
        )


def build_selective_normalization_metrics(
    *,
    run_status: dict[str, Any] | None,
    novel_index: dict[str, Any],
    pass1_payload: dict[str, Any],
    ambiguity_queue: dict[str, Any],
    pass2_payload: dict[str, Any],
    global_payload: dict[str, Any],
) -> dict[str, Any]:
    total_chapters = len(novel_index.get("chapters") or [])
    selected_chapter_ids = [str(item) for item in (pass1_payload.get("selected_chapter_ids") or [])]
    rejected_chapter_ids = [str(item) for item in (pass1_payload.get("rejected_chapter_ids") or [])]
    expanded_chapter_ids = [str(item) for item in (pass2_payload.get("expanded_chapter_ids") or [])]
    entities = [item for item in (global_payload.get("entities") or []) if isinstance(item, dict)]
    contributing_ids = _selected_chapters_that_contributed_changes(selected_chapter_ids, entities)
    reason_counts: dict[str, int] = {}
    for row in pass1_payload.get("chapter_selection") or []:
        if not row.get("selected"):
            continue
        for reason in row.get("reasons") or []:
            reason = str(reason).strip()
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
    alias_count = sum(len(entity.get("aliases") or []) for entity in entities)
    review_count = sum(
        1
        for entity in entities
        if entity.get("needs_review") is True or str(entity.get("review_state") or "").strip() == "review"
    )
    return {
        "schema_version": 1,
        "run_status": run_status or {},
        "observable_change_definition": {
            "rule": "A selected chapter contributed observable changes when at least one pass2 global entity or merge_plan item references that chapter ID in chapter_refs.",
            "counted_changes": [
                "candidate entity created or retained with selected chapter_ref",
                "alias candidates present on pass2 entities",
                "review candidates present on pass2 entities",
                "canonical_candidate present on pass2 entities",
            ],
        },
        "chapter_count_total": total_chapters,
        "chapter_count_selected_for_pass2": len(selected_chapter_ids),
        "chapter_count_rejected_for_pass2": len(rejected_chapter_ids),
        "ambiguous_cluster_count": len(ambiguity_queue.get("ambiguous_clusters") or []),
        "pass2_subcalls_started": len(selected_chapter_ids),
        "pass2_subcalls_completed": len(expanded_chapter_ids),
        "pass2_subcalls_failed": max(0, len(selected_chapter_ids) - len(expanded_chapter_ids)),
        "selected_chapter_ids": selected_chapter_ids,
        "rejected_chapter_ids": rejected_chapter_ids,
        "selection_reason_counts": dict(sorted(reason_counts.items())),
        "did_pass2_change_global_normalization": bool(entities or (global_payload.get("merge_plan") or [])),
        "did_pass2_change_entity_candidates": bool(entities),
        "selected_chapters_that_contributed_changes": contributing_ids,
        "selected_chapters_with_no_observable_changes": [
            chapter_id for chapter_id in selected_chapter_ids if chapter_id not in set(contributing_ids)
        ],
        "changed_candidate_entity_count": len(entities),
        "changed_alias_candidate_count": alias_count,
        "changed_review_candidate_count": review_count,
        "changed_canonical_candidate_count": sum(1 for entity in entities if str(entity.get("canonical_candidate") or "").strip()),
    }


def _selected_chapters_that_contributed_changes(selected_chapter_ids: list[str], entities: list[dict[str, Any]]) -> list[str]:
    selected = set(selected_chapter_ids)
    contributing: list[str] = []
    for entity in entities:
        for chapter_ref in entity.get("chapter_refs") or []:
            chapter_id = str(chapter_ref).strip()
            if chapter_id in selected:
                contributing.append(chapter_id)
    return sorted(set(contributing), key=lambda item: int(item.split("_", 1)[1]) if "_" in item and item.split("_", 1)[1].isdigit() else 0)


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
                        "preferred_slug": _preferred_slug_for_name(canonical),
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
                "preferred_slug": _preferred_slug_for_name(candidate["canonical_name"]),
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
                    "preferred_slug": _preferred_slug_for_name(hint),
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
                "preferred_slug": _preferred_slug_for_name(bucket["canonical_name"]),
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
            "sequence_index": int(getattr(chapter, "source_sequence_index", None) or sequence_index),
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


def _chapters_for_selected_ids(chapters: list[Any], selected_chapter_ids: list[str]) -> list[Any]:
    selected = set(selected_chapter_ids)
    if not selected:
        return chapters
    return [
        chapter
        for sequence_index, chapter in enumerate(chapters, start=1)
        if f"ch_{sequence_index:03d}" in selected
    ]


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
        novel_index=None,
        pass1_payload=None,
        ambiguity_queue=None,
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
    novel_index: dict[str, Any] | None = None,
    pass1_payload: dict[str, Any] | None = None,
    ambiguity_queue: dict[str, Any] | None = None,
) -> str:
    batch_text = "\n\n".join(
        f"[ch_{item['sequence_index']:03d}] {item['title']}\n{item['text']}"
        for item in batch
    )
    batch_chapter_ids = [f"ch_{item['sequence_index']:03d}" for item in batch]
    return (
        f"{GLOBAL_NORMALIZATION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"WORK_LANGUAGE: {language}\n\n"
        "NORMALIZATION_STRATEGY:\n"
        "- Use metadata-first selective expansion.\n"
        "- The full novel text is represented externally by NOVEL_INDEX metadata.\n"
        "- Only SELECTIVE_CHAPTER_TEXT is expanded in this call.\n"
        "- Do not claim evidence from chapters that are not in BATCH_SCOPE.\n\n"
        f"NOVEL_INDEX_METADATA:\n{json.dumps(_compact_novel_index_for_prompt(novel_index), ensure_ascii=False)}\n\n"
        f"PASS1_PLANNER:\n{json.dumps(_compact_pass1_for_prompt(pass1_payload), ensure_ascii=False)}\n\n"
        f"AMBIGUITY_QUEUE:\n{json.dumps(ambiguity_queue or {}, ensure_ascii=False)}\n\n"
        "BATCH_SCOPE:\n"
        f"- Batch index: {batch_index}\n"
        f"- Chapter IDs: {', '.join(batch_chapter_ids)}\n"
        "Normalize persistent entities using only this batch as evidence. "
        "Return entities worth keeping as long-term notes plus high-confidence merges supported by this batch.\n\n"
        f"FULL_TEXT:\n{batch_text}"
    )


def _compact_novel_index_for_prompt(novel_index: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(novel_index, dict):
        return {}
    return {
        "work": novel_index.get("work") or {},
        "chapters": [
            {
                "chapter_id": chapter.get("chapter_id"),
                "sequence_index": chapter.get("sequence_index"),
                "chapter_title_original": chapter.get("chapter_title_original"),
                "chapter_label_type": chapter.get("chapter_label_type"),
                "chapter_number_in_label": chapter.get("chapter_number_in_label"),
                "title_parse_signals": chapter.get("title_parse_signals"),
                "token_count_estimate": chapter.get("token_count_estimate"),
                "content_hash": chapter.get("content_hash"),
            }
            for chapter in (novel_index.get("chapters") or [])
            if isinstance(chapter, dict)
        ],
    }


def _compact_pass1_for_prompt(pass1_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(pass1_payload, dict):
        return {}
    return {
        "strategy": pass1_payload.get("strategy"),
        "dense_chapters": pass1_payload.get("dense_chapters") or [],
        "ambiguous_clusters": pass1_payload.get("ambiguous_clusters") or [],
        "selected_chapter_ids": pass1_payload.get("selected_chapter_ids") or [],
        "normalization_notes": pass1_payload.get("normalization_notes") or [],
    }


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


def _build_global_normalization_pass2_artifact(global_payload: dict[str, Any]) -> dict[str, Any]:
    selective = global_payload.get("selective_normalization") if isinstance(global_payload.get("selective_normalization"), dict) else {}
    return {
        "schema_version": 1,
        "strategy": selective.get("strategy") or "metadata_first_selective_expansion",
        "generation": {
            "method": "llm_selective_chapter_expansion",
            "llm_required": True,
        },
        "work": global_payload.get("work") or {},
        "selected_chapter_ids": selective.get("pass1_selected_chapter_ids") or [],
        "expanded_chapter_ids": selective.get("pass2_expanded_chapter_ids") or [],
        "ambiguous_cluster_count": selective.get("ambiguous_cluster_count", 0),
        "entity_count": len(global_payload.get("entities") or []),
        "merge_plan_count": len(global_payload.get("merge_plan") or []),
        "entities": global_payload.get("entities") or [],
        "merge_plan": global_payload.get("merge_plan") or [],
    }


def _run_global_normalization(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    source_text: str,
    source_path: Path,
    novel_index: dict[str, Any],
    pass1_payload: dict[str, Any],
    ambiguity_queue: dict[str, Any],
    config: NovelBootstrapV1Config,
    request_trace_dir: Path | None = None,
    audit_path: Path | None = None,
    progress_log_path: str | None = None,
    resolved_model_plan: ResolvedModelPlan | None = None,
    telemetry_path: Path | None = None,
    trace_path: Path | None = None,
    llm_call_ledger_path: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    global_model = _resolve_structured_model(config, phase="global_normalization", resolved_model_plan=resolved_model_plan)
    _ = source_text
    _ = source_path
    selected_chapter_ids = [str(item).strip() for item in (pass1_payload.get("selected_chapter_ids") or []) if str(item).strip()]
    selected_chapters = _chapters_for_selected_ids(chapters, selected_chapter_ids)
    provider = get_text_provider(config.global_task_name, config.provider_name)
    if llm_call_ledger_path is not None:
        provider = _LedgerTextProvider(provider, llm_call_ledger_path, phase="global_normalization")
    chapter_batches, batch_audit = _build_global_normalization_batches(
        work_title=work_title,
        language=language,
        chapters=selected_chapters,
        config=config,
        resolved_model_plan=resolved_model_plan,
    )
    batch_audit = {
        **batch_audit,
        "strategy": "metadata_first_selective_expansion",
        "novel_index_chapter_count": len(novel_index.get("chapters") or []),
        "selected_chapter_ids": selected_chapter_ids,
        "selected_chapter_count": len(selected_chapters),
        "pass1_artifacts": ["novel_index.json", "global_normalization_pass1.json", "ambiguous_entity_queue.json"],
    }
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
        batch_chapter_ids = [f"ch_{item['sequence_index']:03d}" for item in batch]
        if trace_path is not None:
            for chapter_id in batch_chapter_ids:
                _append_selective_trace(
                    trace_path,
                    run_id=run_id or "",
                    event_type="pass2_subcall_started",
                    chapter_id=chapter_id,
                    reason="selected_for_selective_expansion",
                    metadata={"batch_index": batch_index, "batch_chapter_ids": batch_chapter_ids, "model": global_model},
                )
        before_count = len(batch_payloads)
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
                novel_index=novel_index,
                pass1_payload=pass1_payload,
                ambiguity_queue=ambiguity_queue,
                request_trace_dir=request_trace_dir,
                progress_log_path=progress_log_path,
                telemetry_path=telemetry_path,
            )
        )
        completed = len(batch_payloads) > before_count
        if trace_path is not None:
            for chapter_id in batch_chapter_ids:
                _append_selective_trace(
                    trace_path,
                    run_id=run_id or "",
                    event_type="pass2_subcall_completed" if completed else "pass2_subcall_failed",
                    chapter_id=chapter_id,
                    reason="batch_payload_generated" if completed else "batch_payload_missing",
                    metadata={"batch_index": batch_index, "batch_chapter_ids": batch_chapter_ids},
                )

    if not batch_payloads:
        return None
    merged = _merge_global_normalization_batches(batch_payloads, work_title=work_title, language=language)
    notes = merged.setdefault("work", {}).setdefault("normalization_notes", [])
    notes.extend(
        [
            "strategy:metadata_first_selective_expansion",
            f"pass2_selected_chapters:{len(selected_chapters)}",
        ]
    )
    merged["selective_normalization"] = {
        "strategy": "metadata_first_selective_expansion",
        "pass1_selected_chapter_ids": selected_chapter_ids,
        "pass2_expanded_chapter_ids": selected_chapter_ids,
        "ambiguous_cluster_count": len(ambiguity_queue.get("ambiguous_clusters") or []),
    }
    if trace_path is not None:
        _append_selective_trace(
            trace_path,
            run_id=run_id or "",
            event_type="global_normalization_merged",
            reason="pass2_payloads_merged",
            metadata={
                "batch_payload_count": len(batch_payloads),
                "entity_count": len(merged.get("entities") or []),
                "merge_plan_count": len(merged.get("merge_plan") or []),
                "expanded_chapter_ids": selected_chapter_ids,
            },
        )
    return merged


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
    novel_index: dict[str, Any] | None,
    pass1_payload: dict[str, Any] | None,
    ambiguity_queue: dict[str, Any] | None,
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
        novel_index=novel_index,
        pass1_payload=pass1_payload,
        ambiguity_queue=ambiguity_queue,
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
            language_errors, language_warnings = _validate_global_normalization_language(
                payload=normalized,
                language=language,
                validator_name=config.prose_language_validator,
                validation_mode=config.prose_language_validation_mode,
            )
            if language_warnings:
                _append_progress(
                    progress_log_path,
                    phase="structured_bootstrap_v1",
                    event="global_normalization_language_validation_warning",
                    batch_index=batch_index,
                    chapter_ids=batch_chapter_ids,
                    failure_attempt=failure_attempt,
                    subdivision_depth=subdivision_depth,
                    warnings=language_warnings[:10],
                )
            if language_errors:
                last_error = "; ".join(language_errors)
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
                continue
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
                novel_index=novel_index,
                pass1_payload=pass1_payload,
                ambiguity_queue=ambiguity_queue,
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
                novel_index=novel_index,
                pass1_payload=pass1_payload,
                ambiguity_queue=ambiguity_queue,
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
    llm_call_ledger_path: Path | None = None,
    request_trace_path: Path | None = None,
) -> ChapterExtractionAttemptResult:
    provider = get_text_provider(config.chapter_task_name, config.provider_name)
    if llm_call_ledger_path is not None:
        provider = _LedgerTextProvider(provider, llm_call_ledger_path, phase="chapter_extraction")
    attempts = max(1, int(config.chapter_extraction_retries) + 1)
    last_result: ChapterExtractionAttemptResult | None = None
    for attempt in range(1, attempts + 1):
        result = _run_chapter_extraction_once(
            provider=provider,
            work_title=work_title,
            language=language,
            chapter_id=chapter_id,
            sequence_index=sequence_index,
            chapter_title=chapter_title,
            chapter_text=chapter_text,
            canonical_entity_map=canonical_entity_map,
            config=config,
            resolved_model_plan=resolved_model_plan,
            telemetry_path=telemetry_path,
            request_trace_path=request_trace_path if attempt == 1 else None,
            attempt_count=attempt,
        )
        if result.ok:
            return result
        last_result = result
        if attempt < attempts:
            time.sleep(max(0.0, config.chapter_extraction_retry_backoff_seconds) * attempt)
    return last_result or _chapter_failure_result(
        attempt_count=0,
        failure_type="unknown_failure",
        failure_reason="chapter extraction did not produce an attempt result",
    )


def _run_chapter_extraction_once(
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
    resolved_model_plan: ResolvedModelPlan | None = None,
    telemetry_path: Path | None = None,
    request_trace_path: Path | None = None,
    attempt_count: int,
) -> ChapterExtractionAttemptResult:
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
            attempt_count=attempt_count,
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
    except TextProviderError as exc:
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
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="api_failure",
            failure_reason=str(exc),
            exception_type=type(exc).__name__,
        )
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
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="parse_failure",
            failure_reason="response did not contain a JSON object",
            response_text=response.text,
            json_valid=False,
        )
    normalized_payload = _normalize_chapter_payload(
        payload,
        chapter_id=chapter_id,
        sequence_index=sequence_index,
        chapter_title=chapter_title,
        chapter_text=chapter_text,
        work_title=work_title,
        language=language,
    )
    schema_valid, validation_errors, validation_warnings = _validate_chapter_extraction_payload(
        normalized_payload,
        chapter_id=chapter_id,
        sequence_index=sequence_index,
        language=language,
        validator_name=config.prose_language_validator,
        validation_mode=config.prose_language_validation_mode,
    )
    if not schema_valid:
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="schema_failure",
            failure_reason="; ".join(validation_errors),
            response_text=response.text,
            json_valid=True,
            schema_valid=False,
            warnings=validation_warnings,
        )
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
    return ChapterExtractionAttemptResult(
        payload=normalized_payload,
        attempt_count=attempt_count,
        json_valid=True,
        schema_valid=True,
        warnings=validation_warnings,
    )


def _chapter_failure_result(
    *,
    attempt_count: int,
    failure_type: str,
    failure_reason: str,
    exception_type: str | None = None,
    response_text: str | None = None,
    json_valid: bool = False,
    schema_valid: bool = False,
    warnings: list[str] | None = None,
) -> ChapterExtractionAttemptResult:
    excerpt = _response_excerpt(response_text) if response_text is not None else None
    digest = hashlib.sha256(response_text.encode("utf-8")).hexdigest() if response_text is not None else None
    return ChapterExtractionAttemptResult(
        payload=None,
        attempt_count=attempt_count,
        failure_type=failure_type,
        failure_reason=failure_reason,
        exception_type=exception_type,
        response_excerpt=excerpt,
        response_sha256=digest,
        json_valid=json_valid,
        schema_valid=schema_valid,
        warnings=warnings or [],
    )


def _response_excerpt(text: str, *, max_chars: int = 500) -> str:
    normalized = str(text or "").replace("\x00", "")
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars] + "...[truncated]"


def _validate_chapter_extraction_payload(
    payload: dict[str, Any],
    *,
    chapter_id: str,
    sequence_index: int,
    language: str,
    validator_name: str | None = "heuristic",
    validation_mode: str = "strict",
) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload.get("work"), dict):
        errors.append("missing object: work")
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or len(chapters) != 1 or not isinstance(chapters[0], dict):
        errors.append("chapters must contain exactly one chapter object")
        return False, errors, warnings
    chapter = chapters[0]
    if chapter.get("chapter_id") != chapter_id:
        errors.append(f"chapter_id mismatch: expected {chapter_id!r}, got {chapter.get('chapter_id')!r}")
    chapter_sequence_index = chapter.get("sequence_index")
    if not isinstance(chapter_sequence_index, int) or isinstance(chapter_sequence_index, bool):
        errors.append(f"sequence_index must be an integer, got {chapter_sequence_index!r}")
    elif chapter_sequence_index != sequence_index:
        errors.append(f"sequence_index mismatch: expected {sequence_index}, got {chapter.get('sequence_index')!r}")
    label_type = chapter.get("chapter_label_type")
    if label_type not in CHAPTER_LABEL_TYPES:
        errors.append(f"chapter_label_type must be one of {sorted(CHAPTER_LABEL_TYPES)}, got {label_type!r}")
    label_number = chapter.get("chapter_number_in_label")
    if label_number is not None and (not isinstance(label_number, int) or isinstance(label_number, bool)):
        errors.append(f"chapter_number_in_label must be an integer or null, got {label_number!r}")
    title_parse_signals = chapter.get("title_parse_signals")
    errors.extend(_validate_title_parse_signals(title_parse_signals))
    for key in (
        "chapter_title_original",
        "chapter_title_canonical",
        "chapter_summary",
    ):
        if not str(chapter.get(key) or "").strip():
            errors.append(f"missing non-empty field: {key}")
    for key in ("characters", "places", "concepts", "events", "relations", "unresolved_mentions"):
        if not isinstance(chapter.get(key), list):
            errors.append(f"missing array field: {key}")
    language_errors, language_warnings = _validate_chapter_explanatory_language(
        chapter=chapter,
        language=language,
        validator_name=validator_name,
        validation_mode=validation_mode,
    )
    errors.extend(language_errors)
    warnings.extend(language_warnings)
    warnings.extend(_chapter_title_language_warnings(chapter, language=language))
    return not errors, errors, warnings


def _validate_chapter_explanatory_language(
    *,
    chapter: dict[str, Any],
    language: str,
    validator_name: str | None,
    validation_mode: str,
) -> tuple[list[str], list[str]]:
    texts = [str(chapter.get("chapter_summary") or "").strip()]
    for key in ("characters", "places", "concepts", "events"):
        for item in chapter.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            texts.extend(str(fact).strip() for fact in (item.get("facts") or []) if str(fact).strip())
    for rel in chapter.get("relations", []) or []:
        if not isinstance(rel, dict):
            continue
        texts.extend(str(fact).strip() for fact in (rel.get("facts") or []) if str(fact).strip())
    return _validate_explanatory_language_with_policy(
        texts=texts,
        language=language,
        context="chapter_extraction",
        validator_name=validator_name,
        validation_mode=validation_mode,
    )


def _validate_title_parse_signals(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["missing object: title_parse_signals"]
    expected_keys = {
        "has_explicit_number",
        "explicit_number_value",
        "has_colon",
        "has_em_dash",
        "primary_separator",
        "prefix_segment",
        "suffix_segment",
    }
    missing = sorted(expected_keys - set(value))
    if missing:
        errors.append(f"title_parse_signals missing fields: {missing}")
    if "has_explicit_number" in value and not isinstance(value.get("has_explicit_number"), bool):
        errors.append("title_parse_signals.has_explicit_number must be boolean")
    if "has_colon" in value and not isinstance(value.get("has_colon"), bool):
        errors.append("title_parse_signals.has_colon must be boolean")
    if "has_em_dash" in value and not isinstance(value.get("has_em_dash"), bool):
        errors.append("title_parse_signals.has_em_dash must be boolean")
    primary_separator = value.get("primary_separator")
    if primary_separator not in {":", "—", None}:
        errors.append("title_parse_signals.primary_separator must be ':', '—', or null")
    explicit_number = value.get("explicit_number_value")
    if explicit_number is not None and (not isinstance(explicit_number, int) or isinstance(explicit_number, bool)):
        errors.append("title_parse_signals.explicit_number_value must be integer or null")
    for key in ("prefix_segment", "suffix_segment"):
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            errors.append(f"title_parse_signals.{key} must be string or null")
    return errors


def _chapter_title_language_warnings(chapter: dict[str, Any], *, language: str) -> list[str]:
    warnings: list[str] = []
    lang = str(language or "").casefold()
    if not lang.startswith("es"):
        return warnings
    canonical_title = str(chapter.get("chapter_title_canonical") or "")
    if re.search(r"\b(episode|chapter|part|prologue|interlude)\b", canonical_title, flags=re.IGNORECASE):
        warnings.append("chapter_title_canonical contains English structural title words in a Spanish-language run")
    return warnings


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
    title_parse_signals = _extract_title_parse_signals(chapter_title)
    return (
        f"{CHAPTER_EXTRACTION_PROMPT}\n\n"
        f"WORK_TITLE: {work_title}\n"
        f"WORK_LANGUAGE: {language}\n\n"
        f"CHAPTER_ID: {chapter_id}\n"
        f"SEQUENCE_INDEX: {sequence_index}\n"
        f"CHAPTER_TITLE: {chapter_title}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
        f"TITLE_PARSE_SIGNALS: {json.dumps(title_parse_signals, ensure_ascii=False)}\n\n"
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
    attempt_count: int,
) -> ChapterExtractionAttemptResult:
    partial_budget = max(1000, budget.usable_input_budget - 4000)
    subchunks = split_markdown_semantically(
        chapter_text=chapter_text,
        max_chunk_tokens=partial_budget,
        estimate_tokens=_estimate_token_count,
        overlap_paragraphs=config.chapter_chunk_overlap_paragraphs,
    )
    title_entity_hints = _extract_title_entity_hints(chapter_title)
    title_parse_signals = _extract_title_parse_signals(chapter_title)
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
            f"WORK_LANGUAGE: {language}\n\n"
            f"CHAPTER_ID: {chapter_id}\n"
            f"CHUNK_ID: {chapter_id}_part_{chunk_index:02d}\n"
            f"CHAPTER_TITLE: {chapter_title}\n\n"
            f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
            f"TITLE_PARSE_SIGNALS: {json.dumps(title_parse_signals, ensure_ascii=False)}\n\n"
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
        except TextProviderError as exc:
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
            return _chapter_failure_result(
                attempt_count=attempt_count,
                failure_type="api_failure",
                failure_reason=str(exc),
                exception_type=type(exc).__name__,
            )
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
            return _chapter_failure_result(
                attempt_count=attempt_count,
                failure_type="parse_failure",
                failure_reason=f"subchunk {chunk_index} response did not contain a JSON object",
                response_text=response.text,
                json_valid=False,
            )
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
        f"WORK_LANGUAGE: {language}\n\n"
        f"CHAPTER_ID: {chapter_id}\n"
        f"SEQUENCE_INDEX: {sequence_index}\n"
        f"CHAPTER_TITLE: {chapter_title}\n\n"
        f"TITLE_ENTITY_HINTS: {json.dumps(title_entity_hints, ensure_ascii=False)}\n\n"
        f"TITLE_PARSE_SIGNALS: {json.dumps(title_parse_signals, ensure_ascii=False)}\n\n"
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
    except TextProviderError as exc:
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
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="api_failure",
            failure_reason=str(exc),
            exception_type=type(exc).__name__,
        )
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
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="parse_failure",
            failure_reason="chapter reduction response did not contain a JSON object",
            response_text=response.text,
            json_valid=False,
        )
    normalized_payload = _normalize_chapter_payload(
        payload,
        chapter_id=chapter_id,
        sequence_index=sequence_index,
        chapter_title=chapter_title,
        chapter_text=chapter_text,
        work_title=work_title,
        language=language,
    )
    schema_valid, validation_errors, validation_warnings = _validate_chapter_extraction_payload(
        normalized_payload,
        chapter_id=chapter_id,
        sequence_index=sequence_index,
        language=language,
        validator_name=config.prose_language_validator,
        validation_mode=config.prose_language_validation_mode,
    )
    if not schema_valid:
        return _chapter_failure_result(
            attempt_count=attempt_count,
            failure_type="schema_failure",
            failure_reason="; ".join(validation_errors),
            response_text=response.text,
            json_valid=True,
            schema_valid=False,
            warnings=validation_warnings,
        )
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
    return ChapterExtractionAttemptResult(
        payload=normalized_payload,
        attempt_count=attempt_count,
        json_valid=True,
        schema_valid=True,
        warnings=validation_warnings,
    )


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


def _extract_title_parse_signals(title: str) -> dict[str, Any]:
    raw_title = str(title or "").strip()
    number_match = re.search(r"\d+", raw_title)
    has_colon = ":" in raw_title
    has_em_dash = "—" in raw_title
    primary_separator = ":" if has_colon else ("—" if has_em_dash else None)
    if primary_separator is not None:
        prefix, suffix = raw_title.split(primary_separator, 1)
        prefix_segment = prefix.strip() or None
        suffix_segment = suffix.strip() or None
    else:
        words = raw_title.split()
        prefix_segment = " ".join(words[:3]).strip() or None
        suffix_segment = " ".join(words[3:]).strip() or None
    return {
        "has_explicit_number": number_match is not None,
        "explicit_number_value": int(number_match.group(0)) if number_match is not None else None,
        "has_colon": has_colon,
        "has_em_dash": has_em_dash,
        "primary_separator": primary_separator,
        "prefix_segment": prefix_segment,
        "suffix_segment": suffix_segment,
    }


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
        "entities": [],
        "merge_plan": merge_plan if isinstance(merge_plan, list) else [],
    }
    for raw in entities if isinstance(entities, list) else []:
        if not isinstance(raw, dict):
            continue
        canonical_name = str(raw.get("canonical_name") or raw.get("canonical_candidate") or "").strip()
        normalized["entities"].append(
            {
                **raw,
                "canonical_name": canonical_name,
                "canonical_candidate": str(raw.get("canonical_candidate") or canonical_name).strip() or canonical_name,
                "preferred_slug": str(raw.get("preferred_slug") or _preferred_slug_for_name(canonical_name)).strip() or _preferred_slug_for_name(canonical_name),
                "entity_subkind": str(raw.get("entity_subkind") or "").strip(),
                "naming_quality": str(raw.get("naming_quality") or "unknown").strip() or "unknown",
                "is_stable_entity": bool(raw.get("is_stable_entity", False)),
                "needs_review": bool(raw.get("needs_review", str(raw.get("review_state") or "").casefold() == "review")),
                "review_reason": str(raw.get("review_reason") or "").strip(),
                "gender_presentation_signal": _normalize_gender_presentation_signal(raw.get("gender_presentation_signal")),
                "gender_signal_confidence": _normalize_optional_float(raw.get("gender_signal_confidence")),
                "gender_signal_evidence": _normalize_gender_signal_evidence(raw.get("gender_signal_evidence")),
            }
        )
    return normalized


def _validate_global_normalization_language(
    *,
    payload: dict[str, Any],
    language: str,
    validator_name: str | None,
    validation_mode: str,
) -> tuple[list[str], list[str]]:
    work = payload.get("work") or {}
    texts: list[str] = [str(item).strip() for item in (work.get("normalization_notes") or []) if str(item).strip()]
    for entity in payload.get("entities", []) or []:
        if not isinstance(entity, dict):
            continue
        texts.append(str(entity.get("summary") or "").strip())
        texts.extend(str(item).strip() for item in (entity.get("key_facts") or []) if str(item).strip())
        for relationship in entity.get("relationships", []) or []:
            if not isinstance(relationship, dict):
                continue
            texts.extend(str(item).strip() for item in (relationship.get("facts") or []) if str(item).strip())
    return _validate_explanatory_language_with_policy(
        texts=texts,
        language=language,
        context="global_normalization",
        validator_name=validator_name,
        validation_mode=validation_mode,
    )


def _validate_downstream_entity_explanations_language(
    *,
    entities: list[dict[str, Any]],
    language: str,
    context: str,
    validator_name: str | None,
    validation_mode: str,
) -> tuple[list[str], list[str]]:
    texts = [
        str(entity.get("review_reason") or "").strip()
        for entity in entities
        if isinstance(entity, dict) and str(entity.get("review_reason") or "").strip()
    ]
    return _validate_explanatory_language_with_policy(
        texts=texts,
        language=language,
        context=context,
        validator_name=validator_name,
        validation_mode=validation_mode,
    )


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
    chapter["chapter_label_type"] = str(chapter.get("chapter_label_type") or "other").strip() or "other"
    if chapter["chapter_label_type"] not in CHAPTER_LABEL_TYPES:
        chapter["chapter_label_type"] = "other"
    chapter["title_parse_signals"] = _extract_title_parse_signals(chapter["chapter_title_original"])
    if chapter.get("chapter_number_in_label") is not None:
        chapter["chapter_number_in_label"] = int(chapter["chapter_number_in_label"])
    else:
        chapter["chapter_number_in_label"] = None
    chapter["chapter_summary"] = str(chapter.get("chapter_summary") or "").strip()
    chapter["chapter_text_markdown"] = str(chapter.get("chapter_text_markdown") or chapter_text).strip()
    for key in ("characters", "places", "concepts", "events", "relations", "unresolved_mentions"):
        if not isinstance(chapter.get(key), list):
            chapter[key] = []
    for key in ("characters", "places", "concepts", "events"):
        normalized_items: list[dict[str, Any]] = []
        for item in chapter.get(key, []):
            if not isinstance(item, dict):
                continue
            surface = str(item.get("surface") or "").strip()
            canonical = str(item.get("canonical") or surface).strip() or surface
            normalized_items.append(
                {
                    **item,
                    "surface": surface,
                    "canonical": canonical,
                    "canonical_candidate": str(item.get("canonical_candidate") or canonical or surface).strip() or canonical,
                    "entity_subkind": str(item.get("entity_subkind") or "").strip(),
                    "naming_quality": str(item.get("naming_quality") or "unknown").strip() or "unknown",
                    "gender_presentation_signal": _normalize_gender_presentation_signal(item.get("gender_presentation_signal")),
                    "gender_signal_confidence": _normalize_optional_float(item.get("gender_signal_confidence")),
                    "gender_signal_evidence": _normalize_gender_signal_evidence(item.get("gender_signal_evidence")),
                    "needs_review": bool(item.get("needs_review", False)),
                }
            )
        chapter[key] = normalized_items
    return {
        "work": {
            "title": str(work.get("title") or work_title).strip() or work_title,
            "language": str(work.get("language") or language).strip() or language,
        },
        "chapters": [chapter],
    }


def _normalize_gender_presentation_signal(value: Any) -> str:
    normalized = str(value or "unknown").strip().casefold()
    if normalized in {"masculine", "feminine", "unknown", "mixed"}:
        return normalized
    return "unknown"


def _normalize_optional_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return round(numeric, 4)


def _normalize_gender_signal_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        chapter_id = str(item.get("chapter_id") or "").strip()
        surface = str(item.get("surface") or "").strip()
        kind = str(item.get("kind") or "").strip() or "unknown"
        key = (chapter_id, surface, kind)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"chapter_id": chapter_id, "surface": surface, "kind": kind})
    return normalized[:5]


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
        f"WORK_LANGUAGE: {language}\n\n"
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
