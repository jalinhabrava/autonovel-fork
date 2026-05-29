# Safepoint 112A — Source map chunks + evidence resolution

## Scope
SP-112A closes chunk-backed evidence resolution contract for project-owned review evidence without provider calls, ingestion reruns, VaERL write-back, patch queue, or editor write-back.

## Files changed
- `textifai/import_review/evidence_store.py`
- `textifai/vaerl/review_queue.py`
- `textifai/web_viewer/project_reader.py`
- `tests/test_textifai_source_map_chunks_evidence_resolution.py`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/source_map_chunks_contract_after_sp111.json`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/evidence_resolution_contract_after_sp111.json`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/review_evidence_runtime_after_sp111.json`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/evidence_modal_ui_contract_after_sp111.json`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/source_map_chunks_decision_after_sp111.json`
- `tests/fixtures/textifai/source_map_chunks_evidence_resolution/expected/evidence_coverage_backfill_after_sp112a.json`
- `tests/fixtures/textifai/source_structure_chapter_manifest/expected/sp111_runtime_verification_after_sp110.json`

## Outcome
- `source_map.chunks` now materializes project-owned chunk entries with `chunk_id`, `chapter_id`, `chapter_path`, `char_start`, `char_end`, `text_hash`, and `excerpt` or `resolvable_range`.
- `evidence_index` now carries stable resolution fields: `review_item_id`, `source_ref_key`, `chunk_id`, chapter mapping, offsets, reason, and technical pointer.
- Review hydration now resolves evidence from `evidence_index -> source_map.chunks -> chapter markdown` in that order.
- Viewer payload keeps excerpt/context as primary evidence and leaves pointer only as technical detail.

## Runtime verification
- Viewer 8872 remained active and returned HTTP 200 on `/`.
- Focused runtime payload verification previously confirmed:
  - `source_map_chunks_count = 18`
  - `evidence_index_item_count = 70`
  - `evidence_refs = 70`
  - `evidence_excerpt_resolved_count = 6`

## Coverage audit
- Total evidence: `70`
- Excerpts before: `6`
- Backfilled deterministically: `0`
- Excerpts after: `6`
- Unresolved: `64`
- Main blocker: `chunk_relative_offsets_without_chunk_text = 61`

## Final assessment
`source_map_chunks_ready_evidence_legacy_blocked`

## Blocker
Current project cannot fully resolve evidence because legacy refs are chunk-relative without persisted chunk text or chapter-valid ranges.

## Next ingestion requirement
`source_map.chunks[]` must persist stable `source_ref_key`, `chunk_id`, `chapter_id`, `chapter_path`, `char_start`, `char_end`, `text_hash`, plus `excerpt` or `resolvable_range`.

## Guardrails kept
- No provider calls.
- No new ingestion.
- No VaERL write-back.
- No patch queue.
- No source prose in commit-safe reports.
