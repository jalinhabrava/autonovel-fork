# Small Real DeepSeek Validation with Calibrated Natural Multi-chunk

## Product Reading
- SP-080 proved natural DeepSeek E2E stability but produced zero natural multi-chunk rows.
- SP-081 added provider-free threshold policy, soft split reasons, patch chapter validation, and thin diagnostics.
- SP-082 validates those changes live with a small capped real run.

## Scope
- Real DeepSeek validation on one naturally multi-chunk chapter under cap 16.
- No force flag.
- Flash + Pro on same naturally split chapter.
- Compact reduction kept for Pro; patch continuation enabled.
- No OpenAI, no auto-switch, no write-back.

## Files Changed
- scripts/dev/real_deepseek_e2e_dryrun.py
- textifai/import_review/batch_planner.py
- tests/test_textifai_chunking_reduction_preflight.py
- tests/test_textifai_real_provider_dryrun_guards.py
- docs/handoffs/safepoint-082_calibrated-natural-multichunk-validation.md
- tests/fixtures/textifai/real_provider_dryrun/expected/calibrated_natural_multichunk_*_after_sp081.json
- tests/fixtures/textifai/real_provider_dryrun/expected/calibrated_natural_multichunk_general_pipeline_learnings_after_sp081.json
- tests/fixtures/textifai/real_provider_dryrun/expected/calibrated_natural_multichunk_deepseek_specific_learnings_after_sp081.json

## Environment Check
- DEEPSEEK_API_KEY present: true.
- Secret not printed or committed.

## SP081 Context
- NaturalChunkingThresholdPolicy active.
- Soft quality split expected to create natural multi-chunk on long chapters.
- Wrong-chapter patch validation active before merge.
- Thin/no-item diagnostics active in privacy-safe reports.

## Chapter Selection
- Selected chapter: ch_097.
- Why: replan predicted 3 natural chunks under calibrated policy; chapter already informative in prior phases; Flash+Pro fit under cap 16 with reserve.

## Natural Chunking Policy
- Used calibrated natural threshold policy from SP-081.
- No `--force-max-chunk-tokens`.
- Observed split reason: `soft_quality_split`.

## Execution Plan
- Planned calls: 8.
- Continuation reserve: 4.
- Planned total with reserve: 12.
- Cap: 16.
- Natural multi-chunk available: true.

## Natural Multi-chunk Validation
- Real natural multi-chunk observed: true.
- Chunk count per model: 3 for Flash, 3 for Pro.
- Predecessor/successor links and source spans preserved in chunk records.

## Models and Profiles
- deepseek-v4-flash / deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1
- deepseek-v4-pro / deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1
- Pro compact reduction enabled.

## Provider Calls
- Actual provider calls: 10 / 16.
- Extra calls beyond planned base came from continuation/patch recovery.

## Long-run Handling
- Progress log written incrementally in private packet.
- Pro not cancelled for latency.
- Call durations, output size, failure mode captured per step.

## Runtime Results
- Assessment: calibrated_natural_multichunk_validation_passed_with_review_warnings.
- Valid reductions: 2/2.
- Best score: 70.0 on Pro reduction.

## Chunk-level Results
- Flash partials: 2 parseable, 1 invalid_json_unknown.
- Pro partials: 2 parseable, 1 pro_reasoning_budget_exhaustion with failed continuation repair.
- Natural chunk rows show `soft_quality_split` in all produced chunks.

## Reduction Results
- Flash reduction: parseable, score 62.5.
- Pro reduction: parseable after patch merge, score 70.0.
- Multi-chunk reduction consumed several chunk partials and stayed valid.

## Source-ref Audit
- Item-level source_ref coverage ratio: 1.0.
- Missing source_ref runs: 0.
- Parseable reduction runs: 2.

## Truncation / Continuation Audit
- Triggered continuations: 2.
- Continuation problem count: 1.
- Pro partial continuation stayed non-parseable.
- Pro reduction patch continuation merged successfully.

## Patch Chapter Validation
- Patch validation framework active.
- Wrong-chapter patch count in this run: 0.
- Merged patch count: 1.
- No wrong-chapter valid JSON was merged.

## Thin / No-item Diagnostics
- No-item reductions: 0.
- Thin-section warnings may still appear at chunk level, but final reductions remained item-bearing and traceable.
- Source-ref coverage did not drop due to no-item outputs in final reductions.

## Comparison vs SP081/SP080/SP079
- SP081: provider-free only, no live validation.
- SP080: natural run stable but no multi-chunk.
- SP079: forced multi-chunk worked, but not natural.
- SP082: natural multi-chunk now works live without force flag.

## General Pipeline Learnings
- Soft threshold policy is now validated with a real natural multi-chunk chapter.
- Hard vs soft split distinction is useful and provider-agnostic.
- Patch chapter validation belongs in core pipeline, not provider adapter.
- Source-ref carry-forward remains stable in natural multi-chunk reduction.

## DeepSeek-specific Learnings
- Flash handled natural multi-chunk cleanly enough without continuation.
- Pro still shows reasoning budget pressure on one partial.
- Pro compact reduction + patch merge stayed useful on reduction stage.
- These remain DeepSeek-family harness learnings, not universal defaults.

## Private Decision Packet
- Root: /tmp/textifai_private_provider_runs/sp082_calibrated_natural_multichunk/20260525T162312Z
- Upload first:
  1. README.md
  2. execution_plan_private.md
  3. natural_multichunk_validation_private.md
  4. matrix_summary_private.md
  5. source_ref_audit_private.md
  6. truncation_recovery_audit_private.md
  7. patch_validation_private.md
  8. thin_reduction_diagnostics_private.md
  9. decision_notes_private.md

## Product Decision
- calibrated_natural_multichunk_validation_passed_with_review_warnings

## What Worked
- Natural calibrated thresholds produced real multi-chunk without force flag.
- Both final reductions were valid and parseable.
- Source-ref coverage stayed 1.0.
- Wrong-chapter patch prevention stayed active.

## What Failed
- One Flash partial returned invalid_json_unknown.
- One Pro partial continuation stayed non-parseable.
- Pro still shows reasoning-budget sensitivity.

## Data Written
- Privacy-safe SP-082 reports in tests/fixtures.
- Private packet under /tmp only.

## Privacy / Non-committed Output
- No prompts/raw outputs committed.
- No /tmp committed.
- No API key committed.
- No source prose committed.

## Tests Added / Updated
- Added SP-082 report parse/privacy/cap/split-reason/patch/thin guards.
- Extended chunking tests for oversized-section natural split.

## Validation Performed
- Full required unittest suite run.
- Real small DeepSeek validation executed because plan fit cap 16.

## Safety Constraints
- Cap 16 respected.
- No OpenAI.
- No auto-switch.
- No write-back.

## Known Limitations
- Only one chapter validated live in SP-082.
- Pro partial continuation still needs monitoring in broader runs.

## Future Extensions
- Broader real natural multi-chunk dry-run on more chapters.
- Optional tighter partial continuation strategy for Pro partials.

## Runtime Changes
- Script now applies calibrated natural threshold policy when no force flag is used.
- Oversized single sections can subdivide naturally under soft split.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4l — Broader Real DeepSeek Natural Multi-chunk Dry-run
