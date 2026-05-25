# Broader DeepSeek E2E with Natural Chunking Calibration

## Product Reading
- SP-079 proved chunk -> partial -> reduction works with forced multi-chunk preflight: 29 calls, 8/8 valid reductions, source_ref coverage 1.0, best score 86.0.
- SP-080 tests the next risk: natural planner calibration on more real chapters, without forcing multi-chunk by default.
- Product question: natural chunking thresholds fit selected real chapters, but need tuning before full-novel E2E.

## Scope
- Ran broader DeepSeek E2E on 8 real chapters using natural chunking only.
- Kept SP-070 Flash/Pro profiles, Pro compact reduction, patch continuation, dynamic budgets, usage/finish_reason telemetry.
- No OpenAI, no auto-switch, no write-back.

## Files Changed
- tests/test_textifai_real_provider_dryrun_guards.py
- tests/fixtures/textifai/real_provider_dryrun/expected/natural_chunking_calibration_plan_after_sp079.json
- tests/fixtures/textifai/real_provider_dryrun/expected/broader_deepseek_natural_chunking_*_after_sp079.json
- tests/fixtures/textifai/real_provider_dryrun/expected/broader_deepseek_general_pipeline_learnings_after_sp079.json
- tests/fixtures/textifai/real_provider_dryrun/expected/broader_deepseek_provider_specific_learnings_after_sp079.json
- docs/handoffs/safepoint-080_broader-deepseek-natural-chunking-calibration.md

## Environment Check
- DEEPSEEK_API_KEY present: true. Secret not printed or committed.

## Chapter Selection
- Source: /home/david/OnT/王者の杖.md
- Baseline chapters: ch_001, ch_002, ch_003, ch_005.
- Additional long chapters: ch_097, ch_106, ch_114, ch_115.
- Source text not committed; reports include only hashes, ids, char ranges, token estimates, metrics, and packet path.

## Natural Chunking Calibration
- Mode: natural.
- Natural chunk rows: 16 chapter/model rows.
- Single-chunk rows: 16.
- Multi-chunk rows: 0.
- Under-split rows: 0.
- Interpretation: selected chapters fit current productive budgets; no default chunking change made.

## Threshold Sensitivity
- Effective source_text_budget_tokens: 6000.
- Natural max chunk tokens observed: 107808.
- threshold_for_2_chunks / threshold_for_3_chunks fields recorded for each row.
- Recommendation: add threshold calibration patch before full novel, rather than force multi-chunk by default.

## Execution Plan
- Planned provider calls: 32.
- Planned with continuation reserve: 48.
- Cap: 64.
- Actual calls: 42.
- Selected subset: Flash + Pro for 8 chapters under cap, with continuation reserve.

## Models and Profiles
- deepseek-v4-flash / deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1
- deepseek-v4-pro / deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1
- Pro compact reduction and patch continuation enabled.

## Provider Calls
- Provider calls: 42 / 64.
- Continuations/patches triggered: 10.
- Progress log written incrementally in private packet.

## Long-run Handling
- Calls logged with run index, chapter, model, chunk, duration, output size, and failure_mode.
- Pro calls were allowed to finish; no premature cancellation.

## Runtime Results
- Assessment: natural_chunking_good_but_needs_threshold_tuning.
- Valid reductions: 16/16.
- Best score: 67.0.
- Write-back: NO.

## Chunk-level Results
- Natural planner produced one chunk per selected chapter/model row.
- Chunk ids, char ranges, source spans, estimated tokens, and parseability recorded privacy-safe.

## Reduction Results
- 16/16 reductions parseable and valid.
- Flash remained strong on longer selected chapters.
- Some Pro outputs remained thin despite parseability.

## Source-ref Audit
- Item-level source_ref coverage ratio: 0.8125.
- Parseable reduction runs: 16.
- Missing source_ref runs: 3, tied to thin parseable reductions with no section items.
- Source_refs remain reliable where reductions produce items.

## Truncation / Continuation Audit
- Triggered continuation count: 10.
- Continuation problem count: 1.
- Continuation statuses: not_triggered=22, patch_merged=6, executed_replaced_primary=3, executed_but_not_parseable=1.
- Failure warnings include valid_json_wrong_chapter and Pro reasoning budget exhaustion.

