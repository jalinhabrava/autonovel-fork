# TextifAI Chunking/Reduction Preflight

## Product Reading

`SP-070` packaged DeepSeek-family profiles, `SP-071` added prompt experiment observability, and `SP-072` confirmed no clear prompt improvement with same input shape. We should stop prompt tuning for now and return to chunking/reduction, using existing pipeline components instead of reimplementing from zero.

## Existing Pipeline Inventory

Existing production modules:

- `textifai/import_review/chapterizer.py`: detects story chapters and chapter char ranges.
- `textifai/import_review/batch_planner.py`: packs items and splits markdown semantically.
- `textifai/import_review/structured_bootstrap_v1.py`: runs global normalization, chapter extraction, chunked partial extraction, and chapter reduction.
- `textifai/import_review/auxiliary_ingestion.py`: chunks and ingests author notes / auxiliary documents.
- `textifai/import_review/token_budget.py`: derives usable input budget from model capability and output reserve.
- `textifai/import_review/model_registry.py`: model capability registry.

## Structured Documents

Structured document support exists:

- chapter boundaries detected by `detect_story_chapters`;
- `DetectedChapter` preserves `chapter_id`, `source_id`, `text`, `char_start`, `char_end`, page hints, and sequence index;
- long chapters can go through `_run_chapter_extraction_chunked`;
- `split_markdown_semantically` splits by markdown headings/paragraphs with overlap.

Gaps:

- semantic subchunks are plain strings, not first-class chunk records;
- oversized heading sections are not subdivided internally by the current semantic splitter;
- no explicit subchunk `char_start`/`char_end`, predecessor/successor, or source span metadata;
- no provider-free fixture e2e for chapter split → partial outputs → reduction.

## Unstructured Author Notes

Auxiliary ingestion support exists:

- `_build_auxiliary_document_record` tracks source id, author hint, title hint, hashes, counts, heading count;
- `_chunk_auxiliary_document` packs heading sections into chunks;
- chunk metadata includes `source_id`, `chunk_id`, `filename`, `path`, `author_hint`, `heading_path`, `chunk_kind`, `char_count`;
- extraction schema supports character sheets, world lore, outlines, timelines, mixed notes, planned events and relationships.

Gaps:

- chunks lack char spans and predecessor/successor metadata;
- no topic classifier enum like `magic_system`/`character_notes` beyond LLM document role;
- reduction/aggregation fixture coverage for contradictory aliases and loose lore is incomplete.

## Budget Policy

Current budgets:

- `global_max_tokens = 9000`
- `chapter_max_tokens = 3000`
- `chapter_reduce_max_tokens = 3000`
- `global_batch_input_token_budget = 6000`
- `global_batch_prompt_overhead_tokens = 5000`
- `max_global_text_chars = 350000`
- `chapter_chunk_overlap_paragraphs = 1`
- SP070 DeepSeek profiles use `default_max_output_tokens = 8192`

Gaps:

- DeepSeek-specific model capabilities are not registered in `model_registry.py`;
- provider profiles are not yet bridged into `TokenBudget` planning;
- source text budget vs output reserve per provider/model needs explicit preflight assertions.

## Reduction/Aggregation

Existing support:

- large chapter partial outputs reduce via `CHAPTER_REDUCTION_PROMPT`;
- global normalization includes merge plan aggregation;
- auxiliary ingestion enriches existing entities or creates future-primary entities;
- review state and uncertainty paths exist.

Gaps:

- object/event/relation dedupe and conflict policy needs provider-free fixture coverage;
- source span preservation through reduction is partial;
- invalid chunk output reducer behavior exists at runtime but lacks synthetic preflight fixtures.

## Provider Harness Integration

SP070 profiles fit at `bootstrap_chapter_extraction` prompt construction.
DeepSeek BYOK constraints remain:

- use enabled model only;
- no global auto-switch;
- no OpenAI fallback;
- same-model rerun guidance only.

Needed integration:

- record `provider_profile_id` per chunk;
- emit thin output warnings per chunk;
- attach failure modes to chunk audit;
- use profile output token budget during chunk planning.

## Prompt Experiment Observability Integration

SP071 helpers can classify per-chunk failure modes and produce future matrix reports.
Future chunking matrices should emit:

- chunk-level variant diff report;
- failure mode report;
- decision report;
- privacy-safe summary.

## Risks

- Running a real private DeepSeek e2e before fixture preflight could hide source-span loss.
- Current subchunk strings make provenance harder to audit.
- Budget policy may mismatch SP070 profile output budget.

## Preflight Decision

Assessment: `chunking_reduction_preflight_ready_with_gaps`

Existing pipeline is clear enough to proceed, but missing chunk metadata/source span and provider-free reducer fixtures should be handled first.

## Next Phase

`Phase 1.3.M-b5c-4c — Implement Missing Chunking/Reduction Gaps`

## SP-074 Gap Implementation

Closed in this phase:

- structured chunk records via `StructuredSourceChunk`;
- structured split metadata with chunk ids, spans, predecessor/successor links, and source spans;
- auxiliary chunk `char_start` / `char_end`;
- DeepSeek budget bridge from SP-070 profiles into provider-free token planning helpers;
- provider-free chunk -> partial mock -> reduction fixture e2e;
- private decision packet contract for future real runs;
- long provider run contract for progress, stall, timeout, and cancellation handling.

Remaining gaps:

- runtime chunk reducer still uses production prompts rather than provider-free reducer helper;
- prompt overhead estimation is still caller-supplied;
- reasoner remains unavailable in current DeepSeek family discovery baseline.

Readiness:

- provider-free chunking/reduction fixture e2e is ready;
- path is ready for controlled real DeepSeek dry-run with private decision packet;
- no provider calls were made in this phase.

## SP-076 Source Refs and Output Budget Protocol

Closed or improved in this phase:

- reduction carry-forward rules for item-level `source_refs` with chunk-level fallback;
- dynamic output budget resolver with source-of-decision metadata;
- prompt injection for output budget control;
- provider-free `response_control` contract;
- truncation detection taxonomy and continuation/repair contract;
- usage / finish_reason capture requirements for private decision packets;
- candidate summary budget guidance to reduce truncation risk.

Remaining gap:

- larger real DeepSeek rerun should verify new source-ref carry-forward end to end after script/runtime adoption.


## SP-081 Natural Chunking Threshold Calibration Patch

Closed or improved in this phase:

- provider-agnostic `NaturalChunkingThresholdPolicy` separates hard context fit from soft quality split;
- soft split thresholds can produce natural multi-chunk before hard overflow;
- provider profiles can suggest chunking preferences without owning planner decisions;
- patch continuation chapter validation rejects `valid_json_wrong_chapter` before merge;
- thin/no-item reduction diagnostics explain source-ref coverage drops;
- provider-free replan simulation estimates natural multi-chunk call counts before provider runs.

Boundary:

- chunking threshold logic is TextifAI core;
- DeepSeek model/profile recommendations stay provider-specific hints only.
