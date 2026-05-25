# Broader Real DeepSeek Natural Multi-chunk Dry-run

## Product Reading
- SP-082 validated live calibrated natural multi-chunk without `--force-max-chunk-tokens` on `ch_097`.
- SP-082 showed 3 natural chunks, Flash + Pro under cap 16, 10 provider calls, 2/2 valid reductions, source_ref coverage 1.0, and wrong-chapter patch merge count 0.
- SP-083 scales the same calibrated natural chunking policy from one chapter to four real chapters before any full-source dry-run.
- Product risk shifted from “does natural multi-chunk work?” to “does it stay stable across several real chapters and map failures to writer-friendly retry UX?”.

## Scope
- Broader real DeepSeek dry-run on natural multi-chunk chapters only.
- No full novel.
- No force flag.
- No OpenAI, no auto-switch, no write-back.
- Reports committed are privacy-safe only; private packet stays in `/tmp`.

## Files Changed
- `scripts/dev/real_deepseek_e2e_dryrun.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `docs/handoffs/safepoint-083_broader-natural-multichunk-dryrun.md`
- `tests/fixtures/textifai/real_provider_dryrun/expected/broader_natural_multichunk_*_after_sp082.json`

## Environment Check
- `DEEPSEEK_API_KEY` present: true.
- Secret verified by length/prefix/suffix/hash only.
- No secret printed in reports or committed files.

## SP082 Context
- SP-082 validated `ch_097` live with calibrated natural chunking.
- Remaining warnings: one Flash partial `invalid_json_unknown`; one Pro partial reasoning pressure with non-parseable continuation.
- Final reductions were still valid and traceable.

## Chapter Selection
- Selected chapters: `ch_097`, `ch_106`, `ch_114`, `ch_115`.
- Why: all generated natural multi-chunk plans under calibrated policy and fit cap 48 with reserve.
- Variety: baseline known chapter plus additional long/medium-long chapters from SP-080/SP-081 calibration set.

## Natural Chunking Policy
- Policy: `natural_quality_split_v1`.
- Soft target: 1200 estimated tokens.
- Soft max: 1800 estimated tokens.
- Min chunk: 450 estimated tokens.
- Split reason observed: `soft_quality_split`.
- Force flag used: no.

## Execution Plan
- Planned runs: 8 chapter/model rows.
- Planned base calls: 31.
- Continuation reserve: 16.
- Planned total with reserve: 47.
- Cap: 48.
- Natural multi-chunk expected in every planned row.

## Natural Multi-chunk Validation
- Real natural multi-chunk observed across 4 chapters.
- Chunk counts: `ch_097` 3, `ch_106` 3, `ch_114` 3, `ch_115` 2 Flash / 3 Pro.
- Source spans, char ranges, split reasons, and predecessor/successor metadata recorded.

## Models and Profiles
- `deepseek-v4-flash` / `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`
- `deepseek-v4-pro` / `deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1`
- Pro compact reduction enabled.
- Patch continuation enabled.

## Provider Calls
- Actual provider calls: 43 / 48.
- Extra calls came from continuation/patch recovery.
- Provider calls executed: YES.

## Long-run Handling
- Progress logged incrementally in `/tmp`.
- Pro calls were allowed to run; no premature cancellation.
- Per-call duration, output size, finish reason, usage, and failure mode captured.

## Runtime Results
- Assessment: `broader_natural_multichunk_passed_with_review_warnings`.
- Valid reductions: 8/8.
- Source_ref coverage: 1.0.
- Continuations triggered: 12.
- Continuation problem count: 0 in final audit.

## Chunk-level Results
- Chunk rows: 23.
- Failure modes at chunk/continuation level: 5 `valid_json_wrong_chapter` continuation outputs.
- Wrong-chapter continuation outputs were rejected before merge.
- No forced chunks.

## Reduction Results
- `ch_097` Flash score 115.0; Pro score 76.5.
- `ch_106` Flash score 95.5; Pro score 35.0.
- `ch_114` Flash score 80.0; Pro score 97.5.
- `ch_115` Flash score 88.0; Pro score 37.5.
- 8/8 reductions parseable and valid.

## Source-ref Audit
- Item-level source_ref coverage ratio: 1.0.
- Parseable reduction runs: 8.
- Missing source_ref runs: 0.
- Coverage remained stable despite continuation and patch activity.

## Truncation / Continuation Audit
- Triggered continuation count: 12.
- Patch merges on reductions: 6.
- Wrong-chapter continuation outputs: 5 rejected.
- Pro reasoning pressure remains visible but recoverable at reduction stage.

## Patch Chapter Validation
- Wrong-chapter patch merge count: 0.
- Rejected wrong-chapter continuation count: 5.
- Valid patch merges accepted only after chapter validation.
- Core rule held: valid JSON for wrong chapter must not merge.

## Thin / No-item Diagnostics
- No-item reductions: 0.
- Thin-section warning count: 1 run (`ch_115__deepseek_v4_pro`).
- Source_ref denominator explanation recorded, so thin/no-item cases are not confused with missing source_refs.

## Internal Fail-only Rerun Plan
- Report: `broader_natural_multichunk_internal_fail_rerun_plan_after_sp082.json`.
- Safe rerun scope: affected chapters only.
- Retryable units include chapter/run ids, technical unit type, model/profile, reason, retry strategy, expected calls, and dependencies.
- Successful chapters are excluded from retry scope unless dependency requires it.

## User-facing Ingestion Outcome
- Report: `broader_natural_multichunk_user_ingestion_outcome_after_sp082.json`.
- Writer-facing status hides internal terminology.
- Outcome summary: 2 of 4 chapters ready; 2 chapters need a second pass (`ch_106`, `ch_115`).
- Shape: total chapters, ready count, retry count, affected chapter list, simple reason labels, primary/secondary action.
- No prompts, provider details, telemetry, source_refs, JSON, chunks, reductions, or patch terms are exposed.

## Writer-facing Retry CTA
- Primary action label: `Retry pending chapters`.
- Action id: `retry_pending_chapters`.
- Scope: `affected_chapters_only`.
- Product copy pattern: “X of Y chapters are ready. Z chapters need a second pass.”

## Technical-to-User Status Mapping
- Internal valid final output with warning units maps to writer `ready_with_warnings`.
- Internal repeated second-pass divergence or thin low-density output maps to `chapter_needs_second_pass` when final chapter can be safely retried alone.
- Internal thin/no-item diagnostics map to `manual_review_recommended` or `chapter_processed_with_warnings` when needed.
- Writer UI should not expose provider/model/telemetry terms.

## Comparison vs SP082/SP080/SP079
- SP079 proved forced multi-chunk e2e under dev forcing.
- SP080 proved broader natural e2e but produced zero multi-chunk rows.
- SP082 proved one real natural multi-chunk chapter.
- SP083 proves four real chapters can run natural multi-chunk with 8/8 valid reductions, but warning patterns justify review before full-source dry-run.

## General Pipeline Learnings
- Calibrated natural chunking scales beyond a single chapter.
- `soft_quality_split` can improve ingestion structure before hard context limits.
- Source spans and item-level source_refs remain stable in broader natural multi-chunk.
- Patch chapter validation and thin/no-item diagnostics belong in core TextifAI.
- Internal fail-only rerun planning and writer-facing outcome mapping are core product capabilities.

## DeepSeek-specific Learnings
- Flash remains useful and high-scoring on multi-chunk chapters.
- Pro compact reduction remains useful but shows recurring reasoning pressure and lower-density outputs on some chapters.
- Wrong-chapter continuation behavior is a DeepSeek-specific warning pattern; core validation should stay provider-agnostic.
- DeepSeek profiles should keep compact-reduction and reasoning-pressure handling in adapter/profile layer.

## Private Decision Packet
- Root: `/tmp/textifai_private_provider_runs/sp083_broader_natural_multichunk/20260525T170226Z`
- Upload first:
  1. `README.md`
  2. `execution_plan_private.md`
  3. `broader_multichunk_validation_private.md`
  4. `matrix_summary_private.md`
  5. `source_ref_audit_private.md`
  6. `truncation_recovery_audit_private.md`
  7. `patch_validation_private.md`
  8. `thin_reduction_diagnostics_private.md`
  9. `internal_fail_rerun_plan_private.md`
  10. `user_facing_ingestion_outcome_private.md`
  11. `decision_notes_private.md`

## Product Decision
- `broader_natural_multichunk_passed_with_review_warnings`

## What Worked
- Natural multi-chunk worked across 4 real chapters without force flag.
- Provider call count stayed below cap 48.
- 8/8 reductions were parseable and valid.
- Source_ref coverage stayed 1.0.
- Wrong-chapter outputs were not merged.
- Writer-facing outcome and fail-only rerun plan now exist as separate artifacts.
- Writer-facing counts stayed simple: 2 ready, 2 retry, 0 failed.

## What Failed
- Several continuation outputs returned valid JSON for wrong chapter.
- Pro showed low scores on `ch_106` and `ch_115`.
- `ch_115__deepseek_v4_pro` produced thin-section warnings.
- Full-source dry-run still needs cautious cap planning and retry UX.

## Data Written
- Privacy-safe SP-083 reports in `tests/fixtures/textifai/real_provider_dryrun/expected/`.
- Private packet under `/tmp/textifai_private_provider_runs/sp083_broader_natural_multichunk/20260525T170226Z/`.
- Handoff in `docs/handoffs/safepoint-083_broader-natural-multichunk-dryrun.md`.

## Privacy / Non-committed Output
- No `/tmp` committed.
- No prompts or raw provider outputs committed.
- No source novel text committed.
- No API key committed.
- User-facing outcome contains no internal provider/chunk/reduction terminology.

## Tests Added / Updated
- Added SP-083 guards for reports, cap, natural multi-chunk, split reasons, patch validation, thin diagnostics, source_ref audit, truncation audit, internal fail-only rerun, and writer-facing outcome privacy.
- Script now has builders for patch validation, thin diagnostics, internal rerun plan, writer outcome, and general/provider-specific learnings.

## Validation Performed
- Required unittest suite run in this phase.
- Broader real DeepSeek validation executed because plan fit cap 48 and key existed.

## Safety Constraints
- Max provider calls: 48.
- Actual provider calls: 43.
- No force flag.
- No OpenAI.
- No auto-switch.
- No write-back.
- No private output committed.

## Known Limitations
- Only 4 chapters, not full novel.
- Writer-facing outcome is report contract only, not UI implementation.
- Fail-only rerun plan is internal artifact only, not an executed retry workflow.
- Pro low-score cases need more calibration before full-source run.

## Future Extensions
- Add UI/reporting integration for writer-facing ingestion outcome.
- Add executable fail-only rerun command scoped to affected chapters.
- Plan controlled full-source dry-run with cap and retry budget.
- Tune DeepSeek Pro handling for reasoning pressure and thin outputs.

## Runtime Changes
- DeepSeek e2e dry-run can emit SP-083-style patch validation, thin diagnostics, internal rerun plan, writer-facing outcome, and learning reports.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- Phase 1.3.M-b5c-4m — Controlled full-source dry-run planning with fail-only retry UX contract.
