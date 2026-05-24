# DeepSeek Extraction Strategy Matrix

## Product Reading
- `SP-066` showed DeepSeek Flash has a viable prompt candidate, but not enough evidence to decide strategy.
- This phase expanded from single-chapter Flash tuning to a two-chapter Flash/Pro strategy matrix.
- Product question: can DeepSeek Flash be cheap primary extraction, does Pro justify fallback/tier use, and what retry policy is needed before returning to chunking/reduction work?

## Scope
- Verify branch, key visibility, and local `ch_002`/`ch_003` prompts.
- Extend dev matrix runner to support two chapters, Flash + optional Pro, explicit call cap, and chapter-aware validation.
- Execute Flash variants A-F on `ch_002` and `ch_003`.
- Execute Pro variants A/B on `ch_002` and `ch_003`.
- Commit only metrics, reports, tests, scripts, and handoff.

## Files Changed
- `scripts/dev/real_provider_dryrun.py`
- `scripts/dev/deepseek_prompt_matrix.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_strategy_matrix_summary_after_sp066.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_strategy_matrix_variants_after_sp066.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_strategy_matrix_ch002_report_after_sp066.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_strategy_matrix_ch003_report_after_sp066.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_strategy_matrix_decision_after_sp066.json`
- `docs/handoffs/safepoint-067_deepseek-extraction-strategy-matrix.md`

## Environment Check
- provider key present in Codex environment: `true`
- provider key length observed: `35`
- provider key sha8 observed: `29fc730d`

## Prompt Status
- `ch_002` prompt found in `/tmp`.
- `ch_003` prompt found in `/tmp`.
- `ch_002` prompt sha256: `74c437e8ed878d16eb7b7a2636b5cff6a51353ee632cd0c188f210e8c6ff677d`
- `ch_003` prompt sha256: `6dda905f672bddffe6794d9d79e6850fe11e3851e654265cdc8832d793feb7c7`
- No prompt text committed.

## Matrix Design
- Provider: `deepseek`.
- Models attempted: `deepseek-v4-flash`, `deepseek-v4-pro`.
- Max output tokens: `8192`.
- Response format JSON: `true`.
- Write-back: `false`.
- Output root: `/tmp/textifai_deepseek_strategy_matrix`.
- Hard call cap respected: `16`.

## Models Attempted
- Flash: attempted all A-F variants for both chapters.
- Pro: attempted A/B variants for both chapters.
- Pro was available enough to return completed responses; no model-unavailable block triggered.

## Variants Executed
- `variant_a_dense_explicit`
- `variant_b_dense_plus_check`
- `variant_c_section_targets_json_safe`
- `variant_d_schema_skeleton_plus_density`
- `variant_e_objects_events_relations_boost`
- `variant_f_two_stage_instruction`

## Provider Calls
- Planned calls: `16`.
- Executed calls: `16`.
- OpenAI calls: `0`.
- Write-back calls: `0`.

## Runtime Validation
- Flash valid runs: `3`.
- Flash invalid/failed validation runs: `9`.
- Pro valid runs: `3`.
- Pro invalid/failed validation runs: `1`.
- Result: DeepSeek strategy is promising but unstable; retry policy is mandatory.

## ch_002 Results
- Best overall: Flash `variant_b_dense_plus_check`, score `25.0`.
- Counts: `characters=4`, `places=3`, `concepts=4`, `objects=1`, `events=1`, `relations=3`, `unresolved_mentions=1`.
- Best Pro: `variant_b_dense_plus_check`, score `20.5`.
- ch_002 decision: Flash B outperformed Pro B by score and section coverage, but still below manual baseline on objects/events/relations/unresolved.

## ch_003 Results
- Best overall: Flash `variant_e_objects_events_relations_boost`, score `26.0`.
- Counts: `characters=2`, `places=1`, `concepts=1`, `objects=2`, `events=2`, `relations=5`, `unresolved_mentions=2`.
- Best Pro: `variant_b_dense_plus_check`, score `14.5`.
- ch_003 decision: Flash E performed best and Pro did not beat Flash.

## Flash Result
- Flash has valid high-scoring candidates across both chapters.
- Flash is not stable across variants: most Flash variants either invalidated JSON or failed validation.
- Flash should be treated as cheap candidate extraction with strict retry/fallback gates, not blind primary extraction.

## Pro Result If Attempted
- Pro was attempted.
- Pro produced valid outputs for 3 of 4 runs.
- Pro did not outperform best Flash candidate on either chapter by this scoring.
- Pro may still help reliability in some cases, but this run does not justify making Pro the default DeepSeek tier.

## Best Variant
- Best ch_002: Flash `variant_b_dense_plus_check`.
- Best ch_003: Flash `variant_e_objects_events_relations_boost`.
- Best single global run by score: Flash `variant_e_objects_events_relations_boost` on `ch_003`.

## Best Strategy
- Use Flash as cheap candidate tier with chapter/result-aware retry policy.
- Candidate overlay family should combine:
  - dense-plus-check for broad recall;
  - objects/events/relations boost for gaps;
  - strict JSON validation and density thresholds.
- Use Pro only as fallback experiment/gate, not default, based on this evidence.

## Comparison vs Manual Baselines
- Manual `ch_002` remains richer overall, especially objects/events/relations/unresolved.
- Manual `ch_003` remains richer where full semantic detail matters.
- DeepSeek Flash can approach useful coverage on selected axes but does not yet match manual baseline robustly.

## Product Decision
- Assessment: `flash_valid_but_requires_retry_policy`.
- DeepSeek Flash remains viable as low-cost extraction candidate.
- It needs strict validation, density scoring, and retry/fallback policy before product use.
- DeepSeek Pro did not clearly beat Flash in this matrix.

## What Worked
- 16-call cap respected.
- Multi-chapter validation worked via expected chapter id.
- Flash found strong candidates on both chapters.
- Pro availability was tested without OpenAI.
- Reports avoid private prompt/output text.

## What Failed
- Flash instability: 9 Flash runs invalid/failed validation.
- Some density-oriented instructions still break JSON.
- Pro did not deliver clear quality advantage.
- No single variant dominated both chapters.

## Data Written
- Runtime outputs stayed under `/tmp/textifai_deepseek_strategy_matrix`.
- Repo includes only dev scripts, tests, summary JSON reports, and handoff.

## Privacy / Non-committed Output
- No prompt text committed.
- No provider output text committed.
- No `/tmp` artifacts committed.
- No API key committed.

## Tests Added / Updated
- Updated provider-free tests for multi-chapter/multi-model scoring and strategy reports.
- Existing dry-run guard tests also cover overlay-file behavior and report privacy checks.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `tests.test_textifai_provider_onboarding` executed under isolated env without provider key to avoid known env-sensitive false negative.
- Real DeepSeek strategy matrix, `16` provider calls.
- `git status --short`
- `git diff --stat`

## Safety Constraints
- Max 16 real calls respected.
- No OpenAI.
- No chunking.
- No write-back.
- No private outputs committed.

## Known Limitations
- Only two chapters.
- Score is heuristic, not semantic truth.
- No automated deep semantic QA.
- No OpenAI runtime comparison in this phase.
- Pro results may be model/version/provider specific.

## Future Extensions
- Package candidate Flash profiles.
- Define retry/fallback thresholds.
- Run a confirmatory profile-gated call on another hard chapter.
- Return to chunking/reduction once provider strategy gate is stable.

## Runtime Changes
- Dev experiment only.
- No ingestion product runtime change.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3l — Flash Candidate Profile Packaging + Retry/Fallback Gate Definition`
