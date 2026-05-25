# Safepoint 073 — Chunking/Reduction Preflight with SP070 DeepSeek Profiles

## Chunking/Reduction Preflight with SP070 DeepSeek Profiles

## Product Reading

`SP-070` packaged DeepSeek profiles, `SP-071` added observability, and `SP-072` showed no clear targeted prompt improvement. Therefore the product should return to chunking/reduction, but by auditing and extending the existing pipeline rather than rebuilding it from scratch.

## Scope

Provider-free inventory, reports, docs, and synthetic tests for existing chunking/reduction readiness.

## Files Changed

- `tests/test_textifai_chunking_reduction_preflight.py`
- `tests/fixtures/textifai/chunking_preflight/expected/chunking_reduction_existing_pipeline_inventory_after_sp072.json`
- `tests/fixtures/textifai/chunking_preflight/expected/chunking_budget_policy_after_sp072.json`
- `tests/fixtures/textifai/chunking_preflight/expected/reduction_aggregation_inventory_after_sp072.json`
- `tests/fixtures/textifai/chunking_preflight/expected/chunking_provider_harness_integration_plan_after_sp072.json`
- `tests/fixtures/textifai/chunking_preflight/expected/chunking_reduction_preflight_decision_after_sp072.json`
- `docs/textifai-chunking-reduction-preflight.md`
- `docs/handoffs/safepoint-073_chunking-reduction-preflight-deepseek-observability.md`

## Existing Pipeline Inventory

Found production modules for chapter detection, semantic markdown splitting, chunked chapter extraction/reduction, auxiliary document ingestion, token budgets, model capabilities, and source inventory.

## Structured Document Chunking

Ready areas:

- `detect_story_chapters` preserves chapter-level char ranges.
- `split_markdown_semantically` splits headings/paragraphs and supports overlap.
- `structured_bootstrap_v1` has chunked partial extraction and chapter reduction.

Gaps:

- structured subchunks are plain strings, not metadata-rich chunk objects.
- no first-class subchunk char ranges or predecessor/successor links.

## Unstructured Author Notes Chunking

Ready areas:

- auxiliary documents are indexed and chunked by heading sections.
- chunks preserve source id, chunk id, heading path, author hint and char count.

Gaps:

- no char_start/char_end per auxiliary chunk.
- chunk kind is coarse; topic kind still LLM-derived.

## Budget Policy

Ready areas:

- `TokenBudget` exists.
- bootstrap config exposes global/chapter/reduction token limits.
- SP070 profiles expose 8192 output token default.

Gaps:

- DeepSeek model capabilities absent from `model_registry.py`.
- provider profile budget not wired into token planning.

## Reduction/Aggregation Inventory

Ready areas:

- chapter partial reduction exists.
- global merge_plan aggregation exists.
- auxiliary enrichment aggregation exists.

Gaps:

- object/event/relation dedupe fixture coverage incomplete.
- source span preservation through reduction partial.

## Provider Harness Integration

SP070 profiles can be applied to `bootstrap_chapter_extraction` chunks. Needed: per-chunk `provider_profile_id`, thin warnings, failure modes, and budget bridge.

## Prompt Experiment Observability Integration

SP071 taxonomy can classify per-chunk failures and support future matrix reports.

## Preflight Assessment

Assessment: `chunking_reduction_preflight_ready_with_gaps`

## What Is Ready

- Existing production pipeline is clear.
- Provider-free chunking APIs can be exercised synthetically.
- DeepSeek SP070 profiles are available.
- SP071 observability is available.

## What Has Gaps

- Subchunk metadata/source spans.
- DeepSeek budget bridge.
- Provider-free reduction fixture e2e.
- Author note topic-kind metadata.

## Tests Added / Updated

Added `tests/test_textifai_chunking_reduction_preflight.py`.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`

## Safety Constraints

- No provider calls.
- No network.
- No private novel e2e.
- No write-back.
- No `/tmp` commit.

## Known Limitations

- This is an audit/preflight, not full e2e.
- Existing chunking gaps are documented but not fixed here.

## Future Extensions

- Introduce metadata-rich structured subchunk records.
- Add provider-free reduction fixture e2e.
- Wire DeepSeek SP070 budgets into chunk planning.

## Runtime Changes

Provider-free tests/docs/reports only.

## Provider Calls

NO.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4c — Implement Missing Chunking/Reduction Gaps`
