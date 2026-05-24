# DeepSeek Prompt Experiment Matrix ch_002

## Product Reading
- `SP-060` proved generic DeepSeek V4 Flash can produce valid JSON but thin extraction.
- `SP-063` proved the first profiled density overlay applied but broke JSON parseability.
- `SP-064` made the overlay compact and JSON-first.
- `SP-065` restored JSON validity with compact overlay but density still stayed below `SP-056` manual baseline.
- This phase moved from single-overlay tuning to a controlled prompt experiment matrix to identify which instruction shape helps DeepSeek Flash produce denser extraction without losing JSON.

## Scope
- Verify branch and environment.
- Reuse existing `ch_002` captured prompt from `/tmp`.
- Add dev-only overlay file support to `real_provider_dryrun.py`.
- Add `deepseek_prompt_matrix.py` for bounded provider experiment orchestration.
- Execute four new runtime variants plus two reference variants, total real calls = 4.
- Commit only metrics/reports/conclusions, no private prompts or outputs.

## Files Changed
- `scripts/dev/real_provider_dryrun.py`
- `scripts/dev/deepseek_prompt_matrix.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_prompt_matrix_summary_after_sp065.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_prompt_matrix_variant_report_after_sp065.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_prompt_matrix_decision_after_sp065.json`
- `docs/handoffs/safepoint-066_deepseek-prompt-experiment-matrix-ch002.md`

## Environment Check
- provider key present in Codex environment: `true`
- provider key length observed: `35`
- provider key sha8 observed: `29fc730d`

## Prompt Status
- Existing prompt found:
  - `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260524T082129Z/request_003_bootstrap_chapter_extraction_ch_002.md`
- Prompt sha256:
  - `74c437e8ed878d16eb7b7a2636b5cff6a51353ee632cd0c188f210e8c6ff677d`
- No prompt text committed.

## Matrix Design
- Provider/model: `deepseek` / `deepseek-v4-flash`.
- `max_output_tokens = 8192`.
- `response_format_json = true`.
- `no_write_back = true`.
- Output root: `/tmp/textifai_deepseek_prompt_matrix_ch002`.
- Variants 1 and 2 reused existing references.
- Variants 3–6 executed as real calls.

## Variants Executed
- Reference only:
  - `variant_01_generic_reference`
  - `variant_02_compact_json_first`
- Executed runtime:
  - `variant_03_dense_explicit`
  - `variant_04_section_targets`
  - `variant_05_internal_coverage_check`
  - `variant_06_json_skeleton_reinforcement`

## Provider Calls
- Real provider calls executed: `4`.
- Limit requested by phase: maximum `6`.
- No OpenAI calls.
- No DeepSeek Pro calls.

## Runtime Validation
- Valid JSON variants:
  - `variant_01_generic_reference`
  - `variant_02_compact_json_first`
  - `variant_03_dense_explicit`
  - `variant_05_internal_coverage_check`
  - `variant_06_json_skeleton_reinforcement`
- Invalid JSON variant:
  - `variant_04_section_targets`

## Variant Comparison
- `variant_03_dense_explicit`: score `17.0`, counts `characters=4 places=1 concepts=3 objects=1 events=1 relations=3 unresolved=0`.
- `variant_05_internal_coverage_check`: score `16.5`, counts `characters=3 places=1 concepts=4 objects=0 events=1 relations=2 unresolved=3`.
- `variant_02_compact_json_first`: score `14.5`, counts `characters=1 places=2 concepts=3 objects=1 events=2 relations=2 unresolved=0`.
- `variant_06_json_skeleton_reinforcement`: score `9.0`, thin but valid.
- `variant_04_section_targets`: invalid JSON, disqualified.

## Best Variant
- `variant_03_dense_explicit`.
- Product rationale:
  - highest weighted score;
  - valid JSON;
  - restores character coverage to manual baseline count;
  - improves relation count vs generic and compact references.

## Comparison vs Generic SP060
- Generic `SP-060` remained valid but thin.
- `variant_03_dense_explicit` improved weighted score and relation count.
- Tradeoff: fewer objects/events than manual baseline and no unresolved mentions.

## Comparison vs Compact SP065
- Compact `SP-065` restored JSON but stayed thin.
- `variant_03_dense_explicit` improved weighted score and character/relation coverage.
- `variant_05` is notable because it recovered unresolved mentions, but dropped objects to zero.

## Comparison vs Manual SP056
- Manual baseline remains richer overall.
- `variant_03_dense_explicit` is closer for characters and relations but still below for places, objects, events, and unresolved mentions.
- Decision: promising Flash candidate found, not final manual-quality replacement.

## Product Decision
- Assessment: `flash_profile_candidate_found`.
- DeepSeek V4 Flash should not be dismissed yet.
- Best next step is one confirmatory candidate run or a profile update based on `variant_03_dense_explicit`, with guardrails for JSON and density.

## What Worked
- Small matrix stayed within provider call budget.
- JSON-first plus dense explicit wording produced best score.
- Internal coverage check recovered unresolved mentions.
- Scoring made tradeoffs visible without relying on raw private output.

## What Failed
- Section-target overlay broke JSON.
- No variant matched manual baseline density.
- No single variant recovered all target sections strongly.

## Data Written
- Runtime artifacts stayed under `/tmp/textifai_deepseek_prompt_matrix_ch002`.
- Repo contains only summary JSON reports, dev script, tests, and handoff.

## Privacy / Non-committed Output
- No prompt text committed.
- No provider output committed.
- No API key committed.
- No `/tmp` artifacts committed.

## Tests Added / Updated
- Added provider-free tests for prompt overlay file behavior.
- Added provider-free tests for matrix variant definitions and scoring.
- Added report parsing and candidate-state assertions.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- DeepSeek matrix real run with 4 provider calls.
- `git status --short`
- `git diff --stat`

## Safety Constraints
- Maximum 6 calls allowed; 4 calls executed.
- No OpenAI.
- No DeepSeek Pro.
- No chunking.
- No write-back.
- No private output committed.

## Known Limitations
- One chapter only.
- DeepSeek Flash only.
- Metrics are count/score based, not full semantic QA.
- `variant_03` may need confirmatory repeat before becoming profile default.

## Future Extensions
- Convert `variant_03_dense_explicit` into candidate profile overlay.
- Run one confirmatory call against `ch_002` or a harder chapter.
- If unstable, evaluate fallback policy or stronger provider/model.

## Runtime Changes
- Dev-only scripts/options only.
- No product ingestion runtime changes.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3k — Confirmatory Flash Candidate Run and Fallback Gate`
