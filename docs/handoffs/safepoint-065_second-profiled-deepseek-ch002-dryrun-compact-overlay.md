# Second Profiled DeepSeek ch_002 Dry-run with Compact Overlay

## Product Reading
- `SP-060` proved DeepSeek V4 Flash can return valid JSON with generic prompt, but semantic density was thin.
- `SP-063` proved first profiled overlay applied but broke JSON parseability.
- `SP-064` revised overlay to compact, imperative, JSON-first form.
- This phase executed one guarded real call with compact overlay to verify whether JSON reliability is restored and whether density improves enough to justify next iteration.

## Scope
- Verify branch/state.
- Verify environment key visibility without exposing secret.
- Resolve `ch_002` prompt capture from `/tmp`.
- Execute exactly one real DeepSeek call with compact profile settings.
- Create summary reports and comparisons without committing private prompt/output.
- Update provider-free tests and run required validation.

## Files Changed
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_compact_profile_runtime_summary_after_sp064.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_compact_profile_vs_generic_report_after_sp064.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_compact_profile_vs_failed_profile_report_after_sp064.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_compact_profile_vs_sp056_baseline_report_after_sp064.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_compact_profile_runtime_issue_report_after_sp064.json`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `docs/handoffs/safepoint-065_second-profiled-deepseek-ch002-dryrun-compact-overlay.md`

## Environment Check
- `DEEPSEEK_API_KEY present: True`
- `DEEPSEEK_API_KEY len: 35`
- `DEEPSEEK_API_KEY sha8: 29fc730d`

## Prompt Recapture Status
- Existing prompt capture found.
- Prompt used:
  - `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260524T082129Z/request_003_bootstrap_chapter_extraction_ch_002.md`
- Recapture not required.

## Provider Profile Used
- `provider = deepseek`
- `model = deepseek-v4-flash`
- `provider_profile_requested = auto`
- `provider_profile_id = deepseek-v4-flash:bootstrap_chapter_extraction:v1`
- `provider_profile_applied = true`

## Real Provider Call Status
- `executed_one_call_compact_profile_valid_json`
- Exactly one real provider call executed.

## Output Directory
- `/tmp/textifai_real_provider_dryrun_profiled_compact/20260524T085508Z`

## Runtime JSON Validation
- `response_parseable_json = true`
- `validation_ok = true`
- `chapter_id = ch_002`
- `chapter_count = 1`
- `response_text_chars = 6968`
- `objects = 1`
- `events = 2`
- `relations = 2`
- `event_importance_present = true`
- `relation_category_present = true`

## Compact Profile vs Generic DeepSeek
- Assessment: `compact_profile_restored_json_but_still_thin`.
- Improvements vs generic `SP-060`:
  - JSON remains valid.
  - `relations`: `1 -> 2`
  - `places`: `1 -> 2`
- Regressions vs generic `SP-060`:
  - `characters`: `3 -> 1`
  - `concepts`: `4 -> 3`
  - `objects`: `2 -> 1`
  - `unresolved_mentions`: still `0`

## Compact Profile vs Failed Profile
- Assessment: `compact_profile_restored_json_but_still_thin`.
- Key difference vs failed profiled run `SP-063`:
  - parseability restored (`false -> true`);
  - minimum v2 validation restored (`false -> true`).

## Compact Profile vs SP056 Manual Baseline
- Assessment: `compact_profile_improved_but_below_manual`.
- Compact profile remains semantically thinner than `SP-056` across counts.
- Still below manual baseline for objects/events/relations and unresolved mentions.

## Semantic Density Decision
- Compact overlay fixed prior JSON parseability regression.
- Density remains below manual baseline and mixed vs generic DeepSeek.
- Decision: keep compact JSON-first profile as safer base, then choose one controlled density iteration or stronger fallback model path.

## What Improved
- JSON parseability restored under profile mode.
- Minimum v2 shape validated successfully.
- Relation coverage improved over generic runtime.
- Overlay no longer reproduces previous profiled invalid-JSON failure.

## What Stayed Weak
- Density still thin relative to manual baseline.
- `unresolved_mentions` remained empty.
- Objects/characters coverage still low.

## Provider Profile Result
- Compact overlay is viable for JSON reliability.
- Compact overlay alone is insufficient for manual-baseline-level semantic density.
- Next decision should balance one more mild density tweak vs fallback to stronger model for hard chapters.

## Data Written
- Summary JSON fixtures, issue/comparison reports, updated tests, and handoff.
- Real runtime payload stayed in `/tmp` only.

## Privacy / Non-committed Output
- No prompt/private output committed.
- No API key committed.
- No `/tmp` content committed.

## Tests Added / Updated
- Updated `tests/test_textifai_real_provider_dryrun_guards.py` to parse/check compact profile report set and asserted executed-valid-json state.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- `git status --short`
- `git diff --stat`

## Safety Constraints
- Exactly one provider call.
- No OpenAI.
- No DeepSeek Pro.
- No chunking.
- No write-back.
- No private runtime artifacts committed.

## Known Limitations
- One chapter only.
- One provider/model only.
- No DeepSeek Pro runtime comparison.
- No OpenAI runtime comparison.
- Density comparisons rely on summary metrics, not full semantic audit.

## Future Extensions
- Run one additional controlled density iteration only if JSON reliability preserved.
- Otherwise define fallback policy for hard chapters (stronger model tier).
- Re-assess readiness to return to chunking/reduction preflight after profile quality gate.

## Runtime Changes
- Reports/tests/handoff only.
- No production ingestion runtime changes.

## Provider Calls
- YES (one guarded call).

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3j — Compact Profile Density Iteration or Fallback Policy Decision`
