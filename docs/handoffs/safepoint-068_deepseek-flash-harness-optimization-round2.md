# DeepSeek Flash Harness Optimization Round 2

## Product Reading
- TextifAI is BYOK: user picks provider/model and supplies key.
- Product value is not hidden provider routing; value is optimized harness for chosen model.
- `SP-067` showed Flash has useful signal but unstable behavior across prompts.
- This phase focused only on DeepSeek V4 Flash and iterated harness variants G-L across `ch_002` and `ch_003`.

## Scope
- Verify branch, key visibility, and local prompts.
- Reuse and extend matrix runner for a Flash-only `round2` variant set.
- Execute 12 guarded Flash calls across two chapters.
- Publish only summary reports, tests, and handoff.

## Files Changed
- `scripts/dev/deepseek_prompt_matrix.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_flash_harness_round2_summary_after_sp067.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_flash_harness_round2_variants_after_sp067.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_flash_harness_round2_ch002_report_after_sp067.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_flash_harness_round2_ch003_report_after_sp067.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_flash_harness_round2_decision_after_sp067.json`
- `docs/handoffs/safepoint-068_deepseek-flash-harness-optimization-round2.md`

## Environment Check
- provider key present in Codex environment: `true`
- provider key length observed: `35`
- provider key sha8 observed: `29fc730d`

## Prompt Status
- `ch_002` prompt recaptured and found under `/tmp`.
- `ch_003` prompt recaptured and found under `/tmp`.
- No prompt text committed.

## Round 2 Matrix Design
- Model: `deepseek-v4-flash` only.
- No Pro.
- No OpenAI.
- Chapters: `ch_002`, `ch_003`.
- Variants: `g` through `l`.
- Max output tokens: `8192`.
- JSON mode enabled.
- No write-back.
- Max real calls allowed: `12`.
- Real calls executed: `12`.

## Variants Executed
- `variant_g_combined_best`
- `variant_h_counts_targeted`
- `variant_i_schema_section_completion`
- `variant_j_review_and_unresolved_boost`
- `variant_k_objects_events_relations_v2`
- `variant_l_balanced_final_candidate`

## Provider Calls
- `12` real Flash calls.
- Within approved cap.

## Runtime Validation
- Valid runs: `9`
- Invalid or failed validation runs: `3`
- Flash is better behaved than in `SP-067`, but not yet stable enough to call harness complete.

## ch_002 Results
- Best variant: `variant_l_balanced_final_candidate`
- Score: `21.5`
- Counts:
  - `characters=3`
  - `places=1`
  - `concepts=4`
  - `objects=0`
  - `events=1`
  - `relations=4`
  - `unresolved_mentions=0`
- Interpretation: relation coverage improved, but objects/unresolved remain weak and score did not meet candidate threshold.

## ch_003 Results
- Best variant: `variant_g_combined_best`
- Score: `26.5`
- Counts:
  - `characters=2`
  - `places=3`
  - `concepts=2`
  - `objects=2`
  - `events=3`
  - `relations=3`
  - `unresolved_mentions=2`
- Interpretation: strong Flash candidate on `ch_003`, especially on places/events/unresolved.

## Best Variant
- Global best run: `variant_g_combined_best` on `ch_003`, score `26.5`.

## Best Harness Candidate
- Chapter-aware candidate set, not one universal winner yet:
  - `ch_002`: `variant_l_balanced_final_candidate`
  - `ch_003`: `variant_g_combined_best`
- This is not enough to declare final harness v1 because `ch_002` stayed below target score `25`.

## Comparison vs Previous Matrix
- `SP-067` best `ch_002`: Flash `variant_b_dense_plus_check`, score `25.0`.
- `SP-068` best `ch_002`: Flash `variant_l_balanced_final_candidate`, score `21.5`.
- `SP-067` best `ch_003`: Flash `variant_e_objects_events_relations_boost`, score `26.0`.
- `SP-068` best `ch_003`: Flash `variant_g_combined_best`, score `26.5`.
- Net: round2 improved `ch_003` slightly, but regressed `ch_002` candidate score.

## Comparison vs Manual Baselines
- `ch_002` still well below `SP-056` manual baseline, especially for objects/events/unresolved.
- `ch_003` still below `SP-057` manual baseline, but closer on some structural axes.
- Manual baselines remain richer and more balanced than Flash outputs.

## Product Decision
- Assessment: `deepseek_flash_harness_needs_more_iteration`.
- Reason:
  - at least one valid variant per chapter exists;
  - `ch_003` crossed target score `25`;
  - `ch_002` did not;
  - valid rate improved, but top harness still not stable and balanced enough across both chapters.

## BYOK Product Interpretation
- TextifAI should not auto-switch provider/model here.
- Correct BYOK interpretation:
  - user chooses DeepSeek Flash;
  - TextifAI provides best-known harness/profile for that chosen model;
  - TextifAI warns when output is thin or unstable;
  - TextifAI can suggest rerun profiles for the same chosen model.

## What Worked
- Flash-only round2 executed within cap.
- `variant_g_combined_best` proved useful on `ch_003`.
- `variant_l_balanced_final_candidate` gave coherent valid JSON on `ch_002`.
- Overall valid rate reached `9/12`.

## What Failed
- `ch_002` still did not reach target score `25`.
- Objects and unresolved mentions remain inconsistent.
- Some variants still broke JSON or failed validation.
- No single overlay generalized cleanly across both chapters.

## Data Written
- Runtime outputs stayed under `/tmp/textifai_deepseek_flash_harness_round2`.
- Repo contains only summary reports, tests, and handoff.

## Privacy / Non-committed Output
- No prompt text committed.
- No provider output text committed.
- No `/tmp` artifacts committed.
- No API key committed.

## Tests Added / Updated
- Added provider-free checks for round2 report parsing, enum validity, and work-agnostic round2 variant definitions.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `tests.test_textifai_provider_onboarding` executed under isolated env without provider key to avoid known env-sensitive false negative.
- Real Flash round2 matrix: `12` calls.
- `git status --short`
- `git diff --stat`

## Safety Constraints
- Flash only.
- No Pro.
- No OpenAI.
- No chunking.
- No write-back.
- No private runtime artifacts committed.

## Known Limitations
- Only two chapters.
- Heuristic scoring, not full semantic QA.
- Harness still chapter-sensitive.
- `ch_002` remains harder than `ch_003` for Flash.

## Future Extensions
- Package `variant_g`/`variant_l` as chapter-aware candidate harness overlays.
- Re-run one stability check on `ch_002` with narrowed candidates only.
- Add density warnings and rerun guidance for same selected model.

## Runtime Changes
- Dev experiment only.
- No product schema or ingestion runtime change.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3m — DeepSeek Flash Harness Candidate Packaging + Stability Re-check`
