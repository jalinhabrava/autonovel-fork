# Natural Chunking Threshold Calibration Patch

## Product Reading
- SP-080 ran broader real DeepSeek E2E on 8 chapters with natural chunking.
- 42 calls under cap 64, 16/16 valid reductions, budgets/usage/finish_reason captured.
- But natural chunking produced 16 single-chunk rows and 0 multi-chunk rows.
- SP-081 focuses on provider-agnostic threshold calibration before full-novel readiness.

## Scope
- Added provider-free natural threshold policy (hard vs soft split).
- Added provider suggestion hook for chunking preferences.
- Added patch continuation chapter-id validation before merge.
- Added thin/no-item diagnostics for source-ref coverage interpretation.
- Added provider-free replan simulation and SP-081 privacy-safe reports.
- No OpenAI, no auto-switch, no write-back, no provider call required.

## Files Changed
- textifai/import_review/batch_planner.py
- textifai/import_review/chunking_reduction_preflight.py
- textifai/import_review/provider_prompt_profiles.py
- textifai/import_review/deepseek_family_profiles.py
- scripts/dev/real_deepseek_e2e_dryrun.py
- tests/test_textifai_chunking_reduction_preflight.py
- tests/test_textifai_real_provider_dryrun_guards.py
- tests/test_textifai_deepseek_family_profiles.py
- docs/textifai-chunking-reduction-preflight.md
- docs/textifai-output-budget-continuation-protocol.md
- docs/textifai-natural-chunking-thresholds.md
- tests/fixtures/textifai/real_provider_dryrun/expected/*after_sp080.json

## SP080 Findings
- Natural chunking stayed single-chunk on all selected chapter/model rows.
- Coverage drop was partly due to thin/no-item valid reductions.
- Some patch continuations returned valid JSON for wrong chapter.

## Natural Chunking Threshold Policy
- Added `NaturalChunkingThresholdPolicy` with:
  - `hard_max_source_tokens`
  - `soft_chunk_target_tokens`
  - `soft_chunk_max_tokens`
  - `min_chunk_tokens`
  - `preferred_overlap_paragraphs`
- Added `choose_natural_chunking_split` to classify hard vs soft split reason.

## Hard Context Fit vs Soft Quality Split
- Hard fit protects context safety ceiling.
- Soft split triggers earlier for ingestion quality and reduction robustness.
- Planner now supports `soft_quality_split` and `hard_budget_split` reasons.

## Threshold Calibration
- Added report: `natural_chunking_threshold_calibration_after_sp080.json`.
- Includes why SP-080 stayed single-chunk, 2/3 chunk sensitivity, proposed initial soft thresholds, and risk framing.

## Provider-specific Chunking Preferences
- Added optional `chunking_preferences` in `ProviderPromptProfile`.
- DeepSeek family profiles now suggest soft thresholds and Pro compact recommendation.
- Core planner still decides; provider only suggests.

## Replan Simulation
- Added provider-free simulation report: `natural_chunking_replan_simulation_after_sp080.json`.
- Compares old vs new natural chunk counts and estimates Flash+Pro call load + continuation reserve vs cap 64.

## Patch Continuation Chapter Validation
- Added pre-merge validation:
  - expected chapter id match,
  - continuation metadata chapter match,
  - expected chunk id family match.
- On mismatch: reject merge and classify `valid_json_wrong_chapter`.

## Thin / No-item Reduction Diagnostics
- Added diagnostics report: `thin_reduction_diagnostics_after_sp080.json`.
- Distinguishes true missing refs from valid no-item/thin reductions.
- Adds denominator explanation for source-ref coverage interpretation.

## Optional Real Validation
- Not executed in SP-081.
- Reason: phase remains provider-free by default; next phase should run small targeted natural multi-chunk validation under cap 16.

## General Pipeline Learnings
- Core: hard/soft split thresholds, patch chapter validation, thin diagnostics, provider-free replan.
- Added report: `natural_chunking_general_pipeline_learnings_after_sp080.json`.

## DeepSeek-specific Learnings
- DeepSeek profiles suggest lower soft thresholds and Pro compact preference.
- Reasoning-token exhaustion remains provider-specific warning.
- Added report: `natural_chunking_provider_specific_learnings_after_sp080.json`.

## Abstraction Boundaries
- General core: threshold policy, split reasons, chunk metadata, patch validation framework, thin diagnostics.
- Provider-specific: model/profile ids, compact reduction preference, reasoning token heuristic, DeepSeek wording.

## Product Decision
- `natural_chunking_threshold_patch_ready_with_review_warnings`

## What Worked
- Provider-free threshold patch and diagnostics implemented.
- Patch wrong-chapter guard added before merge.
- Replan shows natural multi-chunk can be induced by calibrated soft thresholds.

## What Failed
- No real provider validation in this phase.
- Proposed thresholds still require real small-run confirmation.

## Data Written
- New SP-081 privacy-safe reports in `tests/fixtures/textifai/real_provider_dryrun/expected`.
- Docs and tests updated.

## Privacy / Non-committed Output
- No `/tmp` committed.
- No private prompts/outputs committed.
- No API keys committed.

## Tests Added / Updated
- Added chunking policy behavior and soft split tests.
- Added patch wrong-chapter rejection tests.
- Added thin/no-item diagnostics tests.
- Added SP-081 report parse/privacy guards.

## Validation Performed
- Full required unittest suite for phase run before commit.

## Safety Constraints
- No OpenAI.
- No auto-switch.
- No write-back.
- Optional real validation only if explicit low-cap plan.

## Known Limitations
- Soft thresholds need empirical tuning per corpus family.
- Replan uses token estimates, not semantic quality scoring.

## Future Extensions
- Small real natural multi-chunk validation under cap 16.
- Section-wise reduction for very dense chapters if needed.
- More robust chunk boundary quality metrics.

## Runtime Changes
- Added threshold policy and split-reason logic to chunk planner.
- Added patch chapter validation gate and thin diagnostics.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4k — Small Real DeepSeek Validation with Calibrated Natural Multi-chunk
