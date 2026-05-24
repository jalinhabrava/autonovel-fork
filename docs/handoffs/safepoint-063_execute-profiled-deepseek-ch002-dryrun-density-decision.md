# Execute Profiled DeepSeek ch_002 Dry-run + Density Decision

## Product Reading
- `SP-062` left the profiled DeepSeek runtime decision blocked by environment visibility.
- This phase re-checked whether Codex could see `DEEPSEEK_API_KEY` and whether local prompt capture existed.
- Provider call remained forbidden because Codex still could not see the key.

## Scope
- Verify branch and environment.
- Verify prompt capture availability.
- Execute exactly one profiled DeepSeek call only if all guards passed.
- Otherwise, produce safe not-executed reports and handoff.

## Files Changed
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_runtime_summary_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_vs_generic_report_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_vs_sp056_baseline_report_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_provider_profile_runtime_issue_report_after_sp062.json`
- `docs/handoffs/safepoint-063_execute-profiled-deepseek-ch002-dryrun-density-decision.md`

## Environment Check
- `DEEPSEEK_API_KEY present: False`
- `DEEPSEEK_API_KEY len: 0`
- No key hash available because key was absent.
- Conclusion: provider call prohibited in this environment.

## Prompt Recapture Status
- Not attempted.
- Reason: key missing in Codex environment already blocked provider execution.

## Provider Profile Used
- Intended profile: `deepseek-v4-flash:bootstrap_chapter_extraction:v1`
- Intended mode: `--provider-profile auto`

## Real Provider Call Status
- `not_executed_missing_key_in_codex_environment`
- No provider call executed.

## Output Directory
- None. No profiled runtime directory was created.

## Runtime JSON Validation
- Not evaluated.
- No profiled runtime payload exists in this environment.

## Profiled vs Generic DeepSeek
- `overall_assessment = profile_call_failed`
- Generic `SP-060` remains last valid runtime reference.

## Profiled vs SP056 Manual Baseline
- `overall_assessment = profiled_deepseek_invalid`
- Reason: no profiled runtime output exists to compare.

## Semantic Density Decision
- Not finalized.
- Current state: density effect of profile remains unmeasured in runtime.

## What Improved
- Environment failure now classified precisely as Codex key visibility issue.
- New expected reports and tests capture this state explicitly.

## What Stayed Weak
- Still no profiled runtime output.
- No semantic density verdict beyond generic `SP-060` result.

## Provider Profile Result
- Profile infrastructure remains ready.
- Runtime effect remains unverified until Codex can read the key and prompt capture exists.

## Data Written
- Only summary fixtures, tests, and handoff.
- No `/tmp` provider output committed.

## Privacy / Non-committed Output
- No private prompt/output committed.
- No API key stored in fixtures or docs.

## Tests Added / Updated
- Updated `tests/test_textifai_real_provider_dryrun_guards.py` for new `after_sp062` reports and missing-key-in-Codex state.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `uv run python -m unittest -v tests.test_textifai_provider_onboarding`

## Safety Constraints
- No provider call.
- No OpenAI.
- No DeepSeek Pro.
- No chunking.
- No write-back.

## Known Limitations
- Codex environment still does not see `DEEPSEEK_API_KEY`.
- Prompt capture search was moot once key visibility failed.
- Density decision cannot be finalized until one profiled runtime call exists.

## Future Extensions
- Make Codex environment load provider key.
- Re-run exactly one profiled DeepSeek `ch_002` call.
- If output improves, decide whether to iterate Flash profile or compare against Pro/OpenAI.

## Runtime Changes
- Reports only.
- No product runtime changes.

## Provider Calls
- NO.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3h — Fix Codex Environment Provider Key Visibility and Execute Single Profiled DeepSeek Call`
