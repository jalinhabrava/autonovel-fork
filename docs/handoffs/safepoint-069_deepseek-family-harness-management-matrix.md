# DeepSeek Family Harness Management Matrix

## Product Reading
- TextifAI remains BYOK: user enables concrete models; TextifAI adapts to enabled set.
- Product value is model harness quality (prompt/profile, budget, reliability, density checks), not hidden provider routing.
- `SP-068` improved Flash but left chapter imbalance (`ch_002` harder than `ch_003`).
- This phase expands from Flash-only to DeepSeek-family management over actually available DeepSeek models.

## Scope
- Verify branch/key/prompts.
- Run DeepSeek model discovery `/models`.
- Execute DeepSeek-family matrix on available models only.
- Compare chapter results, model behavior, and profile needs.
- Publish reports/handoff/tests only.

## Files Changed
- `scripts/dev/deepseek_model_discovery.py`
- `scripts/dev/deepseek_family_harness_matrix.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_model_discovery_after_sp068.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_harness_matrix_summary_after_sp068.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_harness_matrix_variants_after_sp068.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_harness_ch002_report_after_sp068.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_harness_ch003_report_after_sp068.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_family_harness_decision_after_sp068.json`
- `docs/handoffs/safepoint-069_deepseek-family-harness-management-matrix.md`

## Environment Check
- provider key present in Codex environment: `true`
- provider key length observed: `35`
- provider key sha8 observed: `29fc730d`

## Model Discovery
- Discovery status: `completed`
- Visible models:
  - `deepseek-v4-flash`
  - `deepseek-v4-pro`
- Reasoner/thinking alias discovered: none.
- Chat alias discovered: none.
- No model discovery failure.

## Prompt Status
- `ch_002` and `ch_003` prompts were recaptured and found under `/tmp`.
- `ch_002` prompt sha256: `74c437e8ed878d16eb7b7a2636b5cff6a51353ee632cd0c188f210e8c6ff677d`
- `ch_003` prompt sha256: `6dda905f672bddffe6794d9d79e6850fe11e3851e654265cdc8832d793feb7c7`
- No prompt text committed.

## Matrix Design
- Provider: `deepseek`
- Models tested (available):
  - `deepseek-v4-flash`
  - `deepseek-v4-pro`
- Chapters:
  - `ch_002` with family variants `1-4`
  - `ch_003` with family variants `1-3`
- Max output tokens: `8192`
- JSON mode: enabled
- Write-back: disabled
- Planned calls: `14`
- Executed calls: `14`

## Models Tested
- Flash and Pro tested directly.
- No reasoner model was visible, so reasoner path skipped by discovery fact (not by policy).

## Variants Executed
- `family_variant_1_broad_recall`
- `family_variant_2_oer_focus`
- `family_variant_3_balanced_kb`
- `family_variant_4_ch002_gap_attack`

## Provider Calls
- Total real calls: `14`
- Within approved cap (`<=24`)

## Runtime Validation
- Mixed stability across family variants.
- Best valid runs reached `score >= 25` on both chapters.
- Some model+variant combinations still produced invalid JSON / failed validation.

## ch_002 Results
- Best run:
  - model: `deepseek-v4-flash`
  - variant: `family_variant_2_oer_focus`
  - score: `26.5`
  - counts: `characters=3 places=2 concepts=4 objects=4 events=1 relations=3 unresolved=0`
- Secondary strong run:
  - Flash `family_variant_4_ch002_gap_attack`, score `25.0`
- Observation:
  - Flash outperformed Pro on `ch_002` in this matrix.

## ch_003 Results
- Best run:
  - model: `deepseek-v4-pro`
  - variant: `family_variant_3_balanced_kb`
  - score: `25.0`
  - counts: `characters=2 places=2 concepts=3 objects=3 events=1 relations=4 unresolved=0`
- Best Flash on `ch_003`:
  - `family_variant_2_oer_focus`, score `19.5`
- Observation:
  - Pro outperformed Flash on `ch_003` in this matrix.

## Best Model/Variant
- Chapter-specific bests differ:
  - `ch_002`: Flash + `family_variant_2_oer_focus`
  - `ch_003`: Pro + `family_variant_3_balanced_kb`

## Common Family Harness Viability
- `viable = false` for a single shared model+variant across both chapters.
- Reason:
  - best chapter outcomes require different model+variant combinations.

## Per-model Profile Needs
- `deepseek-v4-flash`: needs dedicated profile tuning, strongest currently on `ch_002` via variant 2.
- `deepseek-v4-pro`: needs dedicated profile tuning, strongest currently on `ch_003` via variant 3.
- Family harness should support per-model profiles under one DeepSeek management layer.

## BYOK Product Interpretation
- Keep user control explicit: model choice remains user-selected.
- TextifAI should expose:
  - discovered DeepSeek model list;
  - per-model harness quality;
  - per-model warnings;
  - same-provider rerun guidance.
- No invisible provider switching introduced.

## Thin Output Warnings
- Warn when score is low (`<20`) even if JSON is valid.
- Warn when objects/events/relations are sparse for structurally dense chapters.
- Warn when unresolved mentions collapse to zero in ambiguous narrative zones.
- Suggest rerun profile/model within DeepSeek family only (BYOK-safe guidance).

## Product Decision
- Assessment: `deepseek_family_harness_candidate_found`
- Interpretation:
  - DeepSeek family can be treated as usable for low-cost e2e experiments,
  - but with per-model harness profiles, not one universal overlay.

## What Worked
- Discovery-driven model set avoided testing unavailable models.
- Family matrix reached >=25 score on both chapters.
- Chapter bottleneck handling improved (`ch_002` no longer strictly sub-25).
- Reports capture model-level and chapter-level tradeoffs.

## What Failed
- No single model/variant generalized best across both chapters.
- Several Pro/Flash combinations still invalid or unstable.
- Unresolved mention recall still inconsistent in top runs.

## Data Written
- Runtime artifacts remained in `/tmp` only.
- Repo received only summary fixtures, tests, scripts, and handoff.

## Privacy / Non-committed Output
- No private prompt text committed.
- No provider output text committed.
- No `/tmp` artifacts committed.
- No API key committed.

## Tests Added / Updated
- Added provider-free checks for:
  - family model discovery report parsing;
  - family matrix report parsing;
  - family decision enum validity;
  - family variant definitions free of OnT-specific names.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `tests.test_textifai_provider_onboarding` executed under isolated env without provider key
- DeepSeek-family matrix real run: `14` calls
- `git status --short`
- `git diff --stat`

## Safety Constraints
- No OpenAI.
- No chunking.
- No write-back.
- No commit of private runtime artifacts.
- Provider calls stayed under approved cap.

## Known Limitations
- Reasoner model not available in discovery at test time.
- Scoring remains heuristic, not semantic gold truth.
- Only two chapters tested.
- Stability still uneven across variants.

## Future Extensions
- Package per-model DeepSeek profiles (Flash v1, Pro v1).
- Add in-model rerun guidance and warnings to harness output.
- Re-test on additional hard chapters before broader e2e claims.

## Runtime Changes
- Dev experiment scripts only.
- No product schema change.
- No ingestion runtime wiring change.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3n — DeepSeek Family Profile Packaging + BYOK In-Model Rerun Guidance`