## Comparison vs SP079 and SP077
- SP077: 13 calls, best score 59.0, one Pro reduction truncation localized.
- SP079: 29 calls, forced multi-chunk, best score 86.0, source_ref coverage 1.0.
- SP080: 42 calls, natural single-chunk, best score 67.0, 16/16 reductions valid, source_ref coverage 0.8125.

## General Pipeline Learnings
- Structured chunk metadata, source spans, dynamic budget resolution, telemetry capture, truncation detection, patch continuation, and private packet pattern are general TextifAI capabilities.
- Natural chunking calibration belongs in provider-agnostic planner thresholds.
- Patch continuation is useful as a provider-agnostic recovery mechanism, but provider adapters must supply reliable telemetry.

## DeepSeek-specific Learnings
- Flash profile stayed useful and efficient.
- Pro profile can produce valid but thin outputs when reasoning/output budget pressure appears.
- Pro compact reduction and patch continuation remain DeepSeek harness policies, not universal core defaults.
- DeepSeek-specific warnings: reasoning_tokens exhaustion, finish_reason=length, wrong-chapter patch continuation.

## Abstraction Boundaries
- Generalizable: chunk metadata, source_refs, reduction pipeline, usage/finish_reason abstraction, truncation/continuation framework, dynamic budget resolver, private packet, long-run monitoring.
- DeepSeek-specific: model ids, profile ids, overlay wording, Pro compact reduction policy, reasoning_tokens heuristic, DeepSeek output defaults, DeepSeek truncation/recovery behavior.

## Provider Adapter Implications
- Provider adapters should expose usage, finish_reason, optional reasoning tokens, response ids, and provider-specific max-token field names through generic telemetry.
- Core TextifAI should own chunking, source_refs, truncation classification, patch merge, and decision packet shape.
- Provider family profiles should own wording, caps, compact mode policy, and model-specific recovery hints.

## Private Decision Packet
- Root: /tmp/textifai_private_provider_runs/sp080_broader_deepseek_natural_chunking/20260525T145328Z
- Upload first:
  1. README.md
  2. execution_plan_private.md
  3. natural_chunking_calibration_private.md
  4. matrix_summary_private.md
  5. source_ref_audit_private.md
  6. truncation_recovery_audit_private.md
  7. general_pipeline_learnings_private.md
  8. deepseek_specific_learnings_private.md
  9. abstraction_boundaries_private.md
  10. decision_notes_private.md

## Product Decision
- natural_chunking_good_but_needs_threshold_tuning.
- Do not run full novel yet; add natural chunking threshold calibration patch first.

## What Worked
- Broader 8-chapter DeepSeek E2E ran under cap.
- All reductions were parseable and valid.
- Dynamic budget and usage/finish_reason telemetry were captured per call.
- Patch continuation handled several truncation cases without auto-switch.

## What Failed
- Natural chunking did not produce multi-chunk rows for selected chapters under current budgets.
- Source_ref coverage dropped because some parseable Pro reductions were thin/no-item.
- Some patch continuations returned valid JSON for wrong chapter.

## Data Written
- Privacy-safe fixtures under tests/fixtures/textifai/real_provider_dryrun/expected.
- Private decision packet under /tmp only.

## Privacy / Non-committed Output
- No prompts, raw outputs, source text, API keys, /tmp files, runs, or vault data committed.

## Tests Added / Updated
- Added SP-080 report parse/privacy/cap/natural-threshold/source_ref/truncation/general-vs-provider-specific guard test.

## Validation Performed
- Full required unittest suite planned for this safepoint before commit.

## Safety Constraints
- Max 64 calls.
- No OpenAI.
- No auto-switch.
- No write-back.
- No private prompt/output commit.

## Known Limitations
- Current natural splitter may be too permissive for full-novel calibration.
- Pro compact mode helps parseability but not always density.
- Wrong-chapter patch continuation needs tighter patch prompt/runtime validation.

## Future Extensions
- Add provider-agnostic natural chunking threshold calibration patch.
- Add section-wise reduction for long/high-risk chapters.
- Tighten patch continuation chapter-id validation before merge.

## Runtime Changes
- No product runtime default changed.
- Added SP-080 privacy-safe reports and tests.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4j — Natural Chunking Threshold Calibration Patch
