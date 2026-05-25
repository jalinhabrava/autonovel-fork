# Safepoint 072 — DeepSeek Targeted Ingestion Harness Improvement from Observability

## DeepSeek Targeted Ingestion Harness Improvement from Observability

## Product Reading

`SP-070` packaged DeepSeek-family profiles and `SP-071` added observability. This phase used those learnings to run targeted variants against concrete gaps: objects, events, unresolved mentions, JSON reliability, and chapter stability. The result did not clearly beat `SP-069`, so TextifAI should keep `SP-070` profiles for now.

## Scope

- Build targeted DeepSeek ingestion matrix runner.
- Generate hypothesis report before runtime.
- Execute controlled DeepSeek calls under cap.
- Produce privacy-safe metrics, failure modes, diff reports, and decision reports.
- No chunking, no OpenAI, no write-back.

## Files Changed

- `scripts/dev/deepseek_targeted_ingestion_matrix.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_hypothesis_after_sp071.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_matrix_summary_after_sp071.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_matrix_variants_after_sp071.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_ch002_report_after_sp071.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_ch003_report_after_sp071.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_targeted_ingestion_decision_after_sp071.json`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_targeted_ingestion_variant_diff_after_sp071.json`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_targeted_ingestion_failure_modes_after_sp071.json`
- `tests/test_textifai_prompt_experiment_observability.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `docs/handoffs/safepoint-072_deepseek-targeted-ingestion-harness-improvement.md`

## Observability Inputs

Read provider-free reports from:

- `SP-067` strategy matrix
- `SP-068` Flash Round 2
- `SP-069` family matrix
- `SP-071` prompt observability taxonomy and diff reports

## Hypothesis Report

Created `deepseek_targeted_ingestion_hypothesis_after_sp071.json` with:

- bottleneck: `ch_002`
- useful prior variants: `family_variant_2_oer_focus`, `family_variant_3_balanced_kb`, `variant_g_combined_best`, `variant_l_balanced_final_candidate`
- failure modes: low objects/events/relations/unresolved plus invalid JSON
- new targeted hypotheses
- items not to repeat

## Matrix Design

New variants:

- `targeted_variant_1_object_event_manifest`
- `targeted_variant_2_no_zero_sections`
- `targeted_variant_3_ch002_gap_recovery`
- `targeted_variant_4_pro_balanced_dense`
- `targeted_variant_5_json_shape_anchor`

## Models Tested

- `deepseek-v4-flash`
- `deepseek-v4-pro`

## Variants Executed

- Flash: ch_002 variants 1/2/3/5, ch_003 variants 1/2/5
- Pro: completed selected ch_002/ch_003 runs; some Pro calls stalled and were cancelled to keep runtime bounded

## Provider Calls

- Completed calls: 11
- Incomplete/cancelled calls: 2
- Approved cap: 16

## Runtime Validation

- Flash valid JSON on several runs, but ch_002 stayed below `SP-069` best.
- Pro produced valid ch_002 outputs, but did not beat `SP-069` score.
- Pro ch_003 balanced run returned empty/non-parseable output.

## ch_002 Results

Best targeted ch_002:

- model: `deepseek-v4-pro`
- variant: `targeted_variant_1_object_event_manifest`
- score: `23.5`
- counts: `characters=3 places=1 concepts=0 objects=3 events=2 relations=4 unresolved=0`

SP-069 ch_002 benchmark remains better:

- Flash + `family_variant_2_oer_focus`
- score: `26.5`

## ch_003 Results

Best targeted ch_003:

- model: `deepseek-v4-flash`
- variant: `targeted_variant_1_object_event_manifest`
- score: `23.5`
- counts: `characters=2 places=2 concepts=1 objects=3 events=2 relations=3 unresolved=1`

SP-069 ch_003 benchmark remains better:

- Pro + `family_variant_3_balanced_kb`
- score: `25.0`

## Failure Mode Findings

Observed:

- `valid_json_low_objects`
- `valid_json_low_events`
- `valid_json_low_relations`
- `valid_json_zero_unresolved`
- `invalid_json_unknown`
- `provider_empty_response`
- `provider_error`

## Variant Diff Findings

- `targeted_variant_1_object_event_manifest` has useful signal and better OER shape, but remains below SP-069.
- `targeted_variant_2_no_zero_sections` did not recover enough density.
- `targeted_variant_3_ch002_gap_recovery` was unstable.
- `targeted_variant_4_pro_balanced_dense` valid on ch_002, unstable on ch_003.
- `targeted_variant_5_json_shape_anchor` did not solve reliability/density tradeoff.

## Best Model/Variant

- Best overall targeted run: Flash `targeted_variant_1_object_event_manifest` on `ch_003`, score `23.5`.
- Best targeted ch_002 run: Pro `targeted_variant_1_object_event_manifest`, score `23.5`.

## Comparison vs SP069

- `ch_002`: targeted best `23.5` vs SP-069 best `26.5` → no improvement.
- `ch_003`: targeted best `23.5` vs SP-069 best `25.0` → no improvement.

## Profile Update Decision

Do not update packaged profiles.
Retain:

- `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`
- `deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1`

## Product Decision

Assessment: `deepseek_ingestion_harness_no_clear_improvement`

## What Worked

- Observability made variant outcomes explainable.
- `targeted_variant_1_object_event_manifest` recovered some objects/events and unresolved mentions.
- Targeted reports identify why no profile update is justified.

## What Failed

- No new variant beat SP-069 scores.
- Some aggressive variants broke JSON.
- Pro had stalled/empty runs in targeted setting.

## Data Written

- Runtime artifacts stayed in `/tmp`.
- Repo contains only privacy-safe reports, scripts, tests, and handoff.

## Privacy / Non-committed Output

- No prompt text committed.
- No provider output committed.
- No API key committed.
- No `/tmp` artifacts committed.

## Tests Added / Updated

- Updated `tests/test_textifai_prompt_experiment_observability.py`.
- Updated `tests/test_textifai_real_provider_dryrun_guards.py`.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- Targeted DeepSeek matrix real run under cap
- `git status --short`
- `git diff --stat`

## Safety Constraints

- No OpenAI.
- No chunking.
- No write-back.
- No commit of `/tmp`.
- No prompt/output private content in repo.

## Known Limitations

- Pro calls were partly manual after matrix stall.
- Results cover only `ch_002`/`ch_003`.
- Failure classification remains metadata-based.

## Future Extensions

- Improve per-call timeout handling for all dev matrix scripts.
- Add runtime-generated observability reports directly from matrix runner.
- Revisit tuning only after chunking/reduction changes input shape.

## Runtime Changes

- Dev experiment script only.
- No production ingestion runtime change.
- No schema change.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4b — Chunking/Reduction Preflight with SP070 DeepSeek Profiles`
