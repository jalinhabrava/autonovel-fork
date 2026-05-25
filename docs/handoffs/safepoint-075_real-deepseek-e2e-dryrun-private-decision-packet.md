# Real DeepSeek E2E Dry-run with Private Decision Packet

## Product Reading

`SP-074` closed provider-free chunking/reduction readiness gaps. This phase ran a controlled real DeepSeek E2E dry-run to test SP-070 profiles with SP-074 structured chunk metadata and private decision packet capture. Product question was not overlay selection; it was whether chunked input shape, budget bridge, private traceability, partial extraction, and reduction are usable before larger E2E.

## Scope

- DeepSeek only.
- Models: `deepseek-v4-flash`, `deepseek-v4-pro`.
- Chapters: `ch_002`, `ch_003`.
- Private prompts/outputs in `/tmp` only.
- Public reports are privacy-safe.
- No write-back.

## Files Changed

- `scripts/dev/real_deepseek_e2e_dryrun.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/real_deepseek_e2e_execution_plan_after_sp074.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/real_deepseek_e2e_summary_after_sp074.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/real_deepseek_e2e_chunk_results_after_sp074.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/real_deepseek_e2e_reduction_summary_after_sp074.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/real_deepseek_e2e_decision_after_sp074.json`
- `docs/handoffs/safepoint-075_real-deepseek-e2e-dryrun-private-decision-packet.md`

## Environment Check

`DEEPSEEK_API_KEY` present. Secret not printed. Real provider calls executed after `--allow-provider-calls`.

## Execution Plan

Planned provider calls: `8`, below cap `24`.

## Source / Chapters

Source reference: `/home/david/OnT/王者の杖.md`. Source content not committed. Chapters: `ch_002`, `ch_003`.

## Models and Profiles

- `deepseek-v4-flash` with `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`.
- `deepseek-v4-pro` with `deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1`.

## Structured Chunk Plan

Each target chapter stayed within budget and produced one `StructuredSourceChunk`:

- `ch_002`: `source_f1e650917c_ch_002_chunk_001`, chars `2309-5013`, estimated tokens `676`.
- `ch_003`: `source_f1e650917c_ch_003_chunk_001`, chars `5015-7290`, estimated tokens `568`.

## Provider Calls

Executed `8` calls:

- 4 partial extraction calls.
- 4 reduction calls.

## Long-run Handling

Progress log written incrementally. Pro calls took longer but finished; no cancellation.

## Runtime Results

Assessment: `real_deepseek_e2e_dryrun_partial_success`.

Partial extraction:

- `ch_002` Flash: valid JSON, score `57.5`.
- `ch_002` Pro: invalid JSON, debuggable in packet.
- `ch_003` Flash: invalid JSON, debuggable in packet.
- `ch_003` Pro: valid JSON, score `39.0`.

## Chunk-level Results

Chunk source spans were preserved in public chunk results and private packet metadata.

## Reduction/Aggregation Results

All four reduction calls returned parseable/valid JSON:

- `ch_002` Flash: score `57.5`.
- `ch_002` Pro: score `37.0`.
- `ch_003` Flash: score `40.0`.
- `ch_003` Pro: score `39.0`.

Reduction output did not preserve item-level `source_refs`; source refs survive in chunk metadata/private trace, not in reduced entity items. This is why assessment is partial success, not passed.

## Thin Output Warnings

Most valid reductions only had `model_profile_experimental`. `ch_002` Pro reduction also warned `zero_unresolved_mentions_in_ambiguous_context`.

## Failure Modes

Chunk-level failures:

- `ch_002` Pro partial: `invalid_json_unknown`.
- `ch_003` Flash partial: `invalid_json_unknown`.

Reductions had no failure modes.

## Comparison vs Previous Non-chunked Runs

SP-069 best scores:

- `ch_002`: `26.5`.
- `ch_003`: `25.0`.

SP-075 best reduction score:

- `57.5` on `ch_002` Flash.

This suggests the structured chunk/reduction flow can produce denser useful JSON, but source-ref preservation still blocks larger E2E confidence.

## Private Decision Packet

Root path:

`/tmp/textifai_private_provider_runs/sp075_real_deepseek_e2e/20260525T104441Z`

Key files to upload first to ChatGPT:

1. `README.md`
2. `matrix_summary_private.md`
3. `decision_notes_private.md`
4. `chunk_plan_private.md`
5. `reduction_trace_private.md`
6. Best run folder: `ch_002__deepseek_v4_flash/reduction/`
7. Failure examples: `ch_002__deepseek_v4_pro/source_f1e650917c_ch_002_chunk_001/` and `ch_003__deepseek_v4_flash/source_f1e650917c_ch_003_chunk_001/`

## Handoff Visibility Summary

The public reports include model/profile/chapter/chunk ids, char ranges, token estimates, call counts, parseability, validation, counts, scores, failure modes, warnings, reduction status, packet root, and recommended private files.

## Product Decision

`real_deepseek_e2e_dryrun_partial_success`.

## What Worked

- SP-074 structured metadata generated traceable chunk plan.
- Private packet generated all required per-run and matrix files.
- DeepSeek calls completed under cap.
- Reduction outputs were valid for all chapter/model runs.
- Flash on `ch_002` and Pro on `ch_003` showed strong chunk-level signals.

## What Failed

- Two partial extraction outputs were invalid JSON.
- Reduced output did not preserve item-level source refs/source spans.
- Larger E2E should wait until reduction prompt or post-processor carries source refs into final items.

## Data Written

- Public privacy-safe fixtures under `tests/fixtures/textifai/real_provider_dryrun/expected/`.
- Private packet under `/tmp/textifai_private_provider_runs/sp075_real_deepseek_e2e/20260525T104441Z`.

## Privacy / Non-committed Output

Prompts and provider outputs stayed in `/tmp`; not staged or committed.

## Tests Added / Updated

Updated real provider dryrun guards for SP-075 reports and script flags.

## Validation Performed

Required unittest suite passed after run.

## Safety Constraints

- No OpenAI.
- No write-back.
- No `/tmp` commit.
- No prompt/output private commit.
- Provider calls capped: `8/24` used in final run.

## Known Limitations

- No current `/models` discovery rerun was committed; visibility used SP-069 baseline plus successful calls to both visible models.
- Source refs are not item-level in reduction output.

## Future Extensions

- Add source-ref carry-forward in reduction prompt/post-processor.
- Add retry policy for invalid partial JSON within same provider/model/profile.
- Review private packet with ChatGPT before larger private e2e.

## Runtime Changes

Dev-only script and privacy-safe reports/tests.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4e — Review Real DeepSeek E2E Packet and Decide Larger Dry-run`
