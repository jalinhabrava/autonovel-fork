# Implement Missing Chunking/Reduction Gaps

## Product Reading

`SP-073` found a real chunking/reduction pipeline and assessed it as `chunking_reduction_preflight_ready_with_gaps`. This phase closes minimum provider-free gaps before real DeepSeek E2E. TextifAI remains BYOK: user-selected models only, no automatic global routing, no provider calls here.

## Scope

Provider-free implementation only:

- structured subchunk records;
- structured chapter split metadata;
- auxiliary chunk char spans;
- DeepSeek SP-070 budget bridge;
- provider-free chunk -> partial mock -> reduction fixture;
- private decision packet contract;
- long provider run contract.

## Files Changed

- `textifai/import_review/batch_planner.py`
- `textifai/import_review/auxiliary_ingestion.py`
- `textifai/import_review/chunking_reduction_preflight.py`
- `textifai/import_review/deepseek_family_profiles.py`
- `textifai/import_review/model_registry.py`
- `textifai/import_review/token_budget.py`
- `tests/test_textifai_chunking_reduction_preflight.py`
- `tests/fixtures/textifai/chunking_preflight/expected/deepseek_budget_bridge_after_sp073.json`
- `tests/fixtures/textifai/chunking_preflight/expected/provider_free_chunking_reduction_fixture_e2e_after_sp073.json`
- `tests/fixtures/textifai/chunking_preflight/expected/private_decision_packet_contract_after_sp073.json`
- `tests/fixtures/textifai/chunking_preflight/expected/long_provider_run_contract_after_sp073.json`
- `docs/textifai-chunking-reduction-preflight.md`
- `docs/textifai-provider-run-decision-packets.md`
- `docs/handoffs/safepoint-074_implement-chunking-reduction-gaps.md`

## Structured Subchunk Records

Added `StructuredSourceChunk` with source/chapter ids, chunk id, section id, sequence, heading path, text, char spans, estimated tokens, kind, split reason, predecessor/successor, source span, budget profile id, and provider profile id.

Legacy `split_markdown_semantically` remains unchanged for callers that expect strings. New `split_structured_chapter_into_chunks` returns records.

## Structured Chapter Split Metadata

Structured chunks preserve document-relative char spans and stable chunk ids. Adjacent chunk links are set after split. Split reason distinguishes within-budget chapter from semantic budget split.

## Auxiliary Chunk Char Spans

Auxiliary chunks now include `char_start`, `char_end`, and `source_span`. Auxiliary source refs also carry char spans.

## DeepSeek Budget Bridge

Added provider-free bridge from SP-070 profiles:

- Flash profile output budget: `8192`;
- Pro profile output budget: `8192`;
- DeepSeek model capabilities added to model registry;
- token planning can carry provider/model/profile id, output tokens, prompt overhead, source budget, and safety margin.

## Provider-free Chunking/Reduction Fixture E2E

Added provider-free mock reducer helper for synthetic chunk partials. It aggregates objects/events/relations, preserves source refs, keeps review/local candidate state, marks simple duplicate critical items for review, and reports invalid partials without aborting.

## Private Decision Packet Contract

Documented future private packet layout under `/tmp/textifai_private_provider_runs/<matrix_or_run_id>`. Contract includes run manifest, prompts, redacted request payload, raw/parsed response, validation, failure mode, variant hypothesis, interpretation, and matrix summaries. Nothing is committable.

## Long Provider Run Contract

Documented progress log, output activity tracking, timeout/stall policy, and cancellation report fields for future long DeepSeek runs.

## What Is Ready

- Provider-free structured chunk metadata path.
- Auxiliary char spans.
- DeepSeek profile budget bridge baseline.
- Provider-free mock reduction fixture.
- Private decision packet contract.
- Long-run contract.

## What Still Has Gaps

- Runtime production reducer still uses provider prompts; mock reducer is fixture-only.
- Prompt overhead estimate remains caller supplied.
- Reasoner remains unavailable/unbridged.
- Single oversized heading section internal split remains future work.

## Tests Added / Updated

Updated `tests/test_textifai_chunking_reduction_preflight.py` with structured record, auxiliary span, budget bridge, provider-free reduction, and contract tests.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- full required suite before commit.

## Safety Constraints

- No provider calls.
- No network.
- No real e2e.
- No private prompt/output commit.
- No write-back.

## Known Limitations

Provider-free reducer proves auditability and metadata preservation, not final semantic merge quality.

## Future Extensions

- Wire structured records into production chunked extraction audit.
- Add provider-free reducer fixture for full bootstrap schema.
- Add real DeepSeek E2E private decision packet.

## Runtime Changes

Provider-free helpers and metadata improvements only.

## Provider Calls

NO.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4d — Real DeepSeek E2E Dry-run with Private Decision Packet`

## Assessment

`chunking_reduction_gaps_closed_for_provider_free_e2e`
