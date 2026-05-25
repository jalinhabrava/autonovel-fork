# Larger DeepSeek E2E with Multi-chunk Chapters

## Product Reading
- SP-075 proved chunk -> partial -> reduction beats non-chunked runs.
- SP-076 added source refs, dynamic budget, truncation detection, response_control, continuation contract.
- SP-077 validated serious E2E and localized Pro reduction truncation.
- SP-078 recovered that case with compact Pro reduction and patch continuation.
- SP-079 validates larger multi-chunk E2E before broader/full-source runs.

## Scope
- Ran controlled larger DeepSeek E2E on selected chapters with forced-budget multi-chunk preflight.
- Models: Flash and Pro SP-070 profiles.
- Compact Pro reduction + patch continuation enabled.
- No OpenAI, no auto-switch, no write-back.

## Files Changed
- scripts/dev/real_deepseek_e2e_dryrun.py
- tests/test_textifai_real_provider_dryrun_guards.py
- tests/fixtures/textifai/real_provider_dryrun/expected/larger_deepseek_multichunk_*_after_sp078.json
- docs/handoffs/safepoint-079_larger-deepseek-e2e-multichunk.md

## Environment Check
- DEEPSEEK_API_KEY present: true. Secret not printed.

## Execution Plan
- planned calls: 26
- planned with continuation reserve: 34
- cap: 48
- actual calls: 29

## Source / Chapters
- Source: /home/david/OnT/王者の杖.md
- Chapters: ['ch_001', 'ch_002', 'ch_003', 'ch_005']
- Source content not committed.

## Natural vs Forced Multi-chunk
- Mode: forced_budget_preflight
- Natural splitter produced single chunks, so dev-only forced budget preflight used `--force-max-chunk-tokens 250`.
- Product budgets unchanged.

## Models and Profiles
- deepseek-v4-flash / deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1
- deepseek-v4-pro / deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1

## Structured Chunk Plan
- Multi-chunk runs confirmed: True
- Chunk counts by run: [{"run_id": "ch_001__deepseek_v4_flash", "chunks": 3}, {"run_id": "ch_001__deepseek_v4_pro", "chunks": 3}, {"run_id": "ch_002__deepseek_v4_flash", "chunks": 2}, {"run_id": "ch_002__deepseek_v4_pro", "chunks": 2}, {"run_id": "ch_003__deepseek_v4_flash", "chunks": 2}, {"run_id": "ch_003__deepseek_v4_pro", "chunks": 2}, {"run_id": "ch_005__deepseek_v4_flash", "chunks": 2}, {"run_id": "ch_005__deepseek_v4_pro", "chunks": 2}]

## Provider Calls
- Provider calls: 29 / 48.
- Continuations/patches triggered: 3.

## Long-run Handling
- Progress log written incrementally in private packet.
- Pro calls allowed to run; no premature cancellation.

## Output Budget / Usage / Finish Reason
- effective_max_output_tokens recorded per run/call.
- finish_reason and usage captured per call.
- reasoning_tokens captured where provider returned it.

## Runtime Results
- Assessment: larger_deepseek_e2e_multichunk_passed_with_review_warnings
- Valid reductions: 8/8
- Best reduction: ch_001__deepseek_v4_pro score=86.0

## Chunk-level Results
- All selected chapter/model runs had multiple chunks under forced preflight.
- Partial status tracked per chunk.

## Multi-chunk Audit
- Reduction consumed all usable partials for every run.
- Invalid/repaired partial count visible per run.
- Multi-ref items observed across chunks.

## Reduction/Aggregation Results
- All 8 reductions parseable and validation_ok.
- Pro compact reduction used on Pro runs.
- Patch merge used where truncation occurred.

## Source-ref Audit
- Item-level source_ref coverage: 1.0
- Missing source_ref runs: 0
- Parseable reduction runs: 8

## Truncation / Continuation Audit
- Triggered continuation count: 3
- Continuation problem count: 1
- Known warning: one Pro partial continuation remained non-parseable, but reduction stayed valid.

## Failure Modes
- finish_reason_length on multi-chunk reductions recovered via patch merge.
- pro_reasoning_budget_exhaustion observed on one Pro partial.

## Comparison vs SP077 and SP075
- SP075 best: 57.5.
- SP077 best: 59.0.
- SP079 best: 86.0.
- SP079 source_ref coverage: 1.0.

## Private Decision Packet
- Root: /tmp/textifai_private_provider_runs/sp079_larger_deepseek_multichunk/20260525T140227Z
- Upload first:
  1. matrix_summary_private.md
  2. multi_chunk_audit_private.md
  3. source_ref_audit_private.md
  4. truncation_recovery_audit_private.md
  5. reduction_trace_private.md
  6. decision_notes_private.md

## Handoff Visibility Summary
- Reports include selected chapters, forced vs natural status, models/profiles, calls, budgets, usage, finish_reason, per-run scores, source_ref coverage, continuation status.

## Product Decision
- larger_deepseek_e2e_multichunk_passed_with_review_warnings

## What Worked
- Multi-chunk forced preflight ran under cap.
- All reductions parseable/valid.
- Source_refs coverage stayed 1.0.
- Patch continuation recovered truncating reductions.

## What Failed
- Natural chunking did not create multi-chunk in selected chapters with default budgets.
- One Pro partial continuation did not parse, though reduction recovered from available partials.

## Data Written
- Privacy-safe fixtures in tests/fixtures/textifai/real_provider_dryrun/expected.
- Private packet under /tmp only.

## Privacy / Non-committed Output
- No prompt/output private files committed.
- No /tmp committed.
- API key not committed.

## Tests Added / Updated
- Provider-free report parsing/privacy/cap/multichunk/source_ref/truncation checks.

## Validation Performed
- Full required unittest suite run in SP-079.

## Safety Constraints
- Max 48 calls.
- No OpenAI.
- No auto-switch.
- No write-back.

## Known Limitations
- Forced multi-chunk is dev-only; natural chunking calibration remains.
- Section-wise reduction may be useful if Pro partial/reduction truncation grows in broader runs.

## Future Extensions
- Broader E2E with calibrated natural chunking.
- Section-wise reduction policy for long chapters.

## Runtime Changes
- Added dev-only `--force-max-chunk-tokens` and chunk audit reports.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4i — Broader DeepSeek E2E on Additional Chapters (Natural Chunking Calibration)
